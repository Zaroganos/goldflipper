# Web Utils - Dynamic Table Sizing

This directory contains utility functions for creating responsive, dynamically-sized tables in Streamlit applications.

## Table Utils (`table_utils.py`)

### Overview

The table utilities provide automatic sizing for Streamlit DataFrames based on their content, eliminating extra rows and columns for a cleaner display.

### Key Functions

#### `create_dynamic_dataframe_display()`

The main function for displaying DataFrames with automatic sizing.

```python
from goldflipper.web.utils.table_utils import create_dynamic_dataframe_display

# Basic usage
create_dynamic_dataframe_display(
    df,
    column_config=column_config,
    auto_height=True,
    auto_width=True
)
```

#### `optimize_table_for_content()`

Optimizes DataFrames by removing empty rows/columns and filtering content.

```python
from goldflipper.web.utils.table_utils import optimize_table_for_content

# Remove empty data and filter by selected metrics
optimized_df = optimize_table_for_content(
    df, 
    layout="vertical", 
    selected_metrics=["symbol", "price", "volume"]
)
```

#### `calculate_dynamic_table_height()`

Calculates optimal table height based on content.

```python
from goldflipper.web.utils.table_utils import calculate_dynamic_table_height

height = calculate_dynamic_table_height(
    df,
    min_height=200,
    max_height=600,
    row_height=35
)
```

### Usage Example

Here's a complete example of how to use the dynamic table utilities:

```python
import streamlit as st
import pandas as pd
from goldflipper.web.utils.table_utils import (
    create_dynamic_dataframe_display,
    optimize_table_for_content,
    get_responsive_table_config
)

# Your data
df = pd.DataFrame({
    'Symbol': ['AAPL', 'MSFT', 'GOOG'],
    'Price': [150.25, 280.50, 2500.75],
    'Volume': [1000000, 750000, 500000]
})

# Optimize the data
optimized_df = optimize_table_for_content(df)

# Create column configuration
column_config = {
    'Symbol': st.column_config.Column('Stock Symbol', width=100),
    'Price': st.column_config.NumberColumn('Price ($)', format='$%.2f', width=120),
    'Volume': st.column_config.NumberColumn('Volume', format='%d', width=120)
}

# Get responsive configuration
responsive_config = get_responsive_table_config(
    optimized_df, 
    base_column_config=column_config
)

# Display with dynamic sizing
create_dynamic_dataframe_display(
    optimized_df,
    column_config=responsive_config,
    auto_height=True,
    auto_width=True,
    min_height=200,
    max_height=600
)
```

### Configuration Options

#### Auto-sizing Controls

You can add user controls for auto-sizing in your sidebar:

```python
# In your sidebar
auto_sizing = st.checkbox("Enable Auto-Sizing", value=True)

if auto_sizing:
    col1, col2 = st.columns(2)
    with col1:
        min_height = st.number_input("Min Height (px)", value=200)
    with col2:
        max_height = st.number_input("Max Height (px)", value=600)
else:
    min_height = max_height = st.number_input("Fixed Height (px)", value=400)

# Use in display
create_dynamic_dataframe_display(
    df,
    auto_height=auto_sizing,
    auto_width=auto_sizing,
    min_height=min_height,
    max_height=max_height
)
```

### Benefits

1. **Automatic Sizing**: Tables automatically adjust to their content
2. **No Empty Space**: Eliminates extra rows and columns
3. **Responsive Design**: Adapts to different screen sizes
4. **User Control**: Optional user controls for sizing preferences
5. **Consistent UX**: Standardized table display across the application

### Integration

To use these utilities in a new page:

1. Import the required functions
2. Optimize your DataFrame with `optimize_table_for_content()`
3. Create responsive column configuration with `get_responsive_table_config()`
4. Display with `create_dynamic_dataframe_display()`

The utilities are designed to be a drop-in replacement for `st.dataframe()` with enhanced functionality. 