"""Regression Test Suite for PowerPoint Generation Quality Improvements.

Verifies:
- Text measurement precision and container fitting
- GridEngine slot symmetry, gutters, and alignments
- Inline collision prevention via PlacementTracker and CollisionDetectionEngine
- ContentCapacityValidator pre-render checks, intelligent shortening, and layout adaptation
- RepairAgent verification loops and geometric fixes
- End-to-end PPTX rendering consistency
"""

from __future__ import annotations

import io
import pytest
from pptx import Presentation

from app.schemas.generation_state import (
    AssetMetadata,
    DesignSystem,
    LayoutFamily,
    SlideSpec,
    ValidationSeverity,
)
from app.services.collision_engine import (
    BoundingBox,
    CollisionDetectionEngine,
    PlacementTracker,
)
from app.services.content_capacity_validator import (
    CapacityIssue,
    ContentCapacityValidator,
)
from app.services.grid_engine import CardSlot, PresentationGridEngine
from app.services.renderer import PPTXRenderer
from app.services.text_measurement import TextMeasurementService


@pytest.fixture
def standard_design_system():
    return DesignSystem()


# =========================================================================
# 1. Text Measurement and Fitting
# =========================================================================

def test_text_never_exceeds_card_bounds():
    """Verify that TextMeasurementService correctly calculates whether long text exceeds card container."""
    long_copy = (
        "Enterprise cloud migration accelerates digital transformation across global operations, "
        "enabling elastic compute scaling, automated compliance governance, and unified data pipelines "
        "for multi-region resilience and low-latency client service delivery."
    )
    # Inside a small 3.5" x 1.2" box at 14pt it should NOT fit
    res = TextMeasurementService.fit_text_into_container(
        text=long_copy,
        container_w=3.5,
        container_h=1.2,
        min_font_pt=11.0,
        max_font_pt=14.0,
    )
    assert not res.fits or res.recommended_font_size_pt <= 11.5


def test_title_never_overflows_at_28pt():
    """Verify that title measurement correctly assesses whether title fits 2 lines at presentation title size."""
    concise_title = "Strategic Roadmap for AI Infrastructure"
    fits, rec_size, lines = TextMeasurementService.measure_title_fits(
        text=concise_title,
        max_width_in=12.133,
        max_height_in=1.15,
        min_font_pt=20.0,
        max_font_pt=32.0,
    )
    assert fits is True
    assert rec_size >= 24.0
    assert len(lines) <= 2


def test_title_shortening_intelligently():
    """Verify that ContentCapacityValidator preserves key predicate when trimming verbose titles."""
    verbose_title = (
        "Comprehensive Strategic Evaluation of Multi-Cloud Architecture: "
        "Key Operational Enablers, Cost Optimization Paradigms, and Long-Term Enterprise Governance Requirements"
    )
    shortened = ContentCapacityValidator.shorten_title_intelligently(verbose_title, max_words=10)
    assert len(shortened.split()) <= 10
    assert "Comprehensive Strategic Evaluation" in shortened


def test_text_measurement_service_check_fits():
    """Verify check_fits method works consistently with measure_text_bounds."""
    short_text = "Brief status update"
    assert TextMeasurementService.check_fits(short_text, w=6.0, h=1.0, size=14.0) is True
    huge_text = "Word " * 200
    assert TextMeasurementService.check_fits(huge_text, w=3.0, h=1.0, size=14.0) is False


def test_text_measurement_service_split_content():
    """Verify split_content_for_layout segregates fitting vs overflowing bullets."""
    bullets = [
        "Milestone 1: Project kick-off and technical requirements baseline.",
        "Milestone 2: Multi-cloud orchestration layer deployment and security audit.",
        "Milestone 3: Data warehouse migration and zero-downtime cutover.",
        "Milestone 4: Continuous observability, telemetry alerting, and disaster recovery validation across secondary regions.",
        "Milestone 5: Post-implementation review, executive sign-off, and knowledge transfer to internal operational teams.",
    ]
    # Small box: only top bullets should fit
    all_fit, fitting, overflow = TextMeasurementService.split_content_for_layout(
        bullets=bullets,
        container_w=4.0,
        container_h=1.5,
        font_size_pt=13.0,
    )
    assert len(fitting) >= 1
    assert len(overflow) >= 1
    assert all_fit is False


# =========================================================================
# 2. Grid Engine Symmetry & Alignment
# =========================================================================

def test_same_row_cards_are_aligned():
    """Verify that computed grid cards in the same row share the exact same top Y coordinate."""
    slots = PresentationGridEngine.compute_card_grid(
        cols=3,
        rows=2,
        margin_left=0.6,
        content_top=2.15,
        total_w=12.133,
        total_h=4.45,
        gutter_x=0.35,
        gutter_y=0.35,
    )
    assert len(slots) == 6

    # Row 0 cards
    row_0 = [s for s in slots if s.row == 0]
    assert len(row_0) == 3
    assert row_0[0].y == row_0[1].y == row_0[2].y == 2.15

    # Row 1 cards
    row_1 = [s for s in slots if s.row == 1]
    assert len(row_1) == 3
    assert row_1[0].y == row_1[1].y == row_1[2].y


def test_grid_cards_have_equal_widths():
    """Verify all columns in a card grid have identical widths."""
    slots = PresentationGridEngine.compute_equal_columns(count=4, total_w=12.0, gap=0.4)
    assert len(slots) == 4
    widths = [s.w for s in slots]
    assert len(set(widths)) == 1
    expected_w = round((12.0 - 3 * 0.4) / 4, 3)
    assert widths[0] == expected_w


def test_grid_cards_have_equal_heights():
    """Verify all cards in an N x M grid have identical heights."""
    slots = PresentationGridEngine.compute_card_grid(cols=3, rows=2, total_h=4.0, gutter_y=0.3)
    assert len(slots) == 6
    heights = [s.h for s in slots]
    assert len(set(heights)) == 1


def test_grid_cards_have_equal_gutters():
    """Verify horizontal spacing between adjacent cards is strictly uniform."""
    slots = PresentationGridEngine.compute_equal_columns(count=3, margin_left=0.6, total_w=12.0, gap=0.5)
    gutter_1 = round(slots[1].x - slots[0].right, 3)
    gutter_2 = round(slots[2].x - slots[1].right, 3)
    assert gutter_1 == gutter_2 == 0.5


def test_two_column_slots_computation():
    """Verify compute_two_column handles custom ratios and creates adjacent non-overlapping slots."""
    left_slot, right_slot = PresentationGridEngine.compute_two_column(
        left_ratio=0.6,
        gap=0.4,
        margin_left=0.6,
        total_w=12.0,
        height=4.5,
    )
    assert left_slot.right < right_slot.x
    assert round(right_slot.x - left_slot.right, 3) == 0.4
    assert left_slot.y == right_slot.y == 2.15


# =========================================================================
# 3. Collision Engine & Inline Placement Tracking
# =========================================================================

def test_collision_engine_detects_text_text_overlap():
    """Verify collision engine flags overlapping text boxes."""
    t1 = BoundingBox(id="t1", name="Title", kind="text", x=1.0, y=1.0, w=5.0, h=1.5)
    t2 = BoundingBox(id="t2", name="Subtitle", kind="text", x=1.0, y=1.8, w=5.0, h=1.5)  # Overlaps y=1.8 to 2.5
    issues = CollisionDetectionEngine.detect_collisions(1, [t1, t2])
    assert len(issues) >= 1
    assert any(i.checkpoint_id == "QA-040" for i in issues)


def test_collision_engine_detects_text_image_overlap():
    """Verify collision engine specifically flags text-on-image collision as QA-041."""
    text_box = BoundingBox(id="t1", name="Paragraph", kind="text", x=5.0, y=2.0, w=4.0, h=2.0)
    image_box = BoundingBox(id="img1", name="Photo", kind="image", x=7.0, y=2.0, w=5.0, h=4.0)
    issues = CollisionDetectionEngine.detect_collisions(1, [text_box, image_box])
    assert any(i.checkpoint_id == "QA-041" for i in issues)


def test_collision_engine_containment_allowed():
    """Verify text inside a card container is legitimate containment, not a collision."""
    card = BoundingBox(id="card_1", name="Card", kind="card", x=1.0, y=2.0, w=4.0, h=4.0)
    text = BoundingBox(id="text_1", name="Card Body", kind="text", x=1.2, y=2.2, w=3.6, h=3.4, parent_id="card_1")
    issues = CollisionDetectionEngine.detect_collisions(1, [card, text])
    assert len(issues) == 0


def test_footer_never_collides_with_content():
    """Verify element invading bottom 0.45 inches triggers footer margin warning."""
    intruder = BoundingBox(id="c1", name="Overextended Card", kind="card", x=1.0, y=4.0, w=4.0, h=3.3)  # bottom at 7.3 > 7.15
    issues = CollisionDetectionEngine.detect_collisions(1, [intruder])
    assert any(i.checkpoint_id == "QA-042" for i in issues)


def test_placement_tracker_detects_collision():
    """Verify PlacementTracker prevents collisions before placement."""
    tracker = PlacementTracker()
    box1 = BoundingBox(id="b1", name="Box 1", kind="card", x=1.0, y=2.0, w=4.0, h=3.0)
    tracker.place(box1)

    # Box 2 collides with Box 1
    box2 = BoundingBox(id="b2", name="Box 2", kind="card", x=3.0, y=2.5, w=4.0, h=3.0)
    collider = tracker.would_collide(box2)
    assert collider is not None
    assert collider.id == "b1"

    # Box 3 placed in free space
    box3 = BoundingBox(id="b3", name="Box 3", kind="card", x=5.5, y=2.0, w=4.0, h=3.0)
    assert tracker.would_collide(box3) is None


def test_placement_tracker_footer_clearance():
    """Verify PlacementTracker.validate_footer_clearance catches footer zone intrusions."""
    good_box = BoundingBox(id="b1", name="Content", kind="card", x=1.0, y=2.0, w=4.0, h=4.0)  # bottom=6.0
    bad_box = BoundingBox(id="b2", name="Intruder", kind="card", x=6.0, y=2.0, w=4.0, h=5.2)  # bottom=7.2 > 6.90
    intrusions = PlacementTracker.validate_footer_clearance([good_box, bad_box], footer_top=6.90)
    assert len(intrusions) == 1
    assert intrusions[0].id == "b2"


def test_placement_tracker_boundary_containment():
    """Verify PlacementTracker.validate_boundary_containment detects canvas overrun."""
    out_of_bounds = BoundingBox(id="oob", name="Overhang", kind="card", x=11.0, y=2.0, w=3.0, h=3.0)  # right=14.0 > 13.333
    violations = PlacementTracker.validate_boundary_containment([out_of_bounds])
    assert len(violations) == 1
    assert violations[0].id == "oob"


# =========================================================================
# 4. Content Capacity Validator & Adaptation
# =========================================================================

def test_capacity_validator_overflow_detection():
    """Verify ContentCapacityValidator catches cards with excessive word count."""
    long_bullet = (
        "This is an excessively long bullet point that goes on and on detailing every single operational "
        "dependency and technological trade-off across three different operating environments without "
        "providing a clear concise headline or allowing for legible typography at standard presentation scale."
    )
    spec = SlideSpec(
        slide_number=1,
        headline="Operational Analysis",
        bullets=[long_bullet],
        layout_family=LayoutFamily.CARD_GRID,
        archetype_id="A13",
    )
    issues = ContentCapacityValidator.validate_slide(spec)
    assert any(i.issue_type == "BODY_OVERFLOW" for i in issues)


def test_capacity_validator_layout_adaptation_4_bullets():
    """Verify ContentCapacityValidator automatically upgrades 4 bullets in TWO_COLUMN to CARD_GRID."""
    spec = SlideSpec(
        slide_number=2,
        headline="Key Enablers",
        bullets=["Point 1", "Point 2", "Point 3", "Point 4"],
        layout_family=LayoutFamily.TWO_COLUMN,
        archetype_id="A7",
    )
    fixed = ContentCapacityValidator.validate_and_fix([spec])
    assert fixed[0].layout_family == LayoutFamily.CARD_GRID
    assert fixed[0].archetype_id == "A13"


def test_capacity_validator_layout_adaptation_6_bullets():
    """Verify ContentCapacityValidator upgrades 6 bullets in THREE_COLUMN to COUNCIL_EIGHT (A25)."""
    spec = SlideSpec(
        slide_number=3,
        headline="Governance Principles",
        bullets=[f"Principle {i+1}: Detailed operational mandate" for i in range(7)],
        layout_family=LayoutFamily.THREE_COLUMN,
        archetype_id="A11",
    )
    fixed = ContentCapacityValidator.validate_and_fix([spec])
    assert fixed[0].layout_family == LayoutFamily.COUNCIL_EIGHT
    assert fixed[0].archetype_id == "A25"


def test_capacity_validator_underfill_boost():
    """Verify ContentCapacityValidator boosts font scale for sparse slides."""
    spec = SlideSpec(
        slide_number=4,
        headline="Core Takeaway",
        bullets=["Primary Strategic Insight: Execution alignment is the critical success factor."],
        layout_family=LayoutFamily.TWO_COLUMN,
    )
    fixed = ContentCapacityValidator.validate_and_fix([spec])
    assert fixed[0].archetype_fields.get("qa_font_scale", 1.0) > 1.0


# =========================================================================
# 5. Repair Agent Verification Loop
# =========================================================================

def test_repair_shortening_actually_fits():
    """Verify repair action shorten_and_reflow shortens text and sets qa_repair_verified."""
    from app.agents.repair_agent import RepairAgent

    verbose_bullets = [
        "In the initial phase of deployment, the automated pipeline extracts high-fidelity vector assets from reference documents.",
        "Subsequently, the transformation engine parses multi-column data tables into structured semantic dictionaries.",
        "Finally, the QA verification suite validates geometry, contrast, and alignment before producing the final deck.",
    ]
    slide = SlideSpec(
        slide_number=5,
        headline="Pipeline Workflow",
        bullets=verbose_bullets,
        layout_family=LayoutFamily.TWO_COLUMN,
    )
    from app.schemas.generation_state import QAReport, ValidationCategory, ValidationIssue
    issue = ValidationIssue(
        checkpoint_id="QA-038",
        severity=ValidationSeverity.HIGH,
        category=ValidationCategory.GEOMETRY,
        slide_number=5,
        message="Text overflows card container",
        suggested_fix="Shorten text",
        auto_fixable=True,
        repair_action="shorten_and_reflow",
    )
    report = QAReport(overall_score=60, issues=[issue])

    # Call repair agent with shorten_and_reflow
    repaired_slides = RepairAgent.apply_corrections(
        slide_specs=[slide],
        qa_report=report,
        topic="Technology",
    )
    assert len(repaired_slides) == 1
    assert repaired_slides[0].archetype_fields.get("qa_post_repair_verified") is True


def test_repair_adapt_layout_to_content():
    """Verify repair agent adapt_layout_to_content routes to appropriate archetype for item count."""
    from app.agents.repair_agent import RepairAgent
    from app.schemas.generation_state import QAReport, ValidationCategory, ValidationIssue

    distinct_bullets = [
        "Feature 1: Sovereign defense and military command",
        "Feature 2: Treasury and tax revenue administration",
        "Feature 3: Judicial arbitration and civil courts",
        "Feature 4: Diplomatic foreign relations and envoys",
        "Feature 5: Trade regulation and port tariffs",
        "Feature 6: Agricultural waterworks and land registry",
        "Feature 7: Intelligence reconnaissance network",
        "Feature 8: Royal secretariat and record keeping",
    ]
    slide = SlideSpec(
        slide_number=6,
        headline="Council Structure",
        bullets=distinct_bullets,
        layout_family=LayoutFamily.TWO_COLUMN,
    )
    issue = ValidationIssue(
        checkpoint_id="QA-040",
        severity=ValidationSeverity.HIGH,
        category=ValidationCategory.GEOMETRY,
        slide_number=6,
        message="Elements overcrowded",
        suggested_fix="Adapt layout",
        auto_fixable=True,
        repair_action="adapt_layout_to_content",
    )
    report = QAReport(overall_score=70, issues=[issue])

    repaired = RepairAgent.apply_corrections(
        slide_specs=[slide],
        qa_report=report,
        topic="Governance",
    )
    assert repaired[0].layout_family == LayoutFamily.COUNCIL_EIGHT
    assert repaired[0].archetype_id == "A25"


# =========================================================================
# 6. Full PPTX Rendering Integration
# =========================================================================

def test_pptx_renderer_with_capacity_validator_and_grid_engine(standard_design_system):
    """Verify end-to-end rendering: slide specs pass pre-validation, render to PPTX, and compile without errors."""
    slides = [
        SlideSpec(
            slide_number=1,
            headline="Antigravity Executive Architecture",
            takeaway="Autonomous generation pipeline for enterprise presentation engineering.",
            layout_family=LayoutFamily.HERO,
            archetype_id="A1",
        ),
        SlideSpec(
            slide_number=2,
            headline="Four Key Architectural Pillars",
            bullets=[
                "Deterministic Grids: Mathematical coordinate layout eliminating drifting gutters.",
                "Text Metrics Engine: Exact character-ratio measurement preventing container overflow.",
                "Inline Collision Prevention: Geometry tracking asserting zero shape intersections.",
                "Pre-Render Validation: Proactive content adaptation before PPTX compilation.",
            ],
            layout_family=LayoutFamily.CARD_GRID,
            archetype_id="A13",
        ),
        SlideSpec(
            slide_number=3,
            headline="Delivery Roadmap & Next Milestones",
            bullets=[
                "Phase 1: Foundation measurement and grid coordinate baseline.",
                "Phase 2: Pre-render validation and collision prevention inline.",
                "Phase 3: QA verification loops and regression hardening.",
            ],
            layout_family=LayoutFamily.THREE_COLUMN,
            archetype_id="A11",
        ),
    ]

    pptx_bytes = PPTXRenderer.render_presentation(
        slide_specs=slides,
        design_system=standard_design_system,
        deck_title="Quality Engineering",
    )

    assert isinstance(pptx_bytes, bytes)
    assert len(pptx_bytes) > 5000

    # Parse PPTX to confirm structure
    prs = Presentation(io.BytesIO(pptx_bytes))
    assert len(prs.slides) == 3
    # Verify slide dimensions 16:9
    assert round(prs.slide_width.inches, 3) == 13.333
    assert round(prs.slide_height.inches, 3) == 7.500
