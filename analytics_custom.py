"""
Custom Database Analytics for Navira
Tracks detailed user activity in SQLite database
"""

import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import json
from typing import Dict, List, Optional
from auth import DB_PATH

class CustomAnalytics:
    def __init__(self):
        """Initialize custom analytics system"""
        self.init_analytics_tables()
    
    def init_analytics_tables(self):
        """Initialize analytics tables in database"""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # User activity table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_activity (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                username TEXT,
                activity_type TEXT,
                page_name TEXT,
                action_details TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                session_id TEXT,
                ip_address TEXT,
                user_agent TEXT,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        
        # Page views table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS page_views (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                page_name TEXT,
                view_duration INTEGER,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                session_id TEXT,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        
        # User sessions table (enhanced)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS analytics_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                session_id TEXT UNIQUE,
                start_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                end_time DATETIME,
                total_actions INTEGER DEFAULT 0,
                pages_visited TEXT,
                device_info TEXT,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        
        # Data export tracking
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS data_exports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                export_type TEXT,
                filters_applied TEXT,
                records_exported INTEGER,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def track_activity(self, user_id: int, username: str, activity_type: str, 
                      page_name: str, action_details: str = None):
        """Track user activity"""
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO user_activity 
                (user_id, username, activity_type, page_name, action_details, session_id)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (user_id, username, activity_type, page_name, 
                  json.dumps(action_details) if action_details else None,
                  self._get_session_id()))
            
            conn.commit()
            conn.close()
            return True
            
        except Exception as e:
            st.error(f"Activity tracking error: {e}")
            return False
    
    def track_page_view(self, user_id: int, username: str, page_name: str, 
                       view_duration: int = 0):
        """Track page view with duration"""
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO page_views 
                (user_id, page_name, view_duration, session_id)
                VALUES (?, ?, ?, ?)
            ''', (user_id, page_name, view_duration, self._get_session_id()))
            
            conn.commit()
            conn.close()
            return True
            
        except Exception as e:
            st.error(f"Page view tracking error: {e}")
            return False
    
    def track_data_export(self, user_id: int, export_type: str, 
                         filters_applied: dict, records_exported: int):
        """Track data export events"""
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO data_exports 
                (user_id, export_type, filters_applied, records_exported)
                VALUES (?, ?, ?, ?)
            ''', (user_id, export_type, json.dumps(filters_applied), records_exported))
            
            conn.commit()
            conn.close()
            return True
            
        except Exception as e:
            st.error(f"Data export tracking error: {e}")
            return False
    
    def get_user_analytics(self, user_id: int, days: int = 30) -> Dict:
        """Get analytics for a specific user"""
        conn = sqlite3.connect(DB_PATH)
        
        # Get activity summary
        activity_df = pd.read_sql_query('''
            SELECT activity_type, COUNT(*) as count
            FROM user_activity 
            WHERE user_id = ? AND timestamp >= datetime('now', '-{} days')
            GROUP BY activity_type
        '''.format(days), conn, params=(user_id,))
        
        # Get page views
        page_views_df = pd.read_sql_query('''
            SELECT page_name, COUNT(*) as views, AVG(view_duration) as avg_duration
            FROM page_views 
            WHERE user_id = ? AND timestamp >= datetime('now', '-{} days')
            GROUP BY page_name
        '''.format(days), conn, params=(user_id,))
        
        # Get data exports
        exports_df = pd.read_sql_query('''
            SELECT export_type, COUNT(*) as count, SUM(records_exported) as total_records
            FROM data_exports 
            WHERE user_id = ? AND timestamp >= datetime('now', '-{} days')
            GROUP BY export_type
        '''.format(days), conn, params=(user_id,))
        
        conn.close()
        
        return {
            'activity_summary': activity_df.to_dict('records'),
            'page_views': page_views_df.to_dict('records'),
            'data_exports': exports_df.to_dict('records')
        }
    
    def get_platform_analytics(self, days: int = 30) -> Dict:
        """Get platform-wide analytics"""
        conn = sqlite3.connect(DB_PATH)
        
        # Overall stats
        total_users = pd.read_sql_query("SELECT COUNT(*) as count FROM users", conn).iloc[0]['count']
        active_users = pd.read_sql_query('''
            SELECT COUNT(DISTINCT user_id) as count 
            FROM user_activity 
            WHERE timestamp >= datetime('now', '-{} days')
        '''.format(days), conn).iloc[0]['count']
        
        # Most active pages
        popular_pages = pd.read_sql_query('''
            SELECT page_name, COUNT(*) as views
            FROM page_views 
            WHERE timestamp >= datetime('now', '-{} days')
            GROUP BY page_name
            ORDER BY views DESC
            LIMIT 10
        '''.format(days), conn)
        
        # Activity by type
        activity_by_type = pd.read_sql_query('''
            SELECT activity_type, COUNT(*) as count
            FROM user_activity 
            WHERE timestamp >= datetime('now', '-{} days')
            GROUP BY activity_type
            ORDER BY count DESC
        '''.format(days), conn)
        
        # Daily activity
        daily_activity = pd.read_sql_query('''
            SELECT DATE(timestamp) as date, COUNT(*) as activities
            FROM user_activity 
            WHERE timestamp >= datetime('now', '-{} days')
            GROUP BY DATE(timestamp)
            ORDER BY date
        '''.format(days), conn)
        
        conn.close()
        
        return {
            'total_users': total_users,
            'active_users': active_users,
            'popular_pages': popular_pages.to_dict('records'),
            'activity_by_type': activity_by_type.to_dict('records'),
            'daily_activity': daily_activity.to_dict('records')
        }
    
    def _get_session_id(self) -> str:
        """Get or generate session ID"""
        if 'analytics_session_id' not in st.session_state:
            import uuid
            st.session_state.analytics_session_id = str(uuid.uuid4())
        return st.session_state.analytics_session_id

# Usage example:
# analytics = CustomAnalytics()
# analytics.track_activity(123, "john_doe", "button_click", "dashboard", {"button": "export"})
# analytics.track_page_view(123, "john_doe", "dashboard", 300)
# analytics.track_data_export(123, "csv", {"filter": "active"}, 1500)
