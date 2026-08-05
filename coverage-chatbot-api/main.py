import re
import sqlite3
import tiktoken   # Day 20 Step 4: token budgeting (deepened Day 26)
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# make repo-root modules importable from inside coverage-chatbot-api/
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import json

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from rag_chatbot import (retrieve_and_answer, stream_answer,   # Day 11 + Day 18
                         summarize_history)                    # Day 20 Step 4

import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("coverage-api")

app = FastAPI(title="Coverage Chatbot API")

# ---- Day 16 Step 3: session store ----
# In-memory, keyed by session_id. Restart wipes it — acceptable for the
# program; SQLite is the drop-in production path (same interface).
SESSIONS: dict[str, dict] = {}

# ---- Day 20 Step 1: persistent conversation memory (SQLite) ----
DB_PATH = "coverage.db"          # uvicorn runs from repo root (3-window ritual)


def _db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_conversations_table() -> None:
    """Mission schema: session_id, role, content, timestamp.
    id autoincrement guarantees turn ordering (timestamps can collide
    at 1s resolution); CHECK on role is Day-13 defense-in-depth; the
    index keeps per-session loads fast as the table grows forever."""
    with _db() as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS conversations ("
            "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  session_id TEXT NOT NULL,"
            "  role TEXT NOT NULL CHECK(role IN ('user','assistant')),"
            "  content TEXT NOT NULL,"
            "  timestamp TEXT NOT NULL"          # ISO-8601 UTC
            ")"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_conv_session "
            "ON conversations(session_id, id)"
        )


def save_turn(session_id: str, role: str, content: str) -> None:
    with _db() as conn:
        conn.execute(
            "INSERT INTO conversations (session_id, role, content, timestamp) "
            "VALUES (?, ?, ?, ?)",
            (session_id, role, content,
             datetime.now(timezone.utc).isoformat(timespec="seconds")),
        )


def load_history(session_id: str, limit: int = 50) -> list[dict]:
    with _db() as conn:
        rows = conn.execute(
            "SELECT role, content, timestamp FROM conversations "
            "WHERE session_id = ? ORDER BY id DESC LIMIT ?",
            (session_id, limit),
        ).fetchall()
    return [dict(r) for r in reversed(rows)]     # chronological


def init_summaries_table() -> None:
    """Day 20 Step 4: summaries live NEXT TO raw turns, never instead of
    them. covered_through_id marks which turns the summary replaces in
    the PROMPT — the audit trail in conversations stays intact."""
    with _db() as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS conversation_summaries ("
            "  session_id TEXT PRIMARY KEY,"
            "  summary TEXT NOT NULL,"
            "  covered_through_id INTEGER NOT NULL,"
            "  updated_at TEXT NOT NULL"
            ")"
        )


def load_summary(session_id: str) -> tuple[str | None, int]:
    with _db() as conn:
        row = conn.execute(
            "SELECT summary, covered_through_id FROM conversation_summaries "
            "WHERE session_id = ?", (session_id,)).fetchone()
    return (row["summary"], row["covered_through_id"]) if row else (None, 0)


def save_summary(session_id: str, summary: str, covered_through_id: int) -> None:
    with _db() as conn:
        conn.execute(
            "INSERT INTO conversation_summaries "
            "(session_id, summary, covered_through_id, updated_at) "
            "VALUES (?, ?, ?, ?) "
            "ON CONFLICT(session_id) DO UPDATE SET summary=excluded.summary, "
            "covered_through_id=excluded.covered_through_id, "
            "updated_at=excluded.updated_at",
            (session_id, summary, covered_through_id,
             datetime.now(timezone.utc).isoformat(timespec="seconds")),
        )


def load_active_rows(session_id: str, after_id: int) -> list[dict]:
    """Turns NOT yet covered by the summary — with ids, chronological."""
    with _db() as conn:
        rows = conn.execute(
            "SELECT id, role, content FROM conversations "
            "WHERE session_id = ? AND id > ? ORDER BY id",
            (session_id, after_id)).fetchall()
    return [dict(r) for r in rows]


_ENC = None          # lazy: tiktoken fetches its BPE file on first use;
                     # a network hiccup must not stop uvicorn from booting


def count_tokens(text: str) -> int:
    """cl100k_base as proxy (qwen has no tiktoken map). Falls back to
    the ~4-chars-per-token estimate if the encoding is unavailable."""
    global _ENC
    if _ENC is None:
        try:
            _ENC = tiktoken.get_encoding("cl100k_base")
        except Exception:
            return max(1, len(text) // 4)
    return len(_ENC.encode(text))


TOKEN_BUDGET = 2000               # mission: summarize once history exceeds ~2000


init_conversations_table()       # at import — table exists before first request
init_summaries_table()
# ------------------------------------------------------------------

# ---- Day 20 Step 3: server-side plan memory + history injection ----
PLAN_LABELS = {"P101": "Gold PPO (P101)", "P102": "Silver HMO (P102)",
               "P103": "Bronze HMO (P103)"}
PLAN_MENTIONS = {"gold": "P101", "p101": "P101", "silver": "P102",
                 "p102": "P102", "bronze": "P103", "p103": "P103"}
# injection v4 = Day-19 v3 rules, moved server-side where memory lives
SKIP_INJECT = ("gold", "silver", "bronze", "p101", "p102", "p103",
               "plans do you", "what plans", "which plans", "all plans",
               "plans are", "plans available", "available plans", "offer",
               "compare", "comparison", "the plans", "difference between")
LEGACY_TAG = re.compile(r"^\[Member's plan:[^\]]*\]\s*")


def format_history(rows: list[dict]) -> str:
    """Mission Step 3: last-N turns as prompt text. Legacy client-side
    plan tags are stripped — Day-20 finding: memory recorded decorated
    messages, and re-feeding old tags would pin a stale plan forever."""
    lines = []
    for r in rows:
        content = LEGACY_TAG.sub("", r["content"]).strip()
        lines.append(f"{r['role']}: {content}")
    return "\n".join(lines)
# --------------------------------------------------------------------


def get_session(session_id: str, member_id: str) -> dict:
    """Fetch or create the conversation state for this session."""
    if session_id not in SESSIONS:
        SESSIONS[session_id] = {
            "member_id": member_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "turns": [],          # each: {role, content, ts, elapsed_ms}
        }
    return SESSIONS[session_id]


def add_turn(session: dict, role: str, content: str, elapsed_ms: int | None = None):
    turn = {"role": role, "content": content,
            "ts": datetime.now(timezone.utc).isoformat()}
    if elapsed_ms is not None:
        turn["elapsed_ms"] = elapsed_ms
    session["turns"].append(turn)


def numbers_grounded(answer: str, context: str) -> bool:
    """Hallucination guard: every numeric figure in the answer must appear as
    a whole number in the retrieved context (set comparison — no substring
    false-passes like '25' inside '250'). Catches invented copays, premiums,
    phone numbers — Day-13 philosophy (validate outputs) applied to generation."""
    # (?<![A-Za-z\d]) / (?![A-Za-z]) : skip digits glued to letters — P102,
    # C1001, M1001 are IDENTIFIERS, not numeric facts (first live false
    # positive: guard flagged "plan ID P102" because the SQL row lacked
    # plan_id — fixed on both sides, Day 18)
    num_re = r"(?<![A-Za-z\d])\d[\d,]*(?:\.\d+)?(?![A-Za-z])"
    figures = re.findall(num_re, answer)
    if not figures:
        return True                      # no numeric claims -> nothing to verify
    ctx_nums = {n.replace(",", "") for n in re.findall(num_re, context)}
    return all(f.replace(",", "") in ctx_nums for f in figures)


REFUSAL_MSG = ("I don't have that information in my records. "
               "Please contact Member Support for a definitive answer.")


@app.get("/health")
def health():
    return {"status": "ok"}


# ---- Day 16 Step 1: POST /chat ----
class ChatRequest(BaseModel):
    session_id: str = Field(min_length=1)
    member_id: str = Field(pattern=r"^M\d{4}$")     # Day-13 discipline at the front door
    message: str = Field(min_length=1, max_length=2000)
    plan_id: str | None = Field(default=None, pattern=r"^P\d{3}$")   # Day 20 Step 3


class ChatResponse(BaseModel):
    session_id: str
    answer: str
    turn_count: int
    sources: list[str] = []
    elapsed_ms: int


def _sse(payload: dict) -> str:
    """Format one Server-Sent Events data line."""
    return f"data: {json.dumps(payload)}\n\n"


@app.post("/chat")
def chat(req: ChatRequest):
    """Day 18: /chat now streams Server-Sent Events.

    Step-2 design — true token streaming: SDK chunks flow to the client as
    they're generated. Gates (retrieval-based) still run pre-stream; the
    numeric guard runs POST-HOC on the accumulated answer and emits a
    "guard" correction event if it fires — the streaming trade-off,
    documented in streaming_notes.md. New metric: ttft_ms.
    """
    def event_stream():
        t0 = time.perf_counter()
        t_first = None                       # time-to-first-token (today's metric)

        session = get_session(req.session_id, req.member_id)     # state in
        # Day 20 Steps 3+4: history loads BEFORE this turn is saved.
        # Budget pipeline: summary covers old turns; active turns are
        # counted; past ~2000 tokens the oldest HALF collapses into the
        # summary via ONE LLM call. Raw rows are never deleted.
        summary, covered_id = load_summary(req.session_id)
        active = load_active_rows(req.session_id, covered_id)
        hist_tokens = count_tokens(
            (summary or "") + format_history(active))
        summarized_now = False
        if hist_tokens > TOKEN_BUDGET and len(active) >= 4:
            half = active[: len(active) // 2]
            summary = summarize_history(format_history(half), summary)
            save_summary(req.session_id, summary, half[-1]["id"])
            active = active[len(active) // 2 :]
            summarized_now = True
        recent = active[-10:]                 # mission Step 3: last N=10
        history_text = format_history(recent)
        if summary:
            history_text = (f"Summary of earlier conversation: {summary}\n"
                            + history_text)
        hist_tokens_after = count_tokens(history_text)

        # plan memory: sidebar field wins; else a plan named in the message
        if req.plan_id:
            session["plan_id"] = req.plan_id
        else:
            for word, pid in PLAN_MENTIONS.items():
                if word in req.message.lower():
                    session["plan_id"] = pid
                    break

        # injection v4 (server-side): remembered plan enters the retrieval
        # question unless the message names a plan / is cross-plan (v3 rules)
        plan_id = session.get("plan_id")
        msg_l = req.message.lower()
        if plan_id and not any(w in msg_l for w in SKIP_INJECT):
            retrieval_q = f"[Member's plan: {PLAN_LABELS[plan_id]}] {req.message}"
        else:
            retrieval_q = req.message

        add_turn(session, "user", req.message)
        save_turn(req.session_id, "user", req.message)      # Day 20: persist RAW message

        yield _sse({"type": "start", "session_id": req.session_id})

        answer, sources, context, status = "", [], "", "ok"
        citations = []                       # Day 19: chunk-ID provenance
        cards = []                           # Day 19: rich cards
        try:
            # ---- Day 18 Step 2: TRUE token streaming from the LLM SDK ----
            # Gates run pre-stream inside stream_answer (retrieval-based).
            for ev in stream_answer(retrieval_q, history_text=history_text or None):
                if ev["kind"] == "meta":
                    sources = ev["sources"][:5]
                    context = ev["context"]
                    citations = ev.get("citations", [])
                    cards = ev.get("cards", [])
                    if ev["gate"]:
                        status = ev["gate"]
                elif ev["kind"] == "token":
                    if t_first is None:
                        t_first = int((time.perf_counter() - t0) * 1000)
                    yield _sse({"type": "token", "text": ev["text"]})
                elif ev["kind"] == "final":
                    answer = ev["answer"]

            # ---- numeric guard: POST-HOC under streaming. Tokens already
            # left the server — if ungrounded, emit a correction event the
            # UI uses to REPLACE the streamed text, and record the refusal.
            # The member may have glimpsed it: streaming's honest cost. ----
            # Day 19 fix: numbers echoed from the QUESTION are grounded too
            # ("under $400" -> answer may say $400; context only has 150/300)
            # Day 20: history-sourced numbers are grounded too — the bot may
            # repeat figures it already told this member (FP class #3 averted)
            if (status == "ok" and context
                    and not numbers_grounded(answer, context + "\n" + req.message
                                             + "\n" + history_text)):
                log.warning(f"ungrounded numbers session={req.session_id} "
                            f"answer={answer[:120]!r}")
                answer = REFUSAL_MSG
                status = "ungrounded_numbers"
                # Day 19 fix: a refused answer must not ship rich data —
                # cards/citations bypassing the guard contradicts the refusal
                cards, citations = [], []
                yield _sse({"type": "guard", "text": REFUSAL_MSG})
        except Exception as e:                  # LLM down, Chroma error, etc.
            log.error(f"pipeline failure session={req.session_id}: "
                      f"{type(e).__name__}: {e}")
            answer = ("I'm having trouble answering right now. Please try "
                      "again in a moment, or contact Member Support.")
            status = "error"
            yield _sse({"type": "token", "text": answer})

        elapsed = int((time.perf_counter() - t0) * 1000)
        add_turn(session, "assistant", answer, elapsed_ms=elapsed)   # state out
        # Day 20 Step 2: persist the FINAL answer — post-guard, so memory
        # records what the member actually saw (refusals, not blocked text)
        save_turn(req.session_id, "assistant", answer)

        log.info(f"chat session={req.session_id} member={req.member_id} "
                 f"status={status} ttft_ms={t_first} elapsed_ms={elapsed} "
                 f"turns={len(session['turns'])} "
                 f"hist_tokens={hist_tokens} ctx_tokens={hist_tokens_after} "
                 f"summarized={summarized_now} plan={session.get('plan_id')}")

        yield _sse({"type": "done", "status": status, "sources": sources,
                    "citations": citations, "cards": cards,
                    "turn_count": len(session["turns"]),
                    "ttft_ms": t_first, "elapsed_ms": elapsed})

    return StreamingResponse(event_stream(), media_type="text/event-stream")


# ---- Day 16 Step 4: GET /history/{session_id} ----
class HistoryResponse(BaseModel):
    session_id: str
    member_id: str
    created_at: str
    turn_count: int
    turns: list[dict]


@app.get("/history/{session_id}", response_model=HistoryResponse)
def history(session_id: str) -> HistoryResponse:
    session = SESSIONS.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"session '{session_id}' not found")
    return HistoryResponse(
        session_id=session_id,
        member_id=session["member_id"],
        created_at=session["created_at"],
        turn_count=len(session["turns"]),
        turns=session["turns"],
    )