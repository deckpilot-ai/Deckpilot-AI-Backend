"""Extraction and Slide Content Quality Assurance Engine.

Computes comprehensive text extraction, image extraction, slide density,
and source utilization metrics for DeckPilot AI presentation generation.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from app.schemas.generation_state import SlideSpec, normalize_bullet_items

logger = logging.getLogger(__name__)


class ExtractionQAResult:
    def __init__(self) -> None:
        # Document Text Extraction Metrics
        self.total_pages: int = 0
        self.pages_parsed: int = 0
        self.text_blocks_count: int = 0
        self.headings_detected: int = 0
        self.paragraphs_detected: int = 0
        self.tables_detected: int = 0
        self.figures_detected: int = 0
        self.captions_detected: int = 0
        self.images_detected: int = 0
        self.suspicious_low_pages: list[int] = []
        self.zero_extraction_pages: list[int] = []
        self.extraction_passed: bool = True

        # Document Image Extraction Metrics
        self.total_images_detected: int = 0
        self.images_extracted: int = 0
        self.images_rejected: int = 0
        self.rejection_reasons: dict[str, int] = {}
        self.captions_matched: int = 0
        self.images_classified: dict[str, int] = {}
        self.images_used_in_ppt: int = 0
        self.unused_high_relevance: int = 0

        # Slide Content & Density Metrics
        self.total_slides: int = 0
        self.slide_word_counts: list[int] = []
        self.low_content_slides: list[int] = []
        self.average_body_words: float = 0.0
        self.source_sections_represented: float = 0.0
        self.high_importance_chunks_used: float = 0.0
        self.image_matching_success_rate: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "text_extraction": {
                "total_pages": self.total_pages,
                "pages_parsed": self.pages_parsed,
                "text_blocks_count": self.text_blocks_count,
                "headings_detected": self.headings_detected,
                "paragraphs_detected": self.paragraphs_detected,
                "tables_detected": self.tables_detected,
                "captions_detected": self.captions_detected,
                "suspicious_low_pages": self.suspicious_low_pages,
                "zero_extraction_pages": self.zero_extraction_pages,
                "extraction_passed": self.extraction_passed,
            },
            "image_extraction": {
                "total_images_detected": self.total_images_detected,
                "images_extracted": self.images_extracted,
                "images_rejected": self.images_rejected,
                "rejection_reasons": self.rejection_reasons,
                "captions_matched": self.captions_matched,
                "images_classified": self.images_classified,
                "images_used_in_ppt": self.images_used_in_ppt,
                "unused_high_relevance": self.unused_high_relevance,
            },
            "slide_content": {
                "total_slides": self.total_slides,
                "average_body_words": round(self.average_body_words, 1),
                "low_content_slides": self.low_content_slides,
                "source_sections_represented_pct": round(self.source_sections_represented * 100, 1),
                "image_matching_rate_pct": round(self.image_matching_success_rate * 100, 1),
            },
        }


class ExtractionQA:
    """Automated evaluation and quality assurance for document-driven slide generation."""

    @classmethod
    def evaluate_extraction(
        cls,
        extraction_result: Any,
        raw_doc: Any = None,
    ) -> ExtractionQAResult:
        """Run QA audit on DocumentExtractor result."""
        qa = ExtractionQAResult()
        qa.total_pages = extraction_result.metadata.get("page_count", len(extraction_result.text_blocks))
        qa.text_blocks_count = len(extraction_result.text_blocks)
        qa.tables_detected = len(extraction_result.tables)
        images = getattr(extraction_result, "extracted_images", [])
        if not images and hasattr(extraction_result, "assets"):
            images = [
                a.metadata.model_dump() if hasattr(a.metadata, "model_dump") else dict(a.metadata)
                for a in extraction_result.assets
            ]
        qa.images_extracted = len(images)

        page_char_counts: dict[int, int] = {}
        for tb in extraction_result.text_blocks:
            page = tb.get("page", 1)
            content = tb.get("content", "")
            page_char_counts[page] = page_char_counts.get(page, 0) + len(content)

            # Count headings and paragraphs
            lines = content.split("\n")
            for line in lines:
                l_s = line.strip()
                if l_s.startswith("#"):
                    qa.headings_detected += 1
                elif l_s.startswith("*Caption:"):
                    qa.captions_detected += 1
                elif len(l_s) > 40:
                    qa.paragraphs_detected += 1

        parsed_pages = set(page_char_counts.keys())
        qa.pages_parsed = len(parsed_pages)

        # Flag suspicious pages
        for p in range(1, qa.total_pages + 1):
            char_len = page_char_counts.get(p, 0)
            if char_len == 0:
                qa.zero_extraction_pages.append(p)
            elif char_len < 120:
                # Check if page actually had images or text
                qa.suspicious_low_pages.append(p)

        if len(qa.zero_extraction_pages) > max(2, int(qa.total_pages * 0.15)):
            qa.extraction_passed = False

        # Image classification and captions QA
        for img in images:
            img_type = img.get("image_type", "photograph")
            qa.images_classified[img_type] = qa.images_classified.get(img_type, 0) + 1
            if img.get("caption"):
                qa.captions_matched += 1

        return qa

    @classmethod
    def evaluate_slides(
        cls,
        slides: list[SlideSpec] | list[dict[str, Any]],
        extraction_result: Any | None = None,
    ) -> ExtractionQAResult:
        """Run QA audit on generated slides: density, source utilization, visual placement."""
        qa = ExtractionQAResult()
        qa.total_slides = len(slides)

        assigned_images: set[str] = set()
        slide_sections_used: set[str] = set()
        total_words = 0

        for s_idx, slide in enumerate(slides):
            if isinstance(slide, SlideSpec):
                headline = slide.headline or ""
                bullets = slide.bullets or []
                img_id = slide.image_artifact_id
                has_visual = bool(img_id or slide.chart_spec or slide.table_spec or slide.diagram_spec)
                section = slide.section or ""
                layout_hint = slide.layout_hint or ""
            else:
                headline = slide.get("headline", "")
                bullets = normalize_bullet_items(slide.get("bullets"))
                img_id = slide.get("imageArtifactId") or slide.get("image_artifact_id")
                has_visual = bool(img_id or slide.get("chart") or slide.get("table"))
                section = slide.get("section", "")
                layout_hint = str(slide.get("layoutHint") or "").lower()

            if img_id:
                assigned_images.add(str(img_id))
            if section:
                slide_sections_used.add(section.lower())

            # Measure word count
            body_text = " ".join(bullets)
            words = [w for w in re.findall(r"\w+", body_text)]
            word_count = len(words)
            total_words += word_count
            qa.slide_word_counts.append(word_count)

            # Check underfilled slides (LOW_CONTENT_SLIDE)
            # Exclude slide 0 (cover) and section dividers
            is_cover_or_divider = (s_idx == 0 or "divider" in layout_hint or "section" in layout_hint)
            if not is_cover_or_divider:
                if word_count < 22 and not has_visual:
                    qa.low_content_slides.append(s_idx + 1)
                    logger.warning("LOW_CONTENT_SLIDE detected at Slide %s (words=%s, no visual)", s_idx + 1, word_count)

        if qa.total_slides > 0:
            qa.average_body_words = total_words / qa.total_slides

        qa.images_used_in_ppt = len(assigned_images)
        if extraction_result and getattr(extraction_result, "extracted_images", None):
            total_extracted = len(extraction_result.extracted_images)
            qa.images_extracted = total_extracted
            qa.unused_high_relevance = max(0, total_extracted - len(assigned_images))

        if extraction_result and getattr(extraction_result, "sections", None):
            total_sections = len(extraction_result.sections)
            if total_sections > 0:
                matched_sec = sum(1 for s in extraction_result.sections if any(s["title"].lower() in ss or ss in s["title"].lower() for ss in slide_sections_used))
                qa.source_sections_represented = matched_sec / total_sections

        # Visual pacing: % of slides having visuals
        if qa.total_slides > 1:
            visual_slides_count = sum(
                1 for s in slides if (isinstance(s, SlideSpec) and (s.image_artifact_id or s.chart_spec or s.table_spec))
                or (isinstance(s, dict) and (s.get("imageArtifactId") or s.get("chart") or s.get("table")))
            )
            qa.image_matching_success_rate = visual_slides_count / (qa.total_slides - 1)

        return qa
