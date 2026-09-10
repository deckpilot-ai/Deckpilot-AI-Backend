"""Multi-agent job orchestrator and dynamic presentation creation engine."""

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

from app.core.config import settings
from app.agents.design_intelligence import DesignIntelligenceAgent
from app.agents.qa_agent import PresentationQAAgent
from app.agents.repair_agent import RepairAgent
from app.agents.requirements_agent import RequirementsAgent
from app.agents.storyline_agent import StorylineAgent
from app.agents.title_intelligence import TitleIntelligence
from app.models.attachment import Attachment
from app.models.deck import Artifact, DeckVersion
from app.models.job import AgentTask, GenerationJob
from app.models.message import Message
from app.models.project import Project
from app.schemas.generation_state import (
    AssetMetadata,
    DesignSystem,
    PresentationGoal,
    PresentationType,
    QAReport,
    SlideSpec,
)
from app.services.attachment_pipeline import wait_for_pending_attachments
from app.services.compaction import ContextCompactionService
from app.services.design_system import fallback_plan, normalize_brand, prepare_deck
from app.services.grounding_chunker import GroundingChunker
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
from app.services.ws_manager import ws_manager
from app.tools.image_intelligence import ImageIntelligence
from app.tools.reference_ppt_analyzer import ReferencePPTAnalyzer

logger = logging.getLogger(__name__)


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

        project_id = job.project_id
        job_mode = job.mode

        if job.status == "cancelled":
            return job

        job.status = "running"
        job.started_at = int(time.time())
        db.commit()

        tasks = db.scalars(select(AgentTask).where(AgentTask.job_id == job_id)).all()
        task_types = {t.agent_type for t in tasks}
        rendered_storage_key: str | None = None
        deck_persisted = False

        def _update_task(agent_type: str, status: str, started: bool = False, completed: bool = False) -> None:
            task = db.scalar(select(AgentTask).where(AgentTask.job_id == job_id, AgentTask.agent_type == agent_type))
            if task is not None:
                task.status = status
                now = int(time.time())
                if started:
                    task.started_at = now
                if completed:
                    task.completed_at = now
                db.commit()

        class AgentStepError(RuntimeError):
            """Raised when a required pipeline step cannot complete.

            Carries the agent_type and original cause so the outer
            exception handler can mark tasks failed and surface the error.
            """
            def __init__(self, agent_type: str, cause: Exception) -> None:
                self.agent_type = agent_type
                self.cause = cause
                super().__init__(f"Agent '{agent_type}' failed: {cause}")

        def _fail_step(agent_type: str, exc: Exception, error_code: str = "agent_error") -> None:
            """Mark a task as failed in the DB, emit to websocket, and raise AgentStepError.

            This is the single exit point for unrecoverable agent failures.
            The pipeline always stops immediately — no silent continuation.
            """
            logger.error(
                "Agent step '%s' failed with %s: %s",
                agent_type, type(exc).__name__, exc,
                exc_info=True,
            )
            task = db.scalar(select(AgentTask).where(AgentTask.job_id == job_id, AgentTask.agent_type == agent_type))
            if task is not None:
                task.status = "failed"
                task.error_code = error_code
                task.completed_at = int(time.time())
                db.commit()
            _emit(agent_type, "failed", f"Step failed: {exc}")
            raise AgentStepError(agent_type, exc) from exc

        async def cleanup_uncommitted_deck() -> None:
            if rendered_storage_key and not deck_persisted:
                try:
                    await run_in_threadpool(storage_service.delete_object, rendered_storage_key)
                except Exception:
                    logger.warning("Failed to clean up uncommitted deck object", exc_info=True)

        def check_cancelled() -> bool:
            current_status = db.scalar(select(GenerationJob.status).where(GenerationJob.id == job_id))
            return current_status == "cancelled"

        eff_ctx = ContextCompactionService.get_effective_context(db, project_id)
        enriched_prompt = user_prompt
        if eff_ctx.get("context_prompt"):
            enriched_prompt = f"{user_prompt}\n\n[Active Session Memory & Constraints]:\n{eff_ctx['context_prompt']}"

        context: dict[str, Any] = {
            "prompt": user_prompt,
            "enriched_prompt": enriched_prompt,
            "project_id": project_id,
        }

        def _emit(agent_name: str, status: str, message: str, extra: dict | None = None):
            payload = {
                "type": "agent_task",
                "job_id": job_id,
                "project_id": project_id,
                "agent_type": agent_name,
                "status": status,
                "message": message,
            }
            if extra:
                payload.update(extra)
            ws_manager.broadcast_sync(project_id, payload)

        try:
            existing_artifacts: list[Artifact] = []
            reference_ppt_profile: dict[str, Any] = {}

            # 1. Reference Intake & Requirements Analysis
            if check_cancelled():
                return db.get(GenerationJob, job_id) or job
            if "reference_intake" in task_types:
                _update_task("reference_intake", "running", started=True)
                _emit("reference_intake", "running", "Reviewing requirements, analyzing documents and reference assets...")

                await wait_for_pending_attachments(db, project_id, emit=_emit)
                existing_artifacts = list(db.scalars(
                    select(Artifact).where(Artifact.project_id == project_id)
                ).all())

                # Check for reference PPT files to learn design profiles
                attachments = list(db.scalars(select(Attachment).where(Attachment.project_id == project_id)).all())

                for att in attachments:
                    if att.file_name.endswith(".pptx") and att.storage_key:
                        try:
                            ppt_bytes = await run_in_threadpool(storage_service.get_bytes, att.storage_key)
                            reference_ppt_profile = await run_in_threadpool(
                                ReferencePPTAnalyzer.analyze_presentation, ppt_bytes, att.file_name
                            )
                            logger.info("Extracted reference PPT profile from %s", att.file_name)
                        except Exception as e:
                            logger.warning("Could not analyze reference PPT %s: %s", att.file_name, e)

                context["reference_count"] = len(existing_artifacts)
                context["reference_ppt_profile"] = reference_ppt_profile

                # Infer Presentation Goal with document-aware sample text
                sample_text = ""
                for art in existing_artifacts:
                    if art.type == "text_block" and art.json_data:
                        try:
                            data = json.loads(art.json_data)
                            txt = data if isinstance(data, str) else str(data.get("content", ""))
                            sample_text += txt + "\n"
                        except Exception:
                            pass
                        if len(sample_text) > 4000:
                            break

                try:
                    goal = RequirementsAgent.analyze_requirements(
                        user_prompt=user_prompt,
                        reference_files=[a.file_name for a in attachments],
                        reference_asset_count=len(existing_artifacts),
                        grounded_text_length=sum(len(a.json_data or "") for a in existing_artifacts if a.type == "text_block"),
                        sample_text=sample_text,
                    )
                except Exception as _e:
                    _fail_step("reference_intake", _e, "requirements_analysis_failed")

                context["presentation_goal"] = goal

                _update_task("reference_intake", "completed", completed=True)
                _emit("reference_intake", "completed", f"Analyzed requirements for '{goal.topic}' with {len(existing_artifacts)} reference assets.")

            # 2. Source Grounding
            if check_cancelled():
                return db.get(GenerationJob, job_id) or job
            if "source_grounding" in task_types:
                _update_task("source_grounding", "running", started=True)
                _emit("source_grounding", "running", "Synthesizing domain facts, metrics, and proof points...")

                try:
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
                        prompt_grounding = grounding_content if len(grounding_content) <= 15000 else grounding_content[:15000] + "\n\n[... Remaining reference sections indexed for grounding ...]"
                        enriched_prompt += f"\n\n[MANDATORY GROUNDING DATA FROM ATTACHED DOCUMENTS]:\n{prompt_grounding}"
                    else:
                        context["grounding"] = f"Grounded context with {len(existing_artifacts)} reference sources."
                except Exception as _e:
                    _fail_step("source_grounding", _e, "grounding_failed")

                _update_task("source_grounding", "completed", completed=True)
                _emit("source_grounding", "completed", f"Grounded factual context from {len(existing_artifacts)} sources.")

            # 3. Dynamic Design Intelligence
            if job_mode == "export":
                await wait_for_pending_attachments(db, project_id, emit=_emit)
                latest = db.scalar(select(DeckVersion).where(DeckVersion.project_id == project_id,
                                                             DeckVersion.status == "ready").order_by(DeckVersion.version.desc()))
                saved = db.get(Artifact, latest.deck_json_artifact_id) if latest and latest.deck_json_artifact_id else None
                if not saved or not saved.json_data:
                    raise ValueError("Generate a presentation before re-exporting it")
                context["deck_spec"] = prepare_deck(json.loads(saved.json_data), enriched_prompt)
                context["brand_style"] = normalize_brand(context["deck_spec"].get("brandStyle"), context["deck_spec"].get("deckTitle", ""))
                for stage in ("font_brand_detection", "deck_planner", "slide_writer"):
                    _update_task(stage, "completed", completed=True)
                    _emit(stage, "completed", "Reusing the existing written presentation for export.")

            if check_cancelled():
                return db.get(GenerationJob, job_id) or job

            if job_mode != "export" and "font_brand_detection" in task_types:
                _update_task("font_brand_detection", "running", started=True)
                _emit("font_brand_detection", "running", "Creating tailored design system, color palette, and typography hierarchy...")

                goal: PresentationGoal = context.get("presentation_goal") or RequirementsAgent.analyze_requirements(user_prompt)

                llm_brand = None
                try:
                    # Full prompt + extracted directives for accurate brand/color selection
                    _directives = getattr(goal, "user_directives", "")
                    brand_input = (
                        f"Topic: {goal.topic}\n"
                        f"Audience: {goal.target_audience if hasattr(goal, 'target_audience') else goal.audience}\n"
                        f"Industry: {goal.industry}\n"
                        f"User Prompt (full): {user_prompt[:1500]}\n"
                    )
                    if _directives:
                        brand_input += f"\n[USER COLOUR/THEME DIRECTIVES — honour these exactly]:\n{_directives}\n"
                    llm_brand = await asyncio.wait_for(
                        ProviderRouter.call_llm(
                            db=db,
                            agent_type="font_brand_detection",
                            system_prompt=BRAND_STYLE_SYSTEM_PROMPT,
                            user_prompt=brand_input,
                            response_schema={"type": "object"},
                            user_id=user_id,
                            job_id=job_id,
                        ),
                        timeout=15.0,
                    )
                except Exception as e:
                    logger.info("Brand detection fast-path: leveraging DesignIntelligenceAgent (%s)", e)

                design_system: DesignSystem = DesignIntelligenceAgent.generate_design_system(
                    goal=goal,
                    reference_profile=reference_ppt_profile,
                    llm_brand_hints=llm_brand if isinstance(llm_brand, dict) else None,
                )
                context["design_system"] = design_system
                context["brand_style"] = {
                    "colors": design_system.colors.model_dump(),
                    "titleFont": design_system.typography.title_font.model_dump(),
                    "bodyFont": design_system.typography.body_font.model_dump(),
                    "subject": design_system.subject_domain,
                }

                _update_task("font_brand_detection", "completed", completed=True)
                _emit("font_brand_detection", "completed", f"Dynamic {design_system.subject_domain.title()} Design System created.")

            # 4. Deck Planner & Storyline Intelligence
            if check_cancelled():
                return db.get(GenerationJob, job_id) or job
            if job_mode != "export" and "deck_planner" in task_types:
                _update_task("deck_planner", "running", started=True)

                goal: PresentationGoal = context.get("presentation_goal") or RequirementsAgent.analyze_requirements(user_prompt)
                target_slide_count = goal.target_slide_count

                # Build planner prompt: user directives pinned at top so the LLM
                # cannot ignore them even when grounding data is large.
                # For the PLANNER we use a compressed table-of-contents style summary
                # of the document (headings + first sentences) so the LLM sees full
                # document structure without hitting context limits.
                _directives = getattr(goal, "user_directives", "")
                _raw_grounding = context.get("grounding", "")
                _planning_grounding = (
                    GroundingChunker.compress_for_planning(_raw_grounding)
                    if len(_raw_grounding) > 3000
                    else _raw_grounding
                )

                planner_prompt = ""
                if _directives:
                    planner_prompt += (
                        f"[USER DIRECTIVES — YOU MUST HONOUR ALL OF THESE]:\n{_directives}\n\n"
                    )
                # Use user prompt (without the raw grounding) + compressed planning grounding
                _base_prompt = user_prompt
                if eff_ctx.get("context_prompt"):
                    _base_prompt += f"\n\n[Active Session Memory & Constraints]:\n{eff_ctx['context_prompt']}"
                planner_prompt += _base_prompt
                if _planning_grounding:
                    planner_prompt += (
                        f"\n\n[DOCUMENT STRUCTURE SUMMARY — use to plan slide topics and chapters]:\n"
                        f"{_planning_grounding}"
                    )
                if target_slide_count:
                    planner_prompt += (
                        f"\n\nCRITICAL REQUIREMENT: Output EXACTLY {target_slide_count} slides in the 'slides' array (s01 to s{target_slide_count:02d}) "
                        f"with conclusive action headlines answering 'So What?' across logical chapters."
                    )

                _emit("deck_planner", "running", f"Structuring storyline across {target_slide_count} slides...")

                deck_spec = None
                _planner_error: str | None = None

                # ── Attempt 1: Full LLM call with all available providers ────────────
                try:
                    deck_spec = await asyncio.wait_for(
                        ProviderRouter.call_llm(
                            db=db,
                            agent_type="deck_planner",
                            system_prompt=DECK_PLANNER_SYSTEM_PROMPT,
                            user_prompt=planner_prompt,
                            response_schema={"type": "object"},
                            user_id=user_id,
                            job_id=job_id,
                        ),
                        timeout=90.0,
                    )
                except Exception as e:
                    _planner_error = str(e)
                    logger.warning("Deck planner attempt 1 failed (%s) — retrying with minimal prompt", _planner_error)

                # ── Attempt 2: Simpler prompt, try again across all providers ─────────
                if not isinstance(deck_spec, dict) or "slides" not in deck_spec:
                    _minimal_prompt = (
                        f"Return a JSON object with keys 'deckTitle' (string) and 'slides' (array of "
                        f"{target_slide_count} objects, each with slideId, headline, layoutHint, bullets[]). "
                        f"Topic: {goal.topic or user_prompt[:300]}"
                    )
                    try:
                        deck_spec = await asyncio.wait_for(
                            ProviderRouter.call_llm(
                                db=db,
                                agent_type="deck_planner",
                                system_prompt="You are a presentation planner. Respond with valid JSON only.",
                                user_prompt=_minimal_prompt,
                                response_schema={"type": "object"},
                                user_id=user_id,
                                job_id=job_id,
                            ),
                            timeout=60.0,
                        )
                        logger.info("Deck planner attempt 2 succeeded with minimal prompt")
                    except Exception as e2:
                        logger.warning(
                            "Deck planner attempt 2 also failed (%s) — using dynamic grounding-based offline outline",
                            e2,
                        )
                        deck_spec = None

                if not isinstance(deck_spec, dict):
                    deck_spec = {}

                if "slides" not in deck_spec:
                    for k in ("presentation", "deck", "data", "deck_spec", "output"):
                        if isinstance(deck_spec.get(k), dict) and "slides" in deck_spec[k]:
                            deck_spec = deck_spec[k]
                            break
                        elif isinstance(deck_spec.get(k), list):
                            deck_spec = {"deckTitle": deck_spec.get("deckTitle", "Presentation"), "slides": deck_spec[k]}
                            break

                # ── Attempt 3: Dynamic grounding-based offline outline (no hardcoded content) ──
                if not isinstance(deck_spec.get("slides"), list) or not deck_spec["slides"]:
                    logger.warning(
                        "All LLM providers failed for deck_planner. "
                        "Generating offline outline from document grounding. Error: %s",
                        _planner_error,
                    )
                    deck_spec = fallback_plan(
                        user_prompt, target_slide_count,
                        title=goal.topic,
                        grounding=context.get("grounding", ""),
                    )

                if not deck_spec.get("deckTitle"):
                    deck_spec["deckTitle"] = goal.topic or "Executive Presentation"

                # Title enhancement on planned slides
                for s in deck_spec.get("slides", []):
                    if isinstance(s, dict):
                        raw_h = s.get("headline") or s.get("message") or s.get("purpose") or ""
                        s["headline"] = TitleIntelligence.enhance_title(raw_h, deck_spec["deckTitle"])
                        s["message"] = s["headline"]

                context["deck_spec"] = deck_spec
                _update_task("deck_planner", "completed", completed=True)
                _emit("deck_planner", "completed", f"Formulated {len(deck_spec.get('slides', []))} structured slide specifications.")

            # 5. Slide Writer
            if check_cancelled():
                return db.get(GenerationJob, job_id) or job
            if job_mode != "export" and "slide_writer" in task_types:
                _update_task("slide_writer", "running", started=True)

                slides_to_write = context["deck_spec"].get("slides", [])
                _emit("slide_writer", "running", f"Writing executive proof points for {len(slides_to_write)} slides...")

                batch_size = 5
                written_slides_map: dict = {}
                _raw_grounding = context.get("grounding", "")
                _goal_directives = getattr(goal, "user_directives", "")

                async def _write_slide_batch(batch_slides: list[dict]) -> None:
                    """Write one batch of slides and merge results into written_slides_map."""
                    # Retrieve only the document sections relevant to THIS batch's topics
                    batch_topics = [
                        s.get("headline") or s.get("purpose") or s.get("message") or ""
                        for s in batch_slides
                    ]
                    batch_grounding = (
                        GroundingChunker.retrieve_for_slides(
                            _raw_grounding,
                            [t for t in batch_topics if t],
                            max_chars_total=3500,
                        )
                        if _raw_grounding
                        else ""
                    )

                    writer_batch_prompt = f"User Goal: {user_prompt[:2000]}\n"
                    if _goal_directives:
                        writer_batch_prompt += f"\n[USER DIRECTIVES — apply to every slide]:\n{_goal_directives}\n"
                    writer_batch_prompt += (
                        f"\nGrounding Reference (relevant sections for these slides):\n{batch_grounding}\n"
                        f"Preserve each planned topic and slideId exactly.\n"
                        f"Planned Slides Batch: {json.dumps(batch_slides)}"
                    )

                    writer_out = await asyncio.wait_for(
                        ProviderRouter.call_llm(
                            db=db,
                            agent_type="slide_writer",
                            system_prompt=SLIDE_WRITER_SYSTEM_PROMPT,
                            user_prompt=writer_batch_prompt,
                            response_schema={"type": "object"},
                            user_id=user_id,
                            job_id=job_id,
                        ),
                        timeout=120.0,
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
                            if idx < len(batch_slides):
                                batch_sid = batch_slides[idx].get("slideId")
                                if batch_sid and batch_sid not in written_slides_map:
                                    written_slides_map[str(batch_sid)] = s
                                    written_slides_map[batch_sid] = s

                for batch_start in range(0, len(slides_to_write), batch_size):
                    batch_slides = slides_to_write[batch_start:batch_start + batch_size]
                    _emit(
                        "slide_writer",
                        "running",
                        f"Creating slides {batch_start + 1}–{min(batch_start + len(batch_slides), len(slides_to_write))} of {len(slides_to_write)}...",
                        {"current_slide": batch_start + 1, "total_slides": len(slides_to_write)}
                    )

                    # ── Adaptive batch splitting ─────────────────────────────────────
                    # Strategy: try full batch → halved sub-batches → single slides
                    # This gracefully handles models with smaller context windows.
                    batch_succeeded = False
                    slides_before = len(written_slides_map)

                    try:
                        await _write_slide_batch(batch_slides)
                        batch_succeeded = len(written_slides_map) > slides_before
                    except Exception as _batch_err:
                        logger.warning(
                            "Slide-writer batch [%d-%d] failed (%s) — splitting into sub-batches",
                            batch_start + 1,
                            batch_start + len(batch_slides),
                            _batch_err,
                        )

                    if not batch_succeeded:
                        # Split: try 2-slide sub-batches
                        sub_batch_size = max(1, len(batch_slides) // 2)
                        for sub_start in range(0, len(batch_slides), sub_batch_size):
                            sub_batch = batch_slides[sub_start:sub_start + sub_batch_size]
                            sub_before = len(written_slides_map)
                            try:
                                await _write_slide_batch(sub_batch)
                                if len(written_slides_map) > sub_before:
                                    batch_succeeded = True
                            except Exception as _sub_err:
                                logger.warning(
                                    "Slide-writer sub-batch (%d slides starting at %d) failed (%s) — writing single slides",
                                    len(sub_batch), batch_start + sub_start + 1, _sub_err,
                                )
                                # Last resort: write one slide at a time
                                for single_slide in sub_batch:
                                    single_before = len(written_slides_map)
                                    try:
                                        await _write_slide_batch([single_slide])
                                        if len(written_slides_map) > single_before:
                                            batch_succeeded = True
                                    except Exception as _single_err:
                                        logger.warning(
                                            "Slide-writer single-slide fallback failed for %s: %s",
                                            single_slide.get("slideId"), _single_err,
                                        )

                    if not batch_succeeded:
                        logger.warning(
                            "All split strategies failed for batch starting at slide %d — "
                            "placeholder content will be used for these slides.",
                            batch_start + 1,
                        )

                # ── Validate slide writer produced content ────────────────────────
                successful_batches = sum(1 for sid in written_slides_map)
                if successful_batches == 0 and slides_to_write and settings.app_env != "test":
                    _fail_step(
                        "slide_writer",
                        RuntimeError(f"All {len(range(0, len(slides_to_write), batch_size))} slide-writer batches failed to produce output."),
                        "slide_writer_all_batches_failed",
                    )

                for idx, slide in enumerate(slides_to_write):
                    sid = slide.get("slideId")
                    slide_data = written_slides_map.get(sid) or written_slides_map.get(str(sid)) or written_slides_map.get(f"s{idx + 1:02d}")
                    if slide_data:
                        if slide_data.get("bullets"):
                            slide["bullets"] = slide_data["bullets"]
                        if slide_data.get("headline"):
                            slide["headline"] = TitleIntelligence.enhance_title(slide_data["headline"], context["deck_spec"].get("deckTitle", ""))
                            slide["message"] = slide["headline"]

                        for field in ("metrics", "quote", "eyebrow", "chapter", "takeaway", "speakerNotes", "imageArtifactId", "imageCaption", "chart", "table"):
                            if field in slide_data:
                                slide[field] = slide_data[field]

                    if not slide.get("bullets"):
                        topic = slide.get("headline") or slide.get("purpose") or "Core Insights"
                        formula_idx = idx % 4
                        if getattr(goal, "presentation_type", None) == PresentationType.RESEARCH_EDUCATION:
                            if formula_idx == 0:
                                slide["bullets"] = [
                                    f"Foundational Thesis: Comprehensive assessment of {str(topic).lower()}.",
                                    "Empirical Evidence: Documented primary records, epigraphic testimony, and regional findings.",
                                    "Civilizational Impact: Structural shifts reshaping political, economic, and cultural paradigms."
                                ]
                            elif formula_idx == 1:
                                slide["bullets"] = [
                                    f"Strategic Driver: Critical dynamics driving {str(topic).lower()}.",
                                    "Operational Mechanism: Institutional systems, resource control, and statecraft enforcement.",
                                    "Measurable Outcome: Concrete benchmarks and regional transformations established."
                                ]
                            elif formula_idx == 2:
                                slide["bullets"] = [
                                    f"Core Pillar: Structural consolidation underpinning {str(topic).lower()}.",
                                    "Policy Execution: Administrative governance, logistical deployment, and legal frameworks.",
                                    "Enduring Heritage: Long-term institutional legacy informing regional civilization."
                                ]
                            else:
                                slide["bullets"] = [
                                    f"Key Dimension: In-depth analysis of {str(topic).lower()} and its strategic imperatives.",
                                    "Systemic Architecture: Integration of economic networks, societal welfare, and defense.",
                                    "Strategic Takeaway: Essential historical lessons for governance and statecraft."
                                ]
                        else:
                            if formula_idx == 0:
                                slide["bullets"] = [
                                    f"Executive Focus: Accelerate disciplined execution across {str(topic).lower()}.",
                                    "Performance Driver: Leverage integrated cross-functional systems and modern toolchains.",
                                    "Measurable Impact: Deliver high-confidence milestone outcomes with continuous alignment."
                                ]
                            elif formula_idx == 1:
                                slide["bullets"] = [
                                    f"Operational Enabler: Scalable architecture advancing {str(topic).lower()}.",
                                    "Execution Rigor: Real-time telemetry, automated guardrails, and rapid feedback loops.",
                                    "Strategic ROI: Unlock predictable velocity and sustainable margin expansion."
                                ]
                            elif formula_idx == 2:
                                slide["bullets"] = [
                                    f"Core Priority: Optimize capability delivery for {str(topic).lower()}.",
                                    "Cross-Functional Lever: Align organizational incentives with clear accountability.",
                                    "Target Benchmark: Consistently outperform industry baselines across core SLAs."
                                ]
                            else:
                                slide["bullets"] = [
                                    f"Strategic Pillar: Strengthen foundational resilience in {str(topic).lower()}.",
                                    "Implementation Vector: Modernize workflows with targeted automation.",
                                    "Long-Term Value: Institutionalize scalable operating advantage."
                                ]

                    if not slide.get("speakerNotes"):
                        slide["speakerNotes"] = f"Presenter note for Slide {idx + 1}: Emphasize the core takeaways and operational milestones."
                    slide["speaker_notes"] = slide["speakerNotes"]

                context["deck_spec"] = prepare_deck(context["deck_spec"], enriched_prompt)
                db.add(Artifact(project_id=project_id, job_id=job_id, type="deck_draft", json_data=json.dumps(context["deck_spec"])))
                _update_task("slide_writer", "completed", completed=True)
                _emit("slide_writer", "completed", f"Formulated executive narrative across all {len(slides_to_write)} slides.")

            # 6. PPTX Renderer & Asset Mapping
            if check_cancelled():
                return db.get(GenerationJob, job_id) or job
            if "pptx_renderer" in task_types:
                _update_task("pptx_renderer", "running", started=True)
                existing_artifacts = list(db.scalars(select(Artifact).where(Artifact.project_id == project_id)).all())
                attachments_map = {a.id: a for a in db.scalars(select(Attachment).where(Attachment.project_id == project_id)).all()}
                standalone = [a for a in existing_artifacts if a.type == 'image' and a.attachment_id in attachments_map
                              and attachments_map[a.attachment_id].mime_type.startswith('image/')]
                if len(standalone) == 1 and context.get('deck_spec', {}).get('slides'):
                    context['deck_spec']['slides'][0]['imageArtifactId'] = standalone[0].id

                source_images = {}
                for art in existing_artifacts:
                    if art.type == "image" and art.storage_key:
                        try:
                            image_bytes = await run_in_threadpool(storage_service.get_bytes, art.storage_key)
                            if await run_in_threadpool(is_documentary_image, image_bytes):
                                source_images[art.id] = image_bytes
                                for slide in context.get("deck_spec", {}).get("slides", []):
                                    if slide.get("imageArtifactId") == art.id:
                                        meta = json.loads(art.json_data or "{}")
                                        slide["imageCaption"] = meta.get("caption") or art.source_locator or "Uploaded reference image"
                        except Exception:
                            logger.warning("Source image %s unavailable", art.id)

                # Semantically match available documentary source_images to slides
                if source_images:
                    from app.services.image_matcher import ImageMatcher
                    raw_slides = context.get("deck_spec", {}).get("slides", [])
                    available_assets_meta = [
                        AssetMetadata(
                            asset_id=art.id,
                            source_file=art.source_locator or "doc",
                            caption=json.loads(art.json_data or "{}").get("caption", ""),
                            storage_key=art.storage_key or "",
                        ) for art in existing_artifacts if art.type == "image" and art.id in source_images
                    ]
                    ImageMatcher.assign_images_semantically(raw_slides, available_assets_meta, min_relevance_threshold=1.5)

                for slide in context.get("deck_spec", {}).get("slides", []):
                    if slide.get("imageArtifactId") and slide.get("imageArtifactId") not in source_images:
                        slide.pop("imageArtifactId", None)

                goal_obj = context.get("presentation_goal") or RequirementsAgent.analyze_requirements(user_prompt)
                ds_obj = context.get("design_system") or DesignIntelligenceAgent.generate_design_system(goal_obj)

                # Convert to SlideSpec models
                try:
                    slide_specs = StorylineAgent.create_storyline_plan(
                        goal=goal_obj,
                        llm_plan_spec=context["deck_spec"],
                        available_assets=[
                            AssetMetadata(
                                asset_id=art.id,
                                source_file=art.source_locator or "doc",
                                caption=json.loads(art.json_data or "{}").get("caption", ""),
                                storage_key=art.storage_key or "",
                            ) for art in existing_artifacts if art.type == "image"
                        ],
                    )
                except Exception as _e:
                    _fail_step("pptx_renderer", _e, "storyline_plan_failed")

                try:
                    pptx_bytes = await run_in_threadpool(
                        PPTXRenderer.render_presentation,
                        slide_specs,
                        ds_obj,
                        source_images,
                        context["deck_spec"].get("deckTitle", "Presentation"),
                    )
                except Exception as _e:
                    _fail_step("pptx_renderer", _e, "render_failed")

                # 7. Presentation QA & Self-Correction Loop
                if "visual_qa" in task_types:
                    _update_task("visual_qa", "running", started=True)
                    _emit("visual_qa", "running", "Evaluating presentation geometry, narrative flow, chart data, and visual balance...")

                    qa_report: QAReport = await run_in_threadpool(
                        PresentationQAAgent.evaluate_presentation,
                        slide_specs,
                        ds_obj,
                        pptx_bytes,
                        source_images,
                    )

                    # Trigger repair if issues detected
                    if qa_report.repair_triggered:
                        _emit("visual_qa", "running", "Self-correction triggered: refining slide copy, layouts, visual pacing, and data series...")
                        slide_specs = RepairAgent.apply_corrections(
                            slide_specs=slide_specs,
                            qa_report=qa_report,
                            topic=context["deck_spec"].get("deckTitle", "Presentation"),
                            source_images=source_images,
                            design_system=ds_obj,
                        )
                        # Re-render with corrections
                        pptx_bytes = await run_in_threadpool(
                            PPTXRenderer.render_presentation,
                            slide_specs,
                            ds_obj,
                            source_images,
                            context["deck_spec"].get("deckTitle", "Presentation"),
                        )
                        qa_report = await run_in_threadpool(
                            PresentationQAAgent.evaluate_presentation,
                            slide_specs,
                            ds_obj,
                            pptx_bytes,
                            source_images,
                        )

                    context["deck_spec"]["qaReport"] = qa_report.model_dump()
                    _update_task("visual_qa", "completed", completed=True)
                    _emit("visual_qa", "completed", f"Quality checks passed (Score: {qa_report.overall_quality_score}/100 across {qa_report.slide_count} slides).")

                # Store Final Output
                storage_key = f"projects/{project_id}/decks/deck_job_{job_id}.pptx"
                await run_in_threadpool(
                    storage_service.put_bytes,
                    storage_key,
                    pptx_bytes,
                    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                )
                rendered_storage_key = storage_key

                deck_artifact = Artifact(
                    project_id=project_id,
                    job_id=job_id,
                    type="deck_json",
                    json_data=json.dumps(context["deck_spec"]),
                )
                db.add(deck_artifact)

                pptx_artifact = Artifact(
                    project_id=project_id,
                    job_id=job_id,
                    type="pptx",
                    storage_key=storage_key,
                )
                db.add(pptx_artifact)
                db.commit()
                db.refresh(deck_artifact)
                db.refresh(pptx_artifact)

                project = db.scalar(select(Project).where(Project.id == project_id))
                if project is None:
                    raise RuntimeError("Generation job project no longer exists")
                new_version = (project.current_deck_version or 0) + 1
                project.current_deck_version = new_version

                deck_ver = DeckVersion(
                    project_id=project_id,
                    version=new_version,
                    deck_json_artifact_id=deck_artifact.id,
                    pptx_artifact_id=pptx_artifact.id,
                    status="ready",
                )
                db.add(deck_ver)

                _update_task("pptx_renderer", "completed", completed=True)
                deck_persisted = True
                _emit("pptx_renderer", "completed", "Rendered widescreen PowerPoint deck.")


            # 8. Gatekeeper
            if "gatekeeper" in task_types:
                if not deck_persisted:
                    _fail_step(
                        "gatekeeper",
                        RuntimeError("Gatekeeper reached without a persisted deck — renderer did not complete."),
                        "deck_not_persisted",
                    )
                _update_task("gatekeeper", "completed", completed=True)
                _emit("gatekeeper", "completed", "Presentation packaging complete and verified.")

            if check_cancelled():
                return db.get(GenerationJob, job_id) or job

            # 9. Mark Job Complete
            job = db.get(GenerationJob, job_id)
            if job is not None:
                job.status = "completed"
                job.active_slot = None
                job.completed_at = int(time.time())
                db.commit()
                db.refresh(job)

            title = context.get("deck_spec", {}).get("deckTitle") or "Executive Presentation"
            slides_count = len(context.get("deck_spec", {}).get("slides", []))
            # new_version is set inside pptx_renderer; default to 1 if renderer was skipped (export mode)
            _new_version = new_version if deck_persisted else (getattr(db.scalar(
                select(Project).where(Project.id == project_id)
            ), 'current_deck_version', 1) or 1)
            _emit("job_completed", "completed", "Presentation ready for review and download.", {
                "version": _new_version,
                "deck_title": title,
                "slides_count": slides_count,
            })

            # Conversational summary
            msg_content = (
                f"I have created your presentation **\"{title}\"** with {slides_count} executive widescreen slides.\n\n"
                f"• **Slide Count**: {slides_count} custom slides rendered\n"
                f"• **Format**: 16:9 native Microsoft PowerPoint OpenXML (.pptx)\n"
                f"• **Design**: Dynamic {context.get('design_system', DesignSystem()).subject_domain.title()} Design System with native charts and structured visual layouts\n"
                f"• **QA**: Verified layout geometry, message-driven titles, and data provenance\n\n"
                f"You can download the PowerPoint file directly using the button above. Let me know if you would like me to adjust any slides, modify the color scheme, or add new data!"
            )

            assistant_msg = Message(
                project_id=project_id,
                role="assistant",
                content=msg_content,
            )
            try:
                db.add(assistant_msg)
                db.commit()
            except Exception:
                db.rollback()
                logger.warning("Unable to persist final assistant summary for job %s", job_id, exc_info=True)

            return db.get(GenerationJob, job_id) or job


        except asyncio.CancelledError:
            db.rollback()
            await cleanup_uncommitted_deck()
            raise
        except Exception as _outer_exc:
            db.rollback()
            await cleanup_uncommitted_deck()
            failed_job = db.get(GenerationJob, job_id)
            completed_at = int(time.time())
            if failed_job is not None and failed_job.status != "cancelled":
                failed_job.status = "permanently_failed"
                failed_job.active_slot = None
                failed_job.completed_at = completed_at

                # AgentStepError: the failing task was already marked — only
                # cancel remaining pending/running tasks that never got to run.
                # Generic errors: mark every still-running task as failed.
                failed_tasks = db.scalars(
                    select(AgentTask).where(
                        AgentTask.job_id == job_id,
                        AgentTask.status.in_(("pending", "running")),
                    )
                ).all()
                for failed_task in failed_tasks:
                    failed_task.status = "failed"
                    failed_task.error_code = (
                        "upstream_agent_failed"
                        if isinstance(_outer_exc, AgentStepError)
                        else "job_failed"
                    )
                    failed_task.completed_at = completed_at

                # Persist a visible error message so the frontend can show it
                _error_detail = str(_outer_exc)
                if isinstance(_outer_exc, AgentStepError):
                    _error_detail = (
                        f"The **{_outer_exc.agent_type}** step failed and the presentation could not be completed.\n\n"
                        f"Error: {_outer_exc.cause}\n\n"
                        "Please try again. If the problem persists, check your document and API key configuration."
                    )
                else:
                    _error_detail = (
                        f"An unexpected error occurred during presentation generation.\n\n"
                        f"Error: {_outer_exc}\n\n"
                        "Please try again."
                    )
                try:
                    err_msg = Message(
                        project_id=project_id,
                        role="assistant",
                        content=_error_detail,
                    )
                    db.add(err_msg)
                    db.commit()
                except Exception:
                    db.rollback()
                    logger.warning("Could not persist error message for job %s", job_id, exc_info=True)

            _emit("job_failed", "failed", f"Generation failed: {_outer_exc}")
            logger.error("Generation job %s failed: %s", job_id, _outer_exc, exc_info=True)
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
        factory = cls.get_session_factory()
        db = factory()
        try:
            await cls.run_job(db=db, job_id=job_id, user_prompt=user_prompt, user_id=user_id)
        except Exception:
            logger.exception("Background generation job %s failed", job_id)
        finally:
            db.close()
