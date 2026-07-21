import os
import requests
from bs4 import BeautifulSoup

url = "https://www.healthcare.gov/glossary/deductible/"
headers = {"User-Agent": "Mozilla/5.0 (learning project; contact: student)"}

resp = requests.get(url, headers=headers, timeout=15)
print("Status:", resp.status_code)          # want 200

soup = BeautifulSoup(resp.text, "html.parser")

# 1. Remove non-content elements BEFORE extracting
for tag in soup(["script", "style", "nav", "footer", "header", "aside", "form", "noscript"]):
    tag.decompose()

# 2. Target the main content container, fall back to <body>
main = soup.find("main") or soup.find("article") or soup.body

# 3. Extract clean text
text = main.get_text(separator="\n", strip=True)

# 4. Drop very short leftover lines (menu crumbs, buttons)
lines = [ln for ln in text.split("\n") if len(ln) > 30]
clean_text = "\n".join(lines)

print(clean_text[:1500])

# 5. Save
os.makedirs("data1/extracted", exist_ok=True)
with open("data1/extracted/webpage_deductible.txt", "w", encoding="utf-8") as f:
    f.write(f"SOURCE: {url}\n\n{clean_text}")
print("\nSaved data1/extracted/webpage_deductible.txt")