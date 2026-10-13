"""End-to-End Test Suite validating deckpilot-skill optimization across the whole PPT generation pipeline.

Tests end-to-end against authentic reference presentations in Expected PPT/:
1. Reference PPT Analysis and Profile Extraction
2. Domain Classification and WCAG Contrast Verification
3. Storyline Planning with Variety Rules (no consecutive repeats, max 3 uses)
4. Spec Validation and Auto-Sanitization
5. Native High-Fidelity Rendering and Geometry
6. Collision Engine and Structural Quality Verification
"""

import os

from app.agents.design_intelligence import DesignIntelligenceAgent
from app.agents.storyline_agent import StorylineAgent
from app.schemas.generation_state import PresentationGoal
from app.services.deck_archetypes import ArchetypeSelector
from app.services.renderer import PPTXRenderer
from app.services.spec_validator import SpecValidator
from app.services.theme_engine import (
    PALETTES,
    audit_theme,
    build_theme,
    classify_domain,
    contrast_ratio,
)
from app.tools.pptx_validator import PPTXValidator
from app.tools.reference_ppt_analyzer import ReferencePPTAnalyzer

WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
EXPECTED_PPT_DIR = os.path.join(WORKSPACE_ROOT, "Expected PPT")


def test_theme_engine_all_14_palettes_pass_wcag():
    """Verify all 14 domain palettes from deckpilot-skill pass WCAG AA contrast."""
    for key in PALETTES:
        th = build_theme(palette_key=key)
        problems = audit_theme(th)
        assert problems == [], f"Palette {key} failed WCAG contrast: {problems}"


def test_theme_engine_domain_classification():
    """Verify domain classification correctly routes topics."""
    d1, _ = classify_domain("Enterprise SaaS Cloud Architecture & Security")
    assert d1 == "tech"

    d2, _ = classify_domain("Quarterly Financial Review, Budget and EBITDA")
    assert d2 == "finance"

    d3, _ = classify_domain("Constitutional Federalism and Sovereign Statecraft")
    assert d3 == "legal_gov"

    d4, _ = classify_domain("NCERT Grade 7 Understanding Markets and Economics")
    assert d4 in ("education", "finance")


def test_spec_validator_detects_and_sanitizes():
    """Verify Layer-1 spec validator detects defects and sanitizes them."""
    defective_spec = {
        "deckTitle": "A Rather Long Title That Exceeds The Maximum Allowed Words In A Normal Headline Structure",
        "slides": [
            {
                "headline": "This Headline Has Too Many Words For A Standard Executive Presentation Slide Title.",
                "bullets": [
                    "**First bullet with markdown** and trailing period.",
                    "• Literal bullet character with way too many unnecessary verbose descriptive words that will cause text overflow issues in presentation cards.",
                ],
            },
            {
                "headline": "This Headline Has Too Many Words For A Standard Executive Presentation Slide Title.",
                "bullets": ["Point A", "Point B"],
            },
        ],
    }

    issues_before = SpecValidator.validate_spec(defective_spec)
    assert len(issues_before) > 0

    sanitized = SpecValidator.sanitize_spec_inplace(defective_spec)
    s1 = sanitized["slides"][0]
    assert not s1["headline"].endswith(".")
    assert len(s1["headline"].split()) <= 10
    assert not s1["bullets"][0].startswith("**")
    assert not s1["bullets"][1].startswith("•")


def test_layout_variety_anti_repetition():
    """Verify ArchetypeSelector never repeats previous layout and respects max 3 uses."""
    used = []
    prev = None
    for _ in range(8):
        arch = ArchetypeSelector.select_archetype(
            content_type="comparison",
            previous_archetype=prev,
            used_archetypes=used,
        )
        assert arch != prev, f"Repeated previous archetype {prev}"
        used.append(arch)
        prev = arch

    # Check max 3 uses across body
    for a in set(used):
        assert used.count(a) <= 3, f"Archetype {a} used {used.count(a)} times (max 3)"


def test_end_to_end_federalism_reference_ppt():
    """End-to-end test using Expected PPT/Federalism (2).pptx reference."""
    fed_path = os.path.join(EXPECTED_PPT_DIR, "Federalism (2).pptx")
    assert os.path.exists(fed_path), f"Reference file missing: {fed_path}"

    with open(fed_path, "rb") as f:
        ppt_bytes = f.read()

    # 1. Reference intake & extraction
    profile = ReferencePPTAnalyzer.analyze_presentation(ppt_bytes, "Federalism (2).pptx")
    assert profile.get("slide_count", 0) > 0
    assert profile.get("fonts") is not None

    # 2. Design system generation with contrast guarantees
    goal = PresentationGoal(topic="Federalism Governance and Constitutional Power", target_slide_count=6)
    ds = DesignIntelligenceAgent.generate_design_system(goal, reference_profile=profile)
    assert ds.colors.primary.startswith("#")
    assert contrast_ratio(ds.colors.ink.lstrip("#"), "FFFFFF") >= 4.5

    # 3. Storyline planning with 17 deckpilot-skill layouts
    specs = StorylineAgent.create_storyline_plan(goal)
    assert len(specs) == 6

    # Verify no consecutive layout repeats
    for i in range(1, len(specs)):
        assert specs[i].layout_family != specs[i - 1].layout_family or specs[i].archetype_id != specs[i - 1].archetype_id

    # 4. Spec validation & sanitization
    raw_spec = {"deckTitle": goal.topic, "slides": [s.model_dump() for s in specs]}
    sanitized = SpecValidator.sanitize_spec_inplace(raw_spec)
    assert len(sanitized["slides"]) == 6

    # 5. Render PPTX
    rendered_bytes = PPTXRenderer.render_presentation(specs, ds, deck_title="Federalism Governance")
    assert len(rendered_bytes) > 20000

    # 6. Validate output
    report = PPTXValidator.validate_pptx_stream(rendered_bytes, 6)
    assert report.status == "passed", f"Validation failed with issues: {[i.message for i in report.issues]}"
    assert report.overall_quality_score >= 85.0
    assert report.slide_count == 6


def test_end_to_end_saas_growth_reference_ppt():
    """End-to-end test using Expected PPT/Accelerating Growth Our Journey into Enterprise SaaS_v1.pptx."""
    saas_path = os.path.join(EXPECTED_PPT_DIR, "Accelerating Growth Our Journey into Enterprise SaaS_v1.pptx")
    assert os.path.exists(saas_path), f"Reference file missing: {saas_path}"

    with open(saas_path, "rb") as f:
        ppt_bytes = f.read()

    # 1. Profile extraction
    profile = ReferencePPTAnalyzer.analyze_presentation(ppt_bytes, "Accelerating Growth Enterprise SaaS.pptx")
    assert profile.get("slide_count", 0) > 0

    # 2. Design system
    goal = PresentationGoal(topic="Enterprise SaaS Scaling and Growth Metrics", target_slide_count=5)
    ds = DesignIntelligenceAgent.generate_design_system(goal, reference_profile=profile)

    # 3. Storyline planning with metric / data cards
    specs = StorylineAgent.create_storyline_plan(goal)
    assert len(specs) == 5

    # 4. Render
    rendered_bytes = PPTXRenderer.render_presentation(specs, ds, deck_title="Accelerating Growth")
    assert len(rendered_bytes) > 15000

    # 5. Quality verification
    report = PPTXValidator.validate_pptx_stream(rendered_bytes, 5)
    assert report.status == "passed"
    assert report.overall_quality_score >= 85.0


def test_end_to_end_development_reference_ppt():
    """End-to-end test using Expected PPT/Development (2).pptx."""
    dev_path = os.path.join(EXPECTED_PPT_DIR, "Development (2).pptx")
    assert os.path.exists(dev_path), f"Reference file missing: {dev_path}"

    with open(dev_path, "rb") as f:
        ppt_bytes = f.read()

    profile = ReferencePPTAnalyzer.analyze_presentation(ppt_bytes, "Development (2).pptx")
    goal = PresentationGoal(topic="Economic Development and Shared Capabilities", target_slide_count=5)
    ds = DesignIntelligenceAgent.generate_design_system(goal, reference_profile=profile)
    specs = StorylineAgent.create_storyline_plan(goal)
    rendered_bytes = PPTXRenderer.render_presentation(specs, ds, deck_title="Economic Development")
    report = PPTXValidator.validate_pptx_stream(rendered_bytes, 5)
    assert report.status == "passed"
    assert report.overall_quality_score >= 85.0
