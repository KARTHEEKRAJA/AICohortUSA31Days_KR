# Rich Outputs Test — Day 19

**Stack:** stream_answer() tracks citations (chunk IDs, deterministic — never
model-claimed) + build_cards() (Pydantic-validated from SQL rows) → SSE `done`
event → Streamlit: bordered cards (st.container/st.columns/st.metric) +
"Policy sources" expander under each answer. Refusals ship nothing but the
refusal (guard zeroes cards + citations).

## Q1 — policy citations: How do I appeal a denied claim?
- [ ] Prose answer streams token-by-token, grounded (180 days), disclaimer present
- [ ] 📚 Policy sources expander: [1] chunk_0003 — claims · raw_text/claims_process.txt
- [ ] No cards (vector-only answer — no SQL rows, correctly nothing to card)

## Q2 — claim-status card: What's the claim status for member M1001?
- [ ] Prose answer grounded
- [ ] ClaimStatusCard ×2: ⏳ C1001 Pending $250.00 · ✅ C1002 Approved $1,200.00
- [ ] Dates trimmed to YYYY-MM-DD on cards
- [ ] 📚 Policy sources: coverage.db provenance

## Q3 — coverage-summary card: What's the Gold plan's deductible?
- [ ] Prose: $2,000 annual deductible, guard silent
- [ ] CoverageSummaryCard: Gold PPO · 🟢 Active · Deductible $2,000 · Copay 10%
- [ ] 📚 Policy sources: coverage.db (1 rows)

## Regression: status of claim C-9999
- [ ] Gated refusal — NO cards, NO citations, no expander

## Extended render coverage (proven during build)
- [x] Optional-field path: "under $400" → Template-3 rows → complete cards
      after full-row SELECT fix (was "—" placeholders)
- [x] Cards + citations survive rerun (session replay path)

## Markdown render probes (st.chat_message)
- [x] Lists: plan catalog renders as numbered list (streamed)
- [x] Tables: 3-plan comparison renders clean post-stream — required
      injection v3 ("compare" added to skip list; injected Gold had
      collapsed the comparison to one row)
- [x] Code blocks: probe widget renders fenced python with highlighting

## Findings (Day 19)
1. **Track citations, don't ask the model to cite** — a model-written citation
   is a hallucination surface; a pipeline-recorded one cannot lie.
2. **Guard false-positive class #2:** numbers echoed from the *question*
   ("under $400") are legitimate but weren't in context. Fix: ground against
   context + question. (Class #1 was identifiers, Day 18.)
3. **Rich outputs must obey the guard:** cards rode the done event past a
   fired guard — refusal prose above data-filled cards. A refused answer now
   ships nothing but the refusal.
4. **Structured data never rides the token stream** — a half-streamed table
   is garbage until its closing row. Cards arrive whole, post-stream,
   validated (Pydantic = the output validator, Day-13 philosophy on outputs).
5. **Injection bug #2:** "Compare the plans" inherited the sidebar's Gold
   plan — the comparison compared nothing. Context injection needs an
   explicit cross-plan/comparison skip list (v3), not just catalog words.