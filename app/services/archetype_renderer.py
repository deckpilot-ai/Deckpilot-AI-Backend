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
    # A1: Title Cover - Short Main Title + Subtitle Below + High Contrast
    # ──────────────────────────────────────────────────────────────────────────
    @classmethod
    def _render_a1(cls, slide, data: SlideSpec, ds: DesignSystem, img: bytes | None, r_cls):
        ink = hex_to_rgb(getattr(ds.colors, "ink", ds.colors.primary))
        primary = hex_to_rgb(ds.colors.primary)
        accent = hex_to_rgb(getattr(ds.colors, "accent", ds.colors.primary))
        white = RGBColor(255, 255, 255)
        title_font = ds.typography.title_font.name
        body_font = ds.typography.body_font.name

        # 1. Dark ink solid background
        slide.background.fill.solid()
        slide.background.fill.fore_color.rgb = ink

        # 2. Extract clean short main title & subtitle below
        raw_title = clean_text(data.headline or data.key_message or "Presentation Title")
        raw_subtitle = clean_text(data.takeaway or data.subtitle or "")

        if ":" in raw_title and len(raw_title) > 16:
            parts = raw_title.split(":", 1)
            main_title = parts[0].strip()
            sub_cand = parts[1].strip()
            if not raw_subtitle:
                raw_subtitle = sub_cand
            elif sub_cand.lower() not in raw_subtitle.lower():
                raw_subtitle = f"{sub_cand} — {raw_subtitle}"
        elif len(raw_title.split()) > 5 and not raw_subtitle:
            words = raw_title.split()
            main_title = " ".join(words[:4])
            raw_subtitle = " ".join(words[4:])
        else:
            main_title = raw_title

        # 3. Signature decorative organic circles (matches Expected PPT benchmark)
        r_cls._shape(slide, MSO_SHAPE.OVAL, 9.60, -2.20, 6.50, 6.50, tint(ink, 0.12), "accent-circle-tr")
        r_cls._shape(slide, MSO_SHAPE.OVAL, 11.00, 3.60, 5.20, 5.20, tint(ink, 0.10), "accent-circle-mr")
        r_cls._shape(slide, MSO_SHAPE.OVAL, -1.60, 4.60, 4.40, 4.40, tint(ink, 0.10), "accent-circle-bl")

        # 4. Eyebrow (Saffron/Gold accent color, tracked uppercase)
        eyebrow = (data.eyebrow or "CURATED EDUCATIONAL & STRATEGIC BRIEFING").upper()
        r_cls._text(slide, eyebrow, 0.75, 1.30, 11.5, 0.35, accent, body_font, 13, bold=True)

        # 5. Main Title (Short words, 50-56pt Cambria, Pure Crisp White)
        title_size = 54 if len(main_title) < 28 else (46 if len(main_title) < 45 else 38)
        r_cls._text(slide, main_title, 0.70, 1.75, 11.5, 1.60, white, title_font, title_size, title=True)

        # 6. Accent Tick (1.6" wide in accent color)
        r_cls._shape(slide, MSO_SHAPE.RECTANGLE, 0.75, 3.45, 1.6, 0.06, accent, "title-accent-tick")

        # 7. Subtitle (Directly below title, crisp high-contrast light tone, 17-19pt Calibri)
        if raw_subtitle:
            sub_col = tint(white, 0.12)  # Soft high-contrast light tone (#E2EEEC / #F0E4DA)
            r_cls._text(slide, raw_subtitle, 0.75, 3.68, 11.2, 0.95, sub_col, body_font, 18)

        # 8. Topic Badges / Category Pills (Dark glass pill background, pure white bold text)
        pills = data.bullets[:4] if data.bullets else ["Strategic Foundations", "Operational Delivery", "Institutional Impact"]
        pill_y = 4.88
        px = 0.75
        for p in pills:
            label = clean_text(p).split(":")[0].strip()[:35]
            pw = max(2.0, min(3.6, len(label) * 0.11 + 0.6))
            r_cls._shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, px, pill_y, pw, 0.45, tint(ink, 0.28), "topic-pill", corner_radius=0.25)
            r_cls._text(slide, label, px, pill_y + 0.05, pw, 0.35, white, body_font, 11.5, bold=True, center=True)
            px += pw + 0.25

        # 9. Footer category note
        footer_note = "Executive Advisory & Comprehensive Research Presentation"
        if data.speaker_notes and ":" in data.speaker_notes:
            footer_note = data.speaker_notes.split(":")[0].strip()[:65]
        r_cls._text(slide, footer_note, 0.75, 6.35, 9.5, 0.35, tint(white, 0.38), body_font, 12)

    # ──────────────────────────────────────────────────────────────────────────
    # A2: Title Cover - Split Panel
    # ──────────────────────────────────────────────────────────────────────────
    @classmethod
    def _render_a2(cls, slide, data: SlideSpec, ds: DesignSystem, img: bytes | None, r_cls):
        ink = hex_to_rgb(getattr(ds.colors, "ink", ds.colors.primary))
        primary = hex_to_rgb(ds.colors.primary)
        accent = hex_to_rgb(getattr(ds.colors, "accent", ds.colors.primary))
        tint_a = hex_to_rgb(getattr(ds.colors, "tint_a", ds.colors.card_fill))
        white = RGBColor(255, 255, 255)
        title_font = ds.typography.title_font.name
        body_font = ds.typography.body_font.name

        # Solid ink background
        slide.background.fill.solid()
        slide.background.fill.fore_color.rgb = ink

        # Title & subtitle parsing
        raw_title = clean_text(data.headline or data.key_message or "Executive Briefing")
        raw_subtitle = clean_text(data.takeaway or (data.bullets[0] if data.bullets else ""))

        if ":" in raw_title and len(raw_title) > 16:
            parts = raw_title.split(":", 1)
            main_title = parts[0].strip()
            sub_cand = parts[1].strip()
            if not raw_subtitle:
                raw_subtitle = sub_cand
            elif sub_cand.lower() not in raw_subtitle.lower():
                raw_subtitle = f"{sub_cand} — {raw_subtitle}"
        elif len(raw_title.split()) > 5 and not raw_subtitle:
            words = raw_title.split()
            main_title = " ".join(words[:4])
            raw_subtitle = " ".join(words[4:])
        else:
            main_title = raw_title

        # Signature decorative background circles (matches Expected PPT benchmark)
        r_cls._shape(slide, MSO_SHAPE.OVAL, -0.90, -0.90, 2.60, 2.60, tint(ink, 0.14), "accent-circle-tl")
        r_cls._shape(slide, MSO_SHAPE.OVAL, 0.20, 5.90, 1.70, 1.70, tint(ink, 0.12), "accent-circle-bl")

        # Left 55%: text narrative
        eyebrow = (data.eyebrow or "CASE STUDY & ANALYSIS").upper()
        r_cls._text(slide, eyebrow, 0.70, 1.30, 6.6, 0.35, accent, body_font, 13, bold=True)

        title_size = 48 if len(main_title) < 28 else 40
        r_cls._text(slide, main_title, 0.65, 1.75, 6.6, 1.8, white, title_font, title_size, title=True)

        # 1.6" Accent Tick
        r_cls._shape(slide, MSO_SHAPE.RECTANGLE, 0.70, 3.65, 1.6, 0.06, accent, "accent-tick")

        if raw_subtitle:
            sub_col = tint(white, 0.12)
            r_cls._text(slide, raw_subtitle, 0.70, 3.88, 6.5, 1.5, sub_col, body_font, 16.5)

        r_cls._text(slide, "COMPREHENSIVE RESEARCH EVALUATION", 0.70, 6.30, 6.5, 0.35, tint(white, 0.38), body_font, 11, bold=True)

        # Right 45%: Framed Hero Photo with Mat in Ink Block
        r_cls._shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, 7.6, 1.1, 5.15, 5.2, tint(ink, 0.25), "photo-container", corner_radius=0.03)
        if img:
            r_cls._shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, 7.85, 1.25, 4.65, 4.2, tint_a, "photo-mat", corner_radius=0.02)
            r_cls._render_picture(slide, img, 7.95, 1.35, 4.45, 4.0)
            caption = data.image_caption or "Documentary reference figure"
            r_cls._text(slide, caption[:80], 7.85, 5.65, 4.65, 0.45, white, body_font, 10, italic=True, center=True)
        else:
            r_cls._shape(slide, MSO_SHAPE.OVAL, 9.6, 2.3, 1.2, 1.2, accent, "center-badge")
            r_cls._text(slide, "★", 9.6, 2.3, 1.2, 1.2, white, body_font, 30, center=True)
            r_cls._text(slide, "Strategic Focus", 8.0, 3.8, 4.35, 0.8, white, title_font, 22, bold=True, center=True)

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

            parts = step.split(":", 1) if ":" in step else [step]
            heading_h = 0.75 if len(parts) > 1 else 1.8
            heading_size = 15 if len(parts) > 1 else 16
            r_cls._text(
                slide,
                parts[0].strip(),
                cx + 0.35,
                card_y + 1.15,
                cw - 0.7,
                heading_h,
                primary,
                title_font,
                heading_size,
                bold=len(parts) > 1,
                center=True,
            )
            r_cls._shape(slide, MSO_SHAPE.RECTANGLE, cx + 0.35, card_y + 1.75, 1.2, 0.04, primary, f"rule-{k+1}")
            if len(parts) > 1:
                desc = parts[1].strip()
                r_cls._text(slide, desc[:160], cx + 0.35, card_y + 1.9, cw - 0.7, card_h - 2.1, hex_to_rgb(ds.colors.text_secondary), body_font, 15, center=True)

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

    # ──────────────────────────────────────────────────────────────────────────
    # A24: Chronology / Horizontal Timeline Band
    # ──────────────────────────────────────────────────────────────────────────
    @classmethod
    def _render_a24(cls, slide, data: SlideSpec, ds: DesignSystem, img: bytes | None, r_cls):
        ink = hex_to_rgb(getattr(ds.colors, "ink", ds.colors.primary))
        primary = hex_to_rgb(ds.colors.primary)
        accent = hex_to_rgb(getattr(ds.colors, "accent", ds.colors.primary))
        tint_a = hex_to_rgb(getattr(ds.colors, "tint_a", ds.colors.card_fill))
        tint_b = hex_to_rgb(getattr(ds.colors, "tint_b", ds.colors.neutral))
        white = RGBColor(255, 255, 255)
        title_font = ds.typography.title_font.name
        body_font = ds.typography.body_font.name

        # Optional intro / era summary banner
        card_y = 2.45
        card_h = 4.25
        if data.takeaway:
            r_cls._text(slide, clean_text(data.takeaway)[:150], 0.6, 1.95, 12.1, 0.45, hex_to_rgb(ds.colors.text_secondary), body_font, 13)
            card_y = 2.55
            card_h = 4.15

        milestones = data.bullets[:5] if len(data.bullets) >= 4 else (data.bullets if data.bullets else [
            "1630: Foundation & Early Sovereignty",
            "1657: Naval Power & Coastal Fortresses",
            "1674: Grand Coronation & State Consolidation",
            "1707: Pan-Indian Expansion & Peshwa Era",
        ])
        count = max(1, len(milestones))
        cw = (12.1 - 0.28 * (count - 1)) / count

        # Continuous Horizontal Connecting Bar
        r_cls._shape(slide, MSO_SHAPE.RECTANGLE, 0.6, card_y + 0.35, 12.1, 0.06, primary, "timeline-connector-bar")

        for k, m in enumerate(milestones):
            cx = 0.6 + k * (cw + 0.28)
            # Alternate card tints
            bg_col = tint_a if k % 2 == 0 else tint_b
            r_cls._shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, cx, card_y, cw, card_h, bg_col, f"timeline-card-{k+1}", corner_radius=0.04)

            # Parse year / era & description
            if ":" in m:
                parts = m.split(":", 1)
                year_tag = parts[0].strip()
                desc_text = parts[1].strip()
            elif " - " in m:
                parts = m.split(" - ", 1)
                year_tag = parts[0].strip()
                desc_text = parts[1].strip()
            else:
                words = m.split()
                year_tag = words[0] if words else f"Phase {k+1}"
                desc_text = " ".join(words[1:]) if len(words) > 1 else m

            # Top Milestone Year Pill
            pill_w = min(cw - 0.4, max(1.2, len(year_tag) * 0.12 + 0.4))
            pill_x = cx + (cw - pill_w) / 2
            r_cls._shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, pill_x, card_y + 0.15, pill_w, 0.46, ink, f"year-pill-{k+1}", corner_radius=0.2)
            r_cls._text(slide, year_tag[:18], pill_x, card_y + 0.18, pill_w, 0.38, white, title_font, 12, bold=True, center=True)

            # Headline & Event narrative
            if " · " in desc_text:
                dparts = desc_text.split(" · ", 1)
                event_title = dparts[0].strip()
                event_body = dparts[1].strip()
            elif ":" in desc_text:
                dparts = desc_text.split(":", 1)
                event_title = dparts[0].strip()
                event_body = dparts[1].strip()
            else:
                event_title = desc_text[:40]
                event_body = desc_text[40:].strip()

            r_cls._text(slide, event_title, cx + 0.15, card_y + 0.78, cw - 0.3, 0.75, primary, title_font, 13.5, bold=True, center=True)
            r_cls._shape(slide, MSO_SHAPE.RECTANGLE, cx + (cw - 0.8) / 2, card_y + 1.6, 0.8, 0.03, accent, f"rule-{k+1}")
            if event_body:
                r_cls._text(slide, clean_text(event_body)[:160], cx + 0.15, card_y + 1.75, cw - 0.3, card_h - 1.9, hex_to_rgb(ds.colors.text_secondary), body_font, 11, center=True)

    # ──────────────────────────────────────────────────────────────────────────
    # A25: Council of Eight / 8-Feature Governance Grid
    # ──────────────────────────────────────────────────────────────────────────
    @classmethod
    def _render_a25(cls, slide, data: SlideSpec, ds: DesignSystem, img: bytes | None, r_cls):
        ink = hex_to_rgb(getattr(ds.colors, "ink", ds.colors.primary))
        primary = hex_to_rgb(ds.colors.primary)
        accent = hex_to_rgb(getattr(ds.colors, "accent", ds.colors.primary))
        tint_a = hex_to_rgb(getattr(ds.colors, "tint_a", ds.colors.card_fill))
        white = RGBColor(255, 255, 255)
        title_font = ds.typography.title_font.name
        body_font = ds.typography.body_font.name

        items = data.bullets[:8] if len(data.bullets) >= 6 else (data.bullets if data.bullets else [
            "Peshwa: Prime Minister and head of civil and military administration.",
            "Amatya: Finance Minister overseeing state treasury and accounts.",
            "Sachiv: Secretary responsible for royal correspondence and decrees.",
            "Mantri: Chronicler keeping daily court records and intelligence.",
            "Senapati: Commander-in-Chief leading military expeditions.",
            "Sumant: Foreign Minister managing diplomacy and external relations.",
            "Nyayadhish: Chief Justice administering judicial rulings.",
            "Panditrao: High Priest managing religious grants and moral welfare.",
        ])

        count = len(items)
        cols = 4 if count >= 7 else (3 if count == 6 else (2 if count <= 4 else 4))
        rows = math.ceil(count / cols)
        cw = (12.1 - 0.25 * (cols - 1)) / cols
        ch = (4.75 - 0.25 * (rows - 1)) / rows

        for k, item in enumerate(items):
            r = k // cols
            c = k % cols
            x = 0.6 + c * (cw + 0.25)
            y = 2.05 + r * (ch + 0.25)

            r_cls._shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, x, y, cw, ch, tint_a, f"council-cell-{k+1}", corner_radius=0.04)

            # Circular number disc badge
            r_cls._shape(slide, MSO_SHAPE.OVAL, x + 0.2, y + 0.2, 0.45, 0.45, primary, f"council-badge-{k+1}")
            r_cls._text(slide, f"0{k+1}", x + 0.2, y + 0.22, 0.45, 0.4, white, body_font, 10.5, bold=True, center=True)

            parts = item.split(":", 1) if ":" in item else [item[:28], item[28:]]
            role_name = parts[0].strip()
            role_desc = parts[1].strip() if len(parts) > 1 else ""

            r_cls._text(slide, role_name, x + 0.75, y + 0.18, cw - 0.85, 0.38, ink, title_font, 13, bold=True)
            if role_desc:
                r_cls._text(slide, clean_text(role_desc)[:110], x + 0.2, y + 0.68, cw - 0.4, ch - 0.75, hex_to_rgb(ds.colors.text_secondary), body_font, 10.5)

    # ──────────────────────────────────────────────────────────────────────────
    # A26: Two Highways / Dual Route Map Split
    # ──────────────────────────────────────────────────────────────────────────
    @classmethod
    def _render_a26(cls, slide, data: SlideSpec, ds: DesignSystem, img: bytes | None, r_cls):
        ink = hex_to_rgb(getattr(ds.colors, "ink", ds.colors.primary))
        primary = hex_to_rgb(ds.colors.primary)
        accent = hex_to_rgb(getattr(ds.colors, "accent", ds.colors.primary))
        tint_a = hex_to_rgb(getattr(ds.colors, "tint_a", ds.colors.card_fill))
        tint_b = hex_to_rgb(getattr(ds.colors, "tint_b", ds.colors.neutral))
        white = RGBColor(255, 255, 255)
        title_font = ds.typography.title_font.name
        body_font = ds.typography.body_font.name

        left_w = 6.2
        mid = max(1, math.ceil(len(data.bullets) / 2))
        grp1 = data.bullets[:mid] or ["Independent units pool sovereignty together to form a larger union."]
        grp2 = data.bullets[mid:] or ["A large central power divides authority between national and state tiers."]

        routes = [
            ("ROUTE 01: COMING TOGETHER", grp1, tint_a),
            ("ROUTE 02: HOLDING TOGETHER", grp2, tint_b),
        ]

        # Left 52%: 2 Stacked Route Cards
        for j, (hdr, grp, bg) in enumerate(routes):
            ry = 2.05 + j * 2.45
            rh = 2.25
            r_cls._shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, 0.6, ry, left_w, rh, bg, f"route-card-{j+1}", corner_radius=0.04)

            # Route Header Pill
            r_cls._shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, 0.85, ry + 0.18, 3.8, 0.38, primary if j == 0 else ink, f"route-pill-{j+1}", corner_radius=0.15)
            r_cls._text(slide, hdr, 0.85, ry + 0.20, 3.8, 0.32, white, body_font, 10.5, bold=True, center=True)

            body_text = "\n".join(grp[:2])
            r_cls._text(slide, clean_text(body_text)[:180], 0.85, ry + 0.68, left_w - 0.5, rh - 0.8, hex_to_rgb(ds.colors.text_primary), body_font, 11.5, bullet_list=len(grp) > 1)

        # Right 45%: Framed Photo Mat / Map Frame
        r_cls._shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, 7.1, 2.05, 5.6, 4.7, white, "map-frame", corner_radius=0.03)
        if img:
            r_cls._shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, 7.25, 2.2, 5.3, 3.9, tint_a, "photo-mat", corner_radius=0.02)
            r_cls._render_picture(slide, img, 7.35, 2.3, 5.1, 3.7)
            caption = data.image_caption or "Comparative territorial and constitutional map"
            r_cls._text(slide, clean_text(caption)[:90], 7.25, 6.25, 5.3, 0.38, primary, body_font, 10.5, italic=True, center=True)
        else:
            r_cls._shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, 7.25, 2.2, 5.3, 4.35, tint_a, "synthesis-box", corner_radius=0.03)
            r_cls._text(slide, "STRATEGIC COMPARISON", 7.55, 2.45, 4.7, 0.35, primary, body_font, 12, bold=True)
            takeaway = data.takeaway or "Constitutional balance requires continuous institutional calibration."
            r_cls._text(slide, clean_text(takeaway)[:200], 7.55, 2.95, 4.7, 3.2, hex_to_rgb(ds.colors.text_primary), title_font, 14)

    # ──────────────────────────────────────────────────────────────────────────
    # A27: Core State Quote with Emblem Disc
    # ──────────────────────────────────────────────────────────────────────────
    @classmethod
    def _render_a27(cls, slide, data: SlideSpec, ds: DesignSystem, img: bytes | None, r_cls):
        ink = hex_to_rgb(getattr(ds.colors, "ink", ds.colors.primary))
        primary = hex_to_rgb(ds.colors.primary)
        accent = hex_to_rgb(getattr(ds.colors, "accent", ds.colors.primary))
        tint_a = hex_to_rgb(getattr(ds.colors, "tint_a", ds.colors.card_fill))
        white = RGBColor(255, 255, 255)
        title_font = ds.typography.title_font.name
        body_font = ds.typography.body_font.name

        # Left 50%: Structured Operational Bullet Cards
        pillars = data.bullets[:3] if data.bullets else [
            "Strategic Strongholds: Forts served as permanent military garrisons and treasury centers.",
            "Territorial Defence: Rugged hill geography neutralized overwhelming enemy numbers.",
            "Administrative Hubs: Local revenue, justice, and governance radiated from the fortress.",
        ]
        left_w = 5.8
        card_h = (4.75 - 0.2 * (len(pillars) - 1)) / max(1, len(pillars))

        for k, p in enumerate(pillars):
            py = 2.05 + k * (card_h + 0.2)
            r_cls._shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, 0.6, py, left_w, card_h, tint_a, f"pillar-card-{k+1}", corner_radius=0.04)
            r_cls._shape(slide, MSO_SHAPE.OVAL, 0.85, py + 0.2, 0.45, 0.45, primary, f"pillar-disc-{k+1}")
            r_cls._text(slide, f"0{k+1}", 0.85, py + 0.22, 0.45, 0.4, white, body_font, 11, bold=True, center=True)

            pparts = p.split(":", 1) if ":" in p else [p[:32], p[32:]]
            r_cls._text(slide, pparts[0].strip(), 1.45, py + 0.18, left_w - 1.6, 0.38, ink, title_font, 13.5, bold=True)
            if len(pparts) > 1:
                r_cls._text(slide, clean_text(pparts[1].strip())[:140], 1.45, py + 0.58, left_w - 1.6, card_h - 0.7, hex_to_rgb(ds.colors.text_secondary), body_font, 11)

        # Right 46%: Tinted Quote Card with Emblem Disc
        qw = 6.05
        qx = 6.65
        r_cls._shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, qx, 2.05, qw, 4.75, ink, "quote-hero-card", corner_radius=0.04)

        # Center top star / emblem disc
        disc_x = qx + (qw - 1.1) / 2
        r_cls._shape(slide, MSO_SHAPE.OVAL, disc_x, 2.35, 1.1, 1.1, accent, "quote-emblem-disc")
        r_cls._text(slide, "★", disc_x, 2.35, 1.1, 1.1, white, body_font, 26, bold=True, center=True)

        quote_txt = (
            data.takeaway or
            "Forts are the core of the state. What is a kingdom without forts? It is like a house without walls, exposed to every storm."
        )
        r_cls._text(slide, f'"{clean_text(quote_txt)}"', qx + 0.5, 3.65, qw - 1.0, 2.0, white, title_font, 16, italic=True, center=True)

        # Author / Provenance line
        r_cls._shape(slide, MSO_SHAPE.RECTANGLE, qx + (qw - 1.8) / 2, 5.75, 1.8, 0.04, accent, "author-tick")
        author_txt = "Historical Doctrine & Strategic Precedent"
        if data.speaker_notes and ":" in data.speaker_notes:
            author_txt = data.speaker_notes.split(":")[0].strip()[:50]
        r_cls._text(slide, author_txt, qx + 0.5, 5.95, qw - 1.0, 0.45, tint(white, 0.35), body_font, 11, bold=True, center=True)

    # ──────────────────────────────────────────────────────────────────────────
    # A28: Concept Definition Card with Photo Mat
    # ──────────────────────────────────────────────────────────────────────────
    @classmethod
    def _render_a28(cls, slide, data: SlideSpec, ds: DesignSystem, img: bytes | None, r_cls):
        ink = hex_to_rgb(getattr(ds.colors, "ink", ds.colors.primary))
        primary = hex_to_rgb(ds.colors.primary)
        accent = hex_to_rgb(getattr(ds.colors, "accent", ds.colors.primary))
        tint_a = hex_to_rgb(getattr(ds.colors, "tint_a", ds.colors.card_fill))
        white = RGBColor(255, 255, 255)
        title_font = ds.typography.title_font.name
        body_font = ds.typography.body_font.name

        left_w = 6.2
        # Top Definition in Ink
        r_cls._shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, 0.6, 2.05, left_w, 2.3, ink, "def-top-card", corner_radius=0.04)
        r_cls._shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, 0.85, 2.25, 2.2, 0.34, accent, "concept-pill", corner_radius=0.15)
        r_cls._text(slide, "KEY CONCEPT", 0.85, 2.27, 2.2, 0.28, white, body_font, 10, bold=True, center=True)

        def_text = data.takeaway or (data.bullets[0] if data.bullets else "Core structural definition of the institutional framework.")
        r_cls._text(slide, clean_text(def_text)[:220], 0.85, 2.7, left_w - 0.5, 1.45, white, title_font, 15)

        # Bottom 2 Characteristic Cards in Tint
        attr_bullets = data.bullets[1:3] if len(data.bullets) > 2 else (data.bullets[:2] if data.bullets else ["Institutional Scope", "Operational Delivery"])
        for j, attr in enumerate(attr_bullets[:2]):
            ay = 4.5 + j * 1.15
            r_cls._shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, 0.6, ay, left_w, 1.05, tint_a, f"attr-row-{j+1}", corner_radius=0.04)
            r_cls._shape(slide, MSO_SHAPE.OVAL, 0.85, ay + 0.15, 0.35, 0.35, primary, f"attr-disc-{j+1}")
            r_cls._text(slide, str(j + 1), 0.85, ay + 0.16, 0.35, 0.32, white, body_font, 10, bold=True, center=True)
            aparts = attr.split(":", 1) if ":" in attr else [attr[:35], attr[35:]]
            r_cls._text(slide, aparts[0].strip(), 1.35, ay + 0.12, left_w - 1.5, 0.35, primary, title_font, 13, bold=True)
            if len(aparts) > 1:
                r_cls._text(slide, clean_text(aparts[1].strip())[:110], 1.35, ay + 0.48, left_w - 1.5, 0.5, hex_to_rgb(ds.colors.text_secondary), body_font, 11)

        # Right 45%: Framed Photo Mat
        r_cls._shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, 7.1, 2.05, 5.6, 4.7, white, "artifact-frame", corner_radius=0.03)
        if img:
            r_cls._shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, 7.25, 2.2, 5.3, 3.9, tint_a, "photo-mat", corner_radius=0.02)
            r_cls._render_picture(slide, img, 7.35, 2.3, 5.1, 3.7)
            caption = data.image_caption or "Documentary reference artifact"
            r_cls._text(slide, clean_text(caption)[:90], 7.25, 6.25, 5.3, 0.38, primary, body_font, 10.5, italic=True, center=True)
        else:
            r_cls._shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, 7.25, 2.2, 5.3, 4.35, tint_a, "narrative-fill", corner_radius=0.03)
            r_cls._text(slide, "FRAMEWORK HIGHLIGHTS", 7.55, 2.45, 4.7, 0.35, primary, body_font, 12, bold=True)
            r_cls._text(slide, "\n".join(data.bullets), 7.55, 2.95, 4.7, 3.2, hex_to_rgb(ds.colors.text_primary), body_font, 12.5, bullet_list=True)

    # ──────────────────────────────────────────────────────────────────────────
    # A29: The Big Questions (4 Hero Numbered Cards)
    # ──────────────────────────────────────────────────────────────────────────
    @classmethod
    def _render_a29(cls, slide, data: SlideSpec, ds: DesignSystem, img: bytes | None, r_cls):
        ink = hex_to_rgb(getattr(ds.colors, "ink", ds.colors.primary))
        primary = hex_to_rgb(ds.colors.primary)
        accent = hex_to_rgb(getattr(ds.colors, "accent", ds.colors.primary))
        tint_a = hex_to_rgb(getattr(ds.colors, "tint_a", ds.colors.card_fill))
        white = RGBColor(255, 255, 255)
        title_font = ds.typography.title_font.name
        body_font = ds.typography.body_font.name

        questions = data.bullets[:4] if len(data.bullets) >= 4 else (data.bullets if data.bullets else [
            "Who were the key actors and what drove their mobilization?",
            "What administrative institutions enabled durable statecraft?",
            "How did fiscal and military policies sustain expansion?",
            "What enduring legacy shaped subsequent constitutional design?",
        ])
        count = max(1, len(questions))
        cw = (12.1 - 0.3 * (count - 1)) / count
        card_h = 4.65
        card_y = 2.05

        for j, q in enumerate(questions):
            cx = 0.6 + j * (cw + 0.3)
            r_cls._shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, cx, card_y, cw, card_h, tint_a, f"question-card-{j+1}", corner_radius=0.04)

            # Centered Large Circular Badge
            badge_size = 1.15
            badge_x = cx + (cw - badge_size) / 2
            r_cls._shape(slide, MSO_SHAPE.OVAL, badge_x, card_y + 0.35, badge_size, badge_size, primary, f"q-badge-{j+1}")
            r_cls._text(slide, f"0{j+1}", badge_x, card_y + 0.38, badge_size, badge_size - 0.1, white, title_font, 26, bold=True, center=True)

            # Parse question title vs explanation
            if "\n" in q:
                parts = q.split("\n", 1)
            elif ":" in q:
                parts = q.split(":", 1)
            elif "?" in q:
                parts = q.split("?", 1)
                parts[0] = parts[0] + "?"
            else:
                parts = [q]

            q_title = parts[0].strip()
            q_desc = parts[1].strip() if len(parts) > 1 else ""

            r_cls._text(slide, q_title, cx + 0.2, card_y + 1.7, cw - 0.4, 1.3, primary, title_font, 15, bold=True, center=True)
            r_cls._shape(slide, MSO_SHAPE.RECTANGLE, cx + (cw - 1.2) / 2, card_y + 3.1, 1.2, 0.04, accent, f"q-rule-{j+1}")

            if q_desc:
                r_cls._text(slide, clean_text(q_desc)[:150], cx + 0.2, card_y + 3.25, cw - 0.4, card_h - 3.4, hex_to_rgb(ds.colors.text_secondary), body_font, 11.5, center=True)

    # ──────────────────────────────────────────────────────────────────────────
    # A30: Stepped Value Chain / Journey of Goods Flow
    # ──────────────────────────────────────────────────────────────────────────
    @classmethod
    def _render_a30(cls, slide, data: SlideSpec, ds: DesignSystem, img: bytes | None, r_cls):
        ink = hex_to_rgb(getattr(ds.colors, "ink", ds.colors.primary))
        primary = hex_to_rgb(ds.colors.primary)
        accent = hex_to_rgb(getattr(ds.colors, "accent", ds.colors.primary))
        tint_a = hex_to_rgb(getattr(ds.colors, "tint_a", ds.colors.card_fill))
        tint_b = hex_to_rgb(getattr(ds.colors, "tint_b", ds.colors.neutral))
        white = RGBColor(255, 255, 255)
        title_font = ds.typography.title_font.name
        body_font = ds.typography.body_font.name

        steps = data.bullets[:5] if len(data.bullets) >= 4 else (data.bullets if data.bullets else [
            "Primary Production: Cultivation, harvesting, and raw commodity aggregation.",
            "Wholesale Trading: Mandi auction, bulk sorting, and regional price discovery.",
            "Processing & Value-Add: Milling, packaging, quality standard compliance.",
            "Retail Distribution: Neighborhood shops, hypermarkets, and digital fulfilment.",
        ])

        count = max(1, len(steps))
        step_w = (12.1 - 0.35 * (count - 1)) / count
        step_y = 2.05
        step_h = 3.65

        for k, st in enumerate(steps):
            sx = 0.6 + k * (step_w + 0.35)
            r_cls._shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, sx, step_y, step_w, step_h, tint_a, f"step-box-{k+1}", corner_radius=0.04)

            # Step Pill
            r_cls._shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, sx + 0.2, step_y + 0.2, step_w - 0.4, 0.42, ink, f"step-hdr-{k+1}", corner_radius=0.15)
            r_cls._text(slide, f"STEP 0{k+1}", sx + 0.2, step_y + 0.23, step_w - 0.4, 0.35, white, body_font, 11, bold=True, center=True)

            parts = st.split(":", 1) if ":" in st else [st[:30], st[30:]]
            r_cls._text(slide, parts[0].strip(), sx + 0.15, step_y + 0.8, step_w - 0.3, 0.7, primary, title_font, 13.5, bold=True, center=True)
            r_cls._shape(slide, MSO_SHAPE.RECTANGLE, sx + (step_w - 0.8) / 2, step_y + 1.6, 0.8, 0.03, accent, f"step-rule-{k+1}")

            if len(parts) > 1:
                r_cls._text(slide, clean_text(parts[1].strip())[:140], sx + 0.15, step_y + 1.75, step_w - 0.3, step_h - 1.9, hex_to_rgb(ds.colors.text_secondary), body_font, 11, center=True)

            # Chevron Arrow between steps
            if k < count - 1:
                arrow_x = sx + step_w + 0.08
                arrow_y = step_y + step_h / 2 - 0.2
                r_cls._shape(slide, MSO_SHAPE.CHEVRON, arrow_x, arrow_y, 0.22, 0.4, primary, f"flow-arrow-{k+1}")

        # Summary / Value-Add Band at Bottom
        r_cls._shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, 0.6, 5.9, 12.1, 0.85, tint_b, "value-band", corner_radius=0.04)
        band_text = data.takeaway or "Value increments at each exchange tier, reflecting logistical transport, risk, and margin."
        r_cls._text(slide, "CHAIN DYNAMICS & VALUE MARGIN", 0.85, 5.98, 4.0, 0.28, primary, body_font, 10, bold=True)
        r_cls._text(slide, clean_text(band_text)[:200], 0.85, 6.28, 11.5, 0.42, hex_to_rgb(ds.colors.text_primary), body_font, 11.5)

