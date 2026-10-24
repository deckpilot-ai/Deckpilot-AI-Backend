"""Centralized Design System Tokens for Rise of Empires Editorial Theme.

Formalizes exact DrawingML colors, dimensions, geometry, shadows, and spacing rules
from reference presentation 'The Rise of Empires (3).pptx'.
"""

from dataclasses import dataclass
from pptx.dml.color import RGBColor


@dataclass(frozen=True)
class ColorTokens:
    # Hex values
    hex_canvas: str = "#FFFFFF"
    hex_canvas_dark: str = "#123B47"
    hex_dark_secondary: str = "#1C505C"
    hex_heading: str = "#123B47"
    hex_body: str = "#26221E"
    hex_muted: str = "#7C7267"
    hex_accent: str = "#C05A38"       # Burnt orange
    hex_kicker: str = "#B0791A"       # Antique gold
    hex_parchment: str = "#FAF6EF"    # Light parchment card
    hex_cream: str = "#F4EEE4"        # Warm cream secondary card / frame
    hex_border_warm: str = "#E1D6C6"  # Subtle warm border
    hex_text_on_dark: str = "#EDE3D6" # Light warm cream text on dark teal
    hex_white: str = "#FFFFFF"

    # RGBColor objects for python-pptx
    rgb_canvas: RGBColor = RGBColor(0xFF, 0xFF, 0xFF)
    rgb_canvas_dark: RGBColor = RGBColor(0x12, 0x3B, 0x47)
    rgb_dark_secondary: RGBColor = RGBColor(0x1C, 0x50, 0x5C)
    rgb_heading: RGBColor = RGBColor(0x12, 0x3B, 0x47)
    rgb_body: RGBColor = RGBColor(0x26, 0x22, 0x1E)
    rgb_muted: RGBColor = RGBColor(0x7C, 0x72, 0x67)
    rgb_accent: RGBColor = RGBColor(0xC0, 0x5A, 0x38)
    rgb_kicker: RGBColor = RGBColor(0xB0, 0x79, 0x1A)
    rgb_parchment: RGBColor = RGBColor(0xFA, 0xF6, 0xEF)
    rgb_cream: RGBColor = RGBColor(0xF4, 0xEE, 0xE4)
    rgb_border_warm: RGBColor = RGBColor(0xE1, 0xD6, 0xC6)
    rgb_text_on_dark: RGBColor = RGBColor(0xED, 0xE3, 0xD6)
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
    footer_slide_num_x: float = 12.18

    # Standard Header Coordinates
    header_badge_x: float = 0.55
    header_badge_y: float = 0.52
    header_badge_d: float = 0.66
    header_kicker_x: float = 1.41
    header_kicker_y: float = 0.50
    header_title_x: float = 1.41
    header_title_y: float = 0.75
    header_title_w: float = 11.40

    # Dark Slide Header Coordinates (S15, S23)
    dark_badge_y: float = 0.60
    dark_kicker_y: float = 0.62
    dark_title_y: float = 0.86

    # Card internal padding standards
    pad_compact: float = 0.18
    pad_standard: float = 0.25
    pad_comfortable: float = 0.35


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
