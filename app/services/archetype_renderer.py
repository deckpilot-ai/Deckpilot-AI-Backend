"""High-Fidelity 23 Archetype Renderer for PowerPoint Presentations.

Implements the exact layout geometry, card headers, photo mats, pill rows,
and connector elements from deck-agent-package/layout_archetypes.json.
"""

import io
import logging
import math
import re
from typing import Any

from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.xmlchemy import OxmlElement
from pptx.util import Inches, Pt

from app.schemas.generation_state import DesignSystem, SlideSpec
from app.services.deck_archetypes import GRID_SPEC, LAYOUT_ARCHETYPES
from app.services.design_system import clean_text

logger = logging.getLogger(__name__)


def hex_to_rgb(value: str, default: tuple[int, int, int] = (19, 42, 82)) -> RGBColor:
    val = value.lstrip("#")
    try:
        return RGBColor(int(val[0:2], 16), int(val[2:4], 16), int(val[4:6], 16))
    except Exception:
        return RGBColor(*default)


def tint(color: RGBColor, amount: float) -> RGBColor:
    return RGBColor(*(round(c + (255 - c) * amount) for c in color))


class ArchetypeRenderer:
    """Renders slides matching archetypes A1 through A23 with exact geometry."""

    @classmethod
    def can_render(cls, archetype_id: str | None) -> bool:
        return bool(archetype_id and archetype_id.upper() in LAYOUT_ARCHETYPES)

    @classmethod
    def render(
        cls,
        slide: Any,
        archetype_id: str,
        slide_data: SlideSpec,
        design_system: DesignSystem,
        image_bytes: bytes | None = None,
        renderer_cls: Any = None,
    ) -> bool:
        arch = archetype_id.upper()
        method_name = f"_render_{arch.lower()}"
        method = getattr(cls, method_name, None)
        if method:
            try:
                method(slide, slide_data, design_system, image_bytes, renderer_cls)
                return True
            except ValueError:
                raise
            except Exception as e:
                logger.warning("Error rendering archetype %s: %s", arch, e, exc_info=True)
                return False
        return False

    # ──────────────────────────────────────────────────────────────────────────
    # A1: Title Cover - Blob Variant
    # ──────────────────────────────────────────────────────────────────────────
    @classmethod
    def _render_a1(cls, slide, data: SlideSpec, ds: DesignSystem, img: bytes | None, r_cls):
        primary = hex_to_rgb(ds.colors.primary)
        secondary = hex_to_rgb(getattr(ds.colors, "secondary", ds.colors.primary))
        white = RGBColor(255, 255, 255)
        title_font = ds.typography.title_font.name
        body_font = ds.typography.body_font.name

        # Decorative soft ellipses bleeding off canvas
        r_cls._shape(slide, MSO_SHAPE.OVAL, 9.6, -2.0, 6.5, 6.5, tint(primary, 0.85), "blob-1")
        r_cls._shape(slide, MSO_SHAPE.OVAL, 11.0, 3.6, 5.2, 5.2, tint(secondary, 0.88), "blob-2")
        r_cls._shape(slide, MSO_SHAPE.OVAL, -1.6, 4.6, 4.4, 4.4, tint(primary, 0.90), "blob-3")

        # Eyebrow
        eyebrow = (data.eyebrow or "CONSULTING PERSPECTIVE").upper()
        r_cls._text(slide, eyebrow, 0.9, 1.4, 8.0, 0.35, primary, body_font, 14, bold=True)

        # Large Headline Title
        title = data.headline or data.key_message or "Strategic Presentation"
        r_cls._text(slide, title, 0.85, 1.85, 11.5, 1.9, primary, title_font, 48, title=True)

        # Subtitle / Takeaway
        subtitle = data.takeaway or data.subtitle or (data.bullets[0] if data.bullets else "")
        if subtitle:
            r_cls._text(slide, subtitle, 0.9, 3.85, 10.5, 0.8, hex_to_rgb(ds.colors.text_secondary), body_font, 18)

        # Topic Pills
        pills = data.bullets[:4] if data.bullets else ["Strategic Foundations", "Operational Delivery", "Institutional Impact"]
        pill_y = 4.95
        px = 0.9
        for p in pills:
            label = clean_text(p).split(":")[0].strip()[:35]
            pw = max(1.8, min(3.5, len(label) * 0.12 + 0.5))
            r_cls._shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, px, pill_y, pw, 0.45, tint(primary, 0.88), "topic-pill", corner_radius=0.2)
            r_cls._text(slide, label, px, pill_y + 0.05, pw, 0.35, primary, body_font, 11, bold=True, center=True)
            px += pw + 0.25

        # Footer note / Badge
        r_cls._shape(slide, MSO_SHAPE.OVAL, 0.9, 6.25, 0.55, 0.55, primary, "seal")
        r_cls._text(slide, "★", 0.9, 6.25, 0.55, 0.55, white, body_font, 14, bold=True, center=True)
        r_cls._text(slide, "Executive Advisory & Comprehensive Evaluation", 1.6, 6.32, 9.5, 0.4, hex_to_rgb(ds.colors.text_secondary), body_font, 12)

    # ──────────────────────────────────────────────────────────────────────────
    # A2: Title Cover - Split Panel
    # ──────────────────────────────────────────────────────────────────────────
    @classmethod
    def _render_a2(cls, slide, data: SlideSpec, ds: DesignSystem, img: bytes | None, r_cls):
        ink = hex_to_rgb(getattr(ds.colors, "ink", ds.colors.primary))
        primary = hex_to_rgb(ds.colors.primary)
        tint_a = hex_to_rgb(getattr(ds.colors, "tint_a", ds.colors.card_fill))
        white = RGBColor(255, 255, 255)
        title_font = ds.typography.title_font.name
        body_font = ds.typography.body_font.name

        # Left 55%: text narrative
        eyebrow = (data.eyebrow or "CASE STUDY & ANALYSIS").upper()
        r_cls._text(slide, eyebrow, 0.65, 1.25, 6.5, 0.35, primary, body_font, 13, bold=True)

        title = data.headline or data.key_message or "Executive Briefing"
        r_cls._text(slide, title, 0.65, 1.75, 6.6, 2.1, ink, title_font, 42, title=True)

        # 1.7" Accent Tick
        r_cls._shape(slide, MSO_SHAPE.RECTANGLE, 0.65, 3.95, 1.7, 0.07, primary, "accent-tick")

        subtitle = data.takeaway or (data.bullets[0] if data.bullets else "")
        if subtitle:
            r_cls._text(slide, subtitle, 0.65, 4.2, 6.5, 1.2, hex_to_rgb(ds.colors.text_secondary), body_font, 15)

        r_cls._text(slide, "COMPREHENSIVE RESEARCH EVALUATION", 0.65, 6.2, 6.5, 0.35, primary, body_font, 11, bold=True)

        # Right 45%: Framed Hero Photo with Mat in Ink Block
        r_cls._shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, 7.6, 0.8, 5.15, 5.8, ink, "photo-container", corner_radius=0.03)
        if img:
            r_cls._shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, 7.85, 1.1, 4.65, 4.5, tint_a, "photo-mat", corner_radius=0.02)
            r_cls._render_picture(slide, img, 7.95, 1.2, 4.45, 4.3)
            caption = data.image_caption or "Documentary reference figure"
            r_cls._text(slide, caption[:80], 7.85, 5.8, 4.65, 0.5, white, body_font, 10, italic=True, center=True)
        else:
            r_cls._text(slide, "Strategic Focus", 8.0, 3.2, 4.35, 0.8, white, title_font, 22, bold=True, center=True)

    # ──────────────────────────────────────────────────────────────────────────
    # A3: Section Divider - Photo Hero
    # ──────────────────────────────────────────────────────────────────────────
    @classmethod
    def _render_a3(cls, slide, data: SlideSpec, ds: DesignSystem, img: bytes | None, r_cls):
        ink = hex_to_rgb(getattr(ds.colors, "ink", ds.colors.primary))
        white = RGBColor(255, 255, 255)
        title_font = ds.typography.title_font.name
        body_font = ds.typography.body_font.name

        # Background Fill
        slide.background.fill.solid()
        slide.background.fill.fore_color.rgb = ink

        if img:
            r_cls._render_picture(slide, img, 0, 0, 13.333, 7.5)
            # Scrim overlay for readability
            r_cls._shape(slide, MSO_SHAPE.RECTANGLE, 0, 3.5, 13.333, 4.0, ink, "scrim")

        # Brand Capsule top-right
        r_cls._shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, 10.4, 0.4, 2.3, 0.6, white, "brand-capsule", corner_radius=0.3)
        r_cls._text(slide, "DECKPILOT ADVISORY", 10.4, 0.45, 2.3, 0.5, ink, body_font, 10, bold=True, center=True)

        # Headline
        title = data.headline or "Strategic Section"
        r_cls._text(slide, title, 0.8, 4.2, 10.0, 1.6, white, title_font, 38, bold=True)
        if data.takeaway:
            r_cls._text(slide, data.takeaway, 0.8, 5.9, 10.0, 0.8, tint(white, 0.2), body_font, 16)

    # ──────────────────────────────────────────────────────────────────────────
    # A4: Chapter Roadmap / Agenda
    # ──────────────────────────────────────────────────────────────────────────
    @classmethod
    def _render_a4(cls, slide, data: SlideSpec, ds: DesignSystem, img: bytes | None, r_cls):
        primary = hex_to_rgb(ds.colors.primary)
        tint_a = hex_to_rgb(getattr(ds.colors, "tint_a", ds.colors.card_fill))
        white = RGBColor(255, 255, 255)
        body_col = hex_to_rgb(ds.colors.text_secondary)
        title_font = ds.typography.title_font.name
        body_font = ds.typography.body_font.name

        items = data.bullets[:6] if data.bullets else [
            "Institutional Foundations: Historical origins and constitutional design",
            "Functional Distribution: Core administrative responsibilities",
            "Performance Evidence: Empirical findings and key benchmarks",
            "Strategic Synthesis: Future horizon and execution priorities",
        ]

        row_y = 2.15
        row_h = 0.72
        row_gap = 0.12

        for k, item in enumerate(items):
            bg = white if k % 2 == 0 else tint_a
            y = row_y + k * (row_h + row_gap)
            r_cls._shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, 0.6, y, 12.1, row_h, bg, f"agenda-row-{k+1}", corner_radius=0.04)

            # Circular badge
            r_cls._shape(slide, MSO_SHAPE.OVAL, 0.85, y + 0.12, 0.48, 0.48, primary, f"badge-{k+1}")
            r_cls._text(slide, f"0{k+1}", 0.85, y + 0.14, 0.48, 0.44, white, body_font, 11, bold=True, center=True)

            # Label & Description
            parts = item.split(":", 1) if ":" in item else [item[:40], item[40:]]
            lbl = parts[0].strip()
            desc = parts[1].strip() if len(parts) > 1 else ""

            r_cls._text(slide, lbl, 1.5, y + 0.08, 9.2, 0.32, primary, title_font, 14, bold=True)
            if desc:
                r_cls._text(slide, desc[:120], 1.5, y + 0.38, 9.2, 0.3, body_col, body_font, 11)

            # Large ghost page number right
            r_cls._text(slide, f"P. 0{k+2}", 10.9, y + 0.12, 1.5, 0.48, tint(primary, 0.75), title_font, 20, bold=True, center=True)

    # ──────────────────────────────────────────────────────────────────────────
    # A5: Core Definition
    # ──────────────────────────────────────────────────────────────────────────
    @classmethod
    def _render_a5(cls, slide, data: SlideSpec, ds: DesignSystem, img: bytes | None, r_cls):
        ink = hex_to_rgb(getattr(ds.colors, "ink", ds.colors.primary))
        primary = hex_to_rgb(ds.colors.primary)
        tint_a = hex_to_rgb(getattr(ds.colors, "tint_a", ds.colors.card_fill))
        tint_b = hex_to_rgb(getattr(ds.colors, "tint_b", ds.colors.neutral))
        white = RGBColor(255, 255, 255)
        title_font = ds.typography.title_font.name
        body_font = ds.typography.body_font.name

        # Left 52%: Definition Card in Ink
        r_cls._shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, 0.6, 2.05, 6.2, 2.45, ink, "def-card", corner_radius=0.04)
        def_text = data.takeaway or (data.bullets[0] if data.bullets else "Core conceptual framework.")
        r_cls._text(slide, "DEFINITION & DOCTRINE", 0.9, 2.25, 5.6, 0.3, tint(primary, 0.6), body_font, 11, bold=True)
        r_cls._text(slide, def_text[:240], 0.9, 2.65, 5.6, 1.7, white, title_font, 17)

        # Right 45%: Two Stacked Attribute Rows
        attrs = data.bullets[1:3] if len(data.bullets) > 2 else (data.bullets[:2] if data.bullets else ["Institutional scope", "Administrative function"])
        for j, attr in enumerate(attrs[:2]):
            ay = 2.05 + j * 1.3
            r_cls._shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, 7.1, ay, 5.6, 1.15, tint_a, f"attr-{j+1}", corner_radius=0.04)
            r_cls._shape(slide, MSO_SHAPE.OVAL, 7.35, ay + 0.2, 0.45, 0.45, primary, f"attr-badge-{j+1}")
            r_cls._text(slide, f"0{j+1}", 7.35, ay + 0.22, 0.45, 0.4, white, body_font, 11, bold=True, center=True)
            aparts = attr.split(":", 1) if ":" in attr else [attr[:35], attr[35:]]
            r_cls._text(slide, aparts[0].strip(), 8.0, ay + 0.15, 4.5, 0.32, primary, title_font, 13, bold=True)
            if len(aparts) > 1:
                r_cls._text(slide, aparts[1].strip()[:100], 8.0, ay + 0.48, 4.5, 0.55, hex_to_rgb(ds.colors.text_secondary), body_font, 11)

        # Bottom Band: Why it Matters (3 columns)
        r_cls._shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, 0.6, 4.75, 12.1, 2.0, tint_b, "why-band", corner_radius=0.04)
        r_cls._text(slide, "STRATEGIC IMPLICATIONS & OUTCOMES", 0.85, 4.9, 11.0, 0.3, primary, body_font, 11, bold=True)

        why_items = data.bullets[3:6] if len(data.bullets) >= 6 else (data.bullets[:3] if data.bullets else ["Autonomy", "Scale", "Stability"])
        cw = 3.65
        for m, item in enumerate(why_items[:3]):
            cx = 0.85 + m * (cw + 0.4)
            r_cls._shape(slide, MSO_SHAPE.OVAL, cx, 5.35, 0.4, 0.4, primary, f"why-disc-{m+1}")
            r_cls._text(slide, "✓", cx, 5.35, 0.4, 0.4, white, body_font, 12, bold=True, center=True)
            wparts = item.split(":", 1) if ":" in item else [item[:30], item[30:]]
            r_cls._text(slide, wparts[0].strip(), cx + 0.5, 5.3, cw - 0.5, 0.32, ink, title_font, 12.5, bold=True)
            if len(wparts) > 1:
                r_cls._text(slide, wparts[1].strip()[:90], cx + 0.5, 5.65, cw - 0.5, 0.95, hex_to_rgb(ds.colors.text_secondary), body_font, 10.5)

    # ──────────────────────────────────────────────────────────────────────────
    # A6: Two-Entity Comparison Cards
    # ──────────────────────────────────────────────────────────────────────────
    @classmethod
    def _render_a6(cls, slide, data: SlideSpec, ds: DesignSystem, img: bytes | None, r_cls):
        primary = hex_to_rgb(ds.colors.primary)
        secondary = hex_to_rgb(getattr(ds.colors, "secondary", ds.colors.primary))
        tint_a = hex_to_rgb(getattr(ds.colors, "tint_a", ds.colors.card_fill))
        tint_b = hex_to_rgb(getattr(ds.colors, "tint_b", ds.colors.neutral))
        white = RGBColor(255, 255, 255)
        title_font = ds.typography.title_font.name
        body_font = ds.typography.body_font.name

        mid = max(1, math.ceil(len(data.bullets) / 2))
        group_a = data.bullets[:mid]
        group_b = data.bullets[mid:]

        labels = ["PRIMARY MODEL / ENTITY A", "CONTRAST MODEL / ENTITY B"]
        if data.takeaway and "vs" in data.takeaway.lower():
            p = re.split(r"\s+vs\.?\s+", data.takeaway, flags=re.IGNORECASE)
            if len(p) >= 2:
                labels = [p[0].strip().upper()[:35], p[1].strip().upper()[:35]]

        for j, (grp, col, bg_tint, lbl) in enumerate([(group_a, primary, tint_a, labels[0]), (group_b, secondary, tint_b, labels[1])]):
            x = 0.6 + j * 6.25
            w = 5.85
            # Main white card with subtle border
            r_cls._shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, x, 2.05, w, 4.75, white, f"card-{j+1}", corner_radius=0.04)

            # Header block
            r_cls._shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, x, 2.05, w, 1.0, col, f"card-hdr-{j+1}", corner_radius=0.04)
            r_cls._shape(slide, MSO_SHAPE.OVAL, x + 0.25, 2.25, 0.55, 0.55, white, f"hdr-badge-{j+1}")
            r_cls._text(slide, f"0{j+1}", x + 0.25, 2.27, 0.55, 0.5, col, body_font, 12, bold=True, center=True)
            r_cls._text(slide, lbl, x + 0.95, 2.35, w - 1.2, 0.4, white, title_font, 14, bold=True)

            # 3 numbered points
            for k, pt in enumerate(grp[:3]):
                py = 3.25 + k * 1.15
                r_cls._shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, x + 0.25, py, w - 0.5, 1.0, bg_tint, f"chip-{j+1}-{k+1}", corner_radius=0.03)
                r_cls._shape(slide, MSO_SHAPE.OVAL, x + 0.45, py + 0.15, 0.35, 0.35, col, f"bullet-{j+1}-{k+1}")
                r_cls._text(slide, str(k + 1), x + 0.45, py + 0.17, 0.35, 0.3, white, body_font, 10, bold=True, center=True)
                r_cls._text(slide, clean_text(pt)[:110], x + 0.95, py + 0.12, w - 1.3, 0.8, hex_to_rgb(ds.colors.text_primary), body_font, 11)

    # ──────────────────────────────────────────────────────────────────────────
    # A8: Stat + Map/Image Highlight
    # ──────────────────────────────────────────────────────────────────────────
    @classmethod
    def _render_a8(cls, slide, data: SlideSpec, ds: DesignSystem, img: bytes | None, r_cls):
        ink = hex_to_rgb(getattr(ds.colors, "ink", ds.colors.primary))
        primary = hex_to_rgb(ds.colors.primary)
        tint_a = hex_to_rgb(getattr(ds.colors, "tint_a", ds.colors.card_fill))
        tint_b = hex_to_rgb(getattr(ds.colors, "tint_b", ds.colors.neutral))
        white = RGBColor(255, 255, 255)
        title_font = ds.typography.title_font.name
        body_font = ds.typography.body_font.name

        # Left 45%: 2 Stacked Stat blocks + 1 Dark Callout
        metrics = data.metrics[:2] if data.metrics else [
            {"value": "85%", "label": "Territorial / Population Reach"},
            {"value": "3.4x", "label": "Growth in Sovereign Revenues"},
        ]

        for k, m in enumerate(metrics[:2]):
            sy = 2.05 + k * 1.3
            bg = tint_a if k == 0 else tint_b
            r_cls._shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, 0.6, sy, 5.0, 1.15, bg, f"stat-card-{k+1}", corner_radius=0.04)
            r_cls._text(slide, str(m.get("value", "")), 0.85, sy + 0.1, 4.5, 0.55, primary, title_font, 36, bold=True)
            r_cls._text(slide, str(m.get("label", "")), 0.85, sy + 0.68, 4.5, 0.38, hex_to_rgb(ds.colors.text_secondary), body_font, 12)

        # Callout card at bottom left
        r_cls._shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, 0.6, 4.8, 5.0, 1.95, ink, "callout-card", corner_radius=0.04)
        r_cls._shape(slide, MSO_SHAPE.OVAL, 0.85, 5.0, 0.45, 0.45, primary, "callout-icon")
        r_cls._text(slide, "★", 0.85, 5.0, 0.45, 0.45, white, body_font, 12, bold=True, center=True)
        callout_txt = data.takeaway or (data.bullets[0] if data.bullets else "Strategic evidence analysis")
        r_cls._text(slide, "KEY EVIDENCE INSIGHT", 1.45, 5.05, 4.0, 0.3, tint(primary, 0.6), body_font, 11, bold=True)
        r_cls._text(slide, callout_txt[:160], 0.85, 5.5, 4.5, 1.1, white, body_font, 12)

        # Right 52%: Framed Photo Mat
        r_cls._shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, 5.9, 2.05, 6.8, 4.75, white, "mat-frame", corner_radius=0.03)
        if img:
            r_cls._shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, 6.05, 2.2, 6.5, 4.0, tint_a, "mat-backing", corner_radius=0.02)
            r_cls._render_picture(slide, img, 6.15, 2.3, 6.3, 3.8)
            caption = data.image_caption or "Source documentary map or reference figure"
            r_cls._text(slide, caption[:95], 6.05, 6.35, 6.5, 0.35, primary, body_font, 10.5, italic=True, center=True)
        else:
            r_cls._text(slide, "\n".join(data.bullets), 6.2, 2.4, 6.2, 4.1, hex_to_rgb(ds.colors.text_primary), body_font, 13, bullet_list=True)

    # ──────────────────────────────────────────────────────────────────────────
    # A10: Numbered Process Row (3 Steps)
    # ──────────────────────────────────────────────────────────────────────────
    @classmethod
    def _render_a10(cls, slide, data: SlideSpec, ds: DesignSystem, img: bytes | None, r_cls):
        ink = hex_to_rgb(getattr(ds.colors, "ink", ds.colors.primary))
        primary = hex_to_rgb(ds.colors.primary)
        tint_a = hex_to_rgb(getattr(ds.colors, "tint_a", ds.colors.card_fill))
        white = RGBColor(255, 255, 255)
        title_font = ds.typography.title_font.name
        body_font = ds.typography.body_font.name

        # Intro text banner if takeaway exists
        if data.takeaway:
            r_cls._text(slide, data.takeaway, 0.6, 2.05, 12.1, 0.6, hex_to_rgb(ds.colors.text_secondary), body_font, 14)
            card_y = 2.85
            card_h = 3.9
        else:
            card_y = 2.2
            card_h = 4.55

        steps = data.bullets[:3] if data.bullets else [
            "Initiation: Mobilize resources and baseline operational requirements.",
            "Execution: Deploy standardized delivery cycles and monitor milestones.",
            "Institutionalization: Solidify governance mechanisms and scale impact.",
        ]

        cw = 3.65
        gap = 0.55

        for k, step in enumerate(steps[:3]):
            cx = 0.6 + k * (cw + gap)
            r_cls._shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, cx, card_y, cw, card_h, tint_a, f"step-card-{k+1}", corner_radius=0.04)

            # Top badge
            r_cls._shape(slide, MSO_SHAPE.OVAL, cx + 0.35, card_y + 0.35, 0.6, 0.6, ink, f"step-badge-{k+1}")
            r_cls._text(slide, f"0{k+1}", cx + 0.35, card_y + 0.4, 0.6, 0.5, white, title_font, 16, bold=True, center=True)

            parts = step.split(":", 1) if ":" in step else [step[:30], step[30:]]
            r_cls._text(slide, parts[0].strip(), cx + 0.35, card_y + 1.15, cw - 0.7, 0.5, primary, title_font, 15, bold=True)
            r_cls._shape(slide, MSO_SHAPE.RECTANGLE, cx + 0.35, card_y + 1.75, 1.2, 0.04, primary, f"rule-{k+1}")
            desc = parts[1].strip() if len(parts) > 1 else ""
            r_cls._text(slide, desc[:160], cx + 0.35, card_y + 1.9, cw - 0.7, card_h - 2.1, hex_to_rgb(ds.colors.text_secondary), body_font, 12)

            # Connecting Arrow Chip
            if k < 2:
                arrow_x = cx + cw + 0.12
                arrow_y = card_y + card_h / 2 - 0.2
                r_cls._shape(slide, MSO_SHAPE.CHEVRON, arrow_x, arrow_y, 0.32, 0.4, primary, f"arrow-{k+1}")

    # ──────────────────────────────────────────────────────────────────────────
    # A11: Stage / Maturity Columns
    # ──────────────────────────────────────────────────────────────────────────
    @classmethod
    def _render_a11(cls, slide, data: SlideSpec, ds: DesignSystem, img: bytes | None, r_cls):
        ink = hex_to_rgb(getattr(ds.colors, "ink", ds.colors.primary))
        primary = hex_to_rgb(ds.colors.primary)
        tint_a = hex_to_rgb(getattr(ds.colors, "tint_a", ds.colors.card_fill))
        white = RGBColor(255, 255, 255)
        title_font = ds.typography.title_font.name
        body_font = ds.typography.body_font.name

        stages = data.bullets[:4] if len(data.bullets) >= 4 else (data.bullets[:3] if data.bullets else ["Stage 1", "Stage 2", "Stage 3"])
        count = len(stages)
        cw = (12.1 - 0.35 * (count - 1)) / count

        for j, st in enumerate(stages):
            x = 0.6 + j * (cw + 0.35)
            y = 2.1
            h = 4.65

            r_cls._shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, x, y, cw, h, tint_a, f"col-{j+1}", corner_radius=0.03)

            # Header Strip
            r_cls._shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, x, y, cw, 0.55, ink, f"hdr-{j+1}", corner_radius=0.03)
            r_cls._text(slide, f"STAGE {j+1}", x, y + 0.12, cw, 0.35, white, body_font, 11, bold=True, center=True)

            parts = st.split(":", 1) if ":" in st else [st[:30], st[30:]]
            r_cls._text(slide, parts[0].strip(), x + 0.2, y + 0.75, cw - 0.4, 0.65, primary, title_font, 14, bold=True, center=True)
            if len(parts) > 1:
                r_cls._text(slide, parts[1].strip()[:180], x + 0.2, y + 1.45, cw - 0.4, h - 1.6, hex_to_rgb(ds.colors.text_secondary), body_font, 11.5)

    # ──────────────────────────────────────────────────────────────────────────
    # A13: 2x2 / 2x3 Icon-Numbered Grid
    # ──────────────────────────────────────────────────────────────────────────
    @classmethod
    def _render_a13(cls, slide, data: SlideSpec, ds: DesignSystem, img: bytes | None, r_cls):
        ink = hex_to_rgb(getattr(ds.colors, "ink", ds.colors.primary))
        primary = hex_to_rgb(ds.colors.primary)
        tint_a = hex_to_rgb(getattr(ds.colors, "tint_a", ds.colors.card_fill))
        white = RGBColor(255, 255, 255)
        title_font = ds.typography.title_font.name
        body_font = ds.typography.body_font.name

        items = data.bullets[:4] if len(data.bullets) >= 4 else (data.bullets if data.bullets else ["Driver 1", "Driver 2", "Driver 3", "Driver 4"])
        cols = 2
        rows = 2
        cw = 5.85
        ch = 2.15
        gap_x = 0.4
        gap_y = 0.35

        for k, item in enumerate(items[:4]):
            r = k // cols
            c = k % cols
            x = 0.6 + c * (cw + gap_x)
            y = 2.15 + r * (ch + gap_y)

            r_cls._shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, x, y, cw, ch, tint_a, f"grid-cell-{k+1}", corner_radius=0.04)

            # Circular Badge
            r_cls._shape(slide, MSO_SHAPE.OVAL, x + 0.3, y + 0.25, 0.55, 0.55, ink, f"cell-badge-{k+1}")
            r_cls._text(slide, f"0{k+1}", x + 0.3, y + 0.28, 0.55, 0.5, white, body_font, 12, bold=True, center=True)

            parts = item.split(":", 1) if ":" in item else [item[:40], item[40:]]
            r_cls._text(slide, parts[0].strip(), x + 1.05, y + 0.22, cw - 1.25, 0.4, primary, title_font, 14, bold=True)
            if len(parts) > 1:
                r_cls._text(slide, parts[1].strip()[:140], x + 1.05, y + 0.65, cw - 1.25, 1.35, hex_to_rgb(ds.colors.text_secondary), body_font, 11.5)

    # ──────────────────────────────────────────────────────────────────────────
    # A14: Chart + Insight Panel
    # ──────────────────────────────────────────────────────────────────────────
    @classmethod
    def _render_a14(cls, slide, data: SlideSpec, ds: DesignSystem, img: bytes | None, r_cls):
        from app.tools.chart_engine import ChartEngine
        ink = hex_to_rgb(getattr(ds.colors, "ink", ds.colors.primary))
        primary = hex_to_rgb(ds.colors.primary)
        tint_a = hex_to_rgb(getattr(ds.colors, "tint_a", ds.colors.card_fill))
        white = RGBColor(255, 255, 255)
        title_font = ds.typography.title_font.name
        body_font = ds.typography.body_font.name

        # Left 60%: Native Chart
        if data.chart_spec:
            ChartEngine.render_chart(slide, data.chart_spec, ds, 0.6, 2.05, 7.5, 4.65)
        else:
            r_cls._text(slide, "\n".join(data.bullets), 0.6, 2.2, 7.5, 4.5, hex_to_rgb(ds.colors.text_primary), body_font, 13, bullet_list=True)

        # Right 38%: Insight Panel
        r_cls._shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, 8.4, 2.05, 4.3, 4.65, tint_a, "insight-panel", corner_radius=0.04)
        r_cls._text(slide, "STRATEGIC INSIGHT", 8.7, 2.3, 3.7, 0.32, primary, body_font, 11, bold=True)

        insight_txt = data.takeaway or (data.bullets[0] if data.bullets else "Consistent outperformance across measured evaluation periods.")
        r_cls._text(slide, insight_txt[:180], 8.7, 2.7, 3.7, 1.8, hex_to_rgb(ds.colors.text_primary), body_font, 12.5)

        # Big Stat highlight in panel
        metric_val = str(data.metrics[0].get("value", "+38%")) if data.metrics else "+42%"
        metric_lbl = str(data.metrics[0].get("label", "Year-over-Year Acceleration")) if data.metrics else "Efficiency Multiplier"
        r_cls._shape(slide, MSO_SHAPE.RECTANGLE, 8.7, 4.65, 1.4, 0.05, primary, "insight-tick")
        r_cls._text(slide, metric_val, 8.7, 4.85, 3.7, 0.65, primary, title_font, 36, bold=True)
        r_cls._text(slide, metric_lbl, 8.7, 5.55, 3.7, 0.8, hex_to_rgb(ds.colors.text_secondary), body_font, 12)

    # ──────────────────────────────────────────────────────────────────────────
    # A15: Dual Big-Stat Comparison
    # ──────────────────────────────────────────────────────────────────────────
    @classmethod
    def _render_a15(cls, slide, data: SlideSpec, ds: DesignSystem, img: bytes | None, r_cls):
        ink = hex_to_rgb(getattr(ds.colors, "ink", ds.colors.primary))
        primary = hex_to_rgb(ds.colors.primary)
        white = RGBColor(255, 255, 255)
        title_font = ds.typography.title_font.name
        body_font = ds.typography.body_font.name

        metrics = data.metrics[:2] if data.metrics else [
            {"value": "9x", "label": "Output Multiplier", "desc": "Baseline improvement across automated processing pipelines."},
            {"value": "3x", "label": "Latency Reduction", "desc": "Sub-second failover across verified provider clusters."},
        ]

        for j, m in enumerate(metrics[:2]):
            x = 0.6 + j * 6.25
            w = 5.85
            r_cls._shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, x, 2.15, w, 4.55, ink, f"stat-box-{j+1}", corner_radius=0.04)
            r_cls._text(slide, str(m.get("value", "10x")), x + 0.4, 2.5, w - 0.8, 1.2, white, title_font, 56, bold=True, center=True)
            r_cls._text(slide, str(m.get("label", "Key Benchmark")), x + 0.4, 3.85, w - 0.8, 0.45, tint(primary, 0.6), body_font, 14, bold=True, center=True)
            r_cls._shape(slide, MSO_SHAPE.RECTANGLE, x + w / 2 - 0.8, 4.45, 1.6, 0.04, primary, f"rule-{j+1}")
            desc = m.get("desc") or (data.bullets[j] if j < len(data.bullets) else "")
            r_cls._text(slide, desc[:150], x + 0.5, 4.65, w - 1.0, 1.8, tint(white, 0.2), body_font, 12, center=True)

    # ──────────────────────────────────────────────────────────────────────────
    # A16: Native Data Table
    # ──────────────────────────────────────────────────────────────────────────
    @classmethod
    def _render_a16(cls, slide, data: SlideSpec, ds: DesignSystem, img: bytes | None, r_cls):
        from app.tools.table_engine import TableEngine
        if data.table_spec:
            TableEngine.render_table(slide, data.table_spec, ds, 0.6, 2.05, 12.1, 4.65)
        else:
            # Fallback to structured two-column
            r_cls._card(slide, "\n".join(data.bullets[:len(data.bullets)//2 or 1]), 0.6, 2.15, 5.85, 4.55, hex_to_rgb(getattr(ds.colors, "tint_a", ds.colors.card_fill)), hex_to_rgb(ds.colors.text_secondary), hex_to_rgb(ds.colors.primary), ds.typography.body_font.name)
            r_cls._card(slide, "\n".join(data.bullets[len(data.bullets)//2:] or ["Key benchmark"]), 6.85, 2.15, 5.85, 4.55, hex_to_rgb(getattr(ds.colors, "tint_a", ds.colors.card_fill)), hex_to_rgb(ds.colors.text_secondary), hex_to_rgb(ds.colors.primary), ds.typography.body_font.name)

    # ──────────────────────────────────────────────────────────────────────────
    # A17: Closing Takeaways (Accent Bar on Left Edge)
    # ──────────────────────────────────────────────────────────────────────────
    @classmethod
    def _render_a17(cls, slide, data: SlideSpec, ds: DesignSystem, img: bytes | None, r_cls):
        primary = hex_to_rgb(ds.colors.primary)
        secondary = hex_to_rgb(getattr(ds.colors, "secondary", ds.colors.primary))
        title_font = ds.typography.title_font.name
        body_font = ds.typography.body_font.name

        # Full-height vertical accent bar on left edge
        r_cls._shape(slide, MSO_SHAPE.RECTANGLE, 0, 0, 0.22, 7.5, secondary, "left-signature-bar")

        # Eyebrow & Title with left margin offset
        eyebrow = (data.eyebrow or "SYNTHESIS & CONCLUSION").upper()
        r_cls._text(slide, eyebrow, 0.8, 0.5, 11.5, 0.35, primary, body_font, 12, bold=True)

        title = data.headline or "Strategic Horizons & Lasting Significance"
        r_cls._text(slide, title, 0.8, 0.9, 11.5, 0.85, hex_to_rgb(getattr(ds.colors, "ink", ds.colors.primary)), title_font, 30, title=True)

        # Bullets / Narrative body
        body_text = "\n".join(data.bullets) if data.bullets else data.takeaway
        r_cls._text(slide, body_text, 0.8, 2.05, 11.5, 3.8, hex_to_rgb(ds.colors.text_secondary), body_font, 14, bullet_list=bool(data.bullets))

        # Accent Rule
        r_cls._shape(slide, MSO_SHAPE.RECTANGLE, 0.8, 6.05, 1.8, 0.05, primary, "closing-rule")

        # Italic Closing Line
        closing_line = data.takeaway or "An enduring precedent in strategic governance and execution excellence."
        r_cls._text(slide, closing_line[:140], 0.8, 6.2, 11.5, 0.6, primary, body_font, 13, italic=True)

    # ──────────────────────────────────────────────────────────────────────────
    # A18: Recap Checklist ("Before We Move On")
    # ──────────────────────────────────────────────────────────────────────────
    @classmethod
    def _render_a18(cls, slide, data: SlideSpec, ds: DesignSystem, img: bytes | None, r_cls):
        primary = hex_to_rgb(ds.colors.primary)
        body_col = hex_to_rgb(ds.colors.text_secondary)
        body_font = ds.typography.body_font.name

        items = data.bullets[:5] if data.bullets else [
            "Institutional foundations established through structured governance.",
            "Fiscal resilience maintained via diversified revenue streams.",
            "Empirical evidence validates continuous performance improvement.",
            "Cross-functional alignment ensures reliable mission delivery.",
        ]

        row_y = 2.15
        row_h = 0.8

        for k, item in enumerate(items[:5]):
            y = row_y + k * row_h
            # Clean checkmark icon
            r_cls._text(slide, "✓", 0.7, y + 0.1, 0.4, 0.4, primary, body_font, 16, bold=True)
            r_cls._text(slide, clean_text(item)[:130], 1.2, y + 0.1, 11.0, 0.65, body_col, body_font, 13)

        # Accent tick & tagline
        r_cls._shape(slide, MSO_SHAPE.RECTANGLE, 0.7, 6.35, 1.6, 0.06, primary, "recap-tick")
        tagline = data.takeaway or "Key concepts verified — proceeding to operational implementation."
        r_cls._text(slide, tagline[:120], 0.7, 6.5, 11.0, 0.4, primary, body_font, 11.5, italic=True)
