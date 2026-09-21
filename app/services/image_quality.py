"""Reject non-illustrative QR assets without decoding or following their URLs."""
import re
from typing import Any

try:
    import cv2
except ImportError:
    cv2 = None
try:
    import numpy as np
except ImportError:
    np = None
try:
    import pymupdf
except ImportError:
    pymupdf = None


def is_documentary_cv_image(image: Any) -> bool:
    """Inspect OpenCV image: check resolution, variance, aspect ratio, and selective QR detection."""
    if cv2 is None or np is None or image is None:
        return True
    height, width = image.shape[:2]
    if min(height, width) < 50 or (height * width) < 6000:
        return False
    aspect = width / max(1, height)
    # Reject extreme thin strips (lines, dividers, slivers)
    if aspect < 0.22 or aspect > 4.5:
        return False
    if max(height, width) > 320:
        scale = 320.0 / max(height, width)
        image = cv2.resize(image, (max(1, round(width * scale)), max(1, round(height * scale))))
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    if float(gray.std()) < 3.5:
        return False
    # Only run QR detector on square-ish, monochrome images (QR codes are 1:1 aspect ratio and near-grayscale)
    if 0.82 <= aspect <= 1.22:
        diff = np.abs(image[:, :, 0].astype(int) - image[:, :, 1].astype(int)) + np.abs(image[:, :, 1].astype(int) - image[:, :, 2].astype(int))
        if diff.mean() < 14:  # mostly grayscale/monochrome
            if max(height, width) <= 500:
                try:
                    detected, _ = cv2.QRCodeDetector().detect(image)
                    return not bool(detected)
                except Exception:
                    return True
    return True


def is_documentary_pixmap(pix: pymupdf.Pixmap) -> bool:
    """Fast check directly on PyMuPDF Pixmap without expensive full-image copies or PNG compression."""
    if pix is None:
        return False
    height, width = pix.height, pix.width
    if min(height, width) < 40 or (height * width) < 3500:
        return False
    aspect = width / max(1, height)
    if aspect < 0.20 or aspect > 5.0:
        return False
    channels = pix.n
    if channels not in (1, 2, 3, 4, 5):
        return False

    # Check sample variance without requiring numpy to succeed
    stride = max(1, (height * width) // 4000)
    samples_buf = pix.samples
    if samples_buf:
        try:
            if np is not None:
                raw_samples = np.frombuffer(samples_buf, dtype=np.uint8)[::stride * channels]
                if len(raw_samples) > 20 and float(raw_samples.std()) < 3.0:
                    return False
            else:
                # Pure python fallback: sample up to 100 bytes
                sampled = [samples_buf[i] for i in range(0, min(len(samples_buf), 100 * stride * channels), stride * channels)]
                if len(sampled) > 20:
                    mean = sum(sampled) / len(sampled)
                    var = sum((x - mean) ** 2 for x in sampled) / len(sampled)
                    if (var ** 0.5) < 3.0:
                        return False
        except Exception:
            # Never silently reject an image due to an internal check failure
            return True

    return True


def is_documentary_image(payload: bytes) -> bool:
    if not payload:
        return False
    if cv2 is None or np is None:
        return len(payload) > 2000
    try:
        image = cv2.imdecode(np.frombuffer(payload, dtype=np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            return False
        return is_documentary_cv_image(image)
    except Exception:
        return len(payload) > 2000


def classify_image_type(caption: str = "", nearby_text: str = "", aspect_ratio: float = 1.0) -> str:
    """Classify documentary image type based on caption, surrounding context, and geometry."""
    combined = f"{caption} {nearby_text}".lower()

    # 1. Map / Geography / Territory
    if any(k in combined for k in ("map", "territory", "boundary", "region", "route", "empire", "province", "peninsula", "geographical", "kingdom", "expansion")):
        return "map"

    # 2. Portrait / Leader / Figure
    if any(k in combined for k in ("portrait", "leader", "ruler", "king", "queen", "emperor", "minister", "president", "chhatrapati", "peshwa", "general", "biography", "statue of", "bust of", "figure of")):
        return "portrait"

    # 3. Chart / Graph / Statistics / Data Table
    if any(k in combined for k in ("chart", "graph", "histogram", "pie chart", "bar chart", "percentage", "table", "statistics", "data", "growth rate", "revenue")):
        return "chart"

    # 4. Diagram / Flowchart / System / Architecture
    if any(k in combined for k in ("diagram", "flowchart", "schematic", "hierarchy", "structure", "framework", "architecture", "system", "process", "cycle", "layout", "plan")):
        return "diagram"

    # 5. Artefact / Archaeology / Coin / Seal / Weapon
    if any(k in combined for k in ("coin", "seal", "inscription", "sculpture", "relic", "artefact", "artifact", "pottery", "sword", "weapon", "fort", "monument", "temple", "manuscript", "plate")):
        return "artefact"

    # 6. Default to photograph / illustration based on aspect ratio
    if 0.6 <= aspect_ratio <= 2.2:
        return "photograph"
    return "illustration"


def source_figure(pdf_bytes: bytes, page_number: int, image_index: int) -> bytes | None:
    """Revalidate cached figures against the original PDF, including old uploads."""
    with pymupdf.open(stream=pdf_bytes, filetype='pdf') as doc:
        page = doc[page_number - 1]
        record = page.get_images(full=True)[image_index]
        pix = pymupdf.Pixmap(doc, record[0])
        if not pix.colorspace:
            return None
        if pix.colorspace.n != 3:
            pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
        if not is_documentary_pixmap(pix):
            return None
        rects = page.get_image_rects(record[0])
        if not rects:
            return None
        rect = rects[0] & page.rect
        page_has_fig = bool(re.search(r'\b(?:fig(?:ure)?\.?\s*[\d\.]|map\b|photo\b|plate\b)', page.get_text(), re.I))
        if rect.is_empty or (rect.get_area() > page.rect.get_area() * .88 and not page_has_fig):
            return None
        return page.get_pixmap(matrix=pymupdf.Matrix(1.8, 1.8), clip=rect, alpha=False).tobytes('png')

