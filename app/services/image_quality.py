"""Reject non-illustrative QR assets without decoding or following their URLs."""
import re

import cv2
import numpy as np
import pymupdf


def is_documentary_cv_image(image: np.ndarray) -> bool:
    """Inspect OpenCV image: check resolution, variance, aspect ratio, and selective QR detection."""
    height, width = image.shape[:2]
    if min(height, width) < 50 or (height * width) < 6000:
        return False
    aspect = width / max(1, height)
    # Reject extreme thin strips (lines, dividers, slivers)
    if aspect < 0.22 or aspect > 4.5:
        return False
    if max(height, width) > 640:
        scale = 640.0 / max(height, width)
        image = cv2.resize(image, (round(width * scale), round(height * scale)))
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    if float(gray.std()) < 3.5:
        return False
    # Only run QR detector on square-ish, monochrome images (QR codes are 1:1 aspect ratio and near-grayscale)
    if 0.82 <= aspect <= 1.22:
        diff = np.abs(image[:, :, 0].astype(int) - image[:, :, 1].astype(int)) + np.abs(image[:, :, 1].astype(int) - image[:, :, 2].astype(int))
        if diff.mean() < 14:  # mostly grayscale/monochrome
            detected, _ = cv2.QRCodeDetector().detect(image)
            return not bool(detected)
    return True


def is_documentary_pixmap(pix: pymupdf.Pixmap) -> bool:
    """Fast check directly on PyMuPDF Pixmap without expensive PNG compression/decompression."""
    height, width = pix.height, pix.width
    if min(height, width) < 50 or (height * width) < 6000:
        return False
    aspect = width / max(1, height)
    if aspect < 0.22 or aspect > 4.5:
        return False
    channels = pix.n
    if channels not in (1, 3, 4):
        return False
    try:
        arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape((height, width, channels))
    except Exception:
        return False
    if channels == 4:
        arr = arr[:, :, :3]
    elif channels == 1:
        arr = cv2.cvtColor(arr, cv2.COLOR_GRAY2BGR)
    return is_documentary_cv_image(arr)


def is_documentary_image(payload: bytes) -> bool:
    image = cv2.imdecode(np.frombuffer(payload, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        return False
    return is_documentary_cv_image(image)


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

