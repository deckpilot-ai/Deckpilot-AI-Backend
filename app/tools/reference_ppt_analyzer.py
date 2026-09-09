"""Reference PPT analyzer tool for extracting design profiles from benchmark and uploaded decks."""

import io
import logging
from collections import Counter
from typing import Any

from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE

logger = logging.getLogger(__name__)


class ReferencePPTAnalyzer:
    """Extracts design language, layout distribution, fonts, and colors from reference PPTX files."""

    @classmethod
    def analyze_presentation(cls, pptx_bytes: bytes, filename: str = "reference.pptx") -> dict[str, Any]:
        profile: dict[str, Any] = {
            "filename": filename,
            "slide_count": 0,
            "dimensions": {"width_in": 13.333, "height_in": 7.5, "is_widescreen": True},
            "fonts": {"title_fonts": [], "body_fonts": [], "dominant_title_font": "Segoe UI", "dominant_body_font": "Segoe UI"},
            "colors": {"fill_colors": [], "text_colors": [], "primary_hint": "#132A52", "accent_hint": "#2563EB", "background_hint": "#FFFFFF"},
            "layout_patterns": [],
            "content_density": {"avg_shapes_per_slide": 0.0, "has_charts": False, "has_tables": False, "has_images": False},
        }

        try:
            prs = Presentation(io.BytesIO(pptx_bytes))
            slide_count = len(prs.slides)
            profile["slide_count"] = slide_count
            w_in = prs.slide_width.inches
            h_in = prs.slide_height.inches
            profile["dimensions"] = {
                "width_in": round(w_in, 2),
                "height_in": round(h_in, 2),
                "is_widescreen": (w_in / max(0.1, h_in)) > 1.5,
            }

            title_fonts = Counter()
            body_fonts = Counter()
            fill_colors = Counter()
            text_colors = Counter()
            shape_counts = []
            has_charts = False
            has_tables = False
            has_images = False

            for slide_idx, slide in enumerate(prs.slides):
                shape_counts.append(len(slide.shapes))
                for shape in slide.shapes:
                    if shape.has_chart:
                        has_charts = True
                    if shape.has_table:
                        has_tables = True
                    if shape.shape_type == MSO_SHAPE_TYPE.PICTURE:
                        has_images = True

                    # Extract fill colors
                    try:
                        if hasattr(shape, "fill") and shape.fill.type == 1:  # solid fill
                            rgb = shape.fill.fore_color.rgb
                            fill_colors[f"#{rgb[0]:02X}{rgb[1]:02X}{rgb[2]:02X}"] += 1
                    except Exception:
                        pass

                    # Extract text font and color
                    if shape.has_text_frame:
                        for p in shape.text_frame.paragraphs:
                            is_title = (p.font.size and p.font.size.pt >= 20) or shape.name.lower().startswith("title")
                            font_name = p.font.name or "Segoe UI"
                            if is_title:
                                title_fonts[font_name] += 1
                            else:
                                body_fonts[font_name] += 1

                            try:
                                if p.font.color and p.font.color.rgb:
                                    rgb = p.font.color.rgb
                                    text_colors[f"#{rgb[0]:02X}{rgb[1]:02X}{rgb[2]:02X}"] += 1
                            except Exception:
                                pass

            profile["fonts"]["dominant_title_font"] = title_fonts.most_common(1)[0][0] if title_fonts else "Segoe UI"
            profile["fonts"]["dominant_body_font"] = body_fonts.most_common(1)[0][0] if body_fonts else "Segoe UI"
            profile["fonts"]["title_fonts"] = [f for f, _ in title_fonts.most_common(3)]
            profile["fonts"]["body_fonts"] = [f for f, _ in body_fonts.most_common(3)]

            # Derive dominant colors
            top_fills = [c for c, _ in fill_colors.most_common(6) if c != "#FFFFFF"]
            if top_fills:
                profile["colors"]["primary_hint"] = top_fills[0]
                if len(top_fills) > 1:
                    profile["colors"]["accent_hint"] = top_fills[1]

            profile["content_density"]["avg_shapes_per_slide"] = round(sum(shape_counts) / max(1, len(shape_counts)), 1)
            profile["content_density"]["has_charts"] = has_charts
            profile["content_density"]["has_tables"] = has_tables
            profile["content_density"]["has_images"] = has_images

        except Exception as e:
            logger.warning("Error analyzing reference PPT %s: %s", filename, e)

        return profile
