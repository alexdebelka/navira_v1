"""
Navigation utilities for the Navira application.
Provides consistent navigation functions that work in both local and deployed environments.
"""

import streamlit as st


def navigate_to_dashboard():
    """Navigate to the user dashboard page."""
    st.switch_page("pages/user_dashboard.py")


def navigate_to_national():
    """Navigate to the national overview page."""
    st.switch_page("pages/national.py")


def navigate_to_hospital_dashboard():
    """Navigate to the hospital dashboard page (details for selected hospital)."""
    st.switch_page("pages/dashboard.py")


def navigate_to_hospital_explorer():
    """Navigate to the hospital explorer page (map)."""
    st.switch_page("pages/hospital_explorer.py")


def navigate_to_admin():
    """Navigate to the admin page."""
    st.switch_page("pages/admin.py")


def navigate_to_login():
    """Navigate to the dedicated login page."""
    st.switch_page("pages/login.py")


def navigate_to_assistant():
    """Navigate to the assistant chat page."""
    st.switch_page("pages/assistant.py")


def navigate_to_page(page_name: str):
    """Navigate to a specific page by name."""
    navigation_map = {
        "dashboard": navigate_to_dashboard,
        "national": navigate_to_national,
        "hospital": navigate_to_hospital_dashboard,
        "hospital_explorer": navigate_to_hospital_explorer,
        "admin": navigate_to_admin,
        "login": navigate_to_login,
        "assistant": navigate_to_assistant,
    }

    if page_name in navigation_map:
        navigation_map[page_name]()
    else:
        st.error(f"Unknown page: {page_name}")


def handle_navigation_request():
    """Handle navigation requests from session state."""
    navigate_to = st.session_state.get('navigate_to')
    if navigate_to:
        navigate_to_page(navigate_to)
        st.session_state.navigate_to = None
