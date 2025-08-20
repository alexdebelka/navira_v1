"""
Navigation utilities for the Navira application.
Provides consistent navigation functions that work in both local and deployed environments.
"""

import streamlit as st
import os

def get_main_file_path():
    """Determine the correct main file path for navigation."""
    # Check if main.py exists and is likely the main file
    if os.path.exists("main.py"):
        return "main.py"
    else:
        return "app.py"

def navigate_to_dashboard():
    """Navigate to the main dashboard."""
    main_file = get_main_file_path()
    st.switch_page(main_file)

def navigate_to_national():
    """Navigate to the national overview page."""
    st.switch_page("pages/national.py")

def navigate_to_hospital_dashboard():
    """Navigate to the hospital dashboard page."""
    st.switch_page("pages/dashboard.py")

def navigate_to_hospital_explorer():
    """Navigate to the hospital explorer page."""
    main_file = get_main_file_path()
    if main_file == "main.py":
        # If main.py is the hospital explorer, stay on current page
        st.rerun()
    else:
        st.switch_page("main.py")

def navigate_to_page(page_name: str):
    """Navigate to a specific page by name."""
    navigation_map = {
        "dashboard": navigate_to_dashboard,
        "national": navigate_to_national,
        "hospital": navigate_to_hospital_dashboard,
        "hospital_explorer": navigate_to_hospital_explorer,
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
