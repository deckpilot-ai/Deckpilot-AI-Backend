"""Deterministic Grid Engine for PowerPoint Presentation Layouts.

Computes exact coordinates, gutters, column spans, and card container slots
to guarantee alignment consistency across all slides and archetypes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RectArea:
    x: float
    y: float
    w: float
    h: float

    @property
    def right(self) -> float:
        return self.x + self.w

    @property
    def bottom(self) -> float:
        return self.y + self.h


@dataclass(frozen=True)
class CardSlot:
    index: int
    col: int
    row: int
    x: float
    y: float
    w: float
    h: float
    title_area: RectArea
    body_area: RectArea
    icon_area: RectArea | None = None

    @property
    def right(self) -> float:
        return self.x + self.w

    @property
    def bottom(self) -> float:
        return self.y + self.h

    @property
    def bounds(self) -> tuple[float, float, float, float]:
        return (self.x, self.y, self.w, self.h)


class PresentationGridEngine:
    """Computes exact coordinate geometry for slide layouts and cards."""

    CANVAS_WIDTH = 13.333
    CANVAS_HEIGHT = 7.500

    # Margins and content zones
    MARGIN_LEFT = 0.60
    MARGIN_RIGHT = 0.60
    HEADER_TOP = 0.45
    HEADER_HEIGHT = 1.45
    CONTENT_TOP = 2.15
    CONTENT_BOTTOM = 6.65
    FOOTER_TOP = 6.95

    # Safe usable content zone
    USABLE_WIDTH = round(CANVAS_WIDTH - MARGIN_LEFT - MARGIN_RIGHT, 3)  # 12.133"
    USABLE_HEIGHT = round(CONTENT_BOTTOM - CONTENT_TOP, 3)  # 4.500"

    # Default gutters
    DEFAULT_GUTTER_X = 0.35
    DEFAULT_GUTTER_Y = 0.35

    @classmethod
    def snap(cls, value: float, grid_step: float = 0.05) -> float:
        """Snaps a coordinate to the nearest grid step."""
        return round(round(value / grid_step) * grid_step, 3)

    @classmethod
    def snap_rect(cls, x: float, y: float, w: float, h: float, grid_step: float = 0.05) -> tuple[float, float, float, float]:
        """Snaps all 4 bounding box coordinates to the grid."""
        return (
            cls.snap(x, grid_step),
            cls.snap(y, grid_step),
            cls.snap(w, grid_step),
            cls.snap(h, grid_step),
        )

    @classmethod
    def compute_card_grid(
        cls,
        cols: int,
        rows: int = 1,
        margin_left: float = MARGIN_LEFT,
        content_top: float = CONTENT_TOP,
        total_w: float = USABLE_WIDTH,
        total_h: float = USABLE_HEIGHT,
        gutter_x: float = DEFAULT_GUTTER_X,
        gutter_y: float = DEFAULT_GUTTER_Y,
        card_padding: float = 0.25,
        title_h: float = 0.55,
        has_icons: bool = False,
        icon_size: float = 0.45,
    ) -> list[CardSlot]:
        """Computes uniform card slots for an N x M grid."""
        if cols <= 0 or rows <= 0:
            return []

        card_w = round((total_w - (cols - 1) * gutter_x) / cols, 3)
        card_h = round((total_h - (rows - 1) * gutter_y) / rows, 3)

        slots: list[CardSlot] = []
        idx = 0

        for r in range(rows):
            card_y = round(content_top + r * (card_h + gutter_y), 3)
            for c in range(cols):
                card_x = round(margin_left + c * (card_w + gutter_x), 3)

                inner_x = round(card_x + card_padding, 3)
                inner_w = round(card_w - 2 * card_padding, 3)

                icon_area = None
                curr_y = round(card_y + card_padding, 3)

                if has_icons:
                    icon_area = RectArea(
                        x=inner_x,
                        y=curr_y,
                        w=icon_size,
                        h=icon_size,
                    )
                    curr_y = round(curr_y + icon_size + 0.15, 3)

                title_area = RectArea(
                    x=inner_x,
                    y=curr_y,
                    w=inner_w,
                    h=title_h,
                )

                body_y = round(curr_y + title_h + 0.10, 3)
                body_h = max(0.4, round(card_y + card_h - card_padding - body_y, 3))
                body_area = RectArea(
                    x=inner_x,
                    y=body_y,
                    w=inner_w,
                    h=body_h,
                )

                slots.append(
                    CardSlot(
                        index=idx,
                        col=c,
                        row=r,
                        x=card_x,
                        y=card_y,
                        w=card_w,
                        h=card_h,
                        title_area=title_area,
                        body_area=body_area,
                        icon_area=icon_area,
                    )
                )
                idx += 1

        return slots

    @classmethod
    def compute_equal_columns(
        cls,
        count: int,
        margin_left: float = MARGIN_LEFT,
        content_top: float = CONTENT_TOP,
        total_w: float = USABLE_WIDTH,
        height: float = USABLE_HEIGHT,
        gap: float = DEFAULT_GUTTER_X,
        card_padding: float = 0.25,
        title_h: float = 0.55,
        has_icons: bool = False,
    ) -> list[CardSlot]:
        """Convenience method for a 1-row multi-column layout."""
        return cls.compute_card_grid(
            cols=count,
            rows=1,
            margin_left=margin_left,
            content_top=content_top,
            total_w=total_w,
            total_h=height,
            gutter_x=gap,
            card_padding=card_padding,
            title_h=title_h,
            has_icons=has_icons,
        )

    @classmethod
    def compute_two_column(
        cls,
        left_ratio: float = 0.50,
        gap: float = 0.40,
        margin_left: float = MARGIN_LEFT,
        content_top: float = CONTENT_TOP,
        total_w: float = USABLE_WIDTH,
        height: float = USABLE_HEIGHT,
        card_padding: float = 0.25,
    ) -> tuple[CardSlot, CardSlot]:
        """Computes 2 asymmetric or symmetric column slots."""
        usable_for_cols = total_w - gap
        left_w = round(usable_for_cols * left_ratio, 3)
        right_w = round(usable_for_cols * (1.0 - left_ratio), 3)

        left_x = margin_left
        right_x = round(margin_left + left_w + gap, 3)

        left_slot = CardSlot(
            index=0,
            col=0,
            row=0,
            x=left_x,
            y=content_top,
            w=left_w,
            h=height,
            title_area=RectArea(round(left_x + card_padding, 3), round(content_top + card_padding, 3), round(left_w - 2 * card_padding, 3), 0.6),
            body_area=RectArea(round(left_x + card_padding, 3), round(content_top + card_padding + 0.7, 3), round(left_w - 2 * card_padding, 3), round(height - 2 * card_padding - 0.7, 3)),
        )

        right_slot = CardSlot(
            index=1,
            col=1,
            row=0,
            x=right_x,
            y=content_top,
            w=right_w,
            h=height,
            title_area=RectArea(round(right_x + card_padding, 3), round(content_top + card_padding, 3), round(right_w - 2 * card_padding, 3), 0.6),
            body_area=RectArea(round(right_x + card_padding, 3), round(content_top + card_padding + 0.7, 3), round(right_w - 2 * card_padding, 3), round(height - 2 * card_padding - 0.7, 3)),
        )

        return (left_slot, right_slot)
