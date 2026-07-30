# Fine-Tuning Prep Notes — Day 14

**Evidence base:** logged failures from Days 10–13 (retrieval_test_results.md,
rag_qa_results.md, prompt_variants.md/variant_answers.md, tool_call_log.md).

## Three recurring issues (from my own test logs)

### Issue 1 — Disclaimer inconsistency  → FINE-TUNING CAN FIX
Day 12: Variant A appended the mandatory disclaimer only intermittently when it
was stated as a rule; only teaching it inside worked examples (Variant E) made
it reliable — and that reliability currently lives in a long prompt. Fine-tuning
on examples that all end with "— Benefits information only, not medical advice."
bakes the behavior into the weights: format/style is FT's home turf.

### Issue 2 — Tone & format instability  → FINE-TUNING CAN FIX
Day 12: Variant B produced four different behaviors in four runs of the same
question; Variant D answered in fragments ("$1500"). Day 13: text replies
occasionally cosplayed tool-JSON. These are output-style problems — consistent
voice, complete sentences, no format leakage — precisely what supervised
examples teach.

### Issue 3 — Over-refusal when the answer is present  → PARTIALLY FIXABLE
Day 12: Variant C refused a $300 premium sitting in its context (3 runs).
Day 11: T06 refused claims data that lacked explicit member linkage. FT on
"worried question + answer present → answered warmly" examples teaches the
boundary. But T06's *root cause* was a missing SQL column — a system bug FT
must not paper over. Fix the data path first, then tune the behavior.

## What fine-tuning CANNOT fix (retrieval problems)

- **Missing knowledge** (Day 10/11: maternity, claim C-2031 — not in the
  corpus). FT injects style, not facts; facts belong in RAG where they can be
  updated without retraining.
- **Retrieval bugs** (Day 10: the HMO filter excluding plan_type="all" chunks;
  the Day-6 mislabeled chunk ranking poorly). A model tuned to perfection
  still can't cite context it never receives.
- **Sampling noise** (Day 13: one greeting, four failure modes). FT strengthens
  format priors but cannot make a stochastic decoder deterministic —
  containment (validation, guards) remains mandatory.

## Decision rule
**Behavior in the output → fine-tune. Facts in the corpus → RAG. Bugs in the
pipeline → fix the pipeline. Noise in sampling → contain it.**