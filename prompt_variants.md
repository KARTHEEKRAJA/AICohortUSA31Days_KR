# Prompt Variants A–E — Day 12

**Method:** five prompt strategies for the same grounding job, tested head-to-head
on 5 questions covering every behavior axis (fact retrieval, medical-advice trap,
worried-member cost, not-in-context refusal, second fact). Model: llama3.2:3b via
local Ollama, temperature 0.2. Evidence: 25 answers (see harness in
prompt_variants.py).

## The Variants

| | Strategy | Core idea |
|---|---|---|
| A | Strict/formal | Numbered rules, exact citation format, scripted refusals |
| B | Warm/empathetic | One-sentence reassurance, kind redirects, precision by instruction |
| C | Few-shot | 3 worked examples (citation, refusal, medical disclaimer) |
| D | Chain-of-thought | 4 explicit checks (plan → section → presence → medical), FINAL ANSWER marker |
| E | Hybrid | C's examples + B's warmth *taught by example* + balanced demonstration set + mandatory closing disclaimer |

*(Full prompt texts in `prompt_variants.py`.)*

## Score Grid (1–5 per dimension)

| Variant | Accuracy | Tone | Conciseness | Compliance | **Total /20** |
|---|---|---|---|---|---|
| A — strict/formal | 5 | 3 | 4 | 4 | 16 |
| B — warm/empathetic | 2 | 4 | 3 | 2 | 11 |
| C — few-shot | 4 | 3 | 5 | 4 | 16 |
| D — chain-of-thought | 4 | 2 | 3 | 3 | 12 |
| **E — hybrid** | **5** | **5** | **5** | **5** | **20** |

## Evidence Highlights

- **B is the least safe variant despite the best bedside manner.** Across
  repeated runs of the same medical-trap question at temperature 0.2, B produced
  four different behaviors — including inventing "pre-authorization from our
  network providers" (not in context) and, on Q4, asserting dental cleanings are
  *not covered* as if it were fact. Warmth-by-instruction pulls a small model
  toward helpfulness, and helpfulness erodes refusal discipline.
- **C is the trap champion with a self-inflicted bug.** Its medical refusal was
  word-perfect every run. But its demonstration set contained one refusal
  example about plan details — and the model over-generalized, refusing to state
  the $300 premium that sat in plain context, in three separate runs. Few-shot
  models imitate examples harder than they read context.
- **D reasons well and answers badly.** Its steps correctly identified plan and
  section every time; its member-facing output collapsed to fragments ("$1500",
  "$300/month"). Visible chain-of-thought traded prose quality for reasoning —
  the wrong trade for a member-facing surface (and ~2–3× the tokens).
- **A is the honest baseline:** accurate and compliant, but cold, and its
  disclaimer appeared inconsistently because it was stated as a rule, not shown
  as a pattern.

## Chosen Prompt: **Variant E (hybrid)**

E swept the grid (20/20) because every element was selected from a *measured*
failure of another variant:

1. **Few-shot core from C** — examples beat instructions on a 3B model.
2. **C's over-refusal fixed by one example**: Example 2 shows a worried cost
   question *answered* from context. The exact question C refused three times,
   E answered correctly with one warmth sentence — before/after proof that
   balancing the demonstration set repairs over-refusal.
3. **B's warmth kept, B's mechanism discarded** — empathy is *shown* inside a
   worked example instead of instructed, making it consistent instead of
   improvised.
4. **D's checking kept, D's visibility dropped** — one "silently check" line,
   no reasoning in the output.
5. **The mission's standard closing disclaimer** ("— Benefits information only,
   not medical advice.") appears in all four examples, so imitation guarantees
   it on every answer — it appeared 5/5 times in testing.

**One-line takeaway:** on small models, show, don't tell — and audit your
examples, because the model will learn your demonstration set's biases more
faithfully than your rules.

**Going forward:** Variant E replaces the Day 11 grounding prompt in
rag_chatbot.py.