import re
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

from rag_chatbot import retrieve_and_answer, stream_answer   # Day 11 pipeline + Day 18 streaming

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
        add_turn(session, "user", req.message)

        yield _sse({"type": "start", "session_id": req.session_id})

        answer, sources, context, status = "", [], "", "ok"
        try:
            # ---- Day 18 Step 2: TRUE token streaming from the LLM SDK ----
            # Gates run pre-stream inside stream_answer (retrieval-based).
            for ev in stream_answer(req.message):
                if ev["kind"] == "meta":
                    sources = ev["sources"][:5]
                    context = ev["context"]
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
            if status == "ok" and context and not numbers_grounded(answer, context):
                log.warning(f"ungrounded numbers session={req.session_id} "
                            f"answer={answer[:120]!r}")
                answer = REFUSAL_MSG
                status = "ungrounded_numbers"
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

        log.info(f"chat session={req.session_id} member={req.member_id} "
                 f"status={status} ttft_ms={t_first} elapsed_ms={elapsed} "
                 f"turns={len(session['turns'])}")

        yield _sse({"type": "done", "status": status, "sources": sources,
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