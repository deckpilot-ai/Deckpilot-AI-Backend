"""Unit tests for PPTX renderer."""

import io

from pptx import Presentation

from app.services.renderer import PPTXRenderer


def test_render_all_slide_layouts():
    spec = {
        "deckTitle": "Comprehensive Strategic Deck",
        "slides": [
            {
                "slideId": "s01",
                "purpose": "Title Hero",
                "message": "Transforming Prompt to Presentation",
                "layoutHint": "hero",
            },
            {
                "slideId": "s02",
                "purpose": "Operational Overview",
                "message": "High-velocity execution across teams",
                "layoutHint": "two_column",
                "bullets": ["Benchmark A hit", "Benchmark B hit"],
            },
            {
                "slideId": "s03",
                "purpose": "KPI Dashboard",
                "message": "Key Performance Metrics",
                "layoutHint": "chart",
            },
            {
                "slideId": "s04",
                "purpose": "Milestone Roadmap",
                "message": "Phased implementation schedule",
                "layoutHint": "timeline",
            },
        ],
    }

    brand = {
        "titleFont": {"name": "Calibri"},
        "colors": {
            "primary": "#1E3A8A",
            "secondary": "#0F172A",
            "accent": "#0D9488",
            "background": "#FFFFFF",
        },
    }

    pptx_bytes = PPTXRenderer.render_deck(spec, brand)
    assert len(pptx_bytes) > 10000
    assert pptx_bytes.startswith(b"PK\x03\x04")

    # Re-open with python-pptx to verify presentation structure
    prs = Presentation(io.BytesIO(pptx_bytes))
    assert len(prs.slides) == 4

    # Verify widescreen 16:9 dimensions
    assert int(prs.slide_width.inches) == 13
    assert int(prs.slide_height.inches) == 7
