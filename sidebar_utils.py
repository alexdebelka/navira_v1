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
        
        # Dashboard button
        if st.button("🏠 Dashboard", use_container_width=True):
            # Track navigation
            try:
                from analytics_integration import track_user_action
                track_user_action("navigation", "sidebar", {"destination": "dashboard"})
            except Exception as e:
                print(f"Analytics tracking error: {e}")
            
            st.session_state.current_page = "dashboard"
            st.switch_page("app.py")
        
        # Hospital Explorer button
        if st.button("🏥 Hospital Explorer", use_container_width=True):
            # Track navigation
            try:
                from analytics_integration import track_user_action
                track_user_action("navigation", "sidebar", {"destination": "hospital_explorer"})
            except Exception as e:
                print(f"Analytics tracking error: {e}")
            
            st.session_state.current_page = "hospital_explorer"
            st.switch_page("pages/hospital_explorer.py")
        
        # National Overview button
        if st.button("📈 National Overview", use_container_width=True):
            # Track navigation
            try:
                from analytics_integration import track_user_action
                track_user_action("navigation", "sidebar", {"destination": "national_overview"})
            except Exception as e:
                print(f"Analytics tracking error: {e}")
            
            st.session_state.current_page = "national"
            st.switch_page("pages/national.py")
        
        # Hospital Analysis button
        if st.button("📊 Hospital Analysis", use_container_width=True):
            # Track navigation
            try:
                from analytics_integration import track_user_action
                track_user_action("navigation", "sidebar", {"destination": "hospital_dashboard"})
            except Exception as e:
                print(f"Analytics tracking error: {e}")
            
            st.session_state.current_page = "hospital"
            st.switch_page("pages/dashboard.py")
        
        # Admin section (only for admin users)
        if st.session_state.user['role'] == 'admin':
            st.markdown("---")
            st.subheader("⚙️ Admin")
            if st.button("👥 User Management", use_container_width=True):
                st.session_state.current_page = "admin"
                st.switch_page("app.py")
        
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
