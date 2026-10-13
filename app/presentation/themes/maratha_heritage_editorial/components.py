"""Reusable Presentation Primitives for Maratha Heritage Editorial Theme.

Generates editable PowerPoint shapes, shadows, borders, image frames, governance diagrams,
timelines, metrics, and typography matching the exact DrawingML properties of benchmark deck
'The Rise of the Marathas (4).pptx'.
"""

import io
import math
import logging
import os
from typing import Any, List, Optional, Tuple

from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.xmlchemy import OxmlElement
from pptx.util import Inches, Pt

from app.presentation.themes.maratha_heritage_editorial.tokens import (
    COLORS, SHADOWS, SPACING, FONTS, GEOMETRY
)
from app.presentation.themes.maratha_heritage_editorial.icons import IconResolver
from app.presentation.themes.maratha_heritage_editorial.typography import (
    BUDGETS, fit_text_to_box, format_kicker_text, TitleOptimizer, TextMeasurementService
)

logger = logging.getLogger(__name__)


def apply_soft_shadow(
    shape: Any,
    blur_rad: int = SHADOWS.blur_rad_emu,
    dist: int = SHADOWS.dist_emu,
    dir_val: int = SHADOWS.dir_deg,
    color: str = SHADOWS.color_hex,
    alpha: int = SHADOWS.alpha_val
):
    """Applies DrawingML outer shadow (16% black, 9pt blur, 3pt distance, 90 deg down)."""
    try:
        spPr = shape._element.spPr
        effectLst = spPr.find("{http://schemas.openxmlformats.org/drawingml/2006/main}effectLst")
        if effectLst is None:
            effectLst = OxmlElement("a:effectLst")
            spPr.append(effectLst)

        outerShdw = OxmlElement("a:outerShdw")
        outerShdw.set("blurRad", str(blur_rad))
        outerShdw.set("dist", str(dist))
        outerShdw.set("dir", str(dir_val))
        outerShdw.set("algn", "tl")
        outerShdw.set("rotWithShape", "0")

        srgbClr = OxmlElement("a:srgbClr")
        srgbClr.set("val", color)

        alpha_el = OxmlElement("a:alpha")
        alpha_el.set("val", str(alpha))
        srgbClr.append(alpha_el)
        outerShdw.append(srgbClr)

        effectLst.append(outerShdw)
    except Exception as e:
        logger.debug("Failed to set outer shadow: %s", e)


def set_shape_border(shape: Any, color: RGBColor, width_pt: float = 0.75):
    """Sets a clean vector outline on a shape."""
    shape.line.color.rgb = color
    shape.line.width = Pt(width_pt)


def create_solid_shape(
    slide: Any,
    shape_type: MSO_SHAPE,
    x: float,
    y: float,
    w: float,
    h: float,
    fill_color: RGBColor,
    border_color: Optional[RGBColor] = None,
    border_width_pt: float = 0.75,
    shadow: bool = False,
    corner_radius_pct: Optional[float] = None
) -> Any:
    """Creates a solid shape with clean styling, subtle corner radius, and optional shadow."""
    shp = slide.shapes.add_shape(shape_type, Inches(x), Inches(y), Inches(w), Inches(h))
    shp.fill.solid()
    shp.fill.fore_color.rgb = fill_color
    if border_color:
        set_shape_border(shp, border_color, border_width_pt)
    else:
        shp.line.fill.background()
    if shadow:
        apply_soft_shadow(shp)
    if shape_type == MSO_SHAPE.ROUNDED_RECTANGLE:
        try:
            if corner_radius_pct is not None:
                shp.adjustments[0] = corner_radius_pct
            else:
                # Authentic editorial corner radius: ~0.16 inches subtle curve, preventing bulbous joining
                min_dim = max(0.1, min(w, h))
                shp.adjustments[0] = min(0.06, max(0.022, 0.16 / min_dim))
        except Exception:
            pass
    return shp


def add_text_box(
    slide: Any,
    x: float,
    y: float,
    w: float,
    h: float,
    margin_left: float = 0.0,
    margin_top: float = 0.0,
    margin_right: float = 0.0,
    margin_bottom: float = 0.0,
    name: Optional[str] = None
) -> Any:
    """Creates a text box with tight zero margins for precision alignment."""
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    if name:
        tb.name = name
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = Inches(margin_left)
    tf.margin_right = Inches(margin_right)
    tf.margin_top = Inches(margin_top)
    tf.margin_bottom = Inches(margin_bottom)
    return tb


class IconBadge:
    """Renders the signature saffron-orange circular badge with centered icon asset."""

    @classmethod
    def render(
        cls,
        slide: Any,
        x: float,
        y: float,
        diameter: float = 0.66,
        icon_path: Optional[str] = None,
        semantic_hint: Optional[str] = None,
        slide_idx: Optional[int] = None
    ) -> Any:
        # 1. Circular badge shape
        circle = create_solid_shape(
            slide,
            MSO_SHAPE.OVAL,
            x,
            y,
            diameter,
            diameter,
            fill_color=COLORS.rgb_orange,
            border_color=None,
            shadow=False
        )

        # 2. Resolve icon asset
        resolved_icon = icon_path
        if not resolved_icon:
            resolved_icon = IconResolver.resolve_path(
                semantic_hint=semantic_hint,
                slide_index=slide_idx
            )

        # 3. Add icon image centered
        if resolved_icon and os.path.exists(resolved_icon):
            icon_size = IconResolver.calculate_responsive_size(diameter)
            ix, iy = IconResolver.calculate_optical_offset(x, y, diameter, icon_size)
            slide.shapes.add_picture(resolved_icon, Inches(ix), Inches(iy), Inches(icon_size), Inches(icon_size))

        return circle


class NumberBadge:
    """Renders saffron-orange circular badge with centered two-digit number."""

    @classmethod
    def render(
        cls,
        slide: Any,
        x: float,
        y: float,
        number_str: str,
        diameter: float = 0.66,
        font_size_pt: float = 14.0
    ) -> Any:
        circle = create_solid_shape(
            slide,
            MSO_SHAPE.OVAL,
            x,
            y,
            diameter,
            diameter,
            fill_color=COLORS.rgb_orange,
            border_color=None,
            shadow=False
        )
        tf = circle.text_frame
        tf.word_wrap = False
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        tf.margin_left = Inches(0)
        tf.margin_right = Inches(0)
        tf.margin_top = Inches(0)
        tf.margin_bottom = Inches(0)
        p = tf.paragraphs[0]
        p.text = str(number_str).zfill(2)
        p.alignment = PP_ALIGN.CENTER
        p.font.name = FONTS.body
        p.font.size = Pt(font_size_pt)
        p.font.bold = True
        p.font.color.rgb = COLORS.rgb_white
        return circle


class CheckBadge:
    """Renders saffron-orange checkmark icon or circular check badge."""

    @classmethod
    def render(
        cls,
        slide: Any,
        x: float,
        y: float,
        size: float = 0.34
    ) -> Any:
        check_icon = os.path.join(os.path.dirname(__file__), "assets", "icons", "image-24-2.png")
        if os.path.exists(check_icon):
            return slide.shapes.add_picture(check_icon, Inches(x), Inches(y), Inches(size), Inches(size))
        # Fallback circle if image missing
        return NumberBadge.render(slide, x, y, "✓", diameter=size, font_size_pt=10.0)


class MarathaEditorialHeader:
    """Renders the standard header: Saffron Orange Badge, Antique Gold Kicker, and Cambria Title."""

    @classmethod
    def render(
        cls,
        slide: Any,
        kicker: str,
        title: str,
        slide_idx: Optional[int] = None,
        semantic_hint: Optional[str] = None,
        icon_path: Optional[str] = None,
        is_dark: bool = False
    ) -> Tuple[Any, Any, Any]:
        badge_y = GEOMETRY.dark_badge_y if is_dark else GEOMETRY.header_badge_y
        kicker_y = GEOMETRY.dark_kicker_y if is_dark else GEOMETRY.header_kicker_y
        title_y = GEOMETRY.dark_title_y if is_dark else GEOMETRY.header_title_y

        # 1. Icon Badge
        badge = IconBadge.render(
            slide,
            x=GEOMETRY.header_badge_x,
            y=badge_y,
            diameter=GEOMETRY.header_badge_d,
            icon_path=icon_path,
            semantic_hint=semantic_hint,
            slide_idx=slide_idx
        )

        # 2. Kicker Text
        clean_kicker = format_kicker_text(kicker)
        tb_kicker = add_text_box(slide, GEOMETRY.header_kicker_x, kicker_y, 11.20, 0.28)
        pk = tb_kicker.text_frame.paragraphs[0]
        pk.text = clean_kicker
        pk.font.name = FONTS.body
        pk.font.size = Pt(12.0)
        pk.font.bold = True
        pk.font.color.rgb = COLORS.rgb_gold

        # 3. Slide Title
        clean_title, _ = TitleOptimizer.optimize(title, max_words=8)
        tb_title = add_text_box(slide, GEOMETRY.header_title_x, title_y, GEOMETRY.header_title_w, 0.68)
        pt = tb_title.text_frame.paragraphs[0]
        pt.text = clean_title
        pt.font.name = FONTS.display
        pt.font.size = Pt(27.0)
        pt.font.bold = True
        pt.font.color.rgb = COLORS.rgb_white if is_dark else COLORS.rgb_maroon

        return badge, tb_kicker, tb_title


class SlideFooter:
    """Renders the standard footer: presentation/source line on left, page number on right."""

    @classmethod
    def render(
        cls,
        slide: Any,
        slide_num: int,
        source_text: str = "The Rise of the Marathas  •  NCERT | Exploring Society: India and Beyond",
        is_dark: bool = False
    ):
        y = GEOMETRY.footer_top
        # Left source line
        tb_left = add_text_box(slide, GEOMETRY.footer_left, y, 10.50, 0.28)
        pl = tb_left.text_frame.paragraphs[0]
        pl.text = source_text
        pl.font.name = FONTS.body
        pl.font.size = Pt(9.0)
        pl.font.color.rgb = COLORS.rgb_text_on_dark if is_dark else COLORS.rgb_muted

        # Right page number
        tb_right = add_text_box(slide, GEOMETRY.footer_slide_num_x, y, 0.60, 0.28)
        pr = tb_right.text_frame.paragraphs[0]
        pr.text = str(slide_num)
        pr.alignment = PP_ALIGN.RIGHT
        pr.font.name = FONTS.body
        pr.font.size = Pt(9.0)
        pr.font.color.rgb = COLORS.rgb_text_on_dark if is_dark else COLORS.rgb_muted


class ParchmentCard:
    """Renders a light parchment information card (#FBF6EF or #F7EEE3) with subtle border."""

    @classmethod
    def render(
        cls,
        slide: Any,
        x: float,
        y: float,
        w: float,
        h: float,
        title: Optional[str] = None,
        body_bullets: Optional[List[str]] = None,
        fill_color: RGBColor = COLORS.rgb_parchment,
        border_color: RGBColor = COLORS.rgb_border_warm,
        shadow: bool = True,
        title_size_pt: float = 16.0,
        body_size_pt: float = 13.5
    ) -> Any:
        card = create_solid_shape(
            slide,
            MSO_SHAPE.ROUNDED_RECTANGLE,
            x,
            y,
            w,
            h,
            fill_color=fill_color,
            border_color=border_color,
            shadow=shadow
        )

        pad_x = 0.28
        pad_y = 0.24
        inner_w = w - (2 * pad_x)
        inner_h = h - (2 * pad_y)

        if title or body_bullets:
            tb = add_text_box(slide, x + pad_x, y + pad_y, inner_w, inner_h)
            tf = tb.text_frame
            tf.word_wrap = True

            first = True
            if title:
                p0 = tf.paragraphs[0]
                p0.text = title
                p0.font.name = FONTS.display
                p0.font.size = Pt(title_size_pt)
                p0.font.bold = True
                p0.font.color.rgb = COLORS.rgb_maroon
                p0.space_after = Pt(8)
                first = False

            if body_bullets:
                for b_text in body_bullets:
                    clean_b = b_text.strip()
                    if not clean_b:
                        continue
                    p = tf.paragraphs[0] if first else tf.add_paragraph()
                    first = False
                    p.text = clean_b
                    p.font.name = FONTS.body
                    p.font.size = Pt(body_size_pt)
                    p.font.color.rgb = COLORS.rgb_body
                    p.space_after = Pt(6)
                    p.line_spacing = 1.15

        return card


class MaroonInsightCard:
    """Renders a dark maroon (#6B221C) insight card with light warm cream text."""

    @classmethod
    def render(
        cls,
        slide: Any,
        x: float,
        y: float,
        w: float,
        h: float,
        title: Optional[str] = None,
        body_text: Optional[str] = None,
        icon_path: Optional[str] = None,
        title_size_pt: float = 16.0,
        body_size_pt: float = 13.5
    ) -> Any:
        card = create_solid_shape(
            slide,
            MSO_SHAPE.ROUNDED_RECTANGLE,
            x,
            y,
            w,
            h,
            fill_color=COLORS.rgb_maroon,
            border_color=None,
            shadow=True
        )

        pad_x = 0.28
        pad_y = 0.24

        if icon_path and os.path.exists(icon_path):
            slide.shapes.add_picture(icon_path, Inches(x + pad_x), Inches(y + pad_y), Inches(0.45), Inches(0.45))
            tb_x = x + pad_x + 0.60
            tb_w = w - (2 * pad_x) - 0.60
        else:
            tb_x = x + pad_x
            tb_w = w - (2 * pad_x)

        tb = add_text_box(slide, tb_x, y + pad_y, tb_w, h - (2 * pad_y))
        tf = tb.text_frame
        tf.word_wrap = True

        first = True
        if title:
            p0 = tf.paragraphs[0]
            p0.text = title
            p0.font.name = FONTS.display
            p0.font.size = Pt(title_size_pt)
            p0.font.bold = True
            p0.font.color.rgb = COLORS.rgb_white
            p0.space_after = Pt(6)
            first = False

        if body_text:
            p = tf.paragraphs[0] if first else tf.add_paragraph()
            p.text = body_text
            p.font.name = FONTS.body
            p.font.size = Pt(body_size_pt)
            p.font.color.rgb = COLORS.rgb_text_on_dark
            p.line_spacing = 1.15

        return card


class MaroonInsightStrip:
    """Renders full-width or compact maroon strip (#6B221C) with icon, title, and body."""

    @classmethod
    def render(
        cls,
        slide: Any,
        x: float,
        y: float,
        w: float,
        h: float,
        text: str,
        highlight_prefix: Optional[str] = None,
        icon_path: Optional[str] = None
    ) -> Any:
        panel = create_solid_shape(
            slide,
            MSO_SHAPE.ROUNDED_RECTANGLE,
            x,
            y,
            w,
            h,
            fill_color=COLORS.rgb_maroon,
            border_color=None,
            shadow=False
        )

        offset_x = 0.25
        if icon_path and os.path.exists(icon_path):
            icon_d = min(0.42, h - 0.20)
            slide.shapes.add_picture(icon_path, Inches(x + 0.20), Inches(y + (h - icon_d) / 2.0), Inches(icon_d), Inches(icon_d))
            offset_x = 0.75

        tb = add_text_box(slide, x + offset_x, y + 0.08, w - offset_x - 0.20, h - 0.16)
        tf = tb.text_frame
        tf.word_wrap = True
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        p = tf.paragraphs[0]
        p.line_spacing = 1.15

        if highlight_prefix:
            r1 = p.add_run()
            r1.text = f"{highlight_prefix}   "
            r1.font.name = FONTS.display
            r1.font.size = Pt(13.0)
            r1.font.bold = True
            r1.font.color.rgb = COLORS.rgb_orange

        r2 = p.add_run()
        r2.text = text
        r2.font.name = FONTS.body
        r2.font.size = Pt(12.0)
        r2.font.color.rgb = COLORS.rgb_text_on_dark

        return panel


class DidYouKnowCard:
    """Renders Did-You-Know historical callout with dark maroon background and gold title."""

    @classmethod
    def render(
        cls,
        slide: Any,
        x: float,
        y: float,
        w: float,
        h: float,
        body_text: str,
        title: str = "DID YOU KNOW?"
    ) -> Any:
        card = create_solid_shape(
            slide,
            MSO_SHAPE.ROUNDED_RECTANGLE,
            x,
            y,
            w,
            h,
            fill_color=COLORS.rgb_maroon,
            border_color=None,
            shadow=True
        )
        pad_x = 0.25
        pad_y = 0.20
        tb = add_text_box(slide, x + pad_x, y + pad_y, w - (2 * pad_x), h - (2 * pad_y))
        tf = tb.text_frame
        tf.word_wrap = True

        p0 = tf.paragraphs[0]
        p0.text = title
        p0.font.name = FONTS.body
        p0.font.size = Pt(11.0)
        p0.font.bold = True
        p0.font.color.rgb = COLORS.rgb_gold
        p0.space_after = Pt(4)

        p1 = tf.add_paragraph()
        p1.text = body_text
        p1.font.name = FONTS.body
        p1.font.size = Pt(12.0)
        p1.font.color.rgb = COLORS.rgb_text_on_dark
        p1.line_spacing = 1.15
        return card


class HeritageGlossaryCard:
    """Renders a single-frame glossary callout with highlighted term and definition."""

    @classmethod
    def render(
        cls,
        slide: Any,
        x: float,
        y: float,
        w: float,
        h: float,
        term: str,
        definition: str,
        icon_path: Optional[str] = None,
        is_maroon: bool = True
    ) -> Any:
        fill_clr = COLORS.rgb_maroon if is_maroon else COLORS.rgb_cream
        border_clr = None if is_maroon else COLORS.rgb_border_warm

        panel = create_solid_shape(
            slide,
            MSO_SHAPE.ROUNDED_RECTANGLE,
            x,
            y,
            w,
            h,
            fill_color=fill_clr,
            border_color=border_clr,
            shadow=False
        )

        offset_x = 0.25
        if icon_path and os.path.exists(icon_path):
            icon_d = min(0.40, h - 0.20)
            slide.shapes.add_picture(icon_path, Inches(x + 0.20), Inches(y + (h - icon_d) / 2.0), Inches(icon_d), Inches(icon_d))
            offset_x = 0.70

        tb = add_text_box(slide, x + offset_x, y + 0.08, w - offset_x - 0.20, h - 0.16)
        tf = tb.text_frame
        tf.word_wrap = True
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE

        p = tf.paragraphs[0]
        p.line_spacing = 1.15

        r1 = p.add_run()
        r1.text = f"{term}   "
        r1.font.name = FONTS.display
        r1.font.size = Pt(13.0)
        r1.font.bold = True
        r1.font.color.rgb = COLORS.rgb_orange if is_maroon else COLORS.rgb_maroon

        r2 = p.add_run()
        r2.text = definition
        r2.font.name = FONTS.body
        r2.font.size = Pt(12.0)
        r2.font.color.rgb = COLORS.rgb_text_on_dark if is_maroon else COLORS.rgb_body

        return panel


class HistoricalImageFrame:
    """Renders an image inside a warm cream frame with caption underneath."""

    @classmethod
    def render(
        cls,
        slide: Any,
        x: float,
        y: float,
        w: float,
        h: float,
        image_path: str,
        caption: Optional[str] = None,
        caption_h: float = 0.45
    ) -> Tuple[Any, Optional[Any]]:
        frame_h = h - caption_h if caption else h
        frame = create_solid_shape(
            slide,
            MSO_SHAPE.ROUNDED_RECTANGLE,
            x,
            y,
            w,
            frame_h,
            fill_color=COLORS.rgb_cream,
            border_color=COLORS.rgb_border_warm,
            shadow=True
        )

        pad = 0.08
        img_x = x + pad
        img_y = y + pad
        img_w = w - (2 * pad)
        img_h = frame_h - (2 * pad)

        if os.path.exists(image_path):
            try:
                slide.shapes.add_picture(image_path, Inches(img_x), Inches(img_y), Inches(img_w), Inches(img_h))
            except Exception as e:
                logger.warning("Could not add picture %s: %s", image_path, e)

        tb_caption = None
        if caption:
            tb_caption = add_text_box(slide, x, y + frame_h + 0.05, w, caption_h - 0.05)
            pc = tb_caption.text_frame.paragraphs[0]
            pc.text = caption
            pc.font.name = FONTS.body
            pc.font.size = Pt(10.5)
            pc.font.italic = True
            pc.font.color.rgb = COLORS.rgb_muted

        return frame, tb_caption


class HistoricalMetricCard:
    """Renders prominent metric card with saffron orange Cambria number and Calibri description."""

    @classmethod
    def render(
        cls,
        slide: Any,
        x: float,
        y: float,
        w: float,
        h: float,
        metric_value: str,
        label: str,
        subtitle: Optional[str] = None
    ) -> Any:
        card = create_solid_shape(
            slide,
            MSO_SHAPE.ROUNDED_RECTANGLE,
            x,
            y,
            w,
            h,
            fill_color=COLORS.rgb_cream,
            border_color=COLORS.rgb_border_warm,
            shadow=True
        )

        pad_x = 0.20
        pad_y = 0.15
        tb = add_text_box(slide, x + pad_x, y + pad_y, w - (2 * pad_x), h - (2 * pad_y))
        tf = tb.text_frame
        tf.word_wrap = True
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE

        p0 = tf.paragraphs[0]
        p0.text = str(metric_value)
        p0.font.name = FONTS.display
        p0.font.size = Pt(30.0)
        p0.font.bold = True
        p0.font.color.rgb = COLORS.rgb_orange
        p0.space_after = Pt(2)

        p1 = tf.add_paragraph()
        p1.text = label
        p1.font.name = FONTS.body
        p1.font.size = Pt(13.0)
        p1.font.bold = True
        p1.font.color.rgb = COLORS.rgb_maroon

        if subtitle:
            p2 = tf.add_paragraph()
            p2.text = subtitle
            p2.font.name = FONTS.body
            p2.font.size = Pt(11.0)
            p2.font.color.rgb = COLORS.rgb_muted

        return card


class MarathaHistoricalQuote:
    """Renders historical quote with large saffron-orange quotation mark and Cambria italic text."""

    @classmethod
    def render(
        cls,
        slide: Any,
        x: float,
        y: float,
        w: float,
        h: float,
        quote_text: str,
        attribution: Optional[str] = None,
        is_dark: bool = True
    ) -> Any:
        tb = add_text_box(slide, x, y, w, h)
        tf = tb.text_frame
        tf.word_wrap = True

        p0 = tf.paragraphs[0]
        p0.text = "“"
        p0.font.name = FONTS.display
        p0.font.size = Pt(48.0)
        p0.font.bold = True
        p0.font.color.rgb = COLORS.rgb_orange
        p0.space_after = Pt(2)

        p1 = tf.add_paragraph()
        p1.text = quote_text
        p1.font.name = FONTS.display
        p1.font.size = Pt(20.0)
        p1.font.italic = True
        p1.font.color.rgb = COLORS.rgb_white if is_dark else COLORS.rgb_maroon
        p1.space_after = Pt(10)
        p1.line_spacing = 1.2

        if attribution:
            p2 = tf.add_paragraph()
            p2.text = f"— {attribution}"
            p2.font.name = FONTS.body
            p2.font.size = Pt(12.0)
            p2.font.color.rgb = COLORS.rgb_gold if is_dark else COLORS.rgb_muted

        return tb


class TimelinePhaseCard:
    """Renders 3-phase chronology column with dark maroon header and cream event card."""

    @classmethod
    def render(
        cls,
        slide: Any,
        x: float,
        y: float,
        w: float,
        h: float,
        phase_title: str,
        date_range: str,
        events: List[Tuple[str, str]]  # [(date_str, desc_str)]
    ):
        header_h = 1.15
        # 1. Dark maroon header card
        h_card = create_solid_shape(
            slide,
            MSO_SHAPE.ROUNDED_RECTANGLE,
            x,
            y,
            w,
            header_h,
            fill_color=COLORS.rgb_maroon,
            border_color=None,
            shadow=False
        )
        tb_h = add_text_box(slide, x + 0.20, y + 0.15, w - 0.40, header_h - 0.30)
        tf_h = tb_h.text_frame
        tf_h.word_wrap = True

        p0 = tf_h.paragraphs[0]
        p0.text = phase_title
        p0.font.name = FONTS.display
        p0.font.size = Pt(15.0)
        p0.font.bold = True
        p0.font.color.rgb = COLORS.rgb_white
        p0.space_after = Pt(2)

        p1 = tf_h.add_paragraph()
        p1.text = date_range
        p1.font.name = FONTS.body
        p1.font.size = Pt(12.5)
        p1.font.bold = True
        p1.font.color.rgb = COLORS.rgb_orange

        # 2. Cream body card
        body_y = y + header_h + 0.12
        body_h = h - header_h - 0.12
        b_card = create_solid_shape(
            slide,
            MSO_SHAPE.ROUNDED_RECTANGLE,
            x,
            body_y,
            w,
            body_h,
            fill_color=COLORS.rgb_cream,
            border_color=COLORS.rgb_border_warm,
            shadow=True
        )

        tb_b = add_text_box(slide, x + 0.22, body_y + 0.20, w - 0.44, body_h - 0.40)
        tf_b = tb_b.text_frame
        tf_b.word_wrap = True

        first = True
        for dt, desc in events:
            p_dt = tf_b.paragraphs[0] if first else tf_b.add_paragraph()
            first = False
            p_dt.text = dt
            p_dt.font.name = FONTS.display
            p_dt.font.size = Pt(13.5)
            p_dt.font.bold = True
            p_dt.font.color.rgb = COLORS.rgb_orange
            p_dt.space_after = Pt(1)

            p_desc = tf_b.add_paragraph()
            p_desc.text = desc
            p_desc.font.name = FONTS.body
            p_desc.font.size = Pt(12.0)
            p_desc.font.color.rgb = COLORS.rgb_body
            p_desc.space_after = Pt(8)
            p_desc.line_spacing = 1.15


class GovernanceHubDiagram:
    """Renders Ashta Pradhana Mandala governance hub: 4 top minister cards, central core node, 4 bottom cards."""

    @classmethod
    def render(
        cls,
        slide: Any,
        x: float,
        y: float,
        w: float,
        h: float,
        center_title: str,
        center_subtitle: str,
        top_cards: List[Tuple[str, str, str]],   # (role, portfolio, person)
        bottom_cards: List[Tuple[str, str, str]]
    ):
        col_count = 4
        card_gap = 0.20
        card_w = (w - (col_count - 1) * card_gap) / col_count
        card_h = 1.50

        top_y = y
        center_y = y + card_h + 0.35
        bottom_y = center_y + 1.20 + 0.35

        # Render 4 Top Cards
        for i in range(min(4, len(top_cards))):
            cx = x + i * (card_w + card_gap)
            cls._render_minister_card(slide, cx, top_y, card_w, card_h, top_cards[i])

        # Central Ruler Core Node (Saffron Orange / Dark Maroon pill)
        center_w = 4.20
        center_h = 1.05
        center_x = x + (w - center_w) / 2.0
        c_node = create_solid_shape(
            slide,
            MSO_SHAPE.ROUNDED_RECTANGLE,
            center_x,
            center_y,
            center_w,
            center_h,
            fill_color=COLORS.rgb_orange,
            border_color=None,
            shadow=True
        )
        tb_c = add_text_box(slide, center_x + 0.15, center_y + 0.12, center_w - 0.30, center_h - 0.24)
        tfc = tb_c.text_frame
        tfc.word_wrap = True
        tfc.vertical_anchor = MSO_ANCHOR.MIDDLE

        p0 = tfc.paragraphs[0]
        p0.alignment = PP_ALIGN.CENTER
        p0.text = center_title
        p0.font.name = FONTS.display
        p0.font.size = Pt(17.0)
        p0.font.bold = True
        p0.font.color.rgb = COLORS.rgb_white
        p0.space_after = Pt(2)

        p1 = tfc.add_paragraph()
        p1.alignment = PP_ALIGN.CENTER
        p1.text = center_subtitle
        p1.font.name = FONTS.body
        p1.font.size = Pt(12.0)
        p1.font.color.rgb = COLORS.rgb_white

        # Render 4 Bottom Cards
        for i in range(min(4, len(bottom_cards))):
            cx = x + i * (card_w + card_gap)
            cls._render_minister_card(slide, cx, bottom_y, card_w, card_h, bottom_cards[i])

    @classmethod
    def _render_minister_card(
        cls,
        slide: Any,
        x: float,
        y: float,
        w: float,
        h: float,
        data: Tuple[str, str, str]
    ):
        role, portfolio, person = data
        header_h = 0.45

        # Header strip (Dark Maroon)
        create_solid_shape(
            slide,
            MSO_SHAPE.ROUNDED_RECTANGLE,
            x,
            y,
            w,
            h,
            fill_color=COLORS.rgb_cream,
            border_color=COLORS.rgb_border_warm,
            shadow=True
        )
        create_solid_shape(
            slide,
            MSO_SHAPE.ROUNDED_RECTANGLE,
            x,
            y,
            w,
            header_h,
            fill_color=COLORS.rgb_maroon,
            border_color=None,
            shadow=False
        )

        # Header role text
        tb_h = add_text_box(slide, x + 0.10, y + 0.08, w - 0.20, header_h - 0.16)
        tf_h = tb_h.text_frame
        p_h = tf_h.paragraphs[0]
        p_h.alignment = PP_ALIGN.CENTER
        p_h.text = role
        p_h.font.name = FONTS.display
        p_h.font.size = Pt(12.5)
        p_h.font.bold = True
        p_h.font.color.rgb = COLORS.rgb_white

        # Body text (Portfolio & Person)
        tb_b = add_text_box(slide, x + 0.12, y + header_h + 0.10, w - 0.24, h - header_h - 0.20)
        tf_b = tb_b.text_frame
        tf_b.word_wrap = True

        p0 = tf_b.paragraphs[0]
        p0.alignment = PP_ALIGN.CENTER
        p0.text = portfolio
        p0.font.name = FONTS.body
        p0.font.size = Pt(11.5)
        p0.font.bold = True
        p0.font.color.rgb = COLORS.rgb_maroon
        p0.space_after = Pt(2)

        if person:
            p1 = tf_b.add_paragraph()
            p1.alignment = PP_ALIGN.CENTER
            p1.text = person
            p1.font.name = FONTS.body
            p1.font.size = Pt(10.5)
            p1.font.color.rgb = COLORS.rgb_muted


class ThreePillarCard:
    """Renders one vertical pillar card (Justice, Trade, Culture) with orange icon badge."""

    @classmethod
    def render(
        cls,
        slide: Any,
        x: float,
        y: float,
        w: float,
        h: float,
        title: str,
        body: str,
        icon_path: Optional[str] = None
    ) -> Any:
        card = create_solid_shape(
            slide,
            MSO_SHAPE.ROUNDED_RECTANGLE,
            x,
            y,
            w,
            h,
            fill_color=COLORS.rgb_cream,
            border_color=COLORS.rgb_border_warm,
            shadow=True
        )

        badge_d = 0.80
        badge_x = x + (w - badge_d) / 2.0
        badge_y = y + 0.30
        IconBadge.render(slide, badge_x, badge_y, diameter=badge_d, icon_path=icon_path)

        tb_title = add_text_box(slide, x + 0.15, y + 1.20, w - 0.30, 0.45)
        pt = tb_title.text_frame.paragraphs[0]
        pt.alignment = PP_ALIGN.CENTER
        pt.text = title
        pt.font.name = FONTS.display
        pt.font.size = Pt(16.0)
        pt.font.bold = True
        pt.font.color.rgb = COLORS.rgb_maroon

        tb_body = add_text_box(slide, x + 0.20, y + 1.70, w - 0.40, h - 1.90)
        tf_b = tb_body.text_frame
        tf_b.word_wrap = True
        pb = tf_b.paragraphs[0]
        pb.text = body
        pb.font.name = FONTS.body
        pb.font.size = Pt(12.5)
        pb.font.color.rgb = COLORS.rgb_body
        pb.line_spacing = 1.15

        return card


class DualBiographyCard:
    """Renders biography card for two leaders / case studies."""

    @classmethod
    def render(
        cls,
        slide: Any,
        x: float,
        y: float,
        w: float,
        h: float,
        name: str,
        role: str,
        bio: str
    ) -> Any:
        card = create_solid_shape(
            slide,
            MSO_SHAPE.ROUNDED_RECTANGLE,
            x,
            y,
            w,
            h,
            fill_color=COLORS.rgb_cream,
            border_color=COLORS.rgb_border_warm,
            shadow=True
        )

        tb = add_text_box(slide, x + 0.25, y + 0.20, w - 0.50, h - 0.40)
        tf = tb.text_frame
        tf.word_wrap = True

        p0 = tf.paragraphs[0]
        p0.text = name
        p0.font.name = FONTS.display
        p0.font.size = Pt(18.0)
        p0.font.bold = True
        p0.font.color.rgb = COLORS.rgb_maroon
        p0.space_after = Pt(2)

        if role:
            p1 = tf.add_paragraph()
            p1.text = role
            p1.font.name = FONTS.body
            p1.font.size = Pt(12.0)
            p1.font.bold = True
            p1.font.color.rgb = COLORS.rgb_gold
            p1.space_after = Pt(8)

        p2 = tf.add_paragraph()
        p2.text = bio
        p2.font.name = FONTS.body
        p2.font.size = Pt(13.0)
        p2.font.color.rgb = COLORS.rgb_body
        p2.line_spacing = 1.15

        return card


class MarathaLegacySummary:
    """Renders full dark maroon summary slide with 5-6 structured takeaway rows, orange check badges, divider, and closing takeaway."""

    @classmethod
    def render(
        cls,
        slide: Any,
        x: float,
        y: float,
        w: float,
        h: float,
        takeaways: List[str],
        final_closing_text: Optional[str] = None
    ):
        n = max(1, len(takeaways))
        row_h = (h - 0.80) / n

        for i, text in enumerate(takeaways):
            iy = y + i * row_h
            # Orange check badge
            CheckBadge.render(slide, x, iy + 0.08, size=0.34)

            # Takeaway text
            tb = add_text_box(slide, x + 0.50, iy, w - 0.50, row_h - 0.06)
            tf = tb.text_frame
            tf.word_wrap = True
            p = tf.paragraphs[0]
            p.text = text
            p.font.name = FONTS.body
            p.font.size = Pt(13.5)
            p.font.color.rgb = COLORS.rgb_text_on_dark
            p.line_spacing = 1.15

        # Thin orange divider line
        divider_y = y + h - 0.65
        div = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x), Inches(divider_y), Inches(1.60), Inches(0.04))
        div.fill.solid()
        div.fill.fore_color.rgb = COLORS.rgb_orange
        div.line.fill.background()

        # Final italic statement
        if final_closing_text:
            tb_f = add_text_box(slide, x, divider_y + 0.12, w, 0.45)
            pf = tb_f.text_frame.paragraphs[0]
            pf.text = final_closing_text
            pf.font.name = FONTS.display
            pf.font.size = Pt(13.5)
            pf.font.italic = True
            pf.font.color.rgb = COLORS.rgb_white
