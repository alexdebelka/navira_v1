import streamlit as st

# Page config
st.set_page_config(
    page_title="Login",
    page_icon="🔐",
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

# Initialize analytics (optional on login page)
try:
    from analytics_integration import init_analytics
    init_analytics()
except Exception:
    pass

# Render login
from auth import init_session_state, login_page
init_session_state()
login_page()
