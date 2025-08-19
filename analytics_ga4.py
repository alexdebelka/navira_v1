"""
Google Analytics 4 Integration for Navira
Requires: pip install streamlit-google-analytics
"""

import streamlit as st
from datetime import datetime, timedelta
import json

class GoogleAnalytics4:
    def __init__(self, measurement_id: str = "G-BQVC35G1QE", api_secret: str = None):
        """
        Initialize GA4 tracking
        
        Args:
            measurement_id: GA4 Measurement ID (G-BQVC35G1QE)
            api_secret: GA4 API Secret (optional for client-side tracking)
        """
        self.measurement_id = measurement_id
        self.api_secret = api_secret
        self.base_url = "https://www.google-analytics.com/mp/collect"
        
    def track_event(self, event_name: str, parameters: dict = None):
        """Track a custom event"""
        try:
            import requests
            
            payload = {
                "client_id": self._get_client_id(),
                "events": [{
                    "name": event_name,
                    "params": parameters or {}
                }]
            }
            
            url = f"{self.base_url}?measurement_id={self.measurement_id}&api_secret={self.api_secret}"
            response = requests.post(url, json=payload)
            return response.status_code == 204
            
        except Exception as e:
            st.error(f"GA4 tracking error: {e}")
            return False
    
    def track_page_view(self, page_name: str, user_id: str = None):
        """Track page view"""
        params = {
            "page_title": page_name,
            "page_location": f"https://navira.app/{page_name}",
            "engagement_time_msec": "1000"
        }
        
        if user_id:
            params["user_id"] = user_id
            
        return self.track_event("page_view", params)
    
    def track_user_action(self, action: str, page: str, user_id: str = None):
        """Track user actions (button clicks, form submissions, etc.)"""
        params = {
            "action": action,
            "page": page,
            "timestamp": datetime.now().isoformat()
        }
        
        if user_id:
            params["user_id"] = user_id
            
        return self.track_event("user_action", params)
    
    def _get_client_id(self):
        """Get or generate client ID for tracking"""
        if 'ga4_client_id' not in st.session_state:
            import uuid
            st.session_state.ga4_client_id = str(uuid.uuid4())
        return st.session_state.ga4_client_id

def setup_ga4_tracking():
    """Setup GA4 tracking in Streamlit with consent manager"""
    # Add GA4 script and consent manager to page
    st.markdown("""
    <!-- Google tag (gtag.js) -->
    <script async src="https://www.googletagmanager.com/gtag/js?id=G-BQVC35G1QE"></script>
    <script>
      window.dataLayer = window.dataLayer || [];
      function gtag(){dataLayer.push(arguments);}
      gtag('js', new Date());
      gtag('config', 'G-BQVC35G1QE');
    </script>
    
    <!-- Consent Manager -->
    <script type="text/javascript" data-cmp-ab="1" src="https://cdn.consentmanager.net/delivery/autoblocking/9abc9467a29c1.js" data-cmp-host="b.delivery.consentmanager.net" data-cmp-cdn="cdn.consentmanager.net" data-cmp-codesrc="16"></script>
    """, unsafe_allow_html=True)

# Usage example:
# ga4 = GoogleAnalytics4()  # Uses default G-BQVC35G1QE
# ga4.track_page_view("dashboard", user_id="123")
# ga4.track_user_action("button_click", "dashboard", user_id="123")
