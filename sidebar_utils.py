import streamlit as st
from auth import logout_user

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
        
        # Navigation form
        with st.form("navigation_form"):
            nav_option = st.selectbox(
                "Navigate to:",
                ["🏠 Dashboard", "🏥 Hospital Explorer", "📈 National Overview", "📊 Hospital Analysis"],
                index=0
            )
            
            if st.form_submit_button("Go"):
                # Track navigation
                try:
                    from analytics_integration import track_user_action
                    track_user_action("navigation", "sidebar", {"destination": nav_option})
                except Exception as e:
                    print(f"Analytics tracking error: {e}")
                
                # Set navigation based on selection
                if "Dashboard" in nav_option:
                    st.session_state.current_page = "dashboard"
                    st.session_state.navigate_to = "dashboard"
                elif "Hospital Explorer" in nav_option:
                    st.session_state.current_page = "hospital_explorer"
                    st.session_state.navigate_to = "hospital_explorer"
                elif "National Overview" in nav_option:
                    st.session_state.current_page = "national"
                    st.session_state.navigate_to = "national"
                elif "Hospital Analysis" in nav_option:
                    st.session_state.current_page = "hospital"
                    st.session_state.navigate_to = "hospital"
                
                st.rerun()
        
        # Admin section (only for admin users)
        if st.session_state.user['role'] == 'admin':
            st.markdown("---")
            st.subheader("⚙️ Admin")
            if st.button("👥 User Management", use_container_width=True):
                st.session_state.current_page = "admin"
                st.session_state.navigate_to = "admin"
                st.experimental_rerun()
        
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
