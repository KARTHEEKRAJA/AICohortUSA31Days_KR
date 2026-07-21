import random
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import pytesseract

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

img = Image.open("data1/raw/enrollment_form_scan.png").convert("RGB")
d = ImageDraw.Draw(img)

# 1. Checkboxes
try:
    font = ImageFont.truetype("arial.ttf", 26)
except OSError:
    font = ImageFont.load_default()
d.rectangle((60, 1050, 85, 1075), outline="black", width=3)          # empty box
d.text((100, 1048), "Individual Coverage", font=font, fill="black")
d.rectangle((450, 1050, 475, 1075), outline="black", width=3)        # checked box
d.line((452, 1052, 473, 1073), fill="black", width=3)
d.line((452, 1073, 473, 1052), fill="black", width=3)
d.text((490, 1048), "Family Coverage", font=font, fill="black")

# 2. "Handwritten" entry (italic simulates cursive)
try:
    hand = ImageFont.truetype("ariali.ttf", 30)   # Arial Italic
except OSError:
    hand = font
d.text((60, 1120), "Notes: please start covrage asap - Jane", font=hand, fill="darkblue")

# 3. Simulate a bad scan: slight rotation + blur + noise
img = img.rotate(1.5, expand=True, fillcolor="white")
img = img.filter(ImageFilter.GaussianBlur(0.8))
px = img.load()
for _ in range(4000):
    x, y = random.randint(0, img.width-1), random.randint(0, img.height-1)
    px[x, y] = (random.randint(0, 80),) * 3

img.save("data1/raw/enrollment_form_noisy.png")

# Re-OCR
noisy_text = pytesseract.image_to_string(Image.open("data1/raw/enrollment_form_noisy.png"))
print(noisy_text)