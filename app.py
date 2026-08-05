"""Day 17 — Streamlit chat UI for the coverage chatbot.
Day 18: consumes the backend's SSE stream — tokens render as they arrive.
Day 19: citations expander + Pydantic rich cards under answers."""
import json
import uuid
from pathlib import Path

import pandas as pd
import requests
import streamlit as st

API_URL = "http://127.0.0.1:8000"
MEMBER_ID = "M1001"
PLANS_CSV = Path(__file__).parent / "data" / "plans.csv"

st.set_page_config(page_title="Coverage Chatbot", page_icon="🏥")
st.title("🏥 Coverage Chatbot")
st.caption("Ask about plans, coverage, claims, and costs — grounded answers only.")

# ---- persistence across reruns ----
if "messages" not in st.session_state:
    st.session_state.messages = []
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())


# ---- sidebar ----
@st.cache_data                            # read the CSV once, not every rerun
def load_plans() -> pd.DataFrame:
    return pd.read_csv(PLANS_CSV)


with st.sidebar:
    st.header("⚙️ Conversation")

    plans = load_plans()
    plan_label = st.selectbox(
        "Your plan",
        options=[f"{r.plan_name} ({r.plan_id})" for r in plans.itertuples()],
    )
    st.caption("Selected plan is added to your questions as context.")

    if st.button("🔄 New conversation", use_container_width=True):
        st.session_state.messages = []
        st.session_state.session_id = str(uuid.uuid4())
        st.rerun()

    st.divider()
    st.caption(f"session: `{st.session_state.session_id[:8]}…`")
    st.caption(f"member: `{MEMBER_ID}`")


def render_cards(cards: list) -> None:
    """Day 19: rich result cards — rendered AFTER the stream completes.
    Structured data never rides the token stream: a half-streamed table
    is garbage until its closing row. Cards arrive whole, in the done
    event, already Pydantic-validated server-side."""
    icons = {"Approved": "\u2705", "Pending": "\u23F3", "Denied": "\u274C"}
    for card in cards:
        if card["card_type"] == "claim_status":
            icon = icons.get(card["status"], "\u2139\uFE0F")
            with st.container(border=True):
                st.markdown(f"{icon} **Claim {card['claim_id']}** — {card['status']}")
                c1, c2 = st.columns(2)
                c1.metric("Amount", f"${card['amount']:,.2f}")
                c2.metric("Filed", card["date"])
        elif card["card_type"] == "coverage_summary":
            with st.container(border=True):
                badge = "\U0001F7E2 Active" if card["covered"] else "\U0001F534 Not covered"
                st.markdown(f"**{card['plan_name']}** · {badge}")
                c1, c2 = st.columns(2)
                ded = card["deductible"]
                cop = card["copay"]
                c1.metric("Deductible", f"${ded:,.0f}" if ded is not None else "\u2014")
                c2.metric("Copay", f"{cop:.0f}%" if cop is not None else "\u2014")


def render_citations(citations: list) -> None:
    """Day 19: expandable Policy-sources section — numbered, chunk-ID first.
    An expander under the FINISHED answer, not footnotes inside it: streamed
    markdown re-renders on every token, so inline anchors flicker/break."""
    if not citations:
        return
    with st.expander(f"\U0001F4DA Policy sources ({len(citations)})"):
        for i, c in enumerate(citations, 1):
            st.markdown(f"**[{i}]** `{c['id']}` — {c['section']} · _{c['source']}_")


def ask_backend_stream(message: str, placeholder, plan_id: str | None = None) -> tuple[str, list, list]:
    """POST one turn to /chat with stream=True; render tokens into the
    placeholder as they arrive. Returns (answer text, citations, cards).

    Day 18 mechanics:
    - stream=True keeps the connection open; iter_lines() yields SSE lines
    - timeout=(5, 90): 5s to CONNECT, 90s max BETWEEN chunks — a mid-stream
      stall raises Timeout without capping total answer length
    - pre-first-token UX: a pulsing cursor until the first token lands
    - a "guard" event REPLACES everything streamed (post-hoc numeric guard)
    """
    answer = ""
    citations = []
    cards = []
    placeholder.markdown("*Checking your coverage…* ▌")   # pre-first-token indicator
    # (replaced by the growing answer the instant the first token arrives)
    try:
        with requests.post(
            f"{API_URL}/chat",
            json={
                "session_id": st.session_state.session_id,
                "member_id": MEMBER_ID,
                "message": message,
                "plan_id": plan_id,        # Day 20: plan is a field, not a prefix
            },
            stream=True,
            timeout=(5, 90),
        ) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines(decode_unicode=True):
                if not line or not line.startswith("data: "):
                    continue                       # skip keep-alives/blanks
                event = json.loads(line[len("data: "):])

                if event["type"] == "token":
                    answer += event["text"]
                    placeholder.markdown(answer + "▌")   # grow the bubble
                elif event["type"] == "guard":
                    answer = event["text"]               # guard overrides
                    placeholder.markdown(answer + "▌")
                elif event["type"] == "done":
                    citations = event.get("citations", [])
                    cards = event.get("cards", [])
                    ttft = event.get("ttft_ms")
                    if ttft is not None:
                        st.caption(f"first token {ttft} ms · total {event.get('elapsed_ms')} ms")
        placeholder.markdown(answer)               # final render, cursor off
        return answer, citations, cards
    except requests.exceptions.ConnectionError:
        answer = ("⚠️ I can't reach the backend at " + API_URL +
                  ". Is uvicorn running?")
    except requests.exceptions.HTTPError as e:
        answer = f"⚠️ Backend error: {e.response.status_code} — {e.response.text[:200]}"
    except requests.exceptions.Timeout:
        answer = (answer + "\n\n⚠️ The stream stalled mid-answer. "
                  "Partial response shown — try again.") if answer else \
                 "⚠️ The backend took too long to start answering. Try again."
    except json.JSONDecodeError:
        answer = "⚠️ Received a malformed stream event. Try again."
    placeholder.markdown(answer)
    return answer, citations, cards


# ---- render the conversation so far ----
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        render_cards(msg.get("cards", []))
        render_citations(msg.get("citations", []))

# ---- input ----
if prompt := st.chat_input("Ask about your coverage..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # smart context injection (v2): skip when the question names a plan
    # (cross-plan fix) OR is a catalog/discovery question about all plans
    # (injection was hijacking "what plans do you offer" into a my-plan
    # answer — the injected plan biased retrieval AND the model's topic)
    # Day 20: injection moved SERVER-SIDE (v4). The client sends the raw
    # message + plan_id field; memory persists clean member words, and the
    # server decides injection with the same v3 skip rules. (v2 fixed the
    # catalog hijack, v3 the comparison hijack, v4 ends DB pollution.)
    plan_id = plan_label.split("(")[-1].rstrip(")")        # "Gold PPO (P101)" -> P101

    with st.chat_message("assistant"):
        placeholder = st.empty()                   # the growing bubble
        reply, citations, cards = ask_backend_stream(prompt, placeholder, plan_id)
        render_cards(cards)
        render_citations(citations)
    st.session_state.messages.append(
        {"role": "assistant", "content": reply, "citations": citations,
         "cards": cards})