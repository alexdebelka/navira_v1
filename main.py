import streamlit as st
from auth_wrapper import add_auth_to_page

# Minimal entrypoint: login page only when unauthenticated, otherwise go to Hospital Dashboard

st.set_page_config(
    page_title="Navira",
    page_icon="🏥",
    layout="wide"
)

add_auth_to_page()

# Hide default Streamlit nav
st.markdown("""
    <style>
        [data-testid="stSidebarNav"] { display: none; }
        [data-testid="stPageNav"] { display: none; }
    </style>
""", unsafe_allow_html=True)

if not st.session_state.get('authenticated'):
    # Show the login page only
    from auth import login_page
    login_page()
else:
    # Navigate directly to Hospital Dashboard (pages/dashboard.py)
    try:
        from navigation_utils import navigate_to_page
        st.session_state.navigate_to = "hospital"
        navigate_to_page("hospital")
        st.stop()
    except Exception:
        # Fallback content if navigation utility is unavailable
        st.title("Hospital Dashboard")
        st.write("Navigation utilities unavailable. Please open the Hospital Dashboard page from the sidebar.")
