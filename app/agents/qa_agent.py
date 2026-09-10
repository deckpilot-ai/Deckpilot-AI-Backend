"""Multi-tier Presentation QA Agent (Content, Design, Data, Geometry, Technical)."""

import logging
from typing import Any

from app.agents.title_intelligence import TitleIntelligence
from app.schemas.generation_state import (
    DesignSystem,
    QAReport,
    SlideSpec,
    ValidationCategory,
    ValidationIssue,
    ValidationSeverity,
)
from app.tools.pptx_validator import PPTXValidator
from app.tools.text_geometry import TextGeometry

logger = logging.getLogger(__name__)


class PresentationQAAgent:
    """Performs multi-dimensional automated QA on presentation specs and rendered binaries."""

    @classmethod
    def evaluate_presentation(
        cls,
        slide_specs: list[SlideSpec],
        design_system: DesignSystem,
        pptx_bytes: bytes | None = None,
        source_images: dict[str, bytes] | None = None,
        available_assets: list[Any] | None = None,
    ) -> QAReport:
        issues: list[ValidationIssue] = []
        checks = [
            "content_narrative_flow",
            "title_intelligence_check",
            "text_budget_and_overflow",
            "visual_rhythm_and_diversity",
            "visual_asset_presence_and_pacing",
            "chart_data_provenance",
            "pptx_openxml_integrity",
            "visual_shapes_and_page_pills",
        ]

        # 1. Title QA
        titles = [s.headline or s.key_message for s in slide_specs]
        title_issues = TitleIntelligence.validate_titles(titles)
        issues.extend(title_issues)

        # Slide 1 Cover Title & Subtitle Check
        if slide_specs:
            s1 = slide_specs[0]
            s1_title = (s1.headline or s1.key_message or "").strip()
            word_count = len(s1_title.split())
            if word_count > 6 or len(s1_title) > 48:
                if not s1.takeaway and not getattr(s1, "subtitle", None) and ":" not in s1_title:
                    issues.append(ValidationIssue(
                        severity=ValidationSeverity.HIGH,
                        category=ValidationCategory.CONTENT,
                        slide_number=1,
                        slide_id=s1.slide_id,
                        message="Slide 1 main title is too long for an executive cover; lacks distinct short title and subtitle separation",
                        suggested_fix="Shorten main title to 3-4 words and place remainder into subtitle below",
                    ))

        # 2. Content & Text Budget QA
        for idx, slide in enumerate(slide_specs):
            bullets = slide.bullets or []
            if len(bullets) > 6:
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.MEDIUM,
                    category=ValidationCategory.CONTENT,
                    slide_number=idx + 1,
                    slide_id=slide.slide_id,
                    message=f"Slide has {len(bullets)} bullets; exceeds maximum recommended 6 for scannability",
                    suggested_fix="Consolidate bullet points into 3-4 high-impact takeaways",
                ))

            for b in bullets:
                if len(str(b).split()) > 25:
                    issues.append(ValidationIssue(
                        severity=ValidationSeverity.LOW,
                        category=ValidationCategory.CONTENT,
                        slide_number=idx + 1,
                        slide_id=slide.slide_id,
                        message="Bullet point exceeds 25 words",
                        suggested_fix="Tighten bullet copy to maintain executive scannability",
                    ))

            # 3. Chart & Data Provenance QA
            if slide.chart_spec:
                c = slide.chart_spec
                if not c.categories or not c.series:
                    issues.append(ValidationIssue(
                        severity=ValidationSeverity.HIGH,
                        category=ValidationCategory.DATA,
                        slide_number=idx + 1,
                        slide_id=slide.slide_id,
                        message="Chart specified without categories or series values",
                        suggested_fix="Provide valid numerical categories and series data",
                    ))

        # 4. Visual Asset Presence, Pacing & De-duplication QA
        asset_keys = list(source_images.keys()) if source_images else ([a.asset_id for a in available_assets] if available_assets else [])
        if asset_keys:
            slides_with_img = [s for s in slide_specs if s.image_artifact_id]
            if not slides_with_img:
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.HIGH,
                    category=ValidationCategory.DESIGN,
                    slide_number=1,
                    slide_id=slide_specs[0].slide_id if slide_specs else "s01",
                    message="Visual assets exist in the project but no images were assigned to presentation slides",
                    suggested_fix="Assign available documentary visual assets across content slides",
                ))
            elif len(slide_specs) >= 6 and len(slides_with_img) < min(len(asset_keys), max(2, len(slide_specs) // 4)):
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.MEDIUM,
                    category=ValidationCategory.DESIGN,
                    slide_number=1,
                    slide_id=slide_specs[0].slide_id if slide_specs else "s01",
                    message=f"Image pacing is sparse; only {len(slides_with_img)} slides have images across {len(slide_specs)} slides",
                    suggested_fix="Distribute visual assets evenly every 2-3 slides across the deck",
                ))

            # Check duplicate asset assignments when unused assets are available
            used_ids = [s.image_artifact_id for s in slides_with_img if s.image_artifact_id]
            unused_ids = [k for k in asset_keys if k not in used_ids]
            counts = {}
            for uid in used_ids:
                counts[uid] = counts.get(uid, 0) + 1
            duplicates = [uid for uid, cnt in counts.items() if cnt > 1]
            if duplicates and unused_ids:
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.MEDIUM,
                    category=ValidationCategory.DESIGN,
                    slide_number=1,
                    slide_id=slide_specs[0].slide_id if slide_specs else "s01",
                    message=f"Duplicate visual assets assigned while {len(unused_ids)} unused assets exist",
                    suggested_fix="Distribute unique visual figures without repeats across candidate slides",
                ))

            # 4b. Semantic Image Relevance Check
            from app.services.image_matcher import ImageMatcher
            for idx, slide in enumerate(slide_specs):
                if slide.image_artifact_id and idx > 0:
                    caption = slide.image_caption or ""
                    slide_text = f"{slide.headline} {slide.objective} {slide.takeaway} {' '.join(slide.bullets or [])}"
                    score = ImageMatcher.calculate_relevance(slide_text, caption)
                    if score < 1.5:
                        issues.append(ValidationIssue(
                            severity=ValidationSeverity.HIGH,
                            category=ValidationCategory.DESIGN,
                            slide_number=idx + 1,
                            slide_id=slide.slide_id,
                            message=f"Semantic image mismatch on Slide {idx + 1}: Image '{slide.image_artifact_id}' ('{caption[:45]}...') has low semantic relevance (score={score:.1f}) to slide topic '{slide.headline[:45]}'",
                            suggested_fix="Re-match image using semantic keyword scoring or switch away from image_focus layout",
                        ))

        # 4c. Repetitive Boilerplate Structure Check across deck
        lead_phrases: dict[str, list[int]] = {}
        for idx, slide in enumerate(slide_specs):
            for b in (slide.bullets or []):
                cleaned = str(b).strip()
                if ":" in cleaned:
                    lead = cleaned.split(":", 1)[0].strip().lower()
                    if len(lead) >= 6:
                        lead_phrases.setdefault(lead, []).append(idx + 1)

        repetitive_leads = {k: v for k, v in lead_phrases.items() if len(set(v)) >= 3}
        if repetitive_leads:
            threshold = max(3, len(slide_specs) // 4)
            for lead, affected_slides in repetitive_leads.items():
                distinct_slides = sorted(list(set(affected_slides)))
                if len(distinct_slides) >= threshold:
                    issues.append(ValidationIssue(
                        severity=ValidationSeverity.HIGH,
                        category=ValidationCategory.CONTENT,
                        slide_number=distinct_slides[0],
                        slide_id=slide_specs[distinct_slides[0] - 1].slide_id if distinct_slides[0] - 1 < len(slide_specs) else "s01",
                        message=f"Repetitive boilerplate text structure detected: Lead phrase '{lead.title()}:' repeated across {len(distinct_slides)} slides {distinct_slides[:5]}",
                        suggested_fix="Synthesize domain-specific, diverse structural bullets tailored to each slide's topic",
                    ))

        # 4d. Typographic Hierarchy Check
        for idx, slide in enumerate(slide_specs):
            bullets = slide.bullets or []
            if bullets and len(bullets) >= 2:
                has_hierarchy = any((":" in str(b)) or ("**" in str(b)) for b in bullets)
                if not has_hierarchy and slide.layout_family in (LayoutFamily.IMAGE_FOCUS, LayoutFamily.TWO_COLUMN, LayoutFamily.CARD_GRID):
                    issues.append(ValidationIssue(
                        severity=ValidationSeverity.MEDIUM,
                        category=ValidationCategory.DESIGN,
                        slide_number=idx + 1,
                        slide_id=slide.slide_id,
                        message=f"Slide {idx + 1} lacks typographic hierarchy: uniform text without bold lead tags or structural segmentation",
                        suggested_fix="Structure bullet points with distinct bold lead tags (e.g. 'Driver: Detail')",
                    ))

        # 5. Visual Rhythm QA
        layouts = [s.layout_family for s in slide_specs]
        consecutive_same = 1
        for i in range(1, len(layouts)):
            if layouts[i] == layouts[i-1]:
                consecutive_same += 1
                if consecutive_same >= 3:
                    issues.append(ValidationIssue(
                        severity=ValidationSeverity.LOW,
                        category=ValidationCategory.DESIGN,
                        slide_number=i + 1,
                        slide_id=slide_specs[i].slide_id,
                        message=f"Layout '{layouts[i].value}' used 3 times consecutively",
                        suggested_fix="Introduce layout variety (e.g. switch to cards, timeline, or chart)",
                    ))
            else:
                consecutive_same = 1

        # 6. Technical PPTX Stream & Shape QA
        if pptx_bytes:
            stream_report = PPTXValidator.validate_pptx_stream(pptx_bytes, len(slide_specs))
            issues.extend(stream_report.issues)

            # Inspect rendered shapes directly
            try:
                import io
                import pptx
                from pptx.enum.shapes import MSO_SHAPE_TYPE
                prs = pptx.Presentation(io.BytesIO(pptx_bytes))
                total_pics = sum(1 for s in prs.slides for sh in s.shapes if sh.shape_type == MSO_SHAPE_TYPE.PICTURE)

                if asset_keys and total_pics == 0:
                    issues.append(ValidationIssue(
                        severity=ValidationSeverity.HIGH,
                        category=ValidationCategory.DESIGN,
                        slide_number=0,
                        message="Rendered presentation contains zero embedded pictures despite available visual assets",
                        suggested_fix="Re-render with image layout routing and valid picture coordinates",
                    ))

                # Check page pills on all slides
                for idx, slide in enumerate(prs.slides):
                    has_pill = any(hasattr(sh, "text") and sh.text.strip() == str(idx + 1) for sh in slide.shapes)
                    if not has_pill:
                        issues.append(ValidationIssue(
                            severity=ValidationSeverity.MEDIUM,
                            category=ValidationCategory.DESIGN,
                            slide_number=idx + 1,
                            message=f"Slide {idx + 1} is missing persistent page number pill",
                            suggested_fix="Ensure persistent page number pill is rendered on top z-order layer",
                        ))

                # Check Slide 1 signature decorative circles (layered OVAL shapes)
                if len(prs.slides) > 0:
                    s0 = prs.slides[0]
                    oval_count = 0
                    for sh in s0.shapes:
                        if sh.shape_type == MSO_SHAPE_TYPE.AUTO_SHAPE:
                            try:
                                if sh.auto_shape_type == pptx.enum.shapes.MSO_SHAPE.OVAL:
                                    oval_count += 1
                            except Exception:
                                pass
                    if oval_count < 2:
                        issues.append(ValidationIssue(
                            severity=ValidationSeverity.HIGH,
                            category=ValidationCategory.DESIGN,
                            slide_number=1,
                            slide_id=slide_specs[0].slide_id if slide_specs else "s01",
                            message=f"Slide 1 missing signature decorative circular geometry (found {oval_count} OVAL shapes, expected >= 2 layered accent circles from benchmark design)",
                            suggested_fix="Ensure Slide 1 renders layered corner and background OVAL accent shapes matching benchmark PPTX",
                        ))
            except Exception as e:
                logger.warning("Shape inspection warning: %s", e)

        # Compute overall status & score
        has_critical = any(i.severity == ValidationSeverity.CRITICAL for i in issues)
        has_high = any(i.severity == ValidationSeverity.HIGH for i in issues)

        if has_critical:
            status = "failed"
        elif has_high:
            status = "issues_detected"
        else:
            status = "passed"

        score = max(0.0, round(100.0 - (len(issues) * 6.5), 1))

        return QAReport(
            status=status,
            overall_quality_score=score,
            issues=issues,
            checks_performed=checks,
            slide_count=len(slide_specs),
            repair_triggered=(status in ("issues_detected", "failed")),
        )
