"""Unit tests for consulting deck archetypes and automated PPT design configurator tool."""

import io
import os
import pytest

from pptx import Presentation
from pptx.util import Inches

from app.schemas.generation_state import LayoutFamily, PresentationGoal, SlideSpec
from app.services.deck_archetypes import (
    ArchetypeSelector,
    ColorTokens,
    GRID_SPEC,
    LAYOUT_ARCHETYPES,
    PaletteGenerator,
)
from app.services.design_preset_registry import DesignPresetRegistry
from app.services.renderer import PPTXRenderer
from app.tools.design_auto_configurator import DesignAutoConfigurator


def test_layout_archetypes_catalog_integrity():
    """Verify all 23 archetypes are registered with valid schemas and families."""
    assert len(LAYOUT_ARCHETYPES) == 23
    for arch_id in (f"A{i}" for i in range(1, 24)):
        assert arch_id in LAYOUT_ARCHETYPES
        arch = LAYOUT_ARCHETYPES[arch_id]
        assert "family" in arch
        assert "name" in arch
        assert "when_to_use" in arch
        assert "schema_keys" in arch


def test_palette_generator_semantic_matching():
    """Verify topic keywords generate expected consulting color tokens."""
    marathas_pal = PaletteGenerator.generate_palette("The Rise of the Maratha Empire")
    assert marathas_pal.ink == "#7E2C22"
    assert marathas_pal.primary == "#E4791F"

    fed_pal = PaletteGenerator.generate_palette("Federalism in the Indian Constitution")
    assert fed_pal.ink == "#0C3B39"
    assert fed_pal.primary == "#0E7C7B"

    econ_pal = PaletteGenerator.generate_palette("Sectors of the Indian Economy")
    assert econ_pal.ink == "#1F3864"
    assert econ_pal.primary == "#5B9BD5"


def test_archetype_selector_anti_pattern_avoidance():
    """Verify consecutive duplicate archetypes are avoided."""
    first = ArchetypeSelector.select_archetype("comparison")
    second = ArchetypeSelector.select_archetype("comparison", previous_archetype=first)
    assert first != second


def test_archetype_rendering_to_pptx():
    """Verify rendering slides with consulting archetypes produces valid presentation."""
    from app.agents.design_intelligence import DesignIntelligenceAgent
    from app.agents.storyline_agent import StorylineAgent

    goal = PresentationGoal(topic="Federalism Governance Framework", target_slide_count=5)
    specs = StorylineAgent.create_storyline_plan(goal)
    ds = DesignIntelligenceAgent.generate_design_system(goal)

    # Ensure archetypes are assigned
    for s in specs:
        assert s.archetype_id is not None
        assert s.archetype_id.startswith("A")

    pptx_bytes = PPTXRenderer.render_presentation(specs, ds, deck_title="Federalism Governance")
    assert len(pptx_bytes) > 10000

    report = PPTXRenderer.validate_deck(pptx_bytes, 5)
    assert report["status"] == "passed"
    assert report["overall_quality_score"] >= 70.0


def test_design_auto_configurator_extract_and_register():
    """Verify auto-configurator extracts visual language from a PPTX and registers a preset."""
    # Create a minimal synthetic PPTX with custom colors and font
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    slide = prs.slides.add_slide(prs.slide_layouts[6])

    from pptx.dml.color import RGBColor
    from pptx.enum.shapes import MSO_SHAPE

    shape = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(1), Inches(1), Inches(5), Inches(3))
    shape.fill.solid()
    shape.fill.fore_color.rgb = RGBColor(14, 124, 123)

    tf = shape.text_frame
    p = tf.paragraphs[0]
    p.text = "Strategic Executive Review"
    p.font.name = "Cambria"
    p.font.size = Inches(0.4)

    buf = io.BytesIO()
    prs.save(buf)
    sample_bytes = buf.getvalue()

    preset = DesignAutoConfigurator.configure_from_pptx(sample_bytes, name="Test Auto Config Preset")
    assert preset["id"].startswith("preset_")
    assert preset["name"] == "Test Auto Config Preset"
    assert "ink" in preset["colors"]
    assert "primary" in preset["colors"]
    assert "title_font" in preset["typography"]
    assert preset["typography"]["title_font"] == "Cambria"

    # Verify preset was registered in registry
    retrieved = DesignPresetRegistry.get_preset(preset["id"])
    assert retrieved is not None
    assert retrieved["id"] == preset["id"]
