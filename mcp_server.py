"""Day 23 — MCP server: coverage tools for desktop AI clients.

Step 2: ONE tool (check_coverage) per the mission — internally Day 10's
vector_lookup() for policy context + the Day 4 plans table for plan
facts + Day 13's tested coverage decision.

Engineering notes (scars applied):
- Claude Desktop launches servers from an UNKNOWN working directory, so
  we chdir to this script's folder BEFORE importing retrieval_engine
  (its chroma client opens the relative path "chroma_db").
- stdout belongs to the MCP protocol — nothing may print to it. Any
  diagnostics go to stderr.
- The tool is ASYNC so it runs on the event loop's main thread: Day 22
  taught us chromadb's Rust bindings abort silently when queried from
  worker threads. Blocking the loop briefly is fine for a local demo.
"""
import json
import os
import sqlite3
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
os.chdir(BASE)                    # BEFORE heavy imports — paths resolve

from mcp.server.fastmcp import FastMCP        # noqa: E402

print("[mcp_server] loading retrieval engine...", file=sys.stderr)
from retrieval_engine import vector_lookup    # noqa: E402  (loads embedder)
from tool_calling_chatbot import (            # noqa: E402
    check_coverage as _decide_coverage,
    get_claim_status as _claim_status,
    validate_tool_result as _validate,
)
print("[mcp_server] ready", file=sys.stderr)

# Manifest (mission step: name · description · tool schema):
# - server name + description below; each tool's name comes from its
#   function name, its description from the docstring, and its JSON
#   schema is auto-derived from the typed signature by the SDK.
mcp = FastMCP(
    "coverage-tools",
    instructions=(
        "Health-insurance coverage tools for a demo member portal. "
        "Look up whether procedures are covered under plans P101 (Gold "
        "PPO), P102 (Silver HMO) and P103 (Bronze HMO), with plan facts "
        "and supporting policy passages. Data is mock/demo data."
    ),
)


def _plan_row(plan_id: str) -> dict | None:
    """Day 4 plans table, fresh connection per call (thread-agnostic)."""
    conn = sqlite3.connect(BASE / "coverage.db")
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT plan_id, plan_name, monthly_premium, "
            "annual_deductible, copay_pct FROM plans WHERE plan_id = ?",
            (plan_id.upper(),),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


@mcp.tool()
async def check_coverage(plan_id: str, procedure: str) -> str:
    """Check whether a medical procedure is covered under a specific
    health plan. Returns the coverage decision, the plan's key facts
    (premium, deductible, copay) and the most relevant policy passages.

    Args:
        plan_id: The plan ID, e.g. "P101" (Gold PPO), "P102" (Silver
            HMO) or "P103" (Bronze HMO).
        procedure: The medical procedure to check, e.g. "x-ray",
            "mri scan", "physical therapy".
    """
    plan = _plan_row(plan_id)
    if plan is None:
        return json.dumps({"error": f"unknown plan_id '{plan_id}' — "
                                    "valid: P101, P102, P103"})

    # Day 13's tested decision logic, Pydantic-validated
    decision = _validate("check_coverage",
                         _decide_coverage(plan_id.upper(), procedure))

    # Day 10's vector store, WITH Day 9's metadata filter: only this
    # plan's documents (or general ones) may serve as context. Finding:
    # unfiltered, the Gold SBC hitched onto P103 answers — and Claude
    # Desktop CAUGHT the mismatch and flagged it to the user.
    ptype = "PPO" if "PPO" in plan["plan_name"].upper() else "HMO"
    hits = vector_lookup(
        f"{plan['plan_name']} {procedure} coverage", n_results=2,
        where={"plan_type": {"$in": [ptype, "all"]}},
    )
    context = [
        {"id": h["id"], "section": h["section"],
         "plan_type": h["plan_type"], "text": h["text"][:300]}
        for h in hits
    ]

    return json.dumps({
        "decision": decision,
        "plan": plan,
        "policy_context": context,
    })


@mcp.tool()
async def get_claim_status(claim_id: str) -> str:
    """Look up the status of a submitted insurance claim by its ID.
    Returns the claim's status (Pending/Approved/Denied), amount,
    procedure and member. Says so honestly if the claim is not found.

    Args:
        claim_id: The claim ID, e.g. "C1001" or "C1002".
    """
    cid = claim_id.upper().replace(" ", "").replace("-", "")
    result = _validate("get_claim_status", _claim_status(cid))
    return json.dumps(result)


if __name__ == "__main__":
    mcp.run()          # stdio transport — silence on stdout is correct