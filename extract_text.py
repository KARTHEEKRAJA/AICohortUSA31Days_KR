import pdfplumber
from docx import Document

# --- 1. PDF extraction with pdfplumber ---
pdf_text = ""
with pdfplumber.open("data1/raw/sbc_gold_ppo.pdf") as pdf:
    for i, page in enumerate(pdf.pages):
        text = page.extract_text()
        if text:                       # extract_text() can return None
            pdf_text += f"\n--- Page {i+1} ---\n{text}"

print("=== PDF TEXT ===")
print(pdf_text)

# --- 2. DOCX extraction with python-docx ---
doc = Document("data1/raw/claims_process.docx")
docx_text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())

print("\n=== DOCX TEXT ===")
print(docx_text)

# --- 3. Save extracted text for later steps ---
import os
os.makedirs("data1/extracted", exist_ok=True)
with open("data1/extracted/sbc_gold_ppo.txt", "w", encoding="utf-8") as f:
    f.write(pdf_text)
with open("data1/extracted/claims_process.txt", "w", encoding="utf-8") as f:
    f.write(docx_text)

print("\nSaved to data1/extracted/")