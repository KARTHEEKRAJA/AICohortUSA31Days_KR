"""Day 15 — load the saved LoRA adapters onto a fresh base model."""
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel

BASE_MODEL = "Qwen/Qwen2.5-0.5B-Instruct"
ADAPTER_DIR = "adapters/benefits-lora"

# IMPORTANT: must match the system prompt used in fine_tune_train.jsonl —
# a small fine-tune binds tightly to its exact training frame.
SYSTEM = ("You are a helpful benefits information assistant for a health "
          "insurance plan. Answer warmly and precisely. Never give medical advice.")

device = "cuda" if torch.cuda.is_available() else "cpu"
tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)

# 1) fresh, untuned base — straight from the hub cache
base = AutoModelForCausalLM.from_pretrained(
    BASE_MODEL, dtype=torch.float32 if device == "cpu" else torch.bfloat16)
base.to(device)

# 2) same base + your saved adapters bolted on
tuned = PeftModel.from_pretrained(
    AutoModelForCausalLM.from_pretrained(
        BASE_MODEL, dtype=torch.float32 if device == "cpu" else torch.bfloat16),
    ADAPTER_DIR)
tuned.to(device)
print(f"adapters loaded from {ADAPTER_DIR}")


def generate(mdl, question: str, max_new_tokens=80) -> str:
    msgs = [{"role": "system", "content": SYSTEM},
            {"role": "user", "content": question}]
    input_ids = tokenizer.apply_chat_template(
        msgs, add_generation_prompt=True, return_tensors="pt")
    if not torch.is_tensor(input_ids):
        input_ids = input_ids["input_ids"]
    input_ids = input_ids.to(device)
    out = mdl.generate(input_ids, max_new_tokens=max_new_tokens, do_sample=False)
    return tokenizer.decode(out[0][input_ids.shape[1]:], skip_special_tokens=True)


if __name__ == "__main__":
    q = "Is physical therapy covered under the Silver plan?"   # a TRAINED example
    print("\nQ:", q)
    print("\n[BASE]:", generate(base, q))
    print("\n[TUNED]:", generate(tuned, q))