"""
Mixpanel Integration for Navira
Requires: pip install mixpanel
"""

import streamlit as st
from datetime import datetime
import json

class MixpanelTracker:
    def __init__(self, project_token: str):
        """
        Initialize Mixpanel tracking
        
        Args:
            project_token: Mixpanel Project Token
        """
        self.project_token = project_token
        
    def track_event(self, event_name: str, properties: dict = None, user_id: str = None):
        """Track an event in Mixpanel"""
        try:
            import mixpanel
            
            mp = mixpanel.Mixpanel(self.project_token)
            
            # Prepare properties
            event_properties = properties or {}
            event_properties.update({
                "timestamp": datetime.now().isoformat(),
                "platform": "streamlit",
                "app": "navira"
            })
            
            # Track event
            if user_id:
                mp.track(user_id, event_name, event_properties)
            else:
                mp.track("anonymous", event_name, event_properties)
                
            return True
            
        except Exception as e:
            st.error(f"Mixpanel tracking error: {e}")
            return False
    
    def identify_user(self, user_id: str, user_properties: dict):
        """Identify a user with properties"""
        try:
            import mixpanel
            
            mp = mixpanel.Mixpanel(self.project_token)
            mp.people_set(user_id, user_properties)
            return True
            
        except Exception as e:
            st.error(f"Mixpanel user identification error: {e}")
            return False
    
    def track_page_view(self, page_name: str, user_id: str = None):
        """Track page view"""
        properties = {
            "page_name": page_name,
            "page_category": "navigation",
            "session_id": self._get_session_id()
        }
        return self.track_event("Page Viewed", properties, user_id)
    
    def track_user_action(self, action: str, page: str, user_id: str = None):
        """Track user actions"""
        properties = {
            "action": action,
            "page": page,
            "action_category": "user_interaction",
            "session_id": self._get_session_id()
        }
        return self.track_event("User Action", properties, user_id)
    
    def track_data_export(self, export_type: str, filters: dict, user_id: str = None):
        """Track data export events"""
        properties = {
            "export_type": export_type,
            "filters_applied": json.dumps(filters),
            "action_category": "data_export"
        }
        return self.track_event("Data Exported", properties, user_id)
    
    def track_search(self, search_term: str, results_count: int, user_id: str = None):
        """Track search events"""
        properties = {
            "search_term": search_term,
            "results_count": results_count,
            "action_category": "search"
        }
        return self.track_event("Search Performed", properties, user_id)
    
    def _get_session_id(self):
        """Get or generate session ID"""
        if 'mixpanel_session_id' not in st.session_state:
            import uuid
            st.session_state.mixpanel_session_id = str(uuid.uuid4())
        return st.session_state.mixpanel_session_id

# Usage example:
# mp = MixpanelTracker("your_project_token")
# mp.track_page_view("dashboard", user_id="123")
# mp.track_user_action("button_click", "dashboard", user_id="123")
# mp.identify_user("123", {"username": "john_doe", "role": "user"})
