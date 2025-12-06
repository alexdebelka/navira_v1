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
        # Hide the sidebar for unauthenticated users
        st.markdown("""
            <style>
                [data-testid="stSidebar"] {
                    display: none;
                }
                [data-testid="collapsedControl"] {
                    display: none;
                }
            </style>
        """, unsafe_allow_html=True)
        
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
    # Mapping of pilot users to their FINESS codes
    pilot_user_hospitals = {
        'andrea.lazzati': '930100037',      # Hôpital Avicenne
        'federica.papini': '940000573',     # CHIC DE CRETEIL
        'sergio.carandina': '830100459',    # CLINIQUE SAINT MICHEL
        'claire.blanchard': '440000271',    # CHU DE NANTES (City of Nantes)
        'thomas.auguste': '560008799',      # CHBA VANNES (City of Vannes)
        'laurent.genser': '750100125'       # GROUPEMENT HOSPITALIER PITIE-SALPETRIERE
    }
    
    # Pages that limited users (pilot users) are allowed to access
    # Note: Pilot users have 'dashboard' permission in the database (see PILOT_USERS_CREDENTIALS.md)
    LIMITED_USER_ALLOWED_PAGES = {'national', 'hospital', 'dashboard'}
    
    try:
        user = st.session_state.get('user') or {}
        username = (user or {}).get('username', '')
        is_limited_user = username in pilot_user_hospitals
        
        if is_limited_user:
            # Force-select their assigned hospital (FINESS id)
            st.session_state.selected_hospital_id = pilot_user_hospitals.get(username)
            st.session_state._limited_user = True
            
            # Detect current page more robustly
            # First try session state, then try to detect from script path
            current_page = st.session_state.get('current_page', 'unknown')
            
            # If current_page is unknown, try to detect from the script path
            if current_page == 'unknown':
                frame = None
                try:
                    import inspect
                    import os
                    # Walk up the call stack to find the page file
                    frame = inspect.currentframe()
                    depth = 0
                    while frame and depth < 10:  # Limit depth to avoid infinite loops
                        filename = frame.f_code.co_filename
                        if 'pages' in filename:
                            basename = os.path.basename(filename)
                            if 'national.py' in basename:
                                current_page = 'national'
                                break
                            elif 'dashboard.py' in basename:
                                current_page = 'hospital'
                                break
                            elif 'hospital_explorer' in basename:
                                current_page = 'hospital_explorer'
                                break
                            elif 'hospital_compare' in basename:
                                current_page = 'hospital_compare'
                                break
                            elif 'admin.py' in basename:
                                current_page = 'admin'
                                break
                            elif 'user_dashboard.py' in basename:
                                current_page = 'dashboard'
                                break
                        next_frame = frame.f_back
                        frame = next_frame
                        depth += 1
                except Exception:
                    pass
                finally:
                    # Explicitly delete frame to break reference cycles and allow garbage collection
                    # This is critical in Streamlit where check_auth() is called on every rerun
                    del frame
            
            # Check if user is on hospital dashboard using the flag (takes precedence)
            if st.session_state.get('_on_hospital_dashboard', False):
                current_page = 'hospital'
            
            # Redirect if the page is not in the allowed list
            if current_page not in LIMITED_USER_ALLOWED_PAGES:
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
