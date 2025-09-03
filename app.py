import streamlit as st
import pandas as pd

import plotly.express as px
from auth import (
    init_session_state, 
    login_page, 
    register_page, 
    user_dashboard, 
    require_auth
)

# Configure the page
st.set_page_config(
    page_title="Navira - Bariatric Surgery Analytics",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for styling and hiding default navigation
st.markdown("""
<style>
    .metric-card {
        background: #f0f2f6;
        padding: 1rem;
        border-radius: 10px;
        border-left: 4px solid #667eea;
    }
    /* Hide default Streamlit navigation */
    [data-testid="stSidebarNav"] {
        display: none;
    }
    [data-testid="stPageNav"] {
        display: none;
    }
</style>
""", unsafe_allow_html=True)

def main():
    """Main application function."""
    # Initialize session state
    init_session_state()
    
    # Initialize analytics
    from analytics_integration import init_analytics
    analytics = init_analytics()
    
    # Check for persistent session first
    from auth import check_persistent_session
    if check_persistent_session():
        st.session_state.authenticated = True
    
    # Add consistent sidebar for authenticated users
    if st.session_state.authenticated and st.session_state.user:
        from sidebar_utils import add_sidebar_to_page
        add_sidebar_to_page()
        
        # Track page view
        try:
            from analytics_integration import track_page_view
            current_page = st.session_state.get('current_page', 'dashboard')
            track_page_view(current_page)
        except Exception as e:
            print(f"Analytics tracking error: {e}")
            current_page = st.session_state.get('current_page', 'dashboard')
    
    # Main content area
    if not st.session_state.authenticated:
        # Show login or register page
        if st.session_state.get('show_register', False):
            register_page()
        else:
            login_page()
    else:
        # User is authenticated, show appropriate page
        current_page = st.session_state.get('current_page', 'dashboard')
        
        # Handle navigation requests
        navigate_to = st.session_state.get('navigate_to')
        if navigate_to:
            from navigation_utils import navigate_to_page
            if navigate_to in ["admin", "login"]:
                # Handle special cases that don't use page navigation
                if navigate_to == "admin":
                    st.session_state.navigate_to = None
                    admin_panel()
                elif navigate_to == "login":
                    st.session_state.navigate_to = None
                    st.session_state.authenticated = False
                    st.session_state.user = None
                    st.session_state.session_token = None
                    login_page()
            else:
                navigate_to_page(navigate_to)
                st.session_state.navigate_to = None
        else:
            # Normal page routing
            if current_page == "dashboard":
                user_dashboard()
            elif current_page == "admin" and st.session_state.user['role'] == 'admin':
                admin_panel()
            else:
                user_dashboard()

def admin_panel():
    """Admin panel for user management."""
    if not st.session_state.authenticated or st.session_state.user['role'] != 'admin':
        st.error("Access denied. Admin privileges required.")
        return
    
    st.title("⚙️ Admin Panel")
    st.markdown("---")
    
    # Admin tabs
    tab1, tab2, tab3, tab4 = st.tabs(["👥 User Management", "📊 System Stats", "📈 Analytics Dashboard", "🔧 Settings"])
    
    with tab1:
        st.subheader("User Management")
        
        # Get all users
        import sqlite3
        from auth import DB_PATH
        
        conn = sqlite3.connect(DB_PATH)
        users_df = pd.read_sql_query("""
            SELECT id, username, email, role, created_at, last_login, is_active
            FROM users ORDER BY created_at DESC
        """, conn)
        conn.close()
        
        # Display users table
        st.dataframe(users_df, use_container_width=True)
        
        # User permissions section
        st.markdown("---")
        st.subheader("👥 User Permissions")
        
        # Get user permissions
        conn = sqlite3.connect(DB_PATH)
        permissions_df = pd.read_sql_query("""
            SELECT u.username, u.role, up.page_access
            FROM users u
            LEFT JOIN user_permissions up ON u.id = up.user_id
            ORDER BY u.username, up.page_access
        """, conn)
        conn.close()
        
        if not permissions_df.empty:
            st.dataframe(permissions_df, use_container_width=True)
        else:
            st.info("No user permissions found.")
        
        # Debug section for current user
        st.markdown("---")
        st.subheader("🔍 Debug: Current User Permissions")
        
        if st.session_state.authenticated and st.session_state.user:
            current_user_id = st.session_state.user['id']
            
            # Get current user permissions
            conn_debug = sqlite3.connect(DB_PATH)
            current_user_permissions = pd.read_sql_query("""
                SELECT page_access FROM user_permissions WHERE user_id = ?
            """, conn_debug, params=(current_user_id,))
            conn_debug.close()
            
            st.write(f"**Current User:** {st.session_state.user['username']} (ID: {current_user_id})")
            st.write(f"**Role:** {st.session_state.user['role']}")
            st.write(f"**Current Page:** {st.session_state.get('current_page', 'unknown')}")
            st.write(f"**Permissions:** {current_user_permissions['page_access'].tolist() if not current_user_permissions.empty else 'None'}")
        else:
            st.write("No user logged in")
        
        # Delete user functionality
        st.markdown("---")
        st.subheader("🗑️ Delete User")
        
        # Get list of users for deletion (excluding current admin)
        current_user_id = st.session_state.user['id']
        users_for_deletion = users_df[users_df['id'] != current_user_id]
        
        if not users_for_deletion.empty:
            selected_user = st.selectbox(
                "Select user to delete:",
                options=users_for_deletion['username'].tolist(),
                format_func=lambda x: f"{x} (ID: {users_for_deletion[users_for_deletion['username'] == x]['id'].iloc[0]})"
            )
            
            if selected_user:
                # Check if selected user exists in the current list
                user_matches = users_for_deletion[users_for_deletion['username'] == selected_user]
                
                if len(user_matches) == 0:
                    st.error(f"❌ Selected user '{selected_user}' not found in current user list")
                    return
                
                user_id = int(user_matches['id'].iloc[0])
                user_email = user_matches['email'].iloc[0]
                
                st.write(f"Debug: Will delete user_id: {user_id}")
                st.write(f"Selected: {selected_user} ({user_email})")
                
                # Show confirmation checkbox (outside form)
                confirm_delete = st.checkbox(f"✅ I confirm I want to delete user '{selected_user}' ({user_email})")
                
                # Delete button (simple button, not in form)
                if confirm_delete:
                    if st.button("🗑️ Delete User", type="primary"):
                        st.write("🔄 Deleting user...")
                        try:
                            from auth import delete_user
                            success = delete_user(user_id)
                            
                            if success:
                                # Track user deletion
                                try:
                                    from analytics_integration import track_user_action
                                    track_user_action("user_deleted", "admin", {
                                        "deleted_username": selected_user,
                                        "deleted_user_id": user_id
                                    })
                                except Exception as e:
                                    print(f"Analytics tracking error: {e}")
                                
                                st.success(f"✅ User '{selected_user}' deleted successfully!")
                                # Force reload the page to refresh the user list
                                st.rerun()
                            else:
                                st.error(f"❌ Failed to delete user '{selected_user}' - Check server logs for details")
                        except Exception as e:
                            st.error(f"❌ Error deleting user: {e}")
                            st.write(f"Debug: Exception details: {str(e)}")
                else:
                    st.info("Please check the confirmation box above to enable deletion.")
        else:
            st.info("No users available for deletion.")
        
        # Add new user
        st.subheader("➕ Add New User")
        
        with st.form("add_user_form"):
            col1, col2 = st.columns(2)
            with col1:
                new_username = st.text_input("Username")
                new_email = st.text_input("Email")
            with col2:
                new_password = st.text_input("Password", type="password")
                new_role = st.selectbox("Role", ["user", "admin"])
            
            if st.form_submit_button("➕ Create Custom User"):
                if all([new_username, new_email, new_password]):
                    from auth import create_user
                    success = create_user(new_username, new_email, new_password, new_role)
                    if success:
                        # Track user creation
                        try:
                            from analytics_integration import track_user_action
                            track_user_action("user_created", "admin", {
                                "new_username": new_username,
                                "new_role": new_role
                            })
                        except Exception as e:
                            print(f"Analytics tracking error: {e}")
                        
                        st.success("✅ User created successfully!")
                        st.rerun()
                    else:
                        st.error("❌ Username or email already exists.")
                else:
                    st.error("❌ Please fill in all fields.")
    
    with tab2:
        st.subheader("System Statistics")
        
        # Get system stats
        conn = sqlite3.connect(DB_PATH)
        
        # User stats
        total_users = pd.read_sql_query("SELECT COUNT(*) as count FROM users", conn).iloc[0]['count']
        active_users = pd.read_sql_query("SELECT COUNT(*) as count FROM users WHERE is_active = 1", conn).iloc[0]['count']
        admin_users = pd.read_sql_query("SELECT COUNT(*) as count FROM users WHERE role = 'admin'", conn).iloc[0]['count']
        
        # Session stats
        active_sessions = pd.read_sql_query("SELECT COUNT(*) as count FROM user_sessions WHERE expires_at > CURRENT_TIMESTAMP", conn).iloc[0]['count']
        
        conn.close()
        
        # Display metrics
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Users", total_users)
        with col2:
            st.metric("Active Users", active_users)
        with col3:
            st.metric("Admin Users", admin_users)
        with col4:
            st.metric("Active Sessions", active_sessions)
        
        st.markdown("---")
        
        # Custom Analytics Section
        st.subheader("📊 Usage Analytics")
        st.info("Track user interactions and app usage patterns")
        
        # Simple usage tracking
        st.markdown("#### User Activity Tracking")
        
        # Track page visits
        if 'page_visits' not in st.session_state:
            st.session_state.page_visits = {}
        
        current_page = st.session_state.get('current_page', 'dashboard')
        if current_page not in st.session_state.page_visits:
            st.session_state.page_visits[current_page] = 0
        st.session_state.page_visits[current_page] += 1
        
        # Display usage statistics
        st.markdown("#### Usage Statistics")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            total_visits = sum(st.session_state.page_visits.values())
            st.metric("Total Page Visits", total_visits)
        
        with col2:
            unique_pages = len(st.session_state.page_visits)
            st.metric("Pages Visited", unique_pages)
        
        with col3:
            current_user = st.session_state.user['username'] if st.session_state.user else "Unknown"
            st.metric("Current User", current_user)
        
        # Page visit breakdown
        st.markdown("#### Page Visit Breakdown")
        if st.session_state.page_visits:
            visit_data = pd.DataFrame([
                {"Page": page, "Visits": visits} 
                for page, visits in st.session_state.page_visits.items()
            ])
            fig = px.bar(visit_data, x="Page", y="Visits", color_discrete_sequence=["#69b3ff"])
            fig.update_layout(xaxis_tickangle=-90, xaxis_title=None, yaxis_title=None, height=300,
                              plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)')
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No page visits recorded yet.")
        
        # Session information
        st.markdown("#### Session Information")
        col1, col2 = st.columns(2)
        
        with col1:
            st.metric("Session Duration", "Active")
            st.metric("User Role", st.session_state.user['role'].title())
        
        with col2:
            st.metric("Login Time", "Current Session")
            st.metric("Last Activity", "Now")
    
    with tab3:
        # Enhanced Analytics Dashboard
        try:
            from analytics_dashboard import render_analytics_dashboard
            render_analytics_dashboard()
        except Exception as e:
            st.error(f"Analytics dashboard error: {e}")
            st.info("Please ensure all analytics dependencies are installed.")
    
    with tab4:
        st.subheader("System Settings")
        st.info("System settings will be implemented here.")

if __name__ == "__main__":
    main()
