"""Enterprise-grade native PowerPoint presentation renderer."""

import io
import logging
import math
import re
from typing import Any

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.xmlchemy import OxmlElement
from pptx.util import Inches, Pt

from app.schemas.generation_state import (
    DesignSystem,
    ImagePlacementMode,
    LayoutFamily,
    SlideSpec,
)
from app.services.design_system import clean_text, default_brand, normalize_brand
from app.tools.chart_engine import ChartEngine
from app.tools.diagram_engine import DiagramEngine
from app.tools.image_intelligence import ImageIntelligence
from app.tools.pptx_validator import PPTXValidator
from app.tools.table_engine import TableEngine
from app.tools.text_geometry import TextGeometry

logger = logging.getLogger(__name__)


def hex_to_rgb(value: str, default: tuple[int, int, int] = (19, 42, 82)) -> RGBColor:
    val = value.lstrip("#")
    try:
        return RGBColor(int(val[0:2], 16), int(val[2:4], 16), int(val[4:6], 16))
    except Exception:
        return RGBColor(*default)


def tint(color: RGBColor, amount: float) -> RGBColor:
    return RGBColor(*(round(c + (255 - c) * amount) for c in color))


class PPTXRenderer:
    SLIDE_WIDTH = Inches(13.333)
    SLIDE_HEIGHT = Inches(7.5)

    @staticmethod
    def _fits(text, w, h, size=13, bullet_list=False):
        capacity = max(1, int((w - 0.04 - (0.23 if bullet_list else 0)) * 72 / (size * 0.56)))
        paragraphs = clean_text(text).split("\n")
        lines = sum(max(1, math.ceil(len(line) / capacity)) for line in paragraphs)
        spacing = max(0, len(paragraphs) - 1) * 5 if bullet_list else 0
        return ((lines * size * 1.25 + spacing) / 72 + 0.06) - 0.02 <= h

    @classmethod
    def _shape(cls, slide, kind, x, y, w, h, color, name="card", corner_radius=0.08):
        shape = slide.shapes.add_shape(kind, Inches(x), Inches(y), Inches(w), Inches(h))
        shape.name = name
        shape.fill.solid()
        shape.fill.fore_color.rgb = color
        shape.line.fill.background()
        shape.shadow.inherit = False
        if kind == MSO_SHAPE.ROUNDED_RECTANGLE:
            shape.adjustments[0] = corner_radius
        return shape

    @classmethod
    def _text(
        cls,
        slide,
        text,
        x,
        y,
        w,
        h,
        color,
        font_name="Segoe UI",
        size=14,
        title=False,
        bold=False,
        center=False,
        italic=False,
        bullet_list=False,
    ):
        text = clean_text(text)
        if bullet_list:
            text = "\n".join(re.sub(r"^\s*[•●▪-]\s*", "", line) for line in text.split("\n"))

        shape = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
        shape.name = "content-text"
        frame = shape.text_frame
        frame.word_wrap = True
        frame.margin_left = frame.margin_right = Inches(0.02)
        frame.margin_top = frame.margin_bottom = Inches(0.02)

        if title and len(text) > 400:
            raise ValueError("Slide text exceeds its layout budget; shorten the source copy and regenerate")

        floor = 18 if title and size >= 24 else min(int(round(size)), 9)
        curr_size = int(round(size))
        while True:
            if cls._fits(text, w, h, curr_size, bullet_list):
                break
            if curr_size <= floor:
                # Text exceeds budget at floor size — trim text progressively until it fits
                if bullet_list:
                    lines_list = text.split("\n")
                    while len(lines_list) > 1 and not cls._fits("\n".join(lines_list), w, h, floor, bullet_list):
                        lines_list.pop()
                    text = "\n".join(lines_list)
                if not cls._fits(text, w, h, floor, bullet_list):
                    while len(text) > 20 and not cls._fits(text + "…", w, h, floor, bullet_list):
                        text = text[:-10].rstrip()
                    text = text.rstrip() + "…"
                curr_size = floor
                break
            curr_size -= 1

        frame.vertical_anchor = MSO_ANCHOR.MIDDLE if center else MSO_ANCHOR.TOP

        for i, line in enumerate(text.split("\n")):
            p = frame.paragraphs[0] if i == 0 else frame.add_paragraph()
            p.text = line
            p.font.name = font_name
            p.font.size = Pt(curr_size)
            p.font.bold = bold or title
            p.font.italic = italic
            p.font.color.rgb = color
            p.alignment = PP_ALIGN.CENTER if center else PP_ALIGN.LEFT

            for r in p.runs:
                r.font.name = font_name
                r.font.size = Pt(curr_size)
                r.font.bold = bold or title
                r.font.italic = italic
                r.font.color.rgb = color

            if bullet_list:
                properties = p._p.get_or_add_pPr()
                properties.set("marL", str(Inches(0.23)))
                properties.set("indent", str(-Inches(0.18)))
                marker = OxmlElement("a:buChar")
                marker.set("char", "•")
                properties.append(marker)
                p.space_after = Pt(5 if i < len(text.split("\n")) - 1 else 0)
                p.line_spacing = 1.15

            if not title and not center and ":" in line and len(line.split(":", 1)[0]) < 55:
                lead, remainder = line.split(":", 1)
                p.clear()
                p.add_run().text = lead + ":"
                p.runs[0].font.bold = True
                p.runs[0].font.name = font_name
                p.runs[0].font.size = Pt(curr_size)
                p.runs[0].font.color.rgb = color
                run_rem = p.add_run()
                run_rem.text = remainder
                run_rem.font.name = font_name
                run_rem.font.size = Pt(curr_size)
                run_rem.font.color.rgb = color

        return shape

    @classmethod
    def _card(
        cls,
        slide,
        text,
        x,
        y,
        w,
        h,
        fill,
        foreground,
        accent,
        font_name="Segoe UI",
        number=None,
        badge_label=None,
    ):
        bullet_list = "\n" in text
        text_x, text_w = x + 0.25, w - 0.5
        if number is not None:
            text_x, text_w = x + 0.8, w - 1.05

        size = 16
        while size > 13 and not cls._fits(text, text_w, h - 0.4, size, bullet_list):
            size -= 1

        capacity = max(1, int((text_w - 0.04 - (0.23 if bullet_list else 0)) * 72 / (size * 0.56)))
        paragraphs = clean_text(text).split("\n")
        lines = sum(max(1, math.ceil(len(line) / capacity)) for line in paragraphs)
        spacing = max(0, len(paragraphs) - 1) * 5 if bullet_list else 0
        actual_h = (lines * size * 1.25 + spacing) / 72 + 0.46
        card_h = min(h, max(0.85, actual_h))

        cls._shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, x, y, w, card_h, fill)
        if number is not None:
            cls._shape(slide, MSO_SHAPE.OVAL, x + 0.2, y + 0.25, 0.4, 0.4, accent)
            cls._text(slide, str(number), x + 0.2, y + 0.25, 0.4, 0.4, RGBColor(255, 255, 255), font_name, 11, bold=True, center=True)
            text_x, text_w = x + 0.8, w - 1.05
        cls._text(slide, text, text_x, y + 0.2, text_w, card_h - 0.4, foreground, font_name, size, bullet_list=bullet_list)

    @classmethod
    def render_presentation(
        cls,
        slide_specs: list[SlideSpec],
        design_system: DesignSystem,
        source_images: dict[str, bytes] | None = None,
        deck_title: str = "Presentation",
        title: str | None = None,
    ) -> bytes:
        prs = Presentation()
        prs.slide_width, prs.slide_height = cls.SLIDE_WIDTH, cls.SLIDE_HEIGHT
        effective_title = title or deck_title

        images = source_images or {}
        ink = hex_to_rgb(getattr(design_system.colors, "ink", design_system.colors.primary))
        primary = hex_to_rgb(design_system.colors.primary)
        secondary = hex_to_rgb(getattr(design_system.colors, "secondary", design_system.colors.primary))
        accent = hex_to_rgb(design_system.colors.accent)
        card_fill = hex_to_rgb(design_system.colors.card_fill)
        neutral = hex_to_rgb(design_system.colors.neutral)
        white = RGBColor(255, 255, 255)
        paper = hex_to_rgb(design_system.colors.paper)
        text_primary = hex_to_rgb(design_system.colors.text_primary)
        text_secondary = hex_to_rgb(design_system.colors.text_secondary)
        title_font = design_system.typography.title_font.name
        body_font = design_system.typography.body_font.name

        for index, slide_data in enumerate(slide_specs):
            slide = prs.slides.add_slide(prs.slide_layouts[6])
            layout = slide_data.layout_family
            arch_id = getattr(slide_data, "archetype_id", None)
            if not arch_id and hasattr(layout, "value") and str(layout.value).startswith("A") and str(layout.value)[1:].isdigit():
                arch_id = str(layout.value)
            if not arch_id and isinstance(slide_data.layout_hint, str) and slide_data.layout_hint.upper().startswith("A"):
                cand = slide_data.layout_hint.upper()
                if cand[1:].isdigit():
                    arch_id = cand

            is_standalone_cover = layout in (LayoutFamily.HERO, LayoutFamily.CLOSING) or arch_id in ("A1", "A2", "A3")
            dark = slide_data.dark_background or (layout in (LayoutFamily.HERO, LayoutFamily.CLOSING, LayoutFamily.DARK_QUOTE) and design_system.subject_domain != "markets") or arch_id in ("A1", "A3")

            slide.background.fill.solid()
            slide.background.fill.fore_color.rgb = ink if dark else paper

            fg = white if dark else text_primary
            body_col = tint(white, 0.18) if dark else text_secondary
            fill = tint(ink, 0.18) if dark else card_fill

            title = slide_data.headline or slide_data.key_message or slide_data.objective
            eyebrow = slide_data.eyebrow or f"CHAPTER {(index // 4) + 1}"
            bullets = [b for b in slide_data.bullets if isinstance(b, str) and b.strip()]
            image_bytes = images.get(slide_data.image_artifact_id or "")

            from app.services.archetype_renderer import ArchetypeRenderer

            # Eyebrow & Title & Accent Tick (Skip for custom cover/divider archetypes)
            if not is_standalone_cover:
                cls._text(slide, eyebrow.upper(), 0.6, 0.45, 12.1, 0.32, primary if not dark else accent, body_font, 12, bold=True)
                cls._text(slide, title, 0.6, 0.82, 12.1, 0.85, fg, title_font, 28, title=True)
                cls._shape(slide, MSO_SHAPE.RECTANGLE, 0.6, 1.72, 0.6, 0.06, accent if not dark else tint(primary, 0.6), "accent-tick")

            # Footer
            if not is_standalone_cover:
                footer_text = f"{deck_title.upper()} · {eyebrow.upper()}"
                cls._text(slide, footer_text[:140], 0.6, 7.05, 11.4, 0.28, body_col, body_font, 9.5)

            # Persistent Page Number Pill
            pill_bg = tint(ink, 0.28) if dark else tint(primary, 0.12)
            pill_fg = white if dark else ink
            cls._shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, 12.15, 6.95, 0.55, 0.35, pill_bg, "page-pill", corner_radius=0.25)
            cls._text(slide, str(index + 1), 12.15, 6.95, 0.55, 0.35, pill_fg, body_font, 10.5, bold=True, center=True)

            # Speaker Notes
            notes = slide_data.speaker_notes or f"Presenter guidance for Slide {index + 1}: {title}"
            slide.notes_slide.notes_text_frame.text = notes

            # --- Consulting Archetype Dispatch ---
            if arch_id and ArchetypeRenderer.can_render(arch_id):
                if ArchetypeRenderer.render(slide, arch_id, slide_data, design_system, image_bytes, cls):
                    # Redraw page pill on top to ensure never obscured
                    cls._shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, 12.15, 6.95, 0.55, 0.35, pill_bg, "page-pill", corner_radius=0.25)
                    cls._text(slide, str(index + 1), 12.15, 6.95, 0.55, 0.35, pill_fg, body_font, 10.5, bold=True, center=True)
                    continue

            # --- Layout Routing ---
            if layout == LayoutFamily.HERO:
                if image_bytes:
                    cls._shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, 0.6, 1.1, 4.2, 0.38, tint(primary, 0.25), "kicker-pill")
                    cls._text(slide, eyebrow.upper(), 0.7, 1.13, 4.0, 0.32, accent, title_font, 11.5, bold=True)
                    cls._text(slide, title, 0.6, 1.65, 5.9, 1.85, fg, title_font, 34, title=True)
                    cls._shape(slide, MSO_SHAPE.RECTANGLE, 0.6, 3.62, 1.8, 0.07, accent, "accent-rule")
                    if slide_data.takeaway:
                        cls._text(slide, slide_data.takeaway, 0.6, 3.82, 5.9, 0.85, body_col, body_font, 15)
                    if bullets:
                        cls._text(slide, "\n".join(bullets), 0.6, 4.75, 5.9, 1.7, body_col, body_font, 13, bullet_list=True)
                    cls._shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, 6.85, 1.1, 5.85, 5.35, white, "hero-frame")
                    cls._render_picture(slide, image_bytes, 7.0, 1.25, 5.55, 4.35)
                    caption = slide_data.image_caption or "Documentary illustration"
                    cls._text(slide, caption[:85], 7.0, 5.75, 5.55, 0.55, primary, body_font, 10, italic=True, center=True)
                else:
                    cls._text(slide, title, 0.6, 1.1, 12.1, 1.65, fg, title_font, 36, title=True)
                    if slide_data.takeaway:
                        cls._text(slide, slide_data.takeaway, 0.6, 2.95, 12.1, 0.65, body_col, body_font, 16)
                        y_card = 3.75
                        h_card = 2.55
                    else:
                        y_card = 2.25
                        h_card = 4.0
                    mid = max(1, math.ceil(len(bullets) / 2))
                    for j, group in enumerate((bullets[:mid], bullets[mid:])):
                        if group:
                            cls._card(slide, "\n".join(group), 0.6 + j * 6.225, y_card, 5.875, h_card, fill, body_col, accent, body_font)

            elif layout in (LayoutFamily.CHART_FOCUS, LayoutFamily.CHART_INSIGHT) and slide_data.chart_spec:
                ChartEngine.render_chart(slide, slide_data.chart_spec, design_system, 0.6, 2.15, 7.2, 4.2)
                cls._shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, 8.1, 2.15, 4.6, 4.2, fill, "insight-card")
                cls._text(slide, "Strategic Insights", 8.35, 2.35, 4.1, 0.4, fg, title_font, 14, bold=True)
                cls._text(slide, "\n".join(bullets) if bullets else slide_data.takeaway, 8.35, 2.85, 4.1, 3.3, body_col, body_font, 12.5, bullet_list=bool(bullets))

            elif layout == LayoutFamily.TABLE_FOCUS and slide_data.table_spec:
                TableEngine.render_table(slide, slide_data.table_spec, design_system, 0.6, 2.15, 12.1, 4.2)

            elif layout in (LayoutFamily.PROCESS_STEPS, LayoutFamily.MATRIX_QUADRANT, LayoutFamily.ARCHITECTURE_DIAGRAM) and slide_data.diagram_spec:
                DiagramEngine.render_diagram(slide, slide_data.diagram_spec, design_system, 0.6, 2.15, 12.1, 4.2)

            elif layout in (LayoutFamily.IMAGE_FOCUS, LayoutFamily.TEXT_IMAGE) and image_bytes:
                cls._text(slide, "\n".join(bullets), 0.6, 2.25, 5.85, 4.15, body_col, body_font, 15, bullet_list=True)
                cls._shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, 6.75, 2.2, 5.95, 4.25, white, "image-frame")
                cls._render_picture(slide, image_bytes, 6.85, 2.3, 5.75, 3.45)
                caption = slide_data.image_caption or "Source document image"
                if not re.match(r"^(?:Fig|Figure|Map)\b", caption, re.I):
                    caption = f"Fig. {index + 1} - {caption}"
                cls._text(slide, caption[:95], 6.85, 5.85, 5.75, 0.5, primary, body_font, 10.5, italic=True, center=True)

            elif slide_data.metrics and slide_data.layout_hint == "bar_chart":
                # Render direct data-bars with provenance
                metrics = slide_data.metrics
                values = [float(re.sub(r"[^\d.]", "", str(m.get("value", "0"))) or 0) for m in metrics]
                maximum = max(values) or 1
                for j, (metric, val) in enumerate(zip(metrics, values)):
                    y = 2.45 + j * 0.82
                    cls._text(slide, metric["label"], 0.6, y, 3.2, 0.65, body_col, body_font, 15)
                    bar_w = max(0.015, val / maximum * 6.6)
                    cls._shape(slide, MSO_SHAPE.RECTANGLE, 4.05, y + 0.05, bar_w, 0.4, accent, "data-bar")
                    cls._text(slide, str(metric["value"]), 10.95, y, 1.75, 0.65, fg, title_font, 16, bold=True)

            elif layout in (LayoutFamily.METRICS_GRID, LayoutFamily.BIG_NUMBERS) and slide_data.metrics:
                metrics = slide_data.metrics[:4]
                width = (12.1 - 0.35 * (len(metrics) - 1)) / len(metrics)
                for j, metric in enumerate(metrics):
                    x = 0.6 + j * (width + 0.35)
                    cls._shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, x, 2.4, width, 3.0, fill)
                    cls._text(slide, str(metric.get("value", "")), x + 0.2, 2.85, width - 0.4, 1.15, fg, title_font, 40, bold=True, center=True)
                    cls._text(slide, str(metric.get("label", "")), x + 0.2, 4.3, width - 0.4, 0.75, body_col, body_font, 13, center=True)

            elif layout in (LayoutFamily.CLOSING, LayoutFamily.DARK_QUOTE):
                cls._text(slide, title, 0.6, 1.05, 12.1, 1.1, fg, title_font, 32, title=True)
                if slide_data.takeaway:
                    cls._text(slide, slide_data.takeaway, 0.6, 1.95, 12.1, 0.65, body_col, body_font, 14)
                cls._text(slide, "\n".join(bullets), 0.6, 2.7, 7.0, 3.65, body_col, body_font, 14, bullet_list=True)
                cls._shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, 7.95, 2.7, 4.75, 3.65, tint(primary, 0.22), "card")
                cls._shape(slide, MSO_SHAPE.OVAL, 9.8, 2.95, 1.0, 1.0, accent, "emblem-disc")
                cls._text(slide, "★", 9.8, 2.95, 1.0, 1.0, white, body_font, 22, bold=True, center=True)
                quote_text = (slide_data.quote or {}).get("text") if isinstance(slide_data.quote, dict) else "Strategic Horizon & Execution Commitment"
                cls._text(slide, quote_text, 8.15, 4.15, 4.35, 1.9, white, title_font, 15, bold=True, center=True, italic=True)

            elif slide_data.layout_hint in ("big_questions", "numbered_columns") or (layout == LayoutFamily.CARD_GRID and len(bullets) == 4 and any("?" in b for b in bullets)):
                for j, item in enumerate(bullets[:4]):
                    x = 0.6 + j * (2.8 + 0.3)
                    y = 2.05
                    w = 2.8
                    h = 4.65
                    cls._shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, x, y, w, h, fill, f"card-{j+1}", corner_radius=0.04)
                    cls._shape(slide, MSO_SHAPE.OVAL, x + 0.8, y + 0.3, 1.2, 1.2, primary, f"badge-{j+1}")
                    cls._text(slide, f"0{j+1}", x + 0.8, y + 0.3, 1.2, 1.2, white, title_font, 28, bold=True, center=True)
                    if "\n" in item:
                        parts = item.split("\n", 1)
                    elif ":" in item:
                        parts = item.split(":", 1)
                    elif "?" in item:
                        parts = item.split("?", 1)
                        parts[0] = parts[0] + "?"
                    else:
                        parts = [item[:45], item[45:]]
                    q_t = parts[0].strip()
                    q_b = parts[1].strip() if len(parts) > 1 else ""
                    if len(q_t) > 48:
                        q_t = q_t[:45].rsplit(" ", 1)[0] + "..."
                    cls._text(slide, q_t, x + 0.15, y + 1.65, w - 0.3, 0.85, primary, title_font, 12.5, bold=True, center=True)
                    cls._shape(slide, MSO_SHAPE.RECTANGLE, x + 0.8, y + 2.55, 1.2, 0.04, accent, "rule")
                    if q_b:
                        if len(q_b) > 180:
                            q_b = q_b[:175].rsplit(" ", 1)[0] + "..."
                        cls._text(slide, q_b, x + 0.2, y + 2.7, w - 0.4, 1.8, body_col, body_font, 11, center=True)

            elif slide_data.layout_hint in ("saptanga", "hub_spoke") or getattr(slide_data.diagram_spec, "diagram_type", "") in ("saptanga", "hub_spoke"):
                cx, cy, cw, ch = 5.25, 2.35, 2.85, 2.95
                cls._shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, cx, cy, cw, ch, primary, "center-hub", corner_radius=0.06)
                cls._shape(slide, MSO_SHAPE.OVAL, cx + 0.925, cy + 0.3, 1.0, 1.0, accent, "hub-disc")
                cls._text(slide, "★", cx + 0.925, cy + 0.3, 1.0, 1.0, white, body_font, 20, bold=True, center=True)
                cls._text(slide, "Swāmi (The Sovereign)", cx + 0.15, cy + 1.45, cw - 0.3, 0.4, white, title_font, 14.5, bold=True, center=True)
                cls._text(slide, "The supreme authority guiding state welfare, justice, defence, and moral righteousness.", cx + 0.15, cy + 1.9, cw - 0.3, 0.9, tint(white, 0.15), body_font, 10.5, center=True)

                limbs = bullets if len(bullets) >= 6 else (bullets + [f"Limb {k}: Administrative function" for k in range(len(bullets), 6)])
                for k, limb in enumerate(limbs[:6]):
                    is_right = k >= 3
                    row = k % 3
                    rx = 8.35 if is_right else 0.6
                    ry = 1.75 + row * 1.55
                    cls._shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, rx, ry, 4.35, 1.35, fill, f"limb-{k+1}", corner_radius=0.04)
                    cls._shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, rx + 0.15, ry + 0.15, 0.5, 0.32, tint(accent, 0.85), f"pill-{k+1}", corner_radius=0.2)
                    cls._text(slide, f"0{k+1}", rx + 0.15, ry + 0.15, 0.5, 0.32, primary, title_font, 11, bold=True, center=True)
                    if ":" in limb:
                        parts = limb.split(":", 1)
                    elif "\n" in limb:
                        parts = limb.split("\n", 1)
                    else:
                        parts = [limb[:30], limb[30:]]
                    l_t = parts[0].strip()
                    l_b = parts[1].strip() if len(parts) > 1 else ""
                    if len(l_t) > 30:
                        l_t = l_t[:27].rsplit(" ", 1)[0] + "..."
                    cls._text(slide, l_t, rx + 0.75, ry + 0.15, 3.45, 0.35, primary, title_font, 12, bold=True)
                    if l_b:
                        if len(l_b) > 140:
                            l_b = l_b[:135].rsplit(" ", 1)[0] + "..."
                        cls._text(slide, l_b, rx + 0.15, ry + 0.55, 4.05, 0.7, body_col, body_font, 11)

            elif slide_data.layout_hint in ("two_column_definition", "concept_definition") and image_bytes:
                cls._shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, 0.6, 1.75, 6.4, 3.1, fill, "narrative-card", corner_radius=0.04)
                cls._text(slide, "\n".join(bullets[:3]), 0.85, 1.95, 5.9, 2.65, body_col, body_font, 12.5, bullet_list=True)
                cls._shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, 0.6, 5.05, 6.4, 1.65, tint(accent, 0.92), "vocab-card", corner_radius=0.04)
                cls._shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, 0.85, 5.2, 2.2, 0.3, accent, "vocab-pill", corner_radius=0.15)
                cls._text(slide, "KEY CONCEPT", 0.85, 5.22, 2.2, 0.26, white, body_font, 10.5, bold=True, center=True)
                def_text = slide_data.takeaway or (bullets[3] if len(bullets) > 3 else "Universal moral conduct and ethical statecraft.")
                cls._text(slide, def_text, 0.85, 5.6, 5.9, 0.95, body_col, body_font, 12)
                cls._shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, 7.3, 1.75, 5.4, 4.95, white, "artifact-frame", corner_radius=0.03)
                cls._render_picture(slide, image_bytes, 7.45, 1.9, 5.1, 4.1)
                caption = slide_data.image_caption or "Source document illustration"
                cls._text(slide, caption[:95], 7.45, 6.2, 5.1, 0.4, primary, body_font, 10.5, italic=True, center=True)

            elif slide_data.layout_hint in ("stacked_comparison", "legacy", "two_highways") and image_bytes:
                mid = max(1, math.ceil(len(bullets) / 2))
                grp1 = bullets[:mid]
                grp2 = bullets[mid:]
                cls._shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, 0.6, 1.75, 6.4, 2.35, fill, "card-1", corner_radius=0.04)
                cls._text(slide, "\n".join(grp1), 0.85, 1.95, 5.9, 1.95, body_col, body_font, 12, bullet_list=True)
                cls._shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, 0.6, 4.3, 6.4, 2.4, fill, "card-2", corner_radius=0.04)
                cls._text(slide, "\n".join(grp2), 0.85, 4.5, 5.9, 2.0, body_col, body_font, 12, bullet_list=True)
                cls._shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, 7.3, 1.75, 5.4, 4.95, white, "map-frame", corner_radius=0.03)
                cls._render_picture(slide, image_bytes, 7.45, 1.9, 5.1, 4.15)
                caption = slide_data.image_caption or "Source document map"
                cls._text(slide, caption[:95], 7.45, 6.2, 5.1, 0.4, primary, body_font, 10.5, italic=True, center=True)

            elif layout in (LayoutFamily.CARD_GRID, LayoutFamily.THREE_COLUMN):
                items = bullets or ([slide_data.takeaway] if slide_data.takeaway else [])
                count = len(items)
                cols = 2 if count == 4 else min(count, 3) or 1
                rows = math.ceil(count / cols) or 1
                h_card = (3.65 - 0.35 * (rows - 1)) / rows
                w_card = (12.1 - 0.35 * (cols - 1)) / cols
                for j, item in enumerate(items):
                    x_c = 0.6 + (j % cols) * (w_card + 0.35)
                    y_c = 2.4 + (j // cols) * (h_card + 0.35)
                    cls._card(slide, item, x_c, y_c, w_card, h_card, fill, body_col, primary, body_font, j + 1)

            else:
                # If image_bytes is present, prioritize visual framed layout
                if image_bytes:
                    cls._text(slide, "\n".join(bullets), 0.6, 2.25, 5.85, 4.15, body_col, body_font, 15, bullet_list=True)
                    cls._shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, 6.75, 2.2, 5.95, 4.25, white, "image-frame")
                    cls._render_picture(slide, image_bytes, 6.85, 2.3, 5.75, 3.45)
                    caption = slide_data.image_caption or "Source document illustration"
                    if not re.match(r"^(?:Fig|Figure|Map)\b", caption, re.I):
                        caption = f"Fig. {index + 1} - {caption}"
                    cls._text(slide, caption[:95], 6.85, 5.85, 5.75, 0.5, primary, body_font, 10.5, italic=True, center=True)
                else:
                    # Two Column / Comparison default
                    midpoint = max(1, math.ceil(len(bullets) / 2))
                    groups = [bullets[:midpoint], bullets[midpoint:]]
                    for j, group in enumerate(groups):
                        cls._card(slide, "\n".join(group), 0.6 + j * 6.225, 2.25, 5.875, 4.0, fill, body_col, accent, body_font)

            # Speaker Notes
            notes = slide_data.speaker_notes or f"Presenter guidance for Slide {index + 1}: {title}"
            slide.notes_slide.notes_text_frame.text = notes

        output = io.BytesIO()
        prs.save(output)
        return output.getvalue()

    @classmethod
    def _render_picture(cls, slide, payload: bytes, x: float, y: float, w: float, h: float):
        try:
            from PIL import Image
            with Image.open(io.BytesIO(payload)) as source:
                px_w, px_h = source.size
            ratio = min(w / px_w, h / px_h)
            pw, ph = px_w * ratio, px_h * ratio
            slide.shapes.add_picture(
                io.BytesIO(payload),
                Inches(x + (w - pw) / 2.0),
                Inches(y + (h - ph) / 2.0),
                Inches(pw),
                Inches(ph),
            )
        except Exception as e:
            logger.warning("Render picture fallback: %s", e)

    @classmethod
    def render_deck(
        cls,
        deck_spec: dict[str, Any],
        brand_style: dict[str, Any] | None = None,
        source_images: dict[str, bytes] | None = None,
    ) -> bytes:
        from app.schemas.generation_state import PresentationGoal
        from app.agents.design_intelligence import DesignIntelligenceAgent
        from app.agents.storyline_agent import StorylineAgent

        title = deck_spec.get("deckTitle", "Presentation")
        brand = normalize_brand(brand_style or deck_spec.get("brandStyle"), title)
        goal = PresentationGoal(topic=title, target_slide_count=len(deck_spec.get("slides", [])) or 4)

        ds = DesignIntelligenceAgent.generate_design_system(goal, llm_brand_hints=brand)
        if brand.get("titleFont", {}).get("name"):
            ds.typography.title_font.name = brand["titleFont"]["name"]
        if brand.get("bodyFont", {}).get("name"):
            ds.typography.body_font.name = brand["bodyFont"]["name"]
        if brand.get("subject"):
            ds.subject_domain = brand["subject"]
            ds.colors.primary = brand["colors"]["primary"]
            ds.colors.accent = brand["colors"]["accent"]
            ds.colors.neutral = brand["colors"]["neutral"]

        available_assets = None
        if source_images:
            from app.schemas.generation_state import AssetMetadata
            available_assets = [
                AssetMetadata(
                    asset_id=k,
                    source_file="source_image",
                    caption="",
                    storage_key="",
                )
                for k in source_images.keys()
            ]

        specs = StorylineAgent.create_storyline_plan(
            goal, llm_plan_spec=deck_spec, available_assets=available_assets
        )
        return cls.render_presentation(specs, ds, source_images, deck_title=title)

    @classmethod
    def validate_deck(cls, payload: bytes, expected_slides: int) -> dict[str, Any]:
        report = PPTXValidator.validate_pptx_stream(payload, expected_slides)
        return {
            "status": report.status,
            "overall_quality_score": report.overall_quality_score,
            "checks": report.checks_performed,
            "visualInspection": "not_performed",
            "slides": report.slide_count,
            "warnings": [i.message for i in report.issues],
        }
