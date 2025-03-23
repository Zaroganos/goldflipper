"""
Database Management and Visualization Page

This page provides a comprehensive interface for:
1. Viewing database structure and contents
2. Managing data and configurations
3. Monitoring database performance
4. Administering the database
"""

import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
import uuid
from typing import Dict, Any, List, Optional
from sqlalchemy.exc import SQLAlchemyError

from goldflipper.database.connection import get_db_connection
from goldflipper.database.models import (
    Play, PlayStatusHistory, TradeLog, TradingStrategy,
    ServiceBackup, LogEntry, ConfigTemplate, WatchdogEvent,
    ChartConfiguration, ToolState
)

def main():
    st.title("Database Management")
    
    # Initialize session state
    if 'db_error' not in st.session_state:
        st.session_state.db_error = None
    
    # Show any errors
    if st.session_state.db_error:
        st.error(st.session_state.db_error)
        if st.button("Clear Error"):
            st.session_state.db_error = None
    
    # Sidebar navigation
    page = st.sidebar.selectbox(
        "Select View",
        ["Overview", "Data Browser", "Monitoring", "Administration"]
    )
    
    try:
        if page == "Overview":
            show_overview()
        elif page == "Data Browser":
            show_data_browser()
        elif page == "Monitoring":
            show_monitoring()
        else:
            show_administration()
    except SQLAlchemyError as e:
        st.session_state.db_error = f"Database error: {str(e)}"
        st.experimental_rerun()

def get_table_stats() -> Dict[str, int]:
    """Get statistics for each table."""
    with get_db_connection() as session:
        return {
            "Plays": session.query(Play).count(),
            "Active Strategies": session.query(TradingStrategy)
                .filter(TradingStrategy.is_active == True).count(),
            "Today's Trades": session.query(TradeLog)
                .filter(TradeLog.datetime_open >= datetime.now().date()).count(),
            "Open Issues": session.query(WatchdogEvent)
                .filter(WatchdogEvent.is_resolved == False).count(),
            "Total Logs": session.query(LogEntry).count(),
            "Chart Configs": session.query(ChartConfiguration).count()
        }

def show_overview():
    st.header("Database Overview")
    
    # Database Statistics
    with st.expander("Database Statistics", expanded=True):
        stats = get_table_stats()
        cols = st.columns(3)
        for i, (name, value) in enumerate(stats.items()):
            cols[i % 3].metric(name, value)
    
    # Table Structure
    with st.expander("Table Structure", expanded=True):
        tables = {
            "Plays": ["play_id", "symbol", "status", "trade_type", "strike_price", "expiration_date"],
            "Trading Strategies": ["strategy_id", "name", "parameters", "is_active"],
            "Service Backups": ["backup_id", "service_name", "state_data", "is_valid"],
            "Log Entries": ["log_id", "level", "message", "component"],
            "Config Templates": ["template_id", "name", "schema", "version"],
            "Watchdog Events": ["event_id", "component", "details", "is_resolved"],
            "Chart Configurations": ["config_id", "chart_type", "settings", "is_default"],
            "Tool States": ["tool_id", "tool_name", "last_state", "is_active"]
        }
        
        selected_table = st.selectbox("Select Table", list(tables.keys()))
        st.subheader(f"{selected_table} Schema")
        st.code(", ".join(tables[selected_table]))
        
        # Show sample data
        with get_db_connection() as session:
            model = globals()[selected_table.replace(" ", "")]
            data = session.query(model).limit(5).all()
            if data:
                df = pd.DataFrame([d.to_dict() for d in data])
                st.dataframe(df)

def show_data_browser():
    st.header("Data Browser")
    
    # Table selector
    table = st.selectbox(
        "Select Table",
        ["Plays", "Trading Strategies", "Log Entries", "Watchdog Events",
         "Chart Configurations", "Tool States"]
    )
    
    # Filters
    with st.expander("Filters", expanded=True):
        filters = {}
        if table == "Plays":
            filters['status'] = st.multiselect(
                "Status",
                ["new", "open", "closed", "expired"]
            )
            filters['symbol'] = st.text_input("Symbol")
            
        elif table == "Log Entries":
            filters['level'] = st.multiselect(
                "Level",
                ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
            )
            filters['component'] = st.text_input("Component")
            
        elif table == "Trading Strategies":
            filters['is_active'] = st.checkbox("Active Only", True)
    
    # Query builder
    with get_db_connection() as session:
        model = globals()[table]
        query = session.query(model)
        
        # Apply filters
        if table == "Plays":
            if filters.get('status'):
                query = query.filter(model.status.in_(filters['status']))
            if filters.get('symbol'):
                query = query.filter(model.symbol == filters['symbol'])
                
        elif table == "Log Entries":
            if filters.get('level'):
                query = query.filter(model.level.in_(filters['level']))
            if filters.get('component'):
                query = query.filter(model.component == filters['component'])
                
        elif table == "Trading Strategies":
            if filters.get('is_active'):
                query = query.filter(model.is_active == True)
        
        # Display results
        results = pd.read_sql(query.statement, session.bind)
        if not results.empty:
            st.dataframe(results)
            
            # Export options
            if st.button("Export to CSV"):
                st.download_button(
                    "Download CSV",
                    results.to_csv(index=False),
                    f"{table.lower()}_{datetime.now().strftime('%Y%m%d')}.csv",
                    "text/csv"
                )
        else:
            st.info("No data found matching the filters.")

def show_monitoring():
    st.header("Database Monitoring")
    
    # Time range selector
    time_range = st.selectbox(
        "Time Range",
        ["Last Hour", "Last Day", "Last Week", "Last Month"]
    )
    
    # Calculate date range
    end_time = datetime.now()
    if time_range == "Last Hour":
        start_time = end_time - timedelta(hours=1)
        freq = "5min"
    elif time_range == "Last Day":
        start_time = end_time - timedelta(days=1)
        freq = "1H"
    elif time_range == "Last Week":
        start_time = end_time - timedelta(weeks=1)
        freq = "1D"
    else:
        start_time = end_time - timedelta(days=30)
        freq = "1D"
    
    # Performance metrics
    with st.expander("Performance Metrics", expanded=True):
        with get_db_connection() as session:
            # Query actual metrics
            log_counts = session.query(
                LogEntry.level,
                LogEntry.timestamp
            ).filter(
                LogEntry.timestamp.between(start_time, end_time)
            ).all()
            
            if log_counts:
                df = pd.DataFrame(log_counts, columns=['level', 'timestamp'])
                df = df.set_index('timestamp').resample(freq).count()
                
                # Log volume chart
                st.subheader("Log Volume")
                fig = px.line(df, y='level')
                st.plotly_chart(fig)
            else:
                st.info("No log data for the selected time range.")
            
            # System health
            health_metrics = {
                "Database Size": "1.2 GB",
                "Active Connections": "3",
                "Query Response Time": "45ms"
            }
            
            cols = st.columns(len(health_metrics))
            for i, (metric, value) in enumerate(health_metrics.items()):
                cols[i].metric(metric, value)

def show_administration():
    st.header("Database Administration")
    
    # Backup management
    with st.expander("Backup Management", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Create Backup"):
                st.info("Backup creation started...")
                # TODO: Implement backup creation
                
        with col2:
            uploaded_file = st.file_uploader("Restore from Backup")
            if uploaded_file:
                st.warning("This will overwrite current data. Are you sure?")
                if st.button("Confirm Restore"):
                    st.info("Restore started...")
                    # TODO: Implement restore
    
    # User management
    with st.expander("User Management", expanded=True):
        users = pd.DataFrame({
            'username': ['admin', 'user1', 'user2'],
            'role': ['admin', 'user', 'user'],
            'last_active': ['2024-03-21', '2024-03-20', '2024-03-19']
        })
        st.dataframe(users)
        
        # Add user form
        with st.form("add_user"):
            st.subheader("Add User")
            username = st.text_input("Username")
            role = st.selectbox("Role", ["user", "admin"])
            if st.form_submit_button("Add User"):
                st.info(f"Adding user {username} with role {role}")
                # TODO: Implement user addition
    
    # Maintenance
    with st.expander("Maintenance", expanded=True):
        if st.button("Optimize Database"):
            st.info("Database optimization started...")
            # TODO: Implement optimization
            
        if st.button("Vacuum"):
            st.info("Vacuum process started...")
            # TODO: Implement vacuum
            
        if st.button("Analyze Tables"):
            st.info("Table analysis started...")
            # TODO: Implement analysis

if __name__ == "__main__":
    main() 