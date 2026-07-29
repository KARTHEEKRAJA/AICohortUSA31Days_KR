"""Day 13 — Tool calling: schemas + execution loop + Pydantic validation."""
import json
import sqlite3
from typing import Literal, Union

from openai import OpenAI
from pydantic import BaseModel, Field, ValidationError

# ---------------------------------------------------------------
# Step 1: JSON schemas for 4 tools (OpenAI tool-calling format)
# ---------------------------------------------------------------

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "check_coverage",
            "description": (
                "Check whether a specific medical procedure is covered under a "
                "given plan. Use when the member asks 'is X covered' for a "
                "named plan."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "plan_id": {
                        "type": "string",
                        "description": "Plan ID, e.g. P101 (Gold PPO), P102 (Silver HMO), P103 (Bronze HMO)",
                    },
                    "procedure": {
                        "type": "string",
                        "description": "The medical procedure to check, e.g. 'X-ray', 'physical therapy'",
                    },
                },
                "required": ["plan_id", "procedure"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_claim_status",
            "description": (
                "Look up the status of a specific claim by its claim ID. Use "
                "when the member asks about a claim's progress, e.g. 'status of "
                "claim C1001'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "claim_id": {
                        "type": "string",
                        "description": "Claim ID, format C followed by digits, e.g. C1001",
                    },
                },
                "required": ["claim_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_plan_details",
            "description": (
                "Get premium, deductible, and copay details for a plan. Use for "
                "questions about plan costs, deductibles, premiums, or copays."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "plan_id": {
                        "type": "string",
                        "description": "Plan ID, e.g. P101, P102, P103",
                    },
                },
                "required": ["plan_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "estimate_out_of_pocket_cost",
            "description": (
                "Estimate a member's out-of-pocket cost for a procedure under a "
                "plan, combining deductible and copay. Use when the member asks "
                "'how much will X cost me'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "procedure": {
                        "type": "string",
                        "description": "The medical procedure, e.g. 'MRI scan'",
                    },
                    "plan_id": {
                        "type": "string",
                        "description": "Plan ID, e.g. P102",
                    },
                },
                "required": ["procedure", "plan_id"],
            },
        },
    },
]

# ---------------------------------------------------------------
# Step 2: LLM client + system prompt (Day 12 Variant E, adapted)
# ---------------------------------------------------------------
client = OpenAI(
    base_url="http://localhost:11434/v1",
    api_key="ollama",
)
MODEL = "llama3.2:3b"

SYSTEM_PROMPT = """You are a helpful benefits information assistant.

RULES:
1. To answer questions about coverage, claims, plan details, or costs, call
   the appropriate tool. Never invent plan facts, dollar amounts, or claim
   statuses — facts come only from tool results.
2. If a required detail is missing (e.g. which plan the member means), ask
   the member instead of guessing.
3. If a tool returns no data or an error, say you don't have that
   information and suggest contacting Member Support.
4. Never give medical advice. If asked whether a treatment is right for the
   member, refuse kindly and refer them to a licensed healthcare provider.
5. End every final answer with: "— Benefits information only, not medical
   advice."
6. Only call a tool when the member's question actually requires plan,
   claim, coverage, or cost data. For greetings or general questions,
   reply with text and briefly describe what you can help with.
"""


def ask_with_tools(question: str):
    """Single turn: send a question with the tool menu; return raw decision."""
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": question},
        ],
        tools=TOOLS,
        temperature=0.2,
    )
    return resp.choices[0].message


# ---------------------------------------------------------------
# Step 3: tool implementations
# ---------------------------------------------------------------
DB_PATH = "coverage.db"

# Mock coverage table — coverage.db has no procedure-level coverage data,
# so per the mission ("mock data is fine") coverage rules are mocked.
MOCK_COVERAGE = {
    "P101": {"x-ray": True, "surgery": True, "physical therapy": True,  "mri scan": True},
    "P102": {"x-ray": True, "surgery": True, "physical therapy": False, "mri scan": True},
    "P103": {"x-ray": True, "surgery": False, "physical therapy": False, "mri scan": False},
}
MOCK_PROCEDURE_COST = {"x-ray": 250, "surgery": 5000, "physical therapy": 120, "mri scan": 1400}


def _plan_row(plan_id: str) -> dict | None:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT plan_name, monthly_premium, annual_deductible, copay_pct "
        "FROM plans WHERE plan_id = ?", (plan_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def check_coverage(plan_id: str, procedure: str) -> dict:
    plan = MOCK_COVERAGE.get(plan_id)
    if plan is None:
        return {"error": f"unknown plan_id {plan_id}"}
    covered = plan.get(procedure.lower().strip())
    if covered is None:
        return {"plan_id": plan_id, "procedure": procedure, "covered": "unknown",
                "note": "procedure not in coverage table"}
    return {"plan_id": plan_id, "procedure": procedure, "covered": covered}


def get_claim_status(claim_id: str) -> dict:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT claim_id, member_id, procedure, claim_amount, status "
        "FROM claims WHERE claim_id = ?", (claim_id,)).fetchone()
    conn.close()
    return dict(row) if row else {"error": f"claim {claim_id} not found"}


def get_plan_details(plan_id: str) -> dict:
    row = _plan_row(plan_id)
    return row if row else {"error": f"plan {plan_id} not found"}


def estimate_out_of_pocket_cost(procedure: str, plan_id: str) -> dict:
    plan = _plan_row(plan_id)
    cost = MOCK_PROCEDURE_COST.get(procedure.lower().strip())
    if plan is None:
        return {"error": f"plan {plan_id} not found"}
    if cost is None:
        return {"error": f"no cost data for procedure '{procedure}'"}
    coverage = check_coverage(plan_id, procedure)
    if coverage.get("covered") is False:
        return {"procedure": procedure, "plan_id": plan_id, "covered": False,
                "estimated_out_of_pocket": cost,
                "note": "not covered — member pays full cost (estimate)"}
    copay_amount = round(cost * plan["copay_pct"] / 100, 2)
    return {"procedure": procedure, "plan_id": plan_id, "covered": True,
            "procedure_cost": cost, "copay_pct": plan["copay_pct"],
            "estimated_out_of_pocket": copay_amount,
            "note": "estimate: copay share after deductible is met (mock logic)"}


TOOL_FUNCTIONS = {
    "check_coverage": check_coverage,
    "get_claim_status": get_claim_status,
    "get_plan_details": get_plan_details,
    "estimate_out_of_pocket_cost": estimate_out_of_pocket_cost,
}

# ---------------------------------------------------------------
# Step 4: Pydantic models — validate every tool output before
#          it is returned to the model
# ---------------------------------------------------------------


class ToolError(BaseModel):
    error: str


class CoverageResult(BaseModel):
    plan_id: str = Field(pattern=r"^P\d{3}$")
    procedure: str = Field(min_length=2)
    covered: Union[bool, Literal["unknown"]]
    note: str | None = None


class ClaimStatus(BaseModel):
    claim_id: str = Field(pattern=r"^C\d+$")
    member_id: str = Field(pattern=r"^M\d{4}$")
    procedure: str
    claim_amount: float = Field(ge=0)
    status: Literal["Pending", "Approved", "Denied"]


class PlanDetails(BaseModel):
    plan_name: str
    monthly_premium: float = Field(gt=0)
    annual_deductible: float = Field(ge=0)
    copay_pct: float = Field(ge=0, le=100)


class CostEstimate(BaseModel):
    procedure: str
    plan_id: str = Field(pattern=r"^P\d{3}$")
    covered: bool
    estimated_out_of_pocket: float = Field(ge=0)
    procedure_cost: float | None = Field(default=None, ge=0)
    copay_pct: float | None = Field(default=None, ge=0, le=100)
    note: str | None = None


TOOL_OUTPUT_MODELS = {
    "check_coverage": CoverageResult,
    "get_claim_status": ClaimStatus,
    "get_plan_details": PlanDetails,
    "estimate_out_of_pocket_cost": CostEstimate,
}


def validate_tool_result(tool_name: str, result: dict) -> dict:
    """Validate a tool's raw output. Errors pass through as ToolError;
    anything malformed is replaced by a safe error dict."""
    if "error" in result:
        return ToolError.model_validate(result).model_dump()
    model = TOOL_OUTPUT_MODELS.get(tool_name)
    if model is None:
        return {"error": f"no output model for tool {tool_name}"}
    try:
        return model.model_validate(result).model_dump(exclude_none=True)
    except ValidationError as e:
        # Never let malformed data reach the LLM — degrade to an honest error
        return {"error": f"tool '{tool_name}' returned invalid data: "
                         f"{e.error_count()} validation error(s)"}


# ---------------------------------------------------------------
# The execution loop (Step 3 + Step 4 wired together)
# ---------------------------------------------------------------
def run_conversation(question: str, max_rounds: int = 3) -> dict:
    """Full loop: question -> tool call(s) -> execute -> validate -> answer."""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ]
    calls_log = []

    for _ in range(max_rounds):
        resp = client.chat.completions.create(
            model=MODEL, messages=messages, tools=TOOLS, temperature=0.2)
        msg = resp.choices[0].message

        if not msg.tool_calls:                      # final text answer
            return {"question": question, "answer": (msg.content or "").strip(),
                    "tool_calls": calls_log}

        messages.append(msg)                        # keep the model's call in history
        for tc in msg.tool_calls:
            fn_name = tc.function.name
            fn = TOOL_FUNCTIONS.get(fn_name)
            try:
                args = json.loads(tc.function.arguments)
                if fn is None:
                    result = {"error": f"unknown tool {fn_name}"}
                else:
                    result = fn(**args)
            except json.JSONDecodeError:
                args = tc.function.arguments        # keep raw string for the log
                result = {"error": f"model produced invalid JSON arguments for {fn_name}"}
            except TypeError as e:
                # wrong/unexpected argument names, e.g. {"f": "get_plan_details"}
                result = {"error": f"invalid arguments for {fn_name}: {e}"}
            result = validate_tool_result(fn_name, result)          # <- Step 4
            calls_log.append({"tool": fn_name, "args": args, "result": result})
            messages.append({                       # feed result back
                "role": "tool",
                "tool_call_id": tc.id,
                "content": json.dumps(result),
            })

    return {"question": question, "answer": "(no final answer after max rounds)",
            "tool_calls": calls_log}


# ---------------------------------------------------------------
# Step 5: tool-selection test battery
# ---------------------------------------------------------------
SELECTION_TESTS = [
    # (test id, question, expected tool or None)
    ("S1", "What's the monthly premium for the Gold plan?",            "get_plan_details"),
    ("S2", "Is an X-ray covered under the Bronze plan?",               "check_coverage"),
    ("S3", "What's the status of claim C1002?",                        "get_claim_status"),
    ("S4", "How much would surgery cost me out of pocket on the Gold plan?", "estimate_out_of_pocket_cost"),
    ("S5", "What's the deductible on the Silver plan?",                "get_plan_details"),
    ("S6", "Thanks for your help, have a great day!",                  None),
]


def run_selection_tests():
    """5 tool questions + 1 no-tool question; confirm selection each time."""
    results = []
    for tid, q, expected in SELECTION_TESTS:
        msg = ask_with_tools(q)
        if msg.tool_calls:
            actual = msg.tool_calls[0].function.name
            raw_args = msg.tool_calls[0].function.arguments
        else:
            actual, raw_args = None, ""
        ok = actual == expected
        results.append({"id": tid, "question": q, "expected": expected,
                        "actual": actual, "args": raw_args, "pass": ok})
        exp_s = expected or "(no tool)"
        act_s = actual or "(no tool)"
        mark = "PASS" if ok else "FAIL"
        print(f"{tid} [{mark}] expected={exp_s:<28} actual={act_s:<28} {raw_args[:60]}")
    passed = sum(r["pass"] for r in results)
    print(f"\nSelection score: {passed}/{len(results)}")
    return results


# ---------------------------------------------------------------
# Step 6: audit log — every tool call written to tool_call_log.md
# ---------------------------------------------------------------
LOG_QUESTIONS = [
    "What's the deductible on the Silver plan?",
    "Is physical therapy covered under the Silver plan?",
    "What's the status of claim C1001?",
    "How much would an MRI scan cost me on the Bronze plan?",
    "Is an X-ray covered under the Bronze plan?",
    "Hello, what can you help me with?",
]


def write_tool_call_log(out_path: str = "tool_call_log.md"):
    lines = [
        "# Tool Call Log — Day 13",
        "",
        "**System:** llama3.2:3b via local Ollama · 4 tools (JSON schemas) · "
        "execution loop with error guards · Pydantic output validation.",
        "**Purpose:** debugging + audit trail — every tool invocation recorded "
        "with tool, arguments, and validated result.",
        "",
        "---",
        "",
    ]
    for q in LOG_QUESTIONS:
        r = run_conversation(q)
        print(f"logged: {q}  ({len(r['tool_calls'])} tool call(s))")
        lines += [f"## Q: {q}", ""]
        if not r["tool_calls"]:
            lines.append("*(no tool called — answered in text)*")
        for i, c in enumerate(r["tool_calls"], 1):
            lines += [
                f"**Call {i}: `{c['tool']}`**",
                "",
                f"- **Arguments:** `{json.dumps(c['args'])}`",
                f"- **Result:** `{json.dumps(c['result'])}`",
                "",
            ]
        lines += [f"**Final answer:** {r['answer']}", "", "---", ""]
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    # --- Step 1 check: schemas well-formed ---
    print(f"{len(TOOLS)} tools defined:")
    for t in TOOLS:
        fn = t["function"]
        params = list(fn["parameters"]["properties"].keys())
        print(f"  - {fn['name']}({', '.join(params)})")
    json.dumps(TOOLS)
    print("Schemas serialize cleanly \u2713\n")

    # --- Step 2 check: raw routing decisions (single turn, no execution) ---
    print("#" * 60)
    print("# STEP 2 \u2014 ROUTING DECISIONS")
    print("#" * 60)
    for q in [
        "What's the deductible on the Silver plan?",
        "Is physical therapy covered under the Gold plan?",
        "What's the status of claim C1001?",
        "Hello, what can you help me with?",
    ]:
        msg = ask_with_tools(q)
        print("=" * 60)
        print(f"Q: {q}")
        if msg.tool_calls:
            for tc in msg.tool_calls:
                print(f"  TOOL CALL -> {tc.function.name}({tc.function.arguments})")
        else:
            print(f"  TEXT -> {(msg.content or '')[:120]}")

    # --- Step 3 check: full execution loop with real DB + mocks ---
    print("\n" + "#" * 60)
    print("# STEP 3 \u2014 FULL EXECUTION LOOP")
    print("#" * 60)
    for q in [
        "What's the deductible on the Silver plan?",
        "Is physical therapy covered under the Silver plan?",      # mock: NOT covered
        "What's the status of claim C1001?",
        "How much would an MRI scan cost me on the Bronze plan?",  # not covered -> full cost
    ]:
        r = run_conversation(q)
        print("=" * 60)
        print(f"Q: {q}")
        for c in r["tool_calls"]:
            print(f"  \u2699 {c['tool']}({c['args']}) -> {c['result']}")
        print(f"A: {r['answer']}")

    # --- Step 4 check: validation catches malformed tool output ---
    print("\n" + "#" * 60)
    print("# STEP 4 \u2014 PYDANTIC VALIDATION")
    print("#" * 60)
    good = {"plan_name": "Silver HMO", "monthly_premium": 300,
            "annual_deductible": 1500, "copay_pct": 20}
    bad  = {"plan_name": "Silver HMO", "monthly_premium": -50,
            "annual_deductible": "fifteen hundred", "copay_pct": 250}
    print("valid plan row   ->", validate_tool_result("get_plan_details", good))
    print("malformed row    ->", validate_tool_result("get_plan_details", bad))
    r = run_conversation("What's the deductible on the Silver plan?")
    print("live loop intact ->", r["answer"][:80])

    # --- hardened greeting: garbage tool calls now degrade gracefully ---
    r = run_conversation("Hello, what can you help me with?")
    print("greeting hardened ->", r["tool_calls"], "|", r["answer"][:80])

    # --- Step 5 check: tool-selection battery ---
    print("\n" + "#" * 60)
    print("# STEP 5 \u2014 TOOL SELECTION TESTS")
    print("#" * 60)
    run_selection_tests()

    # --- Step 6: generate the audit log ---
    print("\n" + "#" * 60)
    print("# STEP 6 \u2014 WRITING TOOL_CALL_LOG.MD")
    print("#" * 60)
    write_tool_call_log()