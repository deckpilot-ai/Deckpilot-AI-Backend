"""Automated PPT Design Configurator Tool.

Reverse-engineers complete visual design languages (grid vertical rhythm,
color palette tokens, typography pairing, and layout archetypes) directly
from user-supplied reference PowerPoint files (.pptx) and automatically
configures them into the DeckPilotAI design system.
"""

from collections import Counter
import io
import logging
import math
import os
import re
import uuid
from typing import Any

from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE, MSO_SHAPE_TYPE

logger = logging.getLogger(__name__)


def rgb_to_hex(rgb_tuple: tuple[int, int, int]) -> str:
    return f"#{rgb_tuple[0]:02X}{rgb_tuple[1]:02X}{rgb_tuple[2]:02X}"


def hex_to_rgb_tuple(hex_str: str) -> tuple[int, int, int]:
    h = hex_str.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def get_luminance(hex_str: str) -> float:
    r, g, b = hex_to_rgb_tuple(hex_str)
    return (0.299 * r + 0.587 * g + 0.114 * b) / 255.0


def lighten_hex(hex_str: str, amount: float = 0.90) -> str:
    """Derive a soft tint (90% lightened towards white) for cards and panels."""
    r, g, b = hex_to_rgb_tuple(hex_str)
    new_r = round(r + (255 - r) * amount)
    new_g = round(g + (255 - g) * amount)
    new_b = round(b + (255 - b) * amount)
    return rgb_to_hex((new_r, new_g, new_b))


class DesignAutoConfigurator:
    """Inspects, extracts, and automatically registers PPT designs into the system."""

    @classmethod
    def configure_from_pptx(
        cls,
        pptx_source: bytes | str,
        name: str | None = None,
        project_id: str | None = None,
        family_hint: str = "A",
    ) -> dict[str, Any]:
        """Reverse engineer PPTX file and register the extracted design preset."""
        if isinstance(pptx_source, str):
            with open(pptx_source, "rb") as f:
                pptx_bytes = f.read()
            detected_name = name or os.path.splitext(os.path.basename(pptx_source))[0]
        else:
            pptx_bytes = pptx_source
            detected_name = name or f"Imported Design {uuid.uuid4().hex[:6].upper()}"

        profile = cls.extract_design_language(pptx_bytes, detected_name)

        # Register preset into DesignPresetRegistry
        from app.services.design_preset_registry import DesignPresetRegistry
        preset_id = f"preset_{uuid.uuid4().hex[:8]}"

        preset_data = {
            "id": preset_id,
            "name": detected_name,
            "family": family_hint,
            "source": "imported_pptx",
            "colors": profile["palette"],
            "typography": profile["typography"],
            "grid": profile["grid"],
            "dimensions": profile["dimensions"],
            "detected_archetypes": profile["detected_archetypes"],
            "slide_count": profile["slide_count"],
        }

        registered = DesignPresetRegistry.register_preset(preset_data)

        # If project_id provided, link design preset to project
        if project_id:
            try:
                from app.db.engine import SessionLocal
                from app.models.project import Project
                with SessionLocal() as db:
                    proj = db.get(Project, project_id)
                    if proj:
                        current_config = proj.design_config if hasattr(proj, "design_config") else {}
                        if isinstance(current_config, dict):
                            current_config["preset_id"] = preset_id
                            current_config["brandStyle"] = {
                                "colors": profile["palette"],
                                "titleFont": {"name": profile["typography"]["title_font"]},
                                "bodyFont": {"name": profile["typography"]["body_font"]},
                            }
                        db.commit()
                        logger.info("Attached design preset %s to project %s", preset_id, project_id)
            except Exception as e:
                logger.warning("Could not persist preset to project %s: %s", project_id, e)

        return registered

    @classmethod
    def extract_design_language(cls, pptx_bytes: bytes, name: str = "Custom") -> dict[str, Any]:
        """Extract deep geometry, color tokens, typography, and archetype patterns."""
        prs = Presentation(io.BytesIO(pptx_bytes))
        slide_count = len(prs.slides)
        w_in = round(prs.slide_width.inches, 3)
        h_in = round(prs.slide_height.inches, 3)

        title_fonts = Counter()
        body_fonts = Counter()
        fill_colors = Counter()
        text_colors = Counter()
        bg_colors = Counter()

        # Vertical rhythm coordinates
        eyebrow_ys = []
        title_ys = []
        content_starts = []
        footer_ys = []

        detected_archetypes = []

        for slide_idx, slide in enumerate(prs.slides):
            shapes = slide.shapes
            shape_count = len(shapes)

            # Analyze background
            try:
                bg = slide.background
                if hasattr(bg, "fill") and bg.fill.type == 1:
                    rgb = bg.fill.fore_color.rgb
                    bg_colors[rgb_to_hex((rgb[0], rgb[1], rgb[2]))] += 1
            except Exception:
                pass

            cards_detected = 0
            has_table = False
            has_chart = False
            has_image = False
            has_arrows = False
            metrics_count = 0

            for shape in shapes:
                if shape.has_table:
                    has_table = True
                if shape.has_chart:
                    has_chart = True
                if shape.shape_type == MSO_SHAPE_TYPE.PICTURE:
                    has_image = True
                try:
                    if shape.shape_type == MSO_SHAPE_TYPE.AUTO_SHAPE and hasattr(shape, "auto_shape_type"):
                        if shape.auto_shape_type in (MSO_SHAPE.CHEVRON, MSO_SHAPE.RIGHT_ARROW):
                            has_arrows = True
                except Exception:
                    pass

                # Fill color extraction
                try:
                    if hasattr(shape, "fill") and shape.fill.type == 1:
                        rgb = shape.fill.fore_color.rgb
                        hex_c = rgb_to_hex((rgb[0], rgb[1], rgb[2]))
                        fill_colors[hex_c] += 1
                        # If large shape, count as card
                        if shape.width.inches > 2.0 and shape.height.inches > 1.0:
                            cards_detected += 1
                except Exception:
                    pass

                # Text and typography extraction
                if shape.has_text_frame:
                    top_in = shape.top.inches
                    for p in shape.text_frame.paragraphs:
                        font_name = p.font.name
                        font_size = p.font.size.pt if p.font.size else 14
                        text_str = p.text.strip()

                        if not text_str:
                            continue

                        # Check if title, eyebrow, or footer
                        if (font_size >= 24) or (top_in < 1.4 and shape.name.lower().startswith("title")):
                            if font_name:
                                title_fonts[font_name] += 1
                            title_ys.append(top_in)
                        elif top_in < 0.75 and font_size <= 15:
                            eyebrow_ys.append(top_in)
                            if font_name:
                                body_fonts[font_name] += 1
                        elif top_in >= 6.8:
                            footer_ys.append(top_in)
                            if font_name:
                                body_fonts[font_name] += 1
                        else:
                            content_starts.append(top_in)
                            if font_name:
                                body_fonts[font_name] += 1

                        # Detect metrics / stats (e.g. 85%, $12M, 3.4x)
                        if font_size >= 32 or re.match(r"^[\$€£]?\d+[\.,]?\d*[%xXkKMmB]?$", text_str):
                            metrics_count += 1

                        # Text color
                        try:
                            if p.font.color and p.font.color.rgb:
                                rgb = p.font.color.rgb
                                text_colors[rgb_to_hex((rgb[0], rgb[1], rgb[2]))] += 1
                        except Exception:
                            pass

            # Detect Archetype for this slide
            if slide_idx == 0:
                detected_archetypes.append("A2" if has_image else "A1")
            elif has_chart:
                detected_archetypes.append("A14")
            elif has_table:
                detected_archetypes.append("A16")
            elif has_image and metrics_count >= 1:
                detected_archetypes.append("A8")
            elif cards_detected == 2:
                detected_archetypes.append("A6")
            elif cards_detected == 3 and has_arrows:
                detected_archetypes.append("A10")
            elif cards_detected >= 4:
                detected_archetypes.append("A13")
            elif metrics_count >= 2:
                detected_archetypes.append("A15")
            elif slide_idx == slide_count - 1:
                detected_archetypes.append("A17")
            else:
                detected_archetypes.append("A7")

        # 1. Typography Resolution
        dominant_title_font = title_fonts.most_common(1)[0][0] if title_fonts else "Cambria"
        dominant_body_font = body_fonts.most_common(1)[0][0] if body_fonts else "Calibri"

        # 2. Color Token Classification
        # Filter fills (excluding pure white #FFFFFF)
        non_white_fills = [c for c, _ in fill_colors.most_common(20) if c.upper() != "#FFFFFF"]
        dark_fills = [c for c in non_white_fills if get_luminance(c) < 0.35]
        vibrant_fills = [c for c in non_white_fills if 0.25 <= get_luminance(c) <= 0.65]
        light_fills = [c for c in non_white_fills if get_luminance(c) > 0.65]

        # Determine ink (dark text / background)
        if dark_fills:
            ink = dark_fills[0]
        else:
            ink = "#0C3B39"

        # Determine primary accent (saturated brand color)
        if vibrant_fills:
            primary = vibrant_fills[0]
        elif non_white_fills:
            primary = non_white_fills[0]
        else:
            primary = "#0E7C7B"

        # Determine secondary accent
        candidates_sec = [c for c in non_white_fills if c not in (ink, primary)]
        if candidates_sec:
            secondary = candidates_sec[0]
        else:
            secondary = lighten_hex(primary, 0.25)

        # Derive tints
        if light_fills:
            tint_a = light_fills[0]
            tint_b = light_fills[1] if len(light_fills) > 1 else lighten_hex(ink, 0.94)
        else:
            tint_a = lighten_hex(primary, 0.90)
            tint_b = lighten_hex(ink, 0.94)

        alert = "#C63A28"

        palette = {
            "ink": ink,
            "primary": primary,
            "secondary": secondary,
            "accent": primary,
            "tint_a": tint_a,
            "tint_b": tint_b,
            "alert": alert,
            "background": "#FFFFFF",
            "paper": "#FAFAF9",
            "card_fill": tint_a,
            "neutral": tint_a,
            "text_primary": ink,
            "text_secondary": "#475569",
        }

        # 3. Grid Coordinates
        eyebrow_y = round(sum(eyebrow_ys) / max(1, len(eyebrow_ys)), 2) if eyebrow_ys else 0.45
        title_y = round(sum(title_ys) / max(1, len(title_ys)), 2) if title_ys else 0.85
        content_y = round(min(content_starts), 2) if content_starts else 1.95
        footer_y = round(sum(footer_ys) / max(1, len(footer_ys)), 2) if footer_ys else 7.05

        grid = {
            "eyebrow_y": eyebrow_y,
            "title_y": title_y,
            "accent_tick_y": 1.72,
            "content_start_y": content_y,
            "footer_y": footer_y,
            "margins_in": {"left": 0.6, "right": 0.6},
        }

        return {
            "name": name,
            "slide_count": slide_count,
            "dimensions": {"width_in": w_in, "height_in": h_in, "is_widescreen": (w_in / max(0.1, h_in)) > 1.5},
            "palette": palette,
            "typography": {
                "title_font": dominant_title_font,
                "body_font": dominant_body_font,
                "numeric_font": dominant_title_font,
            },
            "grid": grid,
            "detected_archetypes": list(dict.fromkeys(detected_archetypes)),
        }
