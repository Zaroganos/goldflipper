import csv
import os
import json
import sys
import re
import copy
import platform
import subprocess
from datetime import datetime

# Add the project root to the Python path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(project_root)

# Import the helper that generates the option contract symbol
from goldflipper.tools.play_creation_tool import create_option_contract_symbol

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
    "strike_price": 7   # "Strike Price" column
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
}
CALLS_SL = {
    "sl_stock_price": 19,
    "sl_premium_pct": 20,
    "sl_stock_pct": 21,
}
PUTS_ENTRY = {
    "symbol": 2,       # Same relative position in puts section
    "expiration_date": 3,
    "entry_stock_price": 10,
    "contracts": 12,
    "strike_price": 7
}
PUTS_VALIDATION = CALLS_VALIDATION.copy()
PUTS_TP = CALLS_TP.copy()
PUTS_SL = CALLS_SL.copy()

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

def fix_expiration_date(exp_date):
    """Handle more date formats including 1-digit months/days"""
    formats = [
        "%m/%d/%Y", "%m/%d/%y", 
        "%m-%d-%Y", "%m-%d-%y",
        "%Y/%m/%d", "%Y-%m-%d"
    ]
    
    for fmt in formats:
        try:
            dt = datetime.strptime(exp_date.strip(), fmt)
            return dt.strftime("%m/%d/%Y")
        except ValueError:
            continue
    
    return exp_date  # Return original if all attempts fail

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

    # Initialize play with template structure
    play = {
        "symbol": symbol_value or "",
        "trade_type": trade_type.upper(),  # PUT/CALL
        "entry_point": {
            "stock_price": entry_stock_numeric,
            "order_type": get_cell(mapping.get("order_type", 11)) or "limit at bid"
        },
        "strike_price": strike_numeric,
        "expiration_date": exp_date.strftime("%Y-%m-%d"),
        "contracts": contracts_numeric,
        "status": {
            "play_status": "NEW",
            "order_id": None,
            "order_status": None,
            "position_exists": False,
            "closing_order_id": None,
            "closing_order_status": None,
            "contingency_order_id": None,
            "contingency_order_status": None,
            "conditionals_handled": False
        },
        "play_class": "SIMPLE",
        "conditional_plays": {},
        "strategy": "Option Swings",
        "play_expiration_date": get_cell(4).strftime("%Y-%m-%d"),
        "take_profit": {
            "stock_price": get_cell(CALLS_TP["tp_stock_price"]) if section == "calls" else get_cell(PUTS_TP["tp_stock_price"]),
            "stock_price_pct": get_cell(CALLS_TP["tp_stock_pct"]) if section == "calls" else get_cell(PUTS_TP["tp_stock_pct"]),
            "premium_pct": get_cell(CALLS_TP["tp_premium_pct"]) if section == "calls" else get_cell(PUTS_TP["tp_premium_pct"]),
            "order_type": "limit at bid"
        }
    }

    # --- Process Take Profit ---
    tp_stock = get_cell(CALLS_TP["tp_stock_price"]) if section == "calls" else get_cell(PUTS_TP["tp_stock_price"])
    tp_prem = get_cell(CALLS_TP["tp_premium_pct"]) if section == "calls" else get_cell(PUTS_TP["tp_premium_pct"])
    tp_stock_pct = get_cell(CALLS_TP["tp_stock_pct"]) if section == "calls" else get_cell(PUTS_TP["tp_stock_pct"])
    
    tp_data = {
        "TP_type": "Single",
        "stock_price": None,
        "stock_price_pct": None,
        "premium_pct": None,
        "order_type": "limit at bid",
        "TP_option_prem": None,
        "TP_stock_price_target": None
    }
    
    # Map CSV values to correct fields
    if tp_stock:
        tp_data["TP_stock_price_target"] = safe_convert_float(tp_stock, "TP stock price", row_num, errors)
    if tp_prem:
        tp_data["premium_pct"] = safe_convert_float(tp_prem, "TP premium pct", row_num, errors)
    if tp_stock_pct:
        tp_data["stock_price_pct"] = safe_convert_float(tp_stock_pct, "TP stock pct", row_num, errors)
    
    play["take_profit"] = tp_data

    # --- Process Stop Loss ---
    sl_stock = get_cell(CALLS_SL["sl_stock_price"]) if section == "calls" else get_cell(PUTS_SL["sl_stock_price"])
    sl_prem = get_cell(CALLS_SL["sl_premium_pct"]) if section == "calls" else get_cell(PUTS_SL["sl_premium_pct"])
    sl_stock_pct = get_cell(CALLS_SL["sl_stock_pct"]) if section == "calls" else get_cell(PUTS_SL["sl_stock_pct"])
    
    sl_data = {
        "SL_type": "LIMIT",
        "stock_price": None,
        "stock_price_pct": None,
        "premium_pct": None,
        "order_type": "limit at bid"
    }
    
    if sl_stock:
        sl_data["stock_price"] = safe_convert_float(sl_stock, "SL stock price", row_num, errors)
    if sl_prem:
        sl_data["premium_pct"] = safe_convert_float(sl_prem, "SL premium pct", row_num, errors)
    if sl_stock_pct:
        sl_data["stock_price_pct"] = safe_convert_float(sl_stock_pct, "SL stock pct", row_num, errors)
    
    play["stop_loss"] = sl_data

    # --- Option Symbol Generation ---
    try:
        if strike_numeric:
            play["option_contract_symbol"] = create_option_contract_symbol(
                play["symbol"],
                play["expiration_date"],
                strike_numeric,
                play["trade_type"].lower()
            )
    except Exception as e:
        errors.append(f"Row {row_num} ({section}): Error generating option symbol: {e}")
        play["option_contract_symbol"] = f"ERR_{play['symbol']}_{exp_date.replace('/', '')}"

    # --- Metadata ---
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    play_name = f"{play['symbol']}-{play['trade_type']}-{timestamp}"
    play["play_name"] = play_name
    play["creation_date"] = datetime.now().strftime("%Y-%m-%d")
    play["creator"] = "auto"

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
        try:
            if platform.system() == "Windows":
                subprocess.run(["notepad.exe", filepath])
            elif platform.system() == "Darwin":
                subprocess.run(["open", "-t", filepath])
            else:
                subprocess.run(["xdg-open", filepath])
        except Exception as e:
            print(f"[WARNING] Could not open file automatically: {e}")
    except Exception as e:
        print(f"[ERROR] Failed to save play: {e}")

def main():
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
    for i, row in enumerate(data_rows, start=1):
        # Process calls only if calls symbol exists
        if row[CALLS_START + CALLS_ENTRY["symbol"]].strip():
            play_calls, errors_calls = create_play_from_data("calls", row, calls_headers, CALLS_START, strike_calls, i)
            if play_calls:
                valid_plays.append(("calls", play_calls))
            all_errors.extend(errors_calls)
        
        # Process puts only if puts symbol exists
        if row[PUTS_START + PUTS_ENTRY["symbol"]].strip():
            play_puts, errors_puts = create_play_from_data("puts", row, puts_headers, PUTS_START, strike_puts, i)
            if play_puts:
                valid_plays.append(("puts", play_puts))
            all_errors.extend(errors_puts)

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

if __name__ == "__main__":
    main()
