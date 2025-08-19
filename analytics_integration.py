"""
Simple Analytics Integration for Navira
Integrates Google Analytics 4 with consent manager
"""

import streamlit as st
from analytics_ga4 import GoogleAnalytics4, setup_ga4_tracking

class NaviraAnalytics:
    def __init__(self):
        """Initialize Navira analytics with GA4"""
        self.ga4 = GoogleAnalytics4()  # Uses your G-BQVC35G1QE ID
        self.setup_tracking()
    
    def setup_tracking(self):
        """Setup GA4 tracking with consent manager"""
        setup_ga4_tracking()
    
    def track_page_view(self, page_name: str):
        """Track page view for current user"""
        if st.session_state.authenticated and st.session_state.user:
            user_id = str(st.session_state.user['id'])
            self.ga4.track_page_view(page_name, user_id)
    
    def track_user_action(self, action: str, page: str, details: dict = None):
        """Track user action for current user"""
        if st.session_state.authenticated and st.session_state.user:
            user_id = str(st.session_state.user['id'])
            self.ga4.track_user_action(action, page, user_id)
    
    def track_login(self, username: str):
        """Track user login"""
        if st.session_state.authenticated and st.session_state.user:
            user_id = str(st.session_state.user['id'])
            self.ga4.track_event("user_login", {
                "username": username,
                "user_id": user_id,
                "user_role": st.session_state.user['role']
            })
    
    def track_data_export(self, export_type: str, records_count: int, filters: dict = None):
        """Track data export events"""
        if st.session_state.authenticated and st.session_state.user:
            user_id = str(st.session_state.user['id'])
            params = {
                "export_type": export_type,
                "records_count": records_count,
                "user_id": user_id
            }
            if filters:
                params["filters"] = str(filters)
            self.ga4.track_event("data_export", params)
    
    def track_search(self, search_term: str, results_count: int):
        """Track search events"""
        if st.session_state.authenticated and st.session_state.user:
            user_id = str(st.session_state.user['id'])
            self.ga4.track_event("search_performed", {
                "search_term": search_term,
                "results_count": results_count,
                "user_id": user_id
            })

# Global analytics instance
analytics = None

def init_analytics():
    """Initialize analytics globally"""
    global analytics
    if analytics is None:
        analytics = NaviraAnalytics()
    return analytics

def get_analytics():
    """Get the global analytics instance"""
    global analytics
    if analytics is None:
        analytics = init_analytics()
    return analytics

# Convenience functions for easy tracking
def track_page_view(page_name: str):
    """Track page view"""
    analytics = get_analytics()
    analytics.track_page_view(page_name)

def track_user_action(action: str, page: str, details: dict = None):
    """Track user action"""
    analytics = get_analytics()
    analytics.track_user_action(action, page, details)

def track_login(username: str):
    """Track user login"""
    analytics = get_analytics()
    analytics.track_login(username)

def track_data_export(export_type: str, records_count: int, filters: dict = None):
    """Track data export"""
    analytics = get_analytics()
    analytics.track_data_export(export_type, records_count, filters)

def track_search(search_term: str, results_count: int):
    """Track search"""
    analytics = get_analytics()
    analytics.track_search(search_term, results_count)
