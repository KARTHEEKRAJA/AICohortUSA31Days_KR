# Agent Traces — Day 21 (LangChain ReAct over Day 13 tools)

**Stack:** langchain 1.3.14 + langchain-classic (`create_react_agent` +
`AgentExecutor`, verbose) · llama3.2:3b via local Ollama (OpenAI-compatible
endpoint) · 4 tools wrapped as `Tool` objects with routing-map descriptions ·
single-string shims (regex ID extraction — argument order never matters) ·
Day-13 Pydantic validation between every tool and the agent · deterministic
final-answer rescue (`_format_final`) when the model can't exit.

## The 5-question battery (final run)

### Q1 — "What is the monthly premium for plan P101?"
```
Action: get_plan_details
Action Input: 'P101'
Observation: {"plan_name": "Gold PPO", "monthly_premium": 500.0, ...}
Final Answer: The monthly premium for plan P101 is $500.00.
```
Tool ✓ (rep would do the same) · self-exit ✓ · answer ✓

### Q2 — "Is physical therapy covered under plan P103?"
```
Thought: I need to check if physical therapy is covered under plan P103.
Action: check_coverage
Action Input: 'P103, physical therapy'
Observation: {"plan_id": "P103", ..., "covered": false}
Final Answer: The physical therapy is not covered under plan P103.
```
Tool ✓ · a real Thought appeared · self-exit ✓ · answer ✓

### Q3 — "What's the status of claim C1002?"
```
Action: get_claim_status
Action Input: C1002
Observation: {"claim_id": "C1002", ..., "status": "Approved"}
Final Answer: The status of claim C1002 is Approved.
```
Tool ✓ (claim ID → claim tool, no hesitation) · self-exit ✓ · answer ✓

### Q4 — "How much would an x-ray cost me on plan P102?"
```
Action: estimate_out_of_pocket_cost
Action Input: 'x-ray, P102'
Observation: {..., "estimated_out_of_pocket": 50.0, "copay_pct": 20.0}
Final Answer: The estimated out-of-pocket cost ... would be $50.
```
Tool ✓ — **the subtlest routing** (cost ≠ coverage ≠ details) done right ·
self-exit ✓ · answer ✓. This same question produced total format collapse
earlier in the day (see findings).

### Q5 — "Is claim C-9999 approved?" (the trap — claim doesn't exist)
```
Action: get_claim_status
Action Input: C-9999
Observation: {"error": "claim C9999 not found"}
Thought: The tool returned an error...
Action: <malformed — flailed reacting to the error> (x2)
FINAL (deterministic rescue): I couldn't complete that lookup: claim
C9999 not found
```
Tool ✓ · honest error surfaced, nothing invented · **rescued** — the one
question where the fire escape earned its keep.

## Scorecard vs a human coverage rep
| Q | Right tool? | Same as a rep? | Self-exit | Correct answer |
|---|---|---|---|---|
| 1 | ✓ | ✓ | ✓ | ✓ |
| 2 | ✓ | ✓ | ✓ | ✓ |
| 3 | ✓ | ✓ | ✓ | ✓ |
| 4 | ✓ | ✓ | ✓ | ✓ |
| 5 | ✓ | ✓ (rep would also look it up, then report not-found) | rescued | ✓ |

**Tool selection: 5/5. Final answers: 5/5. Self-exits: 4/5 + 1 deterministic rescue.**

## Findings (the day's real curriculum)
1. **Right tool, no exit.** First runs: perfect tool choice, then an echo
   loop — the model re-generated "Question:" forever instead of "Final
   Answer:". It KNEW the answer and couldn't say it.
2. **The stop-sequence trap.** Stopping generation at "Question:" killed
   the echo — and zeroed output entirely on cost questions, where the
   echo IS the first token. A fix at the wrong layer.
3. **The framework rescue that wasn't.** `early_stopping_method="generate"`
   is unsupported for runnable agents in langchain-classic 1.x. Discovered
   at runtime.
4. **The model that couldn't read 2 keys of JSON.** An LLM-based rescue
   ("answer from this tool result") got an apology instead of an answer.
   Exit rebuilt as PURE CODE: `_format_final` turns validated JSON into a
   sentence per tool. Zero hallucination surface by construction.
5. **Exception steps poison the trace tail.** `handle_parsing_errors`
   logs recoveries as steps (tool='_Exception') — `steps[-1]` was garbage;
   the rescue now walks backwards to the last REAL tool step.
6. **Few-shot contamination (the big one).** Worked examples added to teach
   entry/exit made the model ANSWER THE EXAMPLE — it merged two examples
   into a hybrid question and solved that instead of the member's. Removing
   ALL content-bearing examples didn't just fix contamination — self-exits
   went 0/5 → 4/5. **The exit example was breaking the exits.** Small
   models don't generalize from examples; they get possessed by them.
7. **Description-as-router works.** With clean prompts, 4 boundary-drawn
   tool descriptions routed 5/5 — including cost vs coverage vs details.
   The descriptions are the product; the agent is just the reader.

## Step 5 completion — the skip-dimension probes

### Probe A — "What can you help me with?" (should SKIP tools)
```
Action: get_plan_details
Action Input: {"error": "need a plan ID like P101"}   <- hallucinated our
                                                         error format as input
(x3, echo loop) → FINAL (rescue): couldn't complete that lookup
```
A rep answers this from their head. The agent CANNOT skip: the prompt's
"use ONLY the tools" rule accidentally bans answering from its own mouth,
so it forced a spurious lookup — and fed the tool a copy of the shim's
error-message format. **Finding #8: a hammer prompt makes every question
a nail. Agents need an explicit no-tool exit ("some questions are
answered directly") — ours doesn't have one, by design-blindness.**

### Probe B — "My member ID is M1001 — am I covered for an mri scan on my gold plan?"
```
Thought: ...check if MRI is covered under their Gold plan   <- real reasoning
Action: check_coverage                                       <- RIGHT tool
Action Input: 'M1001, MRI'                                   <- WRONG id type
Observation: {"error": "need a plan_id like P101 plus a procedure..."}
Thought: I need to fix my Action Input to include a plan ID  <- correct
                                                                self-diagnosis
Action Input: 'M1001, MRI'                                   <- same input, x3
FINAL (rescue): honest error surfaced
```
Two lessons a rep never needs: (1) "gold plan" → P101 lives in our
DATABASE, not the model's world — name→ID translation must be provided
(tool description or a lookup tool), not assumed. (2) **Finding #9, the
day's most human one: the model read the error, correctly diagnosed its
own mistake in a Thought — then repeated the identical broken input.
Self-awareness without self-repair.** The error observations made the
trace honest; they did not make the model adaptive.

### Rep-comparison verdict (mission step 5, complete)
- Wrong tool selections across all 7 runs: **zero**
- Questions that should have skipped tools but didn't: **1 of 1 probed**
  (Probe A — structural, not incidental)
- Questions that should have used tools and didn't: **none observed**
- Gap to a human rep is NOT tool choice — it is exits, error adaptation,
  and world-knowledge (name→ID). All three are scaffolding problems, and
  two of three are already solved with code.

## Architecture verdict
LLM chooses · tools fetch validated truth · code formats the exit.
Trust the 3B with the decision, never with the conclusion.