"""Content Classifier for Slide Semantics.

Extracts semantic signals from raw slide data to power deterministic layout selection.
"""

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class SlideSignals:
    slide_intent: str = "content"
    item_count: int = 0
    has_image: bool = False
    has_table: bool = False
    has_chart: bool = False
    has_quote: bool = False
    has_statistics: bool = False
    has_process: bool = False
    has_timeline: bool = False
    has_comparison: bool = False
    is_dark_preferred: bool = False
    title_words: int = 0
    tags: List[str] = field(default_factory=list)


class ContentClassifier:
    """Classifies slide copy and structural elements into semantic signals."""

    @classmethod
    def classify(cls, slide_data: Dict[str, Any], slide_index: int = 0, total_slides: int = 1) -> SlideSignals:
        signals = SlideSignals()
        
        headline = str(slide_data.get("title") or slide_data.get("headline") or "")
        body = str(slide_data.get("body") or "")
        kicker = str(slide_data.get("kicker") or slide_data.get("eyebrow") or "")
        bullets = slide_data.get("items") or slide_data.get("bullets") or []
        combined_text = f"{kicker} {headline} {body} {' '.join(str(b) for b in bullets)}".lower()
        
        signals.title_words = len(headline.split())
        signals.item_count = len(bullets)
        signals.has_image = bool(slide_data.get("image_id") or slide_data.get("image_artifact_id"))
        signals.has_table = bool(slide_data.get("table_headers") or slide_data.get("table") or slide_data.get("table_rows"))
        signals.has_chart = bool(slide_data.get("chart_series") or slide_data.get("chart"))
        signals.has_quote = bool(slide_data.get("quote") or slide_data.get("callout"))

        # Detect position-based intent
        if slide_index == 0:
            signals.slide_intent = "cover"
            signals.is_dark_preferred = True
            return signals
            
        if slide_index == total_slides - 1:
            if any(w in combined_text for w in ["closing", "reflection", "debate", "future", "where do we", "question", "thank"]):
                signals.slide_intent = "closing"
                signals.is_dark_preferred = True
                return signals

        # Detect timeline
        if re.search(r"\b(chronology|timeline|history|evolution|centuries|milestones|phases|years?)\b", combined_text) and any(re.search(r"\b(19\d\d|20\d\d|phase|century)\b", str(b), re.I) for b in bullets):
            signals.has_timeline = True
            signals.slide_intent = "timeline"

        # Detect process / steps
        elif re.search(r"\b(step\s*\d|process|workflow|stages?|procedure|methodology)\b", combined_text):
            signals.has_process = True
            signals.slide_intent = "process"

        # Detect statistics / KPI
        elif any(re.search(r"(\$|€|£|₹|\bUS\$|\%|\b\d{2,}\%|\b\d+\s*years|\b\d+\s*districts)", str(b)) for b in bullets) or slide_data.get("stats"):
            signals.has_statistics = True
            signals.slide_intent = "kpi"

        # Detect section transition / opener
        elif re.search(r"\b(looking ahead|thematic shift|part\s*\d|chapter\s*\d|section\s*\d|sustainability)\b", combined_text) and signals.has_quote:
            signals.slide_intent = "section_opener"
            signals.is_dark_preferred = True

        # Detect summary / takeaways
        elif re.search(r"\b(summary|takeaways?|key findings|conclusions?|in summary)\b", combined_text):
            signals.slide_intent = "summary"

        # Detect agenda / roadmap
        elif re.search(r"\b(agenda|roadmap|outline|overview|what this chapter|table of contents)\b", combined_text) and 4 <= signals.item_count <= 6:
            signals.slide_intent = "agenda"

        # Detect comparison
        elif re.search(r"\b(versus|vs|compare|comparison|tradeoff|conflicts?|disparit)\b", combined_text):
            signals.has_comparison = True
            signals.slide_intent = "comparison"

        return signals
