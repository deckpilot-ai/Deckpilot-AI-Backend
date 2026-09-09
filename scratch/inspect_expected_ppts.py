import glob, os, traceback
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE

for path in glob.glob("Expected PPT/*.pptx"):
    print(f"\n==========================================")
    print(f"FILE: {path}")
    try:
        prs = Presentation(path)
        print(f"Slide Dimensions: {prs.slide_width.inches:.2f} x {prs.slide_height.inches:.2f} in")
        slide_count = len(prs.slides._sldIdLst)
        print(f"Slide count in _sldIdLst: {slide_count}")
        for idx, slide in enumerate(prs.slides):
            print(f"  --- Slide {idx+1} ---")
            shape_summary = []
            for s in slide.shapes:
                info = f"{s.shape_type}"
                if s.has_text_frame and s.text.strip():
                    info += f": '{s.text.strip()[:40]}...'"
                if s.shape_type == MSO_SHAPE_TYPE.PICTURE:
                    info += f" [PICTURE: {s.image.size}]"
                if s.has_chart:
                    info += f" [CHART: {s.chart.chart_type}]"
                if s.has_table:
                    info += f" [TABLE: {len(s.table.rows)}x{len(s.table.columns)}]"
                shape_summary.append(info)
            print(f"      Shapes ({len(shape_summary)}): " + " | ".join(shape_summary[:6]))
    except Exception as e:
        print(f"Error parsing {path}: {e}")
        traceback.print_exc()
