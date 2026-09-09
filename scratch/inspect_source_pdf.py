import pymupdf

doc = pymupdf.open("source data.pdf")
print(f"source data.pdf: {len(doc)} pages")
for pno in range(min(5, len(doc))):
    p = doc[pno]
    print(f"Page {pno+1}: text length = {len(p.get_text())}, images = {len(p.get_images())}")
    for img in p.get_images():
        print(f"   image xref={img[0]}, size={img[2]}x{img[3]}")
