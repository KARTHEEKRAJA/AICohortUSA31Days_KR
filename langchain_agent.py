"""Day 21 — LangChain ReAct agent over the Day 13 tools.

Step 2: wrap check_coverage / get_claim_status / get_plan_details
(+ Day 13's bonus estimate_out_of_pocket_cost) as LangChain Tool
objects. The DESCRIPTION is the agent's only map — it decides which
tool fires. ReAct tools receive ONE string, so each multi-arg tool
gets a parsing shim; ID-vs-text is regex-detected so argument order
never matters. Every result passes Day 13's Pydantic validation
before the agent sees it — the agent reasons over validated data only.
"""
import json
import re

from langchain_core.tools import Tool

from tool_calling_chatbot import (
    check_coverage,
    get_claim_status,
    get_plan_details,
    estimate_out_of_pocket_cost,
    validate_tool_result,
)

PLAN_RE = re.compile(r"\bP\d{3}\b", re.IGNORECASE)
CLAIM_RE = re.compile(r"\bC[-\s]?\d+\b", re.IGNORECASE)


def _clean(text: str) -> str:
    """Strip quotes/whitespace the model tends to wrap inputs in."""
    return text.strip().strip("\"'` ").strip()


def _parts(text: str) -> list[str]:
    return [p for p in re.split(r"[,;|]", text) if _clean(p)]


def _find_plan(text: str) -> str | None:
    m = PLAN_RE.search(text)
    return m.group(0).upper() if m else None


def _validated(tool_name: str, result: dict) -> str:
    """Day 13 Pydantic gate, then JSON for the agent's Observation."""
    return json.dumps(validate_tool_result(tool_name, result))


# ---- shims: one string in -> real function args -------------------

def coverage_shim(text: str) -> str:
    plan = _find_plan(text)
    if not plan:
        return json.dumps({"error": "need a plan_id like P101 plus a "
                                    "procedure, e.g. 'P101, x-ray'"})
    procedure = _clean(PLAN_RE.sub("", text).replace(",", " "))
    if not procedure:
        return json.dumps({"error": "need a procedure name, "
                                    "e.g. 'P101, x-ray'"})
    return _validated("check_coverage", check_coverage(plan, procedure))


def claim_shim(text: str) -> str:
    m = CLAIM_RE.search(text)
    if not m:
        return json.dumps({"error": "need a claim ID like C1001"})
    claim_id = m.group(0).upper().replace(" ", "").replace("-", "")
    return _validated("get_claim_status", get_claim_status(claim_id))


def plan_shim(text: str) -> str:
    plan = _find_plan(text)
    if not plan:
        return json.dumps({"error": "need a plan ID like P101"})
    return _validated("get_plan_details", get_plan_details(plan))


def cost_shim(text: str) -> str:
    plan = _find_plan(text)
    if not plan:
        return json.dumps({"error": "need a plan_id and a procedure, "
                                    "e.g. 'x-ray, P101'"})
    procedure = _clean(PLAN_RE.sub("", text).replace(",", " "))
    if not procedure:
        return json.dumps({"error": "need a procedure, "
                                    "e.g. 'x-ray, P101'"})
    return _validated("estimate_out_of_pocket_cost",
                      estimate_out_of_pocket_cost(procedure, plan))


# ---- Step 2: the Tool objects — descriptions are the routing map --

AGENT_TOOLS = [
    Tool(
        name="check_coverage",
        func=coverage_shim,
        description=(
            "Answers WHETHER a medical procedure is covered (yes/no) under a "
            "specific plan. Use for 'is X covered on plan Y' questions. "
            "Input: plan ID and procedure, e.g. 'P101, x-ray'. "
            "Does NOT return costs — use estimate_out_of_pocket_cost for "
            "dollar amounts."
        ),
    ),
    Tool(
        name="get_claim_status",
        func=claim_shim,
        description=(
            "Looks up ONE claim by its ID and returns status (Pending/"
            "Approved/Denied), amount and procedure. Use ONLY when the "
            "question contains a claim ID like C1001. Input: the claim ID."
        ),
    ),
    Tool(
        name="get_plan_details",
        func=plan_shim,
        description=(
            "Returns a plan's facts: name, monthly premium, annual "
            "deductible, copay percentage. Use for questions about a plan's "
            "prices or terms, e.g. 'what is P101's deductible'. Input: the "
            "plan ID, e.g. 'P102'. Does NOT say whether procedures are "
            "covered — that is check_coverage."
        ),
    ),
    Tool(
        name="estimate_out_of_pocket_cost",
        func=cost_shim,
        description=(
            "Estimates the DOLLAR amount a member pays for a procedure on a "
            "plan (uses coverage + copay). Use for 'how much will X cost me' "
            "questions. Input: procedure and plan ID, e.g. 'x-ray, P101'."
        ),
    ),
]


# ---- Step 3: the ReAct agent — the brain over the toolbox ---------
# langchain 1.x moved the classic pair to langchain-classic:
#   python -m pip install langchain-classic
from langchain_classic.agents import AgentExecutor, create_react_agent
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI

MODEL = "llama3.2:3b"                       # same tag as rag_chatbot.py

llm = ChatOpenAI(
    model=MODEL,
    base_url="http://localhost:11434/v1",   # local Ollama, OpenAI-compatible
    api_key="ollama",                       # dummy — Ollama ignores it
    temperature=0,                          # agents need determinism, not flair
)

# Classic ReAct prompt, defined inline (no hub download, no network dep).
# The {tools} block is where our Step-2 descriptions do their routing work.
REACT_PROMPT = PromptTemplate.from_template(
    """You are a careful health-insurance coverage support agent.
Answer the member's question using ONLY the tools below. Never invent
plan facts, coverage decisions, claim statuses, or dollar amounts.

You have access to the following tools:

{tools}

Use this format EXACTLY:

Question: the input question you must answer
Thought: think about what to do next
Action: the tool to use, one of [{tool_names}]
Action Input: the input to the tool
Observation: the tool's result
... (Thought/Action/Action Input/Observation can repeat)
Thought: I now know the final answer
Final Answer: the answer to the member's question

If a tool returns an error, read it, fix your Action Input, and try
again. If the tools cannot answer the question, say so in the Final
Answer instead of guessing.

IMPORTANT: answer ONLY the question at the bottom. After an
Observation that answers it, do not call any tool again — reply with
exactly:
Thought: I now know the final answer
Final Answer: <your answer here>

Question: {input}
Thought:{agent_scratchpad}"""
)

agent = create_react_agent(llm=llm, tools=AGENT_TOOLS, prompt=REACT_PROMPT)
# NOTE: a "Question:" stop-sequence was tried against the echo loop — it
# zeroed generation entirely on cost questions (the model's first tokens
# ARE the echo). Removed; the deterministic rescue absorbs echo loops.

executor = AgentExecutor(
    agent=agent,
    tools=AGENT_TOOLS,
    verbose=True,                  # mission: read the traces
    handle_parsing_errors=(        # instructive, not just "invalid" — the
        "Invalid format. Reply with EXACTLY two lines and nothing else:\n"
        "Action: <one tool name from the list>\n"
        "Action Input: <the input>"
    ),                             # generic bounce taught the model nothing (Q4)
    max_iterations=3,              # the answer lives at step 1-2
    return_intermediate_steps=True,  # capture traces for agent_traces.md
)


def _format_final(tool: str, action_input: str, observation: str) -> str | None:
    """Deterministic exit: the tool result IS the answer — turning validated
    JSON into a sentence is string work, not model work. (The LLM rescue was
    tried first and llama3.2 apologized at a two-key JSON. Cut from the exit.)
    """
    try:
        data = json.loads(observation)
    except (TypeError, ValueError):
        return None
    if "error" in data:
        return (f"I couldn't complete that lookup: {data['error']}")
    if tool == "check_coverage":
        c = data.get("covered")
        base = f"{data.get('procedure', 'that procedure')} under plan {data.get('plan_id', '?')}"
        if c is True:
            return f"Yes — {base} is covered."
        if c is False:
            return f"No — {base} is not covered."
        return (f"Coverage for {base} is not listed in our records — "
                "please contact Member Support.")
    if tool == "get_claim_status":
        return (f"Claim {data.get('claim_id', '?')} is {data.get('status', 'unknown')} — "
                f"${data.get('claim_amount', 0):,.2f} for {data.get('procedure', '?')} "
                f"(member {data.get('member_id', '?')}).")
    if tool == "get_plan_details":
        m = PLAN_RE.search(action_input or "")
        pid = f" ({m.group(0).upper()})" if m else ""
        return (f"{data.get('plan_name', 'That plan')}{pid}: "
                f"${data.get('monthly_premium', 0):,.0f}/month premium, "
                f"${data.get('annual_deductible', 0):,.0f} annual deductible, "
                f"{data.get('copay_pct', 0):.0f}% copay.")
    if tool == "estimate_out_of_pocket_cost":
        if data.get("covered") is False:
            return (f"{data.get('procedure', 'That procedure')} is not covered on plan "
                    f"{data.get('plan_id', '?')} — estimated out-of-pocket is the full "
                    f"${data.get('estimated_out_of_pocket', 0):,.2f}. ({data.get('note', '')})")
        return (f"Estimated out-of-pocket for {data.get('procedure', '?')} on plan "
                f"{data.get('plan_id', '?')}: ${data.get('estimated_out_of_pocket', 0):,.2f} "
                f"({data.get('copay_pct', 0):.0f}% copay share of "
                f"${data.get('procedure_cost', 0):,.0f}).")
    return None


def ask_agent(question: str) -> dict:
    """One agented question. Returns {input, output, intermediate_steps}.

    Day 21 finding #1: llama3.2 picks the right tool and gets the right
    Observation, but often cannot produce the 'Final Answer:' exit. The
    framework's own rescue (early_stopping_method='generate') does not
    exist for runnable agents in langchain-classic 1.x — so this is OUR
    fire escape: if the executor stops without an answer but the trace
    holds a successful observation, one plain LLM call turns the last
    observation into the final answer. No ReAct format to fumble.
    """
    result = executor.invoke({"input": question})
    output = result.get("output", "")
    steps = result.get("intermediate_steps") or []
    needs_rescue = (output.startswith("Agent stopped")
                    or "cannot provide an answer" in output.lower())
    if needs_rescue and steps:
        known = {t.name for t in AGENT_TOOLS}
        # walk the trace backwards: parsing-error recoveries are logged as
        # steps too (tool='_Exception'), so the REAL observation may not be
        # last — take the most recent step from an actual tool that formats
        for action, observation in reversed(steps):
            if action.tool not in known:
                continue
            formatted = _format_final(action.tool, str(action.tool_input),
                                      observation)
            if formatted:
                result["output"] = formatted
                result["rescued"] = True  # marked for agent_traces.md honesty
                break
    return result


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        # Step 3 live test:  python langchain_agent.py "your question"
        result = ask_agent(" ".join(sys.argv[1:]))
        print("\nFINAL:", result["output"])
    else:
        # Step 2 smoke test: shims + validation, no LLM involved
        print(coverage_shim("P101, x-ray"))
        print(claim_shim("what about C1001?"))
        print(plan_shim("P102"))
        print(cost_shim("mri scan, P103"))
        print(claim_shim("no id here"))