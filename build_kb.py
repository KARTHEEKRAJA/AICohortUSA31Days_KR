import os
import sqlite3
import pandas as pd

# --- Part 1: Load all Day 5 text files ---
documents = []   # list of dicts: {"source": ..., "text": ...}

RAW = "raw_text"
for fname in os.listdir(RAW):
    if fname.endswith(".txt"):
        with open(os.path.join(RAW, fname), encoding="utf-8") as f:
            documents.append({"source": fname, "text": f.read()})

print(f"Loaded {len(documents)} text files:", [d["source"] for d in documents])

# --- Part 2: Export Day 4 plans as one chunk per plan ---
conn = sqlite3.connect("coverage.db")
plans = pd.read_sql("SELECT * FROM plans", conn)
conn.close()

plan_chunks = []
for _, row in plans.iterrows():
    chunk = (
        f"{row['plan_name']} (plan ID {row['plan_id']}): "
        f"${row['monthly_premium']}/month premium, "
        f"${row['annual_deductible']} annual deductible, "
        f"{row['copay_pct']}% copay, "
        f"coverage type: {row['coverage_type']}, "
        f"network tier: {row['network_tier']}."
    )
    plan_chunks.append(chunk)
    documents.append({"source": f"plans_db:{row['plan_id']}", "text": chunk})

print("\nPlan chunks:")
for c in plan_chunks:
    print("-", c)

print(f"\nTotal documents in knowledge base input: {len(documents)}")

from langchain_text_splitters import RecursiveCharacterTextSplitter

splitter = RecursiveCharacterTextSplitter(
    chunk_size=500,
    chunk_overlap=50,
    separators=["\n\n", "\n", ". ", " ", ""],   # paragraph -> line -> sentence -> word
)

chunks = []   # final KB units: {"source", "section", "text"}

def guess_section(text: str) -> str:
    """Tag chunks by coverage topic so exclusions/claims stay identifiable."""
    t = text.lower()
    if "not covered" in t or "exclusion" in t:
        return "exclusions"
    if "claim" in t or "appeal" in t:
        return "claims_process"
    if any(k in t for k in ["copay", "deductible", "coinsurance", "covered", "premium"]):
        return "covered_services"
    return "general"

for doc in documents:
    if doc["source"].startswith("plans_db:"):
        # Plan chunks are already atomic — never split them
        chunks.append({"source": doc["source"], "section": "plan_summary",
                       "text": doc["text"]})
    else:
        for piece in splitter.split_text(doc["text"]):
            chunks.append({"source": doc["source"],
                           "section": guess_section(piece),
                           "text": piece})

print(f"Total chunks: {len(chunks)}\n")
for i, c in enumerate(chunks):
    print(f"[{i}] {c['source']} | {c['section']} | {len(c['text'])} chars")
    print(c["text"][:110].replace("\n", " "), "...\n")


import json
import re
from datetime import datetime, timezone

def detect_plan_type(text: str) -> str:
    """Find which plan a chunk talks about, if any."""
    t = text.lower()
    if "ppo" in t:
        return "PPO"
    if "hmo" in t:
        return "HMO"
    return "all"          # generic content not tied to one plan type

def map_section(section: str, source: str) -> str:
    """Map Step 3 tags to the required section vocabulary."""
    if "enrollment" in source:
        return "enrollment"
    return {
        "covered_services": "coverage",
        "plan_summary":     "coverage",
        "exclusions":       "exclusions",
        "claims_process":   "claims",
        "general":          "coverage",
    }[section]

now = datetime.now(timezone.utc).isoformat()

kb_records = []
for i, c in enumerate(chunks):
    is_plan = c["source"].startswith("plans_db:")
    record = {
        "id": f"chunk_{i:04d}",
        "text": c["text"],
        "source_file": "coverage.db" if is_plan else f"raw_text/{c['source']}",
        "source_type": "structured" if is_plan else "unstructured",
        "plan_type": detect_plan_type(c["text"]),
        "section": map_section(c["section"], c["source"]),
        "ingested_at": now,
    }
    kb_records.append(record)

# Sanity check
print(f"{len(kb_records)} records")
print(json.dumps(kb_records[0], indent=2))                  # a text chunk
print(json.dumps(kb_records[-1], indent=2))                 # a plan chunk

from collections import Counter
print("\nsource_type:", Counter(r["source_type"] for r in kb_records))
print("section:    ", Counter(r["section"] for r in kb_records))
print("plan_type:  ", Counter(r["plan_type"] for r in kb_records))

import json

with open("knowledge_base.jsonl", "w", encoding="utf-8") as f:
    for record in kb_records:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

print(f"Wrote {len(kb_records)} records to knowledge_base.jsonl")

# --- Verify by reading it back ---
with open("knowledge_base.jsonl", encoding="utf-8") as f:
    loaded = [json.loads(line) for line in f]

print(f"Read back {len(loaded)} records")
print(loaded[0]["id"], "|", loaded[0]["section"], "|", loaded[0]["text"][:60])