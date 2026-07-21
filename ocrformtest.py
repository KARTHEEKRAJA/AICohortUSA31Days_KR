import os
from PIL import Image
from pdf2image import convert_from_path
import pytesseract

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
POPPLER = r"C:\poppler\poppler-26.02.0\Library\bin"   # adjust to your extracted poppler path

# 0. Make a scanned-style PDF from the PNG
img = Image.open("data1/raw/enrollment_form_scan.png").convert("RGB")
img.save("data1/raw/enrollment_form_scan.pdf")

# 1. PDF pages -> images
pages = convert_from_path("data1/raw/enrollment_form_scan.pdf", dpi=300,
                          poppler_path=POPPLER)
print(f"{len(pages)} page(s) converted")

# 2. OCR each page image
ocr_text = ""
for i, page_img in enumerate(pages):
    text = pytesseract.image_to_string(page_img)
    ocr_text += f"\n--- Page {i+1} ---\n{text}"

print(ocr_text)

# 3. Save
os.makedirs("data1/extracted", exist_ok=True)
with open("data1/extracted/enrollment_form_ocr.txt", "w", encoding="utf-8") as f:
    f.write(ocr_text)
print("Saved data1/extracted/enrollment_form_ocr.txt")