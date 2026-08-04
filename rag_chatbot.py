# from openai import OpenAI

# client = OpenAI(
#     base_url="http://localhost:11434/v1",
#     api_key="ollama",          # dummy — local server ignores it
# )

# resp = client.chat.completions.create(
#     model="llama3.2:3b",
#     messages=[{"role": "user", "content": "Say 'RAG pipeline online' and nothing else."}],
# )
# print(resp.choices[0].message.content)


# """Day 11 — RAG chatbot: generate_answer + retrieve_and_answer."""
# from openai import OpenAI

# client = OpenAI(
#     base_url="http://localhost:11434/v1",
#     api_key="ollama",
# )

# MODEL = "llama3.2:3b"   # or "qwen2.5-coder:3b" if you didn't pull llama

# GROUNDING_PROMPT = """Answer using ONLY the context below.
# If the answer isn't in the context, say you don't know and suggest the member contact support.
# This is not medical advice.

# Context: {context}

# Question: {question}"""

# def generate_answer(question: str, context: str) -> str:
#     """Send question + retrieved context to the LLM with a grounding prompt."""
#     prompt = GROUNDING_PROMPT.format(context=context, question=question)
#     resp = client.chat.completions.create(
#         model=MODEL,
#         messages=[{"role": "user", "content": prompt}],
#         temperature=0.2,        # low = factual, less creative wandering
#     )
#     return resp.choices[0].message.content.strip()

# # --- test with hand-made context (retrieval plugs in next step) ---
# if __name__ == "__main__":
#     ctx = ("Silver HMO (plan ID P102): $300/month premium, $1500 annual deductible, "
#            "20% copay, coverage type: HMO, network tier: Silver.")
#     print("TEST 1 (answer in context):")
#     print(generate_answer("What is the Silver plan's deductible?", ctx))
#     print("\nTEST 2 (answer NOT in context — should refuse):")
#     print(generate_answer("Is acupuncture covered?", ctx))

# #     from retrieval_engine import retrieve    # Day 10's engine plugs straight in

# # def retrieve_and_answer(question: str) -> dict:
# #     """Full RAG pipeline: retrieve evidence -> grounded LLM answer."""
# #     retrieval = retrieve(question)                  # Day 10: route, search, merge
# #     answer = generate_answer(question, retrieval["context"])
# #     return {
# #         "question": question,
# #         "route": retrieval["route"],
# #         "n_sql": len(retrieval["sql_results"]),
# #         "n_chunks": len(retrieval["chunks"]),
# #         "answer": answer,
# #     }

# # # --- end-to-end test ---
# # if __name__ == "__main__":
# #     for q in [
# #         "What's the deductible on the Silver plan?",   # SQL-backed
# #         "How do I appeal a denied claim?",             # vector-backed
# #         "Is acupuncture covered?",                     # not in KB -> should refuse
# #     ]:
# #         r = retrieve_and_answer(q)
# #         print(f"\nQ: {q}   [route: {r['route']} | sql: {r['n_sql']} | chunks: {r['n_chunks']}]")
# #         print(f"A: {r['answer']}")


# """Day 11 — RAG chatbot: generate_answer + retrieve_and_answer."""
# from openai import OpenAI
# from retrieval_engine import retrieve    # Day 10's engine

# client = OpenAI(
#     base_url="http://localhost:11434/v1",
#     api_key="ollama",          # dummy — local server ignores it
# )

# MODEL = "llama3.2:3b"   # or "qwen2.5-coder:3b"

# GROUNDING_PROMPT = """Answer using ONLY the context below.
# If the answer isn't in the context, say you don't know and suggest the member contact support.
# This is not medical advice.

# Context: {context}

# Question: {question}"""

# DISTANCE_THRESHOLD = 1.45   # Day 10 finding: beyond this, chunks are noise


# def generate_answer(question: str, context: str) -> str:
#     """Send question + retrieved context to the LLM with a grounding prompt."""
#     prompt = GROUNDING_PROMPT.format(context=context, question=question)
#     resp = client.chat.completions.create(
#         model=MODEL,
#         messages=[{"role": "user", "content": prompt}],
#         temperature=0.2,
#     )
#     return resp.choices[0].message.content.strip()


# def _context_for_llm(retrieval: dict) -> str:
#     """Build clean, generation-friendly context (no debug scaffolding)."""
#     # Trim the noise tail per the Day 10 distance threshold, keep at least one chunk
#     chunks = [c for c in retrieval["chunks"] if c["distance"] < DISTANCE_THRESHOLD]
#     if not chunks and retrieval["chunks"]:
#         chunks = retrieval["chunks"][:1]

#     parts = []
#     if retrieval["sql_results"]:
#         parts.append("Database facts:")
#         parts += [f"- {row}" for row in retrieval["sql_results"]]
#     for c in chunks:
#         parts.append(f"[source: {c['source']}]\n{c['text']}")
#     return "\n\n".join(parts) if parts else "(no relevant information found)"


# def retrieve_and_answer(question: str) -> dict:
#     """Full RAG pipeline: retrieve evidence -> grounded LLM answer."""
#     retrieval = retrieve(question)
#     answer = generate_answer(question, _context_for_llm(retrieval))
#     return {
#         "question": question,
#         "route": retrieval["route"],
#         "n_sql": len(retrieval["sql_results"]),
#         "n_chunks": len(retrieval["chunks"]),
#         "answer": answer,
#     }


# # --- end-to-end test ---
# if __name__ == "__main__":
#     for q in [
#         "What's the deductible on the Silver plan?",   # SQL-backed
#         "How do I appeal a denied claim?",             # vector-backed
#         "Is acupuncture covered?",                     # not in KB -> should refuse
#     ]:
#         r = retrieve_and_answer(q)
#         print(f"\nQ: {q}   [route: {r['route']} | sql: {r['n_sql']} | chunks: {r['n_chunks']}]")
#         print(f"A: {r['answer']}")



# # ---------------------------------------------------------------
# # Step 5: run the Day 10 harness questions through the full pipeline
# # ---------------------------------------------------------------
# from retrieval_engine import TEST_QUESTIONS   # the same 10 from Day 10

# def run_rag_harness(out_path: str = "rag_qa_results.md"):
#     lines = [
#         "# RAG Q&A Results — Day 11",
#         "",
#         "**Pipeline:** question → retrieve() (Day 10 hybrid engine) → distance-trimmed,",
#         "generation-friendly context → llama3.2:3b via local Ollama (OpenAI-compatible",
#         "API) → grounded answer. Temperature 0.2. Fully local, $0.",
#         "",
#         "**Grounding prompt:** answers only from context; refuse + refer to support",
#         "when absent; not medical advice.",
#         "",
#         "---",
#         "",
#     ]
#     for tid, q in TEST_QUESTIONS:
#         r = retrieve_and_answer(q)
#         print(f"{tid} [{r['route']}] {q}")
#         print(f"   -> {r['answer'][:100]}...\n")
#         lines += [
#             f"## {tid}: {q}",
#             f"- **Route:** {r['route']} · **SQL rows:** {r['n_sql']} · **Chunks:** {r['n_chunks']}",
#             f"- **Answer:** {r['answer']}",
#             "",
#         ]
#     with open(out_path, "w", encoding="utf-8") as f:
#         f.write("\n".join(lines))
#     print(f"Wrote {out_path}")

# if __name__ == "__main__":
#     run_rag_harness()

"""Day 11 — RAG chatbot: generate_answer + retrieve_and_answer.

Day 17 patch: (1) GROUNDING_PROMPT upgraded to Day-12's Variant E (the 20/20
winner — few-shot, warmth-by-example, mandatory disclaimer) plus an explicit
no-invented-numbers rule; (2) retrieve_and_answer now returns "context" (for
the API's numeric-grounding hallucination guard) and "sources" (chunk
provenance for API consumers).
"""
from openai import OpenAI
from retrieval_engine import retrieve, TEST_QUESTIONS   # Day 10's engine + harness questions
from response_cards import build_cards   # Day 19: Pydantic-validated rich cards

client = OpenAI(
    base_url="http://localhost:11434/v1",
    api_key="ollama",          # dummy — local server ignores it
)

MODEL = "llama3.2:3b"   # or "qwen2.5-coder:3b"

# Day 12 Variant E — the 20/20 hybrid, deployed as promised in prompt_variants.md,
# plus one hardening line (never state numbers absent from the context).
GROUNDING_PROMPT = """You are a helpful benefits information assistant. Silently check
which plan the question concerns and whether the answer is explicitly in the
context — then reply in the style of these examples. Answer using ONLY the
context. Every answer ends with the standard disclaimer line. Never state a
dollar amount or percentage that does not appear in the context.

Example 1 — coverage fact:
Context: Gold PPO (plan ID P101): $500/month premium, $2000 annual deductible, 10% copay.
Question: What's the Gold plan's deductible?
Answer: The Gold PPO (plan ID P101) has a $2,000 annual deductible.
— Benefits information only, not medical advice.

Example 2 — worried member, answer IS in context:
Context: Bronze HMO (plan ID P103): $150/month premium, $1000 annual deductible.
Question: I'm stressed about money — how much is the Bronze plan monthly?
Answer: I understand cost worries can be stressful. The Bronze HMO (plan ID
P103) has a monthly premium of $150.
— Benefits information only, not medical advice.

Example 3 — information NOT in context:
Context: Bronze HMO (plan ID P103): $150/month premium, $1000 annual deductible.
Question: Does the Bronze plan cover dental cleanings?
Answer: I don't have that information in my records. Please contact Member
Support for details about dental coverage.
— Benefits information only, not medical advice.

Example 4 — medical question:
Context: Silver HMO (plan ID P102): $300/month premium, 20% copay.
Question: Is physical therapy the right treatment for my knee?
Answer: I can't advise on medical treatment. Please consult your licensed
healthcare provider about what's right for your knee — I can tell you what
your plan covers if that would help.
— Benefits information only, not medical advice.

Now answer the real question in the same style. Never repeat, quote, or
reference the examples above or their plans and numbers — they are style
demonstrations only. Never begin your answer with the word "Context". Use
ONLY the Context section below.

Context:
{context}

Question: {question}

Answer:"""

DISTANCE_THRESHOLD = 1.45   # Day 10 finding: beyond this, chunks are noise


def generate_answer(question: str, context: str) -> str:
    """Send question + retrieved context to the LLM with a grounding prompt."""
    prompt = GROUNDING_PROMPT.format(context=context, question=question)
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
    )
    return resp.choices[0].message.content.strip()


MIN_CHUNK_CHARS = 80   # Day 17: chunk_0009 was a 45-char title with no body —
                       # semantically perfect, informationally empty. Drop such
                       # "empty promise" chunks before they anchor an answer.


def _trimmed_chunks(retrieval: dict) -> list:
    """Distance-trim per the Day 10 threshold, keeping at least one chunk.
    Also drops informationally-empty chunks (titles without bodies)."""
    chunks = [
        c for c in retrieval["chunks"]
        if c["distance"] < DISTANCE_THRESHOLD and len(c["text"].strip()) >= MIN_CHUNK_CHARS
    ]
    if not chunks and retrieval["chunks"]:
        chunks = retrieval["chunks"][:1]
    return chunks


def _context_for_llm(retrieval: dict) -> str:
    """Build clean, generation-friendly context (no debug scaffolding)."""
    chunks = _trimmed_chunks(retrieval)

    parts = []
    if retrieval["sql_results"]:
        parts.append("Database facts:")
        parts += [f"- {row}" for row in retrieval["sql_results"]]
    for c in chunks:
        parts.append(f"[source: {c['source']}]\n{c['text']}")
    return "\n\n".join(parts) if parts else "(no relevant information found)"


def _citations(retrieval: dict) -> list[dict]:
    """Day 19: which chunks actually entered the context — tracked, not
    model-claimed. A citation the model writes can be hallucinated; a
    citation the pipeline records cannot."""
    cites = [
        {"id": c["id"], "section": c["section"], "source": c["source"]}
        for c in _trimmed_chunks(retrieval)
    ]
    if retrieval["sql_results"]:                     # DB facts are sources too
        cites.append({"id": f"coverage.db ({len(retrieval['sql_results'])} rows)",
                      "section": "database", "source": "coverage.db"})
    return cites


import re as _re

CLAIM_ID_RE = _re.compile(r"\bC-?\d{3,}\b", _re.IGNORECASE)
REFUSAL_DISTANCE = 1.30   # if best chunk is farther than this AND no SQL rows -> corpus has nothing relevant
HONEST_REFUSAL = ("I don't have that information in my records. Please contact "
                  "Member Support for help with this.\n"
                  "— Benefits information only, not medical advice.")


def _apply_gates(question: str, retrieval: dict) -> str | None:
    """Run the three structural gates. Returns the gate name if one fires
    (caller must refuse), else None. Gates are retrieval-based, so they run
    BEFORE any generation — streaming or not."""
    # Gate 1: claim-ID questions must be backed by a DB row
    if CLAIM_ID_RE.search(question) and not retrieval["sql_results"]:
        return "claim_not_found"

    # Gate 2: nothing relevant retrieved -> honest refusal, no LLM call
    best = min((c["distance"] for c in retrieval["chunks"]), default=99.0)
    if not retrieval["sql_results"] and best > REFUSAL_DISTANCE:
        return "no_relevant_context"

    # Gate 3: "is X covered" demands X actually appear in retrieved context
    m = (_re.search(r"\bis\s+(.+?)\s+covered\b", question, _re.IGNORECASE)
         or _re.search(r"\bcover(?:s)?\s+([a-z][a-z\s-]{2,40}?)[\?\.]?$", question, _re.IGNORECASE))
    if m:
        subject_words = [w for w in _re.findall(r"[a-z-]{4,}", m.group(1).lower())
                         if w not in ("plan", "plans", "care", "under", "with", "this", "that")]
        if subject_words:
            ctx_probe = " ".join(
                c["text"].lower() for c in retrieval["chunks"]
            ) + " " + " ".join(str(r).lower() for r in retrieval["sql_results"])
            if not any(w in ctx_probe for w in subject_words):
                return "subject_not_in_context"
    return None


def stream_answer(question: str):
    """Day 18: streaming RAG pipeline. Yields event dicts:
      {"kind": "meta", "sources": [...], "context": str, "gate": str|None}
      {"kind": "token", "text": str}          (one per SDK chunk)
      {"kind": "final", "answer": str}        (the accumulated full answer)

    Gates run pre-stream (retrieval-based). The numeric guard CANNOT run
    pre-stream — tokens leave before the answer exists — so the API applies
    it post-hoc on the accumulated answer (see main.py). That ordering is
    the fundamental streaming trade-off: latency vs pre-validation.
    """
    retrieval = retrieve(question)
    gate = _apply_gates(question, retrieval)

    if gate:
        yield {"kind": "meta", "sources": [], "context": "", "gate": gate,
               "citations": [], "cards": []}
        yield {"kind": "token", "text": HONEST_REFUSAL}
        yield {"kind": "final", "answer": HONEST_REFUSAL}
        return

    context = _context_for_llm(retrieval)
    sources = [c["source"] for c in _trimmed_chunks(retrieval)]
    yield {"kind": "meta", "sources": sources, "context": context, "gate": None,
           "citations": _citations(retrieval),
           "cards": build_cards(retrieval["sql_results"])}

    prompt = GROUNDING_PROMPT.format(context=context, question=question)
    stream = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
        stream=True,                       # the LLM SDK's streaming mode
    )
    full = []
    for chunk in stream:
        token = chunk.choices[0].delta.content
        if token:                          # first/last chunks can be empty
            full.append(token)
            yield {"kind": "token", "text": token}
    yield {"kind": "final", "answer": "".join(full).strip()}


def retrieve_and_answer(question: str) -> dict:
    """Full RAG pipeline: retrieve evidence -> grounded LLM answer.

    Two structural gates (Day 17) run BEFORE the LLM — the model never gets
    the chance to improvise on these failure classes:
    1. Claim-ID gate (T03): a claim ID with zero SQL rows means the claim
       doesn't exist — refuse; never let the LLM invent a status.
    2. Relevance gate (T09): no SQL rows and only far-away chunks means the
       corpus has nothing on this topic — refuse; never answer from world
       knowledge (e.g. enrollment/HealthCare.gov).
    """
    retrieval = retrieve(question)

    gate = _apply_gates(question, retrieval)
    if gate:
        return {
            "question": question, "route": retrieval["route"],
            "n_sql": len(retrieval["sql_results"]),
            "n_chunks": len(retrieval["chunks"]),
            "answer": HONEST_REFUSAL, "context": "",
            "sources": [], "citations": [], "cards": [], "gate": gate,
        }

    context = _context_for_llm(retrieval)
    answer = generate_answer(question, context)
    return {
        "question": question,
        "route": retrieval["route"],
        "n_sql": len(retrieval["sql_results"]),
        "n_chunks": len(retrieval["chunks"]),
        "answer": answer,
        "context": context,                                     # for the API's hallucination guard
        "sources": [c["source"] for c in _trimmed_chunks(retrieval)],  # provenance for API consumers
        "citations": _citations(retrieval),   # Day 19: chunk-ID provenance
        "cards": build_cards(retrieval["sql_results"]),  # Day 19: rich cards
    }


# ---------------------------------------------------------------
# Step 5: run the Day 10 harness questions through the full pipeline
# ---------------------------------------------------------------
def run_rag_harness(out_path: str = "rag_qa_results.md"):
    lines = [
        "# RAG Q&A Results — Day 11",
        "",
        "**Pipeline:** question → retrieve() (Day 10 hybrid engine) → distance-trimmed,",
        "generation-friendly context → llama3.2:3b via local Ollama (OpenAI-compatible",
        "API) → grounded answer. Temperature 0.2. Fully local, $0.",
        "",
        "**Grounding prompt:** answers only from context; refuse + refer to support",
        "when absent; not medical advice.",
        "",
        "---",
        "",
    ]
    for tid, q in TEST_QUESTIONS:
        r = retrieve_and_answer(q)
        print(f"{tid} [{r['route']}] {q}")
        print(f"   -> {r['answer'][:100]}...\n")
        lines += [
            f"## {tid}: {q}",
            f"- **Route:** {r['route']} · **SQL rows:** {r['n_sql']} · **Chunks:** {r['n_chunks']}",
            f"- **Answer:** {r['answer']}",
            "",
        ]
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"Wrote {out_path}")




# ---------------------------------------------------------------
# Step 7: streaming test — watch tokens arrive live
# ---------------------------------------------------------------
def generate_answer_streaming(question: str, context: str) -> str:
    """Same grounded call, but tokens print as they arrive."""
    prompt = GROUNDING_PROMPT.format(context=context, question=question)
    stream = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
        stream=True,                       # <- the whole trick
    )
    full = []
    for chunk in stream:
        token = chunk.choices[0].delta.content
        if token:                          # first/last chunks can be empty
            print(token, end="", flush=True)   # flush = appear immediately
            full.append(token)
    print()
    return "".join(full)


def streaming_demo():
    from retrieval_engine import retrieve
    q = "How do I appeal a denied claim?"
    retrieval = retrieve(q)
    print(f"Q: {q}\nA: ", end="", flush=True)
    generate_answer_streaming(q, _context_for_llm(retrieval))


if __name__ == "__main__":
    # streaming_demo() # uncomment to see streaming in action
    run_rag_harness()