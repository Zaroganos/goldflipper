"""
Web utilities package for the Goldflipper Streamlit application.

This package contains utility functions and classes for common web interface tasks.
"""

from .table_utils import (
    calculate_dynamic_table_height,
    calculate_dynamic_column_widths,
    create_dynamic_dataframe_display,
    optimize_table_for_content,
    get_responsive_table_config
)

__all__ = [
    'calculate_dynamic_table_height',
    'calculate_dynamic_column_widths', 
    'create_dynamic_dataframe_display',
    'optimize_table_for_content',
    'get_responsive_table_config'
] 