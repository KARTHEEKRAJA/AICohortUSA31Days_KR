# Frontend Test Notes — Day 17 (Before Fix)

**Stack:** Streamlit chat UI (app.py) → POST /chat (FastAPI, Day 16) →
retrieve() (Day 10) → Variant E grounding (Day 12, deployed today) →
llama3.2:3b via Ollama. Sessions: uuid4 in st.session_state, one backend
session per browser session.

## What was built
- Chat UI: st.chat_message / st.chat_input, spinner while thinking,
  friendly error states (backend down / HTTP error / timeout).
- uuid4 session_id generated once per browser session; every turn POSTs to
  /chat; full conversations land in the backend audit trail (verified:
  turn_count 10 via GET /history).
- Sidebar: plan selector from data/plans.csv (@st.cache_data) + New
  conversation (clears thread + mints fresh uuid — old session preserved
  server-side).
- Smart context injection: selected plan is prefixed to the question ONLY
  when the question names no plan — vague queries sharpened, cross-plan
  queries untouched.

## Findings (in discovery order)

1. **Streamlit rerun vs reload boundary.** st.session_state survives
   reruns (R, widget clicks) but a browser reload starts a new session with
   a new uuid. Old conversations persist server-side and could be
   rehydrated from GET /history — future enhancement.

2. **Context injection cuts both ways.** Plan-prefixing fixed vague
   questions (Silver selected + "What is the deductible?" → Silver-only
   $1,500) but broke cross-plan ones (Gold selected + Silver question →
   refusal). Fixed same-day: inject only when the question names no plan.
   Verified: Bronze selected, Gold and Silver questions both answered
   correctly.

3. **THE HEADLINE — suspected hallucination turned out to be my data
   contradicting itself.** "What is the copay on the Gold plan?" returned
   $25 primary / $50 specialist — which contradicted coverage.db's 10%.
   Built a triple-layer defense (Variant E redeployed with a
   no-invented-numbers rule; a numeric-grounding guard in the API that
   blocks answers containing figures absent from retrieved context; sources
   wired through the response). The guard kept passing the answer — and
   investigation proved it right: chunk_0000 (benefits.txt, Day 7) lists
   Gold PPO tiered copays ($25/$50/$10/$40 + 10% coinsurance for
   ER/imaging) while coverage.db carries a single copay_pct=10. Two
   systems of record disagree; hybrid retrieval routes different phrasings
   to different truths ("premium for Gold" → SQL; "copay on the Gold
   plan" → vector). The model was faithfully grounded all along.
   **Resolution path:** treat tiered copays as service copays and
   copay_pct as coinsurance (readings are compatible), or reconcile the
   sources — scheduled with the T06 SQL fix.

4. **Variant E is context-regime-dependent.** On Day 12's hand-made
   contexts it scored 20/20; on real weak retrieval its 3-answered:1-refused
   demonstration set leans it toward invention: T02 fabricated a maternity
   "not covered" (a confident negative — no numbers, so the guard can't
   catch this class), T09 answered enrollment from world knowledge with an
   invented phone number (guard-catchable). Hand-made-context evals
   overestimate prompts; eval on real retrieval.

5. **T07 precision note:** "How do I appeal" retrieved the claims-FILING
   chunk (form CF-100, 90 days) instead of the APPEALS chunk (180 days) —
   sibling-chunk conflation, not invention (verified: all details exist in
   chunk_0002).

6. ** Also: T03 asserted ** "the status of claim C-2031 is currently being 
   processed" for a claim that doesn't exist (SQL rows: 0) — a fabricated
   status wrapped in "according to our records," with real chunk numbers
   alongside. Confirms the guard-blind class: confident non-numeric claims.
   Next-layer defense (future): claim-ID questions must route to SQL and
   refuse when no row returns.

## Defenses now live
- Variant E grounding prompt (disclaimers restored on every answer) with
  explicit no-invented-numbers rule.
- numbers_grounded() guard in /chat: any answer containing figures not
  present in retrieved context → honest refusal + WARNING log
  (status=ungrounded_numbers). Unit-tested incl. substring edge (25 vs 250)
  and phone numbers.
- sources[] now returned per answer for provenance.

## Resolutions (same day — evening hardening session)

All findings above were root-caused and fixed the same day. Final harness:
10/10 behaviorally correct (8 clean, 2 minor generation quirks), zero
hallucinations, zero fabricated verdicts.

| Issue | Root cause | Fix | Verified |
|---|---|---|---|
| T03 invented claim status | Claim ID + zero SQL rows → model improvised | Gate 1: claim-ID questions with no DB row → structural refusal (LLM never called) | ✓ refusal |
| T02 coverage coin-flip (3 verdicts / 3 runs) | Weak context + yes/no question, no numbers → guard-blind | Gate 3: "is X covered" requires X present in retrieved context, else refusal | ✓ refusal |
| T09 HealthCare.gov + invented phone | Corpus gap: only a 45-char title (chunk_0009) + a filled sample form on enrollment | Data repair: authored chunk_0013 (enrollment instructions) via add_kb_chunks.py (jsonl + Chroma, idempotent) + min-info chunk drop (<80 chars) | ✓ grounded 4-step answer |
| T07 filing≠appeals | Day-7 chunk-boundary bug: "Appeals" header orphaned onto the END of the filing chunk | Intent filter: "appeal" questions keep only chunks matching on section/opening text — the orphaned trailing header can't qualify | ✓ 180-days answer, chunks: 1 |
| T06 M1001 refusal (7 days old) | Day-10 SQL template omitted member_id column | Template fixed + new claim-by-ID template (also makes "status of claim C1001" answerable) | ✓ answers (one-row summary quirk noted) |
| T05 incomplete comparison | (SQL was correct — generation omission) | Resolved alongside; both plans now listed | ✓ Bronze + Silver |
| Day-16 finding #5 (catalog) | No plan-overview chunk | chunk_0014 authored + embedded | ✓ bonus close |

## Defense stack (final state)
1. Variant E grounding prompt + no-invented-numbers rule (disclaimers 10/10)
2. Gate 1 — claim-ID must be DB-backed
3. Gate 2 — relevance gate (no SQL + best distance > 1.30 → refuse)
4. Gate 3 — coverage-subject presence check
5. Min-info chunk drop (titles without bodies)
6. numbers_grounded() API guard (word-boundary set comparison, unit-tested)
7. sources[] provenance on every answer

## Known minor quirks (documented, accepted)
- T06: model summarizes 1 of 2 delivered claim rows (3B data-reading limit)
- T04: "(plan ID not specified)" aside; T10: context-scaffolding echo
- Data discrepancy: coverage.db copay_pct=10 vs chunk_0000 tiered copays
  ($25/$50/$10/$40 + 10% coinsurance) — compatible readings (service copays
  vs coinsurance); reconciliation scheduled.


  

  # Frontend Test Notes — Day 17 (After Fix)

**Stack:** Streamlit chat UI (app.py) → POST /chat (FastAPI, Day 16) →
retrieve() (Day 10) → Variant E grounding (Day 12, deployed today) →
llama3.2:3b via Ollama. Sessions: uuid4 in st.session_state, one backend
session per browser session.

## What was built
- Chat UI: st.chat_message / st.chat_input, spinner while thinking,
  friendly error states (backend down / HTTP error / timeout).
- uuid4 session_id generated once per browser session; every turn POSTs to
  /chat; full conversations land in the backend audit trail (verified:
  turn_count 10 via GET /history).
- Sidebar: plan selector from data/plans.csv (@st.cache_data) + New
  conversation (clears thread + mints fresh uuid — old session preserved
  server-side).
- Smart context injection (v2): selected plan is prefixed to the question
  ONLY when the question names no plan AND is not a catalog/discovery
  question — vague queries sharpened, cross-plan and "what plans do you
  offer" queries untouched.

## Findings (in discovery order)

1. **Streamlit rerun vs reload boundary.** st.session_state survives
   reruns (R, widget clicks) but a browser reload starts a new session with
   a new uuid. Old conversations persist server-side and could be
   rehydrated from GET /history — future enhancement.

2. **Context injection cuts both ways.** Plan-prefixing fixed vague
   questions (Silver selected + "What is the deductible?" → Silver-only
   $1,500) but broke cross-plan ones (Gold selected + Silver question →
   refusal). Fixed same-day: inject only when the question names no plan.
   Verified: Bronze selected, Gold and Silver questions both answered
   correctly. (Later extended to v2 — see Resolutions.)

3. **THE HEADLINE — suspected hallucination turned out to be my data
   contradicting itself.** "What is the copay on the Gold plan?" returned
   $25 primary / $50 specialist — which contradicted coverage.db's 10%.
   Built a triple-layer defense (Variant E redeployed with a
   no-invented-numbers rule; a numeric-grounding guard in the API that
   blocks answers containing figures absent from retrieved context; sources
   wired through the response). The guard kept passing the answer — and
   investigation proved it right: chunk_0000 (benefits.txt, Day 7) lists
   Gold PPO tiered copays ($25/$50/$10/$40 + 10% coinsurance for
   ER/imaging) while coverage.db carries a single copay_pct=10. Two
   systems of record disagree; hybrid retrieval routes different phrasings
   to different truths ("premium for Gold" → SQL; "copay on the Gold
   plan" → vector). The model was faithfully grounded all along.
   **Resolution path:** treat tiered copays as service copays and
   copay_pct as coinsurance (readings are compatible), or reconcile the
   sources — scheduled with remaining data work.

4. **Variant E is context-regime-dependent.** On Day 12's hand-made
   contexts it scored 20/20; on real weak retrieval its 3-answered:1-refused
   demonstration set leaned it toward invention: T02 produced three
   different maternity verdicts in three runs (no → hedged → yes — a
   confident non-numeric claim the numeric guard can't catch), T09 answered
   enrollment from world knowledge with an invented phone number. T03
   asserted "the status of claim C-2031 is currently being processed" for a
   claim that doesn't exist (SQL rows: 0) — a fabricated status wrapped in
   "according to our records." Hand-made-context evals overestimate
   prompts; eval on real retrieval. All three classes closed by structural
   gates — see Resolutions.

5. **T07 precision note:** "How do I appeal" retrieved the claims-FILING
   chunk (form CF-100, 90 days) instead of the APPEALS chunk (180 days).
   Root cause found via diagnostics: a Day-7 chunk-boundary bug orphaned
   the "Appeals" section header onto the END of the filing chunk — the
   model saw filing steps "labeled" appeals. Fixed — see Resolutions.

## Resolutions (same day — evening hardening session)

All findings above were root-caused and fixed the same day. Final harness:
10/10 behaviorally correct (8 clean, 2 minor generation quirks), zero
hallucinations, zero fabricated verdicts. UI verified: catalog, vague, and
cross-plan question classes all correct with disclaimers 3/3.

| Issue | Root cause | Fix | Verified |
|---|---|---|---|
| T03 invented claim status | Claim ID + zero SQL rows → model improvised | Gate 1: claim-ID questions with no DB row → structural refusal (LLM never called) | ✓ refusal |
| T02 coverage coin-flip (3 verdicts / 3 runs) | Weak context + yes/no question, no numbers → guard-blind | Gate 3: "is X covered" requires X present in retrieved context, else refusal | ✓ refusal |
| T09 HealthCare.gov + invented phone | Corpus gap: only a 45-char title (chunk_0009) + a filled sample form on enrollment | Data repair: authored chunk_0013 (enrollment instructions) via add_kb_chunks.py (jsonl + Chroma, idempotent) + min-info chunk drop (<80 chars) | ✓ grounded 4-step answer |
| T07 filing≠appeals | Day-7 chunk-boundary bug: "Appeals" header orphaned onto the END of the filing chunk | Intent filter: "appeal" questions keep only chunks matching on section/opening text — the orphaned trailing header can't qualify | ✓ 180-days answer, chunks: 1 |
| T06 M1001 refusal (7 days old) | Day-10 SQL template omitted member_id column | Template fixed + new claim-by-ID template (also makes "status of claim C1001" answerable) | ✓ answers (one-row summary quirk noted) |
| T05 incomplete comparison | (SQL was correct — generation omission) | Resolved alongside; both plans now listed | ✓ Bronze + Silver |
| Day-16 finding #5 (catalog) | No plan-overview chunk | chunk_0014 authored + embedded | ✓ "we offer three health plans" |
| **Plan-metadata filter bug (since Day 9)** | Exact-match filter {"plan_type": "HMO"} silently EXCLUDED plan_type="all" universal chunks (catalog, exclusions, claims process) whenever a plan was named — caught via the catalog question through the UI's plan injection, which retrieved Jane's sample enrollment form instead | $in filters: {"plan_type": {"$in": ["HMO", "all"]}} — plan family + universal chunks always | ✓ catalog answer correct with any plan selected |
| **Injection hijacking catalog questions** | "What plans do you offer" names no plan → injection fired → injected plan biased retrieval AND became the model's topic ("You have selected the Silver HMO…") | Injection v2: catalog/discovery questions (what plans / which plans / available / offer) join the no-injection lane | ✓ all three plans listed |

## Defense stack (final state)
1. Variant E grounding prompt + no-invented-numbers rule (disclaimers 10/10)
2. Gate 1 — claim-ID must be DB-backed
3. Gate 2 — relevance gate (no SQL + best distance > 1.30 → refuse)
4. Gate 3 — coverage-subject presence check
5. Min-info chunk drop (titles without bodies)
6. numbers_grounded() API guard (word-boundary set comparison, unit-tested)
7. sources[] provenance on every answer
8. $in plan filters (universal chunks always retrievable)
9. Injection v2 (plan-named + catalog questions untouched)

## Known minor quirks (documented, accepted)
- T06: model summarizes 1 of 2 delivered claim rows (3B data-reading limit)
- T04: "(plan ID not specified)" aside; T10: context-scaffolding echo
- Data discrepancy: coverage.db copay_pct=10 vs chunk_0000 tiered copays
  ($25/$50/$10/$40 + 10% coinsurance) — compatible readings (service copays
  vs coinsurance); reconciliation scheduled.