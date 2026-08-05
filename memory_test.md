# Conversation Memory Test — Day 20

**Stack:** SQLite `conversations` table (session_id, role, content, timestamp; id
autoincrement for ordering, role CHECK, session index) + `conversation_summaries`
(summary, covered_through_id — turns leave the PROMPT, never the DB) →
last-10 turns + remembered plan_id injected server-side (injection v4) →
tiktoken (cl100k proxy, lazy-loaded w/ chars÷4 fallback) → past ~2000 tokens the
oldest half collapses via ONE strict LLM call.

## Plan-memory gauntlet (16 turns, session e6654946)
| # | Turn | Result |
|---|------|--------|
| 1 | What's my deductible? | ✅ $2,000 Gold — server-remembered plan, hist_tokens=0 |
| 2 | And the copay? | ✅ 10% — pronoun-only follow-up rode history (37 tokens) |
| 3 | What's my monthly premium? | ✅ $500 Gold (P101) |
| 4 | How do I appeal a denied claim? | ✅ 180 days, grounded |
| 5 | Status of claim C1001? | ✅ Pending card, $250, 2023-04-01 |
| 6 | And claim C1002? | ⚠️ refused — **finding #1** (below) |
| 7 | Which plans are under $400? | ✅ Bronze + Silver, 2 cards, no Gold hijack |
| 8 | What plans do you offer? | ✅ catalog, injection v4 skipped |
| 9 | Compare the plans in a table | ✅ 3-row table + 3 cards |
| 10 | How does enrollment work? | ✅ 4-step, chunk_0013 |
| 11 | Silver plan's deductible? | ✅ $1,500 — did NOT overwrite my plan |
| 12 | status of claim C-9999 | ✅ gated refusal, alone |
| 13 | Appeal documents? | ✅ grounded |
| 14 | How long do appeals take? | 🛡️ **guard TRUE POSITIVE** — model invented "30-60 days" (in no chunk); blocked (finding #2) |
| 15 | Are X-rays covered on my plan? | ✅ 10% coinsurance, 5 sources |
| 16 | **So what's my deductible again?** | ✅ **$2,000 Gold (P101)** — plan memory across 15+ turns PROVEN (turns=32, hist_tokens=805, plan=P101) |

## Token budget lifecycle (extension turns, same session)
```
turns=50  hist_tokens=1764  ctx_tokens=543  summarized=False  plan=P101
turns=52  hist_tokens=1884  ctx_tokens=547  summarized=False  plan=P101
turns=54  hist_tokens=2000  ctx_tokens=521  summarized=False  plan=P101  ← at the line (trigger is >2000)
turns=56  hist_tokens=2142  ctx_tokens=760  summarized=True   plan=P101  ← ttft 103,442ms
turns=58  hist_tokens=1668  ctx_tokens=792  summarized=False  plan=P101  ← −474 tokens
```
- ctx_tokens stays ~300-800 throughout — last-10 slicing keeps the prompt lean
  even as stored history grows.
- Summarization turn tax: ttft ~103s (the extra LLM call runs BEFORE the
  member's answer starts). Paid once per ~2000 tokens, on CPU.
- [x] Post-summarization memory check: "So what's my deductible again?" at
  turns=60 (after summarized=True) → $2,000 Gold PPO ✓ — plan memory
  SURVIVED its own compression (hist 1705, ctx 690, plan=P101)

## Summary audit (what the 3B model wrote as permanent context)
covered_through_id=41. Fact-check vs DB/chunks: Gold $2,000/10%/$500 ✓ ·
Silver $1,500/20% ✓ · under-$400 = Bronze+Silver ✓ · 180-day appeals ✓ ·
**inventions: none** — the Variant-E-strict summarizer prompt held.
Cosmetic: instruction echo ("Here is a summary…") persists as dead tokens.

## Mission checklist (steps → evidence)
- [x] Step 1 — conversations table (session_id, role, content, timestamp): created,
      role CHECK verified, smoke-tested round-trip
- [x] Step 2 — both turns saved on every /chat call: DB query showed alternating
      user/assistant rows for the live uuid4 session; survives uvicorn restart
- [x] Step 3 — last 10 turns + remembered plan_id in the prompt: "And the copay?"
      answered from history; injection v4 server-side
- [x] Step 4 — tiktoken check, >~2000 → oldest half summarized in ONE LLM call,
      turns replaced in the PROMPT (raw rows preserved for audit)
- [x] Step 5 — 15+ turn test: plan set early, re-asked at turn 16 → Gold $2,000;
      re-asked at turn 60 post-summarization → still Gold $2,000; logged here
- [x] Step 6 — token counts logged per request (hist_tokens/ctx_tokens); before
      2000 → after 2142+summarized=True → 1668 captured; summary audited

Known limitation: the plan was specified via the sidebar (plan_id field each
request), so the message-mention memory path (PLAN_MENTIONS) is shadowed in
this test — implemented but not exercised live.

## Findings (Day 20)
1. **Memory outruns retrieval:** "And claim C1002?" is natural once the bot
   remembers — but claim-intent routing needs the literal keywords, found 0
   rows, and Gate 1 refused a claim that exists. Conversational ellipsis is a
   retrieval problem now. (Known limitation; intent routing upgrade deferred.)
2. **Guard true positive #3:** "How long do appeals take?" → model fabricated
   "30-60 days" — in no chunk, no row. numbers_grounded blocked it
   mid-conversation, with history in play. The corpus has no processing-time
   fact; the honest answer is a refusal, and that's what shipped.
3. **DB pollution (caught & fixed):** persisted user turns contained the
   client's [Member's plan: …] prefix — memory was recording decorated
   messages. Fix: injection moved server-side (v4); the DB stores what the
   member actually said; legacy tags stripped at read time.
4. **Summaries are a hallucination surface:** the summary is re-injected as
   truth forever, written by the same 3B model the guard polices. Mitigation:
   temperature 0.1 + stated-facts-only prompt + figures-verbatim rule + manual
   audit (passed). The guard also grounds against history, so summary-sourced
   figures stay repeatable without false positives (FP class #3, pre-empted).
5. **Memory has a turn tax:** the summarization call serializes in front of
   the member's answer (~103s ttft on CPU). Async summarization is the
   production path; synchronous is honest for a demo.