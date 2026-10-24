"""Title intelligence, message-driven generation, and quality validation agent."""

import logging
import re
from typing import Any

from app.schemas.generation_state import ValidationCategory, ValidationIssue, ValidationSeverity

logger = logging.getLogger(__name__)


class TitleIntelligence:
    """Transforms static slide titles into insight-driven action headlines and validates title quality."""

    @classmethod
    async def synthesize_impactful_title_llm(
        cls,
        db: Any,
        raw_title: str,
        topic: str,
        context_text: str = "",
        user_id: str | None = None,
        job_id: str | None = None,
    ) -> str:
        """Uses LLM reasoning to synthesize a punchy, impactful 1-4 word slide headline."""
        from app.services.provider_router import ProviderRouter
        prompt = (
            f"Presentation Topic: {topic}\n"
            f"Draft / Context Title: {raw_title}\n"
            f"Slide Body & Details: {context_text[:400]}\n\n"
            "Task: Reason about the core meaning of this slide. Synthesize a high-impact executive headline that:\n"
            "1. Is STRICTLY 1 TO 4 WORDS (minimum 1 word, maximum 4 words).\n"
            "2. Is punchy, authoritative, and encapsulates the complete essence of the slide at a glance.\n"
            "3. Is NOT a sentence, question, or fragment.\n"
            "Return ONLY the 1-4 word headline without quotes, markdown, or trailing periods."
        )
        try:
            res = await ProviderRouter.call_llm(
                db=db,
                agent_type="slide_writer",
                system_prompt="You are an Executive Presentation Headline Architect. You synthesize impactful 1-4 word slide titles through deep semantic reasoning.",
                user_prompt=prompt,
                user_id=user_id,
                job_id=job_id,
            )
            cand = res.strip() if isinstance(res, str) else (res.get("headline") or res.get("title") or "")
            cand = re.sub(r'["\']', '', str(cand)).strip()
            words = cand.split()
            if 1 <= len(words) <= 4:
                return cand
        except Exception as e:
            logger.debug("LLM title synthesis advisory: %s", e)

        # Fallback to general structural normalization
        from app.presentation.themes.development_editorial.typography import normalize_title
        clean_title, _ = normalize_title(raw_title, max_words=4)
        return clean_title

    @classmethod
    def enhance_title(cls, current_title: str, topic: str, slide_type: str = "content", key_takeaway: str = "") -> str:
        from app.presentation.themes.development_editorial.typography import normalize_title

        clean = re.sub(r"[ \t]+", " ", current_title).strip()
        if not clean or len(clean) < 2:
            base = topic.title().split()[:3]
            clean = " ".join(base) or "Overview"

        title, _ = normalize_title(clean, max_words=4)
        return title

    @classmethod
    def validate_titles(cls, titles: list[str]) -> list[ValidationIssue]:
        """Validates all slide titles across a presentation for length, duplication, and quality."""
        issues: list[ValidationIssue] = []
        seen_titles: dict[str, int] = {}

        for idx, t in enumerate(titles):
            clean = t.strip()
            word_count = len(clean.split())
            lower_t = clean.lower()

            # 1. Duplication check
            if lower_t in seen_titles:
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.HIGH,
                    category=ValidationCategory.CONTENT,
                    slide_number=idx + 1,
                    message=f"Duplicate slide title: '{clean}' (matches Slide {seen_titles[lower_t] + 1})",
                    suggested_fix="Refine title to reflect this slide's distinct topic or takeaway",
                ))
            else:
                seen_titles[lower_t] = idx

            # 2. Length check (Strict 1-4 words rule)
            if word_count > 4:
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.HIGH,
                    category=ValidationCategory.CONTENT,
                    slide_number=idx + 1,
                    message=f"Title is too long ({word_count} words; strict maximum is 4 words): '{clean}'",
                    suggested_fix="Condense title into 1-4 impactful words and move details to subtitle or lead prose",
                ))
            elif word_count == 0:
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.CRITICAL,
                    category=ValidationCategory.CONTENT,
                    slide_number=idx + 1,
                    message="Slide title is empty",
                    suggested_fix="Add an impactful 1-4 word headline",
                ))

        return issues
