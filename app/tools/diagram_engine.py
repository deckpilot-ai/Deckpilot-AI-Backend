"""Structured diagram engine tool for rendering process flows, matrices, timelines, and hierarchies."""

import logging
from typing import Any

from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

from app.schemas.generation_state import DesignSystem, DiagramSpec

logger = logging.getLogger(__name__)


def hex_to_rgb(hex_str: str, default: tuple[int, int, int] = (37, 99, 235)) -> RGBColor:
    val = hex_str.lstrip("#")
    try:
        return RGBColor(int(val[0:2], 16), int(val[2:4], 16), int(val[4:6], 16))
    except Exception:
        return RGBColor(*default)


def tint_rgb(color: RGBColor, amount: float) -> RGBColor:
    return RGBColor(*(round(c + (255 - c) * amount) for c in color))


class DiagramEngine:
    """Renders structured conceptual diagrams using PowerPoint shapes and typography."""

    @classmethod
    def render_diagram(
        cls,
        slide: Any,
        diagram_spec: DiagramSpec,
        design_system: DesignSystem,
        x: float,
        y: float,
        w: float,
        h: float,
    ) -> list[Any]:
        dtype = diagram_spec.diagram_type.lower()
        if dtype in ("process", "process_steps", "workflow"):
            return cls._render_process_flow(slide, diagram_spec, design_system, x, y, w, h)
        elif dtype in ("matrix", "quadrant", "2x2"):
            return cls._render_matrix_quadrant(slide, diagram_spec, design_system, x, y, w, h)
        elif dtype in ("hierarchy", "hub_spoke", "architecture"):
            return cls._render_hub_and_spoke(slide, diagram_spec, design_system, x, y, w, h)
        elif dtype in ("pyramid", "funnel"):
            return cls._render_pyramid(slide, diagram_spec, design_system, x, y, w, h)
        else:
            return cls._render_process_flow(slide, diagram_spec, design_system, x, y, w, h)

    @classmethod
    def _render_process_flow(
        cls,
        slide: Any,
        spec: DiagramSpec,
        ds: DesignSystem,
        x: float,
        y: float,
        w: float,
        h: float,
    ) -> list[Any]:
        created_shapes = []
        nodes = spec.nodes or []
        count = max(1, len(nodes))
        primary = hex_to_rgb(ds.colors.primary)
        accent = hex_to_rgb(ds.colors.accent)
        card_fill = tint_rgb(primary, 0.94)
        white = RGBColor(255, 255, 255)
        text_primary = hex_to_rgb(ds.colors.text_primary)
        text_secondary = hex_to_rgb(ds.colors.text_secondary)

        gap = 0.25
        card_w = (w - gap * (count - 1)) / count
        card_h = min(h, 3.8)

        for i, node in enumerate(nodes):
            cx = x + i * (card_w + gap)
            # Card base
            card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(cx), Inches(y), Inches(card_w), Inches(card_h))
            card.fill.solid()
            card.fill.fore_color.rgb = card_fill
            card.line.fill.background()
            card.adjustments[0] = 0.06
            created_shapes.append(card)

            # Step badge circle
            badge = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(cx + 0.2), Inches(y + 0.25), Inches(0.48), Inches(0.48))
            badge.fill.solid()
            badge.fill.fore_color.rgb = accent
            badge.line.fill.background()
            p_badge = badge.text_frame.paragraphs[0]
            p_badge.text = f"{i+1}"
            p_badge.font.name = ds.typography.body_font.name
            p_badge.font.size = Pt(12)
            p_badge.font.bold = True
            p_badge.font.color.rgb = white
            p_badge.alignment = PP_ALIGN.CENTER
            badge.text_frame.vertical_anchor = MSO_ANCHOR.MIDDLE
            created_shapes.append(badge)

            # Node label
            tb_label = slide.shapes.add_textbox(Inches(cx + 0.2), Inches(y + 0.85), Inches(card_w - 0.4), Inches(0.6))
            p_label = tb_label.text_frame.paragraphs[0]
            p_label.text = node.label or f"Phase {i+1}"
            p_label.font.name = ds.typography.title_font.name
            p_label.font.size = Pt(13)
            p_label.font.bold = True
            p_label.font.color.rgb = text_primary
            created_shapes.append(tb_label)

            # Node subtext
            if node.subtext:
                tb_sub = slide.shapes.add_textbox(Inches(cx + 0.2), Inches(y + 1.45), Inches(card_w - 0.4), Inches(card_h - 1.6))
                tb_sub.text_frame.word_wrap = True
                p_sub = tb_sub.text_frame.paragraphs[0]
                p_sub.text = node.subtext
                p_sub.font.name = ds.typography.body_font.name
                p_sub.font.size = Pt(11)
                p_sub.font.color.rgb = text_secondary
                created_shapes.append(tb_sub)

            # Connector chevron between cards
            if i < count - 1:
                chev_x = cx + card_w + (gap - 0.16) / 2.0
                chev = slide.shapes.add_shape(MSO_SHAPE.CHEVRON, Inches(chev_x), Inches(y + card_h / 2 - 0.12), Inches(0.16), Inches(0.24))
                chev.fill.solid()
                chev.fill.fore_color.rgb = accent
                chev.line.fill.background()
                created_shapes.append(chev)

        return created_shapes

    @classmethod
    def _render_matrix_quadrant(
        cls,
        slide: Any,
        spec: DiagramSpec,
        ds: DesignSystem,
        x: float,
        y: float,
        w: float,
        h: float,
    ) -> list[Any]:
        created_shapes = []
        primary = hex_to_rgb(ds.colors.primary)
        accent = hex_to_rgb(ds.colors.accent)
        card_fill = tint_rgb(primary, 0.94)
        accent_fill = tint_rgb(accent, 0.92)
        text_primary = hex_to_rgb(ds.colors.text_primary)
        text_secondary = hex_to_rgb(ds.colors.text_secondary)

        half_w = (w - 0.3) / 2.0
        half_h = (h - 0.3) / 2.0

        quadrant_keys = ["Q1", "Q2", "Q3", "Q4"]
        titles = {
            "Q1": "High Impact · Fast Execution",
            "Q2": "Strategic Vision · Core Investment",
            "Q3": "Operational Hygiene · Maintenance",
            "Q4": "Secondary Priorities · Low Leverage",
        }

        nodes_by_q = {q: [] for q in quadrant_keys}
        for idx, node in enumerate(spec.nodes):
            q_key = quadrant_keys[idx % 4]
            nodes_by_q[q_key].append(node)

        positions = [
            (x, y, "Q1"),
            (x + half_w + 0.3, y, "Q2"),
            (x, y + half_h + 0.3, "Q3"),
            (x + half_w + 0.3, y + half_h + 0.3, "Q4"),
        ]

        for qx, qy, qk in positions:
            is_priority = qk in ("Q1", "Q2")
            box = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(qx), Inches(qy), Inches(half_w), Inches(half_h))
            box.fill.solid()
            box.fill.fore_color.rgb = accent_fill if is_priority else card_fill
            box.line.fill.background()
            box.adjustments[0] = 0.05
            created_shapes.append(box)

            tb = slide.shapes.add_textbox(Inches(qx + 0.2), Inches(qy + 0.15), Inches(half_w - 0.4), Inches(0.45))
            p = tb.text_frame.paragraphs[0]
            p.text = titles.get(qk, qk)
            p.font.name = ds.typography.title_font.name
            p.font.size = Pt(12)
            p.font.bold = True
            p.font.color.rgb = text_primary
            created_shapes.append(tb)

            q_nodes = nodes_by_q.get(qk, [])
            if q_nodes:
                tb_body = slide.shapes.add_textbox(Inches(qx + 0.2), Inches(qy + 0.65), Inches(half_w - 0.4), Inches(half_h - 0.8))
                tb_body.text_frame.word_wrap = True
                for n_idx, n in enumerate(q_nodes):
                    p_item = tb_body.text_frame.paragraphs[0] if n_idx == 0 else tb_body.text_frame.add_paragraph()
                    p_item.text = f"• {n.label}" + (f": {n.subtext}" if n.subtext else "")
                    p_item.font.name = ds.typography.body_font.name
                    p_item.font.size = Pt(11)
                    p_item.font.color.rgb = text_secondary
                created_shapes.append(tb_body)

        return created_shapes

    @classmethod
    def _render_hub_and_spoke(
        cls,
        slide: Any,
        spec: DiagramSpec,
        ds: DesignSystem,
        x: float,
        y: float,
        w: float,
        h: float,
    ) -> list[Any]:
        created_shapes = []
        primary = hex_to_rgb(ds.colors.primary)
        accent = hex_to_rgb(ds.colors.accent)
        card_fill = tint_rgb(primary, 0.94)
        white = RGBColor(255, 255, 255)
        text_primary = hex_to_rgb(ds.colors.text_primary)

        # Center hub
        hub_w, hub_h = 3.2, 1.4
        hub_x = x + (w - hub_w) / 2.0
        hub_y = y + (h - hub_h) / 2.0

        hub = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(hub_x), Inches(hub_y), Inches(hub_w), Inches(hub_h))
        hub.fill.solid()
        hub.fill.fore_color.rgb = accent
        hub.line.fill.background()
        hub.adjustments[0] = 0.08
        p_hub = hub.text_frame.paragraphs[0]
        p_hub.text = spec.center_hub or "Core Platform / Strategy"
        p_hub.font.name = ds.typography.title_font.name
        p_hub.font.size = Pt(13)
        p_hub.font.bold = True
        p_hub.font.color.rgb = white
        p_hub.alignment = PP_ALIGN.CENTER
        hub.text_frame.vertical_anchor = MSO_ANCHOR.MIDDLE
        created_shapes.append(hub)

        nodes = spec.nodes or []
        left_nodes = nodes[:3]
        right_nodes = nodes[3:6]

        # Left flank
        for idx, node in enumerate(left_nodes):
            ny = y + idx * 1.3
            card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(ny), Inches(3.6), Inches(1.1))
            card.fill.solid()
            card.fill.fore_color.rgb = card_fill
            card.line.fill.background()
            p = card.text_frame.paragraphs[0]
            p.text = node.label + (f"\n{node.subtext}" if node.subtext else "")
            p.font.name = ds.typography.body_font.name
            p.font.size = Pt(11)
            p.font.color.rgb = text_primary
            created_shapes.append(card)

            # Connector
            conn = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x + 3.6), Inches(ny + 0.52), Inches(hub_x - (x + 3.6)), Inches(0.03))
            conn.fill.solid()
            conn.fill.fore_color.rgb = accent
            conn.line.fill.background()
            created_shapes.append(conn)

        # Right flank
        right_x = hub_x + hub_w + 0.6
        for idx, node in enumerate(right_nodes):
            ny = y + idx * 1.3
            card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(right_x), Inches(ny), Inches(3.6), Inches(1.1))
            card.fill.solid()
            card.fill.fore_color.rgb = card_fill
            card.line.fill.background()
            p = card.text_frame.paragraphs[0]
            p.text = node.label + (f"\n{node.subtext}" if node.subtext else "")
            p.font.name = ds.typography.body_font.name
            p.font.size = Pt(11)
            p.font.color.rgb = text_primary
            created_shapes.append(card)

            # Connector
            conn = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(hub_x + hub_w), Inches(ny + 0.52), Inches(right_x - (hub_x + hub_w)), Inches(0.03))
            conn.fill.solid()
            conn.fill.fore_color.rgb = accent
            conn.line.fill.background()
            created_shapes.append(conn)

        return created_shapes

    @classmethod
    def _render_pyramid(
        cls,
        slide: Any,
        spec: DiagramSpec,
        ds: DesignSystem,
        x: float,
        y: float,
        w: float,
        h: float,
    ) -> list[Any]:
        created_shapes = []
        nodes = spec.nodes or []
        count = max(1, min(len(nodes), 4))
        primary = hex_to_rgb(ds.colors.primary)
        accent = hex_to_rgb(ds.colors.accent)
        white = RGBColor(255, 255, 255)

        layer_h = (h - 0.2 * (count - 1)) / count
        colors = [accent, tint_rgb(accent, 0.3), tint_rgb(primary, 0.4), primary]

        for i, node in enumerate(nodes[:count]):
            layer_w = w * (0.4 + 0.6 * (i / max(1, count - 1)))
            lx = x + (w - layer_w) / 2.0
            ly = y + i * (layer_h + 0.2)

            box = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(lx), Inches(ly), Inches(layer_w), Inches(layer_h))
            box.fill.solid()
            box.fill.fore_color.rgb = colors[i % len(colors)]
            box.line.fill.background()
            p = box.text_frame.paragraphs[0]
            p.text = f"{node.label}" + (f" — {node.subtext}" if node.subtext else "")
            p.font.name = ds.typography.body_font.name
            p.font.size = Pt(12)
            p.font.bold = True
            p.font.color.rgb = white
            p.alignment = PP_ALIGN.CENTER
            box.text_frame.vertical_anchor = MSO_ANCHOR.MIDDLE
            created_shapes.append(box)

        return created_shapes
