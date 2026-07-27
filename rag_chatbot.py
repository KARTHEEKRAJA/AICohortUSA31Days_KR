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

"""Day 11 — RAG chatbot: generate_answer + retrieve_and_answer."""
from openai import OpenAI
from retrieval_engine import retrieve, TEST_QUESTIONS   # Day 10's engine + harness questions

client = OpenAI(
    base_url="http://localhost:11434/v1",
    api_key="ollama",          # dummy — local server ignores it
)

MODEL = "llama3.2:3b"   # or "qwen2.5-coder:3b"

GROUNDING_PROMPT = """Answer using ONLY the context below.
If the answer isn't in the context, say you don't know and suggest the member contact support.
This is not medical advice.

Context: {context}

Question: {question}"""

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


def _context_for_llm(retrieval: dict) -> str:
    """Build clean, generation-friendly context (no debug scaffolding)."""
    chunks = [c for c in retrieval["chunks"] if c["distance"] < DISTANCE_THRESHOLD]
    if not chunks and retrieval["chunks"]:
        chunks = retrieval["chunks"][:1]

    parts = []
    if retrieval["sql_results"]:
        parts.append("Database facts:")
        parts += [f"- {row}" for row in retrieval["sql_results"]]
    for c in chunks:
        parts.append(f"[source: {c['source']}]\n{c['text']}")
    return "\n\n".join(parts) if parts else "(no relevant information found)"


def retrieve_and_answer(question: str) -> dict:
    """Full RAG pipeline: retrieve evidence -> grounded LLM answer."""
    retrieval = retrieve(question)
    answer = generate_answer(question, _context_for_llm(retrieval))
    return {
        "question": question,
        "route": retrieval["route"],
        "n_sql": len(retrieval["sql_results"]),
        "n_chunks": len(retrieval["chunks"]),
        "answer": answer,
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
