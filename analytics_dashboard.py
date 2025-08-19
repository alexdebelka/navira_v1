"""
Enhanced Analytics Dashboard for Admin Panel
Integrates multiple analytics sources
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import sqlite3
from auth import DB_PATH
from analytics_custom import CustomAnalytics

def render_analytics_dashboard():
    """Render the enhanced analytics dashboard"""
    st.subheader("📊 Advanced Analytics Dashboard")
    
    # Initialize analytics
    analytics = CustomAnalytics()
    
    # Time period selector
    col1, col2, col3 = st.columns(3)
    with col1:
        time_period = st.selectbox(
            "Time Period",
            ["Last 7 days", "Last 30 days", "Last 90 days", "Last year"],
            index=1
        )
    
    with col2:
        analytics_type = st.selectbox(
            "Analytics Type",
            ["Platform Overview", "User Activity", "Page Performance", "Data Usage"],
            index=0
        )
    
    with col3:
        if st.button("🔄 Refresh Analytics", type="primary"):
            st.rerun()
    
    # Convert time period to days
    days_map = {
        "Last 7 days": 7,
        "Last 30 days": 30,
        "Last 90 days": 90,
        "Last year": 365
    }
    days = days_map[time_period]
    
    # Get analytics data
    platform_data = analytics.get_platform_analytics(days)
    
    if analytics_type == "Platform Overview":
        render_platform_overview(platform_data, days)
    elif analytics_type == "User Activity":
        render_user_activity(analytics, days)
    elif analytics_type == "Page Performance":
        render_page_performance(platform_data)
    elif analytics_type == "Data Usage":
        render_data_usage(analytics, days)

def render_platform_overview(data, days):
    """Render platform overview analytics"""
    st.markdown("### 🏥 Platform Overview")
    
    # Key metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "Total Users", 
            data['total_users'],
            help="Total registered users"
        )
    
    with col2:
        st.metric(
            "Active Users", 
            data['active_users'],
            delta=f"{data['active_users']} in last {days} days",
            help="Users active in the selected period"
        )
    
    with col3:
        # Calculate engagement rate
        engagement_rate = (data['active_users'] / data['total_users'] * 100) if data['total_users'] > 0 else 0
        st.metric(
            "Engagement Rate", 
            f"{engagement_rate:.1f}%",
            help="Percentage of total users active in the period"
        )
    
    with col4:
        # Get total activities
        total_activities = sum(item['count'] for item in data['activity_by_type'])
        st.metric(
            "Total Activities", 
            total_activities,
            help="Total user activities in the period"
        )
    
    st.markdown("---")
    
    # Daily activity chart
    if data['daily_activity']:
        st.markdown("### 📈 Daily Activity Trend")
        daily_df = pd.DataFrame(data['daily_activity'])
        daily_df['date'] = pd.to_datetime(daily_df['date'])
        
        fig = px.line(
            daily_df, 
            x='date', 
            y='activities',
            title=f"Daily User Activities - Last {days} Days",
            labels={'activities': 'Activities', 'date': 'Date'}
        )
        fig.update_layout(height=400)
        st.plotly_chart(fig, use_container_width=True)
    
    # Activity breakdown
    if data['activity_by_type']:
        st.markdown("### 🎯 Activity Breakdown")
        activity_df = pd.DataFrame(data['activity_by_type'])
        
        col1, col2 = st.columns(2)
        
        with col1:
            fig = px.pie(
                activity_df, 
                values='count', 
                names='activity_type',
                title="Activities by Type"
            )
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            fig = px.bar(
                activity_df, 
                x='activity_type', 
                y='count',
                title="Activities by Type (Bar Chart)"
            )
            fig.update_xaxis(tickangle=45)
            st.plotly_chart(fig, use_container_width=True)

def render_user_activity(analytics, days):
    """Render user activity analytics"""
    st.markdown("### 👥 User Activity Analysis")
    
    # Get user list for selection
    conn = sqlite3.connect(DB_PATH)
    users_df = pd.read_sql_query("""
        SELECT id, username, role, created_at 
        FROM users 
        ORDER BY username
    """, conn)
    conn.close()
    
    # User selector
    selected_user = st.selectbox(
        "Select User for Detailed Analysis",
        options=users_df['username'].tolist(),
        index=0
    )
    
    if selected_user:
        user_id = users_df[users_df['username'] == selected_user]['id'].iloc[0]
        user_data = analytics.get_user_analytics(user_id, days)
        
        # User summary
        col1, col2, col3 = st.columns(3)
        
        with col1:
            total_activities = sum(item['count'] for item in user_data['activity_summary'])
            st.metric("Total Activities", total_activities)
        
        with col2:
            total_views = sum(item['views'] for item in user_data['page_views'])
            st.metric("Page Views", total_views)
        
        with col3:
            total_exports = sum(item['count'] for item in user_data['data_exports'])
            st.metric("Data Exports", total_exports)
        
        # Activity details
        if user_data['activity_summary']:
            st.markdown("#### 📊 Activity Summary")
            activity_df = pd.DataFrame(user_data['activity_summary'])
            st.dataframe(activity_df, use_container_width=True)
        
        if user_data['page_views']:
            st.markdown("#### 📄 Page Views")
            views_df = pd.DataFrame(user_data['page_views'])
            fig = px.bar(
                views_df, 
                x='page_name', 
                y='views',
                title=f"Page Views for {selected_user}"
            )
            st.plotly_chart(fig, use_container_width=True)

def render_page_performance(data):
    """Render page performance analytics"""
    st.markdown("### 📄 Page Performance")
    
    if data['popular_pages']:
        pages_df = pd.DataFrame(data['popular_pages'])
        
        col1, col2 = st.columns(2)
        
        with col1:
            fig = px.bar(
                pages_df, 
                x='page_name', 
                y='views',
                title="Most Visited Pages",
                labels={'views': 'Page Views', 'page_name': 'Page'}
            )
            fig.update_xaxis(tickangle=45)
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            fig = px.pie(
                pages_df, 
                values='views', 
                names='page_name',
                title="Page Views Distribution"
            )
            st.plotly_chart(fig, use_container_width=True)
        
        # Page performance table
        st.markdown("#### 📋 Page Performance Details")
        st.dataframe(pages_df, use_container_width=True)

def render_data_usage(analytics, days):
    """Render data usage analytics"""
    st.markdown("### 💾 Data Usage Analytics")
    
    # Get data export statistics
    conn = sqlite3.connect(DB_PATH)
    exports_df = pd.read_sql_query(f"""
        SELECT 
            u.username,
            de.export_type,
            COUNT(*) as export_count,
            SUM(de.records_exported) as total_records
        FROM data_exports de
        JOIN users u ON de.user_id = u.id
        WHERE de.timestamp >= datetime('now', '-{days} days')
        GROUP BY u.username, de.export_type
        ORDER BY total_records DESC
    """, conn)
    conn.close()
    
    if not exports_df.empty:
        # Export summary
        col1, col2, col3 = st.columns(3)
        
        with col1:
            total_exports = exports_df['export_count'].sum()
            st.metric("Total Exports", total_exports)
        
        with col2:
            total_records = exports_df['total_records'].sum()
            st.metric("Records Exported", f"{total_records:,}")
        
        with col3:
            avg_records = total_records / total_exports if total_exports > 0 else 0
            st.metric("Avg Records/Export", f"{avg_records:.0f}")
        
        # Export breakdown
        st.markdown("#### 📊 Export Breakdown by User")
        fig = px.bar(
            exports_df, 
            x='username', 
            y='total_records',
            color='export_type',
            title="Data Exports by User and Type",
            labels={'total_records': 'Records Exported', 'username': 'User'}
        )
        fig.update_xaxis(tickangle=45)
        st.plotly_chart(fig, use_container_width=True)
        
        # Export type breakdown
        export_type_summary = exports_df.groupby('export_type').agg({
            'export_count': 'sum',
            'total_records': 'sum'
        }).reset_index()
        
        col1, col2 = st.columns(2)
        
        with col1:
            fig = px.pie(
                export_type_summary, 
                values='export_count', 
                names='export_type',
                title="Exports by Type"
            )
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            fig = px.pie(
                export_type_summary, 
                values='total_records', 
                names='export_type',
                title="Records Exported by Type"
            )
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No data export activity recorded in the selected period.")

# Usage in admin panel:
# from analytics_dashboard import render_analytics_dashboard
# render_analytics_dashboard()
