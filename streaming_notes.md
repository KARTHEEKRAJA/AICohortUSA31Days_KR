# Streaming Notes — Day 18

**Stack:** Streamlit (requests stream=True → iter_lines) ⇄ FastAPI
StreamingResponse (`media_type="text/event-stream"`) ⇄ stream_answer() in
rag_chatbot.py ⇄ llama3.2:3b via Ollama (OpenAI SDK, `stream=True`).
Event protocol: `data: {json}\n\n` lines — `start` → `token`* → optional
`guard` → `done` (status, sources, turn_count, ttft_ms, elapsed_ms).

## Typing UX — confirmed
- Pre-first-token indicator: "*Checking your coverage…* ▌" renders before
  the request resolves; replaced by the growing answer at token #1.
- Tokens append to an `st.empty()` placeholder with a ▌ cursor
  (`placeholder.markdown(answer + "▌")`); cursor drops on completion;
  a caption shows `first token X ms · total Y ms` per answer.
- Confirmed visibly mid-stream (screenshots): partial sentences with the
  cursor — e.g. "…submit an appeal request within 180▌".
- True SDK granularity verified over curl: sub-word chunks ("H"/"MO",
  "P"/"102") — the tokenizer's actual output, not simulated chunking.

## The numbers (measured, not estimated)

| Path | ttft | total | why |
|---|---|---|---|
| Gated refusal (fake claim C-9999) | **25–28 ms** | 26–29 ms | Gates are retrieval-based — no LLM call at all |
| Warm generation | **2,537–7,618 ms** | 9,872–21,232 ms | model resident; first tokens while the rest generates |
| Cold start (after restart) | 45,024–64,827 ms | 48,996–72,516 ms | model loading + prompt processing precede token #1 |

**Finding:** streaming hides *generation* latency, not *loading* latency.
Warm, the member reads at ~2.5s while 7–14 more seconds of generation
happen behind their reading speed. Cold, streaming only animates the last
few seconds. Perceived speed = when the first token lands, not the last.
Bonus: the structural gates are ~100–2,000× faster than any generated
answer — safety and speed turned out to be the same feature.

## Design decisions (the streaming trade-off)
1. **Step 1 shipped buffer-then-flush** (full pipeline + numeric guard
   validate the complete answer, then chunks flush): zero validation
   compromise, but fake streaming.
2. **Step 2 shipped true token streaming**, which forces the trade:
   - Gates 1–3 are retrieval-based → still run **pre-stream**. Gated
     refusals stream instantly (25 ms).
   - The numeric guard needs the full answer → became **post-hoc**: it
     validates the accumulated text after the last token and emits a
     `guard` SSE event; the UI **replaces** the streamed text with the
     refusal. Honest cost: the member may glimpse ungrounded content for
     a moment. Frequency reduced by the prompt; harm eliminated by the
     guard.

## The guard's double feature (both failure modes, one day)
- **Morning — false positive:** flagged "Silver HMO (plan ID P102)…
  $1,500" because `102` wasn't in context — the SQL row lacked plan_id.
  Fixed on both sides: identifier-aware regex
  (`(?<![A-Za-z\d])\d…(?![A-Za-z])` — P102/C1001/M1001 are names, not
  facts) + plan_id added to all plans SQL templates. Unit-tested (IDs
  pass, invented $25/phone numbers still caught).
- **Afternoon — TRUE positive:** flagged an appeals answer that began
  "Context: Gold PPO (plan ID P101): $500/month premium, $2000 annual
  deductible, 10% copay…" — the model had echoed **Variant E's Example 1
  verbatim** into a member-facing answer. Genuinely ungrounded; the guard
  replaced it with a refusal. Fix: anti-echo rule appended to the prompt
  ("never repeat the examples or their numbers; never begin with
  'Context'"). Verified stable across two subsequent runs (both: 180
  days, no echo, status=ok).
- Lesson: a validator that fires teaches you something either way — one
  firing refined its precision, the next proved its purpose.

## Outage drills (mid-stream error handling)
- **Scenario A — LLM down before the question:** Ollama killed →
  the graceful apology ("I'm having trouble answering right now…")
  **streams as a token** through the same SSE pipe. status=error logged,
  failure turn recorded. No crash, no traceback.
- **Scenario B — killed MID-STREAM:** Ollama stopped while tokens were
  typing. Observed behavior, preserved in one bubble:
  "To appeal a denied claim, submit your request in" + apology appended
  in-stream — partial text kept, failure caught at the exact token seam
  (ttft 5,712 ms, failed by 7,307 ms). No hang; the 90 s read-timeout was
  never needed. Recovery required no API restart (Day-16 pattern holds).
- Client timeout is split `(5, 90)`: 5 s to connect, 90 s max **between
  chunks** — a stall shows the partial answer + a stall warning rather
  than discarding everything.
- Cosmetic note (accepted): the mid-stream seam lacks a separator — the
  apology glues to the partial word. One-line polish available (prefix
  `\n\n⚠️` in the except path); deferred.

## Minor observations
- Injection note: "How do I appeal…" contains no plan word, so the
  selected plan is injected; one run opened with "Context indicates the
  question concerns the Gold PPO…" (scaffolding echo, known T10-class).
  The anti-echo prompt rule also suppresses this opener.
- One run embellished "as outlined in our member handbook" (no handbook
  chunk exists) — process-reference, not a fact claim; documented class.
- Run-to-run variance at temp 0.2 changes wording, not facts: two clean
  appeals runs differed in phrasing, matched on 180 days/letter/records.