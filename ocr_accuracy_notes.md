## OCR Accuracy Notes
- Clean 300-DPI printed text: near-100% accuracy, no corrections needed.
- Checkboxes: Tesseract has no concept of checkbox state — the empty box was
  dropped/garbled and the checked box read as noise characters (e.g. "X", "R", "&").
  Detecting checked vs unchecked needs image processing (OpenCV), not OCR.
- Simulated handwriting (italic): several misreads, e.g. "covrage" and the
  signature line degraded — real cursive would be far worse; production forms
  use specialized models (Google Document AI, Azure Form Recognizer).
- Degraded scan (1.5° skew + blur + noise): errors on characters near
  underlines; field lines read as "_" / "—" artifacts. Deskewing and
  binarization as preprocessing would improve results.