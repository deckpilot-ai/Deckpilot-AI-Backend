"""Title intelligence, message-driven generation, and quality validation agent."""

import logging
import re
from typing import Any

from app.schemas.generation_state import ValidationCategory, ValidationIssue, ValidationSeverity

logger = logging.getLogger(__name__)


class TitleIntelligence:
    """Transforms static slide titles into insight-driven action headlines and validates title quality."""

    # Generic titles to upgrade
    GENERIC_PATTERNS = [
        (r"^(?:market|market\s+overview|market\s+size)$", "Substantial Market Growth Creates Immediate Strategic Expansion Window"),
        (r"^(?:revenue|revenue\s+analysis|financials)$", "Strong Revenue Trajectory Driven by Core Customer Expansion and Efficiency"),
        (r"^(?:technology|tech\s+stack|architecture)$", "Scalable High-Throughput Architecture Built for Enterprise Reliability"),
        (r"^(?:roadmap|execution\s+plan)$", "Disciplined Phased Execution Targeting Scalable Enterprise Milestones"),
        (r"^(?:traction|growth)$", "Accelerating Commercial Momentum Demonstrating Product-Market Fit"),
        (r"^(?:competition|competitive\s+landscape)$", "Defensible Competitive Moat Anchored by Proprietary Tooling and Superior Speed"),
    ]

    @classmethod
    def enhance_title(cls, current_title: str, topic: str, slide_type: str = "content", key_takeaway: str = "") -> str:
        clean = re.sub(r"[ \t]+", " ", current_title).strip()
        if not clean or len(clean) < 3:
            return f"Strategic Insights: {topic.title()}"

        # If already an action sentence with verb, keep it
        has_verb = bool(re.search(r"\b(?:is|are|was|were|has|have|drives|accelerates|delivers|enables|powers|expands|achieves|transforms|proves|outpaces|grew|scaled)\b", clean, re.IGNORECASE))
        if has_verb and len(clean.split()) >= 4:
            return clean

        # Check generic pattern replacements
        for pattern, replacement in cls.GENERIC_PATTERNS:
            if re.match(pattern, clean, re.IGNORECASE):
                return replacement

        # If takeaway is substantive and concise, use it to make title action-driven
        if key_takeaway and len(key_takeaway.split()) <= 12 and bool(re.search(r"\b(?:is|are|drives|enables|achieves)\b", key_takeaway, re.I)):
            return key_takeaway

        return clean

    @classmethod
    def validate_titles(cls, titles: list[str]) -> list[ValidationIssue]:
        """Validates all slide titles across a presentation for length, duplication, and generic repetition."""
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

            # 2. Length check
            if word_count > 16:
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.MEDIUM,
                    category=ValidationCategory.CONTENT,
                    slide_number=idx + 1,
                    message=f"Title is too long ({word_count} words; recommended max 14 words)",
                    suggested_fix="Condense title into a crisp headline and move details to subtitle or takeaway",
                ))
            elif word_count <= 1 and idx > 0:
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.LOW,
                    category=ValidationCategory.CONTENT,
                    slide_number=idx + 1,
                    message=f"One-word title '{clean}' is too generic for executive presentation",
                    suggested_fix="Expand title into a complete insight headline",
                ))

        return issues
