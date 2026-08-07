# Multi-Agent vs Single-Agent — Day 22 (CrewAI) vs Day 21 (LangChain ReAct)

**Day 22 stack:** CrewAI 1.15.12 · Router + Coverage Specialist + Claims
Specialist · llama3.2:3b via Ollama (LiteLLM route) · 5 tools (Day-13
lookups with regex shims + pure-Python policy-doc search over the 15-chunk
JSONL) · deterministic guardrails on routing (claim-ID override, keyword
fallback) · max_iter=3 per specialist.

## The head-to-head (same 5 questions, same model, same tools)

| Q | Day 21 single agent | Day 22 crew | Winner |
|---|---|---|---|
| Premium P101 | ✓ right tool · ✓ answer · self-exit | ✓ route · ✓ $500 · clean | tie |
| PT covered P103 | ✓ · ✓ · self-exit | ✓ · ✓ not covered · clean | tie |
| Status C1002 | ✓ · ✓ · self-exit | ✓ · ✓ Approved · clean | tie |
| X-ray cost P102 | ✓ · ✓ $50 · self-exit (after a day of format collapse) | ✓ · ✓ $50 + procedure cost + copay% · clean | **crew** (richer, zero drama) |
| C-9999 trap | ✓ tool · then FLAILED at the error, x3 malformed actions — **code rescue delivered the answer** | ✓ route · **"not found" natively, clean self-exit** | **crew** |

**Routing accuracy:** Day 21: 5/5 tool choices (but format collapse cost a
question a whole debugging session). Day 22: 5/5 lane routes AND 5/5 tool
choices inside the specialists — 10/10 decisions, zero guardrail firings,
zero format errors, zero rescues.

**Answer quality:** both systems 5/5 grounded; the crew's answers were
richer (Q4 cited procedure cost and copay share) and needed no
deterministic rescue anywhere. Day 21 finished 4/5 self-exits + 1 rescue;
Day 22 finished 5/5 self-exits.

**Two old scars, healed by the Router:**
1. Day 20 finding: "And claim C1002?" (bare reference) was REFUSED by the
   single-pipeline chatbot — keyword-blind retrieval. The crew's wiring
   test routed "Tell me about C1002" to claims natively and answered
   Approved/$1,200.
2. Day 21 finding: the trap question made the ReAct agent flail at an
   error observation. The Claims Specialist reported not-found cleanly.

**Why the improvement?** Not a smarter model — the same 3B. Two structural
reasons: (a) each LLM call now has ONE narrow job (classify | answer
within a domain), and narrow jobs are what 3Bs do well; (b) CrewAI's
structured tool-calling (via LiteLLM function-calling) replaced raw
ReAct text parsing — the format llama3.2 kept fumbling simply no longer
exists. **Specialization + structured calling > monolithic ReAct, at
this model size.**

## The costs (documented honestly)
- **Latency:** every question now pays TWO LLM calls (router + specialist)
  — roughly 1.5–2× Day 21's per-question time on CPU.
- **Dependency risk (finding #0):** `pip install crewai` silently
  DOWNGRADED chromadb (1.5.x → 1.1.1); the older Rust engine panicked on
  our existing vector store. Caught in 90 seconds by a 3-command health
  protocol; fixed by re-upgrading, leaving one tolerable "crewai requires
  chromadb~=1.1.0" warning (only its unused memory feature cares).
- **Thread hostility (finding #1, two acts):** native code inside crew
  tools = silent process death on Windows. Act 1: lazy-importing torch in
  the tool killed the run. Act 2: pre-warmed, chromadb's Rust bindings
  STILL aborted when queried off the main thread. Verdict: crew tools got
  a pure-Python doc search (15 chunks — keyword scoring ≈ vector search
  at this size). Native code does not belong inside worker-thread tools.
- **Framework noise:** telemetry banners on every kickoff until
  CREWAI_TRACING_ENABLED=false.

## When multi-agent is worth it (the mission's real question)
**Worth it when:**
- Domains are genuinely different (coverage vs claims vs enrollment) so
  each specialist's toolset and instructions stay small — small models
  thrive on narrow contexts;
- Routing itself is the hard part (bare IDs, ambiguous phrasing) — a
  dedicated classifier beats keyword-dependent retrieval and beats hoping
  one agent picks right among many tools;
- You need per-domain guardrails/instructions (claims discipline differs
  from coverage discipline).

**Overkill when:**
- One domain, few tools: Day 21's single agent matched the crew on 3/5
  questions at half the latency;
- Latency budgets are tight (2× calls per question);
- You can't afford the dependency surface — the framework's install
  nearly wounded a 21-day-old production stack.

**Verdict:** for THIS chatbot, the crew wins on robustness (10/10
decisions, no rescues, two old bugs fixed) and loses on speed. The Day-21
law survives contact with orchestration: trust the 3B with decisions —
the crew just gives it MORE decisions, each SMALLER.