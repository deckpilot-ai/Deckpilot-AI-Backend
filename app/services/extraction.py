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
        self.sections: list[dict[str, Any]] = []
        self.semantic_chunks: list[dict[str, Any]] = []


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

        from app.services.image_quality import is_documentary_pixmap, classify_image_type

        # 1. Pre-scan for repeating template graphics / watermarks and running headers/footers across >= 3 pages
        xref_page_counts: dict[int, int] = {}
        text_counts: dict[str, int] = {}
        if total_pages >= 3:
            for p_idx in range(total_pages):
                p = doc[p_idx]
                seen_xrefs = set()
                for img_info in p.get_images(full=True):
                    x = img_info[0]
                    if x not in seen_xrefs:
                        seen_xrefs.add(x)
                        xref_page_counts[x] = xref_page_counts.get(x, 0) + 1
                for b in p.get_text("blocks"):
                    if b[6] == 0:
                        t = b[4].strip()
                        if 4 < len(t) < 80:
                            text_counts[t] = text_counts.get(t, 0) + 1

        repeating_texts = {t for t, c in text_counts.items() if c >= 3}

        extracted_candidates: list[dict[str, Any]] = []
        current_chapter = ""
        current_section = "Introduction & Overview"
        doc_sections_map: dict[str, list[int]] = {}

        for page_idx in range(total_pages):
            import time
            time.sleep(0.001)  # Yield GIL to keep event loop responsive
            if on_progress and (page_idx % 4 == 0 or page_idx == total_pages - 1):
                on_progress(f"Analyzing {filename}: scanned {page_idx + 1} of {total_pages} pages ({len(extracted_candidates)} visual figures found)...")

            page = doc[page_idx]
            rect = page.rect
            blocks = page.get_text("blocks")

            # --- Multi-Column & Margin-Aware Text Cleaning ---
            clean_blocks = []
            for b in blocks:
                if b[6] != 0:
                    continue
                text = b[4].strip()
                if not text:
                    continue
                # Skip repeating header/footer text
                if text in repeating_texts:
                    continue
                # Skip top header margin (< 42pt from top unless multi-line title)
                if b[1] < 42 and len(text) < 100:
                    continue
                # Skip bottom footer margin (< 35pt from bottom)
                if b[3] > rect.height - 35:
                    continue
                # Skip outer margin running title labels
                if (b[0] > rect.width - 45 or b[2] < 45) and len(text) < 80:
                    continue
                # Skip standalone page numbers
                if re.match(r"^\d{1,4}$", text):
                    continue
                clean_blocks.append(b)

            # Sort blocks by multi-column layout if 2 distinct columns exist
            mid_x = rect.width / 2
            col1 = [b for b in clean_blocks if b[2] <= mid_x + 35]
            col2 = [b for b in clean_blocks if b[0] >= mid_x - 35]
            is_multi_column = len(col1) >= 2 and len(col2) >= 2 and (len(col1) + len(col2)) >= len(clean_blocks) * 0.75

            if is_multi_column:
                col1.sort(key=lambda b: b[1])
                col2.sort(key=lambda b: b[1])
                sorted_blocks = col1 + col2
            else:
                sorted_blocks = sorted(clean_blocks, key=lambda b: (b[1], b[0]))

            # Format page text and preserve headings / callouts
            formatted_lines: list[str] = []
            page_headings: list[str] = []

            for b in sorted_blocks:
                t = b[4].strip()
                # Check for explicit figure captions first
                if re.match(r"^(?:Fig(?:ure)?\.?|Map|Photo(?:graph)?|Plate|Chart|Diagram)\s*[\d\.]", t, re.IGNORECASE):
                    formatted_lines.append(f"*Caption: {t}*")
                # Check for chapter title
                elif re.match(r"^(?:CHAPTER\s*\d+|UNIT\s*\d+)", t, re.IGNORECASE) or (b[1] < 120 and len(t) < 70 and ("Chapter" in t or "The Parliamentary System" in t)):
                    current_chapter = t
                    page_headings.append(t)
                    formatted_lines.append(f"# {t}")
                    if current_chapter not in doc_sections_map:
                        doc_sections_map[current_chapter] = []
                    doc_sections_map[current_chapter].append(page_idx + 1)
                # Check for section heading
                elif len(t) < 80 and not t.endswith(".") and (t.isupper() or t.istitle() or b[1] < 100):
                    current_section = t
                    page_headings.append(t)
                    formatted_lines.append(f"## {t}")
                    if current_section not in doc_sections_map:
                        doc_sections_map[current_section] = []
                    doc_sections_map[current_section].append(page_idx + 1)
                # Check for callout boxes
                elif re.match(r"^(?:DON'T MISS OUT|LET'S REMEMBER|ACTIVITY|SOURCE\s+[A-Z]|EXERCISE|IMPORTANT|NOTE)", t, re.IGNORECASE):
                    formatted_lines.append(f"> **{t}**")
                else:
                    formatted_lines.append(t)

            page_content = "\n\n".join(formatted_lines).strip()
            if page_content:
                result.text_blocks.append({
                    "page": page_idx + 1,
                    "chapter": current_chapter,
                    "section": current_section,
                    "content": page_content,
                    "headings": page_headings,
                    "source": f"{filename}#page={page_idx + 1}",
                })

            # Check for native tables
            try:
                page_tables = page.find_tables().tables
                for tbl_idx, tbl in enumerate(page_tables):
                    extracted_data = tbl.extract()
                    if extracted_data and len(extracted_data) >= 2 and len(extracted_data[0]) >= 2:
                        # Clean cells
                        cleaned_rows = [
                            [str(c or "").replace("\n", " ").strip() for c in row]
                            for row in extracted_data
                            if any(c for c in row)
                        ]
                        if len(cleaned_rows) >= 2:
                            result.tables.append({
                                "page": page_idx + 1,
                                "section": current_section,
                                "headers": cleaned_rows[0],
                                "rows": cleaned_rows[1:],
                                "source": f"{filename}#page={page_idx + 1}#table={tbl_idx + 1}",
                            })
            except Exception:
                pass

            # --- Image & Visual Extraction ---
            image_list = page.get_images(full=True)
            if not image_list:
                continue

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
                if rect.width < 40 or rect.height < 40 or (rect.width * rect.height) < 3500:
                    continue

                # Search surrounding blocks for captions with multi-line merging
                caption_blocks: list[tuple[int, float, str]] = []
                nearby_paragraphs: list[str] = []

                for b in clean_blocks:
                    b_text = b[4].strip()
                    if not b_text:
                        continue
                    # Check horizontal overlap with image bbox
                    h_overlap = max(0.0, min(rect.x1 + 35, b[2]) - max(rect.x0 - 35, b[0]))
                    if h_overlap > 20:
                        dist_below = b[1] - rect.y1
                        dist_above = rect.y0 - b[3]
                        is_fig = bool(re.search(r'\b(?:fig(?:ure)?\.?|map|photo(?:graph)?|chart|diagram|plate|source)\b', b_text, re.IGNORECASE))
                        if is_fig and (-20 <= dist_below < 100 or -20 <= dist_above < 80):
                            caption_blocks.append((0, abs(dist_below), b_text))
                        elif 0 <= dist_below < 80:
                            caption_blocks.append((1, dist_below, b_text))
                        elif 0 <= dist_above < 60:
                            caption_blocks.append((2, dist_above, b_text))
                    # Nearby text collection
                    if abs(b[1] - rect.y0) < 180 or abs(b[3] - rect.y1) < 180:
                        nearby_paragraphs.append(b_text[:200])

                caption_blocks.sort(key=lambda c: (c[0], c[1]))
                # Merge up to 2 adjacent caption lines if available
                if caption_blocks:
                    caption_lines = [caption_blocks[0][2]]
                    if len(caption_blocks) > 1 and caption_blocks[1][0] == caption_blocks[0][0]:
                        caption_lines.append(caption_blocks[1][2])
                    raw_caption = " ".join(" ".join(caption_lines).split())[:350]
                    caption = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', raw_caption).strip()
                else:
                    caption = ""

                fig_match = re.search(r'\b(?:fig(?:ure)?\.?|map|photo|chart|diagram|plate)\s*([\d\.]+)', caption, re.IGNORECASE)
                fig_label = fig_match.group(0).lower() if fig_match else ""
                has_explicit_caption = 1 if fig_label or bool(re.search(r'\b(?:fig(?:ure)?\.?|map|photo|chart|diagram|plate)\b', caption, re.IGNORECASE)) else 0
                area = rect.width * rect.height

                # Determine image type and aspect ratio
                aspect = round(rect.width / max(1, rect.height), 3)
                img_type = classify_image_type(caption, " ".join(nearby_paragraphs[:2]), aspect)

                # Extract semantic tags
                semantic_tags = [
                    w.lower() for w in re.findall(r"[A-Za-z]{4,}", f"{caption} {current_section}")
                    if w.lower() not in {"this", "that", "with", "from", "were", "been", "have", "figure", "photo", "image"}
                ][:8]

                candidate = {
                    "xref": xref,
                    "img_info": img_info,
                    "page": page_idx + 1,
                    "img_idx": img_idx,
                    "caption": caption,
                    "fig_label": fig_label,
                    "section": current_section,
                    "image_type": img_type,
                    "semantic_tags": semantic_tags,
                    "nearby_text": " ".join(nearby_paragraphs[:2])[:400],
                    "rect": (rect.x0, rect.y0, rect.x1, rect.y1),
                    "priority": (has_explicit_caption, 1 if caption else 0, area),
                }

                # Same-page deduplication
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

        # Store detected sections outline
        result.sections = [{"title": s, "pages": sorted(list(set(pgs)))} for s, pgs in doc_sections_map.items()]

        # Sort candidate figures: explicit caption first, then caption presence, then area
        extracted_candidates.sort(key=lambda c: c["priority"], reverse=True)

        if on_progress:
            on_progress(f"Finalizing high-res documentary figures from {filename}...")

        # Dynamic capacity: scale up to max(40, total_pages * 2) so large textbooks retain rich visual evidence
        max_figures = max(40, total_pages * 2)
        seen_image_hashes: set[str] = set()

        for cand in extracted_candidates:
            if len(result.extracted_images) >= max_figures:
                break
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
                image_sha = hashlib.sha256(image_bytes).hexdigest()
                if image_sha in seen_image_hashes:
                    continue
                seen_image_hashes.add(image_sha)

                image_id = f"img_{Path(filename).stem}_p{cand['page']}_{cand['img_idx']}"
                storage_key = f"extracted/{Path(filename).stem}_p{cand['page']}_img{cand['img_idx']}.{ext}"
                aspect_ratio = round(pix.width / max(1, pix.height), 3)

                result.image_payloads.append((storage_key, image_bytes, f"image/{ext}"))
                result.extracted_images.append({
                    "image_id": image_id,
                    "storage_key": storage_key,
                    "source_document": filename,
                    "source_page": cand["page"],
                    "page": cand["page"],
                    "source": f"{filename}#page={cand['page']}",
                    "width": pix.width,
                    "height": pix.height,
                    "aspect_ratio": aspect_ratio,
                    "format": ext,
                    "byte_size": len(image_bytes),
                    "sha256": image_sha,
                    "caption": cand["caption"],
                    "image_type": cand["image_type"],
                    "section": cand["section"],
                    "semantic_tags": cand["semantic_tags"],
                    "nearby_text": cand["nearby_text"],
                    "relevance": 1.0 if cand["caption"] else 0.7,
                    "quality_score": 1.0 if pix.width >= 300 and pix.height >= 300 else 0.85,
                })
            except Exception:
                logger.warning("Skipping image xref %s on page %s", xref, cand["page"], exc_info=True)

        try:
            doc.close()
        except Exception:
            pass

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
