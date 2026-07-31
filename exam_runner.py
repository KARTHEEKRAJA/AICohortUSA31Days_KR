"""Day 15 — THE EXAM: 5 held-out questions, base vs tuned, side by side.

The vault opens: these questions were never trained on. Output goes to
console + fine_tune_exam_raw.md (evidence for fine_tune_comparison.md).
"""
import json
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel

BASE_MODEL = "Qwen/Qwen2.5-0.5B-Instruct"
ADAPTER_DIR = "adapters/benefits-lora"
TEST_FILE = "fine_tune_test.jsonl"
OUT_FILE = "fine_tune_exam_raw.md"

# must match the system prompt in the training data exactly
SYSTEM = ("You are a helpful benefits information assistant for a health "
          "insurance plan. Answer warmly and precisely. Never give medical advice.")

device = "cuda" if torch.cuda.is_available() else "cpu"
tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)

base = AutoModelForCausalLM.from_pretrained(
    BASE_MODEL, dtype=torch.float32 if device == "cpu" else torch.bfloat16)
base.to(device)

tuned = PeftModel.from_pretrained(
    AutoModelForCausalLM.from_pretrained(
        BASE_MODEL, dtype=torch.float32 if device == "cpu" else torch.bfloat16),
    ADAPTER_DIR)
tuned.to(device)
print(f"adapters loaded from {ADAPTER_DIR} — exam begins\n")


def generate(mdl, question: str, max_new_tokens=90) -> str:
    msgs = [{"role": "system", "content": SYSTEM},
            {"role": "user", "content": question}]
    input_ids = tokenizer.apply_chat_template(
        msgs, add_generation_prompt=True, return_tensors="pt")
    if not torch.is_tensor(input_ids):
        input_ids = input_ids["input_ids"]
    input_ids = input_ids.to(device)
    out = mdl.generate(input_ids, max_new_tokens=max_new_tokens, do_sample=False)
    return tokenizer.decode(out[0][input_ids.shape[1]:], skip_special_tokens=True).strip()


# load the sealed exam — question + the ideal answer written on Day 14
exam = []
for line in open(TEST_FILE, encoding="utf-8"):
    msgs = json.loads(line)["messages"]
    q = next(m["content"] for m in msgs if m["role"] == "user")
    ideal = next(m["content"] for m in msgs if m["role"] == "assistant")
    exam.append((q, ideal))
print(f"{len(exam)} sealed questions loaded — the model has NEVER seen these\n")

lines = ["# Fine-Tune Exam — Raw Results (Day 15)", "",
         "5 held-out questions. Neither answer was trained on. "
         "Base vs LoRA-tuned Qwen2.5-0.5B-Instruct, greedy decoding.", "", "---", ""]

for i, (q, ideal) in enumerate(exam, 1):
    print("=" * 70)
    print(f"E{i}: {q}")
    b = generate(base, q)
    t = generate(tuned, q)
    print(f"\n[BASE ]: {b}")
    print(f"\n[TUNED]: {t}")
    print(f"\n[IDEAL]: {ideal}")
    lines += [f"## E{i}: {q}", "",
              f"**BASE:** {b}", "",
              f"**TUNED:** {t}", "",
              f"**IDEAL (from Day 14):** {ideal}", "", "---", ""]

with open(OUT_FILE, "w", encoding="utf-8") as f:
    f.write("\n".join(lines))
print("=" * 70)
print(f"\nWrote {OUT_FILE} — raw evidence for the comparison write-up")