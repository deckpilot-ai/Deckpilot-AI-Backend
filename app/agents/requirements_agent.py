"""Requirements analysis agent for interpreting user presentation briefs."""

import logging
import re
from typing import Any

from app.schemas.generation_state import PresentationGoal, PresentationType
from app.skills.skill_registry import get_skill_for_request

logger = logging.getLogger(__name__)


class RequirementsAgent:
    """Extracts presentation goal, target slide count, audience, domain, and visual needs."""

    @classmethod
    def analyze_requirements(
        cls,
        user_prompt: str,
        reference_files: list[str] | None = None,
        reference_asset_count: int = 0,
        grounded_text_length: int = 0,
        target_slide_count: int | None = None,
    ) -> PresentationGoal:
        prompt_lower = user_prompt.lower()
        files = reference_files or []

        NUMBER_WORDS = {
            "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
            "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
            "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19,
            "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50
        }

        # 1. Slide Count detection (supports "12 page", "12 slides", "deck of 12", "12-page", "twelve slides")
        if target_slide_count is not None and target_slide_count > 0:
            slide_count = target_slide_count
        else:
            count_match = re.search(
                r"\b(\d+)\s*[-_]?(?:slides?|pages?|pgs?|screens?|cards?|sections?|parts?)\b"
                r"|\b(?:deck|presentation|slides?|pages?)\s+of\s+(\d+)\b"
                r"|\b(?:target|count|length|size)\s*[:=]?\s*(\d+)\b"
                r"|\b(\d+)\s*[-_]?(?:slide|page)\s+(?:deck|presentation|ppt|pptx)\b",
                user_prompt,
                re.IGNORECASE,
            )
            detected_num = None
            if count_match:
                for grp in count_match.groups():
                    if grp and grp.isdigit():
                        detected_num = int(grp)
                        break

            if detected_num is None:
                for word, num in NUMBER_WORDS.items():
                    if re.search(rf"\b{word}\s*[-_]?(?:slides?|pages?|pgs?|screens?|cards?|deck|parts?)\b|\b(?:deck|presentation)\s+of\s+{word}\b", user_prompt, re.IGNORECASE):
                        detected_num = num
                        break

            if detected_num is not None:
                slide_count = max(1, min(detected_num, 60))
            elif "quick" in prompt_lower or "short" in prompt_lower or "summary" in prompt_lower:
                slide_count = 5
            elif "investor" in prompt_lower or "pitch" in prompt_lower:
                slide_count = 10
            elif reference_asset_count > 10 and grounded_text_length > 5000:
                # In-depth textbook or extensive reference doc default
                slide_count = 14
            else:
                slide_count = 8

        # 2. Presentation Type classification
        if "pitch" in prompt_lower or "investor" in prompt_lower or "fundraise" in prompt_lower or "seed" in prompt_lower:
            p_type = PresentationType.PITCH_DECK
            audience = "Venture Capitalists & Angel Investors"
            tone = "dynamic_visionary"
        elif "architecture" in prompt_lower or "tech" in prompt_lower or "cloud" in prompt_lower or "ai" in prompt_lower or "saas" in prompt_lower or "system" in prompt_lower:
            p_type = PresentationType.TECHNICAL_ARCHITECTURE
            audience = "CTOs, Technical Leads & Architects"
            tone = "modern_technical"
        elif "financial" in prompt_lower or "earning" in prompt_lower or "revenue" in prompt_lower or "budget" in prompt_lower or "q1" in prompt_lower or "q2" in prompt_lower or "q3" in prompt_lower or "q4" in prompt_lower:
            p_type = PresentationType.FINANCIAL_REVIEW
            audience = "CFOs, Executive Board & Investors"
            tone = "analytical_restrained"
        elif "history" in prompt_lower or "ncert" in prompt_lower or "chapter" in prompt_lower or "education" in prompt_lower or "lecture" in prompt_lower:
            p_type = PresentationType.RESEARCH_EDUCATION
            audience = "Students, Educators & Domain Specialists"
            tone = "authoritative_editorial"
        elif "consulting" in prompt_lower or "transformation" in prompt_lower or "market entry" in prompt_lower:
            p_type = PresentationType.CONSULTING_DECK
            audience = "Senior Leadership & Strategy Teams"
            tone = "structured_insight_driven"
        else:
            p_type = PresentationType.BUSINESS_STRATEGY
            audience = "Executive Leadership & Board"
            tone = "executive_authoritative"

        # 3. Topic Extraction
        first_line = user_prompt.strip().split("\n")[0]
        topic = re.sub(r"^(?:generate|create|make|build|prepare)\s+(?:a|an)?\s*(?:\d+[- ]slide\s+)?(?:presentation|deck)?\s*(?:on|about|for)?\s*", "", first_line, flags=re.IGNORECASE).strip()
        if not topic or len(topic) < 3:
            topic = "Executive Strategic Review"
        topic = topic[:80].strip()

        # 4. Check references
        has_docs = reference_asset_count > 0 or len(files) > 0 or grounded_text_length > 0
        has_ppt = any(f.endswith(".pptx") for f in files)

        # 5. Determine chart/table needs
        req_charts = []
        if p_type in (PresentationType.FINANCIAL_REVIEW, PresentationType.PITCH_DECK, PresentationType.BUSINESS_STRATEGY):
            req_charts.extend(["column", "bar", "line"])
        
        req_tables = []
        if "table" in prompt_lower or p_type == PresentationType.FINANCIAL_REVIEW:
            req_tables.append("comparison_table")

        return PresentationGoal(
            topic=topic,
            objective=f"Deliver a clear, authoritative presentation on {topic} tailored to {audience}.",
            audience=audience,
            industry=p_type.value,
            presentation_type=p_type,
            target_slide_count=slide_count,
            tone=tone,
            narrative_arc="pyramid" if p_type != PresentationType.RESEARCH_EDUCATION else "chronological_thematic",
            has_reference_docs=has_docs,
            has_reference_ppt=has_ppt,
            required_charts=req_charts,
            required_tables=req_tables,
        )
