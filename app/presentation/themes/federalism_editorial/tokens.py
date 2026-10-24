"""Centralized Design System Tokens for Federalism Editorial Theme.

Extracts and formalizes exact DrawingML colors, dimensions, geometry,
shadows, and spacing rules from benchmark deck 'Federalism (2).pptx'.
"""

from dataclasses import dataclass
from pptx.dml.color import RGBColor


@dataclass(frozen=True)
class ColorTokens:
    # Hex values
    hex_dark: str = "#0C3B39"
    hex_dark_alt: str = "#11504C"
    hex_primary_teal: str = "#0E7C7B"
    hex_secondary_teal: str = "#16A085"
    hex_accent_orange: str = "#E08A1E"
    hex_negative_red: str = "#C63A28"
    hex_pale_negative: str = "#F6E0DB"
    hex_panel_teal: str = "#E9F3F1"
    hex_warm_cream: str = "#F6EFE2"
    hex_body_ink: str = "#1E2B2A"
    hex_muted_text: str = "#6B7A78"
    hex_text_on_dark: str = "#CFE7E3"
    hex_ghost_teal: str = "#D8EAE7"
    hex_border_teal: str = "#CFE0DD"
    hex_border_warm: str = "#E6D8BF"
    hex_white: str = "#FFFFFF"

    # RGBColor objects for python-pptx
    rgb_dark: RGBColor = RGBColor(0x0C, 0x3B, 0x39)
    rgb_dark_alt: RGBColor = RGBColor(0x11, 0x50, 0x4C)
    rgb_primary_teal: RGBColor = RGBColor(0x0E, 0x7C, 0x7B)
    rgb_secondary_teal: RGBColor = RGBColor(0x16, 0xA0, 0x85)
    rgb_accent_orange: RGBColor = RGBColor(0xE0, 0x8A, 0x1E)
    rgb_negative_red: RGBColor = RGBColor(0xC6, 0x3A, 0x28)
    rgb_pale_negative: RGBColor = RGBColor(0xF6, 0xE0, 0xDB)
    rgb_panel_teal: RGBColor = RGBColor(0xE9, 0xF3, 0xF1)
    rgb_warm_cream: RGBColor = RGBColor(0xF6, 0xEF, 0xE2)
    rgb_body_ink: RGBColor = RGBColor(0x1E, 0x2B, 0x2A)
    rgb_muted_text: RGBColor = RGBColor(0x6B, 0x7A, 0x78)
    rgb_text_on_dark: RGBColor = RGBColor(0xCF, 0xE7, 0xE3)
    rgb_ghost_teal: RGBColor = RGBColor(0xD8, 0xEA, 0xE7)
    rgb_border_teal: RGBColor = RGBColor(0xCF, 0xE0, 0xDD)
    rgb_border_warm: RGBColor = RGBColor(0xE6, 0xD8, 0xBF)
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
    safe_left: float = 0.70
    safe_right: float = 0.70
    safe_top: float = 0.55
    safe_bottom: float = 0.45
    content_bottom: float = 6.80
    footer_top: float = 7.00
    footer_left: float = 0.60
    footer_right_w: float = 0.80

    # Title Accent Line
    title_accent_x: float = 0.72
    title_accent_y: float = 1.72
    title_accent_w: float = 0.60
    title_accent_h: float = 0.06

    # Card internal padding standards
    pad_compact: float = 0.20
    pad_standard: float = 0.28
    pad_comfortable: float = 0.35


@dataclass(frozen=True)
class ShadowTokens:
    blur_rad_emu: int = 114300  # 9pt
    dist_emu: int = 38100       # 3pt
    dir_deg: int = 5400000      # 90 degrees straight down
    color_hex: str = "000000"
    alpha_val: int = 18000      # 18% opacity


@dataclass(frozen=True)
class SpacingTokens:
    xs: float = 0.08
    sm: float = 0.15
    md: float = 0.25
    lg: float = 0.40
    xl: float = 0.60


COLORS = ColorTokens()
FONTS = FontTokens()
GEOMETRY = GeometryTokens()
SHADOWS = ShadowTokens()
SPACING = SpacingTokens()
