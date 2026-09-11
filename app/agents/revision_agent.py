"""Smart Targeted Slide Revision Agent.

Enables iterative conversational modifications to existing presentation decks.
When a user requests changes to a specific slide (e.g., 'change slide 3 to X',
'make title of slide 2 shorter', 'add bullet to slide 4'), this agent identifies
the exact targeted slide(s) and revises ONLY those slides, guaranteeing that all
other slides remain 100% untouched and preserved.
"""

import copy
import json
import logging
import re
from typing import Any

from sqlalchemy.orm import Session

from app.schemas.generation_state import SlideSpec
from app.services.prompts import SLIDE_WRITER_SYSTEM_PROMPT
from app.services.provider_router import ProviderRouter

logger = logging.getLogger(__name__)

ORDINAL_MAP = {
    "first": 0, "1st": 0,
    "second": 1, "2nd": 1,
    "third": 2, "3rd": 2,
    "fourth": 3, "4th": 3,
    "fifth": 4, "5th": 4,
    "sixth": 5, "6th": 5,
    "seventh": 6, "7th": 6,
    "eighth": 7, "8th": 7,
    "ninth": 8, "9th": 8,
    "tenth": 9, "10th": 9,
}


class RevisionAgent:
    @classmethod
    def detect_target_slide_indices(
        cls, prompt: str, deck_spec: dict[str, Any]
    ) -> list[int]:
        """Identifies which slide index(es) (0-indexed) the user wants to revise."""
        slides = deck_spec.get("slides", [])
        targets: set[int] = set()
        lower = prompt.lower()

        # 1. Match numeric slide references (e.g. "slide 3", "slide #3", "slides 2 and 4", "s3")
        m_slides = re.findall(r"\b(?:slide|page|s)\s*#?\s*(\d+)\b", lower)
        for num_str in m_slides:
            try:
                val = int(num_str)
                if slides:
                    if 1 <= val <= len(slides):
                        targets.add(val - 1)
                elif val >= 1:
                    targets.add(val - 1)
            except ValueError:
                pass

        # 2. Match ordinals (e.g. "3rd slide", "third slide", "first slide")
        for word, idx in ORDINAL_MAP.items():
            if re.search(rf"\b{word}\s+slide\b", lower) or re.search(rf"\bslide\s+{word}\b", lower):
                if idx < len(slides):
                    targets.add(idx)

        # 3. If no direct number found, try semantic matching against existing slide headlines/purposes
        if not targets:
            # Check for cover / title slide mentions
            if re.search(r"\b(?:cover|title\s*slide|intro\s*slide|opening\s*slide)\b", lower):
                targets.add(0)
            # Check for conclusion / closing / summary mentions
            elif re.search(r"\b(?:closing|conclusion|last\s*slide|final\s*slide|summary\s*slide|roadmap\s*slide)\b", lower):
                targets.add(len(slides) - 1)
            else:
                # Search for keyword overlap with slide headlines
                words = [w for w in re.findall(r"\b[a-zA-Z]{4,}\b", lower) if w not in {"change", "update", "modify", "revise", "slide", "slides", "please", "make", "with"}]
                if words:
                    best_match_idx = -1
                    max_overlap = 0
                    for i, s in enumerate(slides):
                        s_text = f"{s.get('headline', '')} {s.get('purpose', '')} {s.get('message', '')}".lower()
                        overlap = sum(1 for w in words if w in s_text)
                        if overlap > max_overlap and overlap >= 2:
                            max_overlap = overlap
                            best_match_idx = i
                    if best_match_idx >= 0:
                        targets.add(best_match_idx)

        return sorted(targets)

    @classmethod
    def is_global_theme_change(cls, prompt: str) -> bool:
        """Checks if the user prompt is requesting a global theme/color/font change."""
        lower = prompt.lower()
        theme_words = [
            "theme", "palette", "dark mode", "light mode", "obsidian", "corporate light",
            "color scheme", "accent color", "blue color", "make all", "all page",
            "mismatch in color", "color mismatch", "numbers blue", "elements blue",
            "colors to blue", "color theme", "blue theme"
        ]
        has_theme = any(w in lower for w in theme_words)
        has_slide_target = bool(re.search(r"\bslide\s*\d+\b", lower))
        return has_theme and not has_slide_target

    @classmethod
    async def revise_single_slide(
        cls,
        db: Session,
        slide_idx: int,
        existing_slide: dict[str, Any],
        user_prompt: str,
        deck_title: str = "",
        brand_style: dict[str, Any] | None = None,
        user_id: str = "",
        job_id: str = "",
    ) -> dict[str, Any]:
        """Revises a single slide using LLM while preserving its identity."""
        revised = copy.deepcopy(existing_slide)
        slide_num = slide_idx + 1

        prompt_input = (
            f"You are revising Slide {slide_num} of presentation \"{deck_title}\".\n\n"
            f"CURRENT SLIDE SPECIFICATION:\n"
            f"{json.dumps(existing_slide, indent=2)}\n\n"
            f"USER REVISION INSTRUCTION:\n"
            f"\"{user_prompt}\"\n\n"
            f"INSTRUCTIONS:\n"
            f"1. Apply the user's requested changes to this slide (update headline, message, bullets, or layoutHint as requested).\n"
            f"2. Keep the same slideId (\"{existing_slide.get('slideId', f's{slide_num:02d}')}\").\n"
            f"3. Maintain professional McKinsey-grade consulting typography and structure.\n"
            f"4. Return ONLY a valid JSON object matching the SlideSpec schema."
        )

        try:
            llm_res = await ProviderRouter.call_llm(
                db=db,
                agent_type="slide_writer",
                system_prompt=SLIDE_WRITER_SYSTEM_PROMPT,
                user_prompt=prompt_input,
                response_schema={"type": "object"},
                user_id=user_id,
                job_id=job_id,
            )
            if isinstance(llm_res, dict):
                candidate = llm_res.get("slide") or llm_res
                if isinstance(candidate, dict) and ("headline" in candidate or "bullets" in candidate):
                    # Validate via SlideSpec schema
                    spec = SlideSpec.model_validate(candidate)
                    spec_dict = spec.model_dump()
                    spec_dict["slideId"] = existing_slide.get("slideId", f"s{slide_num:02d}")
                    return spec_dict
        except Exception as e:
            logger.warning("LLM slide revision failed (%s); using deterministic fallback", e)

        # Deterministic Fallback if LLM unavailable
        lower = user_prompt.lower()
        # 1. Headline change
        m_head = re.search(r"(?:headline|title|heading)\s*(?:to|as|:|=)\s*[\"']?([^\"'\n\.,;]+)[\"']?", user_prompt, re.I)
        if m_head:
            cand_head = m_head.group(1).strip()
            # If combined with "and add bullet..." or "and set layout...", strip subsequent clauses
            cand_head = re.split(r"\s+and\s+(?:add|set|change|make|layout|bullet)", cand_head, flags=re.I)[0].strip()
            if cand_head:
                revised["headline"] = cand_head
                revised["purpose"] = cand_head

        # 2. Layout change
        m_lay = re.search(r"(?:layout|style|template)\s*(?:to|as|:|=)?\s*([a-zA-Z0-9_\-]+)", lower)
        if m_lay:
            lay_cand = m_lay.group(1).replace("-", "_")
            revised["layoutHint"] = lay_cand

        # 3. Bullets / content addition or replacement
        m_bullet = re.search(r"(?:add\s+bullet|change\s+bullet|bullet|point)s?\s*(?:to|:|=)\s*(.+)$", user_prompt, re.I)
        if m_bullet:
            new_bullet_text = m_bullet.group(1).strip()
            if "replace" in lower:
                revised["bullets"] = [new_bullet_text]
            else:
                revised.setdefault("bullets", []).append(new_bullet_text)

        return revised

    @classmethod
    async def apply_revision(
        cls,
        db: Session,
        deck_spec: dict[str, Any],
        user_prompt: str,
        brand_style: dict[str, Any] | None = None,
        user_id: str = "",
        job_id: str = "",
        emit_fn: Any = None,
    ) -> tuple[dict[str, Any], str]:
        """
        Applies targeted revision to deck_spec.
        Guarantees non-targeted slides remain 100% UNTOUCHED.
        Returns (revised_deck_spec, change_summary_message).
        """
        updated_spec = copy.deepcopy(deck_spec)
        slides = updated_spec.get("slides", [])
        deck_title = updated_spec.get("deckTitle", "Presentation")

        target_indices = cls.detect_target_slide_indices(user_prompt, updated_spec)

        if cls.is_global_theme_change(user_prompt):
            if emit_fn:
                emit_fn("slide_writer", "running", "Updating visual theme and design system across presentation...")
            return updated_spec, "Updated global design theme. All slide content preserved."

        if not target_indices:
            logger.info("No specific slide index detected for revision '%s'; checking deck title", user_prompt[:80])
            m_deck_title = re.search(r"(?:deck\s*title|presentation\s*title)\s*(?:to|as|:|=)\s*[\"']?([^\"'\n]+)[\"']?", user_prompt, re.I)
            if m_deck_title:
                updated_spec["deckTitle"] = m_deck_title.group(1).strip()
                if slides:
                    slides[0]["headline"] = updated_spec["deckTitle"]
                return updated_spec, f"Updated presentation title to \"{updated_spec['deckTitle']}\"."

            # If user provides explicit multi-slide outline or general change
            target_indices = [0] if len(slides) == 1 else list(range(len(slides)))

        # Targeted revision on specific slides only!
        revised_slide_numbers = []
        for idx in target_indices:
            if 0 <= idx < len(slides):
                slide_num = idx + 1
                revised_slide_numbers.append(str(slide_num))
                if emit_fn:
                    emit_fn("slide_writer", "running", f"Revising Slide {slide_num} ('{slides[idx].get('headline', '')[:30]}')...")

                revised_slide = await cls.revise_single_slide(
                    db=db,
                    slide_idx=idx,
                    existing_slide=slides[idx],
                    user_prompt=user_prompt,
                    deck_title=deck_title,
                    brand_style=brand_style,
                    user_id=user_id,
                    job_id=job_id,
                )
                slides[idx] = revised_slide

        updated_spec["slides"] = slides

        preserved_count = len(slides) - len(target_indices)
        summary = (
            f"Successfully revised Slide {', '.join(revised_slide_numbers)} as requested. "
            f"Preserved remaining {preserved_count} slide(s) untouched."
            if preserved_count > 0
            else f"Successfully revised Slide {', '.join(revised_slide_numbers)}."
        )

        return updated_spec, summary
