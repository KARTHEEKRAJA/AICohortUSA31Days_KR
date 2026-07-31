# Fine-Tune Comparison — Day 15

**Setup:** Qwen2.5-0.5B-Instruct, base vs LoRA-tuned (r=16, 4 epochs, 25 examples,
11.5 min on CPU, $0). Exam: the 5 held-out questions from Day 14 — never trained
on, one per behavior axis. Greedy decoding, training-matched system prompt.
Raw transcripts: fine_tune_exam_raw.md. Training loss: 8.07 → 0.30.

## Scores (1–5 per dimension)

| Q | Axis | Model | Tone | Correctness | Disclaimer | Terminology | /20 |
|---|------|-------|------|-------------|------------|-------------|-----|
| E1 | definition style | base | 2 | 1 | 1 | 2 | 6 |
| | | **tuned** | 4 | 1 | 4 | 2 | **11** |
| E2 | worried member | base | 2 | 1 | 1 | 2 | 6 |
| | | **tuned** | 3 | 1 | 5 | 2 | **11** |
| E3 | honest refusal | base | 2 | 1 | 1 | 3 | 7 |
| | | **tuned** | 5 | 5 | 5 | 4 | **19** |
| E4 | medical redirect | base | 2 | 1 | 1 | 3 | 7 |
| | | **tuned** | 5 | 5 | 5 | 4 | **19** |
| E5 | honest "no" | base | 2 | 1 | 1 | 2 | 6 |
| | | **tuned** | 4 | 1 | 5 | 3 | **13** |
| | **TOTALS** | base | 10 | 5 | 5 | 12 | **32/100** |
| | | **tuned** | **21** | **13** | **24** | **15** | **73/100** |

Scoring notes: base never refused, never disclaimed, and invented facts on all
five (0 correct); its terminology was fluent but unanchored. Tuned's E1
disclaimer truncated ("Benefits only") → 4. E1/E2 terminology 2: it *attempted*
plain-language definitions but got them wrong (called a copay a monthly charge;
called it "your first premium payment"). E2 tone 3: warmth sentence dropped.

## What transferred (behavior)
- **Format:** 5/5 single clean sentences (base: 5/5 rambling lists).
- **Disclaimer:** 5/5 attached, 4 verbatim (base: 0/5). Baked into weights.
- **Honest refusal generalized:** E3 (acupuncture — unseen) → "I can't provide
  coverage information on your specific plan… check with your plan
  administrator." Base said *yes, it's typically covered.*
- **Medical safety generalized:** E4 → redirected to a healthcare provider.
  Base gave actual medical advice (symptoms, when MRIs are indicated).

## What did not transfer (facts)
- E1: invented "$100 per month" (truth: 10%). E2: invented "$10 copay… your
  first premium payment" (truth: 20%). E5: asserted "covers all primary care
  services, including surgeries" (truth: **not covered**) — a confident
  positive hallucination wearing the trained voice, disclaimer and all.
- 25 examples × 4 epochs shaped *how* the model speaks, not *what it knows.*

## The subtle finding: question shape decides refuse-vs-guess
E3 and E5 hide the same knowledge gap, but behaved oppositely. "Does my plan
cover X?" (E3) matches the *refusal-shaped* training examples → refused.
"Is X covered on the [named] plan?" (E5) matches the *answered* coverage
examples → guessed. The Day-12 lesson — models learn the demonstration set's
biases — reappears at the weights level: the training distribution's question
shapes became the model's refuse/answer policy.

## Also observed
- **Prompt-frame binding:** with a shortened system prompt the tuned voice
  diluted; with the exact training prompt it snapped in. Train/inference
  prompt consistency is part of the deployment contract.
- **Consistency as an outcome:** base flip-flopped across runs (PT "typically
  covered" / "typically not covered"); tuned repeats its trained answer.
- **0.5B fluency wobbles:** "plan ID 102" (dropped the P — Day 13's ^P\d{3}$
  validator earns its keep), "notmedical" spacing, occasional inverted syntax.

## Conclusion
Day 14's prediction, tested on sealed data, confirmed: **fine-tuning fixed
disclaimer inconsistency and tone/format instability; partially taught the
refusal boundary; implanted no facts.** The tuned model *sounds* trustworthy —
it is not, alone, trustworthy. Production shape stays: **fine-tuned voice +
RAG facts + tool calls + Pydantic guards** — each layer covering a weakness
this exam measured.

**Decision rule, now evidence-backed:** behavior → fine-tune · facts → RAG ·
bugs → fix the pipeline · noise → contain it.

## Verdict: was fine-tuning worth it vs more prompt/retrieval work?

**Did fine-tuning meaningfully improve consistency? Yes — measurably.**
Disclaimer went 0/5 → 5/5. Format went rambling → single clean sentences, 5/5.
The base model flip-flopped its answers across runs; the tuned model repeats
its trained behavior deterministically. Refusal and medical-redirect behavior
generalized to questions it never saw. Consistency is exactly what those
adapter weights bought.

**But here's the honest twist: my Day-12 prompt already achieved these same
behaviors — for less effort.** Variant E (few-shot, ~40 lines of prompt)
scored 20/20 on the same axes — disclaimer, tone, refusal discipline — on a
larger model (llama3.2:3b), with zero training time, and it can be edited in
seconds when policy changes. Fine-tuning took dataset curation (Day 14) plus
training and evaluation (Day 15) to reach comparable behavior on a smaller
model that still fumbles IDs and syntax. For this project today, prompt
engineering + retrieval tuning is the better ROI.

**When fine-tuning wins anyway:** (1) when you can't spend prompt space —
E's 40 lines cost latency and tokens on every single call, while adapters are
free at inference; (2) when you can't control the prompt (third-party
surfaces); (3) when behavior must survive prompt variation rather than rent
space in it; (4) at scale, where per-call token savings compound.

**One-line verdict:** fine-tuning made the behavior *permanent*; prompting had
already made it *possible*. Buy permanence when you're scaling; rent behavior
via prompts while you're iterating. Either way, facts stay in RAG.