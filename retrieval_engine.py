"""Day 10 — Hybrid Retrieval Engine.
classifier -> sql_lookup / vector_lookup -> retrieve (orchestrator)
"""

# ---------------------------------------------------------------
# Step 1: question classifier
# ---------------------------------------------------------------

# Signals that the answer lives in the database (exact facts/numbers)
STRUCTURED_KEYWORDS = [
    "deductible", "premium", "copay", "cost", "price", "how much",
    "claim status", "my claim", "status of claim", "pending", "approved",
    "denied", "monthly", "annual", "$", "cheapest", "under", "compare price",
]

# Signals that the answer lives in documents (explanations/policies)
UNSTRUCTURED_KEYWORDS = [
    "covered", "coverage", "exclude", "not covered", "how do i",
    "how to", "process", "appeal", "file a claim", "enroll",
    "what is", "explain", "eligible", "procedure", "policy",
]

def classify(question: str) -> str:
    """Label a question 'structured', 'unstructured', or 'both'."""
    q = question.lower()
    is_structured = any(kw in q for kw in STRUCTURED_KEYWORDS)
    is_unstructured = any(kw in q for kw in UNSTRUCTURED_KEYWORDS)

    if is_structured and is_unstructured:
        return "both"
    if is_structured:
        return "structured"
    if is_unstructured:
        return "unstructured"
    return "unstructured"   # safe default: semantic search degrades gracefully

# --- quick test ---
if __name__ == "__main__":
    tests = [
        "What's my deductible?",                              # structured
        "Is physical therapy covered under the Silver plan?", # unstructured
        "How much does the plan that covers X-rays cost?",    # both
        "How do I appeal a denied claim?",                    # unstructured (appeal/how do i)
        "What's the claim status for member M1001?",          # structured
        "Tell me about health insurance",                     # fallback -> unstructured
    ]
    for t in tests:
        print(f"{classify(t):>12}  <-  {t}")


# ---------------------------------------------------------------
# Step 2: sql_lookup — structured questions -> SQL over coverage.db
# ---------------------------------------------------------------
import re
import sqlite3

DB_PATH = "coverage.db"

def _run_sql(query: str, params: tuple = ()) -> list[dict]:
    """Execute SQL, return rows as list of dicts."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = [dict(r) for r in conn.execute(query, params).fetchall()]
    conn.close()
    return rows

def _extract_plan(q: str) -> str | None:
    """Find which plan the question mentions, if any."""
    for name in ("gold", "silver", "bronze"):
        if name in q:
            return name.capitalize()
    return None

def _extract_member(q: str) -> str | None:
    m = re.search(r"\bM\d{4}\b", q, flags=re.IGNORECASE)
    return m.group(0).upper() if m else None


def _extract_claim_id(q: str) -> str | None:
    """Find a claim ID like C1001 or C-2031; normalize to DB form (C1001)."""
    m = re.search(r"\bC-?\d{3,}\b", q, flags=re.IGNORECASE)
    return m.group(0).upper().replace("-", "") if m else None

def sql_lookup(question: str) -> list[dict]:
    """Route a structured question to a templated, parameterized SQL query."""
    q = question.lower()
    plan = _extract_plan(q)
    member = _extract_member(question)

    # Template 1: deductible / premium / copay for a plan
    if any(w in q for w in ("deductible", "premium", "copay")) and plan:
        return _run_sql(
            "SELECT plan_name, monthly_premium, annual_deductible, copay_pct "
            "FROM plans WHERE plan_name LIKE ?", (f"{plan}%",))

    # Template 2a: claim status by claim ID  e.g. "status of claim C1001"
    claim_id = _extract_claim_id(question)
    if "claim" in q and claim_id:
        return _run_sql(
            "SELECT claim_id, member_id, procedure, claim_amount, status, date_filed "
            "FROM claims WHERE claim_id = ?", (claim_id,))

    # Template 2b: claim status for a member
    # (T06 fix: member_id now SELECTed — its absence made the model unable to
    #  confirm the member and refuse; root-caused Day 11, fixed Day 17)
    if "claim" in q and member:
        return _run_sql(
            "SELECT claim_id, member_id, procedure, claim_amount, status, date_filed "
            "FROM claims WHERE member_id = ?", (member,))

    # Template 3: plans under a price  e.g. "under $400"
    price = re.search(r"\$?(\d{2,5})", q)
    if any(w in q for w in ("under", "cheaper", "less than", "cheapest")) and price:
        return _run_sql(
            "SELECT plan_name, monthly_premium FROM plans "
            "WHERE monthly_premium < ? ORDER BY monthly_premium", (int(price.group(1)),))

    # Template 4: generic plan facts (no specific plan named) — return all plans
    if any(w in q for w in ("deductible", "premium", "copay", "cost", "price", "plans")):
        return _run_sql(
            "SELECT plan_name, monthly_premium, annual_deductible, copay_pct FROM plans")

    return []   # no template matched — orchestrator will fall back to vector

# --- quick test ---
if __name__ == "__main__":
    for t in [
        "What's the deductible on the Silver plan?",
        "What's the claim status for member M1001?",
        "Which plans are under $400 a month?",
        "What are the copays?",
        "How do I appeal?",           # expect [] — not a structured question
    ]:
        print(f"\nQ: {t}")
        for row in sql_lookup(t) or [{"result": "no SQL template matched"}]:
            print("  ", row)


# ---------------------------------------------------------------
# Step 3: vector_lookup — semantic questions -> Chroma top-5
# ---------------------------------------------------------------
import chromadb
from sentence_transformers import SentenceTransformer

# Load once at module level (same pattern as Day 7 — load once, call many)
_model = SentenceTransformer("all-MiniLM-L6-v2")
_client = chromadb.PersistentClient(path="chroma_db")
_collection = _client.get_or_create_collection("coverage_kb")

def vector_lookup(question: str, n_results: int = 5,
                  where: dict | None = None) -> list[dict]:
    """Embed the question, return top-N chunks with metadata + distance."""
    q_vec = _model.encode(question).tolist()

    kwargs = {"query_embeddings": [q_vec], "n_results": n_results}
    if where:
        kwargs["where"] = where          # optional metadata filter (Day 9's fix)

    res = _collection.query(**kwargs)

    hits = []
    for doc_id, doc, meta, dist in zip(
        res["ids"][0], res["documents"][0],
        res["metadatas"][0], res["distances"][0],
    ):
        hits.append({
            "id": doc_id,
            "text": doc,
            "distance": round(dist, 3),
            "section": meta["section"],
            "plan_type": meta["plan_type"],
            "source": meta["source_file"],
        })
    return hits

# --- quick test ---
if __name__ == "__main__":
    print("\n--- vector_lookup test ---")
    for h in vector_lookup("How do I appeal a denied claim?"):
        print(f"  {h['id']}  d={h['distance']}  [{h['section']}]  {h['text'][:60]}...")

    print("\n--- with metadata filter (plan_type=HMO) ---")
    for h in vector_lookup("Is physical therapy covered under the Silver plan?",
                           where={"plan_type": "HMO"}):
        print(f"  {h['id']}  d={h['distance']}  [{h['section']} | {h['plan_type']}]")


# ---------------------------------------------------------------
# Step 4: retrieve — the orchestrator
# ---------------------------------------------------------------

def _detect_plan_filter(question: str) -> dict | None:
    """If a specific plan family is mentioned, build a metadata filter.

    Day 17 fix: filters must NEVER exclude plan_type="all" universal chunks
    (catalog, exclusions, claims process...). The old exact-match filter had
    silently discarded universal knowledge whenever a plan was named — since
    Day 9. $in keeps the plan family AND the universal chunks.
    """
    q = question.lower()
    if "silver" in q or "bronze" in q:
        return {"plan_type": {"$in": ["HMO", "all"]}}   # plan family + universal
    if "gold" in q:
        return {"plan_type": {"$in": ["PPO", "all"]}}
    return None

def retrieve(question: str) -> dict:
    """Classify, route, merge. Returns one context package."""
    route = classify(question)
    sql_rows, chunks = [], []

    if route in ("structured", "both"):
        sql_rows = sql_lookup(question)

    if route in ("unstructured", "both") or (route == "structured" and not sql_rows):
        # vector runs for unstructured/both — AND as fallback when SQL found nothing
        chunks = vector_lookup(question, where=_detect_plan_filter(question))

    # --- intent-aware FILTER (T07 fix, upgraded): "appeal" questions keep
    #     only appeal-matching chunks (judged on section + opening text, so
    #     chunk_0002's orphaned trailing "Appeals" header doesn't qualify).
    #     Root cause was a Day-7 chunk-boundary bug: the appeals heading got
    #     appended to the end of the claims-FILING chunk, so the model saw
    #     filing steps "labeled" appeals. If nothing matches, keep all.
    if "appeal" in question.lower():
        appeal_chunks = [
            c for c in chunks
            if "appeal" in (c["section"] + " " + c["text"][:200]).lower()
        ]
        if appeal_chunks:
            chunks = appeal_chunks

    # --- de-duplicate ---
    # 1) identical chunk ids (can't happen in one query, but guards future multi-query)
    seen, unique_chunks = set(), []
    for c in chunks:
        if c["id"] not in seen:
            seen.add(c["id"])
            unique_chunks.append(c)
    # 2) cross-source dupes: drop DB-derived chunks when SQL already returned those plans
    if sql_rows:
        sql_plans = {str(r.get("plan_name", "")).lower() for r in sql_rows}
        unique_chunks = [
            c for c in unique_chunks
            if not (c["source"] == "coverage.db"
                    and any(p and p in c["text"].lower() for p in sql_plans))
        ]

    # --- merge into one context block ---
    lines = [f"QUESTION: {question}", f"ROUTE: {route}", ""]
    if sql_rows:
        lines.append("=== STRUCTURED FACTS (coverage.db) ===")
        lines += [f"  {row}" for row in sql_rows]
        lines.append("")
    if unique_chunks:
        lines.append("=== POLICY CONTEXT (vector search) ===")
        for c in unique_chunks:
            lines.append(f"  [{c['id']} | {c['section']} | d={c['distance']} | {c['source']}]")
            lines.append(f"  {c['text'][:200]}")
            lines.append("")
    if not sql_rows and not unique_chunks:
        lines.append("(no results from either path)")

    return {
        "question": question,
        "route": route,
        "sql_results": sql_rows,
        "chunks": unique_chunks,
        "context": "\n".join(lines),
    }

# --- quick test ---
if __name__ == "__main__":
    print("\n" + "=" * 60)
    for t in [
        "What's the deductible on the Silver plan?",     # structured
        "How do I appeal a denied claim?",               # both (per your classifier)
        "Is physical therapy covered under the Silver plan?",  # both
    ]:
        r = retrieve(t)
        print(r["context"])
        print("=" * 60)

# ---------------------------------------------------------------
# Step 5: test harness — 10 varied questions
# ---------------------------------------------------------------

TEST_QUESTIONS = [
    # -- mission's examples --
    ("T01", "what's my copay"),
    ("T02", "is maternity care covered on the Bronze plan"),
    ("T03", "status of claim C-2031"),
    # -- structured --
    ("T04", "What's the monthly premium for the Gold plan?"),
    ("T05", "Which plans are under $400 a month?"),
    ("T06", "What's the claim status for member M1001?"),
    # -- unstructured --
    ("T07", "How do I appeal a denied claim?"),
    ("T08", "What services are not covered?"),
    ("T09", "How do I enroll in a health plan?"),
    # -- mixed: needs BOTH sources --
    ("T10", "What's the Silver plan's deductible and how do I file a claim against it?"),
]

def run_harness():
    for tid, q in TEST_QUESTIONS:
        r = retrieve(q)
        print("=" * 70)
        print(f"{tid} | ROUTE: {r['route']} | sql_rows: {len(r['sql_results'])} "
              f"| chunks: {len(r['chunks'])}")
        print(f"Q: {q}")
        if r["sql_results"]:
            print("  SQL:", r["sql_results"][:2])
        for c in r["chunks"][:3]:
            print(f"  VEC: {c['id']} d={c['distance']} [{c['section']}] {c['text'][:60]}...")
    print("=" * 70)

if __name__ == "__main__":
    run_harness()