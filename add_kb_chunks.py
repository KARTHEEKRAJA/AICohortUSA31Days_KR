"""Day 17 — KB repair: add two missing chunks discovered by testing.

1. chunk_0013 (enrollment instructions): T09 showed the corpus had only an
   'empty promise' title (chunk_0009) and a filled sample form (chunk_0004)
   on enrollment — no actual instructions. The model padded the gap with
   world knowledge (HealthCare.gov + an invented phone number).
2. chunk_0014 (plan catalog overview): Day-16 finding #5 — "What plans do
   you offer?" retrieved weakly because per-plan chunks exist but no chunk
   enumerates the catalog.

Appends to knowledge_base.jsonl AND embeds into the Chroma collection with
the same model/collection the retrieval engine uses. Idempotent: skips ids
that already exist.
"""
import json
from datetime import datetime, timezone

import chromadb
from sentence_transformers import SentenceTransformer

KB_PATH = "knowledge_base.jsonl"

NEW_CHUNKS = [
    {
        "id": "chunk_0013",
        "text": (
            "How to Enroll in a Health Plan - Member Instructions\n"
            "Step 1: Review the available plans (Gold PPO P101, Silver HMO P102, "
            "Bronze HMO P103) and choose the one that fits your needs and budget.\n"
            "Step 2: Complete the Health Plan Enrollment Form with your name, date "
            "of birth, member ID, selected plan, coverage start date, dependents, "
            "and primary care physician.\n"
            "Step 3: Sign and date the form, then submit it to Member Support by "
            "mail or through the member portal.\n"
            "Step 4: Your coverage begins on the coverage start date shown on your "
            "confirmation. Contact Member Support with any enrollment questions."
        ),
        "source_file": "raw_text/enrollment_instructions.txt",
        "source_type": "unstructured",
        "plan_type": "all",
        "section": "enrollment",
    },
    {
        "id": "chunk_0014",
        "text": (
            "Plan Catalog Overview - Plans We Offer\n"
            "We offer three health plans:\n"
            "1. Gold PPO (plan ID P101) - premium tier, PPO network.\n"
            "2. Silver HMO (plan ID P102) - mid tier, HMO network.\n"
            "3. Bronze HMO (plan ID P103) - value tier, HMO network.\n"
            "Each plan has its own monthly premium, annual deductible, and copay "
            "structure - see the plan's Summary of Benefits and Coverage or ask "
            "about a specific plan for details."
        ),
        "source_file": "raw_text/plan_catalog.txt",
        "source_type": "unstructured",
        "plan_type": "all",
        "section": "coverage",
    },
]


def main():
    # 1) append to the jsonl (skip existing ids)
    existing = set()
    with open(KB_PATH, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                existing.add(json.loads(line)["id"])

    to_add = [c for c in NEW_CHUNKS if c["id"] not in existing]
    if not to_add:
        print("All chunks already present in knowledge_base.jsonl — nothing to do.")
    else:
        stamp = datetime.now(timezone.utc).isoformat()
        with open(KB_PATH, "a", encoding="utf-8") as f:
            for c in to_add:
                record = {**c, "ingested_at": stamp}
                f.write(json.dumps(record) + "\n")
        print(f"Appended {len(to_add)} chunk(s) to {KB_PATH}: "
              f"{[c['id'] for c in to_add]}")

    # 2) embed + add to Chroma (same model + collection as retrieval_engine)
    model = SentenceTransformer("all-MiniLM-L6-v2")
    client = chromadb.PersistentClient(path="chroma_db")
    collection = client.get_or_create_collection("coverage_kb")

    have = set(collection.get(ids=[c["id"] for c in NEW_CHUNKS])["ids"])
    missing = [c for c in NEW_CHUNKS if c["id"] not in have]
    if not missing:
        print("All chunks already present in Chroma — nothing to do.")
        return

    collection.add(
        ids=[c["id"] for c in missing],
        documents=[c["text"] for c in missing],
        embeddings=[model.encode(c["text"]).tolist() for c in missing],
        metadatas=[{
            "source_file": c["source_file"],
            "source_type": c["source_type"],
            "plan_type": c["plan_type"],
            "section": c["section"],
        } for c in missing],
    )
    print(f"Embedded + added {len(missing)} chunk(s) to Chroma: "
          f"{[c['id'] for c in missing]}")
    print(f"Collection now holds {collection.count()} chunks.")


if __name__ == "__main__":
    main()