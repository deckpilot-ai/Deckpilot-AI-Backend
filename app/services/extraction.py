import csv
import hashlib
import io
import logging
import re
from pathlib import Path
from typing import Any

import openpyxl
import pymupdf
from docx import Document
from PIL import Image
from pptx import Presentation

logger = logging.getLogger(__name__)


class ExtractionResult:
    def __init__(self) -> None:
        self.text_blocks: list[dict[str, Any]] = []
        self.tables: list[dict[str, Any]] = []
        self.extracted_images: list[dict[str, Any]] = []
        self.image_payloads: list[tuple[str, bytes, str]] = []
        self.metadata: dict[str, Any] = {}


class DocumentExtractor:
    @staticmethod
    def extract_pdf(file_bytes: bytes, filename: str, on_progress: Any = None) -> ExtractionResult:
        result = ExtractionResult()
        doc = pymupdf.open(stream=file_bytes, filetype="pdf")
        total_pages = len(doc)
        metadata = doc.metadata or {}
        result.metadata["page_count"] = total_pages
        result.metadata["title"] = metadata.get("title", "")
        result.metadata["author"] = metadata.get("author", "")

        if on_progress:
            on_progress(f"Analyzing {filename}: opened {total_pages} pages...")

        from app.services.image_quality import is_documentary_pixmap

        # Pre-scan: detect repeating template graphics / watermarks across >= 3 pages
        xref_page_counts: dict[int, int] = {}
        if total_pages >= 3:
            for p_idx in range(total_pages):
                p = doc[p_idx]
                seen_xrefs = set()
                for img_info in p.get_images(full=True):
                    x = img_info[0]
                    if x not in seen_xrefs:
                        seen_xrefs.add(x)
                        xref_page_counts[x] = xref_page_counts.get(x, 0) + 1

        extracted_candidates: list[dict[str, Any]] = []

        for page_idx in range(total_pages):
            import time
            time.sleep(0.005)  # Yield GIL to keep event loop responsive
            if on_progress and (page_idx % 3 == 0 or page_idx == total_pages - 1):
                on_progress(f"Analyzing {filename}: scanned {page_idx + 1} of {total_pages} pages ({len(extracted_candidates)} visual figures found)...")

            page = doc[page_idx]
            page_text = page.get_text("text").strip()
            if page_text:
                result.text_blocks.append({
                    "page": page_idx + 1,
                    "content": page_text,
                    "source": f"{filename}#page={page_idx + 1}",
                })

            # Extract embedded figures & images
            image_list = page.get_images(full=True)
            visible = {item['xref']: pymupdf.Rect(item['bbox']) for item in page.get_image_info(xrefs=True)}
            page_figures: list[dict[str, Any]] = []

            for img_idx, img_info in enumerate(image_list):
                xref = img_info[0]
                # Skip template graphics/watermarks that repeat across 3+ pages
                if xref_page_counts.get(xref, 0) >= 3:
                    continue

                rect = visible.get(xref)
                if rect is None:
                    continue

                # Skip full-page background scans / page covers (> 88% of page area)
                if rect.width * rect.height > page.rect.width * page.rect.height * 0.88:
                    continue

                # Skip tiny decorative icons, border lines, and slivers
                if rect.width < 45 or rect.height < 45:
                    continue

                # Search nearby text for captions / figure labels
                rects = page.get_image_rects(xref)
                caption = ""
                if rects:
                    r = rects[0]
                    candidates = []
                    for b in page.get_text("blocks"):
                        if len(b) > 4:
                            b_text = str(b[4]).strip()
                            if not b_text:
                                continue
                            if b[0] < r.x1 + 40 and b[2] > r.x0 - 40:
                                dist_below = b[1] - r.y1
                                dist_above = r.y0 - b[3]
                                is_fig = bool(re.search(r'\b(?:fig(?:ure)?\.?|map|photo(?:graph)?|chart|diagram|plate)\s*[\d\.]', b_text, re.IGNORECASE))
                                is_inside_top = (r.y0 - 20 <= b[1] <= r.y0 + 70)
                                is_inside_bottom = (r.y1 - 70 <= b[3] <= r.y1 + 20)
                                if is_fig and (is_inside_top or is_inside_bottom or -30 <= dist_below < 120 or -30 <= dist_above < 100):
                                    candidates.append((0, min(abs(b[1] - r.y0), abs(b[3] - r.y1)), b_text))
                                elif -15 <= dist_below < 120:
                                    candidates.append((1, abs(dist_below), b_text))
                                elif -15 <= dist_above < 90:
                                    candidates.append((1, abs(dist_above), b_text))
                    if candidates:
                        candidates.sort(key=lambda c: (c[0], c[1]))
                        raw_caption = " ".join(candidates[0][2].split())[:350]
                        # Clean control characters
                        caption = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', raw_caption).strip()

                fig_match = re.search(r'\b(?:fig(?:ure)?\.?|map|photo|chart|diagram|plate)\s*([\d\.]+)', caption, re.I)
                fig_label = fig_match.group(0).lower() if fig_match else ""
                has_explicit_caption = 1 if fig_label or bool(re.search(r'\b(?:fig(?:ure)?\.?|map|photo|chart|diagram|plate)\b', caption, re.I)) else 0
                area = rect.width * rect.height

                candidate = {
                    "xref": xref,
                    "img_info": img_info,
                    "page": page_idx + 1,
                    "img_idx": img_idx,
                    "caption": caption,
                    "fig_label": fig_label,
                    "rect": (rect.x0, rect.y0, rect.x1, rect.y1),
                    "priority": (has_explicit_caption, 1 if caption else 0, area),
                }

                # Same-page deduplication: check if this figure overlaps or has same fig_label as another figure on this page
                duplicate = False
                for existing in page_figures:
                    if fig_label and existing.get("fig_label") == fig_label:
                        if area > (existing["rect"][2] - existing["rect"][0]) * (existing["rect"][3] - existing["rect"][1]):
                            page_figures.remove(existing)
                            page_figures.append(candidate)
                        duplicate = True
                        break
                    ex_r = existing["rect"]
                    ix0 = max(rect.x0, ex_r[0])
                    iy0 = max(rect.y0, ex_r[1])
                    ix1 = min(rect.x1, ex_r[2])
                    iy1 = min(rect.y1, ex_r[3])
                    if ix1 > ix0 and iy1 > iy0:
                        inter_area = (ix1 - ix0) * (iy1 - iy0)
                        smaller_area = min(rect.width * rect.height, (ex_r[2] - ex_r[0]) * (ex_r[3] - ex_r[1]))
                        if smaller_area > 0 and (inter_area / smaller_area) > 0.65:
                            if candidate["priority"] > existing["priority"]:
                                page_figures.remove(existing)
                                page_figures.append(candidate)
                            duplicate = True
                            break

                if not duplicate:
                    page_figures.append(candidate)

            extracted_candidates.extend(page_figures)

        # Cap to top 10 most relevant illustrative figures per document
        if len(extracted_candidates) > 10:
            extracted_candidates.sort(key=lambda c: c["priority"], reverse=True)
            extracted_candidates = extracted_candidates[:10]

        # Extract image bytes and payloads for the top candidates
        if on_progress:
            on_progress(f"Finalizing {len(extracted_candidates)} high-res figures from {filename}...")

        for cand in extracted_candidates:
            xref = cand["xref"]
            try:
                pix = pymupdf.Pixmap(doc, xref)
                if pix.colorspace and pix.colorspace.n != 3:
                    pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
                if not is_documentary_pixmap(pix):
                    continue

                mask_xref = cand["img_info"][1] if len(cand.get("img_info", [])) > 1 else 0
                if mask_xref:
                    try:
                        mask = pymupdf.Pixmap(doc, mask_xref)
                        if (mask.width, mask.height) == (pix.width, pix.height):
                            if pix.alpha:
                                pix = pymupdf.Pixmap(pix, 0)
                            pix = pymupdf.Pixmap(pix, mask)
                    except Exception:
                        pass

                ext = "png" if pix.alpha else "jpg"
                image_bytes = pix.tobytes("png") if pix.alpha else pix.tobytes("jpg", jpg_quality=92)
                storage_key = f"extracted/{Path(filename).stem}_p{cand['page']}_img{cand['img_idx']}.{ext}"

                result.image_payloads.append((storage_key, image_bytes, f"image/{ext}"))
                result.extracted_images.append({
                    "storage_key": storage_key,
                    "width": pix.width,
                    "height": pix.height,
                    "format": ext,
                    "page": cand["page"],
                    "byte_size": len(image_bytes),
                    "caption": cand["caption"],
                })
            except Exception:
                logger.warning("Skipping image xref %s on page %s", xref, cand["page"], exc_info=True)

        return result

    @staticmethod
    def extract_docx(file_bytes: bytes, filename: str) -> ExtractionResult:
        """Extracts text paragraphs, tables, and embedded images from Word (.docx) files."""
        result = ExtractionResult()
        doc = Document(io.BytesIO(file_bytes))

        full_text = []
        for p in doc.paragraphs:
            text = p.text.strip()
            if text:
                # Retain heading indicators
                if p.style and "Heading" in p.style.name:
                    full_text.append(f"### {text}")
                else:
                    full_text.append(text)

        if full_text:
            result.text_blocks.append({
                "content": "\n\n".join(full_text),
                "source": filename,
            })

        # Extract structured tables
        for table_idx, table in enumerate(doc.tables):
            rows = []
            for row in table.rows:
                rows.append([cell.text.strip() for cell in row.cells])
            if rows:
                result.tables.append({
                    "table_index": table_idx + 1,
                    "rows": rows,
                    "source": f"{filename}#table={table_idx + 1}",
                })

                # Also format table as markdown for seamless grounding by text LLMs
                if len(rows) > 0:
                    md_table_lines = []
                    header = " | ".join(rows[0])
                    sep = " | ".join(["---"] * len(rows[0]))
                    md_table_lines.append(f"| {header} |")
                    md_table_lines.append(f"| {sep} |")
                    for r in rows[1:]:
                        md_table_lines.append(f"| {' | '.join(r)} |")
                    result.text_blocks.append({
                        "content": f"### Document Table {table_idx + 1}:\n" + "\n".join(md_table_lines),
                        "source": f"{filename}#table={table_idx + 1}",
                    })

        # Extract embedded images from docx
        try:
            for rel_id, part in doc.part.related_parts.items():
                if "image" in part.content_type:
                    img_bytes = part.blob
                    ext = part.content_type.split("/")[-1]
                    storage_key = f"extracted/{Path(filename).stem}_{rel_id}.{ext}"
                    result.image_payloads.append((storage_key, img_bytes, part.content_type))
                    result.extracted_images.append({
                        "storage_key": storage_key,
                        "format": ext,
                        "byte_size": len(img_bytes),
                        "source": f"{filename}#{rel_id}",
                    })
        except Exception:
            logger.warning("Unable to extract optional embedded media from %s", filename, exc_info=True)

        return result

    @staticmethod
    def extract_image(file_bytes: bytes, filename: str, mime_type: str = "image/jpeg") -> ExtractionResult:
        """Parses image files (JPG, PNG, WEBP, GIF, BMP), stores asset, and produces visual metadata."""
        result = ExtractionResult()
        sha256 = hashlib.sha256(file_bytes).hexdigest()
        ext = Path(filename).suffix.lstrip(".").lower() or "jpg"
        if ext == "jpeg":
            ext = "jpg"

        width, height = 800, 600
        img_format = ext
        color_mode = "RGB"

        try:
            with Image.open(io.BytesIO(file_bytes)) as img:
                from PIL import ImageOps
                normalized = ImageOps.exif_transpose(img).convert('RGBA' if 'A' in img.getbands() else 'RGB')
                normalized.thumbnail((4096, 4096))
                width, height = normalized.size
                img_format = 'png'
                color_mode = normalized.mode
                buffer = io.BytesIO()
                normalized.save(buffer, format='PNG')
                file_bytes = buffer.getvalue()
        except Exception as exc:
            raise ValueError(f"Unable to decode image {filename}") from exc

        aspect_ratio = round(width / max(1, height), 2)
        storage_key = f"extracted/images/{sha256[:16]}_{Path(filename).stem}.png"
        result.image_payloads.append((storage_key, file_bytes, f"image/{img_format}"))

        result.metadata["width"] = width
        result.metadata["height"] = height
        result.metadata["format"] = img_format
        result.metadata["aspect_ratio"] = aspect_ratio
        result.metadata["byte_size"] = len(file_bytes)

        # 1. Register image artifact for presentation renderer
        result.extracted_images.append({
            "storage_key": storage_key,
            "width": width,
            "height": height,
            "format": img_format,
            "byte_size": len(file_bytes),
            "color_mode": color_mode,
            "aspect_ratio": aspect_ratio,
            "source": filename,
        })

        # 2. Register structured semantic text block so planner agents understand the visual asset
        orientation = "landscape (16:9 compatible)" if width > height else ("portrait" if height > width else "square")
        result.text_blocks.append({
            "content": (
                f"### Attached Visual Document / Image: {filename}\n"
                f"- **Format**: {img_format.upper()} ({color_mode})\n"
                f"- **Dimensions**: {width}x{height}px ({orientation}, aspect ratio {aspect_ratio}:1)\n"
                f"- **File Size**: {round(len(file_bytes) / 1024, 1)} KB\n"
                f"- **Storage Key**: `{storage_key}`\n"
                f"- **Presentation Layout Role**: Can be featured on Hero, Two-Column Architecture, or Product Highlight slides."
            ),
            "source": filename,
        })

        return result

    @staticmethod
    def extract_spreadsheet(file_bytes: bytes, filename: str) -> ExtractionResult:
        """Extracts structured tables and data rows from Excel (.xlsx, .xlsm, .xls) workbooks."""
        result = ExtractionResult()
        wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)
        result.metadata["sheet_names"] = wb.sheetnames

        for sheet_name in wb.sheetnames:
            sheet = wb[sheet_name]
            rows = []
            for row in sheet.iter_rows(values_only=True):
                if any(cell is not None for cell in row):
                    rows.append([str(c).strip() if c is not None else "" for c in row])

            if rows:
                result.tables.append({
                    "sheet": sheet_name,
                    "rows": rows[:100],  # cap to first 100 rows for presentation brevity
                    "source": f"{filename}#{sheet_name}",
                })

                # Create markdown table for LLM reasoning
                md_lines = [f"### Spreadsheet Sheet: {sheet_name}"]
                if len(rows) > 0:
                    header = " | ".join(rows[0])
                    sep = " | ".join(["---"] * len(rows[0]))
                    md_lines.append(f"| {header} |")
                    md_lines.append(f"| {sep} |")
                    for r in rows[1:50]:  # first 50 rows in text summary
                        md_lines.append(f"| {' | '.join(r)} |")
                result.text_blocks.append({
                    "content": "\n".join(md_lines),
                    "source": f"{filename}#{sheet_name}",
                })

        return result

    @staticmethod
    def extract_csv(file_bytes: bytes, filename: str) -> ExtractionResult:
        """Extracts structured tables and markdown rows from CSV/TSV files."""
        result = ExtractionResult()
        try:
            text = file_bytes.decode("utf-8")
        except UnicodeDecodeError:
            text = file_bytes.decode("latin-1", errors="ignore")

        delimiter = "\t" if filename.endswith(".tsv") else ","
        reader = csv.reader(io.StringIO(text), delimiter=delimiter)
        rows = [row for row in reader if any(cell.strip() for cell in row)]

        if rows:
            result.tables.append({
                "rows": rows[:100],
                "source": filename,
            })
            md_lines = [f"### Tabular CSV Data: {filename}"]
            header = " | ".join(rows[0])
            sep = " | ".join(["---"] * len(rows[0]))
            md_lines.append(f"| {header} |")
            md_lines.append(f"| {sep} |")
            for r in rows[1:50]:
                md_lines.append(f"| {' | '.join(r)} |")
            result.text_blocks.append({
                "content": "\n".join(md_lines),
                "source": filename,
            })
        return result

    @staticmethod
    def extract_pptx(file_bytes: bytes, filename: str) -> ExtractionResult:
        result = ExtractionResult()
        prs = Presentation(io.BytesIO(file_bytes))
        result.metadata["slide_count"] = len(prs.slides)
        result.metadata["slide_width"] = prs.slide_width
        result.metadata["slide_height"] = prs.slide_height

        for slide_idx, slide in enumerate(prs.slides):
            slide_texts = []
            for shape in slide.shapes:
                if shape.has_text_frame and shape.text.strip():
                    slide_texts.append(shape.text.strip())

            if slide_texts:
                result.text_blocks.append({
                    "slide": slide_idx + 1,
                    "content": "\n".join(slide_texts),
                    "source": f"{filename}#slide={slide_idx + 1}",
                })

        return result

    @staticmethod
    def extract_text(file_bytes: bytes, filename: str) -> ExtractionResult:
        result = ExtractionResult()
        try:
            content = file_bytes.decode("utf-8")
        except UnicodeDecodeError:
            content = file_bytes.decode("latin-1", errors="ignore")

        if content.strip():
            result.text_blocks.append({
                "content": content.strip(),
                "source": filename,
            })
        return result

    @classmethod
    def extract_document(cls, file_bytes: bytes, filename: str, mime_type: str = "", on_progress: Any = None) -> ExtractionResult:
        """Universal document extractor supporting PDF, DOCX/Word, XLSX/Excel, CSV, Images (JPG, PNG, WEBP), and PPTX."""
        ext = Path(filename).suffix.lower()
        # 1. Images (JPG, JPEG, PNG, WEBP, GIF, BMP, TIFF)
        if ext in [".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tiff"]:
            if on_progress:
                on_progress(f"Processing image asset: {filename}...")
            return cls.extract_image(file_bytes, filename, mime_type)

        # 2. PDF Documents
        elif ext == ".pdf":
            return cls.extract_pdf(file_bytes, filename, on_progress=on_progress)

        # 3. Microsoft Word (.docx, .doc)
        elif ext == ".docx":
            if on_progress:
                on_progress(f"Extracting Word document: {filename}...")
            return cls.extract_docx(file_bytes, filename)

        # 4. Microsoft Excel / Spreadsheets (.xlsx, .xlsm, .xls)
        elif ext in [".xlsx", ".xlsm"]:
            if on_progress:
                on_progress(f"Extracting spreadsheet: {filename}...")
            return cls.extract_spreadsheet(file_bytes, filename)

        # 5. CSV Tabular Data
        elif ext in [".csv", ".tsv"]:
            if on_progress:
                on_progress(f"Extracting tabular data: {filename}...")
            return cls.extract_csv(file_bytes, filename)

        # 6. PowerPoint Presentations (.pptx)
        elif ext == ".pptx":
            if on_progress:
                on_progress(f"Extracting presentation slides: {filename}...")
            return cls.extract_pptx(file_bytes, filename)

        # 7. Plain text / Markdown / Structured text
        elif ext in [".txt", ".md", ".json", ".yaml", ".yml", ".xml"]:
            if on_progress:
                on_progress(f"Reading reference text: {filename}...")
            return cls.extract_text(file_bytes, filename)

        # Fallback
        else:
            raise ValueError(f"Unsupported file type: {ext or '(none)'}")
