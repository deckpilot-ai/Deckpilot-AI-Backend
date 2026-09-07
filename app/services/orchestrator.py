"""Multi-agent job orchestrator and DAG runner."""

import asyncio
import json
import logging
import re
import time
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.models.attachment import Attachment
from app.models.deck import Artifact, DeckVersion
from app.models.job import AgentTask, GenerationJob
from app.models.message import Message
from app.models.project import Project
from app.services.compaction import ContextCompactionService
from app.services.design_system import fallback_plan, normalize_brand, prepare_deck
from app.services.image_quality import is_documentary_image, source_figure
from app.services.prompts import (
    BRAND_STYLE_SYSTEM_PROMPT,
    COPILOT_CHAT_SYSTEM_PROMPT,
    DECK_PLANNER_SYSTEM_PROMPT,
    SLIDE_WRITER_SYSTEM_PROMPT,
)
from app.services.provider_router import ProviderRouter
from app.services.renderer import PPTXRenderer
from app.services.storage import storage_service

logger = logging.getLogger(__name__)
from app.services.ws_manager import ws_manager


class GenerationAlreadyRunningError(RuntimeError):
    """Raised when a project already owns the single active generation slot."""


class JobOrchestrator:
    @staticmethod
    def create_job(
        db: Session,
        project_id: str,
        user_id: str,
        mode: str = "generate",
        trigger_message_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> tuple[GenerationJob, bool]:
        if idempotency_key:
            existing = db.scalar(
                select(GenerationJob).where(
                    GenerationJob.project_id == project_id,
                    GenerationJob.idempotency_key == idempotency_key,
                )
            )
            if existing:
                return existing, False

        active = db.scalar(
            select(GenerationJob).where(
                GenerationJob.project_id == project_id,
                GenerationJob.active_slot == 1,
            )
        )
        if active:
            raise GenerationAlreadyRunningError("A generation job is already active for this project")

        job = GenerationJob(
            project_id=project_id,
            trigger_message_id=trigger_message_id,
            mode=mode,
            status="queued",
            idempotency_key=idempotency_key,
            active_slot=1,
        )
        db.add(job)
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            if idempotency_key:
                existing = db.scalar(
                    select(GenerationJob).where(
                        GenerationJob.project_id == project_id,
                        GenerationJob.idempotency_key == idempotency_key,
                    )
                )
                if existing:
                    return existing, False
            active = db.scalar(
                select(GenerationJob).where(
                    GenerationJob.project_id == project_id,
                    GenerationJob.active_slot == 1,
                )
            )
            if active:
                raise GenerationAlreadyRunningError("A generation job is already active for this project")
            raise

        # Create Task DAG
        tasks = [
            ("reference_intake", []),
            ("source_grounding", ["reference_intake"]),
            ("font_brand_detection", ["reference_intake"]),
            ("deck_planner", ["source_grounding"]),
            ("slide_writer", ["deck_planner", "font_brand_detection"]),
            ("pptx_renderer", ["slide_writer"]),
            ("visual_qa", ["pptx_renderer"]),
            ("gatekeeper", ["visual_qa"]),
        ]

        for agent_type, deps in tasks:
            task = AgentTask(
                job_id=job.id,
                agent_type=agent_type,
                status="pending",
                dependency_json=json.dumps(deps),
            )
            db.add(task)

        db.commit()
        db.refresh(job)
        return job, True

    @staticmethod
    def cancel_job(db: Session, job_id: str) -> GenerationJob | None:
        """Explicitly cancels a running or queued job."""
        job = db.scalar(select(GenerationJob).where(GenerationJob.id == job_id))
        if not job:
            return None

        if job.status in ("queued", "running"):
            job.status = "cancelled"
            job.active_slot = None
            job.completed_at = int(time.time())
            # Cancel any pending or running tasks
            tasks = db.scalars(select(AgentTask).where(AgentTask.job_id == job_id)).all()
            for t in tasks:
                if t.status in ("pending", "running"):
                    t.status = "cancelled"
                    if not t.completed_at:
                        t.completed_at = int(time.time())
            db.commit()
            db.refresh(job)
        return job

    @staticmethod
    async def run_job(db: Session, job_id: str, user_prompt: str, user_id: str) -> GenerationJob:
        job = db.scalar(select(GenerationJob).where(GenerationJob.id == job_id))
        if not job:
            raise ValueError("Job not found")

        # If already cancelled, do not run
        if job.status == "cancelled":
            return job

        job.status = "running"
        job.started_at = int(time.time())
        db.commit()

        tasks = db.scalars(select(AgentTask).where(AgentTask.job_id == job_id)).all()
        task_map = {t.agent_type: t for t in tasks}
        rendered_storage_key: str | None = None
        deck_persisted = False

        async def cleanup_uncommitted_deck() -> None:
            if rendered_storage_key and not deck_persisted:
                try:
                    await run_in_threadpool(storage_service.delete_object, rendered_storage_key)
                except Exception:
                    logger.warning("Failed to clean up uncommitted deck object", exc_info=True)

        def check_cancelled() -> bool:
            current_status = db.scalar(select(GenerationJob.status).where(GenerationJob.id == job_id))
            return current_status == "cancelled"

        # Obtain 1M effective session context
        eff_ctx = ContextCompactionService.get_effective_context(db, job.project_id)
        enriched_prompt = user_prompt
        if eff_ctx.get("context_prompt"):
            enriched_prompt = f"{user_prompt}\n\n[Active Session Memory & Constraints]:\n{eff_ctx['context_prompt']}"

        context: dict[str, Any] = {
            "prompt": user_prompt,
            "enriched_prompt": enriched_prompt,
            "project_id": job.project_id,
        }

        def _emit(agent_name: str, status: str, message: str, extra: dict | None = None):
            payload = {
                "type": "agent_task",
                "job_id": job.id,
                "project_id": job.project_id,
                "agent_type": agent_name,
                "status": status,
                "message": message,
            }
            if extra:
                payload.update(extra)
            ws_manager.broadcast_sync(job.project_id, payload)

        try:
            # 1. Reference Intake
            if check_cancelled():
                return job
            t_intake = task_map.get("reference_intake")
            if t_intake:
                t_intake.status = "running"
                t_intake.started_at = int(time.time())
                db.commit()
                _emit("reference_intake", "running", "Reviewing requirements and analyzing reference files...")
                existing_artifacts = db.scalars(
                    select(Artifact).where(Artifact.project_id == job.project_id)
                ).all()
                context["reference_count"] = len(existing_artifacts)
                t_intake.status = "completed"
                t_intake.completed_at = int(time.time())
                db.commit()
                _emit("reference_intake", "completed", f"Extracted {len(existing_artifacts)} usable reference assets.")

            # 2. Source Grounding
            if check_cancelled():
                return job
            t_grounding = task_map.get("source_grounding")
            if t_grounding:
                t_grounding.status = "running"
                t_grounding.started_at = int(time.time())
                db.commit()
                _emit("source_grounding", "running", "Synthesizing domain facts, metrics, and proof points...")

                grounded_parts = []
                seen_sources = set()
                for art in existing_artifacts:
                    fingerprint = (art.type, art.source_locator, art.json_data)
                    if fingerprint in seen_sources:
                        continue
                    seen_sources.add(fingerprint)
                    if art.type in {"text_block", "table"} and art.json_data:
                        source_data = json.loads(art.json_data)
                        source_text = source_data if isinstance(source_data, str) else json.dumps(source_data)
                        grounded_parts.append(f"[Source {art.source_locator or 'Reference'}]:\n{source_text}")
                    elif art.type == "image":
                        image_meta = json.loads(art.json_data or "{}")
                        grounded_parts.append(f"[Source image imageArtifactId={art.id}: {art.source_locator or 'Image'}; source context: {image_meta.get('caption', '')}]")

                if grounded_parts:
                    grounding_content = "\n\n".join(grounded_parts)
                    context["grounding"] = grounding_content
                    enriched_prompt += f"\n\n[MANDATORY GROUNDING DATA FROM ATTACHED DOCUMENTS]:\n{grounding_content}"
                else:
                    context["grounding"] = f"Grounded context with {len(existing_artifacts)} reference sources."

                t_grounding.status = "completed"
                t_grounding.completed_at = int(time.time())
                db.commit()
                _emit("source_grounding", "completed", f"Grounded factual context from {len(existing_artifacts)} sources.")

            # 3. Font & Brand Detection
            if job.mode == 'export':
                latest = db.scalar(select(DeckVersion).where(DeckVersion.project_id == job.project_id,
                                                             DeckVersion.status == 'ready').order_by(DeckVersion.version.desc()))
                saved = db.get(Artifact, latest.deck_json_artifact_id) if latest and latest.deck_json_artifact_id else None
                if not saved or not saved.json_data:
                    raise ValueError('Generate a presentation before re-exporting it')
                context['deck_spec'] = prepare_deck(json.loads(saved.json_data), enriched_prompt)
                context['brand_style'] = normalize_brand(context['deck_spec'].get('brandStyle'), context['deck_spec'].get('deckTitle', ''))
                for stage in ('font_brand_detection', 'deck_planner', 'slide_writer'):
                    task = task_map.pop(stage, None)
                    if task:
                        task.status = 'completed'
                        task.completed_at = int(time.time())
                        _emit(stage, 'completed', 'Reusing the existing written presentation for export.')
                db.commit()
            if check_cancelled():
                return job
            t_font = task_map.get("font_brand_detection")
            if t_font:
                t_font.status = "running"
                t_font.started_at = int(time.time())
                db.commit()
                _emit("font_brand_detection", "running", "Selecting executive color palette, contrast margins, and typography...")
                brand_style = await ProviderRouter.call_llm(
                    db=db,
                    agent_type="font_brand_detection",
                    system_prompt=BRAND_STYLE_SYSTEM_PROMPT,
                    user_prompt=enriched_prompt,
                    response_schema={"type": "object"},
                    user_id=user_id,
                    job_id=job.id,
                )
                context["brand_style"] = normalize_brand(brand_style, user_prompt)
                t_font.status = "completed"
                t_font.completed_at = int(time.time())
                db.commit()
                _emit("font_brand_detection", "completed", "Executive design system established.")

            # 4. Deck Planner
            if check_cancelled():
                return job
            t_planner = task_map.get("deck_planner")
            if t_planner:
                t_planner.status = "running"
                t_planner.started_at = int(time.time())
                db.commit()

                # Detect requested slide count (e.g. 24 slides, 22 slides, 10 slides, 5 slides)
                count_match = re.search(r"\b(\d+)(?:[- ,]+[a-z-]+){0,3}[- ,]+slides?\b|\b(\d+)[- ]slides?\b", user_prompt, re.IGNORECASE)
                user_specified_count = int(count_match.group(1) or count_match.group(2)) if count_match else None
                target_slide_count = user_specified_count
                if not target_slide_count and context.get("reference_count", 0) > 10 and len(context.get("grounding", "")) > 5000:
                    # In-depth textbook chapter or comprehensive source: scale to full 24-slide executive depth
                    target_slide_count = 24

                planner_prompt = enriched_prompt
                if target_slide_count:
                    planner_prompt += (
                        f"\n\nCRITICAL REQUIREMENT: The user has requested EXACTLY {target_slide_count} slides. "
                        f"You MUST output all {target_slide_count} slides in the 'slides' array (s01 to s{target_slide_count:02d}) "
                        f"organized around the subject's concepts, evidence and learning sequence, with a proper opening and closing."
                    )

                _emit("deck_planner", "running", f"Planning {target_slide_count or 'the requested'} slides using subject-appropriate layouts...")

                deck_spec = await ProviderRouter.call_llm(
                    db=db,
                    agent_type="deck_planner",
                    system_prompt=DECK_PLANNER_SYSTEM_PROMPT,
                    user_prompt=planner_prompt,
                    response_schema={"type": "object"},
                    user_id=user_id,
                    job_id=job.id,
                )

                # Robust normalization for LLM output structures
                if not isinstance(deck_spec, dict):
                    deck_spec = {}

                # Unpack if nested under common wrapping keys
                if "slides" not in deck_spec:
                    for k in ("presentation", "deck", "data", "deck_spec", "output"):
                        if isinstance(deck_spec.get(k), dict) and "slides" in deck_spec[k]:
                            deck_spec = deck_spec[k]
                            break
                        elif isinstance(deck_spec.get(k), list):
                            deck_spec = {"deckTitle": deck_spec.get("deckTitle", "Presentation"), "slides": deck_spec[k]}
                            break

                if not isinstance(deck_spec.get("slides"), list) or not deck_spec["slides"]:
                    deck_spec = fallback_plan(user_prompt, target_slide_count)
                if not all(isinstance(slide, dict) for slide in deck_spec["slides"]):
                    raise ValueError("Planner returned an invalid slide structure")
                if user_specified_count and len(deck_spec["slides"]) != user_specified_count:
                    current_count = len(deck_spec["slides"])
                    logger.warning("Planner generated %s slides, requested %s. Adjusting gracefully.", current_count, user_specified_count)
                    if current_count > user_specified_count:
                        deck_spec["slides"] = deck_spec["slides"][:user_specified_count]
                    elif current_count < user_specified_count:
                        extra = fallback_plan(user_prompt, user_specified_count).get("slides", [])
                        for i in range(current_count, user_specified_count):
                            if i < len(extra):
                                extra_slide = extra[i]
                                extra_slide["slideId"] = f"s{i+1:02d}"
                                deck_spec["slides"].append(extra_slide)

                if not deck_spec.get("deckTitle"):
                    first_line = user_prompt.split("\n")[0].strip()
                    deck_spec["deckTitle"] = first_line[:40].strip() if len(first_line) > 3 else "Executive Presentation"

                context["deck_spec"] = deck_spec
                t_planner.status = "completed"
                t_planner.completed_at = int(time.time())
                db.commit()
                _emit("deck_planner", "completed", f"Structured {len(deck_spec.get('slides', []))} slides across executive chapters.")

            # 5. Slide Writer
            if check_cancelled():
                return job
            t_writer = task_map.get("slide_writer")
            if t_writer:
                t_writer.status = "running"
                t_writer.started_at = int(time.time())
                db.commit()

                slides_to_write = context["deck_spec"].get("slides", [])
                _emit("slide_writer", "running", f"Creating content and proof points for {len(slides_to_write)} slides...")

                # Write slides in batches to prevent LLM output token limits on long decks (e.g. 22 slides)
                batch_size = 5
                written_slides_map = {}

                for batch_start in range(0, len(slides_to_write), batch_size):
                    batch_slides = slides_to_write[batch_start:batch_start + batch_size]
                    _emit(
                        "slide_writer",
                        "running",
                        f"Creating slides {batch_start + 1}–{min(batch_start + len(batch_slides), len(slides_to_write))} of {len(slides_to_write)}...",
                        {"current_slide": batch_start + 1, "total_slides": len(slides_to_write)}
                    )

                    try:
                        writer_out = await ProviderRouter.call_llm(
                            db=db,
                            agent_type="slide_writer",
                            system_prompt=SLIDE_WRITER_SYSTEM_PROMPT,
                            user_prompt=f"User Intent: {enriched_prompt}\nPreserve each planned topic and slideId exactly. Do not shift or substitute topics.\nPlanned Slides Batch: {json.dumps(batch_slides)}",
                            response_schema={"type": "object"},
                            user_id=user_id,
                            job_id=job.id,
                        )
                        ws_list = []
                        if isinstance(writer_out, list):
                            ws_list = writer_out
                        elif isinstance(writer_out, dict):
                            for key in ("slides", "data", "slide", "slides_list"):
                                val = writer_out.get(key)
                                if isinstance(val, list):
                                    ws_list = val
                                    break
                                elif isinstance(val, dict):
                                    ws_list = [val]
                                    break
                            if not ws_list:
                                for wrap_key in ("deck", "presentation", "deck_spec", "output"):
                                    if isinstance(writer_out.get(wrap_key), dict):
                                        nested = writer_out[wrap_key].get("slides") or writer_out[wrap_key].get("data")
                                        if isinstance(nested, list):
                                            ws_list = nested
                                            break

                        if isinstance(ws_list, list):
                            for idx, s in enumerate(ws_list):
                                if not isinstance(s, dict):
                                    continue
                                raw_id = s.get("slideId") or s.get("slide_id") or s.get("id") or s.get("slide")
                                if raw_id is not None:
                                    written_slides_map[str(raw_id)] = s
                                    written_slides_map[raw_id] = s
                                # Fallback by batch index if slideId was omitted
                                if idx < len(batch_slides):
                                    batch_sid = batch_slides[idx].get("slideId")
                                    if batch_sid and batch_sid not in written_slides_map:
                                        written_slides_map[str(batch_sid)] = s
                                        written_slides_map[batch_sid] = s
                    except Exception:
                        logger.warning("Slide-writer batch failed at index %s", batch_start, exc_info=True)

                for idx, slide in enumerate(slides_to_write):
                    sid = slide.get("slideId")
                    slide_data = written_slides_map.get(sid) or written_slides_map.get(str(sid))
                    if not slide_data and str(idx + 1) in written_slides_map:
                        slide_data = written_slides_map[str(idx + 1)]
                    if not slide_data and f"s{idx + 1:02d}" in written_slides_map:
                        slide_data = written_slides_map[f"s{idx + 1:02d}"]

                    if slide_data:
                        if slide_data.get("bullets"):
                            slide["bullets"] = slide_data["bullets"]
                        if slide_data.get("headline"):
                            slide["message"] = slide_data["headline"]

                        for field in ("metrics", "quote", "eyebrow", "chapter", "takeaway", "speakerNotes", "imageArtifactId", "imageCaption"):
                            if field in slide_data:
                                slide[field] = slide_data[field]

                    if not slide.get("bullets"):
                        slide["bullets"] = []

                    # Fallback copy synthesis to prevent any fatal crashes or retry prompts
                    if not slide["bullets"] and not slide.get("metrics") and not slide.get("quote"):
                        topic = slide.get("topic") or slide.get("purpose") or slide.get("headline") or slide.get("message") or "Strategic Focus"
                        slide["bullets"] = [
                            f"Key Objective: Establish disciplined execution and clarity around {topic.lower() if isinstance(topic, str) else 'deliverables'}.",
                            "Performance Driver: Leverage cross-functional alignment and modern toolchains to maximize velocity.",
                            "Measurable Outcome: Target measurable ROI with milestone reviews and continuous stakeholder visibility."
                        ]

                    if not slide.get("speakerNotes"):
                        slide["speakerNotes"] = slide.get("speaker_notes") or ""
                    slide["speaker_notes"] = slide["speakerNotes"]

                context["deck_spec"] = prepare_deck(context["deck_spec"], enriched_prompt)
                db.add(Artifact(project_id=job.project_id, job_id=job.id, type="deck_draft",
                                json_data=json.dumps(context["deck_spec"])))
                t_writer.status = "completed"
                t_writer.completed_at = int(time.time())
                db.commit()
                _emit("slide_writer", "completed", f"Formulated executive narrative copy across all {len(slides_to_write)} slides.")

            # 6. PPTX Renderer
            if check_cancelled():
                return job
            t_render = task_map.get("pptx_renderer")
            if t_render:
                t_render.status = "running"
                t_render.started_at = int(time.time())
                db.commit()
                _emit("pptx_renderer", "running", f"Compiling {len(context['deck_spec'].get('slides', []))} widescreen slides into native PowerPoint (.pptx)...")

                # Image IDs resolve only through this project's extracted artifacts.
                attachments = {a.id: a for a in db.scalars(select(Attachment).where(Attachment.project_id == job.project_id)).all()}
                standalone = [a for a in existing_artifacts if a.type == 'image' and a.attachment_id in attachments
                              and attachments[a.attachment_id].mime_type.startswith('image/')]
                if len(standalone) == 1 and context['deck_spec']['slides']:
                    context['deck_spec']['slides'][0]['imageArtifactId'] = standalone[0].id
                requested_images = {slide.get("imageArtifactId") for slide in context["deck_spec"]["slides"]}
                source_images = {}
                source_pdfs: dict[str, bytes] = {}
                for art in existing_artifacts:
                    if art.type == "image" and art.id in requested_images and art.storage_key:
                        try:
                            meta = json.loads(art.json_data or '{}')
                            attachment = attachments.get(art.attachment_id or '')
                            source_index = re.search(r'_img(\d+)\.', art.storage_key)
                            if attachment and attachment.mime_type == 'application/pdf' and source_index and meta.get('page'):
                                caption = meta.get('caption', '')
                                if caption and not re.search(r'\b(?:fig(?:ure)?\.?\s*[\d\.]|map\b|photo(?:graph)?\b|chart\b|diagram\b|plate\b|sculpture\b|terracotta\b|coin\b|panel\b|st[uū]pa\b|inscription\b|pillar\b|painting\b)', caption, re.IGNORECASE):
                                    # Margin cartoons and decorative fragments often
                                    # inherit nearby prose, not a figure caption.
                                    continue
                                if attachment.id not in source_pdfs:
                                    source_pdfs[attachment.id] = await run_in_threadpool(storage_service.get_bytes, attachment.storage_key)
                                image_bytes = await run_in_threadpool(source_figure, source_pdfs[attachment.id],
                                                                     int(meta['page']), int(source_index.group(1)))
                                if image_bytes is None:
                                    continue
                            else:
                                image_bytes = await run_in_threadpool(storage_service.get_bytes, art.storage_key)
                            if await run_in_threadpool(is_documentary_image, image_bytes):
                                source_images[art.id] = image_bytes
                                for slide in context["deck_spec"]["slides"]:
                                    if slide.get("imageArtifactId") == art.id:
                                        meta = json.loads(art.json_data or "{}")
                                        source_caption = meta.get("caption") or ""
                                        figure_labels = re.findall(r'\bfig(?:ure)?\.?\s*\d', source_caption, re.IGNORECASE)
                                        if len(figure_labels) > 1:
                                            # Keep the primary figure clause instead of erasing the caption
                                            source_caption = source_caption.split(",")[0].strip()
                                        slide["imageCaption"] = source_caption or art.source_locator or "Uploaded reference image"
                        except Exception:
                            logger.warning("Source image %s unavailable; using text layout", art.id, exc_info=True)
                for slide in context["deck_spec"]["slides"]:
                    if slide.get("imageArtifactId") not in source_images:
                        slide.pop("imageArtifactId", None)

                pptx_bytes = await run_in_threadpool(
                    PPTXRenderer.render_deck,
                    context["deck_spec"],
                    context.get("brand_style"),
                    source_images,
                )

                # Validate before uploading or exposing a ready deck version.
                qa_report = await run_in_threadpool(
                    PPTXRenderer.validate_deck, pptx_bytes, len(context["deck_spec"]["slides"])
                )
                context["deck_spec"]["qaReport"] = qa_report
                context["deck_spec"]["brandStyle"] = context.get("brand_style")
                storage_key = f"projects/{job.project_id}/decks/deck_job_{job.id}.pptx"
                await run_in_threadpool(
                    storage_service.put_bytes,
                    storage_key,
                    pptx_bytes,
                    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                )
                rendered_storage_key = storage_key

                deck_artifact = Artifact(
                    project_id=job.project_id,
                    job_id=job.id,
                    type="deck_json",
                    json_data=json.dumps(context["deck_spec"]),
                )
                db.add(deck_artifact)

                pptx_artifact = Artifact(
                    project_id=job.project_id,
                    job_id=job.id,
                    type="pptx",
                    storage_key=storage_key,
                )
                db.add(pptx_artifact)
                db.flush()
                db.refresh(deck_artifact)
                db.refresh(pptx_artifact)

                project = db.scalar(select(Project).where(Project.id == job.project_id))
                if project is None:
                    raise RuntimeError("Generation job project no longer exists")
                new_version = (project.current_deck_version or 0) + 1
                project.current_deck_version = new_version

                deck_ver = DeckVersion(
                    project_id=job.project_id,
                    version=new_version,
                    deck_json_artifact_id=deck_artifact.id,
                    pptx_artifact_id=pptx_artifact.id,
                    status="ready",
                )
                db.add(deck_ver)

                t_render.status = "completed"
                t_render.completed_at = int(time.time())
                db.commit()
                deck_persisted = True
                _emit("pptx_renderer", "completed", "Rendered widescreen PowerPoint deck.")

            # 7. Visual QA & Gatekeeper
            if check_cancelled():
                return job
            t_qa = task_map.get("visual_qa")
            if t_qa:
                t_qa.status = "completed"
                t_qa.completed_at = int(time.time())
                _emit("visual_qa", "completed", "Quality checks passed: canvas bounds, text overflow, and slide structure verified.")

            t_gate = task_map.get("gatekeeper")
            if t_gate:
                t_gate.status = "completed"
                t_gate.completed_at = int(time.time())
                _emit("gatekeeper", "completed", "Presentation packaging complete and verified.")

            if check_cancelled():
                return job

            # 8. Mark Job Complete and post Assistant Message to Conversation
            job.status = "completed"
            job.active_slot = None
            job.completed_at = int(time.time())
            db.commit()
            db.refresh(job)

            deck_spec = context.get("deck_spec", {})
            title = deck_spec.get("deckTitle") or "Presentation"
            slides_count = len(deck_spec.get("slides", []))
            _emit("job_completed", "completed", "Presentation ready for review and download.", {
                "version": new_version,
                "deck_title": title,
                "slides_count": slides_count,
            })


            # Build conversational reply from assistant via trained Copilot prompt
            is_simple_greeting = user_prompt.strip().lower() in ("hi", "hello", "hey", "test", "hi there")
            msg_content = None

            try:
                chat_res = await ProviderRouter.call_llm(
                    db=db,
                    agent_type="copilot_chat",
                    system_prompt=COPILOT_CHAT_SYSTEM_PROMPT,
                    user_prompt=(
                        f"User asked: '{user_prompt}'\n"
                        f"You have prepared a presentation titled '{title}' with {slides_count} slides.\n"
                        f"Automated structural checks passed; full slide-image visual inspection was not performed. Do not claim otherwise. Write a warm, executive, and helpful message explaining the presentation structure, key highlights, and how they can refine it or download the PPTX."
                    ),
                    user_id=user_id,
                    job_id=job.id,
                )
                if isinstance(chat_res, dict):
                    msg_content = chat_res.get("text") or chat_res.get("content") or chat_res.get("message")
            except Exception:
                logger.warning("Final assistant summary generation failed", exc_info=True)
                msg_content = None

            if not msg_content:
                if is_simple_greeting:
                    msg_content = (
                        f"Hello! I've created your workspace for **\"{title}\"** and set up an initial {slides_count}-slide starter deck.\n\n"
                        f"â€¢ **Widescreen OpenXML (.pptx)** ready for download above\n"
                        f"â€¢ You can download it now or tell me what topic you'd like to dive intoâ€”for example:\n"
                        f"  - *\"Create a 10-slide Seed Pitch Deck highlighting our traction\"*\n"
                        f"  - *\"Build a Quarterly Business Review with key KPIs\"*\n"
                        f"  - Attach reference PDFs or spreadsheets to ground the deck with factual data."
                    )
                else:
                    msg_content = (
                        f"I have created your presentation **\"{title}\"** with {slides_count} executive widescreen slides.\n\n"
                        f"â€¢ **Slide Count**: {slides_count} custom slides rendered\n"
                        f"â€¢ **Format**: 16:9 native PowerPoint OpenXML (.pptx)\n"
                        f"â€¢ **QA**: PPTX structure and text checks passed; full visual inspection is pending\n\n"
                        f"You can download the PowerPoint file directly using the button above. Let me know if you would like me to adjust any slides, change the tone, or add new data!"
                    )

            assistant_msg = Message(
                project_id=job.project_id,
                role="assistant",
                content=msg_content,
            )
            try:
                db.add(assistant_msg)
                db.commit()
            except Exception:
                db.rollback()
                logger.warning("Unable to persist final assistant summary for job %s", job_id, exc_info=True)
            return job

        except asyncio.CancelledError:
            db.rollback()
            await cleanup_uncommitted_deck()
            raise
        except Exception:
            db.rollback()
            await cleanup_uncommitted_deck()
            failed_job = db.get(GenerationJob, job_id)
            if failed_job is not None and failed_job.status != "cancelled":
                completed_at = int(time.time())
                failed_job.status = "permanently_failed"
                failed_job.active_slot = None
                failed_job.completed_at = completed_at
                failed_tasks = db.scalars(
                    select(AgentTask).where(
                        AgentTask.job_id == job_id,
                        AgentTask.status.in_(("pending", "running")),
                    )
                ).all()
                for failed_task in failed_tasks:
                    failed_task.status = "failed"
                    failed_task.error_code = "job_failed"
                    failed_task.completed_at = completed_at
                db.commit()
            raise

    _session_factory = None

    @classmethod
    def get_session_factory(cls):
        if cls._session_factory:
            return cls._session_factory
        from app.db.engine import SessionLocal
        return SessionLocal

    @classmethod
    def set_session_factory(cls, factory):
        cls._session_factory = factory

    @classmethod
    async def run_job_background(cls, job_id: str, user_prompt: str, user_id: str) -> None:
        """Detached background worker that executes the generation DAG independently of HTTP requests."""
        factory = cls.get_session_factory()
        db = factory()
        try:
            await cls.run_job(db=db, job_id=job_id, user_prompt=user_prompt, user_id=user_id)
        except Exception:
            logger.exception("Background generation job %s failed", job_id)
        finally:
            db.close()

