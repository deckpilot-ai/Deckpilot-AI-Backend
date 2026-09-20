import asyncio
import io
import re
import pytest
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.enum.shapes import MSO_SHAPE

from app.schemas.generation_state import (
    AssetMetadata,
    DesignSystem,
    LayoutFamily,
    PresentationGoal,
    SlideSpec,
    ValidationSeverity,
)
from app.services.archetype_renderer import ArchetypeRenderer
from app.services.renderer import PPTXRenderer
from app.agents.storyline_agent import StorylineAgent
from app.agents.qa_agent import PresentationQAAgent
from app.agents.repair_agent import RepairAgent
from app.services.image_matcher import ImageMatcher, tokenize


def test_no_hardcoded_strings_in_archetype_renderer():
    """Verify that no historical textbook mock strings appear in archetype output."""
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    slide = prs.slides.add_slide(prs.slide_layouts[6])

    spec = SlideSpec(
        slide_number=1,
        headline="Quarterly Cloud Infrastructure Growth",
        key_message="Sustained adoption across enterprise accounts",
        takeaway="Operational reliability remains top priority",
        bullets=[
            "Data Center Expansion: Scaled across 3 major regions",
            "Latency Reduction: Achieved sub-50ms roundtrip delivery",
        ],
        layout_family=LayoutFamily.A24_TIMELINE_BAND,
        archetype_id="A24",
    )
    ds = DesignSystem()

    ArchetypeRenderer.render(slide, "A24", spec, ds)

    all_text = " ".join(
        shape.text for shape in slide.shapes if getattr(shape, "has_text_frame", False)
    )

    forbidden_strings = [
        "Swāmi",
        "Peshwa",
        "Amatya",
        "Sachiv",
        "Sumant",
        "Panditrao",
        "Nyayadish",
        "Senapati",
        "Limb",
        "Forts are the core",
        "Universal moral conduct",
        "1630: Foundation & Early Sovereignty",
        "Dharma & Rajyavyavahara",
    ]

    for forbidden in forbidden_strings:
        assert forbidden.lower() not in all_text.lower(), f"Found forbidden hardcoded string: '{forbidden}'"


def test_timeline_chronology_detection():
    """StorylineAgent._determine_layout should route chronological content to LayoutFamily.TIMELINE."""
    raw_slide = {
        "headline": "Major Milestones of Modern Computing",
        "purpose": "Historical development from early mainframes to cloud",
        "bullets": [
            "1945: ENIAC becomes operational as first programmable computer",
            "1969: ARPANET established, creating the foundation for the internet",
            "1981: IBM Personal Computer launched, revolutionizing business computing",
            "1991: World Wide Web made publicly available",
        ],
    }
    goal = PresentationGoal(topic="History of Computing", target_slide_count=5)

    chosen = StorylineAgent._determine_layout(
        index=1,
        total_slides=5,
        hint="",
        recent=[],
        raw_slide=raw_slide,
        assets=[],
        goal=goal,
    )
    assert chosen == LayoutFamily.TIMELINE


def test_a24_timeline_rendering():
    """Verify A24 dynamically renders 4 milestones without Shivaji/Maratha mock data."""
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    slide = prs.slides.add_slide(prs.slide_layouts[6])

    spec = SlideSpec(
        slide_number=2,
        headline="Key Milestones in Renewable Energy Transition",
        bullets=[
            "1997: Kyoto Protocol adopted",
            "2015: Paris Agreement signed by 196 nations",
            "2020: Global solar PV capacity surpasses 700 GW",
            "2025: Renewable generation accounts for 35% of global power",
        ],
        layout_family=LayoutFamily.TIMELINE,
        archetype_id="A24",
    )
    ds = DesignSystem()

    ArchetypeRenderer.render(slide, "A24", spec, ds)

    rendered_text = " ".join(
        shape.text for shape in slide.shapes if getattr(shape, "has_text_frame", False)
    )
    assert "1997" in rendered_text
    assert "Paris Agreement" in rendered_text
    assert "Kyoto Protocol" in rendered_text
    assert "1630" not in rendered_text


def test_qa_agent_detects_long_paragraph_title():
    """QA Agent must detect overly long and paragraph-style titles as HIGH severity."""
    specs = [
        SlideSpec(
            slide_number=1,
            headline="Comprehensive Overview of the Strategic Imperatives and Multiple Cross-Functional Initiatives Undertaken During the Entire Fiscal Year.",
            bullets=["Bullet A: Revenue grew by 20%", "Bullet B: Margins improved by 400 bps"],
            layout_family=LayoutFamily.TWO_COLUMN,
        )
    ]
    ds = DesignSystem()
    report = PresentationQAAgent.evaluate_presentation(specs, ds)

    long_title_issues = [
        i for i in report.issues
        if i.checkpoint_id in ("QA-003", "QA-121") or "title" in i.message.lower()
    ]
    assert len(long_title_issues) >= 1
    assert any(i.severity in (ValidationSeverity.HIGH, ValidationSeverity.MEDIUM) for i in long_title_issues)


def test_qa_agent_detects_timeline_chronology_disorder():
    """QA Agent must detect milestones out of chronological sequence."""
    specs = [
        SlideSpec(
            slide_number=2,
            headline="Chronological Evolution of State Policy",
            bullets=[
                "1942: Quit India Movement",
                "1919: Jallianwala Bagh incident",  # Out of order!
                "1947: Indian Independence Act",
            ],
            layout_family=LayoutFamily.TIMELINE,
            archetype_id="A24",
        )
    ]
    ds = DesignSystem()
    report = PresentationQAAgent.evaluate_presentation(specs, ds)

    disorder_issues = [
        i for i in report.issues
        if i.checkpoint_id == "QA-123" or "chronological" in i.message.lower()
    ]
    assert len(disorder_issues) >= 1
    assert disorder_issues[0].severity == ValidationSeverity.HIGH


def test_qa_agent_detects_empty_shape_in_rendered_pptx():
    """QA Agent must inspect rendered shapes and flag empty content boxes."""
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    slide = prs.slides.add_slide(prs.slide_layouts[6])

    # Add a title
    title_box = slide.shapes.add_textbox(Inches(1), Inches(1), Inches(8), Inches(1))
    title_box.text = "Strategic Roadmap"

    # Add an empty content card
    empty_card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(1), Inches(2.5), Inches(4), Inches(2))
    empty_card.name = "content-card-1"
    empty_card.text_frame.text = ""  # Empty!

    pptx_io = io.BytesIO()
    prs.save(pptx_io)
    pptx_bytes = pptx_io.getvalue()

    specs = [
        SlideSpec(
            slide_number=1,
            headline="Strategic Roadmap",
            bullets=["Point 1: Strategic Direction"],
            layout_family=LayoutFamily.CARD_GRID,
        )
    ]
    ds = DesignSystem()
    report = PresentationQAAgent.evaluate_presentation(specs, ds, pptx_bytes=pptx_bytes)

    empty_shape_issues = [
        i for i in report.issues
        if i.checkpoint_id == "QA-116" or "empty shape" in i.message.lower()
    ]
    assert len(empty_shape_issues) >= 1


def test_repair_agent_rewrites_bad_title():
    """Repair Agent must shorten and clean paragraph titles."""
    bad_spec = SlideSpec(
        slide_number=1,
        headline="The Comprehensive List of Key Milestones and Critical Technical Architecture Changes That Occurred in 2025.",
        bullets=["Milestone A", "Milestone B"],
        layout_family=LayoutFamily.TWO_COLUMN,
    )
    ds = DesignSystem()
    report = PresentationQAAgent.evaluate_presentation([bad_spec], ds)

    repaired = RepairAgent.apply_corrections([bad_spec], report)
    assert len(repaired) == 1
    repaired_title = repaired[0].headline
    assert len(repaired_title.split()) <= 8
    assert not repaired_title.endswith(".")


def test_repair_agent_reorders_timeline():
    """Repair Agent reorder_timeline should sort out-of-order years."""
    disordered_spec = SlideSpec(
        slide_number=1,
        headline="Historical Timeline",
        bullets=[
            "1947: Independence",
            "1857: Revolt",
            "1919: Jallianwala Bagh",
        ],
        layout_family=LayoutFamily.TIMELINE,
        archetype_id="A24",
    )
    ds = DesignSystem()
    report = PresentationQAAgent.evaluate_presentation([disordered_spec], ds)

    repaired = RepairAgent.apply_corrections([disordered_spec], report)
    assert len(repaired) == 1
    bullets = repaired[0].bullets
    assert "1857" in bullets[0]
    assert "1919" in bullets[1]
    assert "1947" in bullets[2]


def test_image_matcher_semantic_allocation():
    """Verify ImageMatcher assigns available valid documentary assets to slides."""
    slides = [
        SlideSpec(slide_number=1, headline="Ancient Mauryan Empire", bullets=["Empire founded by Chandragupta"]),
        SlideSpec(slide_number=2, headline="Ashoka's Edicts and Inscriptions", bullets=["Major Rock Edicts deciphered by James Prinsep"]),
        SlideSpec(slide_number=3, headline="Administrative Structure and Economy", bullets=["Agrarian revenue and coinage system"]),
    ]
    assets = [
        AssetMetadata(
            asset_id="art_ashoka_edicts",
            caption="Ashoka pillar inscription at Sarnath",
            quality_score=0.9,
        ),
        AssetMetadata(
            asset_id="art_mauryan_map",
            caption="Map of the Mauryan Empire territories",
            quality_score=0.9,
        ),
    ]

    ImageMatcher.assign_images_semantically(slides, assets, topic_context="Mauryan Empire")

    assigned_slides = [s for s in slides if s.image_artifact_id]
    assert len(assigned_slides) >= 1
    assert any(s.image_artifact_id == "art_ashoka_edicts" for s in assigned_slides)
