# RAG Q&A Results — Day 11

**Pipeline:** question → retrieve() (Day 10 hybrid engine) → distance-trimmed,
generation-friendly context → llama3.2:3b via local Ollama (OpenAI-compatible
API) → grounded answer. Temperature 0.2. Fully local, $0.

**Grounding prompt:** answers only from context; refuse + refer to support
when absent; not medical advice.

---

## T01: what's my copay
- **Route:** structured · **SQL rows:** 3 · **Chunks:** 0
- **Answer:** I don't know. The context only provides information about plan names and premiums, but not the specific plan you're enrolled in or your personal details. I recommend contacting support for more personalized assistance.

## T02: is maternity care covered on the Bronze plan
- **Route:** unstructured · **SQL rows:** 0 · **Chunks:** 3
- **Answer:** I don't know and suggest contacting support for more information about maternity care coverage on the Bronze HMO plan (P103).

## T03: status of claim C-2031
- **Route:** unstructured · **SQL rows:** 0 · **Chunks:** 5
- **Answer:** I don't know the current status of claim C-2031. I suggest contacting member support for more information on how to check the status of your claim or for assistance with the appeals process.

## T04: What's the monthly premium for the Gold plan?
- **Route:** structured · **SQL rows:** 1 · **Chunks:** 0
- **Answer:** The monthly premium for the Gold plan is $500.

## T05: Which plans are under $400 a month?
- **Route:** structured · **SQL rows:** 2 · **Chunks:** 0
- **Answer:** The Bronze HMO plan is under $400 a month.

## T06: What's the claim status for member M1001?
- **Route:** structured · **SQL rows:** 2 · **Chunks:** 0
- **Answer:** I don't know and suggest contacting support.

## T07: How do I appeal a denied claim?
- **Route:** both · **SQL rows:** 0 · **Chunks:** 5
- **Answer:** To appeal a denied claim, you must include the denial letter and any supporting medical records within 180 days of the denial.

## T08: What services are not covered?
- **Route:** unstructured · **SQL rows:** 0 · **Chunks:** 5
- **Answer:** According to the context, the following services are NOT covered:

1. Cosmetic surgery
2. Weight loss programs
3. Long-term care
4. Non-emergency care when traveling outside the U.S.

## T09: How do I enroll in a health plan?
- **Route:** unstructured · **SQL rows:** 0 · **Chunks:** 5
- **Answer:** I don't know. The context only provides information about the enrollment process, but it doesn't mention how to actually enroll in a health plan. I suggest contacting member support for assistance with enrolling in a health plan.

## T10: What's the Silver plan's deductible and how do I file a claim against it?
- **Route:** both · **SQL rows:** 1 · **Chunks:** 2
- **Answer:** I don't know and suggest contacting support for more information on filing a claim against the Silver HMO plan, as this detail is not provided in the given context.
