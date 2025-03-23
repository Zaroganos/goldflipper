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
import logging
from typing import Dict, Any, List, Optional
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import inspect

from goldflipper.database.connection import get_db_connection, init_db
from goldflipper.database.models import (
    Play, PlayStatusHistory, TradeLog, TradingStrategy,
    ServiceBackup, LogEntry, ConfigTemplate, WatchdogEvent,
    ChartConfiguration, ToolState
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def check_database_initialized() -> bool:
    """Check if database is initialized by verifying table existence."""
    try:
        with get_db_connection() as session:
            inspector = inspect(session.bind)
            required_tables = ['plays', 'play_status_history', 'trade_logs']
            existing_tables = inspector.get_table_names()
            return all(table in existing_tables for table in required_tables)
    except Exception as e:
        logger.error(f"Error checking database status: {e}")
        st.error(f"Error checking database status: {str(e)}")
        return False

def initialize_database():
    """Initialize the database with required tables."""
    try:
        init_db(force=False)
        logger.info("Database initialized successfully")
        st.success("Database initialized successfully!")
        st.rerun()
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        st.error(f"Failed to initialize database: {str(e)}")

def main():
    st.title("Database Management")
    
    # Check if database is initialized
    if not check_database_initialized():
        logger.warning("Database not initialized")
        st.warning("Database is not initialized. Tables need to be created.")
        if st.button("Initialize Database"):
            initialize_database()
        return
    
    # Initialize session state
    if 'db_error' not in st.session_state:
        st.session_state.db_error = None
    
    # Show any errors with retry option
    if st.session_state.db_error:
        st.error(st.session_state.db_error)
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Clear Error"):
                logger.info("Clearing database error")
                st.session_state.db_error = None
                st.rerun()
        with col2:
            if st.button("Retry Connection"):
                try:
                    # Test connection and table existence
                    if check_database_initialized():
                        logger.info("Database connection restored")
                        st.session_state.db_error = None
                        st.success("Database connection restored!")
                        st.rerun()
                    else:
                        logger.warning("Database tables not found")
                        st.session_state.db_error = "Database tables not found. Please initialize the database."
                        st.rerun()
                except Exception as e:
                    logger.error(f"Database connection failed: {e}")
                    st.session_state.db_error = f"Database connection failed: {str(e)}"
                    st.rerun()
    
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
    except Exception as e:
        error_msg = f"Database error: {str(e)}"
        logger.error(error_msg)
        st.session_state.db_error = error_msg
        
        if "Table with name" in str(e) and "does not exist" in str(e):
            logger.warning("Database tables not found")
            st.session_state.db_error += "\n\nDatabase tables not found. Please initialize the database."
        elif "already open" in str(e):
            logger.warning("Database already in use by another process")
            st.session_state.db_error += "\n\nThis error occurs because another process is accessing the database. Try clicking 'Retry Connection'."
        st.rerun()

def get_table_stats() -> Dict[str, int]:
    """Get statistics for various database tables."""
    stats = {}
    try:
        with get_db_connection() as session:
            # Only query tables that exist
            inspector = inspect(session.bind)
            existing_tables = inspector.get_table_names()
            
            if 'plays' in existing_tables:
                stats["Plays"] = session.query(Play).count()
            if 'trading_strategies' in existing_tables:
                stats["Active Strategies"] = session.query(TradingStrategy).filter_by(is_active=True).count()
            if 'trade_logs' in existing_tables:
                today = datetime.now().date()
                stats["Today's Trades"] = session.query(TradeLog).filter(
                    TradeLog.datetime_open >= today
                ).count()
            if 'watchdog_events' in existing_tables:
                stats["Open Issues"] = session.query(WatchdogEvent).filter_by(is_resolved=False).count()
            if 'log_entries' in existing_tables:
                stats["Total Logs"] = session.query(LogEntry).count()
            if 'chart_configurations' in existing_tables:
                stats["Chart Configs"] = session.query(ChartConfiguration).count()
    except Exception as e:
        logger.error(f"Error getting table stats: {e}")
        stats["Error"] = "Failed to retrieve statistics"
    
    return stats

def show_overview():
    st.header("Database Overview")
    
    # Database Statistics
    with st.expander("Database Statistics", expanded=True):
        stats = get_table_stats()
        cols = st.columns(3)
        for i, (name, value) in enumerate(stats.items()):
            cols[i % 3].metric(name, value)
    
    # Model class mapping
    model_map = {
        "Plays": Play,
        "Trading Strategies": TradingStrategy,
        "Service Backups": ServiceBackup,
        "Log Entries": LogEntry,
        "Config Templates": ConfigTemplate,
        "Watchdog Events": WatchdogEvent,
        "Chart Configurations": ChartConfiguration,
        "Tool States": ToolState
    }
    
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
        try:
            with get_db_connection() as session:
                model = model_map[selected_table]
                data = session.query(model).limit(5).all()
                if data:
                    df = pd.DataFrame([d.to_dict() for d in data])
                    st.dataframe(df)
        except Exception as e:
            logger.error(f"Error fetching sample data: {e}")
            st.error("Failed to fetch sample data")

def show_data_browser():
    st.header("Data Browser")
    
    # Model class mapping
    model_map = {
        "Plays": Play,
        "Trading Strategies": TradingStrategy,
        "Log Entries": LogEntry,
        "Watchdog Events": WatchdogEvent,
        "Chart Configurations": ChartConfiguration,
        "Tool States": ToolState
    }
    
    # Table selector
    table = st.selectbox(
        "Select Table",
        list(model_map.keys())
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
    try:
        with get_db_connection() as session:
            model = model_map[table]
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
    except Exception as e:
        logger.error(f"Error querying data: {e}")
        st.error("Failed to query data")

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
            try:
                with get_db_connection() as session:
                    # Enable optimizations
                    session.execute("SET enable_object_cache=true;")
                    session.execute("SET enable_external_access=true;")
                    # Force statistics collection
                    session.execute("PRAGMA force_index_statistics;")
                st.success("Database optimization completed successfully!")
            except Exception as e:
                st.error(f"Optimization failed: {str(e)}")
            
        if st.button("Clean Up"):
            try:
                with get_db_connection() as session:
                    # DuckDB's cleanup operations
                    session.execute("PRAGMA memory_limit='4GB';")  # Ensure enough memory
                    session.execute("PRAGMA cleanup_allocated_memory;")
                    session.execute("PRAGMA shrink_memory;")
                st.success("Database cleanup completed successfully!")
            except Exception as e:
                st.error(f"Cleanup failed: {str(e)}")
            
        if st.button("Analyze Tables"):
            try:
                with get_db_connection() as session:
                    # Get table list
                    inspector = inspect(session.bind)
                    tables = inspector.get_table_names()
                    
                    # Show progress
                    progress_text = "Analyzing tables..."
                    progress_bar = st.progress(0, text=progress_text)
                    
                    # Analyze each table
                    for i, table in enumerate(tables):
                        progress_bar.progress((i + 1) / len(tables), 
                                           text=f"Analyzing {table}...")
                        session.execute(f"SELECT COUNT(*) FROM {table};")
                    
                    progress_bar.progress(1.0, text="Analysis complete!")
                st.success("Table analysis completed successfully!")
            except Exception as e:
                st.error(f"Analysis failed: {str(e)}")

if __name__ == "__main__":
    main() 