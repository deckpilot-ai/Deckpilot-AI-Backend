"""Design tokens for the Development Editorial Presentation Theme.

Extracted directly from benchmark presentation 'Development (2).pptx'.
Canvas: 13.333" x 7.500" (16:9 Widescreen).
"""

from dataclasses import dataclass
from pptx.dml.color import RGBColor


def hex_to_rgb(hex_code: str) -> RGBColor:
    val = hex_code.lstrip("#")
    return RGBColor(int(val[0:2], 16), int(val[2:4], 16), int(val[4:6], 16))


@dataclass(frozen=True)
class ColorTokens:
    canvas: str = "#FFFFFF"
    canvas_dark: str = "#163A33"
    ink: str = "#20302C"
    ink_muted: str = "#5E726B"
    green_dark: str = "#1F4F45"
    green_primary: str = "#2E7D6B"
    green_mid: str = "#4CA08A"
    gold: str = "#C28A2C"
    gold_light: str = "#E7C879"
    panel: str = "#F1F6F4"
    panel_border: str = "#DDE8E3"
    quote: str = "#FBF4E4"
    quote_border: str = "#EAD9A8"
    quote_text: str = "#5A4715"
    warm_frame: str = "#FBF6EA"
    image_border: str = "#D7E2DD"
    divider: str = "#CBDAD3"
    text_on_dark: str = "#CFE2DB"
    text_on_dark_muted: str = "#BFD6CE"
    text_footer_dark: str = "#9FBCB3"
    number_ghost: str = "#E5EFEB"
    white: str = "#FFFFFF"

    # Convenient RGBColor properties
    @property
    def rgb_canvas(self) -> RGBColor: return hex_to_rgb(self.canvas)
    @property
    def rgb_canvas_dark(self) -> RGBColor: return hex_to_rgb(self.canvas_dark)
    @property
    def rgb_ink(self) -> RGBColor: return hex_to_rgb(self.ink)
    @property
    def rgb_ink_muted(self) -> RGBColor: return hex_to_rgb(self.ink_muted)
    @property
    def rgb_green_dark(self) -> RGBColor: return hex_to_rgb(self.green_dark)
    @property
    def rgb_green_primary(self) -> RGBColor: return hex_to_rgb(self.green_primary)
    @property
    def rgb_green_mid(self) -> RGBColor: return hex_to_rgb(self.green_mid)
    @property
    def rgb_gold(self) -> RGBColor: return hex_to_rgb(self.gold)
    @property
    def rgb_gold_light(self) -> RGBColor: return hex_to_rgb(self.gold_light)
    @property
    def rgb_panel(self) -> RGBColor: return hex_to_rgb(self.panel)
    @property
    def rgb_panel_border(self) -> RGBColor: return hex_to_rgb(self.panel_border)
    @property
    def rgb_quote(self) -> RGBColor: return hex_to_rgb(self.quote)
    @property
    def rgb_quote_border(self) -> RGBColor: return hex_to_rgb(self.quote_border)
    @property
    def rgb_quote_text(self) -> RGBColor: return hex_to_rgb(self.quote_text)
    @property
    def rgb_warm_frame(self) -> RGBColor: return hex_to_rgb(self.warm_frame)
    @property
    def rgb_image_border(self) -> RGBColor: return hex_to_rgb(self.image_border)
    @property
    def rgb_divider(self) -> RGBColor: return hex_to_rgb(self.divider)
    @property
    def rgb_text_on_dark(self) -> RGBColor: return hex_to_rgb(self.text_on_dark)
    @property
    def rgb_text_on_dark_muted(self) -> RGBColor: return hex_to_rgb(self.text_on_dark_muted)
    @property
    def rgb_text_footer_dark(self) -> RGBColor: return hex_to_rgb(self.text_footer_dark)
    @property
    def rgb_number_ghost(self) -> RGBColor: return hex_to_rgb(self.number_ghost)
    @property
    def rgb_white(self) -> RGBColor: return hex_to_rgb(self.white)


@dataclass(frozen=True)
class ShadowTokens:
    blur_rad_emu: int = 88900      # 7.0 pt
    dist_emu: int = 38100          # 3.0 pt
    dir_deg: int = 5400000         # 90 degrees downward
    color_hex: str = "000000"      # Pure black
    alpha_val: int = 18000         # 18.0% opacity


@dataclass(frozen=True)
class SpacingTokens:
    xs: float = 0.10
    sm: float = 0.20
    md: float = 0.30
    lg: float = 0.45
    xl: float = 0.80

    margin_x: float = 0.60
    margin_top: float = 0.48
    title_y: float = 0.86
    content_top: float = 1.75
    safe_width: float = 12.133
    safe_right: float = 12.733


@dataclass(frozen=True)
class FontTokens:
    display: str = "Cambria"
    body: str = "Calibri"


COLORS = ColorTokens()
SHADOWS = ShadowTokens()
SPACING = SpacingTokens()
FONTS = FontTokens()
