import streamlit as st
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
		
		# Admin section (only for admin users)
		if st.session_state.user['role'] == 'admin':
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
