"""
Google Analytics 4 Integration for Navira
Requires: requests
"""

import streamlit as st
from datetime import datetime


def _get_ga4_config():
    """Return GA config from Streamlit secrets with sane defaults."""
    measurement_id = "G-BQVC35G1QE"
    api_secret = None
    cmp_script_url = None
    cmp_host = None
    cmp_cdn = None
    cmp_codesrc = None

    if hasattr(st, "secrets") and st.secrets:
        ga4 = st.secrets.get("ga4", {})
        measurement_id = ga4.get("measurement_id", measurement_id)
        api_secret = ga4.get("api_secret", api_secret)
        cmp = st.secrets.get("consent_manager", {})
        cmp_script_url = cmp.get("script_url")
        cmp_host = cmp.get("host")
        cmp_cdn = cmp.get("cdn")
        cmp_codesrc = cmp.get("codesrc")

    return {
        "measurement_id": measurement_id,
        "api_secret": api_secret,
        "cmp_script_url": cmp_script_url,
        "cmp_host": cmp_host,
        "cmp_cdn": cmp_cdn,
        "cmp_codesrc": cmp_codesrc,
    }


class GoogleAnalytics4:
    def __init__(self, measurement_id: str | None = None, api_secret: str | None = None):
        cfg = _get_ga4_config()
        self.measurement_id = measurement_id or cfg["measurement_id"]
        self.api_secret = api_secret if api_secret is not None else cfg["api_secret"]
        self.base_url = "https://www.google-analytics.com/mp/collect"

    def track_event(self, event_name: str, parameters: dict | None = None) -> bool:
        """Send event via GA4 Measurement Protocol (requires api_secret)."""
        try:
            if not self.api_secret:
                # Skip silently if API secret not configured
                return False
            import requests

            payload = {
                "client_id": self._get_client_id(),
                "events": [
                    {
                        "name": event_name,
                        "params": parameters or {},
                    }
                ],
            }
            url = f"{self.base_url}?measurement_id={self.measurement_id}&api_secret={self.api_secret}"
            response = requests.post(url, json=payload, timeout=3)
            return response.status_code == 204
        except Exception:
            return False

    def track_page_view(self, page_name: str, user_id: str | None = None) -> bool:
        params = {
            "page_title": page_name,
            "page_location": f"/{page_name}",
            "engagement_time_msec": "1000",
        }
        if user_id:
            params["user_id"] = user_id
        return self.track_event("page_view", params)

    def track_user_action(self, action: str, page: str, user_id: str | None = None) -> bool:
        params = {
            "action": action,
            "page": page,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
        if user_id:
            params["user_id"] = user_id
        return self.track_event("user_action", params)

    def _get_client_id(self) -> str:
        if "ga4_client_id" not in st.session_state:
            import uuid
            st.session_state.ga4_client_id = str(uuid.uuid4())
        return st.session_state.ga4_client_id


def setup_ga4_tracking():
    """Inject GA4 gtag with consent mode and optional Consent Manager.
    Should be called on every page load (safe due to Streamlit reruns).
    """
    cfg = _get_ga4_config()
    mid = cfg["measurement_id"]

    # Base gtag with Consent Mode v2 (default denied)
    scripts = f"""
    <!-- Google tag (gtag.js) -->
    <script async src="https://www.googletagmanager.com/gtag/js?id={mid}"></script>
    <script>
      window.dataLayer = window.dataLayer || [];
      function gtag(){{dataLayer.push(arguments);}}
      gtag('consent', 'default', {{
        'ad_storage': 'denied',
        'ad_user_data': 'denied',
        'ad_personalization': 'denied',
        'analytics_storage': 'denied'
      }});
      gtag('js', new Date());
      gtag('config', '{mid}');
    </script>
    """

    # Optional Consent Manager (Consentmanager.net) if configured
    if cfg["cmp_script_url"]:
        # Autoconsent/Autoblocking script; CM will update gtag consent after user choice
        scripts += f"""
        <script type="text/javascript" data-cmp-ab="1" src="{cfg['cmp_script_url']}"
                data-cmp-host="{cfg.get('cmp_host','')}" data-cmp-cdn="{cfg.get('cmp_cdn','')}"
                data-cmp-codesrc="{cfg.get('cmp_codesrc','')}"></script>
        """

    # Inject once per run (safe to repeat across pages)
    st.markdown(scripts, unsafe_allow_html=True)
