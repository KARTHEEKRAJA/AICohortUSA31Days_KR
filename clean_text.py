import os
import re
import unicodedata

SRC = "data1/extracted"
DST = "raw_text"
os.makedirs(DST, exist_ok=True)

def clean(text: str) -> str:
    # 1. Fix encoding artifacts / normalize unicode (curly quotes, dashes, ligatures)
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("\u00a0", " ")                 # non-breaking spaces
    # 2. Remove OCR/extraction junk lines (underscores, dashes, page markers)
    text = re.sub(r"^[\s_\-—=·.]{3,}$", "", text, flags=re.MULTILINE)
    # 3. Collapse whitespace
    text = re.sub(r"[ \t]+", " ", text)                # multiple spaces -> one
    text = re.sub(r"\n{3,}", "\n\n", text)             # 3+ newlines -> blank line
    # 4. Strip each line + drop empties at edges
    lines = [ln.strip() for ln in text.split("\n")]
    return "\n".join(lines).strip()

# source file -> required output name
mapping = {
    "sbc_gold_ppo.txt":         "benefits.txt",
    "claims_process.txt":       "claims_process.txt",
    "enrollment_form_ocr.txt":  "enrollment.txt",
    "webpage_deductible.txt":   "webpage_faq.txt",   # bonus 4th source
}

for src_name, dst_name in mapping.items():
    src_path = os.path.join(SRC, src_name)
    if not os.path.exists(src_path):
        print(f"MISSING: {src_path} — check filename")
        continue
    with open(src_path, encoding="utf-8", errors="replace") as f:
        raw = f.read()
    cleaned = clean(raw)
    with open(os.path.join(DST, dst_name), "w", encoding="utf-8") as f:
        f.write(cleaned)
    print(f"{src_name} -> {DST}/{dst_name}  ({len(raw)} -> {len(cleaned)} chars)")

print("\nDone:", os.listdir(DST))