"""2D Geometry, Bounding-Box Alignment, and Collision Detection Engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.schemas.generation_state import (
    ValidationCategory,
    ValidationIssue,
    ValidationSeverity,
)


@dataclass
class BoundingBox:
    id: str
    name: str
    kind: str  # "card", "text", "icon", "image", "badge", "chart", "table", "footer", "header"
    x: float
    y: float
    w: float
    h: float
    parent_id: str | None = None
    allow_containment: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def right(self) -> float:
        return self.x + self.w

    @property
    def bottom(self) -> float:
        return self.y + self.h

    @property
    def area(self) -> float:
        return max(0.0, self.w) * max(0.0, self.h)

    def intersects(self, other: BoundingBox, buffer: float = 0.03) -> bool:
        """Checks if two boxes intersect with an optional tolerance buffer (in inches)."""
        ix = min(self.right, other.right) - max(self.x, other.x)
        iy = min(self.bottom, other.bottom) - max(self.y, other.y)
        return ix > buffer and iy > buffer

    def intersection_area(self, other: BoundingBox) -> float:
        """Calculates area of intersection in square inches."""
        ix = max(0.0, min(self.right, other.right) - max(self.x, other.x))
        iy = max(0.0, min(self.bottom, other.bottom) - max(self.y, other.y))
        return ix * iy

    def contains(self, other: BoundingBox, margin: float = 0.08) -> bool:
        """Returns True if self contains other (with margin tolerance)."""
        return (
            self.x - margin <= other.x
            and self.y - margin <= other.y
            and self.right + margin >= other.right
            and self.bottom + margin >= other.bottom
        )


class CollisionDetectionEngine:
    """Detects element collisions, canvas out-of-bounds, alignment drift, and layout defects."""

    CANVAS_WIDTH = 13.333
    CANVAS_HEIGHT = 7.500
    SAFE_MARGIN_LEFT = 0.50
    SAFE_MARGIN_RIGHT = 0.50
    SAFE_MARGIN_TOP = 0.40
    SAFE_MARGIN_BOTTOM = 0.40

    @classmethod
    def detect_collisions(
        cls,
        slide_number: int,
        boxes: list[BoundingBox],
        canvas_w: float = CANVAS_WIDTH,
        canvas_h: float = CANVAS_HEIGHT,
    ) -> list[ValidationIssue]:
        """Detects all collisions, container violations, and margin intrusions on a slide."""
        issues: list[ValidationIssue] = []
        n = len(boxes)

        for i in range(n):
            box_a = boxes[i]

            # 1. Canvas Boundary Check
            if (
                box_a.x < -0.05
                or box_a.y < -0.05
                or box_a.right > canvas_w + 0.05
                or box_a.bottom > canvas_h + 0.05
            ):
                issues.append(
                    ValidationIssue(
                        checkpoint_id="QA-037",
                        severity=ValidationSeverity.CRITICAL if (box_a.x < -0.2 or box_a.bottom > canvas_h + 0.2) else ValidationSeverity.HIGH,
                        category=ValidationCategory.GEOMETRY,
                        slide_number=slide_number,
                        message=(
                            f"Element '{box_a.name}' ({box_a.kind}) extends outside slide canvas: "
                            f"x={box_a.x:.2f}, y={box_a.y:.2f}, w={box_a.w:.2f}, h={box_a.h:.2f} "
                            f"(canvas bounds: {canvas_w:.2f}x{canvas_h:.2f}\")"
                        ),
                        suggested_fix="Adjust element placement to keep within canvas margins",
                        auto_fixable=True,
                        repair_action="constrain_bounds",
                    )
                )

            # 2. Footer Zone Intrusion (bottom 0.45 inches reserved for footer and page markers)
            if box_a.kind not in ("footer", "page_number", "background") and box_a.bottom > (canvas_h - 0.35):
                issues.append(
                    ValidationIssue(
                        checkpoint_id="QA-042",
                        severity=ValidationSeverity.HIGH,
                        category=ValidationCategory.GEOMETRY,
                        slide_number=slide_number,
                        message=f"Element '{box_a.name}' ({box_a.kind}) collides with footer margin at y={box_a.bottom:.2f}\"",
                        suggested_fix="Reduce element height or shift upward above y=7.05\"",
                        auto_fixable=True,
                        repair_action="constrain_bounds",
                    )
                )

            # Pairwise Collision Checks
            for j in range(i + 1, n):
                box_b = boxes[j]

                # Ignore background accents or elements intentionally linked by parent-child hierarchy
                if box_a.kind == "background" or box_b.kind == "background":
                    continue
                if box_a.parent_id == box_b.id or box_b.parent_id == box_a.id:
                    continue
                if box_a.parent_id and box_a.parent_id == box_b.parent_id:
                    # Siblings inside the same card (e.g. card title vs card body text)
                    if box_a.intersects(box_b, buffer=0.04):
                        issues.append(
                            ValidationIssue(
                                checkpoint_id="QA-040",
                                severity=ValidationSeverity.CRITICAL,
                                category=ValidationCategory.GEOMETRY,
                                slide_number=slide_number,
                                message=f"Internal collision inside card: '{box_a.name}' overlaps sibling '{box_b.name}'",
                                suggested_fix="Separate card title and body with vertical spacing gap",
                                auto_fixable=True,
                                repair_action="resolve_overlap",
                            )
                        )
                    continue

                # Check if one box legitimately contains the other (e.g. text or badge inside card container)
                if (box_a.kind in ("card", "shape") and box_b.kind in ("text", "icon", "badge", "image", "shape") and box_a.contains(box_b)) or \
                   (box_b.kind in ("card", "shape") and box_a.kind in ("text", "icon", "badge", "image", "shape") and box_b.contains(box_a)) or \
                   (box_a.kind == "badge" and box_b.kind in ("icon", "text") and box_a.contains(box_b)) or \
                   (box_b.kind == "badge" and box_a.kind in ("icon", "text") and box_b.contains(box_a)):
                    continue

                if box_a.intersects(box_b, buffer=0.03):
                    overlap_sq_in = box_a.intersection_area(box_b)
                    if overlap_sq_in > 0.02:
                        # Categorize specific collision type
                        kinds = {box_a.kind, box_b.kind}
                        if "text" in kinds and "image" in kinds:
                            chk_id = "QA-041"
                            sev = ValidationSeverity.CRITICAL
                            msg = f"Text '{box_a.name}' directly collides with image '{box_b.name}' (overlap={overlap_sq_in:.2f} sq in)"
                        elif "text" in kinds and "icon" in kinds:
                            chk_id = "QA-040"
                            sev = ValidationSeverity.CRITICAL
                            msg = f"Text '{box_a.name}' directly collides with icon '{box_b.name}' (overlap={overlap_sq_in:.2f} sq in)"
                        elif box_a.kind == "card" and box_b.kind == "card":
                            chk_id = "QA-040"
                            sev = ValidationSeverity.CRITICAL
                            msg = f"Card '{box_a.name}' collides with adjacent card '{box_b.name}' (overlap={overlap_sq_in:.2f} sq in)"
                        elif box_a.kind == "text" and box_b.kind == "text":
                            chk_id = "QA-040"
                            sev = ValidationSeverity.CRITICAL
                            msg = f"Text box '{box_a.name}' collides with text box '{box_b.name}' (overlap={overlap_sq_in:.2f} sq in)"
                        else:
                            chk_id = "QA-040"
                            sev = ValidationSeverity.HIGH
                            msg = f"Element '{box_a.name}' ({box_a.kind}) collides with '{box_b.name}' ({box_b.kind})"

                        issues.append(
                            ValidationIssue(
                                checkpoint_id=chk_id,
                                severity=sev,
                                category=ValidationCategory.GEOMETRY,
                                slide_number=slide_number,
                                message=msg,
                                suggested_fix="Adjust element positions to maintain at least 0.15\" separation",
                                auto_fixable=True,
                                repair_action="resolve_overlap",
                            )
                        )

        return issues

    @classmethod
    def validate_card_alignment(
        cls,
        slide_number: int,
        cards: list[BoundingBox],
    ) -> list[ValidationIssue]:
        """Validates that multi-card row elements share consistent top coordinates, heights, and gutters."""
        issues: list[ValidationIssue] = []
        if len(cards) < 2:
            return issues

        # Sort cards by X coordinate
        sorted_cards = sorted(cards, key=lambda c: c.x)

        # Check if cards are intended to be a horizontal row
        y_coords = [c.y for c in sorted_cards]
        avg_y = sum(y_coords) / len(y_coords)
        is_row = all(abs(y - avg_y) < 0.8 for y in y_coords)

        if is_row:
            # 1. Top Alignment Check
            max_y_drift = max(abs(y - avg_y) for y in y_coords)
            if max_y_drift > 0.05:
                issues.append(
                    ValidationIssue(
                        checkpoint_id="QA-045",
                        severity=ValidationSeverity.HIGH if max_y_drift > 0.15 else ValidationSeverity.MEDIUM,
                        category=ValidationCategory.GEOMETRY,
                        slide_number=slide_number,
                        message=f"Card row exhibits top alignment drift of {max_y_drift:.2f}\" across {len(cards)} cards",
                        suggested_fix="Align all cards in row to a shared Y top baseline",
                        auto_fixable=True,
                        repair_action="align_columns",
                    )
                )

            # 2. Card Height Consistency Check
            heights = [c.h for c in sorted_cards]
            avg_h = sum(heights) / len(heights)
            max_h_drift = max(abs(h - avg_h) for h in heights)
            if max_h_drift > 0.08:
                issues.append(
                    ValidationIssue(
                        checkpoint_id="QA-045",
                        severity=ValidationSeverity.MEDIUM,
                        category=ValidationCategory.GEOMETRY,
                        slide_number=slide_number,
                        message=f"Inconsistent card heights in row: variation of {max_h_drift:.2f}\" (range: {min(heights):.2f}\" to {max(heights):.2f}\")",
                        suggested_fix="Standardize all card heights to the maximum required height",
                        auto_fixable=True,
                        repair_action="align_columns",
                    )
                )

            # 3. Gutter Consistency Check
            if len(sorted_cards) >= 3:
                gutters = [
                    round(sorted_cards[i + 1].x - sorted_cards[i].right, 3)
                    for i in range(len(sorted_cards) - 1)
                ]
                avg_gutter = sum(gutters) / len(gutters)
                max_gutter_drift = max(abs(g - avg_gutter) for g in gutters)
                if max_gutter_drift > 0.06:
                    issues.append(
                        ValidationIssue(
                            checkpoint_id="QA-046",
                            severity=ValidationSeverity.MEDIUM,
                            category=ValidationCategory.GEOMETRY,
                            slide_number=slide_number,
                            message=f"Uneven gutters between cards: variation of {max_gutter_drift:.2f}\" (gutters: {gutters})",
                            suggested_fix="Normalize gutters to equal spacing using (canvas_width - margins) / (cols - 1)",
                            auto_fixable=True,
                            repair_action="normalize_gutters",
                        )
                    )

        return issues
