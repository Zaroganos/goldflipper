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
# These ranges (relative to the entire row) assume that the final header row
# (from the CSV template) splits calls and puts via a blank separator column.
CALLS_START = 0
CALLS_END = 23   # calls section covers indices 0 to 22; index 23 is a separator
PUTS_START = 24  # puts section starts at index 24

# Fixed (expected) index mappings for each section (relative to the section, not the whole row).
# For example, in the Calls section (i.e. the final header row indices 0-22),
# we expect:
#   • Entry group: symbol in relative index 2, expiration in index 3, etc.
#   • Validation group: ITM (6), ATM (7), OTM (8)
#   • TP group: TP stock price at 14, TP Prem % at 15, TP Stock % at 16
#   • SL group: SL stock price at 19, SL Prem % at 20, SL Stock % at 21
CALLS_ENTRY = {
    "symbol": 2,
    "expiration_date": 3,
    # The strike price is not in the final header row; we will search for it in the merged headers.
    "entry_stock_price": 10,
    "entry_order_type": 11,
    "contracts": 12,
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
# For the puts section we expect the same relative ordering (when the section is isolated).
PUTS_ENTRY = CALLS_ENTRY.copy()
PUTS_VALIDATION = CALLS_VALIDATION.copy()
PUTS_TP = CALLS_TP.copy()
PUTS_SL = CALLS_SL.copy()

# --- Utility Functions ---

def is_data_row(row):
    """
    Returns True if the row represents play data.
    In our case, a data row is defined as one whose first cell can be converted to an integer.
    """
    if not row:
        return False
    try:
        int(row[0])
        return True
    except ValueError:
        return False

def build_composite_headers(header_rows):
    """
    Given a list of header rows (each a list of cells), build a composite header list.
    For each column index, use the first (from bottom) non-empty cell.
    This allows us to merge multi-line header information (for instance, to catch "Strike Price"
    from an earlier header row if the final header row has a blank at that index).
    """
    if not header_rows:
        return []
    num_cols = max(len(row) for row in header_rows)
    composite = []
    for j in range(num_cols):
        value = ""
        # iterate from the last header row upward
        for row in reversed(header_rows):
            if j < len(row) and row[j].strip():
                value = row[j].strip()
                break
        composite.append(value)
    return composite

def find_strike_index(section_headers):
    """
    Given a list of composite headers for one section (calls or puts),
    return the relative index (within that section) where the header contains
    the keyword 'strike'. Returns None if not found.
    """
    for idx, header in enumerate(section_headers):
        if "strike" in header.lower():
            return idx
    return None

def safe_convert_float(value, field_name, row_num, errors, default=None):
    try:
        return float(value)
    except ValueError:
        errors.append(f"Row {row_num}: Unable to convert field '{field_name}' value '{value}' to float.")
        return default

def safe_convert_int(value, field_name, row_num, errors, default=None):
    try:
        return int(value)
    except ValueError:
        errors.append(f"Row {row_num}: Unable to convert field '{field_name}' value '{value}' to int.")
        return default

# --- Core Processing Function ---

def create_play_from_data(section, data_row, section_headers, section_range_start, strike_rel_index, row_num):
    """
    Process a single CSV row for the given section ('calls' or 'puts').
    'section_headers' is the composite header list (for the section) derived from the header rows.
    'section_range_start' is the starting index in the full row that this section occupies.
    'strike_rel_index' is the relative index (within the section) where the strike price should come from.
    
    Returns a tuple (play_dict, errors). The play_dict is None if essential data is missing.
    """
    errors = []

    # Helper: get cell from data_row using a relative index (adjusting for section start)
    def get_cell(rel_index):
        col_index = section_range_start + rel_index
        if col_index < len(data_row):
            return data_row[col_index].strip()
        return ""
    
    # Only process this section if the symbol cell is non-empty.
    entry_map = CALLS_ENTRY if section == "calls" else PUTS_ENTRY
    symbol_val = get_cell(entry_map["symbol"])
    if not symbol_val:
        # Section empty; no play in this part of the row.
        return None, errors

    # Load the play configuration template (from play-template.json)
    template_path = os.path.join(os.path.dirname(__file__), "play-template.json")
    try:
        with open(template_path, "r") as f:
            play_template = json.load(f)
    except Exception as e:
        errors.append(f"Row {row_num} ({section}): Could not load play template: {e}")
        return None, errors

    play = copy.deepcopy(play_template)

    # Set trade type based on section.
    trade_type = "CALL" if section == "calls" else "PUT"
    play["trade_type"] = trade_type

    # --- Entry Group ---
    symbol = get_cell(entry_map["symbol"])
    if not symbol:
        errors.append(f"Row {row_num} ({section}): Missing symbol in entry.")
    play["symbol"] = symbol.upper() if symbol else ""
    
    expiration = get_cell(entry_map["expiration_date"])
    if not expiration:
        errors.append(f"Row {row_num} ({section}): Missing expiration date in entry.")
    play["expiration_date"] = expiration

    # Strike price: use the found strike column (if available) in this section.
    if strike_rel_index is None:
        errors.append(f"Row {row_num} ({section}): Strike price column not found in headers.")
    else:
        strike_val = get_cell(strike_rel_index)
        if not strike_val:
            errors.append(f"Row {row_num} ({section}): Missing strike price.")
        play["strike_price"] = strike_val

    entry_stock_str = get_cell(entry_map["entry_stock_price"])
    if not entry_stock_str:
        errors.append(f"Row {row_num} ({section}): Missing entry stock price.")
    play["entry_point"]["stock_price"] = safe_convert_float(entry_stock_str, "entry stock price", row_num, errors)

    order_type = get_cell(entry_map["entry_order_type"])
    if not order_type:
        errors.append(f"Row {row_num} ({section}): Missing entry order type.")
    play["entry_point"]["order_type"] = order_type

    contracts_str = get_cell(entry_map["contracts"])
    if not contracts_str:
        errors.append(f"Row {row_num} ({section}): Missing contracts value.")
    play["contracts"] = safe_convert_int(contracts_str, "contracts", row_num, errors)

    # --- Validation Group: ITM/ATM/OTM ---
    val_map = CALLS_VALIDATION if section == "calls" else PUTS_VALIDATION
    itm = get_cell(val_map["itm"])
    atm = get_cell(val_map["atm"])
    otm = get_cell(val_map["otm"])
    flag_count = sum(1 for x in [itm, atm, otm] if x)
    if flag_count != 1:
        errors.append(f"Row {row_num} ({section}): Expected exactly one of ITM/ATM/OTM to be filled, found {flag_count}.")

    # --- Take Profit (TP) Group ---
    tp_map = CALLS_TP if section == "calls" else PUTS_TP
    tp_stock = get_cell(tp_map["tp_stock_price"])
    tp_prem = get_cell(tp_map["tp_premium_pct"])
    tp_stock_pct = get_cell(tp_map["tp_stock_pct"])
    tp_count = sum(1 for v in [tp_stock, tp_prem, tp_stock_pct] if v)
    if tp_count != 1:
        errors.append(f"Row {row_num} ({section}): For Take Profit, expected exactly one price type to be provided, found {tp_count}.")
    else:
        if tp_stock:
            # We assume that if a stock price is provided it goes to the stock price target.
            play["take_profit"]["TP_option_prem"] = 0.0  # not applicable
            play["take_profit"]["TP_stock_price_target"] = safe_convert_float(tp_stock, "TP stock price", row_num, errors)
        elif tp_prem:
            play["take_profit"]["premium_pct"] = safe_convert_float(tp_prem, "TP premium pct", row_num, errors)
        elif tp_stock_pct:
            play["take_profit"]["stock_price_pct"] = safe_convert_float(tp_stock_pct, "TP stock price pct", row_num, errors)

    # --- Stop Loss (SL) Group ---
    sl_map = CALLS_SL if section == "calls" else PUTS_SL
    sl_stock = get_cell(sl_map["sl_stock_price"])
    sl_prem = get_cell(sl_map["sl_premium_pct"])
    sl_stock_pct = get_cell(sl_map["sl_stock_pct"])
    sl_count = sum(1 for v in [sl_stock, sl_prem, sl_stock_pct] if v)
    if sl_count != 1:
        errors.append(f"Row {row_num} ({section}): For Stop Loss, expected exactly one price type to be provided, found {sl_count}.")
    else:
        if sl_stock:
            play["stop_loss"]["SL_option_prem"] = 0.0
            play["stop_loss"]["SL_stock_price_target"] = safe_convert_float(sl_stock, "SL stock price", row_num, errors)
        elif sl_prem:
            play["stop_loss"]["premium_pct"] = safe_convert_float(sl_prem, "SL premium pct", row_num, errors)
        elif sl_stock_pct:
            play["stop_loss"]["stock_price_pct"] = safe_convert_float(sl_stock_pct, "SL stock price pct", row_num, errors)

    # --- Generate Option Contract Symbol ---
    try:
        play["option_contract_symbol"] = create_option_contract_symbol(
            play["symbol"],
            play["expiration_date"],
            play["strike_price"],
            play["trade_type"]
        )
    except Exception as e:
        errors.append(f"Row {row_num} ({section}): Error generating option contract symbol: {e}")

    # --- Other Metadata ---
    # Generate a play name if not provided: using symbol, trade type, and current timestamp.
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    play_name = f"{play['symbol']}_{play['trade_type']}_{timestamp}"
    play["play_name"] = play_name

    # Set play expiration date to the option expiration date by default.
    play["play_expiration_date"] = play["expiration_date"] if play["expiration_date"] else ""
    play["creator"] = "auto"
    play["creation_date"] = datetime.now().strftime("%Y-%m-%d")
    play["play_class"] = "SIMPLE"
    play["strategy"] = "Option Swings"
    
    return play, errors

def save_play(play, section):
    """
    Save the play as a JSON file in the appropriate plays directory.
    Plays with "SIMPLE" class will be saved to plays/new.
    """
    base_dir = os.path.join(project_root, "goldflipper", "plays")
    if play.get("play_class", "SIMPLE") == "OTO":
        target_dir = os.path.join(base_dir, "temp")
    else:
        target_dir = os.path.join(base_dir, "new")
    os.makedirs(target_dir, exist_ok=True)
    
    # Sanitize play name to create a valid filename.
    filename = re.sub(r"[^\w\-]", "_", play["play_name"]) + ".json"
    filepath = os.path.join(target_dir, filename)
    try:
        with open(filepath, "w") as f:
            json.dump(play, f, indent=4)
        print(f"[SUCCESS] ({section}) Play saved to: {filepath}")
        # Attempt to open the file in a text editor.
        try:
            if platform.system() == "Windows":
                subprocess.run(["notepad.exe", filepath])
            elif platform.system() == "Darwin":  # macOS
                subprocess.run(["open", "-t", filepath])
            else:
                subprocess.run(["xdg-open", filepath])
        except Exception as e:
            print(f"[WARNING] Could not open file automatically: {e}")
    except Exception as e:
        print(f"[ERROR] Failed to save play: {e}")

# --- Main Ingestion Routine ---

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

    # Separate header rows from data rows.
    header_rows = []
    data_rows = []
    for row in reader:
        if row and is_data_row(row):
            data_rows.append(row)
        else:
            header_rows.append(row)
    
    if not data_rows:
        print("No data rows found in CSV.")
        return

    # Build composite headers from all header rows.
    composite_headers = build_composite_headers(header_rows)
    # Split composite headers into calls and puts based on known ranges.
    calls_headers = composite_headers[CALLS_START:CALLS_END]
    puts_headers = composite_headers[PUTS_START:] if len(composite_headers) > PUTS_START else []
    
    # Find the relative index for the strike price column.
    strike_index_calls = find_strike_index(calls_headers)
    strike_index_puts = find_strike_index(puts_headers)
    
    all_errors = []
    valid_plays = []
    row_number = 0
    for row in data_rows:
        row_number += 1
        # Process calls section.
        play_calls, errors_calls = create_play_from_data("calls", row, calls_headers, CALLS_START, strike_index_calls, row_number)
        if play_calls:
            if errors_calls:
                all_errors.extend(errors_calls)
            else:
                valid_plays.append(("calls", play_calls))
        # Process puts section.
        play_puts, errors_puts = create_play_from_data("puts", row, puts_headers, PUTS_START, strike_index_puts, row_number)
        if play_puts:
            if errors_puts:
                all_errors.extend(errors_puts)
            else:
                valid_plays.append(("puts", play_puts))
    
    # Write all errors into a log file (one error per line) in the logs folder.
    logs_dir = os.path.join(project_root, "logs")
    os.makedirs(logs_dir, exist_ok=True)
    log_filename = f"play_ingestion_errors_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    log_filepath = os.path.join(logs_dir, log_filename)
    with open(log_filepath, "w", encoding="utf-8") as log_file:
        for err in all_errors:
            log_file.write(err + "\n")
    
    # Display a summary (tail) of errors inline (capped at 10 lines).
    if all_errors:
        print("\nError Summary (last up to 10 errors):")
        for err in all_errors[-10:]:
            print(err)
    
    # Prompt user whether to override errors and proceed with valid plays.
    if all_errors:
        user_input = input("\nErrors were found during ingestion. Do you want to proceed with valid plays? (Y/N): ").strip().upper()
        if user_input != "Y":
            print("Aborting ingestion due to errors.")
            return
    
    # Save all valid plays.
    for section, play in valid_plays:
        save_play(play, section)
    
    print(f"\nIngestion complete. Valid plays: {len(valid_plays)}. Full error log saved to: {log_filepath}")

if __name__ == "__main__":
    main()
