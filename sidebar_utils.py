import streamlit as st
import os
from auth import logout_user
from navigation_utils import (
    navigate_to_dashboard,
    navigate_to_hospital_explorer,
    navigate_to_national,
    navigate_to_hospital_dashboard,
)


def add_sidebar_to_page():
    """
    Add the consistent sidebar navigation to any page.
    This should be called at the beginning of each page after authentication.
    """
    with st.sidebar:
        # Navira branding header
        st.markdown("""
        <div style="
            background: linear-gradient(180deg, #667eea 0%, #764ba2 100%);
            padding: 1rem;
            border-radius: 10px;
            color: white;
            text-align: center;
            margin-bottom: 1rem;
        ">
            <h2 style="margin: 0; display: flex; align-items: center; justify-content: center; gap: 0.5rem;">
                🏥 Navira
            </h2>
            <p style="margin: 0.5rem 0 0 0; font-size: 0.9rem; opacity: 0.9;">
                Bariatric Surgery Analytics
            </p>
        </div>
        """, unsafe_allow_html=True)

        # Welcome section
        st.markdown(f"**Welcome, {st.session_state.user['username']}!**")
        st.markdown(f"*Role: {st.session_state.user['role'].title()}*")

        st.markdown("---")

        # Navigation section
        st.subheader("🧭 Navigation")

        # Direct navigation buttons (no dropdown, no Go button)
        def _track(dest: str):
            try:
                from analytics_integration import track_user_action
                track_user_action("navigation", "sidebar", {"destination": dest})
            except Exception:
                pass

        limited = bool(st.session_state.get('_limited_user'))
        if not limited:
            if st.button("🏠 Dashboard", use_container_width=True):
                _track("Dashboard")
                navigate_to_dashboard()
            if st.button("🏥 Hospital Explorer", use_container_width=True):
                _track("Hospital Explorer")
                navigate_to_hospital_explorer()
            if st.button("📈 National Overview", use_container_width=True):
                _track("National Overview")
                navigate_to_national()
            if st.button("📊 Hospital Analysis", use_container_width=True):
                _track("Hospital Analysis")
                navigate_to_hospital_dashboard()
            if st.button("⚖️ Hospital Comparison", use_container_width=True):
                _track("Hospital Comparison")
                from navigation_utils import navigate_to_hospital_compare
                navigate_to_hospital_compare()
        else:
            # Limited users see only the hospital dashboard entry
            st.info("Limited pilot access enabled")
            if st.button("📊 Hospital Dashboard (Avicenne)", use_container_width=True):
                _track("Hospital Dashboard (Limited)")
                navigate_to_hospital_dashboard()
        # Assistant feature flag
        _assistant_enabled = False
        try:
            val = None
            if hasattr(st, "secrets") and st.secrets:
                val = (
                    st.secrets.get("features", {}).get("assistant_enabled")
                    or st.secrets.get("ASSISTANT_ENABLED")
                )
            if val is None:
                val = os.environ.get("ASSISTANT_ENABLED", "0")
            _assistant_enabled = str(val).strip().lower() in ("1", "true", "yes", "on")
        except Exception:
            _assistant_enabled = False

        if _assistant_enabled and not limited:
            if st.button("💬 Assistant", use_container_width=True):
                _track("Assistant")
                from navigation_utils import navigate_to_assistant
                navigate_to_assistant()

        # Admin section (only for admin users)
        if st.session_state.user['role'] == 'admin' and not limited:
            st.markdown("---")
            st.subheader("⚙️ Admin")
            if st.button("👥 User Management", use_container_width=True):
                from navigation_utils import navigate_to_admin
                navigate_to_admin()

        # Logout
        st.markdown("---")
        if st.button("🚪 Logout", use_container_width=True):
            if st.session_state.session_token:
                logout_user(st.session_state.session_token)

            # Clear session file
            from auth import clear_session_file
            clear_session_file()

            # Clear session state
            st.session_state.authenticated = False
            st.session_state.user = None
            st.session_state.session_token = None
            st.session_state.current_page = "login"

            st.success("Logged out successfully!")
            st.rerun()
