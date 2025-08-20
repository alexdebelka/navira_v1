import streamlit as st
from auth_wrapper import add_auth_to_page
from auth import user_dashboard as render_user_dashboard

# Ensure auth and sidebar are set up
add_auth_to_page()

# Page config
st.set_page_config(
    page_title="User Dashboard",
    page_icon="🏠",
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

# Render the dashboard
render_user_dashboard()
