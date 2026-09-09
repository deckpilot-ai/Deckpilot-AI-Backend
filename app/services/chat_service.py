"""Service for conversational chat turns, intent detection, 3-mode routing (Ask, Plan, Autopilot), and presentation triggering."""

import asyncio
import json
import logging
import time
import uuid
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session, selectinload

from app.models.attachment import Attachment
from app.models.deck import DeckVersion
from app.models.message import Message
from app.schemas.message import MessageOut
from app.services.guardrails import (
    InputGuardrailService,
    IntentCategory,
    OutputGuardrailService,
)
from app.services.prompts import (
    ASK_MODE_SYSTEM_PROMPT,
    COPILOT_CHAT_SYSTEM_PROMPT,
    PLAN_MODE_SYSTEM_PROMPT,
)
from app.services.provider_router import ProviderRouter

logger = logging.getLogger(__name__)


class ChatService:
    @staticmethod
    def is_presentation_intent(content: str, has_attachments: bool = False) -> bool:
        """Determines if the user's message is requesting a presentation to be created."""
        result = InputGuardrailService.evaluate(content, has_attachments=has_attachments)
        return result.intent == IntentCategory.DECK_GENERATION

    @staticmethod
    async def handle_chat_message(
        db: Session,
        project_id: str,
        user_id: str,
        content: str,
        has_attachments: bool = False,
        attachment_ids: list[str] | None = None,
        mode: str = "autopilot",
        existing_user_msg: Message | None = None,
    ) -> dict[str, Any]:
        """
        Handles incoming user message across 3 operational modes with input & output guardrails:
        - 'ask': Research, advisory, SWOT, market data synthesis without deck generation.
        - 'plan': Researches and structures slide-by-slide narrative for review before PPTX generation.
        - 'autopilot' (default): End-to-end presentation generation (or greeting if non-presentation).
        """
        now = int(time.time())
        mode = (mode or "autopilot").lower().strip()
        if mode not in ("autopilot", "plan", "ask"):
            mode = "autopilot"

        # 0. Evaluate Input Guardrails
        input_guardrail = InputGuardrailService.evaluate(
            content=content,
            has_attachments=has_attachments,
            mode=mode,
        )

        # 1. Persist or Update User Message (using sanitized content)
        if existing_user_msg:
            user_msg = existing_user_msg
            user_msg.content = input_guardrail.sanitized_content or content
            db.commit()
        else:
            user_msg = Message(
                id=str(uuid.uuid4()),
                project_id=project_id,
                user_id=user_id,
                role="user",
                content=input_guardrail.sanitized_content or content,
                created_at=now,
            )
            db.add(user_msg)
            db.flush()

        # Link attachments
        if attachment_ids:
            db.execute(
                update(Attachment)
                .where(Attachment.id.in_(attachment_ids), Attachment.project_id == project_id)
                .values(message_id=user_msg.id)
            )
        elif has_attachments:
            db.execute(
                update(Attachment)
                .where(Attachment.project_id == project_id, Attachment.message_id.is_(None))
                .values(message_id=user_msg.id)
            )

        db.commit()
        db.expire_all()
        loaded_user_msg = db.scalar(
            select(Message)
            .options(selectinload(Message.attachments))
            .where(Message.id == user_msg.id)
        )
        if loaded_user_msg:
            user_msg = loaded_user_msg

        user_msg_dict = MessageOut.model_validate(user_msg).model_dump()


        # 2. Handle Security / Policy Violations
        if not input_guardrail.is_safe:
            output_guardrail = OutputGuardrailService.apply(
                input_guardrail.direct_response or "Request could not be processed due to safety guidelines.",
                input_guardrail,
            )
            assistant_msg = Message(
                id=str(uuid.uuid4()),
                project_id=project_id,
                role="assistant",
                content=output_guardrail.content,
                created_at=max(int(time.time()), user_msg.created_at + 1),
            )
            db.add(assistant_msg)
            db.commit()
            db.refresh(assistant_msg)

            return {
                "intent": "chat",
                "mode": mode,
                "should_generate": False,
                "user_message": user_msg_dict,
                "assistant_message": {
                    "id": assistant_msg.id,
                    "project_id": assistant_msg.project_id,
                    "user_id": None,
                    "role": assistant_msg.role,
                    "content": assistant_msg.content,
                    "created_at": assistant_msg.created_at,
                },
                "plan_spec": None,
                "decision_questions": None,
                "guardrail_info": {
                    "input": input_guardrail.model_dump(),
                    "output": output_guardrail.model_dump(),
                },
            }

        # 3. Direct Guardrail Responses (e.g. Greetings, Politeness, Quick Help)
        # Prevents unnecessary long LLM calls and avoids dumping walls of text on "Hi" or "Thanks"
        if input_guardrail.direct_response:
            output_guardrail = OutputGuardrailService.apply(
                input_guardrail.direct_response,
                input_guardrail,
            )
            assistant_msg = Message(
                id=str(uuid.uuid4()),
                project_id=project_id,
                role="assistant",
                content=output_guardrail.content,
                created_at=max(int(time.time()), user_msg.created_at + 1),
            )
            db.add(assistant_msg)
            db.commit()
            db.refresh(assistant_msg)

            return {
                "intent": "chat",
                "mode": mode,
                "should_generate": False,
                "user_message": user_msg_dict,
                "assistant_message": {
                    "id": assistant_msg.id,
                    "project_id": assistant_msg.project_id,
                    "user_id": None,
                    "role": assistant_msg.role,
                    "content": assistant_msg.content,
                    "created_at": assistant_msg.created_at,
                },
                "plan_spec": None,
                "decision_questions": None,
                "guardrail_info": {
                    "input": input_guardrail.model_dump(),
                    "output": output_guardrail.model_dump(),
                },
            }

        # -------------------------------------------------------------
        # MODE 1: ASK MODE (Research, advisory, and Q&A without slides)
        # -------------------------------------------------------------
        if mode == "ask":
            advisory_text = None
            try:
                llm_res = await ProviderRouter.call_llm(
                    db=db,
                    agent_type="copilot_chat",
                    system_prompt=ASK_MODE_SYSTEM_PROMPT,
                    user_prompt=f"User Query (Ask Mode): {input_guardrail.sanitized_content}",
                    response_schema=None,
                    user_id=user_id,
                )
                if isinstance(llm_res, dict):
                    advisory_text = llm_res.get("text") or llm_res.get("content")
            except Exception:
                logger.warning("Ask-mode provider failed; using fallback", exc_info=True)

            if not advisory_text:
                advisory_text = (
                    f"### Strategic Research & Advisory Summary\n\n"
                    f"**Topic**: {input_guardrail.sanitized_content}\n\n"
                    f"• **Market Positioning**: In competitive enterprise categories, positioning requires quantitative evidence of time-to-value and verifiable ROI.\n"
                    f"• **Key Question for Your Audience**: What specific friction in current workflows justifies immediate budget reallocation?\n"
                    f"• **Storyline Recommendation**: Structure the narrative using the Pyramid Principle—lead with the core business outcome, followed by operational proof points.\n\n"
                    f"*Tip: Switch to **Plan Mode** to outline slides or **Autopilot** to generate the complete deck.*"
                )

            # Apply Output Guardrails
            output_guardrail = OutputGuardrailService.apply(advisory_text, input_guardrail)

            assistant_msg = Message(
                id=str(uuid.uuid4()),
                project_id=project_id,
                role="assistant",
                content=output_guardrail.content,
                created_at=max(int(time.time()), user_msg.created_at + 1),
            )
            db.add(assistant_msg)
            db.commit()
            db.refresh(assistant_msg)

            return {
                "intent": "ask",
                "mode": "ask",
                "should_generate": False,
                "user_message": user_msg_dict,
                "assistant_message": {
                    "id": assistant_msg.id,
                    "project_id": assistant_msg.project_id,
                    "user_id": None,
                    "role": assistant_msg.role,
                    "content": assistant_msg.content,
                    "created_at": assistant_msg.created_at,
                },
                "plan_spec": None,
                "decision_questions": None,
                "guardrail_info": {
                    "input": input_guardrail.model_dump(),
                    "output": output_guardrail.model_dump(),
                },
            }

        # -------------------------------------------------------------
        # MODE 2: PLAN MODE (Slide narrative structure for review)
        # -------------------------------------------------------------
        if mode == "plan":
            plan_text = None
            plan_spec = None
            try:
                llm_res = await ProviderRouter.call_llm(
                    db=db,
                    agent_type="deck_planner",
                    system_prompt=PLAN_MODE_SYSTEM_PROMPT,
                    user_prompt=f"Plan Request: {input_guardrail.sanitized_content}",
                    response_schema=None,
                    user_id=user_id,
                )
                if isinstance(llm_res, dict):
                    plan_text = llm_res.get("text") or llm_res.get("content")
                    # Check if JSON block exists
                    if plan_text and "```json" in plan_text:
                        json_str = plan_text.split("```json")[1].split("```")[0].strip()
                        plan_spec = json.loads(json_str)
                    elif isinstance(llm_res.get("slides"), list):
                        plan_spec = llm_res
            except Exception:
                logger.warning("Plan-mode provider failed; using fallback", exc_info=True)

            if not plan_text:
                plan_text = (
                    f"### Executive Presentation Plan: {input_guardrail.sanitized_content[:40]}\n\n"
                    f"**Strategic Objective**: Align stakeholders on the core value proposition, growth milestones, and execution roadmap.\n\n"
                    f"#### Slide Outline:\n"
                    f"1. **Executive Thesis & Vision** (`hero`) — Transformative market opportunity and core value proposition.\n"
                    f"2. **Problem Analysis & Friction** (`two_column`) — Enterprise inefficiencies and quantified cost of status quo.\n"
                    f"3. **Proprietary Solution** (`two_column`) — Architectural moat, core platform capabilities, and customer ROI.\n"
                    f"4. **Traction & Unit Economics** (`metrics_grid`) — Net retention, customer growth trajectory, and payback period.\n"
                    f"5. **12-Month Execution Roadmap** (`timeline`) — Phased product rollout, enterprise milestones, and scale vectors.\n\n"
                    f"Click **Approve & Build Presentation** below when you are ready to compile this into PowerPoint (.pptx)."
                )

            # Apply Output Guardrails
            output_guardrail = OutputGuardrailService.apply(plan_text, input_guardrail)

            assistant_msg = Message(
                id=str(uuid.uuid4()),
                project_id=project_id,
                role="assistant",
                content=output_guardrail.content,
                created_at=max(int(time.time()), user_msg.created_at + 1),
            )
            db.add(assistant_msg)
            if not plan_spec:
                plan_spec = {
                    "deckTitle": input_guardrail.sanitized_content[:50].strip() or "Presentation Plan",
                    "objective": "Align leadership and key stakeholders on the core value proposition, architecture, and timeline.",
                    "totalSlides": 5,
                    "slides": [
                        {"slideId": "s_1", "purpose": "Executive Thesis & Strategic Context", "headline": "Transformative market opportunity and core value proposition.", "layoutHint": "hero"},
                        {"slideId": "s_2", "purpose": "Problem Definition & Enterprise Cost", "headline": "Enterprise friction and quantified cost of current status quo.", "layoutHint": "two_column"},
                        {"slideId": "s_3", "purpose": "Proprietary Architecture & Solution", "headline": "Scalable platform capabilities delivering 4.2x ROI.", "layoutHint": "two_column"},
                        {"slideId": "s_4", "purpose": "Traction Metrics & Commercial Impact", "headline": "Accelerating revenue expansion, 135% NDR, and low payback.", "layoutHint": "metrics_grid"},
                        {"slideId": "s_5", "purpose": "Strategic Execution Roadmap", "headline": "Phased implementation milestones and next quarterly deliverables.", "layoutHint": "timeline"},
                    ]
                }

            return {
                "intent": "plan",
                "mode": "plan",
                "should_generate": False,
                "user_message": user_msg_dict,
                "assistant_message": {
                    "id": assistant_msg.id,
                    "project_id": assistant_msg.project_id,
                    "user_id": None,
                    "role": assistant_msg.role,
                    "content": assistant_msg.content,
                    "created_at": assistant_msg.created_at,
                },
                "plan_spec": plan_spec,
                "decision_questions": [
                    {
                        "id": "theme_decision",
                        "question": "Which design aesthetic do you prefer for this deck?",
                        "options": ["⚡ Obsidian Dark", "🏢 Clean Corporate Light", "🌐 Modern Indigo"]
                    }
                ],
                "guardrail_info": {
                    "input": input_guardrail.model_dump(),
                    "output": output_guardrail.model_dump(),
                },
            }

        # -------------------------------------------------------------
        # MODE 3: AUTOPILOT MODE (Default: End-to-end execution)
        # -------------------------------------------------------------
        should_generate = input_guardrail.intent == IntentCategory.DECK_GENERATION

        if should_generate:
            # Check for decisions if prompt is concise
            decision_questions = None
            if len(input_guardrail.sanitized_content.split()) <= 7:
                decision_questions = [
                    {
                        "id": "deck_depth",
                        "question": "Target slide count for this presentation?",
                        "options": ["5 Slides (Executive Brief)", "10 Slides (Standard Pitch)", "20 Slides (Full Diligence)"]
                    }
                ]

            return {
                "intent": "generate",
                "mode": "autopilot",
                "should_generate": True,
                "user_message": user_msg_dict,
                "assistant_message": None,
                "plan_spec": None,
                "decision_questions": decision_questions,
                "guardrail_info": {
                    "input": input_guardrail.model_dump(),
                    "output": None,
                },
            }

        # Conversational query in Autopilot mode (not a direct greeting/thanks, e.g. custom question)
        existing_deck = db.scalar(select(DeckVersion).where(DeckVersion.project_id == project_id))

        deck_context_note = ""
        if existing_deck:
            deck_context_note = f"\nNote: The user already has Deck v{existing_deck.version} in this workspace session."

        user_prompt_conversational = (
            f"User Inquiry: \"{input_guardrail.sanitized_content}\"\n"
            f"{deck_context_note}\n"
            f"Instructions:\n"
            f"- Understand what the user is asking and answer their specific question directly.\n"
            f"- Guardrail constraint: Keep response concise (under {input_guardrail.max_words} words). Do NOT generate unnecessary big responses, unsolicited feature lists, or multi-paragraph text.\n"
            f"- Be professional and helpful as deckpilotAI Copilot."
        )

        assistant_text = None
        try:
            llm_res = await asyncio.wait_for(
                ProviderRouter.call_llm(
                    db=db,
                    agent_type="copilot_chat",
                    system_prompt=COPILOT_CHAT_SYSTEM_PROMPT,
                    user_prompt=user_prompt_conversational,
                    response_schema=None,
                    user_id=user_id,
                ),
                timeout=6.0,
            )
            if isinstance(llm_res, dict):
                assistant_text = llm_res.get("text") or llm_res.get("content")
        except Exception:
            logger.warning("Chat provider failed or timed out; using fast fallback", exc_info=True)

        # Concise default if LLM returns empty or fails
        if not assistant_text or len(assistant_text.strip()) < 5:
            assistant_text = (
                "I am your AI Presentation Copilot at **deckpilotAI**.\n"
                "I can research, outline, and generate complete PowerPoint presentations. "
                "Share your topic or upload reference documents to get started!"
            )

        # Apply Output Guardrails
        output_guardrail = OutputGuardrailService.apply(assistant_text, input_guardrail)

        assistant_msg = Message(
            id=str(uuid.uuid4()),
            project_id=project_id,
            role="assistant",
            content=output_guardrail.content,
            created_at=max(int(time.time()), user_msg.created_at + 1),
        )
        db.add(assistant_msg)
        db.commit()
        db.refresh(assistant_msg)

        return {
            "intent": "chat",
            "mode": "autopilot",
            "should_generate": False,
            "user_message": user_msg_dict,
            "assistant_message": {
                "id": assistant_msg.id,
                "project_id": assistant_msg.project_id,
                "user_id": None,
                "role": assistant_msg.role,
                "content": assistant_msg.content,
                "created_at": assistant_msg.created_at,
            },
            "plan_spec": None,
            "decision_questions": None,
            "guardrail_info": {
                "input": input_guardrail.model_dump(),
                "output": output_guardrail.model_dump(),
            },
        }
