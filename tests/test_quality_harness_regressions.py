"""Unit and permanent regression test suite for Quality Harness components."""

from __future__ import annotations

import pytest

from app.agents.presentation_level_qa import PresentationLevelQA
from app.schemas.generation_state import (
    AssetMetadata,
    DesignSystem,
    LayoutFamily,
    QAReport,
    SlideSpec,
    ValidationCategory,
    ValidationIssue,
    ValidationSeverity,
)
from app.services.collision_engine import BoundingBox, CollisionDetectionEngine
from app.services.quality_scorer import PresentationQualityScorer
from app.services.text_measurement import TextMeasurementService


def test_text_measurement_bounds_and_overflow():
    """Verify that TextMeasurementService detects container overflow and wraps accurately."""
    short_text = "Executive Summary: Q3 Milestones and Market Performance."
    w, h, lines, line_list = TextMeasurementService.measure_text_bounds(
        text=short_text,
        font_name="Segoe UI",
        font_size_pt=14,
        max_width_in=4.0,
    )
    assert lines >= 1
    assert h > 0.2
    assert w <= 4.0

    # Test overflow detection: 80-word paragraph packed into a 2x1 inch box
    long_text = (
        "In the second phase of international expansion across EMEA and APAC corridors, "
        "enterprise sales cycles compressed by 22% due to localized partner onboarding, "
        "automated compliance checks, multi-currency settlement capabilities, and dedicated "
        "solutions engineering pods stationed in London and Singapore."
    )
    res = TextMeasurementService.fit_text_into_container(
        text=long_text,
        container_w=2.0,
        container_h=0.8,
        min_font_pt=11,
        max_font_pt=14,
    )
    assert not res.fits
    assert res.overflow_height_in > 0.1

    # Validate slide elements emission
    elements = [{
        "name": "card_1_body",
        "text": long_text,
        "w": 2.0,
        "h": 0.8,
        "min_font_pt": 11,
        "max_font_pt": 14,
    }]
    issues = TextMeasurementService.validate_slide_text_elements(1, elements)
    assert len(issues) >= 1
    assert issues[0].checkpoint_id == "QA-038"
    assert issues[0].severity in (ValidationSeverity.CRITICAL, ValidationSeverity.HIGH)


def test_collision_detection_engine_overlaps():
    """Verify that CollisionDetectionEngine catches shape, text, image, and footer collisions."""
    # Box A and Box B collide directly
    box_a = BoundingBox(id="c1", name="Card 1", kind="card", x=1.0, y=2.0, w=4.0, h=3.0)
    box_b = BoundingBox(id="c2", name="Card 2", kind="card", x=3.5, y=2.0, w=4.0, h=3.0)  # Overlaps Box A from x=3.5 to 5.0
    issues = CollisionDetectionEngine.detect_collisions(1, [box_a, box_b])
    assert len(issues) >= 1
    assert any(i.checkpoint_id == "QA-040" for i in issues)

    # Box inside parent card (allowed containment) should NOT flag collision
    card = BoundingBox(id="parent_card", name="Card Container", kind="card", x=1.0, y=1.5, w=3.5, h=4.0)
    text_inside = BoundingBox(id="child_text", name="Card Text", kind="text", x=1.2, y=1.8, w=3.0, h=2.5, parent_id="parent_card")
    no_collision_issues = CollisionDetectionEngine.detect_collisions(1, [card, text_inside])
    assert len(no_collision_issues) == 0

    # Text colliding with image
    text_box = BoundingBox(id="t1", name="Body Text", kind="text", x=4.0, y=2.0, w=4.0, h=2.0)
    image_box = BoundingBox(id="img1", name="Product Photo", kind="image", x=6.0, y=2.0, w=4.0, h=3.0)
    text_img_issues = CollisionDetectionEngine.detect_collisions(1, [text_box, image_box])
    assert any(i.checkpoint_id == "QA-041" for i in text_img_issues)

    # Footer margin collision
    footer_intruder = BoundingBox(id="f1", name="Low Element", kind="card", x=2.0, y=5.0, w=4.0, h=2.3)  # bottom at 7.3 > 7.15
    footer_issues = CollisionDetectionEngine.detect_collisions(1, [footer_intruder])
    assert any(i.checkpoint_id == "QA-042" for i in footer_issues)


def test_card_alignment_validation():
    """Verify that validate_card_alignment flags uneven card top drift and inconsistent heights."""
    # 3 cards with top alignment drift
    card1 = BoundingBox(id="c1", name="Card 1", kind="card", x=1.0, y=2.0, w=3.0, h=3.0)
    card2 = BoundingBox(id="c2", name="Card 2", kind="card", x=4.5, y=2.25, w=3.0, h=3.0)  # 0.25" lower
    card3 = BoundingBox(id="c3", name="Card 3", kind="card", x=8.0, y=2.0, w=3.0, h=3.0)

    issues = CollisionDetectionEngine.validate_card_alignment(1, [card1, card2, card3])
    assert len(issues) >= 1
    assert any("top alignment drift" in i.message for i in issues)

    # Uneven gutters
    card_g1 = BoundingBox(id="c1", name="Card 1", kind="card", x=1.0, y=2.0, w=3.0, h=3.0)
    card_g2 = BoundingBox(id="c2", name="Card 2", kind="card", x=4.3, y=2.0, w=3.0, h=3.0)  # gutter = 0.3"
    card_g3 = BoundingBox(id="c3", name="Card 3", kind="card", x=8.3, y=2.0, w=3.0, h=3.0)  # gutter = 1.0"
    gutter_issues = CollisionDetectionEngine.validate_card_alignment(1, [card_g1, card_g2, card_g3])
    assert any("Uneven gutters" in i.message for i in gutter_issues)


def test_presentation_level_qa_repetition_and_visuals():
    """Verify that PresentationLevelQA catches consecutive layout repetition and missing visuals."""
    # 3 consecutive identical layouts
    slides = [
        SlideSpec(slide_number=1, layout_family=LayoutFamily.THREE_COLUMN, headline="Slide 1"),
        SlideSpec(slide_number=2, layout_family=LayoutFamily.THREE_COLUMN, headline="Slide 2"),
        SlideSpec(slide_number=3, layout_family=LayoutFamily.THREE_COLUMN, headline="Slide 3"),
        SlideSpec(slide_number=4, layout_family=LayoutFamily.TWO_COLUMN, headline="Slide 4"),
    ]
    issues = PresentationLevelQA.evaluate_deck(slides, DesignSystem())
    assert any(i.checkpoint_id == "QA-077" for i in issues)

    # Missing visuals when assets are available
    assets = [AssetMetadata(asset_id="img_01", caption="Sample chart", width=800, height=600)]
    slides_no_images = [
        SlideSpec(slide_number=i, layout_family=LayoutFamily.TWO_COLUMN, headline=f"Slide {i}")
        for i in range(1, 6)
    ]
    visual_issues = PresentationLevelQA.evaluate_deck(slides_no_images, DesignSystem(), available_assets=assets)
    assert any(i.checkpoint_id == "QA-073" for i in visual_issues)


def test_presentation_quality_scorer_14_gates():
    """Verify that PresentationQualityScorer computes 14-Gate weighted scores and strictly enforces 0 CRITICAL defects."""
    slides = [SlideSpec(slide_number=1, headline="Slide 1", layout_family=LayoutFamily.HERO)]

    # Clean report with no issues
    clean_qa = QAReport(status="passed", overall_quality_score=98.0, issues=[], checks_performed=[], slide_count=1)
    clean_scorecard = PresentationQualityScorer.score_presentation(slides, clean_qa)
    assert clean_scorecard.is_presentation_ready
    assert clean_scorecard.overall_quality_score >= 95.0
    assert clean_scorecard.status == "PASSED"

    # Report with a single CRITICAL defect (e.g. text collision or severe overflow)
    crit_issue = ValidationIssue(
        checkpoint_id="QA-038",
        severity=ValidationSeverity.CRITICAL,
        category=ValidationCategory.GEOMETRY,
        slide_number=1,
        message="Text overflows container by 0.65 inches",
    )
    crit_qa = QAReport(status="failed", overall_quality_score=70.0, issues=[crit_issue], checks_performed=[], slide_count=1)
    crit_scorecard = PresentationQualityScorer.score_presentation(slides, crit_qa)

    # Must be marked NOT presentation-ready and status FAILED
    assert not crit_scorecard.is_presentation_ready
    assert crit_scorecard.status == "FAILED"
    assert crit_scorecard.critical_issues_count == 1


def test_renderer_page_pill_editorial_archetype_safety():
    """Verify that PPTXRenderer does not crash with UnboundLocalError on pill_bg for editorial/archetype layouts."""
    from app.services.renderer import PPTXRenderer

    # Slide with an editorial archetype
    slide_spec = SlideSpec(
        slide_number=1,
        headline="Editorial Analysis of Governance",
        layout_hint="L07",
        bullets=["First major principle of governance.", "Second supporting insight."],
    )
    design = DesignSystem()

    # Must render without UnboundLocalError: pill_bg
    pptx_bytes = PPTXRenderer.render_presentation(
        slide_specs=[slide_spec],
        design_system=design,
        deck_title="Test Governance",
    )
    assert len(pptx_bytes) > 5000


def test_health_tracker_circuit_open_duration_not_read_only():
    """Verify that _ModelHealth allows setting circuit_open_duration on account outage."""
    from app.services.health_tracker import HealthTracker

    tracker = HealthTracker()
    # Trigger account outage which modifies circuit_open_duration
    tracker.record_account_outage("openai", 429, "You have no credits remaining", cooldown_seconds=1800.0)
    score = tracker.composite_score("openai", "gpt-4o", 50)
    assert score >= 0.0


def test_repair_agent_and_orchestrator_symbols():
    """Verify that RepairAgent and orchestrator have LayoutFamily and json defined."""
    from app.agents.repair_agent import RepairAgent, json
    from app.services.orchestrator import LayoutFamily, JobOrchestrator

    assert json is not None
    assert LayoutFamily.HERO is not None
    assert hasattr(JobOrchestrator, "run_job")


def test_pptx_validator_shape_classification_and_containment():
    """Verify that cards containing badges and text do not trigger false positive collision."""
    from app.services.collision_engine import BoundingBox, CollisionDetectionEngine

    # def-top-card containing concept-pill and content text
    card = BoundingBox(id="1", name="def-top-card", kind="card", x=0.6, y=2.05, w=6.2, h=2.3)
    pill = BoundingBox(id="2", name="concept-pill", kind="badge", x=0.85, y=2.25, w=2.2, h=0.34)
    pill_txt = BoundingBox(id="3", name="pill-txt", kind="text", x=0.85, y=2.27, w=2.2, h=0.28)
    def_txt = BoundingBox(id="4", name="content-text", kind="text", x=0.85, y=2.7, w=5.7, h=1.45)

    issues = CollisionDetectionEngine.detect_collisions(
        slide_number=1,
        boxes=[card, pill, pill_txt, def_txt],
        canvas_w=13.333,
        canvas_h=7.500,
    )
    # The elements are legitimately nested within the card container
    critical_issues = [i for i in issues if i.severity == ValidationSeverity.CRITICAL]
    assert len(critical_issues) == 0


def test_presentation_quality_scorer_categories():
    """Verify quality scorer handles TYPOGRAPHY and IMAGES categories without AttributeError."""
    from app.schemas.generation_state import ValidationCategory, ValidationIssue, ValidationSeverity, QAReport
    from app.services.quality_scorer import PresentationQualityScorer

    issues = [
        ValidationIssue(
            checkpoint_id="QA-025",
            severity=ValidationSeverity.MEDIUM,
            category=ValidationCategory.TYPOGRAPHY,
            slide_number=1,
            message="Slight typography scaling",
        ),
        ValidationIssue(
            checkpoint_id="QA-061",
            severity=ValidationSeverity.LOW,
            category=ValidationCategory.IMAGES,
            slide_number=2,
            message="Image aspect ratio slightly varied",
        ),
    ]
    report = QAReport(
        status="passed",
        overall_quality_score=96.0,
        issues=issues,
        checks_performed=["QA-025", "QA-061"],
        slide_count=5,
    )
    slides = [SlideSpec(slide_number=i, headline=f"Slide {i}", layout_family=LayoutFamily.HERO) for i in range(1, 6)]
    scorecard = PresentationQualityScorer.score_presentation(slides, report)
    assert scorecard.overall_quality_score >= 90.0
    assert scorecard.gate_results["QG3_typography"].score < 100.0
    assert scorecard.gate_results["QG7_images"].score < 100.0
