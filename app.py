"""Day 17 — Streamlit chat UI for the coverage chatbot."""
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


def ask_backend(message: str) -> str:
    """POST one turn to /chat; return the answer or a friendly error."""
    try:
        resp = requests.post(
            f"{API_URL}/chat",
            json={
                "session_id": st.session_state.session_id,
                "member_id": MEMBER_ID,
                "message": message,
            },
            timeout=120,
        )
        resp.raise_for_status()
        return resp.json()["answer"]
    except requests.exceptions.ConnectionError:
        return ("⚠️ I can't reach the backend at " + API_URL +
                ". Is uvicorn running?")
    except requests.exceptions.HTTPError as e:
        return f"⚠️ Backend error: {e.response.status_code} — {e.response.text[:200]}"
    except requests.exceptions.Timeout:
        return "⚠️ The backend took too long. Try again — warm requests are faster."


# ---- render the conversation so far ----
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# ---- input ----
if prompt := st.chat_input("Ask about your coverage..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # smart context injection (v2): skip when the question names a plan
    # (cross-plan fix) OR is a catalog/discovery question about all plans
    # (injection was hijacking "what plans do you offer" into a my-plan
    # answer — the injected plan biased retrieval AND the model's topic)
    plan_words = ("gold", "silver", "bronze", "p101", "p102", "p103")
    catalog_words = ("plans do you", "what plans", "which plans", "all plans",
                     "plans are", "plans available", "available plans", "offer")
    p = prompt.lower()
    if any(w in p for w in plan_words) or any(w in p for w in catalog_words):
        contextual = prompt                                # don't interfere
    else:
        contextual = f"[Member's plan: {plan_label}] {prompt}"

    with st.chat_message("assistant"):
        with st.spinner("Checking your coverage..."):
            reply = ask_backend(contextual)
        st.markdown(reply)
    st.session_state.messages.append({"role": "assistant", "content": reply})