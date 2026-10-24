"""Centralized Design System Tokens for Maratha Heritage Editorial Theme.

Formalizes exact DrawingML colors, dimensions, geometry, shadows, and spacing rules
from reference presentation 'The Rise of the Marathas (4).pptx'.
"""

from dataclasses import dataclass
from pptx.dml.color import RGBColor


@dataclass(frozen=True)
class ColorTokens:
    # Hex values
    hex_canvas: str = "#FFFFFF"
    hex_maroon: str = "#6B221C"         # Primary dark maroon
    hex_maroon_alt: str = "#7E2C22"     # Secondary rich maroon
    hex_orange: str = "#E4791F"         # Primary saffron orange
    hex_gold: str = "#B0771A"           # Antique gold kicker/eyebrow
    hex_body: str = "#2A211C"           # Deep warm charcoal body text
    hex_muted: str = "#8A7A6C"          # Muted captions, footers, sources
    hex_parchment: str = "#FBF6EF"      # Light parchment cards
    hex_cream: str = "#F7EEE3"          # Light cream cards / secondary panels
    hex_border_warm: str = "#E9D8CB"    # Warm subtle border
    hex_text_on_dark: str = "#F5EAE0"   # Pale warm text on dark maroon
    hex_white: str = "#FFFFFF"

    # RGBColor objects for python-pptx
    rgb_canvas: RGBColor = RGBColor(0xFF, 0xFF, 0xFF)
    rgb_maroon: RGBColor = RGBColor(0x6B, 0x22, 0x1C)
    rgb_maroon_alt: RGBColor = RGBColor(0x7E, 0x2C, 0x22)
    rgb_orange: RGBColor = RGBColor(0xE4, 0x79, 0x1F)
    rgb_gold: RGBColor = RGBColor(0xB0, 0x77, 0x1A)
    rgb_body: RGBColor = RGBColor(0x2A, 0x21, 0x1C)
    rgb_muted: RGBColor = RGBColor(0x8A, 0x7A, 0x6C)
    rgb_parchment: RGBColor = RGBColor(0xFB, 0xF6, 0xEF)
    rgb_cream: RGBColor = RGBColor(0xF7, 0xEE, 0xE3)
    rgb_border_warm: RGBColor = RGBColor(0xE9, 0xD8, 0xCB)
    rgb_text_on_dark: RGBColor = RGBColor(0xF5, 0xEA, 0xE0)
    rgb_white: RGBColor = RGBColor(0xFF, 0xFF, 0xFF)


@dataclass(frozen=True)
class FontTokens:
    display: str = "Cambria"
    body: str = "Calibri"
    monospace: str = "Consolas"


@dataclass(frozen=True)
class GeometryTokens:
    slide_width: float = 13.333
    slide_height: float = 7.500
    safe_left: float = 0.55
    safe_right: float = 0.55
    safe_top: float = 0.50
    safe_bottom: float = 0.44
    content_top: float = 1.65
    content_bottom: float = 6.80
    footer_top: float = 7.06
    footer_left: float = 0.55
    footer_slide_num_x: float = 12.183

    # Standard Header Coordinates
    header_badge_x: float = 0.55
    header_badge_y: float = 0.52
    header_badge_d: float = 0.66
    header_kicker_x: float = 1.41
    header_kicker_y: float = 0.50
    header_title_x: float = 1.41
    header_title_y: float = 0.75
    header_title_w: float = 11.40

    # Dark Slide Header Coordinates (M19, M24)
    dark_badge_y: float = 0.60
    dark_kicker_y: float = 0.62
    dark_title_y: float = 0.86

    # Card internal padding standards
    pad_compact: float = 0.18
    pad_standard: float = 0.25
    pad_comfortable: float = 0.35

    # Alignment tolerance (inches)
    alignment_tolerance: float = 0.03


@dataclass(frozen=True)
class ShadowTokens:
    blur_rad_emu: int = 114300  # 9pt
    dist_emu: int = 38100       # 3pt
    dir_deg: int = 5400000      # 90 degrees straight down
    color_hex: str = "000000"
    alpha_val: int = 16000      # 16% opacity


@dataclass(frozen=True)
class SpacingTokens:
    xs: float = 0.08
    sm: float = 0.15
    md: float = 0.25
    lg: float = 0.35
    xl: float = 0.55


COLORS = ColorTokens()
FONTS = FontTokens()
GEOMETRY = GeometryTokens()
SHADOWS = ShadowTokens()
SPACING = SpacingTokens()
