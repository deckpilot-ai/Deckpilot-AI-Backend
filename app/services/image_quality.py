"""Reject non-illustrative QR assets without decoding or following their URLs."""
import cv2
import numpy as np
import pymupdf


def is_documentary_image(payload: bytes) -> bool:
    image = cv2.imdecode(np.frombuffer(payload, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        return False
    height, width = image.shape[:2]
    if min(height, width) < 40:
        return False
    if max(height, width) > 640:
        image = cv2.resize(image, (round(width * 640 / max(height, width)),
                                   round(height * 640 / max(height, width))))
    if float(cv2.cvtColor(image, cv2.COLOR_BGR2GRAY).std()) < 2:
        return False
    detected, _ = cv2.QRCodeDetector().detect(image)
    return not bool(detected)


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
        if not is_documentary_image(pix.tobytes('png')):
            return None
        rects = page.get_image_rects(record[0])
        if not rects:
            return None
        rect = rects[0] & page.rect
        page_has_fig = bool(re.search(r'\b(?:fig(?:ure)?\.?\s*[\d\.]|map\b|photo\b|plate\b)', page.get_text(), re.I))
        if rect.is_empty or (rect.get_area() > page.rect.get_area() * .95 and not page_has_fig):
            return None
        return page.get_pixmap(matrix=pymupdf.Matrix(1.8, 1.8), clip=rect, alpha=False).tobytes('png')
