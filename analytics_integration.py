"""
Simple Analytics Integration for Navira
Integrates Google Analytics 4 with consent manager
"""

import streamlit as st
from analytics_ga4 import GoogleAnalytics4, setup_ga4_tracking


class NaviraAnalytics:
    def __init__(self):
        self.ga4 = GoogleAnalytics4()
        self._tracking_ready = False
        self.setup_tracking()

    def setup_tracking(self):
        try:
            setup_ga4_tracking()
            self._tracking_ready = True
        except Exception:
            self._tracking_ready = False

    def track_page_view(self, page_name: str):
        if not self._tracking_ready:
            return
        uid = None
        if st.session_state.get("authenticated") and st.session_state.get("user"):
            uid = str(st.session_state.user['id'])
        self.ga4.track_page_view(page_name, uid)

    def track_user_action(self, action: str, page: str, details: dict | None = None):
        if not self._tracking_ready:
            return
        uid = None
        if st.session_state.get("authenticated") and st.session_state.get("user"):
            uid = str(st.session_state.user['id'])
        params = details.copy() if details else {}
        self.ga4.track_user_action(action, page, uid)

    def track_login(self, username: str):
        if not self._tracking_ready:
            return
        uid = None
        if st.session_state.get("authenticated") and st.session_state.get("user"):
            uid = str(st.session_state.user['id'])
        self.ga4.track_event("user_login", {"username": username, "user_id": uid})

    def track_data_export(self, export_type: str, records_count: int, filters: dict | None = None):
        if not self._tracking_ready:
            return
        uid = None
        if st.session_state.get("authenticated") and st.session_state.get("user"):
            uid = str(st.session_state.user['id'])
        params = {"export_type": export_type, "records_count": records_count, "user_id": uid}
        if filters:
            params["filters"] = str(filters)
        self.ga4.track_event("data_export", params)

    def track_search(self, search_term: str, results_count: int):
        if not self._tracking_ready:
            return
        uid = None
        if st.session_state.get("authenticated") and st.session_state.get("user"):
            uid = str(st.session_state.user['id'])
        self.ga4.track_event("search_performed", {"search_term": search_term, "results_count": results_count, "user_id": uid})


_analytics = None

def init_analytics():
    global _analytics
    if _analytics is None:
        _analytics = NaviraAnalytics()
    return _analytics


def get_analytics():
    return init_analytics()


# Convenience wrappers

def track_page_view(page_name: str):
    get_analytics().track_page_view(page_name)


def track_user_action(action: str, page: str, details: dict | None = None):
    get_analytics().track_user_action(action, page, details)


def track_login(username: str):
    get_analytics().track_login(username)


def track_data_export(export_type: str, records_count: int, filters: dict | None = None):
    get_analytics().track_data_export(export_type, records_count, filters)


def track_search(search_term: str, results_count: int):
    get_analytics().track_search(search_term, results_count)
