"""
Short Puts CSV Ingestion Tool

This tool processes CSV files containing Short Puts strategy play data.
The CSV should follow the format defined in "Play Template - ShortPuts - 2025.csv".

The tool automatically finds matching put options based on DTE, delta, and IV Rank criteria,
then creates play JSON files with position_side: "SHORT".
"""

import csv
import os
import json
import sys
import re
import platform
import subprocess
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple

# Add the project root to the Python path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(project_root)

from goldflipper.strategy.short_puts import find_short_put_option
from goldflipper.config.config import config
from goldflipper.utils.display import TerminalDisplay as display
from goldflipper.data.market.manager import MarketDataManager
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Column Mapping ---
# Expected columns in Short Puts CSV template
COLUMN_MAPPING = {
    "symbol": 0,
    "contracts": 1,
    "entry_order_type": 2,
    "tp_premium_pct": 3,
    "sl_multiplier": 4,
    "sl_premium_pct": 5,
    "target_dte": 6,
    "target_delta": 7,
    "iv_rank_threshold": 8,
    "gtd": 9,
    "notes": 10
}

def clean_ticker_symbol(symbol: str) -> str:
    """Clean a ticker symbol by removing leading '$' and converting to uppercase."""
    return symbol.strip().lstrip('$').upper()

def parse_order_type(cell_value: str) -> str:
    """Convert spreadsheet order types to standardized values."""
    if not cell_value:
        return 'limit at ask'  # Default for SHORT entry
    
    lower_val = str(cell_value).strip().lower()
    if 'market' in lower_val:
        return 'market'
    if any(term in lower_val for term in ['bid', 'limit (bid)', 'limit at bid']):
        return 'limit at bid'
    if any(term in lower_val for term in ['ask', 'limit (ask)', 'limit at ask']):
        return 'limit at ask'
    if any(term in lower_val for term in ['mid', 'limit (mid)', 'limit at mid']):
        return 'limit at mid'
    if any(term in lower_val for term in ['last', 'limit (last)', 'limit at last']):
        return 'limit at last'
    return 'limit at ask'  # Default for SHORT entry

def safe_convert_float(value: str, field_name: str, row_num: int, errors: List[str]) -> Optional[float]:
    """Convert value to float with error handling."""
    if not value or str(value).strip().upper() in ['N/A', '', 'NULL']:
        return None
    
    clean_str = str(value).strip().upper()
    clean_str = clean_str.replace(",", "").replace("$", "").replace("%", "")
    
    try:
        return float(clean_str)
    except ValueError:
        # Try extracting numeric value
        match = re.search(r"[-+]?\d*\.?\d+", clean_str)
        if match:
            try:
                return float(match.group())
            except ValueError:
                pass
        
        errors.append(f"Row {row_num}: Failed to convert {field_name} value '{value}'")
        return None

def safe_convert_int(value: str, field_name: str, row_num: int, errors: List[str]) -> Optional[int]:
    """Convert value to int with error handling."""
    if not value or str(value).strip().upper() in ['N/A', '', 'NULL']:
        return None
    
    try:
        return int(float(str(value).replace(",", "").strip()))
    except ValueError:
        errors.append(f"Row {row_num}: Failed to convert {field_name} value '{value}' to int")
        return None

def fix_expiration_date(raw_date: str, ref_year: Optional[int] = None) -> Optional[str]:
    """Parse and format expiration date to MM/DD/YYYY."""
    if not raw_date or str(raw_date).lower() in ['n/a', '']:
        return None
    
    date_str = re.sub(r"[^0-9/\\-]", "", str(raw_date).strip()).replace("\\", "/").replace("-", "/")
    if not date_str:
        return None
    
    current_date = datetime.now()
    formats = ["%m/%d/%Y", "%m/%d/%y", "%Y/%m/%d", "%m/%d", "%d/%m/%Y", "%Y-%m-%d"]
    
    for fmt in formats:
        try:
            dt = datetime.strptime(date_str, fmt)
            if dt.year < 100:
                dt = dt.replace(year=2000 + dt.year)
            if dt < current_date:
                dt = dt.replace(year=dt.year + 1)
            return dt.strftime("%m/%d/%Y")
        except ValueError:
            continue
    
    return None

def is_data_row(row: List[str]) -> bool:
    """Check if row contains data (not header)."""
    if not row or len(row) == 0:
        return False
    
    # Check if first cell is a symbol (not empty, not a header keyword)
    first_cell = row[0].strip() if len(row) > 0 else ""
    if not first_cell:
        return False
    
    # Skip header rows
    header_keywords = ['symbol', 'contracts', 'entry', 'tp', 'sl', 'target', 'iv', 'gtd', 'notes', 'short puts']
    if any(keyword in first_cell.lower() for keyword in header_keywords):
        return False
    
    # Check if it looks like a ticker symbol (alphanumeric, 1-5 chars)
    if re.match(r'^[A-Z0-9]{1,5}$', first_cell.upper()):
        return True
    
    return False

def create_short_put_play(data_row: List[str], row_num: int, headers: List[str]) -> Tuple[Optional[Dict[str, Any]], List[str]]:
    """
    Create a Short Puts play from CSV row data.
    
    Returns:
        Tuple of (play_dict, errors_list)
    """
    errors = []
    
    def get_cell(col_name: str) -> str:
        """Get cell value by column name."""
        if col_name not in COLUMN_MAPPING:
            return ""
        col_idx = COLUMN_MAPPING[col_name]
        if col_idx < len(data_row):
            return data_row[col_idx].strip()
        return ""
    
    # Required fields
    symbol_value = get_cell("symbol")
    if not symbol_value:
        errors.append(f"Row {row_num}: Missing symbol")
        return None, errors
    
    symbol = clean_ticker_symbol(symbol_value)
    
    contracts_value = get_cell("contracts")
    contracts = safe_convert_int(contracts_value, "contracts", row_num, errors)
    if contracts is None:
        errors.append(f"Row {row_num}: Missing or invalid contracts")
        return None, errors
    
    # Optional fields with defaults from config
    short_puts_config = config.get('short_puts', {})
    
    entry_order_type_raw = get_cell("entry_order_type")
    entry_order_type = parse_order_type(entry_order_type_raw) if entry_order_type_raw else 'limit at ask'
    
    tp_premium_pct_raw = get_cell("tp_premium_pct")
    tp_premium_pct = safe_convert_float(tp_premium_pct_raw, "TP Premium %", row_num, errors) if tp_premium_pct_raw else short_puts_config.get('profit_target_pct', 50.0)
    
    sl_multiplier_raw = get_cell("sl_multiplier")
    sl_multiplier = safe_convert_float(sl_multiplier_raw, "SL Multiplier", row_num, errors) if sl_multiplier_raw else short_puts_config.get('stop_loss_multiplier', 2.0)
    
    sl_premium_pct_raw = get_cell("sl_premium_pct")
    sl_premium_pct = safe_convert_float(sl_premium_pct_raw, "SL Premium %", row_num, errors)
    
    target_dte_raw = get_cell("target_dte")
    target_dte = int(safe_convert_float(target_dte_raw, "Target DTE", row_num, errors)) if target_dte_raw else short_puts_config.get('target_dte', 45)
    
    target_delta_raw = get_cell("target_delta")
    target_delta = safe_convert_float(target_delta_raw, "Target Delta", row_num, errors) if target_delta_raw else short_puts_config.get('target_delta', 0.30)
    
    iv_rank_threshold_raw = get_cell("iv_rank_threshold")
    iv_rank_threshold = safe_convert_float(iv_rank_threshold_raw, "IV Rank Threshold", row_num, errors) if iv_rank_threshold_raw else short_puts_config.get('iv_rank_threshold', 50)
    
    gtd_raw = get_cell("gtd")
    gtd_date = fix_expiration_date(gtd_raw) if gtd_raw else None
    
    # Find matching short put option
    market_data_manager = MarketDataManager()
    current_price = market_data_manager.get_stock_price(symbol)
    
    if not current_price:
        errors.append(f"Row {row_num}: Could not get current price for {symbol}")
        return None, errors
    
    display.info(f"Row {row_num}: Searching for matching short put option for {symbol}...")
    option_data = find_short_put_option(
        symbol,
        target_dte=target_dte,
        target_delta=target_delta,
        iv_rank_threshold=iv_rank_threshold,
        market_data_manager=market_data_manager
    )
    
    if not option_data:
        errors.append(f"Row {row_num}: No matching short put option found for {symbol} with criteria: DTE={target_dte}, Delta={target_delta}, IV Rank>{iv_rank_threshold}%")
        return None, errors
    
    # Entry point for SHORT positions (SELL to open)
    entry_credit = option_data['ask']  # Use ask price for entry credit
    
    entry_point = {
        "stock_price": round(current_price, 2),
        "order_type": entry_order_type,
        "entry_credit": entry_credit
    }
    
    # Take Profit: percentage of premium (premium decreases)
    tp_premium_target = entry_credit * (1 - tp_premium_pct / 100.0)
    take_profit = {
        'premium_pct': tp_premium_pct,
        'order_type': 'limit at bid',  # For SHORT: buy back at bid (close position)
        'TP_option_prem': tp_premium_target
    }
    
    # Stop Loss: use multiplier or premium %
    stop_loss = None
    if sl_premium_pct:
        # Use premium percentage if specified
        sl_premium_target = entry_credit * (1 + sl_premium_pct / 100.0)
        stop_loss = {
            'premium_pct': sl_premium_pct,
            'order_type': 'market',
            'SL_type': 'STOP',
            'SL_option_prem': sl_premium_target
        }
    elif sl_multiplier:
        # Use multiplier if specified
        sl_premium_target = entry_credit * sl_multiplier
        stop_loss = {
            'premium_pct': (sl_multiplier - 1.0) * 100.0,
            'order_type': 'market',
            'SL_type': 'STOP',
            'SL_option_prem': sl_premium_target
        }
    
    # Use GTD date or expiration date for play expiration
    play_expiration_date = gtd_date or option_data['expiration_date_formatted']
    
    # Generate play name
    play_name = f"{symbol}-PUT-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{row_num}"
    
    # Build play dictionary
    play = {
        "play_name": play_name,
        "symbol": symbol,
        "expiration_date": option_data['expiration_date_formatted'],
        "trade_type": "PUT",
        "strike_price": option_data['strike_price'],
        "option_contract_symbol": option_data['option_contract_symbol'],
        "contracts": contracts,
        "play_expiration_date": play_expiration_date,
        "entry_point": entry_point,
        "take_profit": take_profit,
        "stop_loss": stop_loss,
        "play_class": "SIMPLE",
        "strategy": "Short Puts",
        "position_side": "SHORT",
        "creation_date": datetime.now().strftime('%Y-%m-%d'),
        "creator": "csv-ingestor",
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
        "conditional_plays": {}
    }
    
    display.success(f"Row {row_num}: Created Short Puts play for {symbol} - {option_data['option_contract_symbol']}")
    display.info(f"  Strike: ${option_data['strike_price']}, DTE: {option_data['dte']}, "
                f"Delta: {option_data['abs_delta']:.3f}, IV Rank: {option_data['iv_rank']:.1f}%")
    
    return play, errors

def save_play(play: Dict[str, Any]) -> str:
    """Save play to JSON file in appropriate directory."""
    base_dir = os.path.join(project_root, "goldflipper", "plays")
    target_dir = os.path.join(base_dir, "new")  # Short Puts plays go to 'new' directory
    os.makedirs(target_dir, exist_ok=True)
    
    filename = re.sub(r"[^\w\-]", "_", play["play_name"]) + ".json"
    filepath = os.path.join(target_dir, filename)
    
    try:
        with open(filepath, "w") as f:
            json.dump(play, f, indent=4)
        display.success(f"Play saved to: {filepath}")
        return filepath
    except Exception as e:
        display.error(f"Failed to save play: {e}")
        raise

def main():
    """Main function to process Short Puts CSV file."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Ingest Short Puts plays from CSV template.")
    parser.add_argument("csv_file", help="Path to the CSV file containing Short Puts play data.")
    args = parser.parse_args()
    
    csv_file_path = args.csv_file
    if not os.path.exists(csv_file_path):
        display.error(f"CSV file not found: {csv_file_path}")
        return
    
    display.header("Short Puts CSV Ingestion Tool")
    
    # Read CSV file
    with open(csv_file_path, newline="", encoding="utf-8") as csvfile:
        reader = list(csv.reader(csvfile))
    
    if not reader:
        display.error("CSV file is empty.")
        return
    
    # Find header row and data rows
    header_row = None
    data_rows = []
    
    for i, row in enumerate(reader):
        if i == 0 or (header_row is None and any('symbol' in str(cell).lower() for cell in row if cell)):
            # Check if this looks like a header row
            row_lower = [str(cell).lower().strip() for cell in row]
            if 'symbol' in row_lower or 'contracts' in row_lower:
                header_row = row
                continue
        elif is_data_row(row):
            data_rows.append((i + 1, row))  # Store row number for error reporting
    
    if not data_rows:
        display.error("No data rows found in CSV file.")
        return
    
    display.info(f"Found {len(data_rows)} data row(s) to process")
    
    # Process each row
    valid_plays = []
    all_errors = []
    created_files = []
    
    for row_num, data_row in data_rows:
        try:
            play, errors = create_short_put_play(data_row, row_num, header_row or [])
            if play:
                valid_plays.append(play)
                filepath = save_play(play)
                created_files.append(filepath)
            all_errors.extend(errors)
        except Exception as e:
            error_msg = f"Row {row_num}: Error processing play - {str(e)}"
            display.error(error_msg)
            all_errors.append(error_msg)
            logging.exception(error_msg)
    
    # Summary
    display.header("Ingestion Summary")
    display.info(f"Successfully created {len(valid_plays)} play(s)")
    
    if all_errors:
        display.warning(f"Found {len(all_errors)} error(s)/warning(s):")
        for err in all_errors[:10]:  # Show first 10 errors
            display.warning(f"  - {err}")
        if len(all_errors) > 10:
            display.warning(f"  ... and {len(all_errors) - 10} more error(s)")
    
    # Open files if configured
    ingestor_config = config.get('csv_ingestor') or {}
    should_open = ingestor_config.get('open_after_creation', True)
    
    if should_open and created_files:
        display.info("Opening created play files...")
        for json_path in created_files:
            if os.path.exists(json_path):
                try:
                    if platform.system() == "Windows":
                        os.startfile(json_path)
                    elif platform.system() == "Darwin":
                        subprocess.run(["open", json_path])
                    else:
                        subprocess.run(["xdg-open", json_path])
                except Exception as e:
                    display.warning(f"Could not open file {json_path}: {e}")

if __name__ == "__main__":
    main()
