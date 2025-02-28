import csv
import os
import json
import sys
import re
import copy
import platform
import subprocess
from datetime import datetime
from collections import defaultdict

# Add the project root to the Python path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(project_root)

from goldflipper.tools.play_creation_tool import create_option_contract_symbol
from goldflipper.config.config import config

# --- Constants and Fixed Index Ranges ---
# These ranges assume that the final header row splits calls and puts via a blank separator column.
CALLS_START = 0
CALLS_END = 23   # Calls section covers indices 0 to 22; index 23 is a separator.
PUTS_START = 24  # Puts section starts at index 24.

# Fixed (expected) index mappings for each section.
CALLS_ENTRY = {
    "symbol": 2,       # "Ticket" column (3rd column in calls section)
    "expiration_date": 3,  # "Expiration (Contract)"
    "entry_stock_price": 10, # "Share Price (Buy)"
    "contracts": 12,   # "# of Con"
    "strike_price": 7,   # "Strike Price" column
    "order_type": 11  # "Order Type" column for entry
}
CALLS_VALIDATION = {
    "itm": 6,
    "atm": 7,
    "otm": 8,
}
CALLS_TP = {
    "tp_stock_price": 14,
    "tp_premium_pct": 15,
    "tp_stock_pct": 16,
    "tp_order_type": 18  # "Order Type" column for sell side (shared between TP and SL)
}
CALLS_SL = {
    "sl_stock_price": 19,
    "sl_premium_pct": 20,
    "sl_stock_pct": 21,
    "sl_order_type": 18  # Same as TP - using the shared sell side order type
}
PUTS_ENTRY = {
    "symbol": 2,       # Same relative position in puts section
    "expiration_date": 3,
    "entry_stock_price": 10,
    "contracts": 12,
    "strike_price": 7,
    "order_type": 11  # "Order Type" column for entry
}
PUTS_VALIDATION = CALLS_VALIDATION.copy()
PUTS_TP = {
    "tp_stock_price": 14,
    "tp_premium_pct": 15,
    "tp_stock_pct": 16,
    "tp_order_type": 18  # "Order Type" column for sell side (shared between TP and SL)
}
PUTS_SL = {
    "sl_stock_price": 19,
    "sl_premium_pct": 20,
    "sl_stock_pct": 21,
    "sl_order_type": 18  # Same as TP - using the shared sell side order type
}

# --- Utility Functions ---

def is_data_row(row):
    """
    Determines if a row represents play data.
    Previously, only the first cell (calls side) was checked.
    Now, if either the first cell or the cell at index PUTS_START (put side) 
    can be converted to int, we consider the row as data.
    """
    if not row:
        return False
    for idx in [0, PUTS_START]:
        if idx < len(row) and row[idx].strip():
            try:
                int(row[idx].strip())
                return True
            except ValueError:
                continue
    return False

def build_composite_headers(header_rows):
    """
    Merge header rows by concatenating nonempty cell values (from top to bottom)
    for each column. This ensures that if the bottom row is blank but an upper row contains
    an important term like "Strike Price", it will be included in the merged header.
    """
    if not header_rows:
        return []
    num_cols = max(len(row) for row in header_rows)
    composite = []
    for j in range(num_cols):
        col_parts = []
        for row in header_rows:
            if j < len(row):
                cell = row[j].strip()
                if cell:
                    col_parts.append(cell)
        composite.append(" ".join(col_parts))
    return composite

def find_strike_index(section_headers):
    """
    Find strike price columns by looking for these patterns:
    1. Column with "strike price" in header
    2. Columns labeled ITM/ATM/OTM
    Returns a list of column indices in order of priority.
    """
    strike_columns = []
    # First look for explicit strike price column
    for idx, header in enumerate(section_headers):
        if "strike price" in header.lower():
            strike_columns.append(idx)
    
    # Then look for moneyness columns
    moneyness_terms = ["itm", "atm", "otm"]
    for idx, header in enumerate(section_headers):
        if any(term in header.lower() for term in moneyness_terms):
            strike_columns.append(idx)
    
    return strike_columns

def clean_numeric_string(value):
    """
    Attempts to extract a numeric substring from a given string.
    Returns the extracted number as a string if found, else None.
    """
    match = re.search(r"[-+]?\d*\.?\d+", value)
    if match:
        return match.group(0)
    return None

def safe_convert_float(value, field_name, row_num, errors):
    """More aggressive cleaning for financial values"""
    clean_str = str(value).strip().upper()
    clean_str = clean_str.replace(",", "").replace("$", "").replace("%", "")
    
    # Handle negative values in parentheses
    if "(" in clean_str and ")" in clean_str:
        clean_str = "-" + clean_str.replace("(", "").replace(")", "")
    
    # Extract first numeric value found
    match = re.search(r"[-+]?\d*\.?\d+", clean_str)
    if match:
        try:
            return float(match.group())
        except ValueError:
            pass
    
    errors.append(f"Row {row_num}: Failed to convert {field_name} value '{value}'")
    return None

def safe_convert_int(value, field_name, row_num, errors):
    """
    Attempts to convert the given value to an int.
    Tries direct conversion; if that fails, removes extraneous commas and then falls back
    to extracting an integer substring via regex.
    """
    try:
        return int(value)
    except ValueError:
        cleaned = value.replace(",", "").strip()
        try:
            # Try converting as float then cast to int.
            return int(float(cleaned))
        except ValueError:
            match = re.search(r"[-+]?\d+", cleaned)
            if match:
                try:
                    return int(match.group(0))
                except ValueError:
                    pass
        errors.append(f"Row {row_num}: Unable to convert field '{field_name}' value '{value}' to int after cleaning.")
        return None

def fix_expiration_date(raw_date, ref_year=None):
    """Ultra-resilient date parser with smart year handling"""
    if not raw_date or str(raw_date).lower() == "n/a":
        return None

    # Clean input aggressively
    date_str = re.sub(r"[^0-9/\\-]", "", str(raw_date).strip()).replace("\\", "/").replace("-", "/")
    
    # Handle empty string after cleaning
    if not date_str:
        return None

    # Get current date for year comparison
    current_date = datetime.now()
    
    # If only month and day provided, add current year
    parts = date_str.split('/')
    if len(parts) == 2:
        month, day = int(parts[0]), int(parts[1])
        # Try current year first
        target_date = datetime(current_date.year, month, day)
        # If date has passed, use next year
        if target_date < current_date:
            target_date = datetime(current_date.year + 1, month, day)
        return target_date.strftime("%m/%d/%Y")

    # Try all possible date formats with priority to MM/DD formats
    formats = [
        "%m/%d/%Y", "%m/%d/%y", "%Y/%m/%d",
        "%m/%d", "%d/%m/%Y", "%d/%m/%y",
        "%Y-%m-%d", "%y-%m-%d", "%m-%d"
    ]
    
    for fmt in formats:
        try:
            dt = datetime.strptime(date_str, fmt)
            # Handle 2-digit year
            if dt.year < 100:
                if dt.year < 50:  # Assume 20xx for years less than 50
                    dt = dt.replace(year=2000 + dt.year)
                else:  # Assume 19xx for years 50 and above
                    dt = dt.replace(year=1900 + dt.year)
            
            # Handle 2-digit year ambiguity
            if dt.year > 2100:
                dt = dt.replace(year=dt.year - 100)
            elif dt.year < 1900:
                dt = dt.replace(year=ref_year) if ref_year else dt.replace(year=2000 + dt.year)
                    
            # If resulting date is in the past, add a year
            if dt < current_date:
                dt = dt.replace(year=dt.year + 1)
                
            return dt.strftime("%m/%d/%Y")
        except ValueError:
            continue

    # Final fallback: extract any date-like pattern
    date_components = re.findall(r'\d+', date_str)
    if len(date_components) >= 3:
        m, d, y = date_components[0], date_components[1], date_components[2]
    elif len(date_components) == 2 and ref_year:
        m, d, y = date_components[0], date_components[1], ref_year
    else:
        return None

    try:
        y = int(y)
        m = int(m)
        d = int(d)
        
        # Year adjustments
        if y < 50:
            y += 2000
        elif y < 100:
            y += 1900
            
        # Create date with validation
        dt = datetime(y, m, d)
        return dt.strftime("%m/%d/%Y")
    except:
        return None

def parse_order_type(cell_value):
    """Convert spreadsheet order types to standardized values"""
    lower_val = str(cell_value).strip().lower()
    if 'market' in lower_val:
        return 'market'
    if any(term in lower_val for term in ['bid', 'limit (bid)']):
        return 'limit at bid'
    if any(term in lower_val for term in ['ask', 'limit (ask)']):
        return 'limit at ask'
    if any(term in lower_val for term in ['mid', 'last']):
        return 'limit at last'
    return 'limit at last'  # Default fallback

# --- Core Processing Function ---

def create_play_from_data(section, data_row, section_headers, section_range_start, strike_rel_index, row_num):
    """
    Processes a single CSV row for the given section ('calls' or 'puts').
    'section_headers' is the merged header list.
    'section_range_start' indicates where that section starts in the full row.
    'strike_rel_index' is the relative index (within that section) for the strike price.
    Returns a tuple (play_dict, errors). This version makes all efforts
    to clean/convert each value to the format required by the JSON play file.
    """
    errors = []

    def get_cell(rel_index):
        abs_index = section_range_start + rel_index
        if abs_index < len(data_row):
            return data_row[abs_index].strip()
        return ""

    # Use the appropriate mapping for each section.
    mapping = CALLS_ENTRY if section == "calls" else PUTS_ENTRY

    # --- Process Critical Fields ---
    symbol_value = get_cell(mapping["symbol"])
    if not symbol_value:
        errors.append(f"Row {row_num} ({section}): Missing symbol.")

    expiration_value = get_cell(mapping["expiration_date"])
    if not expiration_value:
        errors.append(f"Row {row_num} ({section}): Missing expiration date.")
    # Attempt to fix and standardize the expiration date.
    exp_date = fix_expiration_date(expiration_value) if expiration_value else ""
    if not re.match(r"\d{2}/\d{2}/\d{4}$", exp_date):
        errors.append(f"Row {row_num} ({section}): Expiration date '{exp_date}' is not in MM/DD/YYYY format.")

    entry_stock_value = get_cell(mapping["entry_stock_price"])
    if not entry_stock_value:
        errors.append(f"Row {row_num} ({section}): Missing entry stock price.")
        entry_stock_numeric = None
    else:
        entry_stock_numeric = safe_convert_float(entry_stock_value, "entry stock price", row_num, errors)

    contracts_value = get_cell(mapping["contracts"])
    if not contracts_value:
        errors.append(f"Row {row_num} ({section}): Missing contracts count.")
        contracts_numeric = None
    else:
        contracts_numeric = safe_convert_int(contracts_value, "contracts", row_num, errors)

    # --- Process Strike Price ---
    strike_columns = find_strike_index(section_headers)
    strike_value = ""
    for col in strike_columns:
        temp_value = get_cell(col)
        if temp_value.strip():
            strike_value = temp_value
            break
    
    if not strike_value:
        # Fallback: check neighboring columns to the first strike column
        if strike_columns:
            for offset in [-1, 0, 1]:
                check_idx = strike_columns[0] + offset
                if 0 <= check_idx < len(section_headers):
                    temp_value = get_cell(check_idx)
                    if temp_value.strip():
                        strike_value = temp_value
                        break
    
    # Clean the found strike value
    if strike_value:
        cleaned_strike = strike_value.replace(",", "").replace("$", "").strip()
        try:
            strike_numeric = float(cleaned_strike)
        except ValueError:
            match = re.search(r"[-+]?\d*\.?\d+", cleaned_strike)
            strike_numeric = float(match.group()) if match else None
    else:
        errors.append(f"Row {row_num} ({section}): Missing strike price")
        strike_numeric = None

    # Determine the trade type (e.g. "call" or "put")
    trade_type = section[:-1] if section.endswith("s") else section

    # Modified date handling with error suppression
    raw_exp_date = get_cell(mapping["expiration_date"])
    exp_date = fix_expiration_date(raw_exp_date) or raw_exp_date
    
    # Get reference year from expiration date
    ref_year = None
    try:
        ref_year = datetime.strptime(exp_date, "%m/%d/%Y").year
    except:
        pass

    # Process GTD date with expiration year fallback
    raw_gtd_date = get_cell(4)
    gtd_date = fix_expiration_date(raw_gtd_date, ref_year=ref_year) or exp_date

    # Generate option contract symbol using the proper method
    option_symbol = create_option_contract_symbol(
        symbol=symbol_value,
        expiration_date=exp_date,
        strike_price=f"{strike_numeric:.3f}",  # Ensure 3 decimal places
        trade_type=trade_type  # 'calls' or 'puts'
    )

    # Error handling if needed
    if "INVALID" in option_symbol:
        errors.append(f"Row {row_num}: Invalid option symbol generated")

    # Unified TP/SL processing with multiple price type support
    def process_condition(condition_type):
        """Process TP/SL conditions with order type handling"""
        prefix = "tp" if condition_type == "tp" else "sl"
        base_idx = CALLS_TP if section == "calls" else PUTS_TP
        if condition_type == "sl":
            base_idx = CALLS_SL if section == "calls" else PUTS_SL

        condition = {}
        # Stock price
        stock_price = get_cell(base_idx[f"{prefix}_stock_price"])
        if stock_price and stock_price != 'N/A':
            converted = safe_convert_float(stock_price, f"{condition_type} stock price", row_num, errors)
            if converted: condition["share_price"] = converted
        
        # Premium percentage
        premium_pct = get_cell(base_idx[f"{prefix}_premium_pct"]).replace('%', '')
        if premium_pct and premium_pct != 'N/A':
            converted = safe_convert_float(premium_pct, f"{condition_type} premium %", row_num, errors)
            if converted: condition["premium_pct"] = converted
        
        # Stock percentage
        stock_pct = get_cell(base_idx[f"{prefix}_stock_pct"]).replace('%', '')
        if stock_pct and stock_pct != 'N/A':
            converted = safe_convert_float(stock_pct, f"{condition_type} stock %", row_num, errors)
            if converted: condition["stock_pct"] = converted

        # Get order type from correct column
        order_type_col = base_idx[f"{prefix}_order_type"]
        raw_order_type = get_cell(order_type_col)
        parsed_order_type = parse_order_type(raw_order_type)

        # Set SL_type based on order type
        if condition_type == "sl":
            condition["SL_type"] = "STOP" if parsed_order_type == "market" else "LIMIT"
        
        condition["order_type"] = parsed_order_type

        # Only create condition if at least one price type exists
        if condition:
            return condition
        return None

    # Process both TP and SL
    take_profit = process_condition("tp")
    stop_loss = process_condition("sl")

    # Process entry order type
    entry_order_type_col = mapping["order_type"]
    raw_entry_order_type = get_cell(entry_order_type_col)
    parsed_entry_order_type = parse_order_type(raw_entry_order_type)

    # Remove logging section and match exact field order
    play = {
        "symbol": symbol_value or "",
        "trade_type": trade_type.upper(),
        "entry_point": {
            "stock_price": entry_stock_numeric,
            "order_type": parsed_entry_order_type
        },
        "strike_price": f"{strike_numeric:.1f}",
        "expiration_date": exp_date,
        "contracts": contracts_numeric,
        "option_contract_symbol": option_symbol,
        "play_name": generate_play_name(symbol_value, trade_type),
        "play_class": "SIMPLE",
        "conditional_plays": {},
        "strategy": "Option Swings",
        "creation_date": datetime.now().strftime("%Y-%m-%d"),
        "creator": "auto-ingestor",
        "status": {
            "play_status": "NEW",
            "order_id": None,
            "order_status": None,
            "position_exists": False,
            "last_checked": None,
            "closing_order_id": None,
            "closing_order_status": None,
            "contingency_order_id": None,
            "contingency_order_status": None,
            "conditionals_handled": False
        },
        "play_expiration_date": gtd_date,
        "stop_loss": stop_loss if stop_loss else None,
        "take_profit": take_profit if take_profit else None
    }

    return play, errors

def save_play(play, section):
    """
    Save the play as a JSON file in the appropriate plays directory.
    SIMPLE plays are saved to plays/new; OTO plays to plays/temp.
    """
    base_dir = os.path.join(project_root, "goldflipper", "plays")
    target_dir = os.path.join(base_dir, "temp" if play.get("play_class", "SIMPLE") == "OTO" else "new")
    os.makedirs(target_dir, exist_ok=True)
    filename = re.sub(r"[^\w\-]", "_", play["play_name"]) + ".json"
    filepath = os.path.join(target_dir, filename)
    
    try:
        with open(filepath, "w") as f:
            json.dump(play, f, indent=4)
        print(f"[SUCCESS] ({section}) Play saved to: {filepath}")
        
    except Exception as e:
        print(f"[ERROR] Failed to save play: {e}")

def main():
    # At the very start:
    print(f"Script version: 2024-02-21-debug-01")
    
    # After config import:
    from goldflipper.config.config import config
    print(f"Config instance ID: {id(config)}")
    config.reload()  # Force fresh load
    
    # At the file open check:
    ingestor_config = config.get('csv_ingestor') or {}
    print(f"Raw ingestor config: {ingestor_config}")
    should_open = ingestor_config.get('open_after_creation', True)
    print(f"Final open_after_creation value: {should_open} (type: {type(should_open)})")

    import argparse
    parser = argparse.ArgumentParser(description="Ingest plays from a standardized CSV template.")
    parser.add_argument("csv_file", help="Path to the CSV file containing play data.")
    args = parser.parse_args()

    csv_file_path = args.csv_file
    if not os.path.exists(csv_file_path):
        print(f"CSV file not found: {csv_file_path}")
        return

    with open(csv_file_path, newline="", encoding="utf-8") as csvfile:
        reader = list(csv.reader(csvfile))
    if not reader:
        print("CSV file is empty.")
        return

    # --- NEW LOGIC FOR HEADER EXTRACTION ---
    # Only use rows before the first data row as header rows.
    header_rows = []
    data_rows = []
    found_data = False
    for row in reader:
        if not found_data and is_data_row(row):
            found_data = True
        if found_data:
            data_rows.append(row)
        else:
            header_rows.append(row)

    composite_headers = build_composite_headers(header_rows)
    calls_headers = composite_headers[CALLS_START:CALLS_END]
    puts_headers = composite_headers[PUTS_START:]
    
    strike_calls = find_strike_index(calls_headers)
    if strike_calls is None:
        strike_calls = 7
        print("Warning: Falling back to default strike column index 7 for calls.")
    strike_puts = find_strike_index(puts_headers)
    if strike_puts is None:
        strike_puts = 7
        print("Warning: Falling back to default strike column index 7 for puts.")

    valid_plays = []
    all_errors = []
    created_files = []
    for i, row in enumerate(data_rows, start=1):
        # Process calls only if calls symbol exists
        if row[CALLS_START + CALLS_ENTRY["symbol"]].strip():
            play_calls, errors_calls = create_play_from_data("calls", row, calls_headers, CALLS_START, strike_calls, i)
            if play_calls:
                valid_plays.append(("calls", play_calls))
            all_errors.extend(errors_calls)
            if play_calls:
                output_filename = f"Play_{datetime.now().strftime('%Y%m%d-%H%M')}_{play_calls['symbol']}_calls.json"
                output_path = os.path.join(os.path.join(project_root, "goldflipper", "plays", "new"), output_filename)
                with open(output_path, 'w') as f:
                    json.dump(play_calls, f, indent=2)
                created_files.append(output_path)
        
        # Process puts only if puts symbol exists
        if row[PUTS_START + PUTS_ENTRY["symbol"]].strip():
            play_puts, errors_puts = create_play_from_data("puts", row, puts_headers, PUTS_START, strike_puts, i)
            if play_puts:
                valid_plays.append(("puts", play_puts))
            all_errors.extend(errors_puts)
            if play_puts:
                output_filename = f"Play_{datetime.now().strftime('%Y%m%d-%H%M')}_{play_puts['symbol']}_puts.json"
                output_path = os.path.join(os.path.join(project_root, "goldflipper", "plays", "new"), output_filename)
                with open(output_path, 'w') as f:
                    json.dump(play_puts, f, indent=2)
                created_files.append(output_path)

    if all_errors:
        print("\nError Summary (last up to 10 messages):")
        for err in all_errors[-10:]:
            print(err)
    
    if all_errors:
        user_input = input("\nErrors/warnings were found during ingestion. Proceed with valid plays? (Y/N): ").strip().upper()
        if user_input != "Y":
            print("Aborting ingestion due to errors.")
            return
    
    for section, play in valid_plays:
        save_play(play, section)
    
    print(f"\nIngestion complete. Valid plays: {len(valid_plays)}.")

    # Single file-opening location
    if config.get('csv_ingestor', 'open_after_creation', default=True):
        for json_path in created_files:
            if os.path.exists(json_path):
                if sys.platform == "win32":
                    os.startfile(json_path)
                elif sys.platform == "darwin":
                    subprocess.run(["open", json_path])
                else:
                    subprocess.run(["xdg-open", json_path])

# Initialize play counter at module level
play_counter = defaultdict(int)

def generate_play_name(symbol, trade_type):
    """Generate unique play name with counter and timestamp"""
    key = f"{symbol}-{trade_type}"
    play_counter[key] += 1
    timestamp = datetime.now().strftime("%Y%m%d-%H%M")
    return f"{symbol}-{trade_type}-{play_counter[key]}-{timestamp}"

if __name__ == "__main__":
    main()
    