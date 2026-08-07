"""Day 22 — Multi-Agent Orchestration (CrewAI).

Step 2: the ROUTER — one agent, one job: read the member's question and
classify it as coverage | claims | enrollment, deciding which specialist
runs. Day-21 law applies: trust the 3B with the decision, never the
conclusion — the LLM's verdict passes through deterministic guardrails
(a claim ID in the question FORCES claims; unparseable output falls back
to keyword rules). The router may be wrong; the route cannot be garbage.
"""
import re
import sys

from crewai import Agent, Crew, LLM, Task

# ---- LLM: local Ollama via CrewAI's LiteLLM route ------------------
llm = LLM(
    model="ollama/llama3.2:3b",            # LiteLLM dialect: provider/tag
    base_url="http://localhost:11434",     # NOT /v1 — LiteLLM adds paths
    temperature=0,
)

VALID_ROUTES = ("coverage", "claims", "enrollment")
CLAIM_RE = re.compile(r"\bC[-\s]?\d+\b", re.IGNORECASE)
ENROLL_WORDS = ("enroll", "enrolment", "enrollment", "sign up", "signup",
                "join a plan", "switch plans", "open enrollment")

# ---- Agent 1: the Router -------------------------------------------
router = Agent(
    role="Question Router",
    goal=("Classify a member's question into exactly one word: coverage, "
          "claims, or enrollment. Output ONLY that single word."),
    backstory=("You are the front desk of a health-insurance support "
               "team. You never answer questions yourself — you only "
               "decide which specialist should handle them. Questions "
               "about what a plan covers, plan prices, deductibles, "
               "copays or costs are 'coverage'. Questions about the "
               "status or details of a submitted claim are 'claims'. "
               "Questions about joining, changing or signing up for a "
               "plan are 'enrollment'."),
    llm=llm,
    verbose=False,
    allow_delegation=False,
)


def _route_task(question: str) -> Task:
    return Task(
        description=(f"Classify this member question: '{question}'. "
                     "Reply with exactly one word — coverage, claims, "
                     "or enrollment. No punctuation, no explanation."),
        expected_output="one word: coverage, claims, or enrollment",
        agent=router,
    )


def _keyword_fallback(question: str) -> str:
    q = question.lower()
    if CLAIM_RE.search(question):
        return "claims"
    if any(w in q for w in ENROLL_WORDS):
        return "enrollment"
    return "coverage"


def route(question: str) -> dict:
    """LLM routes; guardrails make the verdict safe.
    Returns {question, llm_said, route, guardrail}."""
    crew = Crew(agents=[router], tasks=[_route_task(question)],
                verbose=False)
    raw = str(crew.kickoff()).strip().lower()
    # normalize: first recognizable route word anywhere in the reply
    llm_said = next((w for w in VALID_ROUTES if w in raw), None)

    guardrail = None
    final = llm_said
    if CLAIM_RE.search(question) and llm_said != "claims":
        final, guardrail = "claims", "claim-ID override"
    elif llm_said is None:
        final, guardrail = _keyword_fallback(question), "keyword fallback"
    return {"question": question, "llm_said": llm_said or f"<{raw[:40]}>",
            "route": final, "guardrail": guardrail}


# ==== Step 3: the specialists =======================================
# "retrieval + tools": each specialist gets its slice of the Day-13
# toolbox PLUS policy-doc search over the Day-7 chroma store. Claim/plan
# ID parsing reuses Day 21's shim discipline — one string in, regex out.
from crewai.tools import tool

# DOC SEARCH (Day-22 finding, two acts): (1) lazy-importing retrieval
# inside the tool loaded torch in CrewAI's worker thread — silent death;
# (2) pre-warming fixed the embedder but chromadb's RUST bindings still
# abort when queried off the main thread — a Rust panic kills the whole
# process, no traceback. Verdict: native code does not belong inside
# crew tools. At 15 chunks, a pure-Python keyword scorer over the JSONL
# matches vector search anyway — zero threads, zero Rust, zero deaths.
import json as _json


def _load_chunks(path: str = "knowledge_base.jsonl") -> list[dict]:
    chunks = []
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    chunks.append(_json.loads(line))
    except FileNotFoundError:
        pass
    return chunks


_KB = _load_chunks()
_WORD = re.compile(r"[a-z0-9']+")


def _score(query: str, text: str) -> float:
    q = set(_WORD.findall(query.lower()))
    t = _WORD.findall(text.lower())
    if not q or not t:
        return 0.0
    tset = set(t)
    overlap = len(q & tset) / len(q)
    return overlap


def _kb_search(query: str, k: int = 3) -> list[dict]:
    scored = sorted(_KB, key=lambda c: _score(query, c.get("text", "")),
                    reverse=True)
    return [c for c in scored[:k] if _score(query, c.get("text", "")) > 0]

from tool_calling_chatbot import (
    check_coverage as _check_coverage,
    get_claim_status as _get_claim_status,
    get_plan_details as _get_plan_details,
    estimate_out_of_pocket_cost as _estimate_cost,
    validate_tool_result as _validate,
)

PLAN_RE = re.compile(r"\bP\d{3}\b", re.IGNORECASE)


def _plan_and_text(text: str) -> tuple[str | None, str]:
    m = PLAN_RE.search(text)
    plan = m.group(0).upper() if m else None
    rest = PLAN_RE.sub("", text).replace(",", " ").strip().strip("'\"` ")
    return plan, rest


@tool("check_coverage")
def t_check_coverage(text: str) -> str:
    """Answers WHETHER a procedure is covered under a plan. Input: plan ID
    and procedure together, e.g. 'P101, x-ray'."""
    plan, proc = _plan_and_text(text)
    if not plan or not proc:
        return str({"error": "need plan ID + procedure, e.g. 'P101, x-ray'"})
    return str(_validate("check_coverage", _check_coverage(plan, proc)))


@tool("get_plan_details")
def t_get_plan_details(text: str) -> str:
    """Returns a plan's premium, deductible and copay. Input: plan ID,
    e.g. 'P102'."""
    plan, _ = _plan_and_text(text)
    if not plan:
        return str({"error": "need a plan ID like P101"})
    return str(_validate("get_plan_details", _get_plan_details(plan)))


@tool("estimate_out_of_pocket_cost")
def t_estimate_cost(text: str) -> str:
    """Estimates the DOLLAR amount a member pays for a procedure on a
    plan. Input: procedure and plan ID, e.g. 'x-ray, P101'."""
    plan, proc = _plan_and_text(text)
    if not plan or not proc:
        return str({"error": "need procedure + plan ID, e.g. 'x-ray, P101'"})
    return str(_validate("estimate_out_of_pocket_cost",
                         _estimate_cost(proc, plan)))


@tool("get_claim_status")
def t_get_claim_status(text: str) -> str:
    """Looks up ONE claim by ID (like C1001): status, amount, procedure."""
    m = CLAIM_RE.search(text)
    if not m:
        return str({"error": "need a claim ID like C1001"})
    cid = m.group(0).upper().replace(" ", "").replace("-", "")
    return str(_validate("get_claim_status", _get_claim_status(cid)))


@tool("search_policy_docs")
def t_search_policy_docs(query: str) -> str:
    """Searches the policy knowledge base (coverage rules, exclusions,
    claims process, appeals, enrollment). Input: a plain-English query.
    Returns the most relevant policy text passages."""
    chunks = _kb_search(query)
    if not chunks:
        return "No relevant policy passages found."
    out = []
    for c in chunks:
        sec = c.get("section") or c.get("metadata", {}).get("section", "?")
        text = (c.get("text") or "")[:400]
        out.append(f"[{c.get('id', '?')} · {sec}] {text}")
    return "\n---\n".join(out)


# ---- Agent 2: Coverage Specialist ----------------------------------
coverage_specialist = Agent(
    role="Coverage Specialist",
    goal=("Answer coverage, plan-details, cost and enrollment questions "
          "using your tools. Use the numbers the tools return — never "
          "invent plan facts, prices or coverage decisions."),
    backstory=("You handle everything about what plans include and cost: "
               "whether procedures are covered, premiums, deductibles, "
               "copays, out-of-pocket estimates, and how enrollment "
               "works. For plan facts use the lookup tools; for process "
               "questions (like enrollment steps) use search_policy_docs."),
    tools=[t_check_coverage, t_get_plan_details, t_estimate_cost,
           t_search_policy_docs],
    llm=llm,
    verbose=False,
    allow_delegation=False,
    max_iter=3,
)

# ---- Agent 3: Claims Specialist ------------------------------------
claims_specialist = Agent(
    role="Claims Specialist",
    goal=("Answer questions about submitted claims using your tools. "
          "Report exactly what the claim lookup returns — never invent "
          "a status or amount. If a claim is not found, say so."),
    backstory=("You handle submitted claims: their status, amounts and "
               "details, plus the claims/appeals process. For a specific "
               "claim use get_claim_status with its ID; for process "
               "questions (how to appeal, deadlines) use "
               "search_policy_docs."),
    tools=[t_get_claim_status, t_search_policy_docs],
    llm=llm,
    verbose=False,
    allow_delegation=False,
    max_iter=3,
)


def ask_specialist(agent: Agent, question: str,
                   instructions: str = "") -> str:
    """Run ONE specialist on ONE question. The wiring (Step 4) passes
    route-specific instructions so the Router's classification isn't
    wasted. Set MULTIAGENT_VERBOSE=1 to watch the crew think."""
    import os
    vb = os.environ.get("MULTIAGENT_VERBOSE") == "1"
    task = Task(
        description=(f"Answer this member question: '{question}'. "
                     f"{instructions} Use your tools to get real data, "
                     "then answer in one or two sentences using only "
                     "what the tools returned."),
        expected_output="a short factual answer based on tool results",
        agent=agent,
    )
    crew = Crew(agents=[agent], tasks=[task], verbose=vb)
    out = str(crew.kickoff()).strip()
    if not out:
        out = "<EMPTY CREW OUTPUT — see verbose run>"
    return out


# ==== Step 4: the wiring — Router output picks the specialist =======
# claims -> Claims Specialist; coverage AND enrollment -> Coverage
# Specialist (its backstory owns enrollment via search_policy_docs).
# Each dispatch carries clear route-specific instructions, so the
# Router's classification work is not wasted (mission bullet 2).
INSTRUCTIONS = {
    "coverage": ("The router classified this as a COVERAGE question: "
                 "plan facts, prices, coverage decisions or cost "
                 "estimates. Prefer the lookup tools for plan numbers; "
                 "use search_policy_docs only for process questions."),
    "claims": ("The router classified this as a CLAIMS question. If the "
               "question contains a claim ID, use get_claim_status with "
               "it. For process questions (appeals, deadlines) use "
               "search_policy_docs."),
    "enrollment": ("The router classified this as an ENROLLMENT "
                   "question. Use search_policy_docs to find the "
                   "enrollment instructions and answer with the steps."),
}


def ask(question: str) -> dict:
    """The full system: Router classifies -> specialist executes.
    Returns {question, llm_said, route, guardrail, specialist, answer}."""
    r = route(question)
    lane = r["route"]
    agent = claims_specialist if lane == "claims" else coverage_specialist
    answer = ask_specialist(agent, question, INSTRUCTIONS[lane])
    return {**r, "specialist": agent.role, "answer": answer}


if __name__ == "__main__":
    import os
    os.environ.setdefault("CREWAI_TRACING_ENABLED", "false")
    if len(sys.argv) > 2 and sys.argv[1] == "--route":
        r = route(" ".join(sys.argv[2:]))
        print(r)
    elif len(sys.argv) > 2 and sys.argv[1] == "--coverage":
        print(ask_specialist(coverage_specialist, " ".join(sys.argv[2:])))
    elif len(sys.argv) > 2 and sys.argv[1] == "--claims":
        print(ask_specialist(claims_specialist, " ".join(sys.argv[2:])))
    elif len(sys.argv) > 2 and sys.argv[1] == "--ask":
        r = ask(" ".join(sys.argv[2:]))
        tag = "[route: " + r["route"] + " -> " + r["specialist"]
        if r["guardrail"]:
            tag += " · " + r["guardrail"]
        tag += "]"
        print(tag)
        print(r["answer"])
    else:
        # Step 2 test: 4 questions, one per lane + the claim-ID trap
        for q in [
            "What is the deductible for plan P102?",
            "What's the status of claim C1001?",
            "How do I sign up for a new health plan?",
            "Tell me about C1002",        # no 'claim' word — ID must force it
        ]:
            print(route(q))