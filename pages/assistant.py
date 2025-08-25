import os
import streamlit as st

from auth_wrapper import add_auth_to_page
from navigation_utils import (
    navigate_to_dashboard,
    navigate_to_national,
    navigate_to_hospital_explorer,
    navigate_to_hospital_dashboard,
)

# Feature flag: early exit if disabled to minimize cost and imports
def _assistant_enabled() -> bool:
    try:
        val = None
        if hasattr(st, "secrets") and st.secrets:
            val = (
                st.secrets.get("features", {}).get("assistant_enabled")
                or st.secrets.get("ASSISTANT_ENABLED")
            )
        if val is None:
            val = os.environ.get("ASSISTANT_ENABLED", "0")
        return str(val).strip().lower() in ("1", "true", "yes", "on")
    except Exception:
        return False

# Page config
st.set_page_config(
    page_title="Assistant",
    page_icon="💬",
    layout="wide",
)

# Hide default Streamlit navigation
st.markdown(
    """
    <style>
        [data-testid="stSidebarNav"] { display: none; }
        [data-testid="stPageNav"] { display: none; }
    </style>
    """,
    unsafe_allow_html=True,
)

# If disabled, show message and exit early without initializing chat/OpenAI
if not _assistant_enabled():
    from auth_wrapper import add_auth_to_page as _add_auth
    _add_auth()
    st.title("💬 Navira Assistant")
    st.info("Assistant is temporarily disabled. Please contact the administrator if you need access.")
    st.stop()

# Ensure auth + sidebar
add_auth_to_page()

st.title("💬 Navira Assistant")
st.caption("Ask anything about this app or say things like 'go to national', 'open hospital explorer', 'show my dashboard'.")

# Chat state
if "assistant_chat" not in st.session_state:
    st.session_state.assistant_chat = []  # list of {role, content}

# Helper: render history
for msg in st.session_state.assistant_chat:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# OpenAI client init (key via Secrets or env var)
@st.cache_resource(show_spinner=False)
def _init_openai_client():
    api_key = None
    if hasattr(st, "secrets") and st.secrets:
        api_key = st.secrets.get("openai", {}).get("api_key") or st.secrets.get("OPENAI_API_KEY")
        if not api_key:
            api_key = st.secrets.get("openai_api_key")
    api_key = api_key or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return None, "Missing OpenAI API key. Add to Secrets under [openai].api_key or set OPENAI_API_KEY."
    try:
        from openai import OpenAI  # type: ignore
    except Exception:
        return None, "OpenAI package not installed. Add 'openai' to requirements.txt or 'pip install openai'."
    try:
        client = OpenAI(api_key=api_key)
        return client, None
    except Exception as e:
        return None, f"Failed initializing OpenAI client: {e}"

# Simple intent detection for navigation
NAV_KEYWORDS = {
    "dashboard": ["dashboard", "home", "my dashboard", "user dashboard"],
    "hospital_explorer": ["explorer", "map", "hospital explorer", "explore"],
    "national": ["national", "country", "france", "overview"],
    "hospital": ["hospital analysis", "analysis", "details", "hospital page"],
}

def maybe_navigate(text: str) -> bool:
    t = (text or "").strip().lower()
    if not t:
        return False
    def _match(keys):
        return any(k in t for k in keys)
    if _match(NAV_KEYWORDS["dashboard"]):
        navigate_to_dashboard();
        return True
    if _match(NAV_KEYWORDS["hospital_explorer"]):
        navigate_to_hospital_explorer();
        return True
    if _match(NAV_KEYWORDS["national"]):
        navigate_to_national();
        return True
    if _match(NAV_KEYWORDS["hospital"]):
        navigate_to_hospital_dashboard();
        return True
    return False

# System prompt to guide the assistant
SYSTEM_PROMPT = (
    "You are Navira's in-app guide. Help users navigate between pages (Dashboard, Hospital Explorer, National, Hospital Analysis), "
    "explain metrics, and answer questions concisely."
)

user_msg = st.chat_input("Type a question or a command…")
if user_msg:
    # First, try local navigation intents
    if maybe_navigate(user_msg):
        st.session_state.assistant_chat.append({"role": "user", "content": user_msg})
        st.session_state.assistant_chat.append({"role": "assistant", "content": "Navigating…"})
        st.rerun()

    # Show the user's message immediately
    with st.chat_message("user"):
        st.markdown(user_msg)

    st.session_state.assistant_chat.append({"role": "user", "content": user_msg})

    with st.chat_message("assistant"):
        with st.spinner("Thinking…"):
            client, err = _init_openai_client()
            if err:
                st.info(err)
                reply = "I can't reach the assistant service yet. Please configure it and try again."
            else:
                try:
                    response = client.responses.create(
                        model="gpt-4o-mini",
                        input=[
                            {"role": "system", "content": SYSTEM_PROMPT},
                            {"role": "user", "content": user_msg},
                        ],
                        store=False,
                    )
                    reply = getattr(response, "output_text", "Sorry, I couldn't generate a response.")
                except Exception as e:
                    reply = f"Assistant error: {e}"
            st.markdown(reply)
            st.session_state.assistant_chat.append({"role": "assistant", "content": reply})
