"""Reusable Presentation Primitives for Federalism Editorial Theme.

Generates editable PowerPoint shapes, shadows, borders, tables, and typography
matching the exact XML properties of benchmark deck 'Federalism (2).pptx'.
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

from app.presentation.themes.federalism_editorial.tokens import COLORS, SHADOWS, SPACING, FONTS, GEOMETRY
from app.presentation.themes.federalism_editorial.icons import IconResolver, calculate_responsive_icon_size
from app.presentation.themes.federalism_editorial.typography import (
    BUDGETS, fit_text_to_box, format_kicker_text, TitleOptimizer, TextMeasurementService
)

logger = logging.getLogger(__name__)


def apply_soft_shadow(shape: Any, blur_rad: int = SHADOWS.blur_rad_emu, dist: int = SHADOWS.dist_emu,
                       dir_val: int = SHADOWS.dir_deg, color: str = SHADOWS.color_hex, alpha: int = SHADOWS.alpha_val):
    """Applies the exact DrawingML outer shadow (18% black, 9pt blur, 3pt distance, 90 deg down)."""
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
                       border_width_pt: float = 0.75, shadow: bool = False,
                       corner_radius_pct: Optional[float] = None) -> Any:
    """Helper to create a solid shape with clean styling, subtle corner radius, and optional shadow."""
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
                # Authentic editorial corner radius: ~0.16 inches subtle curve, matching reference PPTX (0.022–0.04)
                min_dim = max(0.1, min(w, h))
                shp.adjustments[0] = min(0.06, max(0.022, 0.16 / min_dim))
        except Exception:
            pass
    return shp


def add_text_box(slide: Any, x: float, y: float, w: float, h: float,
                 margin_left: float = 0.0, margin_top: float = 0.0,
                 margin_right: float = 0.0, margin_bottom: float = 0.0,
                 name: Optional[str] = None) -> Any:
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


class SlideKicker:
    """Renders uppercase tracked kicker in accent orange."""
    @classmethod
    def render(cls, slide: Any, text: str, is_dark: bool = False, x: float = GEOMETRY.safe_left, y: float = GEOMETRY.safe_top):
        if not text:
            return
        clean_text = format_kicker_text(text)
        tb = add_text_box(slide, x, y, 7.50, 0.32)
        p = tb.text_frame.paragraphs[0]
        p.text = clean_text
        p.font.name = FONTS.body
        p.font.size = Pt(12.5)
        p.font.bold = True
        p.font.color.rgb = COLORS.rgb_accent_orange


class TitleAccentBar:
    """Renders signature 0.60in accent orange bar below main title."""
    @classmethod
    def render(cls, slide: Any, x: float = GEOMETRY.title_accent_x, y: float = GEOMETRY.title_accent_y,
               w: float = GEOMETRY.title_accent_w, h: float = GEOMETRY.title_accent_h):
        bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
        bar.fill.solid()
        bar.fill.fore_color.rgb = COLORS.rgb_accent_orange
        bar.line.fill.background()
        return bar


class SlideTitle:
    """Renders Cambria 32pt slide title and automatically adds the signature accent bar."""
    @classmethod
    def render(cls, slide: Any, text: str, is_dark: bool = False, x: float = GEOMETRY.safe_left, y: float = 0.88,
               w: float = 11.90, h: float = 0.82, add_accent_bar: bool = True) -> Tuple[str, Optional[str]]:
        clean_title, subtitle = TitleOptimizer.optimize(text, max_words=8)
        color = COLORS.rgb_white if is_dark else COLORS.rgb_dark

        t_text, t_pt, _ = fit_text_to_box(clean_title, w, h, preferred_pt=32.0, min_pt=26.0, font_family=FONTS.display)
        tb = add_text_box(slide, x, y, w, h)
        p = tb.text_frame.paragraphs[0]
        p.text = t_text
        p.font.name = FONTS.display
        p.font.size = Pt(t_pt)
        p.font.bold = True
        p.font.color.rgb = color

        if add_accent_bar and not is_dark:
            accent_y = y + h + 0.04
            accent_y = min(1.78, max(1.68, accent_y))
            TitleAccentBar.render(slide, x=x, y=accent_y)

        return clean_title, subtitle


class SlideSubtitle:
    """Renders editorial lead prose below title / accent bar."""
    @classmethod
    def render(cls, slide: Any, text: str, is_dark: bool = False, x: float = GEOMETRY.safe_left, y: float = 1.95, w: float = 11.90, h: float = 0.60):
        if not text:
            return
        text_color = COLORS.rgb_text_on_dark if is_dark else COLORS.rgb_body_ink
        tb = add_text_box(slide, x, y, w, h)
        p = tb.text_frame.paragraphs[0]
        p.text = str(text).strip()
        p.font.name = FONTS.body
        p.font.size = Pt(14.5)
        p.font.color.rgb = text_color
        p.line_spacing = 1.15


class SlideFooter:
    """Renders chapter/deck title left and two-digit zero-padded page number right."""
    @classmethod
    def render(cls, slide: Any, page_num: int, deck_title: str = "Federalism", is_dark: bool = False):
        color = COLORS.rgb_text_on_dark if is_dark else COLORS.rgb_muted_text
        
        # Left title
        tb_l = add_text_box(slide, GEOMETRY.footer_left, GEOMETRY.footer_top, 4.00, 0.35)
        p_l = tb_l.text_frame.paragraphs[0]
        p_l.text = str(deck_title).strip()
        p_l.font.name = FONTS.body
        p_l.font.size = Pt(9.5)
        p_l.font.color.rgb = color

        # Right page number (e.g. "02", "03")
        page_str = str(page_num).zfill(2)
        tb_r = add_text_box(slide, 12.38, GEOMETRY.footer_top, 0.60, 0.35)
        p_r = tb_r.text_frame.paragraphs[0]
        p_r.alignment = PP_ALIGN.RIGHT
        p_r.text = page_str
        p_r.font.name = FONTS.body
        p_r.font.size = Pt(9.5)
        p_r.font.color.rgb = color


class IconBadge:
    """Circular badge with teal or orange background and centered authentic icon."""
    @classmethod
    def render(cls, slide: Any, x: float, y: float, diameter: float = 0.70,
               bg_color: Optional[RGBColor] = None, title: str = "", body: str = "",
               icon_bytes: Optional[bytes] = None, emoji_char: Optional[str] = None,
               default_index: int = 0):
        col = bg_color or COLORS.rgb_primary_teal
        badge = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(x), Inches(y), Inches(diameter), Inches(diameter))
        badge.fill.solid()
        badge.fill.fore_color.rgb = col
        badge.line.fill.background()
        apply_soft_shadow(badge)

        # 1. Resolve authentic icon if not supplied
        if not icon_bytes:
            res_icon, res_emoji = IconResolver.resolve(title, body, default_index=default_index)
            icon_bytes = res_icon
            if not emoji_char:
                emoji_char = res_emoji

        # 2. Render authentic white icon picture (responsive 64% diameter, mathematical centering)
        if icon_bytes and len(icon_bytes) > 50:
            try:
                icon_sz = round(diameter * 0.64, 2)
                pad = (diameter - icon_sz) / 2.0
                stream = io.BytesIO(icon_bytes)
                slide.shapes.add_picture(stream, Inches(x + pad), Inches(y + pad), Inches(icon_sz), Inches(icon_sz))
                return badge
            except Exception as e:
                logger.debug("Failed to render icon picture in badge: %s", e)

        # 3. Fallback emoji / symbol
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

        return badge


class InfoCard:
    """Light teal panel card with soft drop shadow, teal border, and synchronized row baselines."""
    @classmethod
    def render(cls, slide: Any, x: float, y: float, w: float, h: float,
               title: Optional[str] = None, body: Optional[str] = None,
               ghost_no: Optional[str] = None, icon_color: Optional[RGBColor] = None,
               icon_bytes: Optional[bytes] = None, emoji_char: Optional[str] = None,
               default_index: int = 0, is_cream: bool = False,
               pill: Optional[str] = None, pill_variant: str = "teal",
               bottom_pill: Optional[str] = None, bottom_pill_variant: str = "teal",
               bullets: Optional[List[str]] = None):
        bg_col = COLORS.rgb_warm_cream if is_cream else COLORS.rgb_panel_teal
        border_col = COLORS.rgb_border_warm if is_cream else COLORS.rgb_border_teal

        card = create_solid_shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, x, y, w, h,
                                  bg_col, border_col, 0.75, shadow=True)

        is_horizontal = (h <= 1.9) or (w >= 7.0 and h <= 2.4)
        pad_x = 0.28

        # 1. Horizontal banner layout (used for wide context strips or compact row roadmaps)
        if is_horizontal:
            if icon_color:
                badge_d = min(0.64, max(0.46, h - 0.34))
                badge_y = y + (h - badge_d) / 2.0
                IconBadge.render(slide, x + pad_x, badge_y, diameter=badge_d, bg_color=icon_color,
                                 title=title or "", body=body or "",
                                 icon_bytes=icon_bytes, emoji_char=emoji_char, default_index=default_index)
                text_x = x + pad_x + badge_d + 0.20
                text_w = w - (text_x - x) - pad_x
            else:
                text_x = x + pad_x
                text_w = w - (pad_x * 2)

            avail_h = h - 0.20
            # Unified single text frame: physically guarantees title and body cannot overlap
            tb = add_text_box(slide, text_x, y + 0.10, text_w, avail_h, name="card-content")
            tf = tb.text_frame
            tf.word_wrap = True
            tf.vertical_anchor = MSO_ANCHOR.MIDDLE

            p_idx = 0
            if title:
                t_clean, t_pt, _ = fit_text_to_box(title, text_w, avail_h * 0.50, preferred_pt=14.0, min_pt=11.0, font_family=FONTS.display)
                p_t = tf.paragraphs[0]
                p_idx += 1
                p_t.text = t_clean
                p_t.font.name = FONTS.display
                p_t.font.size = Pt(t_pt)
                p_t.font.bold = True
                p_t.font.color.rgb = COLORS.rgb_dark
                if body or bullets:
                    p_t.space_after = Pt(3)

            # Bullet items or body string
            raw_bullets = bullets
            if not raw_bullets and body and ("\n" in body or body.strip().startswith("•") or body.strip().startswith("-")):
                raw_bullets = [line.strip().lstrip("•-").strip() for line in body.split("\n") if line.strip()]

            if raw_bullets:
                for b_item in raw_bullets:
                    p_b = tf.paragraphs[0] if p_idx == 0 else tf.add_paragraph()
                    p_idx += 1
                    p_b.text = f"• {b_item}"
                    p_b.font.name = FONTS.body
                    p_b.font.size = Pt(10.5)
                    p_b.font.color.rgb = COLORS.rgb_muted_text
                    p_b.space_after = Pt(2)
                    p_b.line_spacing = 1.15
            elif body:
                b_clean, b_pt, _ = fit_text_to_box(body, text_w, avail_h * 0.55, preferred_pt=11.5, min_pt=9.5)
                p_b = tf.paragraphs[0] if p_idx == 0 else tf.add_paragraph()
                p_b.text = b_clean
                p_b.font.name = FONTS.body
                p_b.font.size = Pt(b_pt)
                p_b.font.color.rgb = COLORS.rgb_muted_text
                p_b.line_spacing = 1.15

            return card

        # 2. Vertical stacked layout for columns & grids (unified alignment)
        content_w = w - (pad_x * 2)
        badge_d = 0.68 if h <= 2.6 else 0.72
        badge_x = x + pad_x
        badge_y = y + 0.20

        # Top Badge
        if icon_color:
            IconBadge.render(slide, badge_x, badge_y, diameter=badge_d, bg_color=icon_color,
                             title=title or "", body=body or "",
                             icon_bytes=icon_bytes, emoji_char=emoji_char, default_index=default_index)

        # Top-Right Header Pill (aligned with badge)
        if pill:
            pill_w = Pill.calculate_width(pill)
            pill_h = 0.32
            pill_x = x + w - 0.40 - pill_w
            pill_y = badge_y + 0.08
            Pill.render(slide, pill_x, pill_y, pill, variant=pill_variant, height=pill_h)
        elif ghost_no:
            tb_ghost = add_text_box(slide, x + w - 0.40 - 0.70, y + 0.16, 0.70, 0.40, name="ghost-no")
            p_g = tb_ghost.text_frame.paragraphs[0]
            p_g.alignment = PP_ALIGN.RIGHT
            p_g.text = str(ghost_no).zfill(2)
            p_g.font.name = FONTS.display
            p_g.font.size = Pt(24.0)
            p_g.font.bold = True
            p_g.font.color.rgb = COLORS.rgb_ghost_teal

        # Title: Positioned cleanly below the badge
        title_top = (badge_y + badge_d + 0.12) if icon_color else (y + 0.22)
        title_h = 0.48 if h <= 3.2 else 0.54

        actual_title_h = title_h
        if title:
            t_text, t_pt, t_est_h = fit_text_to_box(title, content_w, title_h, preferred_pt=16.0, min_pt=13.0, font_family=FONTS.display)
            actual_title_h = max(title_h, t_est_h)
            tb_t = add_text_box(slide, x + pad_x, title_top, content_w, actual_title_h, name="card-title")
            p_t = tb_t.text_frame.paragraphs[0]
            p_t.text = t_text
            p_t.font.name = FONTS.display
            p_t.font.size = Pt(t_pt)
            p_t.font.bold = True
            p_t.font.color.rgb = COLORS.rgb_dark

        # Body / Bullets
        body_top = title_top + actual_title_h + 0.05
        body_bottom = (y + h - 0.72) if bottom_pill else (y + h - 0.18)
        body_h = max(0.40, body_bottom - body_top)

        # Auto-detect bullet list in body if not explicitly passed
        raw_bullets = bullets
        if not raw_bullets and body and ("\n" in body or body.strip().startswith("•") or body.strip().startswith("-")):
            raw_bullets = [line.strip().lstrip("•-").strip() for line in body.split("\n") if line.strip()]

        if raw_bullets:
            tb_b = add_text_box(slide, x + pad_x, body_top, content_w, body_h, name="card-body")
            tf = tb_b.text_frame
            for b_idx, bullet in enumerate(raw_bullets):
                p = tf.paragraphs[0] if b_idx == 0 else tf.add_paragraph()
                p.text = f"• {bullet.strip()}"
                p.font.name = FONTS.body
                p.font.size = Pt(11.5)
                p.font.color.rgb = COLORS.rgb_body_ink
                p.space_after = Pt(4)
                p.line_spacing = 1.15
        elif body:
            b_text, b_pt, _ = fit_text_to_box(body, content_w, body_h, preferred_pt=12.0, min_pt=10.5)
            tb_b = add_text_box(slide, x + pad_x, body_top, content_w, body_h, name="card-body")
            p_b = tb_b.text_frame.paragraphs[0]
            p_b.text = b_text
            p_b.font.name = FONTS.body
            p_b.font.size = Pt(b_pt)
            p_b.font.color.rgb = COLORS.rgb_muted_text
            p_b.line_spacing = 1.15

        if bottom_pill:
            pill_h = 0.32
            pill_x = x + 0.40
            pill_y = y + h - pill_h - 0.28
            Pill.render(slide, pill_x, pill_y, bottom_pill, variant=bottom_pill_variant, height=pill_h)

        return card


class CreamCard:
    """Warm cream card with warm border for secondary insights, commentary, or contrast."""
    @classmethod
    def render(cls, slide: Any, x: float, y: float, w: float, h: float,
               title: Optional[str] = None, body: Optional[str] = None,
               ghost_no: Optional[str] = None, icon_color: Optional[RGBColor] = None,
               icon_bytes: Optional[bytes] = None, emoji_char: Optional[str] = None,
               default_index: int = 0, pill: Optional[str] = None, pill_variant: str = "orange",
               bottom_pill: Optional[str] = None, bottom_pill_variant: str = "orange",
               bullets: Optional[List[str]] = None):
        return InfoCard.render(slide, x, y, w, h, title=title, body=body,
                               ghost_no=ghost_no, icon_color=icon_color,
                               icon_bytes=icon_bytes, emoji_char=emoji_char,
                               default_index=default_index, is_cream=True,
                               pill=pill, pill_variant=pill_variant,
                               bottom_pill=bottom_pill, bottom_pill_variant=bottom_pill_variant,
                               bullets=bullets)


class DarkCard:
    """Deep teal card (#0C3B39 or #11504C) with high contrast white text and light mint body."""
    @classmethod
    def render(cls, slide: Any, x: float, y: float, w: float, h: float,
               title: Optional[str] = None, body: Optional[str] = None,
               icon_color: Optional[RGBColor] = None,
               icon_bytes: Optional[bytes] = None, emoji_char: Optional[str] = None,
               default_index: int = 0, ghost_no: Optional[str] = None,
               pill: Optional[str] = None, pill_variant: str = "teal"):
        card = create_solid_shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, x, y, w, h,
                                  COLORS.rgb_dark, COLORS.rgb_dark_alt, 1.0, shadow=False)

        is_horizontal = (h <= 1.9) or (w >= 7.0 and h <= 2.4)
        pad_x = 0.28
        col = icon_color or COLORS.rgb_primary_teal

        if is_horizontal:
            badge_d = min(0.64, max(0.46, h - 0.34))
            badge_y = y + (h - badge_d) / 2.0
            IconBadge.render(slide, x + pad_x, badge_y, diameter=badge_d, bg_color=col,
                             title=title or "", body=body or "",
                             icon_bytes=icon_bytes, emoji_char=emoji_char, default_index=default_index)
            text_x = x + pad_x + badge_d + 0.20
            text_w = w - (text_x - x) - pad_x
            avail_h = h - 0.20

            tb = add_text_box(slide, text_x, y + 0.10, text_w, avail_h, name="dark-content")
            tf = tb.text_frame
            tf.word_wrap = True
            tf.vertical_anchor = MSO_ANCHOR.MIDDLE

            p_idx = 0
            if title:
                t_clean, t_pt, _ = fit_text_to_box(title, text_w, avail_h * 0.50, preferred_pt=14.0, min_pt=11.0, font_family=FONTS.display)
                p_t = tf.paragraphs[0]
                p_idx += 1
                p_t.text = t_clean
                p_t.font.name = FONTS.display
                p_t.font.size = Pt(t_pt)
                p_t.font.bold = True
                p_t.font.color.rgb = COLORS.rgb_white
                if body:
                    p_t.space_after = Pt(3)

            if body:
                b_clean, b_pt, _ = fit_text_to_box(body, text_w, avail_h * 0.55, preferred_pt=11.5, min_pt=9.5)
                p_b = tf.paragraphs[0] if p_idx == 0 else tf.add_paragraph()
                p_b.text = b_clean
                p_b.font.name = FONTS.body
                p_b.font.size = Pt(b_pt)
                p_b.font.color.rgb = COLORS.rgb_text_on_dark
                p_b.line_spacing = 1.15
            return card

        # Tall vertical DarkCard
        content_w = w - (pad_x * 2)
        if ghost_no:
            tb_ghost = add_text_box(slide, x + w - pad_x - 0.70, y + 0.16, 0.70, 0.40, name="ghost-no")
            p_g = tb_ghost.text_frame.paragraphs[0]
            p_g.alignment = PP_ALIGN.RIGHT
            p_g.text = str(ghost_no).zfill(2)
            p_g.font.name = FONTS.display
            p_g.font.size = Pt(24.0)
            p_g.font.bold = True
            p_g.font.color.rgb = COLORS.rgb_primary_teal

        badge_d = 0.68 if h <= 2.6 else 0.72
        badge_x = x + pad_x
        badge_y = y + 0.20
        IconBadge.render(slide, badge_x, badge_y, diameter=badge_d, bg_color=col,
                         title=title or "", body=body or "",
                         icon_bytes=icon_bytes, emoji_char=emoji_char, default_index=default_index)
        title_top = badge_y + badge_d + 0.12
        title_h = 0.48 if h <= 3.2 else 0.54

        actual_title_h = title_h
        if title:
            t_text, t_pt, t_est_h = fit_text_to_box(title, content_w, title_h, preferred_pt=15.5, min_pt=13.0, font_family=FONTS.display)
            actual_title_h = max(title_h, t_est_h)
            tb_t = add_text_box(slide, x + pad_x, title_top, content_w, actual_title_h, name="dark-title")
            p_t = tb_t.text_frame.paragraphs[0]
            p_t.text = t_text
            p_t.font.name = FONTS.display
            p_t.font.size = Pt(t_pt)
            p_t.font.bold = True
            p_t.font.color.rgb = COLORS.rgb_white

        body_top = title_top + actual_title_h + 0.05
        body_h = max(0.20, (y + h - 0.15) - body_top)

        raw_bullets = [line.strip().lstrip("•-").strip() for line in body.split("\n") if line.strip()] if (body and ("\n" in body or body.strip().startswith("•"))) else None
        if raw_bullets:
            tb_b = add_text_box(slide, x + pad_x, body_top, content_w, body_h, name="dark-body")
            tf = tb_b.text_frame
            for b_idx, bullet in enumerate(raw_bullets):
                p = tf.paragraphs[0] if b_idx == 0 else tf.add_paragraph()
                p.text = f"• {bullet.strip()}"
                p.font.name = FONTS.body
                p.font.size = Pt(11.5)
                p.font.color.rgb = COLORS.rgb_text_on_dark
                p.space_after = Pt(4)
                p.line_spacing = 1.15
        elif body:
            b_text, b_pt, _ = fit_text_to_box(body, content_w, body_h, preferred_pt=12.0, min_pt=10.5)
            tb_b = add_text_box(slide, x + pad_x, body_top, content_w, body_h, name="dark-body")
            p_b = tb_b.text_frame.paragraphs[0]
            p_b.text = b_text
            p_b.font.name = FONTS.body
            p_b.font.size = Pt(b_pt)
            p_b.font.color.rgb = COLORS.rgb_text_on_dark
            p_b.line_spacing = 1.15

        return card


class NegativeCard:
    """Pale negative red card (#F6E0DB) for problems, warnings, or opposing systems."""
    @classmethod
    def render(cls, slide: Any, x: float, y: float, w: float, h: float,
               title: Optional[str] = None, body: Optional[str] = None,
               default_index: int = 0, pill: Optional[str] = None,
               pill_variant: str = "negative", bullets: Optional[List[str]] = None,
               bottom_pill: Optional[str] = None):
        card = create_solid_shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, x, y, w, h,
                                  COLORS.rgb_pale_negative, COLORS.rgb_negative_red, 0.85, shadow=True)
        pad_x = 0.28
        content_w = w - (pad_x * 2)

        badge_d = 0.68 if h <= 2.6 else 0.72
        badge_x = x + pad_x
        badge_y = y + 0.20
        IconBadge.render(slide, badge_x, badge_y, diameter=badge_d, bg_color=COLORS.rgb_negative_red,
                         title=title or "", body=body or "", default_index=default_index)

        if pill:
            pill_w = Pill.calculate_width(pill)
            pill_h = 0.32
            pill_x = x + w - 0.40 - pill_w
            pill_y = badge_y + 0.08
            Pill.render(slide, pill_x, pill_y, pill, variant=pill_variant, height=pill_h)

        title_top = badge_y + badge_d + 0.12
        title_h = 0.48 if h <= 3.2 else 0.54

        actual_title_h = title_h
        if title:
            t_text, t_pt, t_est_h = fit_text_to_box(title, content_w, title_h, preferred_pt=16.0, min_pt=13.0, font_family=FONTS.display)
            actual_title_h = max(title_h, t_est_h)
            tb_t = add_text_box(slide, x + pad_x, title_top, content_w, actual_title_h, name="card-title")
            p_t = tb_t.text_frame.paragraphs[0]
            p_t.text = t_text
            p_t.font.name = FONTS.display
            p_t.font.size = Pt(t_pt)
            p_t.font.bold = True
            p_t.font.color.rgb = COLORS.rgb_negative_red

        body_top = title_top + actual_title_h + 0.05
        body_bottom = (y + h - 0.72) if bottom_pill else (y + h - 0.18)
        body_h = max(0.40, body_bottom - body_top)

        raw_bullets = bullets
        if not raw_bullets and body and ("\n" in body or body.strip().startswith("•") or body.strip().startswith("-")):
            raw_bullets = [line.strip().lstrip("•-").strip() for line in body.split("\n") if line.strip()]

        if raw_bullets:
            tb_b = add_text_box(slide, x + pad_x, body_top, content_w, body_h, name="card-body")
            tf = tb_b.text_frame
            for b_idx, bullet in enumerate(raw_bullets):
                p = tf.paragraphs[0] if b_idx == 0 else tf.add_paragraph()
                p.text = f"• {bullet.strip()}"
                p.font.name = FONTS.body
                p.font.size = Pt(11.5)
                p.font.color.rgb = COLORS.rgb_body_ink
                p.space_after = Pt(4)
                p.line_spacing = 1.15
        elif body:
            b_text, b_pt, _ = fit_text_to_box(body, content_w, body_h, preferred_pt=12.0, min_pt=10.5)
            tb_b = add_text_box(slide, x + pad_x, body_top, content_w, body_h, name="card-body")
            p_b = tb_b.text_frame.paragraphs[0]
            p_b.text = b_text
            p_b.font.name = FONTS.body
            p_b.font.size = Pt(b_pt)
            p_b.font.color.rgb = COLORS.rgb_body_ink
            p_b.line_spacing = 1.15

        if bottom_pill:
            pill_h = 0.32
            pill_x = x + 0.40
            pill_y = y + h - pill_h - 0.28
            Pill.render(slide, pill_x, pill_y, bottom_pill, variant="negative", height=pill_h)

        return card



class MetricCard:
    """Vertical KPI card with Cambria 34pt number and explanatory text."""
    @classmethod
    def render(cls, slide: Any, x: float, y: float, w: float, h: float,
               value: str, label: str, subtext: Optional[str] = None,
               is_warning: bool = False, is_cream: bool = False):
        bg = COLORS.rgb_pale_negative if is_warning else (COLORS.rgb_warm_cream if is_cream else COLORS.rgb_panel_teal)
        border = COLORS.rgb_negative_red if is_warning else (COLORS.rgb_border_warm if is_cream else COLORS.rgb_border_teal)
        val_color = COLORS.rgb_negative_red if is_warning else COLORS.rgb_accent_orange

        create_solid_shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, x, y, w, h, bg, border, 0.75, shadow=True)

        # Value text
        tb = add_text_box(slide, x + 0.25, y + 0.18, w - 0.50, 0.65)
        p_v = tb.text_frame.paragraphs[0]
        p_v.text = str(value).strip()
        p_v.font.name = FONTS.display
        p_v.font.size = Pt(34.0)
        p_v.font.bold = True
        p_v.font.color.rgb = val_color

        # Label
        l_clean, l_pt, l_est_h = fit_text_to_box(label, w - 0.50, 0.45, preferred_pt=15.5, min_pt=13.0, font_family=FONTS.display)
        tb_l = add_text_box(slide, x + 0.25, y + 0.88, w - 0.50, l_est_h)
        p_l = tb_l.text_frame.paragraphs[0]
        p_l.text = l_clean
        p_l.font.name = FONTS.display
        p_l.font.size = Pt(l_pt)
        p_l.font.bold = True
        p_l.font.color.rgb = COLORS.rgb_dark

        if subtext:
            cur_y = y + 0.88 + l_est_h + 0.04
            avail_s_h = max(0.25, (y + h - 0.12) - cur_y)
            s_clean, s_pt, _ = fit_text_to_box(subtext, w - 0.50, avail_s_h, preferred_pt=11.5, min_pt=10.0)
            tb_s = add_text_box(slide, x + 0.25, cur_y, w - 0.50, avail_s_h)
            p_s = tb_s.text_frame.paragraphs[0]
            p_s.text = s_clean
            p_s.font.name = FONTS.body
            p_s.font.size = Pt(s_pt)
            p_s.font.color.rgb = COLORS.rgb_muted_text
            p_s.line_spacing = 1.15


class HorizontalMetricCard:
    """Horizontal KPI row with large number left and description right."""
    @classmethod
    def render(cls, slide: Any, x: float, y: float, w: float, h: float,
               value: str, label: str, description: Optional[str] = None,
               is_warning: bool = False):
        bg = COLORS.rgb_pale_negative if is_warning else COLORS.rgb_panel_teal
        border = COLORS.rgb_negative_red if is_warning else COLORS.rgb_border_teal
        val_color = COLORS.rgb_negative_red if is_warning else COLORS.rgb_accent_orange

        create_solid_shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, x, y, w, h, bg, border, 0.75, shadow=True)

        num_w = min(1.80, w * 0.32)
        tb_v = add_text_box(slide, x + 0.20, y + (h - 0.70) / 2.0, num_w, 0.70)
        p_v = tb_v.text_frame.paragraphs[0]
        p_v.text = str(value).strip()
        p_v.font.name = FONTS.display
        p_v.font.size = Pt(36.0)
        p_v.font.bold = True
        p_v.font.color.rgb = val_color

        # Text on right
        t_x = x + 0.20 + num_w + 0.15
        t_w = w - (t_x - x) - 0.20
        avail_h = h - 0.24

        tb_t = add_text_box(slide, t_x, y + 0.12, t_w, avail_h)
        p_t = tb_t.text_frame.paragraphs[0]
        p_t.text = str(label).strip()
        p_t.font.name = FONTS.display
        p_t.font.size = Pt(15.0)
        p_t.font.bold = True
        p_t.font.color.rgb = COLORS.rgb_dark

        if description:
            p_d = tb_t.text_frame.add_paragraph()
            p_d.text = str(description).strip()
            p_d.font.name = FONTS.body
            p_d.font.size = Pt(11.5)
            p_d.font.color.rgb = COLORS.rgb_muted_text
            p_d.space_before = Pt(4)


class FeatureContainerCard:
    """Wide container (warm cream or panel teal) with a header title and 2 to 4 distributed columns inside."""
    @classmethod
    def render(cls, slide: Any, x: float, y: float, w: float, h: float,
               title: str, items: List[Any],
               is_cream: bool = True, default_index: int = 0):
        bg = COLORS.rgb_warm_cream if is_cream else COLORS.rgb_panel_teal
        border = COLORS.rgb_border_warm if is_cream else COLORS.rgb_border_teal
        create_solid_shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, x, y, w, h, bg, border, 0.85, shadow=True)

        pad_x = 0.35
        # 1. Container Title
        tb_t = add_text_box(slide, x + pad_x, y + 0.16, w - (pad_x * 2), 0.36, name="container-title")
        p_t = tb_t.text_frame.paragraphs[0]
        p_t.text = str(title).strip()
        p_t.font.name = FONTS.display
        p_t.font.size = Pt(15.5)
        p_t.font.bold = True
        p_t.font.color.rgb = COLORS.rgb_dark

        # 2. Parse items into structured dicts
        parsed_items = []
        for it in items:
            if isinstance(it, dict):
                parsed_items.append({
                    "title": it.get("title", ""),
                    "body": it.get("body", "")
                })
            else:
                raw = str(it).strip().lstrip("•-").strip()
                if ":" in raw:
                    parts = raw.split(":", 1)
                    parsed_items.append({"title": parts[0].strip(), "body": parts[1].strip()})
                else:
                    parsed_items.append({"title": "", "body": raw})

        n = max(1, min(4, len(parsed_items)))
        gap = 0.28
        total_w = w - (pad_x * 2)
        col_w = (total_w - (gap * (n - 1))) / n
        col_y = y + 0.58
        avail_col_h = max(0.40, (y + h - 0.14) - col_y)

        for i, it in enumerate(parsed_items[:n]):
            col_x = x + pad_x + i * (col_w + gap)
            i_title = it.get("title", "")
            i_body = it.get("body", "")

            # Icon badge for each column
            badge_d = 0.44
            col_icon = COLORS.rgb_accent_orange if (i % 2 == 1 or not is_cream) else COLORS.rgb_primary_teal
            IconBadge.render(slide, col_x, col_y, diameter=badge_d,
                             bg_color=col_icon,
                             title=i_title, body=i_body, default_index=default_index + i)

            # Text beside badge
            text_x = col_x + badge_d + 0.14
            text_w = max(1.0, col_w - badge_d - 0.14)

            tb_col = add_text_box(slide, text_x, col_y - 0.04, text_w, avail_col_h, name=f"col-{i+1}")
            tf_col = tb_col.text_frame
            tf_col.word_wrap = True

            p_idx = 0
            if i_title:
                p_ct = tf_col.paragraphs[0]
                p_idx += 1
                p_ct.text = i_title
                p_ct.font.name = FONTS.display
                p_ct.font.size = Pt(13.0)
                p_ct.font.bold = True
                p_ct.font.color.rgb = COLORS.rgb_dark
                if i_body:
                    p_ct.space_after = Pt(2)

            if i_body:
                b_fit, b_pt, _ = fit_text_to_box(i_body, text_w, avail_col_h * 0.75, preferred_pt=10.5, min_pt=9.0)
                p_cb = tf_col.paragraphs[0] if p_idx == 0 else tf_col.add_paragraph()
                p_cb.text = b_fit
                p_cb.font.name = FONTS.body
                p_cb.font.size = Pt(b_pt)
                p_cb.font.color.rgb = COLORS.rgb_muted_text
                p_cb.line_spacing = 1.15


class ImageFrame:
    """Framed image container with aspect ratio preservation (FIT or COVER) and caption safety."""
    @classmethod
    def render(cls, slide: Any, x: float, y: float, w: float, h: float,
               img_bytes: Optional[bytes] = None, caption: Optional[str] = None,
               fit_mode: str = "FIT"):
        # Frame shape
        frame_h = h - (0.45 if caption else 0.0)
        create_solid_shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, x, y, w, frame_h,
                           COLORS.rgb_white, COLORS.rgb_border_teal, 0.75, shadow=True)

        if not img_bytes or len(img_bytes) <= 100:
            from app.presentation.themes.federalism_editorial.icons import IconResolver
            # Try loading authentic reference asset
            img_bytes = IconResolver.get_raw_bytes("image-5-1.png")

        if img_bytes and len(img_bytes) > 100:
            try:
                stream = io.BytesIO(img_bytes)
                im = PILImage.open(stream)
                orig_w, orig_h = im.size

                pad = 0.12
                avail_w = w - (pad * 2)
                avail_h = frame_h - (pad * 2)

                if fit_mode == "COVER":
                    img_w, img_h = avail_w, avail_h
                    img_x, img_y = x + pad, y + pad
                else: # FIT
                    ratio = min(avail_w / orig_w, avail_h / orig_h)
                    img_w = orig_w * ratio
                    img_h = orig_h * ratio
                    img_x = x + pad + (avail_w - img_w) / 2.0
                    img_y = y + pad + (avail_h - img_h) / 2.0

                stream.seek(0)
                slide.shapes.add_picture(stream, Inches(img_x), Inches(img_y), Inches(img_w), Inches(img_h))
            except Exception as e:
                logger.debug("Failed to place image: %s", e)
        else:
            # Stylized graphic fallback to prevent empty frame defect
            badge_d = 0.80
            bx = x + (w - badge_d) / 2.0
            by = y + (frame_h - badge_d) / 2.0
            IconBadge.render(slide, bx, by, diameter=badge_d, bg_color=COLORS.rgb_primary_teal,
                             title="Visual Document", default_index=0)

        if caption:
            cap_y = y + frame_h + 0.08
            tb_c = add_text_box(slide, x, cap_y, w, 0.35)
            p_c = tb_c.text_frame.paragraphs[0]
            p_c.text = str(caption).strip()
            p_c.font.name = FONTS.body
            p_c.font.size = Pt(10.0)
            p_c.font.italic = True
            p_c.font.color.rgb = COLORS.rgb_muted_text


class MapFrame:
    """Specialized map frame ensuring FIT aspect ratio and clean borders."""
    @classmethod
    def render(cls, slide: Any, x: float, y: float, w: float, h: float,
               map_bytes: Optional[bytes] = None, caption: Optional[str] = None):
        return ImageFrame.render(slide, x, y, w, h, img_bytes=map_bytes, caption=caption, fit_mode="FIT")


class EditorialQuoteCard:
    """Warm cream card with oversized orange quote marks."""
    @classmethod
    def render(cls, slide: Any, x: float, y: float, w: float, h: float,
               quote_text: str, attribution: Optional[str] = None):
        card = create_solid_shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, x, y, w, h,
                                  COLORS.rgb_warm_cream, COLORS.rgb_border_warm, 0.85, shadow=True)

        # Oversized decorative quote mark
        tb_q = add_text_box(slide, x + 0.25, y + 0.16, 0.50, 0.50, name="quote-mark")
        p_q = tb_q.text_frame.paragraphs[0]
        p_q.text = "“"
        p_q.font.name = FONTS.display
        p_q.font.size = Pt(42.0)
        p_q.font.bold = True
        p_q.font.color.rgb = COLORS.rgb_accent_orange

        # Quote body - indented to the right of quote mark for zero collision
        text_x = x + 0.82
        text_w = w - 1.10
        avail_h = max(0.40, h - 0.36 - (0.38 if attribution else 0.0))
        q_clean = quote_text.strip().strip('"')
        q_fit, q_pt, q_est_h = fit_text_to_box(f'"{q_clean}"', text_w, avail_h, preferred_pt=14.5, min_pt=12.0, font_family=FONTS.display)

        tb = add_text_box(slide, text_x, y + 0.20, text_w, avail_h, name="quote-content")
        tf = tb.text_frame
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.text = q_fit
        p.font.name = FONTS.display
        p.font.size = Pt(q_pt)
        p.font.bold = True
        p.font.color.rgb = COLORS.rgb_dark
        p.line_spacing = 1.15

        if attribution:
            p.space_after = Pt(6)
            p_att = tf.add_paragraph()
            p_att.text = f"— {attribution.strip()}"
            p_att.font.name = FONTS.body
            p_att.font.size = Pt(11.0)
            p_att.font.bold = True
            p_att.font.color.rgb = COLORS.rgb_accent_orange

        return card


class Pill:
    """Status chip or tag pill with clean borders and centered text."""
    @classmethod
    def calculate_width(cls, text: str) -> float:
        clean = str(text or "").strip().upper()
        char_w = 0.085
        return max(1.10, min(3.80, len(clean) * char_w + 0.40))

    @classmethod
    def render(cls, slide: Any, x: float, y: float, text: str,
               variant: str = "orange", height: float = 0.34) -> float:
        clean = str(text or "").strip().upper()
        w = cls.calculate_width(clean)

        if variant == "orange":
            bg, border, fg = COLORS.rgb_accent_orange, COLORS.rgb_accent_orange, COLORS.rgb_white
        elif variant == "teal":
            bg, border, fg = COLORS.rgb_primary_teal, COLORS.rgb_primary_teal, COLORS.rgb_white
        elif variant == "green":
            bg, border, fg = COLORS.rgb_secondary_teal, COLORS.rgb_secondary_teal, COLORS.rgb_white
        elif variant == "negative":
            bg, border, fg = COLORS.rgb_negative_red, COLORS.rgb_negative_red, COLORS.rgb_white
        else: # outline
            bg, border, fg = COLORS.rgb_white, COLORS.rgb_border_teal, COLORS.rgb_body_ink

        pill = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(height))
        pill.fill.solid()
        pill.fill.fore_color.rgb = bg
        set_shape_border(pill, border, 0.75)
        try:
            pill.adjustments[0] = 0.5
        except Exception:
            pass

        tf = pill.text_frame
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        tf.margin_left = Inches(0.10)
        tf.margin_right = Inches(0.10)
        tf.margin_top = Inches(0)
        tf.margin_bottom = Inches(0)
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        p.text = clean
        p.font.name = FONTS.body
        p.font.size = Pt(10.0)
        p.font.bold = True
        p.font.color.rgb = fg
        return w


class TimelineNode:
    """Milestone marker on a timeline track."""
    @classmethod
    def render(cls, slide: Any, x: float, y: float, diameter: float = 0.36, is_highlight: bool = False):
        col = COLORS.rgb_accent_orange if is_highlight else COLORS.rgb_primary_teal
        node = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(x), Inches(y), Inches(diameter), Inches(diameter))
        node.fill.solid()
        node.fill.fore_color.rgb = col
        node.line.fill.background()
        apply_soft_shadow(node)
        return node


class TimelineTrack:
    """Thin connecting track line for chronological workflows."""
    @classmethod
    def render(cls, slide: Any, x1: float, y1: float, x2: float, y2: float, width_pt: float = 2.0):
        w = max(0.02, abs(x2 - x1))
        h = max(0.02, abs(y2 - y1))
        line = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(min(x1, x2)), Inches(min(y1, y2)), Inches(w), Inches(h))
        line.fill.solid()
        line.fill.fore_color.rgb = COLORS.rgb_primary_teal
        line.line.fill.background()
        return line
