import streamlit as st
from auth_wrapper import add_auth_to_page

# Add authentication and sidebar
add_auth_to_page()

# Page config
st.set_page_config(
    page_title="Admin Panel",
    page_icon="⚙️",
    layout="wide"
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

# Render the admin panel from the main app module
try:
    from app import admin_panel
    admin_panel()
except Exception as e:
    st.error(f"Failed to load admin panel: {e}")
