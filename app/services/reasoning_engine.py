"""LangGraph-powered AI Chat Reasoning & Tool Orchestration Engine.

Provides transparent step-by-step LLM reasoning for user prompts, workspace state,
intent classification, and tool selection without guessing.
"""

import asyncio
import json
import logging
import re
from typing import Any, Literal, TypedDict

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.attachment import Attachment
from app.models.deck import Artifact, DeckVersion
from app.models.message import Message
from app.services.guardrails import (
    InputGuardrailService,
    IntentCategory,
    OutputGuardrailService,
    VerbosityLevel,
)
from app.services.prompts import (
    ASK_MODE_SYSTEM_PROMPT,
    COPILOT_CHAT_SYSTEM_PROMPT,
    PLAN_MODE_SYSTEM_PROMPT,
)
from app.services.provider_router import ProviderRouter

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# State Schema for LangGraph Reasoning
# ─────────────────────────────────────────────────────────────────────────────

class ChatReasoningState(TypedDict, total=False):
    project_id: str
    user_id: str
    user_content: str
    sanitized_content: str
    has_attachments: bool
    attachment_ids: list[str]
    mode: str
    
    # Workspace Context
    has_existing_deck: bool
    existing_deck_version: int | None
    existing_deck_title: str | None
    existing_slides: list[dict[str, Any]]
    existing_brand_style: dict[str, Any] | None
    
    # Reasoning Output
    selected_tool: str
    tool_reasoning: str
    intent: str
    should_generate: bool
    targeted_slide_indices: list[int]
    is_theme_change: bool
    theme_directive: str | None
    
    # Artifacts & Outputs
    plan_spec: dict[str, Any] | None
    decision_questions: list[dict[str, Any]] | None
    assistant_text: str | None
    guardrail_input: dict[str, Any] | None
    guardrail_output: dict[str, Any] | None


# ─────────────────────────────────────────────────────────────────────────────
# Reasoning Engine Implementation
# ─────────────────────────────────────────────────────────────────────────────

REASONING_PROMPT = """You are the Reasoning & Tool Dispatch Agent for deckpilotAI Copilot.
Analyze the user's message and workspace state to choose the single most appropriate tool and extract required parameters.

WORKSPACE CONTEXT:
- Has Existing Deck: {has_existing_deck} (Version: {existing_deck_version}, Title: "{existing_deck_title}", Slides: {slide_count})
- Active Mode: {mode} (ask / plan / autopilot)
- Has File Attachments: {has_attachments}
- User Message: "{user_content}"

AVAILABLE TOOLS:
1. `generate_deck_tool`: User wants to create a new presentation from scratch (topic, outline, or attached documents).
2. `revise_deck_tool`: User wants to fix, update, edit, recolor, modify, or redo an existing presentation or specific slide(s).
3. `plan_deck_tool`: User wants an interactive slide-by-slide plan outline for review before compiling into PowerPoint.
4. `ask_advisor_tool`: User is asking a research, SWOT, strategic, or domain question without generating slides.
5. `fetch_stock_images_tool`: User wants to search or fetch stock images/photos (via Unsplash / Pexels) for slides or presentation.
6. `conversational_chat_tool`: Greetings, quick FAQs, general capabilities, or acknowledgement.

INSTRUCTIONS:
- If a deck already exists in this workspace and the user says "fix this ppt", "fix the color theme", "in slide 2 change X", "make it blue", "there is a mismatch", choose `revise_deck_tool`.
- If the user asks to find, fetch, or add images/photos from stock providers, choose `fetch_stock_images_tool`.
- Return ONLY a JSON object with:
{{
  "selected_tool": "generate_deck_tool" | "revise_deck_tool" | "plan_deck_tool" | "ask_advisor_tool" | "fetch_stock_images_tool" | "conversational_chat_tool",
  "tool_reasoning": "1-2 sentence explanation of why this tool was chosen based on prompt and context",
  "targeted_slides": [slide numbers if revising, e.g. [2]],
  "is_theme_change": true/false,
  "theme_directive": "blue" | "dark" | "emerald" | null
}}
"""


class ReasoningEngine:
    """Multi-step reasoning pipeline utilizing LangGraph state machine with fallback."""

    @classmethod
    def _extract_workspace_context(cls, db: Session, project_id: str) -> dict[str, Any]:
        """Loads relevant presentation state and existing deck specification from database."""
        latest_deck = db.scalar(
            select(DeckVersion)
            .where(DeckVersion.project_id == project_id, DeckVersion.status == "ready")
            .order_by(DeckVersion.version.desc())
        )
        has_existing = latest_deck is not None
        deck_version = latest_deck.version if latest_deck else None
        deck_title = None
        slides: list[dict[str, Any]] = []
        brand_style = None

        if latest_deck and latest_deck.deck_json_artifact_id:
            art = db.scalar(select(Artifact).where(Artifact.id == latest_deck.deck_json_artifact_id))
            if art and art.json_data:
                try:
                    spec = json.loads(art.json_data)
                    deck_title = spec.get("deckTitle")
                    slides = spec.get("slides", [])
                    brand_style = spec.get("brandStyle")
                except Exception:
                    pass

        return {
            "has_existing_deck": has_existing,
            "existing_deck_version": deck_version,
            "existing_deck_title": deck_title,
            "existing_slides": slides,
            "existing_brand_style": brand_style,
        }

    @classmethod
    def _deterministic_reasoning(
        cls,
        user_content: str,
        mode: str,
        has_attachments: bool,
        has_existing_deck: bool,
        existing_slides: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """High-precision deterministic rule reasoning when LLM reasoning is bypassed or offline."""
        lower = user_content.lower().strip()
        
        # 1. Mode overrides
        if mode == "ask":
            return {
                "selected_tool": "ask_advisor_tool",
                "tool_reasoning": "User explicitly selected Ask mode for research/advisory without slide generation.",
                "targeted_slides": [],
                "is_theme_change": False,
                "theme_directive": None,
            }
        if mode == "plan":
            return {
                "selected_tool": "plan_deck_tool",
                "tool_reasoning": "User selected Plan mode to outline slide narrative before PPTX compilation.",
                "targeted_slides": [],
                "is_theme_change": False,
                "theme_directive": None,
            }

        # 2. Check for Greetings / Politeness / FAQs
        input_guard = InputGuardrailService.evaluate(user_content, has_attachments=has_attachments, mode=mode)
        if input_guard.intent in (
            IntentCategory.GREETING,
            IntentCategory.POLITENESS,
            IntentCategory.CAPABILITY_QUERY,
            IntentCategory.CASUAL_HELP,
        ):
            return {
                "selected_tool": "conversational_chat_tool",
                "tool_reasoning": f"Query classified as {input_guard.intent.value} requiring crisp conversational response.",
                "targeted_slides": [],
                "is_theme_change": False,
                "theme_directive": None,
            }

        # 3. Check for stock image request
        if re.search(r"\b(find|fetch|search|get|add|insert)\s+(images?|photos?|pictures?|visuals?)\b", lower) or "unsplash" in lower or "pexels" in lower:
            from app.agents.revision_agent import RevisionAgent
            fake_spec = {"slides": existing_slides} if existing_slides else {}
            targets = RevisionAgent.detect_target_slide_indices(user_content, fake_spec)
            return {
                "selected_tool": "fetch_stock_images_tool",
                "tool_reasoning": "User requested finding or fetching stock images/photos for the deck.",
                "targeted_slides": [t + 1 for t in targets],
                "is_theme_change": False,
                "theme_directive": None,
            }

        # 4. Check for Revision if deck exists or revision keywords present
        is_fix_prompt = any(w in lower for w in (
            "fix", "change", "update", "edit", "modify", "rewrite", "replace", "revise",
            "tweak", "adjust", "redo", "rework", "mismatch", "inconsistency", "make slide",
            "in slide", "color theme", "theme to", "numbers to"
        ))

        theme_match = re.search(r"\b(?:theme|color|palette)\s*(?:to|as|:|=)?\s*([a-zA-Z]+)\b", lower)
        theme_dir = theme_match.group(1) if theme_match else None
        is_theme = bool(theme_dir or any(w in lower for w in ("dark mode", "light mode", "blue theme", "obsidian", "emerald")))

        if has_existing_deck and (is_fix_prompt or input_guard.intent == IntentCategory.REVISION):
            # Detect target slide index(es)
            from app.agents.revision_agent import RevisionAgent
            fake_spec = {"slides": existing_slides} if existing_slides else {}
            targets = RevisionAgent.detect_target_slide_indices(user_content, fake_spec)
            
            return {
                "selected_tool": "revise_deck_tool",
                "tool_reasoning": "Existing presentation detected in workspace and user requested targeted fixes or revisions.",
                "targeted_slides": [t + 1 for t in targets],
                "is_theme_change": is_theme,
                "theme_directive": theme_dir,
            }

        # 5. Generate Deck
        if has_attachments or input_guard.intent == IntentCategory.DECK_GENERATION or len(lower.split()) >= 4:
            return {
                "selected_tool": "generate_deck_tool",
                "tool_reasoning": "Presentation creation intent recognized in Autopilot mode.",
                "targeted_slides": [],
                "is_theme_change": False,
                "theme_directive": None,
            }

        # 5. Default conversational Q&A
        return {
            "selected_tool": "conversational_chat_tool",
            "tool_reasoning": "General inquiry answered conversationally without generation.",
            "targeted_slides": [],
            "is_theme_change": False,
            "theme_directive": None,
        }

    @classmethod
    async def reason_and_route(
        cls,
        db: Session,
        project_id: str,
        user_id: str,
        content: str,
        has_attachments: bool = False,
        attachment_ids: list[str] | None = None,
        mode: str = "autopilot",
    ) -> ChatReasoningState:
        """
        Executes the reasoning graph:
        1. Context extraction (DB state, existing deck).
        2. LLM reasoning over workspace state and tool definitions.
        3. Fallback deterministic reasoning if LLM call is unavailable.
        4. Structured routing state output.
        """
        ws_ctx = cls._extract_workspace_context(db, project_id)
        sanitized = InputGuardrailService.sanitize_input(content)

        state: ChatReasoningState = {
            "project_id": project_id,
            "user_id": user_id,
            "user_content": content,
            "sanitized_content": sanitized,
            "has_attachments": has_attachments,
            "attachment_ids": attachment_ids or [],
            "mode": mode,
            "has_existing_deck": ws_ctx["has_existing_deck"],
            "existing_deck_version": ws_ctx["existing_deck_version"],
            "existing_deck_title": ws_ctx["existing_deck_title"],
            "existing_slides": ws_ctx["existing_slides"],
            "existing_brand_style": ws_ctx["existing_brand_style"],
            "plan_spec": None,
            "decision_questions": None,
            "assistant_text": None,
        }

        # Step 1: Check Input Guardrails for Safety & Direct Greetings
        input_guard = InputGuardrailService.evaluate(sanitized, has_attachments=has_attachments, mode=mode)
        state["guardrail_input"] = input_guard.model_dump()

        if not input_guard.is_safe:
            state["selected_tool"] = "conversational_chat_tool"
            state["tool_reasoning"] = "Safety guardrail violation handled."
            state["intent"] = "chat"
            state["should_generate"] = False
            state["assistant_text"] = input_guard.direct_response or "Request could not be processed due to safety guidelines."
            return state

        if input_guard.direct_response and mode == "autopilot" and not ws_ctx["has_existing_deck"]:
            state["selected_tool"] = "conversational_chat_tool"
            state["tool_reasoning"] = "Direct greeting / politeness handled crisply without LLM call."
            state["intent"] = "chat"
            state["should_generate"] = False
            state["assistant_text"] = input_guard.direct_response
            return state

        # Step 2: LLM Reasoning Graph Step (with fast fallback)
        reasoning_decision = None
        try:
            prompt_formatted = REASONING_PROMPT.format(
                has_existing_deck=ws_ctx["has_existing_deck"],
                existing_deck_version=ws_ctx["existing_deck_version"] or "None",
                existing_deck_title=ws_ctx["existing_deck_title"] or "None",
                slide_count=len(ws_ctx["existing_slides"]),
                mode=mode,
                has_attachments=has_attachments,
                user_content=sanitized[:1000],
            )

            llm_res = await asyncio.wait_for(
                ProviderRouter.call_llm(
                    db=db,
                    agent_type="copilot_chat",
                    system_prompt="You are a precise presentation router. Respond with valid JSON only.",
                    user_prompt=prompt_formatted,
                    response_schema={"type": "object"},
                    user_id=user_id,
                ),
                timeout=4.0,
            )
            if isinstance(llm_res, dict) and "selected_tool" in llm_res:
                reasoning_decision = llm_res
        except Exception as e:
            logger.info("Fast reasoning fallback engaged (%s)", e)

        if not reasoning_decision or not isinstance(reasoning_decision, dict):
            reasoning_decision = cls._deterministic_reasoning(
                user_content=sanitized,
                mode=mode,
                has_attachments=has_attachments,
                has_existing_deck=ws_ctx["has_existing_deck"],
                existing_slides=ws_ctx["existing_slides"],
            )

        selected_tool = reasoning_decision.get("selected_tool", "conversational_chat_tool")
        tool_reasoning = reasoning_decision.get("tool_reasoning", "Tool determined via reasoning engine.")
        state["selected_tool"] = selected_tool
        state["tool_reasoning"] = tool_reasoning
        state["is_theme_change"] = bool(reasoning_decision.get("is_theme_change"))
        state["theme_directive"] = reasoning_decision.get("theme_directive")

        # Step 3: Tool Dispatch & Action Synthesis
        if selected_tool == "revise_deck_tool":
            state["intent"] = "revise"
            state["should_generate"] = True
            targets = reasoning_decision.get("targeted_slides", [])
            state["targeted_slide_indices"] = [int(x) - 1 for x in targets if isinstance(x, (int, str)) and str(x).isdigit()]
            return state

        elif selected_tool == "generate_deck_tool":
            state["intent"] = "generate"
            state["should_generate"] = True
            if len(sanitized.split()) <= 7:
                state["decision_questions"] = [
                    {
                        "id": "deck_depth",
                        "question": "Target slide count for this presentation?",
                        "options": ["5 Slides (Executive Brief)", "10 Slides (Standard Pitch)", "20 Slides (Full Diligence)"],
                    }
                ]
            return state

        elif selected_tool == "plan_deck_tool":
            state["intent"] = "plan"
            state["should_generate"] = False
            state["decision_questions"] = [
                {
                    "id": "theme_decision",
                    "question": "Which design aesthetic do you prefer for this deck?",
                    "options": ["⚡ Obsidian Dark", "🏢 Clean Corporate Light", "🌐 Modern Indigo"],
                }
            ]
            return state

        elif selected_tool == "fetch_stock_images_tool":
            state["intent"] = "revise" if ws_ctx["has_existing_deck"] else "generate"
            state["should_generate"] = True
            targets = reasoning_decision.get("targeted_slides", [])
            state["targeted_slide_indices"] = [int(x) - 1 for x in targets if isinstance(x, (int, str)) and str(x).isdigit()]
            return state

        elif selected_tool == "ask_advisor_tool":
            state["intent"] = "ask"
            state["should_generate"] = False
            return state

        else:
            state["intent"] = "chat"
            state["should_generate"] = False
            return state
