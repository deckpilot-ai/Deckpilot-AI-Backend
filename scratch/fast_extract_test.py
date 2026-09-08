import time
import pymupdf
import re
from pathlib import Path

def benchmark_full_extraction(pdf_bytes: bytes, filename: str):
    t0 = time.perf_counter()
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    total_pages = len(doc)
    
    # 1. Text blocks
    text_blocks = []
    for p_idx in range(total_pages):
        page = doc[p_idx]
        text = page.get_text("text").strip()
        if text:
            text_blocks.append({"page": p_idx + 1, "content": text, "source": f"{filename}#page={p_idx + 1}"})
            
    # 2. Pre-scan xrefs
    xref_page_counts = {}
    if total_pages >= 3:
        for p_idx in range(total_pages):
            p = doc[p_idx]
            seen = set()
            for img in p.get_images(full=True):
                x = img[0]
                if x not in seen:
                    seen.add(x)
                    xref_page_counts[x] = xref_page_counts.get(x, 0) + 1
                    
    # 3. Candidate metadata scan
    candidates = []
    for page_idx in range(total_pages):
        page = doc[page_idx]
        image_list = page.get_images(full=True)
        visible = {item["xref"]: pymupdf.Rect(item["bbox"]) for item in page.get_image_info(xrefs=True)}
        
        for img_idx, img_info in enumerate(image_list):
            xref = img_info[0]
            if xref_page_counts.get(xref, 0) >= 3:
                continue
            rect = visible.get(xref)
            if not rect or rect.width < 45 or rect.height < 45:
                continue
            if rect.width * rect.height > page.rect.width * page.rect.height * 0.88:
                continue
                
            # Quick caption scan
            rects = page.get_image_rects(xref)
            caption = ""
            if rects:
                r = rects[0]
                cand_blocks = []
                for b in page.get_text("blocks"):
                    if len(b) > 4 and str(b[4]).strip():
                        b_text = str(b[4]).strip()
                        if b[0] < r.x1 + 40 and b[2] > r.x0 - 40:
                            dist_below = b[1] - r.y1
                            is_fig = bool(re.search(r'\b(?:fig(?:ure)?\.?|map|photo|chart|diagram|plate)\s*[\d\.]', b_text, re.I))
                            if is_fig and (-30 <= dist_below < 120):
                                cand_blocks.append((0, abs(dist_below), b_text))
                            elif -15 <= dist_below < 120:
                                cand_blocks.append((1, abs(dist_below), b_text))
                if cand_blocks:
                    cand_blocks.sort(key=lambda c: (c[0], c[1]))
                    caption = " ".join(cand_blocks[0][2].split())[:300]
                    
            fig_match = re.search(r'\b(?:fig(?:ure)?\.?|map|photo|chart|diagram|plate)\s*([\d\.]+)', caption, re.I)
            fig_label = fig_match.group(0).lower() if fig_match else ""
            has_caption = 1 if fig_label or bool(re.search(r'\b(?:fig(?:ure)?\.?|map|photo|chart|diagram|plate)\b', caption, re.I)) else 0
            area = rect.width * rect.height
            
            candidates.append({
                "xref": xref,
                "page": page_idx + 1,
                "img_idx": img_idx,
                "rect": (rect.x0, rect.y0, rect.x1, rect.y1),
                "caption": caption,
                "fig_label": fig_label,
                "priority": (has_caption, 1 if caption else 0, area),
                "width": int(rect.width),
                "height": int(rect.height)
            })
            
    # Sort and take top 20
    candidates.sort(key=lambda c: c["priority"], reverse=True)
    top_candidates = candidates[:20]
    
    # 4. Extract bytes ONLY for top 20
    extracted_images = []
    for cand in top_candidates:
        xref = cand["xref"]
        try:
            pix = pymupdf.Pixmap(doc, xref)
            if pix.colorspace and pix.colorspace.n != 3:
                pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
            img_bytes = pix.tobytes("png")
            storage_key = f"extracted/{Path(filename).stem}_p{cand['page']}_img{cand['img_idx']}.png"
            extracted_images.append({
                "storage_key": storage_key,
                "width": pix.width,
                "height": pix.height,
                "format": "png",
                "page": cand["page"],
                "byte_size": len(img_bytes),
                "caption": cand["caption"]
            })
        except Exception:
            pass
            
    t1 = time.perf_counter()
    print(f"Full optimized extraction took {t1 - t0:.2f}s! Extracted {len(text_blocks)} pages, {len(extracted_images)} top figures.")

if __name__ == "__main__":
    with open(r"c:\DeckPilotAI\source data.pdf", "rb") as f:
        pdf_bytes = f.read()
    benchmark_full_extraction(pdf_bytes, "source data.pdf")
