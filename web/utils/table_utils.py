"""
Table utilities for dynamic sizing and display in Streamlit applications.

This module provides utilities for automatically sizing tables based on their content,
eliminating extra rows and columns for a cleaner display.
"""

import streamlit as st
import pandas as pd
from typing import Dict, Any, Optional, List, Union


def calculate_dynamic_table_height(df: pd.DataFrame, 
                                 min_height: int = 200, 
                                 max_height: int = 800, 
                                 row_height: int = 35,
                                 header_height: int = 40,
                                 padding: int = 20) -> int:
    """
    Calculate optimal table height based on DataFrame content.
    
    Args:
        df: DataFrame to calculate height for
        min_height: Minimum table height in pixels
        max_height: Maximum table height in pixels
        row_height: Height per row in pixels
        header_height: Height of header row in pixels
        padding: Additional padding in pixels
        
    Returns:
        Optimal height in pixels
    """
    if df.empty:
        return min_height
    
    # Calculate height based on number of rows
    calculated_height = header_height + (len(df) * row_height) + padding
    
    # Ensure height is within bounds
    return max(min_height, min(calculated_height, max_height))


def calculate_dynamic_column_widths(df: pd.DataFrame, 
                                  column_config: Optional[Dict[str, Dict[str, Any]]] = None,
                                  min_width: int = 80,
                                  max_width: int = 300,
                                  char_width: int = 8) -> Dict[str, int]:
    """
    Calculate optimal column widths based on content.
    
    Args:
        df: DataFrame to calculate widths for
        column_config: Existing column configuration
        min_width: Minimum column width in pixels
        max_width: Maximum column width in pixels
        char_width: Approximate width per character in pixels
        
    Returns:
        Dictionary mapping column names to optimal widths
    """
    widths = {}
    
    for col in df.columns:
        # Start with existing width if available
        if column_config and col in column_config:
            existing_width = column_config[col].get('width', min_width)
        else:
            existing_width = min_width
        
        # Calculate width based on content
        if not df.empty:
            # Get max length of content in this column (including header)
            max_content_length = max(
                len(str(col)),  # Header length
                df[col].astype(str).str.len().max() if not df[col].empty else 0
            )
            
            # Calculate width based on content length
            content_width = max_content_length * char_width + 20  # 20px padding
            
            # Use the larger of existing width or content-based width
            optimal_width = max(existing_width, content_width)
        else:
            optimal_width = existing_width
        
        # Ensure width is within bounds and convert to regular Python int
        widths[col] = int(max(min_width, min(optimal_width, max_width)))
    
    return widths


def create_dynamic_dataframe_display(df: pd.DataFrame,
                                   column_config: Optional[Dict[str, Any]] = None,
                                   use_container_width: bool = True,
                                   hide_index: bool = True,
                                   auto_height: bool = True,
                                   auto_width: bool = True,
                                   min_height: int = 200,
                                   max_height: int = 800,
                                   **kwargs) -> None:
    """
    Display a DataFrame with dynamic sizing based on content.
    
    Args:
        df: DataFrame to display
        column_config: Column configuration dictionary
        use_container_width: Whether to use full container width
        hide_index: Whether to hide the DataFrame index
        auto_height: Whether to automatically calculate height
        auto_width: Whether to automatically calculate column widths
        min_height: Minimum table height
        max_height: Maximum table height
        **kwargs: Additional arguments passed to st.dataframe
    """
    if df.empty:
        st.warning("No data to display.")
        return
    
    # Calculate dynamic height if enabled
    if auto_height:
        height = calculate_dynamic_table_height(
            df, 
            min_height=min_height, 
            max_height=max_height
        )
        kwargs['height'] = height
    
    # Calculate dynamic column widths if enabled
    if auto_width and column_config:
        dynamic_widths = calculate_dynamic_column_widths(df, column_config)
        
        # Update column config with dynamic widths
        for col, width in dynamic_widths.items():
            if col in column_config:
                if hasattr(column_config[col], 'width'):
                    column_config[col].width = width
                elif isinstance(column_config[col], dict):
                    column_config[col]['width'] = width
    
    # Display the DataFrame
    st.dataframe(
        df,
        use_container_width=use_container_width,
        hide_index=hide_index,
        column_config=column_config,
        **kwargs
    )


def optimize_table_for_content(df: pd.DataFrame, 
                             layout: str = "vertical",
                             selected_metrics: Optional[List[str]] = None) -> pd.DataFrame:
    """
    Optimize DataFrame by removing empty rows/columns and filtering content.
    
    Args:
        df: DataFrame to optimize
        layout: Table layout ("horizontal" or "vertical")
        selected_metrics: List of metrics to include
        
    Returns:
        Optimized DataFrame
    """
    if df.empty:
        return df
    
    # Make a copy to avoid modifying the original
    optimized_df = df.copy()
    
    # Remove completely empty rows
    optimized_df = optimized_df.dropna(how='all')
    
    # Remove completely empty columns
    optimized_df = optimized_df.dropna(axis=1, how='all')
    
    # Filter columns based on selected metrics if provided
    if selected_metrics:
        if layout == "horizontal":
            # In horizontal layout, metrics are rows (index)
            available_metrics = [metric for metric in selected_metrics 
                               if metric in optimized_df.index]
            if available_metrics:
                optimized_df = optimized_df.loc[available_metrics]
        else:
            # In vertical layout, metrics are columns
            available_metrics = [metric for metric in selected_metrics 
                               if metric in optimized_df.columns]
            if available_metrics:
                optimized_df = optimized_df[available_metrics]
    
    return optimized_df


def get_responsive_table_config(df: pd.DataFrame, 
                              layout: str = "vertical",
                              base_column_config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Generate responsive table configuration based on DataFrame content.
    
    Args:
        df: DataFrame to configure
        layout: Table layout ("horizontal" or "vertical")
        base_column_config: Base column configuration to extend
        
    Returns:
        Responsive table configuration
    """
    config = {}
    
    if df.empty:
        return config
    
    # Calculate dynamic widths
    dynamic_widths = calculate_dynamic_column_widths(df, base_column_config)
    
    # Apply base configuration and dynamic widths
    for col in df.columns:
        if base_column_config and col in base_column_config:
            # Start with base config
            config[col] = base_column_config[col]
        else:
            # Create basic config
            config[col] = st.column_config.Column(col)
        
        # Apply dynamic width - ensure it's a regular Python int
        width_value = int(dynamic_widths.get(col, 120))
        if hasattr(config[col], 'width'):
            config[col].width = width_value
        elif isinstance(config[col], dict):
            config[col]['width'] = width_value
    
    return config 