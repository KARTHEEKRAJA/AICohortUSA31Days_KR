# Backend Chat Test — Day 16

**Setup:** FastAPI + uvicorn (reload mode) serving POST /chat and
GET /history/{session_id}. Orchestration per request: Day-10 retrieve() →
clean context → Day-12 Variant E grounding prompt → Day-11 LLM (llama3.2:3b
via local Ollama). Session store: in-memory dict keyed by session_id.
Validation: Pydantic request models — member_id must match ^M\d{4}$
(invalid IDs rejected 422 before handler code runs).

## 3-message session test (session_id: demo1)

| # | Message | Answer (summary) | turn_count | elapsed_ms |
|---|---------|------------------|-----------|-----------|
| 1 | What plans do you offer? | "I don't know. Suggest contacting our support team…" (see Finding 5) | 2 | 9609 |
| 2 | What is the copay on the Silver plan? | "The copay percentage for the Silver HMO plan is 20%." | 4 | 18224 |
| 3 | How do I appeal a denied claim? | "…include the denial letter and any supporting medical records within 180 days." | 6 | 14710 |

**GET /history/demo1** returned all 6 turns in order with member_id,
created_at, per-turn timestamps, and per-answer elapsed_ms:

```json
{"session_id":"demo1","member_id":"M1001","created_at":"2026-08-01T13:39:13.473536+00:00","turn_count":6,"turns":[{"role":"user","content":"What plans do you offer?","ts":"2026-08-01T13:39:13.473536+00:00"},{"role":"assistant","content":"I don't know. Suggest contacting our support team for more information on available health plans.","ts":"2026-08-01T13:39:23.083274+00:00","elapsed_ms":9609},{"role":"user","content":"What is the copay on the Silver plan?","ts":"2026-08-01T13:39:29.077904+00:00"},{"role":"assistant","content":"The copay percentage for the Silver HMO plan is 20%.","ts":"2026-08-01T13:39:47.302572+00:00","elapsed_ms":18224},{"role":"user","content":"How do I appeal a denied claim?","ts":"2026-08-01T13:39:51.461875+00:00"},{"role":"assistant","content":"To appeal a denied claim, you must include the denial letter and any supporting medical records within 180 days of the denial.","ts":"2026-08-01T13:40:06.173241+00:00","elapsed_ms":14710}]}
```

## Verified behaviors

- Session continuity: turn_count climbed 2 → 4 → 6 across one session_id.
- Session isolation: parallel sessions (s10, s99) held separate histories.
- Grounded answers over HTTP identical to the local pipeline (Silver $300,
  Gold $500, appeals-180-days all correct; honest refusals on maternity
  and medical-advice questions).
- Input validation at the boundary: member_id "bob" → 422 with the
  ^M\d{4}$ pattern error — malformed requests never reach the pipeline.
- 404 semantics: /history/nope → {"detail": "session 'nope' not found"}.

## Timing observations

- Cold start (first request after boot): ~33s (embedding model + LLM load).
- Warm requests: ~5–12s typical on CPU-only llama3.2:3b.
- Server reload mid-day reproduced the cold spike (~24s) — timings logged
  per answer in session turns.

## Findings (honest)

1. **Store remembers; model doesn't read it yet.** "And the deductible?"
   after a Silver question answered with all three plans — history is
   captured but not fed to the LLM. Fix is small (prepend recent turns to
   the prompt); deferred by design today.
2. **In-memory trade-off observed live:** a --reload restart wiped
   sessions mid-test. Documented limitation; SQLite is the drop-in
   persistence path.
3. **Known T06 carries over:** claim C1001 refuses over HTTP for the same
   Day-10 root cause (SQL template lacks member_id). Consistent, not new.
4. Small talk ("Hello") gets an awkward grounded refusal — the RAG prompt
   has no greeting path (Day-13's tool bot handles this better).
5. **Catalog questions retrieve weakly.** "What plans do you offer?" was
   refused — the corpus has per-plan chunks but no plan-overview chunk, so
   discovery-style questions match nothing strongly. Fix: add one summary
   chunk enumerating the catalog.

   ## Error handling & recovery (session err1)

Simulated a live LLM outage: killed Ollama mid-service, then restored it.
The same session captured the full arc:

| Phase | Question | Answer | status log |
|---|---|---|---|
| Healthy | What is the Gold premium? | "$500" ✓ | status=ok elapsed_ms=24465 |
| Ollama DOWN | What is the Silver deductible? | "I'm having trouble answering right now. Please try again in a moment, or contact Member Support." | ERROR APIConnectionError · status=error elapsed_ms=13626 |
| Restored | What is the Silver deductible? | "$1,500" ✓ | status=ok elapsed_ms=17529 |

**Design choice:** graceful degradation over a raw 500 — the member receives a
polite retry message (HTTP 200), the failure is logged server-side
(`ERROR pipeline failure ... APIConnectionError`), and the failure turn is
recorded in session history for audit. The API needed no restart to recover.
Day-13 containment philosophy at the HTTP layer: the system stays correct
even when its components aren't.