import streamlit as st
import sys
import os
from auth import init_session_state, require_auth


def check_auth():
    """Check if user is authenticated, redirect to login if not."""
    init_session_state()

    # Check for persistent session first
    from auth import check_persistent_session
    if check_persistent_session():
        st.session_state.authenticated = True

    if not st.session_state.authenticated:
        st.error("🔐 Please login to access this page.")
        st.markdown("---")
        st.markdown("### Login Required")
        st.markdown("You need to be logged in to view this content.")

        if st.button("🔐 Go to Login"):
            try:
                from navigation_utils import navigate_to_login
                navigate_to_login()
            except Exception:
                st.session_state.navigate_to = "login"
                st.rerun()

        st.stop()

    # Initialize analytics (inject GA4 + CMP scripts)
    try:
        from analytics_integration import init_analytics
        init_analytics()
    except Exception:
        pass

    # Limited access mode for specific pilot users
    try:
        user = st.session_state.get('user') or {}
        username = (user or {}).get('username', '')
        email = (user or {}).get('email', '')
        is_limited_user = username == 'andrea.lazzati' or email.startswith('andrea.lazzati')
        if is_limited_user:
            # Force-select Avicenne hospital (FINESS id)
            st.session_state.selected_hospital_id = '930100037'
            st.session_state._limited_user = True
            # If we're not already on the hospital dashboard, redirect there
            if not st.session_state.get('_on_hospital_dashboard', False):
                try:
                    from navigation_utils import navigate_to_hospital_dashboard
                    navigate_to_hospital_dashboard()
                except Exception:
                    st.session_state.navigate_to = "hospital"
                    st.rerun()
    except Exception:
        pass

    # Check if user has permission for this page
    from auth import get_user_permissions
    user_permissions = get_user_permissions(st.session_state.user['id'])
    current_page = st.session_state.get('current_page', 'unknown')

    # Map page names to permissions
    page_permission_map = {
        'dashboard': 'dashboard',
        'hospital_explorer': 'hospital_explorer',  # Use actual permission name
        'hospital': 'hospital',  # Use actual permission name
        'national': 'national',
        'admin': 'admin'
    }

    # Check if user has permission for this page
    required_permission = page_permission_map.get(current_page, current_page)

    # If current_page is unknown, allow access (user might be on main dashboard)
    if current_page == 'unknown':
        pass  # Allow access
    elif required_permission not in user_permissions and st.session_state.user['role'] != 'admin':
        st.error("🚫 Access Denied")
        st.markdown("You don't have permission to access this page.")
        if st.button("🏠 Go to Dashboard"):
            st.session_state.navigate_to = "dashboard"
            st.rerun()
        st.stop()


def show_user_info():
    """Display user information in the sidebar."""
    if st.session_state.authenticated and st.session_state.user:
        with st.sidebar:
            st.markdown("---")
            st.markdown(f"**👤 {st.session_state.user['username']}**")
            st.markdown(f"*Role: {st.session_state.user['role'].title()}*")

            if st.button("🚪 Logout"):
                from auth import logout_user, clear_session_file
                if st.session_state.session_token:
                    logout_user(st.session_state.session_token)

                # Clear session file
                clear_session_file()

                # Clear session state
                st.session_state.authenticated = False
                st.session_state.user = None
                st.session_state.session_token = None

                st.success("Logged out successfully!")
                st.rerun()


def add_auth_to_page():
    """Add authentication check to any page."""
    check_auth()
    # Add the consistent sidebar to all pages
    from sidebar_utils import add_sidebar_to_page
    add_sidebar_to_page()
