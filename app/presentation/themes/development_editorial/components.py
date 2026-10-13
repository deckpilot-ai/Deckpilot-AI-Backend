"""Reusable Presentation Primitives for the Development Editorial Theme.

Generates editable PowerPoint shapes, shadows, borders, tables, and typography
matching the exact XML properties of benchmark deck 'Development (2).pptx'.
"""

import io
import math
import logging
from typing import Any, List, Optional, Tuple

from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.xmlchemy import OxmlElement
from pptx.util import Inches, Pt
from PIL import Image as PILImage

from app.presentation.themes.development_editorial.tokens import COLORS, SHADOWS, SPACING, FONTS
from app.presentation.themes.development_editorial.icons import IconResolver
from app.presentation.themes.development_editorial.typography import (
    BUDGETS, fit_font_size, fit_text_to_box, format_kicker_text, normalize_title
)

logger = logging.getLogger(__name__)


def apply_soft_shadow(shape: Any, blur_rad: int = SHADOWS.blur_rad_emu, dist: int = SHADOWS.dist_emu,
                       dir_val: int = SHADOWS.dir_deg, color: str = SHADOWS.color_hex, alpha: int = SHADOWS.alpha_val):
    """Applies the exact DrawingML outer shadow (18% black, 7pt blur, 3pt distance, 90 deg down)."""
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


def create_solid_shape(slide: Any, shape_type: MSO_SHAPE, x: float, y: float, w: float, h: float,
                       fill_color: RGBColor, border_color: Optional[RGBColor] = None,
                       border_width_pt: float = 0.75, shadow: bool = False) -> Any:
    """Helper to create a solid shape with clean styling and optional shadow."""
    shp = slide.shapes.add_shape(shape_type, Inches(x), Inches(y), Inches(w), Inches(h))
    shp.fill.solid()
    shp.fill.fore_color.rgb = fill_color
    if border_color:
        set_shape_border(shp, border_color, border_width_pt)
    else:
        shp.line.fill.background()
    if shadow:
        apply_soft_shadow(shp)
    return shp


def add_text_box(slide: Any, x: float, y: float, w: float, h: float,
                 margin_left: float = 0.0, margin_top: float = 0.0,
                 margin_right: float = 0.0, margin_bottom: float = 0.0) -> Any:
    """Creates a text box with tight zero margins for precision alignment."""
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = Inches(margin_left)
    tf.margin_right = Inches(margin_right)
    tf.margin_top = Inches(margin_top)
    tf.margin_bottom = Inches(margin_bottom)
    return tb


class SlideKicker:
    """Renders the signature mustard dot and tracked uppercase kicker label."""
    @classmethod
    def render(cls, slide: Any, kicker_text: str, is_dark: bool = False, y: float = 0.48):
        dot_color = COLORS.rgb_gold
        text_color = COLORS.rgb_gold_light if is_dark else COLORS.rgb_gold
        
        # 1. Mustard dot
        dot = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(0.60), Inches(y + 0.08), Inches(0.16), Inches(0.16))
        dot.fill.solid()
        dot.fill.fore_color.rgb = dot_color
        dot.line.fill.background()
        
        # 2. Kicker Text
        tb = add_text_box(slide, 0.88, y, 9.00, 0.36)
        p = tb.text_frame.paragraphs[0]
        p.text = format_kicker_text(kicker_text)
        p.font.name = FONTS.body
        p.font.size = Pt(13.0)
        p.font.bold = True
        p.font.color.rgb = text_color


class SlideTitle:
    """Renders standard 33pt Cambria slide title."""
    @classmethod
    def render(cls, slide: Any, title_text: str, is_dark: bool = False, x: float = 0.60, y: float = 0.86, w: float = 12.10, h: float = 0.85):
        clean_title, subtitle = normalize_title(title_text)
        text_color = COLORS.rgb_white if is_dark else COLORS.rgb_ink
        
        tb = add_text_box(slide, x, y, w, h)
        p = tb.text_frame.paragraphs[0]
        p.text = clean_title
        p.font.name = FONTS.display
        p.font.size = Pt(33.0 if len(clean_title) <= 50 else 28.0)
        p.font.bold = True
        p.font.color.rgb = text_color
        return clean_title, subtitle


class SlideSubtitle:
    """Renders editorial lead prose below title."""
    @classmethod
    def render(cls, slide: Any, text: str, is_dark: bool = False, x: float = 0.60, y: float = 1.70, w: float = 12.10, h: float = 0.85):
        if not text:
            return
        text_color = COLORS.rgb_text_on_dark if is_dark else COLORS.rgb_ink
        tb = add_text_box(slide, x, y, w, h)
        p = tb.text_frame.paragraphs[0]
        p.text = str(text).strip()
        p.font.name = FONTS.body
        p.font.size = Pt(15.5)
        p.font.color.rgb = text_color
        p.line_spacing = 1.15


class IconBadge:
    """Circular badge with green or gold background and centered authentic icon or relatable emoji."""
    @classmethod
    def render(cls, slide: Any, x: float, y: float, diameter: float = 0.70,
               bg_color: Optional[RGBColor] = None, title: str = "", body: str = "",
               icon_bytes: Optional[bytes] = None, emoji_char: Optional[str] = None,
               symbol_text: Optional[str] = None, default_index: int = 0):
        col = bg_color or COLORS.rgb_green_primary
        badge = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(x), Inches(y), Inches(diameter), Inches(diameter))
        badge.fill.solid()
        badge.fill.fore_color.rgb = col
        badge.line.fill.background()
        apply_soft_shadow(badge)

        # 1. Resolve authentic icon or relatable emoji if not explicitly supplied
        if not icon_bytes and not emoji_char:
            if symbol_text and len(symbol_text) == 1 and ord(symbol_text) > 127:
                emoji_char = symbol_text
            else:
                res_icon, res_emoji = IconResolver.resolve(title, body, default_index=default_index)
                icon_bytes = res_icon
                emoji_char = res_emoji

        # If emoji_char is provided without icon_bytes, check if an authentic icon file exists for it
        if not icon_bytes and emoji_char:
            import os
            from app.presentation.themes.development_editorial.icons import EMOJI_TO_ICON_FILE, ICONS_DIR
            clean_emoji = emoji_char.replace("\ufe0f", "")
            for e_key, icon_fname in EMOJI_TO_ICON_FILE.items():
                if e_key.replace("\ufe0f", "") == clean_emoji:
                    p_file = os.path.join(ICONS_DIR, icon_fname)
                    if os.path.exists(p_file):
                        try:
                            with open(p_file, "rb") as f:
                                icon_bytes = f.read()
                            break
                        except Exception:
                            pass

        # 2. Render authentic white icon picture if available (responsive 64% sizing)
        if icon_bytes and len(icon_bytes) > 50:
            try:
                icon_sz = round(diameter * 0.64, 2)
                pad = (diameter - icon_sz) / 2.0
                stream = io.BytesIO(icon_bytes)
                slide.shapes.add_picture(stream, Inches(x + pad), Inches(y + pad), Inches(icon_sz), Inches(icon_sz))
                return badge
            except Exception as e:
                logger.debug("Failed to render icon picture in badge: %s", e)

        # 3. Render relatable Unicode emoji (responsive 60% container sizing with middle vertical anchor)
        if emoji_char:
            tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(diameter), Inches(diameter))
            tf = tb.text_frame
            tf.word_wrap = False
            tf.vertical_anchor = MSO_ANCHOR.MIDDLE
            tf.margin_left = Inches(0)
            tf.margin_right = Inches(0)
            tf.margin_top = Inches(0)
            tf.margin_bottom = Inches(0)
            p = tf.paragraphs[0]
            p.alignment = PP_ALIGN.CENTER
            p.text = emoji_char
            p.font.name = "Segoe UI Emoji"
            p.font.size = Pt(round(diameter * 38.0, 1))
            p.font.color.rgb = COLORS.rgb_white
            p.space_before = Pt(0)
            p.space_after = Pt(0)
            return badge

        # 4. Fallback symbol text
        if symbol_text:
            tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(diameter), Inches(diameter))
            tf = tb.text_frame
            tf.word_wrap = False
            tf.vertical_anchor = MSO_ANCHOR.MIDDLE
            tf.margin_left = Inches(0)
            tf.margin_right = Inches(0)
            tf.margin_top = Inches(0)
            tf.margin_bottom = Inches(0)
            p = tf.paragraphs[0]
            p.alignment = PP_ALIGN.CENTER
            p.text = str(symbol_text)[:2]
            p.font.name = FONTS.body
            p.font.size = Pt(round(diameter * 24.0, 1))
            p.font.bold = True
            p.font.color.rgb = COLORS.rgb_white
            p.space_before = Pt(0)
            p.space_after = Pt(0)

        return badge


class InfoCard:
    """Light information card with soft drop shadow, mint border, and dynamic overflow protection."""
    @classmethod
    def render(cls, slide: Any, x: float, y: float, w: float, h: float,
               title: Optional[str] = None, body: Optional[str] = None,
               ghost_no: Optional[str] = None, icon_color: Optional[RGBColor] = None,
               icon_bytes: Optional[bytes] = None, emoji_char: Optional[str] = None,
               default_index: int = 0):
        # 1. Base shape
        card = create_solid_shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, x, y, w, h,
                                  COLORS.rgb_panel, COLORS.rgb_panel_border, 0.75, shadow=True)

        # 2. Horizontal layout when card is wide (w >= 5.0 or h <= 1.8)
        if w >= 5.0 or h <= 1.8:
            pad_x = 0.28
            if icon_color:
                badge_d = min(0.70, max(0.54, h - 0.35))
                badge_y = y + (h - badge_d) / 2.0
                IconBadge.render(slide, x + pad_x, badge_y, diameter=badge_d, bg_color=icon_color,
                                title=title or "", body=body or "",
                                icon_bytes=icon_bytes, emoji_char=emoji_char, default_index=default_index)
                text_x = x + pad_x + badge_d + 0.20
                text_w = w - (text_x - x) - pad_x
            else:
                text_x = x + pad_x
                text_w = w - (pad_x * 2)

            avail_h = h - 0.26
            if title and body:
                title_h = min(0.42, avail_h * 0.45)
                tb_t = add_text_box(slide, text_x, y + 0.14, text_w, title_h, margin_left=0, margin_top=0)
                p_t = tb_t.text_frame.paragraphs[0]
                p_t.text = str(title).strip()
                p_t.font.name = FONTS.display
                p_t.font.size = Pt(15.0)
                p_t.font.bold = True
                p_t.font.color.rgb = COLORS.rgb_ink
                p_t.space_before = Pt(0)
                p_t.space_after = Pt(0)

                body_y = y + 0.14 + title_h + 0.04
                avail_b_h = max(0.20, (y + h - 0.12) - body_y)
                b_text, b_pt, _ = fit_text_to_box(body, text_w, avail_b_h, preferred_pt=12.0, min_pt=10.5)
                tb_b = add_text_box(slide, text_x, body_y, text_w, avail_b_h, margin_left=0, margin_top=0)
                p_b = tb_b.text_frame.paragraphs[0]
                p_b.text = b_text
                p_b.font.name = FONTS.body
                p_b.font.size = Pt(b_pt)
                p_b.font.color.rgb = COLORS.rgb_ink_muted
                p_b.space_before = Pt(0)
                p_b.space_after = Pt(0)
                p_b.line_spacing = 1.15
            elif title:
                tb_t = add_text_box(slide, text_x, y + 0.14, text_w, avail_h, margin_left=0, margin_top=0)
                p_t = tb_t.text_frame.paragraphs[0]
                p_t.text = str(title).strip()
                p_t.font.name = FONTS.display
                p_t.font.size = Pt(15.5)
                p_t.font.bold = True
                p_t.font.color.rgb = COLORS.rgb_ink
            elif body:
                b_text, b_pt, _ = fit_text_to_box(body, text_w, avail_h, preferred_pt=12.0, min_pt=10.5)
                tb_b = add_text_box(slide, text_x, y + 0.14, text_w, avail_h, margin_left=0, margin_top=0)
                p_b = tb_b.text_frame.paragraphs[0]
                p_b.text = b_text
                p_b.font.name = FONTS.body
                p_b.font.size = Pt(b_pt)
                p_b.font.color.rgb = COLORS.rgb_ink_muted
                p_b.line_spacing = 1.15

            return card

        # 3. Vertical stacked layout for columns & grids (unified alignment)
        pad_x = 0.28
        content_w = w - (pad_x * 2)

        # Ghost number if provided (neatly anchored top-right)
        if ghost_no:
            tb_ghost = add_text_box(slide, x + w - pad_x - 0.70, y + 0.16, 0.70, 0.40, margin_left=0, margin_top=0)
            p_g = tb_ghost.text_frame.paragraphs[0]
            p_g.alignment = PP_ALIGN.RIGHT
            p_g.text = str(ghost_no).zfill(2)
            p_g.font.name = FONTS.display
            p_g.font.size = Pt(24.0 if h <= 2.4 else 26.0)
            p_g.font.bold = True
            p_g.font.color.rgb = COLORS.rgb_number_ghost

        # Icon Badge if provided
        is_compact = (h <= 2.4)
        if icon_color:
            badge_d = 0.68 if is_compact else 0.72
            badge_x = x + pad_x
            badge_y = y + (0.18 if is_compact else 0.22)
            IconBadge.render(slide, badge_x, badge_y, diameter=badge_d, bg_color=icon_color,
                            title=title or "", body=body or "",
                            icon_bytes=icon_bytes, emoji_char=emoji_char, default_index=default_index)
            title_top = badge_y + badge_d + (0.10 if is_compact else 0.14)
        else:
            title_top = y + (0.20 if is_compact else 0.26)

        # Standardized Title and Body baseline alignment across all cards in the row
        if title and body:
            title_h = 0.44 if is_compact else 0.54
            t_text, t_pt, _ = fit_text_to_box(title, content_w, title_h, preferred_pt=15.5 if is_compact else 16.5, min_pt=13.5)
            tb_t = add_text_box(slide, x + pad_x, title_top, content_w, title_h, margin_left=0, margin_top=0)
            p_t = tb_t.text_frame.paragraphs[0]
            p_t.text = t_text
            p_t.font.name = FONTS.display
            p_t.font.size = Pt(t_pt)
            p_t.font.bold = True
            p_t.font.color.rgb = COLORS.rgb_ink
            p_t.space_before = Pt(0)
            p_t.space_after = Pt(0)

            body_top = title_top + title_h + (0.02 if is_compact else 0.05)
            body_h = max(0.20, (y + h - 0.10) - body_top)
            b_text, b_pt, _ = fit_text_to_box(body, content_w, body_h, preferred_pt=12.0 if is_compact else 13.0, min_pt=11.0)
            tb_b = add_text_box(slide, x + pad_x, body_top, content_w, body_h, margin_left=0, margin_top=0)
            p_b = tb_b.text_frame.paragraphs[0]
            p_b.text = b_text
            p_b.font.name = FONTS.body
            p_b.font.size = Pt(b_pt)
            p_b.font.color.rgb = COLORS.rgb_ink_muted
            p_b.space_before = Pt(0)
            p_b.space_after = Pt(0)
            p_b.line_spacing = 1.15
        elif title:
            rem_h = max(0.30, (y + h - 0.12) - title_top)
            t_text, t_pt, _ = fit_text_to_box(title, content_w, rem_h, preferred_pt=15.5, min_pt=13.0)
            tb_t = add_text_box(slide, x + pad_x, title_top, content_w, rem_h, margin_left=0, margin_top=0)
            p_t = tb_t.text_frame.paragraphs[0]
            p_t.text = t_text
            p_t.font.name = FONTS.display
            p_t.font.size = Pt(t_pt)
            p_t.font.bold = True
            p_t.font.color.rgb = COLORS.rgb_ink
        elif body:
            rem_h = max(0.30, (y + h - 0.12) - title_top)
            b_text, b_pt, _ = fit_text_to_box(body, content_w, rem_h, preferred_pt=12.0, min_pt=10.5)
            tb_b = add_text_box(slide, x + pad_x, title_top, content_w, rem_h, margin_left=0, margin_top=0)
            p_b = tb_b.text_frame.paragraphs[0]
            p_b.text = b_text
            p_b.font.name = FONTS.body
            p_b.font.size = Pt(b_pt)
            p_b.font.color.rgb = COLORS.rgb_ink_muted
            p_b.line_spacing = 1.15

        return card


class DarkInfoCard:
    """Dark green card used on dark section slides with dynamic overflow protection."""
    @classmethod
    def render(cls, slide: Any, x: float, y: float, w: float, h: float,
               title: Optional[str] = None, body: Optional[str] = None,
               icon_color: Optional[RGBColor] = None,
               icon_bytes: Optional[bytes] = None, emoji_char: Optional[str] = None,
               default_index: int = 0):
        card = create_solid_shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, x, y, w, h,
                                  COLORS.rgb_green_dark, COLORS.rgb_green_mid, 1.0, shadow=False)
        
        # 1. Horizontal layout when card is wide (w >= 5.0 or h <= 1.8)
        if w >= 5.0 or h <= 1.8:
            pad_x = 0.28
            badge_d = min(0.70, max(0.54, h - 0.35))
            badge_y = y + (h - badge_d) / 2.0
            col = icon_color or COLORS.rgb_green_mid
            IconBadge.render(slide, x + pad_x, badge_y, diameter=badge_d, bg_color=col,
                            title=title or "", body=body or "",
                            icon_bytes=icon_bytes, emoji_char=emoji_char, default_index=default_index)
            text_x = x + pad_x + badge_d + 0.20
            text_w = w - (text_x - x) - pad_x
            avail_h = h - 0.26

            if title and body:
                title_h = min(0.42, avail_h * 0.45)
                tb_t = add_text_box(slide, text_x, y + 0.14, text_w, title_h, margin_left=0, margin_top=0)
                p_t = tb_t.text_frame.paragraphs[0]
                p_t.text = str(title).strip()
                p_t.font.name = FONTS.display
                p_t.font.size = Pt(15.0)
                p_t.font.bold = True
                p_t.font.color.rgb = COLORS.rgb_white
                p_t.space_before = Pt(0)
                p_t.space_after = Pt(0)

                body_y = y + 0.14 + title_h + 0.04
                avail_b_h = max(0.20, (y + h - 0.12) - body_y)
                b_text, b_pt, _ = fit_text_to_box(body, text_w, avail_b_h, preferred_pt=12.0, min_pt=10.5)
                tb_b = add_text_box(slide, text_x, body_y, text_w, avail_b_h, margin_left=0, margin_top=0)
                p_b = tb_b.text_frame.paragraphs[0]
                p_b.text = b_text
                p_b.font.name = FONTS.body
                p_b.font.size = Pt(b_pt)
                p_b.font.color.rgb = COLORS.rgb_panel_border
                p_b.space_before = Pt(0)
                p_b.space_after = Pt(0)
                p_b.line_spacing = 1.15
            elif title:
                tb_t = add_text_box(slide, text_x, y + 0.14, text_w, avail_h, margin_left=0, margin_top=0)
                p_t = tb_t.text_frame.paragraphs[0]
                p_t.text = str(title).strip()
                p_t.font.name = FONTS.display
                p_t.font.size = Pt(15.5)
                p_t.font.bold = True
                p_t.font.color.rgb = COLORS.rgb_white
            elif body:
                b_text, b_pt, _ = fit_text_to_box(body, text_w, avail_h, preferred_pt=12.0, min_pt=10.5)
                tb_b = add_text_box(slide, text_x, y + 0.14, text_w, avail_h, margin_left=0, margin_top=0)
                p_b = tb_b.text_frame.paragraphs[0]
                p_b.text = b_text
                p_b.font.name = FONTS.body
                p_b.font.size = Pt(b_pt)
                p_b.font.color.rgb = COLORS.rgb_panel_border
                p_b.line_spacing = 1.15
            return card

        # 2. Vertical stacked layout for columns & grids on dark slides
        pad_x = 0.28
        content_w = w - (pad_x * 2)
        is_compact = (h <= 2.4)
        col = icon_color or COLORS.rgb_green_mid
        badge_d = 0.68 if is_compact else 0.72
        badge_x = x + pad_x
        badge_y = y + (0.18 if is_compact else 0.22)
        IconBadge.render(slide, badge_x, badge_y, diameter=badge_d, bg_color=col,
                        title=title or "", body=body or "",
                        icon_bytes=icon_bytes, emoji_char=emoji_char, default_index=default_index)
        title_top = badge_y + badge_d + (0.10 if is_compact else 0.14)

        if title and body:
            title_h = 0.44 if is_compact else 0.54
            t_text, t_pt, _ = fit_text_to_box(title, content_w, title_h, preferred_pt=15.5 if is_compact else 16.5, min_pt=13.5)
            tb_t = add_text_box(slide, x + pad_x, title_top, content_w, title_h, margin_left=0, margin_top=0)
            p_t = tb_t.text_frame.paragraphs[0]
            p_t.text = t_text
            p_t.font.name = FONTS.display
            p_t.font.size = Pt(t_pt)
            p_t.font.bold = True
            p_t.font.color.rgb = COLORS.rgb_white
            p_t.space_before = Pt(0)
            p_t.space_after = Pt(0)

            body_top = title_top + title_h + (0.02 if is_compact else 0.05)
            body_h = max(0.20, (y + h - 0.10) - body_top)
            b_text, b_pt, _ = fit_text_to_box(body, content_w, body_h, preferred_pt=12.0 if is_compact else 13.0, min_pt=11.0)
            tb_b = add_text_box(slide, x + pad_x, body_top, content_w, body_h, margin_left=0, margin_top=0)
            p_b = tb_b.text_frame.paragraphs[0]
            p_b.text = b_text
            p_b.font.name = FONTS.body
            p_b.font.size = Pt(b_pt)
            p_b.font.color.rgb = COLORS.rgb_panel_border
            p_b.space_before = Pt(0)
            p_b.space_after = Pt(0)
            p_b.line_spacing = 1.15
        elif title:
            rem_h = max(0.30, (y + h - 0.12) - title_top)
            t_text, t_pt, _ = fit_text_to_box(title, content_w, rem_h, preferred_pt=15.5, min_pt=13.0)
            tb_t = add_text_box(slide, x + pad_x, title_top, content_w, rem_h, margin_left=0, margin_top=0)
            p_t = tb_t.text_frame.paragraphs[0]
            p_t.text = t_text
            p_t.font.name = FONTS.display
            p_t.font.size = Pt(t_pt)
            p_t.font.bold = True
            p_t.font.color.rgb = COLORS.rgb_white
        elif body:
            rem_h = max(0.30, (y + h - 0.12) - title_top)
            b_text, b_pt, _ = fit_text_to_box(body, content_w, rem_h, preferred_pt=12.0, min_pt=10.5)
            tb_b = add_text_box(slide, x + pad_x, title_top, content_w, rem_h, margin_left=0, margin_top=0)
            p_b = tb_b.text_frame.paragraphs[0]
            p_b.text = b_text
            p_b.font.name = FONTS.body
            p_b.font.size = Pt(b_pt)
            p_b.font.color.rgb = COLORS.rgb_panel_border
            p_b.line_spacing = 1.15

        return card


class QuoteCard:
    """Warm cream card with dark gold text for quotes, reflections, and cautions with dynamic fitting."""
    @classmethod
    def render(cls, slide: Any, x: float, y: float, w: float, h: float,
               quote_text: str, attribution: Optional[str] = None,
               strong_border: bool = False):
        border_col = COLORS.rgb_gold if strong_border else COLORS.rgb_quote_border
        card = create_solid_shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, x, y, w, h,
                                  COLORS.rgb_quote, border_col, 0.85, shadow=True)
        
        avail_h = max(0.40, h - 0.45 - (0.50 if attribution else 0.0))
        q_clean = f'"{quote_text.strip()}"' if not quote_text.strip().startswith('"') else quote_text.strip()
        q_fit, q_pt, q_est_h = fit_text_to_box(q_clean, w - 0.70, avail_h, preferred_pt=18.0, min_pt=12.5, line_spacing=1.15)

        tb = add_text_box(slide, x + 0.35, y + 0.20, w - 0.70, q_est_h)
        p = tb.text_frame.paragraphs[0]
        p.text = q_fit
        p.font.name = FONTS.display
        p.font.size = Pt(q_pt)
        p.font.bold = True
        p.font.color.rgb = COLORS.rgb_quote_text
        p.line_spacing = 1.15
        
        if attribution:
            att_y = max(y + 0.20 + q_est_h + 0.08, y + h - 0.45)
            att_y = min(y + h - 0.36, att_y)
            tb_att = add_text_box(slide, x + 0.35, att_y, w - 0.70, 0.30)
            p_att = tb_att.text_frame.paragraphs[0]
            p_att.text = f"— {attribution.strip()}"
            p_att.font.name = FONTS.body
            p_att.font.size = Pt(11.5)
            p_att.font.bold = True
            p_att.font.color.rgb = COLORS.rgb_gold
        return card


class MetricCard:
    """Vertical KPI card with Cambria 34pt number and explanatory text with dynamic fitting."""
    @classmethod
    def render(cls, slide: Any, x: float, y: float, w: float, h: float,
               value: str, label: str, subtext: Optional[str] = None,
               is_warning: bool = False):
        bg = COLORS.rgb_quote if is_warning else COLORS.rgb_panel
        border = COLORS.rgb_quote_border if is_warning else COLORS.rgb_panel_border
        val_color = COLORS.rgb_gold if is_warning else COLORS.rgb_green_primary
        
        create_solid_shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, x, y, w, h, bg, border, 0.75, shadow=True)
        
        # Value text
        tb = add_text_box(slide, x + 0.25, y + 0.20, w - 0.50, 0.65)
        p_v = tb.text_frame.paragraphs[0]
        p_v.text = str(value).strip()
        p_v.font.name = FONTS.display
        p_v.font.size = Pt(32.0)
        p_v.font.bold = True
        p_v.font.color.rgb = val_color
        
        # Label
        l_clean, l_pt, l_est_h = fit_text_to_box(label, w - 0.50, 0.45, preferred_pt=16.0, min_pt=13.5)
        tb_l = add_text_box(slide, x + 0.25, y + 0.86, w - 0.50, l_est_h)
        p_l = tb_l.text_frame.paragraphs[0]
        p_l.text = l_clean
        p_l.font.name = FONTS.display
        p_l.font.size = Pt(l_pt)
        p_l.font.bold = True
        p_l.font.color.rgb = COLORS.rgb_ink
        
        if subtext:
            cur_y = y + 0.86 + l_est_h + 0.04
            avail_s_h = max(0.25, (y + h - 0.14) - cur_y)
            s_clean, s_pt, _ = fit_text_to_box(subtext, w - 0.50, avail_s_h, preferred_pt=12.0, min_pt=10.5)
            tb_s = add_text_box(slide, x + 0.25, cur_y, w - 0.50, avail_s_h)
            p_s = tb_s.text_frame.paragraphs[0]
            p_s.text = s_clean
            p_s.font.name = FONTS.body
            p_s.font.size = Pt(s_pt)
            p_s.font.color.rgb = COLORS.rgb_ink_muted
            p_s.line_spacing = 1.15


class HorizontalMetricCard:
    """Horizontal metric row with number on left, vertical divider, description right."""
    @classmethod
    def render(cls, slide: Any, x: float, y: float, w: float, h: float,
               value: str, label: str, description: Optional[str] = None,
               is_warning: bool = False):
        bg = COLORS.rgb_quote if is_warning else COLORS.rgb_panel
        border = COLORS.rgb_quote_border if is_warning else COLORS.rgb_panel_border
        val_color = COLORS.rgb_gold if is_warning else COLORS.rgb_green_primary
        
        create_solid_shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, x, y, w, h, bg, border, 0.75, shadow=True)
        
        # Stat value on left
        tb_val = add_text_box(slide, x + 0.20, y + 0.10, 2.00, h - 0.20)
        p_v = tb_val.text_frame.paragraphs[0]
        p_v.text = str(value).strip()
        p_v.font.name = FONTS.display
        p_v.font.size = Pt(30.0 if len(str(value)) <= 8 else 24.0)
        p_v.font.bold = True
        p_v.font.color.rgb = val_color
        
        # Thin vertical divider
        div = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x + 2.30), Inches(y + 0.15), Inches(0.02), Inches(h - 0.30))
        div.fill.solid()
        div.fill.fore_color.rgb = COLORS.rgb_divider
        div.line.fill.background()
        
        # Explanation on right
        text_w = w - 2.65
        avail_h = h - 0.24
        if label and description:
            l_clean, l_pt, l_est_h = fit_text_to_box(label, text_w, min(0.38, avail_h * 0.45), preferred_pt=15.0, min_pt=13.0)
            tb_l = add_text_box(slide, x + 2.45, y + 0.12, text_w, l_est_h)
            p_l = tb_l.text_frame.paragraphs[0]
            p_l.text = l_clean
            p_l.font.name = FONTS.display
            p_l.font.size = Pt(l_pt)
            p_l.font.bold = True
            p_l.font.color.rgb = COLORS.rgb_ink

            desc_y = y + 0.12 + l_est_h + 0.03
            avail_d_h = max(0.20, (y + h - 0.12) - desc_y)
            d_clean, d_pt, _ = fit_text_to_box(description, text_w, avail_d_h, preferred_pt=12.0, min_pt=10.5)
            tb_d = add_text_box(slide, x + 2.45, desc_y, text_w, avail_d_h)
            p_d = tb_d.text_frame.paragraphs[0]
            p_d.text = d_clean
            p_d.font.name = FONTS.body
            p_d.font.size = Pt(d_pt)
            p_d.font.color.rgb = COLORS.rgb_ink_muted
            p_d.line_spacing = 1.15
        elif label:
            l_clean, l_pt, _ = fit_text_to_box(label, text_w, avail_h, preferred_pt=15.0, min_pt=13.0)
            tb_l = add_text_box(slide, x + 2.45, y + 0.12, text_w, avail_h)
            p_l = tb_l.text_frame.paragraphs[0]
            p_l.text = l_clean
            p_l.font.name = FONTS.display
            p_l.font.size = Pt(l_pt)
            p_l.font.bold = True
            p_l.font.color.rgb = COLORS.rgb_ink


class ImageFrame:
    """Clean photo mat card preserving aspect ratio and preventing distortion."""
    @classmethod
    def render(cls, slide: Any, x: float, y: float, w: float, h: float,
               image_bytes: Optional[bytes] = None, caption: Optional[str] = None,
               warm_card: bool = False):
        bg = COLORS.rgb_warm_frame if warm_card else COLORS.rgb_white
        border = COLORS.rgb_gold if warm_card else COLORS.rgb_image_border
        
        # Outer Mat Card with Shadow
        create_solid_shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, x, y, w, h, bg, border, 0.75, shadow=True)
        
        pad = 0.14
        inner_x = x + pad
        inner_y = y + pad
        inner_w = w - (pad * 2)
        inner_h = h - (pad * 2) - (0.35 if caption else 0.0)
        
        if image_bytes and len(image_bytes) > 100:
            try:
                # Aspect ratio fitting
                stream = io.BytesIO(image_bytes)
                with PILImage.open(stream) as pil_img:
                    orig_w, orig_h = pil_img.size
                
                scale = min(inner_w / orig_w, inner_h / orig_h)
                final_w = orig_w * scale
                final_h = orig_h * scale
                pos_x = inner_x + (inner_w - final_w) / 2.0
                pos_y = inner_y + (inner_h - final_h) / 2.0
                
                img_stream = io.BytesIO(image_bytes)
                slide.shapes.add_picture(img_stream, Inches(pos_x), Inches(pos_y), Inches(final_w), Inches(final_h))
            except Exception as e:
                logger.warning("Could not render image bytes: %s", e)
        
        # Caption below image if present
        if caption:
            tb = add_text_box(slide, x + pad, y + h - 0.38, inner_w, 0.30)
            p = tb.text_frame.paragraphs[0]
            p.text = str(caption).strip()
            p.font.name = FONTS.body
            p.font.size = Pt(10.5)
            p.font.italic = True
            p.font.color.rgb = COLORS.rgb_ink_muted


class GhostNumber:
    """Renders 26pt bold Cambria ghost sequence number (e.g. 01, 02)."""
    @classmethod
    def render(cls, slide: Any, x: float, y: float, w: float = 0.85, h: float = 0.55, number_str: str = "01"):
        tb = add_text_box(slide, x, y, w, h)
        p = tb.text_frame.paragraphs[0]
        p.alignment = PP_ALIGN.RIGHT
        p.text = str(number_str).zfill(2)
        p.font.name = FONTS.display
        p.font.size = Pt(26.0)
        p.font.bold = True
        p.font.color.rgb = COLORS.rgb_number_ghost
        return tb


class SummaryStrip:
    """High-contrast takeaway strip at the bottom of slides with dynamic text fitting."""
    @classmethod
    def render(cls, slide: Any, x: float, y: float, w: float, h: float,
               headline: str, text: str):
        create_solid_shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, x, y, w, h,
                           COLORS.rgb_green_dark, COLORS.rgb_green_dark, 0.75, shadow=True)
        
        text_w = w - 0.60
        avail_h = h - 0.22
        tb = add_text_box(slide, x + 0.30, y + 0.11, text_w, avail_h)
        p = tb.text_frame.paragraphs[0]
        
        full_combined = f"{headline.strip()}: {text.strip()}" if headline else text.strip()
        c_clean, c_pt, _ = fit_text_to_box(full_combined, text_w, avail_h, preferred_pt=13.0, min_pt=10.5)
        
        if headline and c_clean.startswith(f"{headline.strip()}:"):
            body_part = c_clean[len(f"{headline.strip()}:"):].strip()
            run_h = p.add_run()
            run_h.text = f"{headline.strip()}: "
            run_h.font.name = FONTS.display
            run_h.font.size = Pt(c_pt + 1.0)
            run_h.font.bold = True
            run_h.font.color.rgb = COLORS.rgb_white
            
            run_t = p.add_run()
            run_t.text = body_part
            run_t.font.name = FONTS.body
            run_t.font.size = Pt(c_pt)
            run_t.font.color.rgb = COLORS.rgb_text_on_dark
        else:
            run_t = p.add_run()
            run_t.text = c_clean
            run_t.font.name = FONTS.body
            run_t.font.size = Pt(c_pt)
            run_t.font.color.rgb = COLORS.rgb_white


class StyledTable:
    """Editorial table with green header and clean rows."""
    @classmethod
    def render(cls, slide: Any, x: float, y: float, w: float, h: float,
               headers: List[str], rows: List[List[str]]):
        rows_count = len(rows) + 1
        cols_count = len(headers)
        table_shape = slide.shapes.add_table(rows_count, cols_count, Inches(x), Inches(y), Inches(w), Inches(h))
        table = table_shape.table
        
        # Header formatting
        for c_idx, h_text in enumerate(headers):
            cell = table.cell(0, c_idx)
            cell.fill.solid()
            cell.fill.fore_color.rgb = COLORS.rgb_green_primary
            p = cell.text_frame.paragraphs[0]
            p.text = str(h_text).strip()
            p.font.name = FONTS.body
            p.font.size = Pt(12.0)
            p.font.bold = True
            p.font.color.rgb = COLORS.rgb_white
            p.alignment = PP_ALIGN.CENTER if c_idx > 0 else PP_ALIGN.LEFT
            
        # Data rows formatting
        for r_idx, row_data in enumerate(rows):
            for c_idx, val in enumerate(row_data):
                cell = table.cell(r_idx + 1, c_idx)
                cell.fill.solid()
                cell.fill.fore_color.rgb = COLORS.rgb_panel if (r_idx % 2 == 1) else COLORS.rgb_white
                p = cell.text_frame.paragraphs[0]
                p.text = str(val).strip()
                p.font.name = FONTS.body
                p.font.size = Pt(11.5)
                p.font.color.rgb = COLORS.rgb_ink
                p.alignment = PP_ALIGN.CENTER if c_idx > 0 else PP_ALIGN.LEFT
        return table_shape


class EditorialDivider:
    """Hairline divider line."""
    @classmethod
    def render(cls, slide: Any, x: float, y: float, w: float, color: Optional[RGBColor] = None):
        col = color or COLORS.rgb_divider
        line = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(0.015))
        line.fill.solid()
        line.fill.fore_color.rgb = col
        line.line.fill.background()
        return line
