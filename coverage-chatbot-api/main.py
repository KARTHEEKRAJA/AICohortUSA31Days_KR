import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# make repo-root modules importable from inside coverage-chatbot-api/
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from rag_chatbot import retrieve_and_answer          # Day 11 pipeline (Day 10 retrieve() inside)

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


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    t0 = time.perf_counter()

    session = get_session(req.session_id, req.member_id)     # state in
    add_turn(session, "user", req.message)

    # ---- Day 16 Step 2 + Step 6: guarded orchestration ----
    # Day 10 retrieve() -> clean context -> Day 12 Variant E prompt -> Day 11 LLM
    try:
        result = retrieve_and_answer(req.message)
        answer = result["answer"]
        sources = result.get("sources", [])[:5]
        status = "ok"
    except Exception as e:                      # LLM down, Chroma error, etc.
        log.error(f"pipeline failure session={req.session_id}: {type(e).__name__}: {e}")
        answer = ("I'm having trouble answering right now. Please try again "
                  "in a moment, or contact Member Support.")
        sources = []
        status = "error"

    elapsed = int((time.perf_counter() - t0) * 1000)
    add_turn(session, "assistant", answer, elapsed_ms=elapsed)   # state out
    # failure turns are recorded too — audit trails include the bad moments

    # ---- Step 6: request-timing log ----
    log.info(f"chat session={req.session_id} member={req.member_id} "
             f"status={status} elapsed_ms={elapsed} turns={len(session['turns'])}")

    return ChatResponse(
        session_id=req.session_id,
        answer=answer,
        turn_count=len(session["turns"]),
        sources=sources,
        elapsed_ms=elapsed,
    )


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