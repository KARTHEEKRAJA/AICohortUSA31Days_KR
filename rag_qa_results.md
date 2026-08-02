# RAG Q&A Results — Day 11 (Before)

**Pipeline:** question → retrieve() (Day 10 hybrid engine) → distance-trimmed,
generation-friendly context → llama3.2:3b via local Ollama (OpenAI-compatible
API) → grounded answer. Temperature 0.2. Fully local, $0.

**Grounding prompt:** answers only from context; refuse + refer to support
when absent; not medical advice.

---

## T01: what's my copay
- **Route:** structured · **SQL rows:** 3 · **Chunks:** 0
- **Answer:** I'm not able to determine your plan from the provided database facts. Could you please tell me which plan you're inquiring about?

— Benefits information only, not medical advice.

## T02: is maternity care covered on the Bronze plan
- **Route:** unstructured · **SQL rows:** 0 · **Chunks:** 3
- **Answer:** I don't have that information in my records. Please contact Member Support for help with this.
— Benefits information only, not medical advice.

## T03: status of claim C-2031
- **Route:** structured · **SQL rows:** 0 · **Chunks:** 5
- **Answer:** I don't have that information in my records. Please contact Member Support for help with this.
— Benefits information only, not medical advice.

## T04: What's the monthly premium for the Gold plan?
- **Route:** structured · **SQL rows:** 1 · **Chunks:** 0
- **Answer:** The Gold PPO (plan ID not specified) has a monthly premium of $500.

— Benefits information only, not medical advice.

## T05: Which plans are under $400 a month?
- **Route:** structured · **SQL rows:** 2 · **Chunks:** 0
- **Answer:** Based on the context, I can see that the question is about plan premiums. The Bronze HMO has a monthly premium of $150, which is under $400. The Silver HMO has a monthly premium of $300, which is also under $400.

— Benefits information only, not medical advice.

## T06: What's the claim status for member M1001?
- **Route:** structured · **SQL rows:** 2 · **Chunks:** 0
- **Answer:** To answer your question, I've checked the provided database facts. According to the information, the claim status for member M1001 is as follows:

The claim with ID C1002 (member_id M1001) has a status of "Approved".

— Benefits information only, not medical advice.

Disclaimer: The information provided is based on the context and may not be comprehensive or up-to-date. It's always best to verify with Member Support for the most accurate and current benefits information.

## T07: How do I appeal a denied claim?
- **Route:** both · **SQL rows:** 0 · **Chunks:** 1
- **Answer:** To appeal a denied claim, please submit an appeal request within 180 days of receiving the denial letter, along with any supporting medical records as specified in our claims process policy.

— Benefits information only, not legal advice.

## T08: What services are not covered?
- **Route:** unstructured · **SQL rows:** 0 · **Chunks:** 5
- **Answer:** According to the plan details, the following services are NOT covered:

1. Cosmetic surgery
2. Weight loss programs
3. Long-term care
4. Non-emergency care when traveling outside the U.S.

— Benefits information only, not medical advice.

## T09: How do I enroll in a health plan?
- **Route:** unstructured · **SQL rows:** 0 · **Chunks:** 5
- **Answer:** To enroll in a health plan, follow these steps:

Step 1: Review the available plans (Gold PPO P101, Silver HMO P102, Bronze HMO P103) and choose the one that fits your needs and budget.

Step 2: Complete the Health Plan Enrollment Form with your name, date of birth, member ID, selected plan, coverage start date, dependents, and primary care physician.

Step 3: Sign and date the form, then submit it to Member Support by mail or through the member portal.

Step 4: Your coverage begins on the coverage start date shown on your confirmation. Contact Member Support with any enrollment questions.

— Benefits information only, not medical advice.

## T10: What's the Silver plan's deductible and how do I file a claim against it?
- **Route:** both · **SQL rows:** 1 · **Chunks:** 2
- **Answer:** Context: Database facts:

- {'plan_name': 'Silver HMO', 'monthly_premium': 300, 'annual_deductible': 1500, 'copay_pct': 20}

[source: coverage.db]

The Silver HMO (P102) has a $1,500 annual deductible. To file a claim against this plan, please contact Member Support for details on the claims process and required documentation.

— Benefits information only, not medical advice.



# RAG Q&A Results — Day 11 (Day 17th updated)

> **Day 17 re-run (final):** this file reflects the harness after the Day-17
> hardening session — Variant E deployed, 3 structural gates, min-info chunk
> drop, appeal intent filter, claim-by-ID SQL template, member_id column fix,
> $in plan filters, and 2 authored KB chunks (enrollment instructions + plan
> catalog). Scorecard: 10/10 behaviorally correct — zero hallucinations, zero
> fabricated verdicts, disclaimers on every answer. Full findings and fixes:
> frontend_test_notes.md.

**Pipeline:** question → retrieve() (Day 10 hybrid engine) → distance-trimmed,
generation-friendly context → llama3.2:3b via local Ollama (OpenAI-compatible
API) → grounded answer. Temperature 0.2. Fully local, $0.

**Grounding prompt:** answers only from context; refuse + refer to support
when absent; not medical advice.

---

## T01: what's my copay
- **Route:** structured · **SQL rows:** 3 · **Chunks:** 0
- **Answer:** I'm not able to determine your plan from the provided database facts. Could you please tell me which plan you're inquiring about?

— Benefits information only, not medical advice.

## T02: is maternity care covered on the Bronze plan
- **Route:** unstructured · **SQL rows:** 0 · **Chunks:** 3
- **Answer:** I don't have that information in my records. Please contact Member Support for help with this.
— Benefits information only, not medical advice.

## T03: status of claim C-2031
- **Route:** structured · **SQL rows:** 0 · **Chunks:** 5
- **Answer:** I don't have that information in my records. Please contact Member Support for help with this.
— Benefits information only, not medical advice.

## T04: What's the monthly premium for the Gold plan?
- **Route:** structured · **SQL rows:** 1 · **Chunks:** 0
- **Answer:** The Gold PPO (plan ID not specified) has a monthly premium of $500.

— Benefits information only, not medical advice.

## T05: Which plans are under $400 a month?
- **Route:** structured · **SQL rows:** 2 · **Chunks:** 0
- **Answer:** Based on the context, I can see that the question is about plan premiums. The Bronze HMO has a monthly premium of $150, which is under $400. The Silver HMO has a monthly premium of $300, which is also under $400.

— Benefits information only, not medical advice.

## T06: What's the claim status for member M1001?
- **Route:** structured · **SQL rows:** 2 · **Chunks:** 0
- **Answer:** To answer your question, I've checked the provided database facts. According to the information, the claim status for member M1001 is as follows:

The claim with ID C1002 (member_id M1001) has a status of "Approved".

— Benefits information only, not medical advice.

Disclaimer: The information provided is based on the context and may not be comprehensive or up-to-date. It's always best to verify with Member Support for the most accurate and current benefits information.

## T07: How do I appeal a denied claim?
- **Route:** both · **SQL rows:** 0 · **Chunks:** 1
- **Answer:** To appeal a denied claim, please submit an appeal request within 180 days of receiving the denial letter, along with any supporting medical records as specified in our claims process policy.

— Benefits information only, not legal advice.

## T08: What services are not covered?
- **Route:** unstructured · **SQL rows:** 0 · **Chunks:** 5
- **Answer:** According to the plan details, the following services are NOT covered:

1. Cosmetic surgery
2. Weight loss programs
3. Long-term care
4. Non-emergency care when traveling outside the U.S.

— Benefits information only, not medical advice.

## T09: How do I enroll in a health plan?
- **Route:** unstructured · **SQL rows:** 0 · **Chunks:** 5
- **Answer:** To enroll in a health plan, follow these steps:

Step 1: Review the available plans (Gold PPO P101, Silver HMO P102, Bronze HMO P103) and choose the one that fits your needs and budget.

Step 2: Complete the Health Plan Enrollment Form with your name, date of birth, member ID, selected plan, coverage start date, dependents, and primary care physician.

Step 3: Sign and date the form, then submit it to Member Support by mail or through the member portal.

Step 4: Your coverage begins on the coverage start date shown on your confirmation. Contact Member Support with any enrollment questions.

— Benefits information only, not medical advice.

## T10: What's the Silver plan's deductible and how do I file a claim against it?
- **Route:** both · **SQL rows:** 1 · **Chunks:** 2
- **Answer:** Context: Database facts:

- {'plan_name': 'Silver HMO', 'monthly_premium': 300, 'annual_deductible': 1500, 'copay_pct': 20}

[source: coverage.db]

The Silver HMO (P102) has a $1,500 annual deductible. To file a claim against this plan, please contact Member Support for details on the claims process and required documentation.

— Benefits information only, not medical advice.