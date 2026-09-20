"""Slide visual rendering and computer-vision inspection engine."""

from __future__ import annotations

import io
import logging
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from typing import Any

import numpy as np
from PIL import Image
import pymupdf

from app.agents.qa_checkpoints import CHECKPOINT_BY_ID, CHECKPOINT_ID_BY_SLUG
from app.schemas.generation_state import (
    LayoutFamily,
    SlideSpec,
    ValidationCategory,
    ValidationIssue,
    ValidationSeverity,
)

logger = logging.getLogger(__name__)

_SPARSE_ALLOWED_LAYOUTS = {
    LayoutFamily.HERO,
    LayoutFamily.CLOSING,
    LayoutFamily.SECTION_DIVIDER,
    LayoutFamily.A1_TITLE_BLOB,
    LayoutFamily.A2_TITLE_SPLIT,
    LayoutFamily.A3_DIVIDER_HERO,
    LayoutFamily.A17_CLOSING_TAKEAWAYS,
}


class SlideVisualInspector:
    """Renders PPTX slides into high-resolution images and applies computer-vision inspection."""

    @classmethod
    def _render_via_com(
        cls,
        pptx_bytes: bytes,
        output_dir: Path | None,
        dpi: int = 150,
    ) -> list[tuple[int, bytes, Path | None]]:
        """Renders PPTX slides into native high-res 16:9 PNGs using PowerPoint COM automation on Windows."""
        width = int(1920 * (dpi / 96))
        height = int(1080 * (dpi / 96))
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_pptx = Path(temp_dir) / "temp_deck.pptx"
            temp_pptx.write_bytes(pptx_bytes)
            render_dir = output_dir if output_dir else Path(temp_dir) / "slides"
            render_dir.mkdir(parents=True, exist_ok=True)

            ps_script = f'''
$pptx = "{temp_pptx.resolve()}"
$outDir = "{render_dir.resolve()}"
$ppt = New-Object -ComObject PowerPoint.Application
try {{
    $pres = $ppt.Presentations.Open($pptx, [Microsoft.Office.Core.MsoTriState]::msoTrue, [Microsoft.Office.Core.MsoTriState]::msoFalse, [Microsoft.Office.Core.MsoTriState]::msoFalse)
    $count = $pres.Slides.Count
    for ($i = 1; $i -le $count; $i++) {{
        $slide = $pres.Slides.Item($i)
        $idxStr = $i.ToString("D2")
        $outPng = Join-Path $outDir ("slide_" + $idxStr + ".png")
        $slide.Export($outPng, "PNG", {width}, {height})
    }}
    $pres.Close()
    Write-Host "RENDER_COM_OK"
}} catch {{
    Write-Host "RENDER_COM_ERR: $($_.Exception.Message)"
}} finally {{
    $ppt.Quit()
    [System.GC]::Collect()
}}
'''
            res = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_script],
                capture_output=True,
                text=True,
                timeout=45,
            )
            if "RENDER_COM_OK" in res.stdout:
                results: list[tuple[int, bytes, Path | None]] = []
                for p in sorted(render_dir.glob("slide_*.png")):
                    try:
                        idx = int(p.stem.split("_")[-1])
                        b = p.read_bytes()
                        fp = p if output_dir else None
                        results.append((idx, b, fp))
                    except Exception:
                        continue
                if results:
                    return results
        return []

    @classmethod
    def _render_via_libreoffice(
        cls,
        pptx_bytes: bytes,
        output_dir: Path | None,
        dpi: int = 150,
    ) -> list[tuple[int, bytes, Path | None]]:
        """Renders PPTX slides into PNGs by converting to PDF via headless LibreOffice on Linux."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_pptx = Path(temp_dir) / "deck.pptx"
            temp_pptx.write_bytes(pptx_bytes)
            subprocess.run(
                ["soffice", "--headless", "--convert-to", "pdf", str(temp_pptx), "--outdir", temp_dir],
                capture_output=True,
                timeout=60,
            )
            pdf_path = Path(temp_dir) / "deck.pdf"
            if not pdf_path.exists():
                return []
            doc = pymupdf.open(str(pdf_path))
            results: list[tuple[int, bytes, Path | None]] = []
            for idx, page in enumerate(doc, 1):
                pix = page.get_pixmap(dpi=dpi)
                png_bytes = pix.tobytes("png")
                fp: Path | None = None
                if output_dir:
                    fp = output_dir / f"slide_{idx:02d}.png"
                    fp.write_bytes(png_bytes)
                results.append((idx, png_bytes, fp))
            return results

    @classmethod
    def render_slide_previews(
        cls,
        pptx_bytes: bytes,
        output_dir: str | Path | None = None,
        dpi: int = 150,
    ) -> list[tuple[int, bytes, Path | None]]:
        """Renders every slide in a PPTX stream into high-res PNG bytes and optionally saves to disk."""
        results: list[tuple[int, bytes, Path | None]] = []
        if not pptx_bytes:
            return results

        out_path: Path | None = Path(output_dir) if output_dir else None
        if out_path:
            out_path.mkdir(parents=True, exist_ok=True)

        # 1. Native Windows COM rendering (PowerPoint installed)
        if sys.platform == "win32":
            try:
                native_results = cls._render_via_com(pptx_bytes, out_path, dpi=dpi)
                if native_results:
                    return native_results
            except Exception as com_err:
                logger.debug("PowerPoint COM rendering unavailable: %s", com_err)

        # 2. Linux headless LibreOffice rendering (if soffice installed)
        if sys.platform != "win32" and shutil.which("soffice"):
            try:
                lo_results = cls._render_via_libreoffice(pptx_bytes, out_path, dpi=dpi)
                if lo_results:
                    return lo_results
            except Exception as lo_err:
                logger.debug("LibreOffice rendering unavailable: %s", lo_err)

        # 3. Direct PyMuPDF fallback
        try:
            doc = pymupdf.open(stream=pptx_bytes, filetype="pptx")
            for idx, page in enumerate(doc, 1):
                try:
                    pix = page.get_pixmap(dpi=dpi)
                    png_bytes = pix.tobytes("png")
                    file_path: Path | None = None
                    if out_path:
                        file_path = out_path / f"slide_{idx:02d}.png"
                        file_path.write_bytes(png_bytes)
                    results.append((idx, png_bytes, file_path))
                except Exception as slide_err:
                    logger.warning("Failed to render slide %d preview: %s", idx, slide_err)
        except Exception as e:
            logger.warning("Could not open PPTX for visual rendering: %s", e)

        return results

    @classmethod
    def inspect_rendered_slide(
        cls,
        slide_number: int,
        png_bytes: bytes,
        spec: SlideSpec | None = None,
    ) -> list[ValidationIssue]:
        """Inspects a rendered slide PNG for visual balance, density, contrast, and layout health."""
        issues: list[ValidationIssue] = []
        if not png_bytes:
            return issues

        sid = spec.slide_id if spec else f"s{slide_number:02d}"

        try:
            pil_img = Image.open(io.BytesIO(png_bytes)).convert("RGB")
            w, h = pil_img.size
            if w <= 0 or h <= 0:
                return issues

            arr = np.array(pil_img, dtype=np.uint8)

            # 1. Overall Image Variance (detect completely blank slides)
            variance = float(np.var(arr))
            if variance < 2.0:
                issues.append(
                    ValidationIssue(
                        checkpoint_id=CHECKPOINT_ID_BY_SLUG.get("excessive_blank_space", "QA-049"),
                        severity=ValidationSeverity.CRITICAL,
                        category=ValidationCategory.GEOMETRY,
                        slide_number=slide_number,
                        slide_id=sid,
                        message=f"Slide {slide_number} is visually completely blank (variance={variance:.1f})",
                        suggested_fix="Ensure slide elements and content are populated and rendered onto the canvas",
                        auto_fixable=True,
                        repair_action="restore_title",
                    )
                )
                return issues

            # 2. Quadrant Density Analysis
            # Compare non-background pixels across quadrants (Top-Left, Top-Right, Bottom-Left, Bottom-Right)
            # Find dominant background color by sampling inset margin points
            iy = max(5, int(h * 0.05))
            ix = max(5, int(w * 0.08))
            sample_points = np.array([
                arr[iy, ix], arr[iy, -ix], arr[-iy, ix], arr[-iy, -ix],
                arr[h // 2, -ix], arr[iy, w // 2], arr[-iy, w // 2],
            ])
            bg_color = np.median(sample_points, axis=0)

            # Mask pixels that differ meaningfully from the background color
            diff = np.abs(arr.astype(np.int16) - bg_color.astype(np.int16))
            content_mask = np.any(diff > 25, axis=-1)

            half_h, half_w = h // 2, w // 2
            tl = float(np.mean(content_mask[:half_h, :half_w]))
            tr = float(np.mean(content_mask[:half_h, half_w:]))
            bl = float(np.mean(content_mask[half_h:, :half_w]))
            br = float(np.mean(content_mask[half_h:, half_w:]))

            left_density = tl + bl
            right_density = tr + br
            total_content_density = float(np.mean(content_mask))

            is_sparse_allowed = spec and spec.layout_family in _SPARSE_ALLOWED_LAYOUTS

            if not is_sparse_allowed:
                # Check for extreme left/right imbalance
                if left_density > 0.08 and right_density < 0.005:
                    issues.append(
                        ValidationIssue(
                            checkpoint_id=CHECKPOINT_ID_BY_SLUG.get("blank_right_half", "QA-051"),
                            severity=ValidationSeverity.MEDIUM,
                            category=ValidationCategory.DESIGN,
                            slide_number=slide_number,
                            slide_id=sid,
                            message=f"Right half of Slide {slide_number} has no rendered visual or text content",
                            suggested_fix="Distribute content across columns or pair text with a supporting graphic",
                            auto_fixable=True,
                            repair_action="vary_structure",
                        )
                    )
                elif right_density > 0.08 and left_density < 0.005:
                    issues.append(
                        ValidationIssue(
                            checkpoint_id=CHECKPOINT_ID_BY_SLUG.get("blank_left_half", "QA-050"),
                            severity=ValidationSeverity.MEDIUM,
                            category=ValidationCategory.DESIGN,
                            slide_number=slide_number,
                            slide_id=sid,
                            message=f"Left half of Slide {slide_number} has no rendered visual or text content",
                            suggested_fix="Balance layout by aligning introductory cards and headlines properly",
                            auto_fixable=True,
                            repair_action="vary_structure",
                        )
                    )

                # Check for severely sparse content on standard slides
                if total_content_density < 0.015:
                    issues.append(
                        ValidationIssue(
                            checkpoint_id=CHECKPOINT_ID_BY_SLUG.get("excessive_blank_space", "QA-049"),
                            severity=ValidationSeverity.MEDIUM,
                            category=ValidationCategory.DESIGN,
                            slide_number=slide_number,
                            slide_id=sid,
                            message=f"Slide {slide_number} has sparse content coverage ({total_content_density:.1%})",
                            suggested_fix="Enrich slide with key takeaways, metric callouts, or structured bullet cards",
                            auto_fixable=True,
                            repair_action="vary_structure",
                        )
                    )

            # 3. Text & Background Contrast Check
            # Grayscale luminance: Y = 0.299 R + 0.587 G + 0.114 B
            bg_lum = (0.299 * bg_color[0] + 0.587 * bg_color[1] + 0.114 * bg_color[2]) / 255.0
            if content_mask.any():
                content_pixels = arr[content_mask]
                fg_lum = np.mean(
                    0.299 * content_pixels[:, 0] + 0.587 * content_pixels[:, 1] + 0.114 * content_pixels[:, 2]
                ) / 255.0
                contrast_ratio = (max(bg_lum, fg_lum) + 0.05) / (min(bg_lum, fg_lum) + 0.05)
                if contrast_ratio < 2.0:
                    issues.append(
                        ValidationIssue(
                            checkpoint_id=CHECKPOINT_ID_BY_SLUG.get("theme_inconsistency", "QA-084"),
                            severity=ValidationSeverity.MEDIUM,
                            category=ValidationCategory.DESIGN,
                            slide_number=slide_number,
                            slide_id=sid,
                            message=f"Slide {slide_number} content has poor visual contrast against background (ratio={contrast_ratio:.1f}:1)",
                            suggested_fix="Increase color contrast between typography runs and slide surface",
                            auto_fixable=True,
                            repair_action="normalize_palette",
                        )
                    )

        except Exception as inspect_err:
            logger.debug("Visual inspection error on slide %d: %s", slide_number, inspect_err)

        return issues

    @classmethod
    def inspect_presentation_visually(
        cls,
        pptx_bytes: bytes,
        specs: list[SlideSpec],
        output_dir: str | Path | None = None,
    ) -> tuple[list[tuple[int, bytes, Path | None]], list[ValidationIssue]]:
        """Renders all slides to PNG and conducts visual inspection across the entire deck."""
        rendered = cls.render_slide_previews(pptx_bytes, output_dir=output_dir)
        spec_map = {s.slide_number: s for s in specs}
        all_issues: list[ValidationIssue] = []

        for slide_num, png_bytes, _path in rendered:
            spec = spec_map.get(slide_num)
            slide_issues = cls.inspect_rendered_slide(slide_num, png_bytes, spec=spec)
            all_issues.extend(slide_issues)

        return rendered, all_issues
