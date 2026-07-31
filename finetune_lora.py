"""Day 15 — LoRA fine-tune on the Day-14 dataset (CPU-friendly, 0.5B base).

Part 1: load base model + "before" sanity generation
Part 2: LoRA training on fine_tune_train.jsonl with live loss logs
"""
import json
import torch
from transformers import (AutoModelForCausalLM, AutoTokenizer,
                          Trainer, TrainingArguments)
from peft import LoraConfig, get_peft_model
from datasets import Dataset

BASE_MODEL = "Qwen/Qwen2.5-0.5B-Instruct"
TRAIN_FILE = "fine_tune_train.jsonl"
ADAPTER_DIR = "adapters/benefits-lora"
MAX_LEN = 256

device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"device: {device}")

tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)
model = AutoModelForCausalLM.from_pretrained(
    BASE_MODEL,
    dtype=torch.float32 if device == "cpu" else torch.bfloat16,
)
model.to(device)
print(f"loaded {BASE_MODEL}: {sum(p.numel() for p in model.parameters())/1e6:.0f}M params")


def generate(msgs, mdl, max_new_tokens=80):
    input_ids = tokenizer.apply_chat_template(
        msgs, add_generation_prompt=True, return_tensors="pt")
    if not torch.is_tensor(input_ids):
        input_ids = input_ids["input_ids"]
    input_ids = input_ids.to(device)
    out = mdl.generate(input_ids, max_new_tokens=max_new_tokens, do_sample=False)
    return tokenizer.decode(out[0][input_ids.shape[1]:], skip_special_tokens=True)


# ---------- "before" photo ----------
before = generate(
    [{"role": "system", "content": "You are a helpful benefits information assistant."},
     {"role": "user", "content": "What's the copay on the Gold plan?"}],
    model)
print("\nBASE MODEL says:")
print(before)

# ---------- Step 2: LoRA training ----------
print("\n" + "=" * 60)
print("LoRA TRAINING — 25 examples, watch the loss fall")
print("=" * 60)

# 1) load the Day-14 training set and render each example with the
#    model's own chat template (so it learns in its native format)
rows = [json.loads(l) for l in open(TRAIN_FILE, encoding="utf-8")]
texts = [tokenizer.apply_chat_template(r["messages"], tokenize=False) for r in rows]
print(f"training examples: {len(texts)}")


def tokenize(batch):
    enc = tokenizer(batch["text"], truncation=True, max_length=MAX_LEN,
                    padding="max_length")
    enc["labels"] = enc["input_ids"].copy()      # causal LM: predict the text itself
    return enc


ds = Dataset.from_dict({"text": texts}).map(tokenize, batched=True,
                                            remove_columns=["text"])

# 2) attach LoRA adapters — tiny trainable matrices on attention projections;
#    the 494M base weights stay frozen
lora_cfg = LoraConfig(
    r=16, lora_alpha=32, lora_dropout=0.05,
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
    task_type="CAUSAL_LM",
)
model = get_peft_model(model, lora_cfg)
model.print_trainable_parameters()               # expect ~0.5-1% of total

# 3) train — small epochs, live logs every few steps
args = TrainingArguments(
    output_dir="lora_out",
    num_train_epochs=4,
    per_device_train_batch_size=2,
    learning_rate=2e-4,
    logging_steps=5,
    save_strategy="no",
    report_to="none",
)
trainer = Trainer(model=model, args=args, train_dataset=ds)
trainer.train()

# 4) save just the adapters (a few MB — the "diploma")
model.save_pretrained(ADAPTER_DIR)
print(f"\nadapters saved to {ADAPTER_DIR}/")

# ---------- quick "after" peek (full exam comes next step) ----------
after = generate(
    [{"role": "system", "content": "You are a helpful benefits information assistant."},
     {"role": "user", "content": "What's the copay on the Gold plan?"}],
    model)
print("\nTUNED MODEL says:")
print(after)