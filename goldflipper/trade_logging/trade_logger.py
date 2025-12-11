from datetime import datetime
import pandas as pd
import os
import json
import shutil
from typing import List, Dict, Any
import logging

# Import the data backfill helper
try:
    from .data_backfill_helper import DataBackfillHelper
    BACKFILL_AVAILABLE = True
except ImportError as e:
    logging.warning(f"Data backfill helper not available: {str(e)}")
    BACKFILL_AVAILABLE = False

class PlayLogger:
    def __init__(self, base_directory=None, save_to_desktop=True, enable_backfill=True):
        if base_directory is None:
            # Use exe-aware, account-aware path utilities
            from goldflipper.utils.exe_utils import get_plays_dir
            self.base_directory = str(get_plays_dir())
        else:
            self.base_directory = base_directory
        
        # Main log directory - use exe-aware path utilities
        from goldflipper.utils.exe_utils import get_logs_dir
        self.log_directory = os.path.join(str(get_logs_dir()), "trade_logging")
        
        # Create log directory if it doesn't exist
        if not os.path.exists(self.log_directory):
            os.makedirs(self.log_directory)
        
        # Current working log file
        self.csv_path = os.path.join(self.log_directory, "trade_log.csv")
        
        # Save to desktop option
        self.save_to_desktop = save_to_desktop
        
        # Data backfill options
        self.enable_backfill = enable_backfill and BACKFILL_AVAILABLE
        self.backfill_helper = None
        
        if self.enable_backfill:
            try:
                self.backfill_helper = DataBackfillHelper()
                logging.info("Data backfill helper initialized successfully")
            except Exception as e:
                logging.warning(f"Failed to initialize backfill helper: {str(e)}")
                self.enable_backfill = False
            
        # Initialize or load existing CSV
        if not os.path.exists(self.csv_path):
            self._create_empty_log()
    
    def _create_empty_log(self):
        """Initialize empty CSV with columns and proper dtypes"""
        # Define columns and their appropriate dtypes to prevent warnings
        # Added 'strategy' and 'action' for multi-strategy support (2025-12-01)
        dtype_dict = {
            'play_name': 'object',
            'symbol': 'object', 
            'strategy': 'object',  # Strategy type: option_swings, momentum, sell_puts, spreads
            'action': 'object',    # Order action: BTO, STC, STO, BTC
            'trade_type': 'object',
            'strike_price': 'float64',
            'expiration_date': 'object',
            'contracts': 'int64',
            'date_atOpen': 'object',  # String dates
            'time_atOpen': 'object',  # String times
            'date_atClose': 'object',  # String dates
            'time_atClose': 'object',  # String times
            'price_atOpen': 'float64',
            'price_atClose': 'float64', 
            'premium_atOpen': 'float64',
            'premium_atClose': 'float64',
            'delta_atOpen': 'float64',
            'theta_atOpen': 'float64',
            'close_type': 'object',  # String values like 'SL', 'TP'
            'close_condition': 'object',  # String values
            'profit_loss_pct': 'float64',
            'profit_loss': 'float64',
            'status': 'object'  # String values like 'closed', 'expired'
        }
        
        columns = list(dtype_dict.keys())
        df = pd.DataFrame(columns=columns).astype(dtype_dict)
        df.to_csv(self.csv_path, index=False)
    
    def reset_log(self):
        """Reset the log file with correct columns"""
        self._create_empty_log()
        print("Log file has been reset with correct columns.")
    
    def import_closed_plays(self):
        """Import all plays from CLOSED and EXPIRED folders"""
        # First reset the log to ensure clean state
        self.reset_log()
        
        print(f"Looking for plays in: {self.base_directory}")
        
        # Collect all valid play data first
        all_plays_data = []
        skipped_count = 0
        
        for status in ['closed', 'expired']:
            folder_path = os.path.join(self.base_directory, status)
            print(f"Checking folder: {folder_path}")
            
            if not os.path.exists(folder_path):
                print(f"Folder does not exist: {folder_path}")
                continue
                
            for filename in os.listdir(folder_path):
                if filename.endswith('.json'):
                    file_path = os.path.join(folder_path, filename)
                    print(f"Processing file: {file_path}")
                    try:
                        with open(file_path, 'r') as f:
                            play_data = json.load(f)
                        
                        # Validate the play data with enhanced validation
                        validation_result = self._validate_play_data(play_data, status)
                        if validation_result['valid']:
                            # Add status and file path for reference
                            play_data['_status'] = status
                            play_data['_file_path'] = file_path
                            all_plays_data.append(play_data)
                        else:
                            print(f"⚠ Skipped {filename}: {validation_result['reason']}")
                            skipped_count += 1
                            
                    except Exception as e:
                        print(f"✗ Error processing {file_path}: {str(e)}")
                        skipped_count += 1
        
        print(f"Collected {len(all_plays_data)} valid plays for processing")
        
        # Apply data backfill if enabled
        if self.enable_backfill and self.backfill_helper and all_plays_data:
            print(f"🔄 Starting data backfill process...")
            try:
                all_plays_data = self.backfill_helper.backfill_multiple_plays(all_plays_data)
                print(f"✅ Data backfill completed")
            except Exception as e:
                print(f"⚠ Data backfill failed: {str(e)}")
                logging.error(f"Backfill error: {str(e)}")
        elif not self.enable_backfill:
            print(f"ℹ Data backfill disabled")
        
        # Now log all the plays (with backfilled data if available)
        imported_count = 0
        for play_data in all_plays_data:
            status = play_data.pop('_status')
            file_path = play_data.pop('_file_path')
            filename = os.path.basename(file_path)
            
            try:
                self.log_play(play_data, status, source_filename=filename)
                imported_count += 1
                # Only show success message every 5 files to reduce spam
                if imported_count % 5 == 0 or imported_count <= 5:
                    print(f"✓ Successfully logged: {filename}")
            except Exception as log_error:
                print(f"✗ Error logging {filename}: {str(log_error)}")
                import traceback
                traceback.print_exc()
        
        print(f"Total plays imported: {imported_count}")
        if skipped_count > 0:
            print(f"Total plays skipped: {skipped_count}")
        
        return imported_count
    
    def import_all_plays(self):
        """Import plays from ALL subfolders (except 'old'), with minimal validation.
        Only requires the 'symbol' field to be present. Other fields are optional.
        """
        # Reset the log first
        self.reset_log()

        print(f"Scanning all play folders in: {self.base_directory}")

        if not os.path.exists(self.base_directory):
            print(f"Base plays directory does not exist: {self.base_directory}")
            return 0

        all_plays_data = []
        skipped_count = 0

        try:
            subfolders = [
                name for name in os.listdir(self.base_directory)
                if os.path.isdir(os.path.join(self.base_directory, name)) and name.lower() != 'old'
            ]
        except Exception as e:
            print(f"Error reading subfolders: {str(e)}")
            return 0

        # Process each subfolder as a status bucket
        for status in subfolders:
            folder_path = os.path.join(self.base_directory, status)
            print(f"Checking folder: {folder_path}")

            for filename in os.listdir(folder_path):
                if not filename.endswith('.json'):
                    continue

                file_path = os.path.join(folder_path, filename)
                try:
                    with open(file_path, 'r') as f:
                        play_data = json.load(f)

                    # Minimal validation: symbol must exist and be non-empty
                    symbol = (play_data.get('symbol') or '').strip()
                    if not symbol:
                        print(f"⚠ Skipped {filename}: missing required 'symbol'")
                        skipped_count += 1
                        continue

                    play_data['_status'] = status
                    play_data['_file_path'] = file_path
                    all_plays_data.append(play_data)
                except Exception as e:
                    print(f"✗ Error processing {file_path}: {str(e)}")
                    skipped_count += 1

        print(f"Collected {len(all_plays_data)} plays for processing (minimal validation)")

        # Apply data backfill if enabled and available
        if self.enable_backfill and self.backfill_helper and all_plays_data:
            print("🔄 Starting data backfill process...")
            try:
                all_plays_data = self.backfill_helper.backfill_multiple_plays(all_plays_data)
                print("✅ Data backfill completed")
            except Exception as e:
                print(f"⚠ Data backfill failed: {str(e)}")
                logging.error(f"Backfill error: {str(e)}")
        elif not self.enable_backfill:
            print("ℹ Data backfill disabled")

        imported_count = 0
        for play_data in all_plays_data:
            status = play_data.pop('_status')
            file_path = play_data.pop('_file_path')
            filename = os.path.basename(file_path)
            try:
                self.log_play(play_data, status, source_filename=filename)
                imported_count += 1
                if imported_count % 5 == 0 or imported_count <= 5:
                    print(f"✓ Successfully logged: {filename}")
            except Exception as log_error:
                print(f"✗ Error logging {filename}: {str(log_error)}")
                import traceback
                traceback.print_exc()

        print(f"Total plays imported: {imported_count}")
        if skipped_count > 0:
            print(f"Total plays skipped: {skipped_count}")

        return imported_count
    
    def log_play(self, play_data: Dict[str, Any], status: str, source_filename: str = None):
        """Log a single play to CSV with enhanced data extraction from multiple sources.
        This method is resilient to missing fields; only 'symbol' is strictly required.
        """
        logging_data = play_data.get('logging', {})
        entry_point = play_data.get('entry_point', {})
        
        # Enhanced data extraction with fallback sources
        def safe_float(value):
            """Safely convert value to float"""
            if value is None or value == '':
                return None
            try:
                return float(value)
            except (ValueError, TypeError):
                return None

        def safe_int(value, default: int = 0):
            """Safely convert value to int with default."""
            if value is None or value == '':
                return default
            try:
                return int(value)
            except (ValueError, TypeError):
                return default
        
        # Extract opening data with fallbacks, but only use entry_point values if play is considered opened
        entry_premium_value = safe_float(entry_point.get('entry_premium'))
        opened_by_entry_premium = entry_premium_value is not None and entry_premium_value > 0
        premium_open = safe_float(
            logging_data.get('premium_atOpen') if logging_data.get('premium_atOpen') is not None else (
                entry_point.get('entry_premium') if opened_by_entry_premium else None
            )
        )
        price_open = safe_float(
            logging_data.get('price_atOpen') if logging_data.get('price_atOpen') is not None else (
                entry_point.get('entry_stock_price') if opened_by_entry_premium else None
            )
        )
        
        # For expired plays, we might not have premium data, which is acceptable
        # They represent trading setups that never executed
        
        # Extract closing data (only from logging for now)
        premium_close = safe_float(logging_data.get('premium_atClose'))
        price_close = safe_float(logging_data.get('price_atClose'))
        
        # Split datetime strings into date and time if they exist
        datetime_open = logging_data.get('datetime_atOpen', '')
        datetime_close = logging_data.get('datetime_atClose', '')
        
        date_open = ''
        time_open = ''
        date_close = ''
        time_close = ''
        
        if datetime_open:
            try:
                dt_open = pd.to_datetime(datetime_open)
                date_open = dt_open.strftime('%Y-%m-%d')
                time_open = dt_open.strftime('%H:%M:%S')
            except:
                pass
            
        if datetime_close:
            try:
                dt_close = pd.to_datetime(datetime_close)
                date_close = dt_close.strftime('%Y-%m-%d')
                time_close = dt_close.strftime('%H:%M:%S')
            except:
                pass
            
        # Calculate profit/loss percentage
        pl_pct = 0.0
        if premium_open and premium_close and premium_open != 0:
            pl_pct = ((premium_close - premium_open) / abs(premium_open)) * 100
            
        # Calculate absolute profit/loss
        pl_dollars = self._calculate_pl(play_data)

        # Ensure we at least have a symbol; if not, skip
        symbol_value = play_data.get('symbol')
        if not symbol_value:
            raise ValueError("Missing required field: symbol")

        # Extract strategy and action for multi-strategy support
        strategy = play_data.get('strategy') or 'option_swings'  # Default to legacy strategy
        action = play_data.get('action') or 'BTO'  # Default to Buy-To-Open
        
        play_entry = {
            'play_name': play_data.get('play_name') or (source_filename or ''),
            'symbol': symbol_value,
            'strategy': strategy,
            'action': action,
            'trade_type': play_data.get('trade_type') or '',
            'strike_price': safe_float(play_data.get('strike_price')),
            'expiration_date': play_data.get('expiration_date') or '',
            'contracts': safe_int(play_data.get('contracts'), default=0),
            'date_atOpen': date_open,
            'time_atOpen': time_open,
            'date_atClose': date_close,
            'time_atClose': time_close,
            'price_atOpen': price_open,
            'price_atClose': price_close,
            'premium_atOpen': premium_open,
            'premium_atClose': premium_close,
            'delta_atOpen': safe_float(logging_data.get('delta_atOpen')),
            'theta_atOpen': safe_float(logging_data.get('theta_atOpen')),
            'close_type': logging_data.get('close_type'),
            'close_condition': logging_data.get('close_condition'),
            'profit_loss_pct': pl_pct,
            'profit_loss': pl_dollars,
            'status': status
        }
        
        # Read existing DataFrame with proper dtypes to prevent warnings
        # Define the expected dtypes for consistent behavior (with strategy/action for multi-strategy)
        dtype_dict = {
            'play_name': 'object',
            'symbol': 'object',
            'strategy': 'object',
            'action': 'object',
            'trade_type': 'object',
            'strike_price': 'float64',
            'expiration_date': 'object',
            'contracts': 'int64',
            'date_atOpen': 'object',
            'time_atOpen': 'object',
            'date_atClose': 'object',
            'time_atClose': 'object',
            'price_atOpen': 'float64',
            'price_atClose': 'float64',
            'premium_atOpen': 'float64',
            'premium_atClose': 'float64',
            'delta_atOpen': 'float64',
            'theta_atOpen': 'float64',
            'close_type': 'object',
            'close_condition': 'object',
            'profit_loss_pct': 'float64',
            'profit_loss': 'float64',
            'status': 'object'
        }
        
        try:
            df = pd.read_csv(self.csv_path, dtype=dtype_dict)
        except (ValueError, TypeError):
            # Fallback: read without dtype specification if there are issues
            df = pd.read_csv(self.csv_path)
            # Convert string columns to object dtype to prevent warnings
            string_columns = ['date_atOpen', 'time_atOpen', 'date_atClose', 'time_atClose', 
                            'close_type', 'close_condition', 'status', 'play_name', 'symbol', 
                            'strategy', 'action', 'trade_type', 'expiration_date']
            for col in string_columns:
                if col in df.columns:
                    df.loc[:, col] = df[col].astype('object')
        
        # Create new DataFrame entry
        new_entry = pd.DataFrame([play_entry])
        
        # Handle DataFrame concatenation to avoid FutureWarning about empty/NA columns
        # Following pandas best practices to prevent FutureWarning about all-NA columns
        if df.empty:
            # If the existing DataFrame is empty, just use the new entry
            df = new_entry.copy()
        else:
            # Ensure column consistency and handle all-NA columns explicitly
            # Add missing columns to new_entry with appropriate default values
            for col in df.columns:
                if col not in new_entry.columns:
                    new_entry[col] = None
            
            # Add any new columns from new_entry to existing df
            for col in new_entry.columns:
                if col not in df.columns:
                    df.loc[:, col] = None
            
            # Ensure both DataFrames have columns in the same order
            new_entry = new_entry[df.columns]
            
            # Use manual row appending to avoid FutureWarning
            # Since we now create DataFrames with proper dtypes, this should work cleanly
            new_row_index = len(df)
            for col in df.columns:
                df.loc[new_row_index, col] = new_entry.iloc[0][col]
        
        # Save to CSV
        df.to_csv(self.csv_path, index=False)
    
    def _calculate_pl(self, play_data: Dict[str, Any]) -> float:
        """Calculate profit/loss in dollars using enhanced data extraction"""
        logging_data = play_data.get('logging', {})
        entry_point = play_data.get('entry_point', {})
        contracts = play_data.get('contracts', 0)
        
        def safe_float(value):
            """Safely convert value to float"""
            if value is None or value == '':
                return None
            try:
                return float(value)
            except (ValueError, TypeError):
                return None
        
        # Extract premium data with fallbacks (same gating as in log_play)
        entry_premium_value = safe_float(entry_point.get('entry_premium'))
        opened_by_entry_premium = entry_premium_value is not None and entry_premium_value > 0
        premium_open = safe_float(
            logging_data.get('premium_atOpen') if logging_data.get('premium_atOpen') is not None else (
                entry_point.get('entry_premium') if opened_by_entry_premium else None
            )
        )
        premium_close = safe_float(logging_data.get('premium_atClose'))
        
        # Note: Expired plays might not have premium data, which is acceptable
        
        # Calculate P/L if we have both values
        if premium_open is not None and premium_close is not None and contracts:
            try:
                return (premium_close - premium_open) * float(contracts) * 100
            except (ValueError, TypeError):
                pass
                
        return 0.0

    def _validate_play_data(self, play_data: Dict[str, Any], status: str) -> Dict[str, Any]:
        """Enhanced validation that accepts files with entry_point data as fallback"""
        required_fields = ['play_name', 'symbol', 'trade_type', 'strike_price', 'expiration_date', 'contracts']
        
        # Check required basic fields
        for field in required_fields:
            if field not in play_data or play_data[field] is None:
                return {'valid': False, 'reason': f'Missing required field: {field}'}
        
        # Validate numeric fields
        try:
            float(play_data['strike_price'])
        except (ValueError, TypeError):
            return {'valid': False, 'reason': f'Invalid strike_price: {play_data["strike_price"]}'}
        
        try:
            int(play_data['contracts'])
        except (ValueError, TypeError):
            return {'valid': False, 'reason': f'Invalid contracts: {play_data["contracts"]}'}
        
        # Enhanced validation for data availability
        logging_data = play_data.get('logging', {})
        entry_point = play_data.get('entry_point', {})
        
        # Check if we have ANY useful data for opening positions
        has_logging_open = (logging_data.get('datetime_atOpen') or logging_data.get('premium_atOpen') is not None)
        has_entry_data = (entry_point.get('entry_premium') is not None or entry_point.get('entry_stock_price') is not None)
        has_basic_entry = entry_point.get('stock_price') is not None  # For expired plays
        
        # For expired status, be very permissive - accept files with basic trade info
        if status == 'expired':
            if has_logging_open or has_entry_data or has_basic_entry:
                return {'valid': True, 'reason': 'Valid - expired play with basic data'}
            else:
                return {'valid': False, 'reason': 'No usable data found (expired play missing basic entry_point data)'}
        
        # For closed status, require at least some opening data
        if status == 'closed':
            if has_logging_open or has_entry_data:
                return {'valid': True, 'reason': 'Valid - has opening data'}
            else:
                return {'valid': False, 'reason': 'No usable opening data found (closed play missing logging and entry_point data)'}
        
        return {'valid': True, 'reason': 'Valid'}

    def export_to_spreadsheet(self, format='csv', save_to_desktop=None):
        """
        Export logs to spreadsheet format with enhanced formatting
        
        Args:
            format (str): 'csv', 'excel', or 'both' format
            save_to_desktop (bool, optional): Override instance setting for saving to desktop
        
        Returns:
            dict: Dictionary containing paths to the exported files
        """
        # Create timestamp for unique directory
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        export_dir = os.path.join(self.log_directory, f"trade_log_{timestamp}")
        
        # Create the export directory
        if not os.path.exists(export_dir):
            os.makedirs(export_dir)
            
        # Determine if we should save to desktop
        if save_to_desktop is None:
            save_to_desktop = self.save_to_desktop
            
        # Get desktop path
        desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
        
        # Dictionary to store all paths
        result_paths = {
            'export_dir': export_dir,
            'main_file': None,
            'desktop_file': None,
            'csv_file': None,
            'excel_file': None,
            'csv_desktop_file': None,
            'excel_desktop_file': None
        }
        
        # If format is 'both', export both formats
        if format == 'both':
            csv_result = self._export_csv(export_dir, timestamp, desktop_path, save_to_desktop)
            excel_result = self._export_excel(export_dir, timestamp, desktop_path, save_to_desktop)
            
            result_paths.update({
                'csv_file': csv_result['main_file'],
                'excel_file': excel_result['main_file'],
                'csv_desktop_file': csv_result['desktop_file'],
                'excel_desktop_file': excel_result['desktop_file'],
                'main_file': excel_result['main_file']  # Default to Excel as main file
            })
            
            return result_paths
            
        elif format == 'csv':
            csv_result = self._export_csv(export_dir, timestamp, desktop_path, save_to_desktop)
            result_paths.update({
                'csv_file': csv_result['main_file'],
                'main_file': csv_result['main_file'],
                'desktop_file': csv_result['desktop_file']
            })
            
            return result_paths
            
        elif format == 'excel':
            excel_result = self._export_excel(export_dir, timestamp, desktop_path, save_to_desktop)
            result_paths.update({
                'excel_file': excel_result['main_file'],
                'main_file': excel_result['main_file'],
                'desktop_file': excel_result['desktop_file']
            })
            
            return result_paths
    
    def _export_csv(self, export_dir, timestamp, desktop_path, save_to_desktop):
        """Helper method to export CSV format"""
        result = {
            'main_file': None,
            'desktop_file': None
        }
        
        # Main export file
        export_path = os.path.join(export_dir, "trade_log.csv")
        
        # Read the current CSV and save to the new location
        df = pd.read_csv(self.csv_path)
        df.to_csv(export_path, index=False)
        
        # Save a copy to the desktop if requested
        if save_to_desktop:
            desktop_file = os.path.join(desktop_path, f"trade_log_{timestamp}.csv")
            df.to_csv(desktop_file, index=False)
            result['desktop_file'] = desktop_file
            
        result['main_file'] = export_path
        return result
        
    def _export_excel(self, export_dir, timestamp, desktop_path, save_to_desktop):
        """Helper method to export Excel format with formatting"""
        result = {
            'main_file': None,
            'desktop_file': None
        }
        
        # Main export file
        export_path = os.path.join(export_dir, "trade_log.xlsx")
        df = pd.read_csv(self.csv_path)
        
        # Ensure numeric columns are properly typed
        numeric_columns = ['strike_price', 'price_atOpen', 'price_atClose', 
                          'premium_atOpen', 'premium_atClose', 'delta_atOpen', 
                          'theta_atOpen', 'profit_loss_pct', 'profit_loss']
        
        for col in numeric_columns:
            if col in df.columns:
                df.loc[:, col] = pd.to_numeric(df[col], errors='coerce')
        
        # Define friendly column names mapping (with strategy/action for multi-strategy)
        column_mapping = {
            'play_name': 'Play Name',
            'symbol': 'Symbol',
            'strategy': 'Strategy',
            'action': 'Action',
            'trade_type': 'Trade',
            'strike_price': 'Strike',
            'expiration_date': 'Expiration',
            'contracts': '#',
            'date_atOpen': 'Open Date',
            'time_atOpen': 'Open Time',
            'date_atClose': 'Close Date',
            'time_atClose': 'Close Time',
            'price_atOpen': 'Open Price',
            'price_atClose': 'Close Price',
            'premium_atOpen': 'Open Prem.',
            'premium_atClose': 'Close Prem.',
            'delta_atOpen': 'Open Δ',
            'theta_atOpen': 'Open Θ',
            'close_type': 'Close',
            'close_condition': 'Condition',
            'profit_loss_pct': 'P/L %',
            'profit_loss': 'P/L $',
            'status': 'Status'
        }
        
        # Rename columns
        df = df.rename(columns=column_mapping)
        
        # Create Excel writer object with xlsxwriter engine
        writer = pd.ExcelWriter(
            export_path,
            engine='xlsxwriter',
            engine_kwargs={'options': {'nan_inf_to_errors': True}}
        )
        
        with writer as writer:
            df.to_excel(writer, index=False, sheet_name='Trade Log')
            
            # Get the xlsxwriter workbook and worksheet objects
            workbook = writer.book
            worksheet = writer.sheets['Trade Log']
            
            # Define border color and profit/loss colors
            border_color = '#D3D3D3'  # Light gray
            profit_color = '#E8F4EA'  # Light green
            loss_color = '#FBE9E7'    # Light red
            
            # Money formats with alternating shades
            money_format_even = workbook.add_format({
                'num_format': '$#,##0.00',
                'align': 'center',
                'bg_color': '#F2F2F2',
                'border_color': border_color,
                'border': 1
            })
            
            money_format_odd = workbook.add_format({
                'num_format': '$#,##0.00',
                'align': 'center',
                'bg_color': 'white',
                'border_color': border_color,
                'border': 1
            })
            
            # Strike price format (no cents)
            strike_format_even = workbook.add_format({
                'num_format': '$#,##0',
                'align': 'center',
                'bg_color': '#F2F2F2',
                'border_color': border_color,
                'border': 1
            })
            
            strike_format_odd = workbook.add_format({
                'num_format': '$#,##0',
                'align': 'center',
                'bg_color': 'white',
                'border_color': border_color,
                'border': 1
            })
            
            # Profit/Loss formats with colors
            profit_format_even = workbook.add_format({
                'num_format': '+$#,##0.00;-$#,##0.00',
                'align': 'center',
                'bg_color': profit_color,
                'border_color': border_color,
                'border': 1
            })
            
            profit_format_odd = workbook.add_format({
                'num_format': '+$#,##0.00;-$#,##0.00',
                'align': 'center',
                'bg_color': profit_color,
                'border_color': border_color,
                'border': 1
            })
            
            loss_format_even = workbook.add_format({
                'num_format': '+$#,##0.00;-$#,##0.00',
                'align': 'center',
                'bg_color': loss_color,
                'border_color': border_color,
                'border': 1
            })
            
            loss_format_odd = workbook.add_format({
                'num_format': '+$#,##0.00;-$#,##0.00',
                'align': 'center',
                'bg_color': loss_color,
                'border_color': border_color,
                'border': 1
            })
            
            # Add percentage formats with alternating shades
            profit_pct_format_even = workbook.add_format({
                'num_format': '0.00%',
                'align': 'center',
                'bg_color': profit_color,
                'border_color': border_color,
                'border': 1
            })
            
            profit_pct_format_odd = workbook.add_format({
                'num_format': '0.00%',
                'align': 'center',
                'bg_color': profit_color,
                'border_color': border_color,
                'border': 1
            })
            
            loss_pct_format_even = workbook.add_format({
                'num_format': '0.00%',
                'align': 'center',
                'bg_color': loss_color,
                'border_color': border_color,
                'border': 1
            })
            
            loss_pct_format_odd = workbook.add_format({
                'num_format': '0.00%',
                'align': 'center',
                'bg_color': loss_color,
                'border_color': border_color,
                'border': 1
            })
            
            # Define border color
            border_color = '#D3D3D3'  # Light gray
            
            # Define formats with borders
            header_format_centered = workbook.add_format({
                'bold': True,
                'font_color': 'white',
                'bg_color': '#2F75B5',
                'align': 'center',
                'valign': 'vcenter',
                'border_color': border_color,
                'border': 1
            })

            header_format_left = workbook.add_format({
                'bold': True,
                'font_color': 'white',
                'bg_color': '#2F75B5',
                'align': 'left',
                'valign': 'vcenter',
                'border_color': border_color,
                'border': 1
            })
            
            even_row_format = workbook.add_format({
                'bg_color': '#F2F2F2',
                'align': 'center',
                'border_color': border_color,
                'border': 1
            })
            
            odd_row_format = workbook.add_format({
                'bg_color': 'white',
                'align': 'center',
                'border_color': border_color,
                'border': 1
            })

            even_row_format_left = workbook.add_format({
                'bg_color': '#F2F2F2',
                'align': 'left',
                'border_color': border_color,
                'border': 1
            })
            
            odd_row_format_left = workbook.add_format({
                'bg_color': 'white',
                'align': 'left',
                'border_color': border_color,
                'border': 1
            })
            
            date_format = workbook.add_format({
                'num_format': 'yyyy-mm-dd',
                'align': 'center',
                'border_color': border_color,
                'border': 1
            })
            
            time_format = workbook.add_format({
                'num_format': 'hh:mm:ss',
                'align': 'center',
                'border_color': border_color,
                'border': 1
            })
            
            # Add date and time formats with alternating shades
            date_format_even = workbook.add_format({
                'num_format': 'yyyy-mm-dd',
                'align': 'center',
                'bg_color': '#F2F2F2',
                'border_color': border_color,
                'border': 1
            })
            
            date_format_odd = workbook.add_format({
                'num_format': 'yyyy-mm-dd',
                'align': 'center',
                'bg_color': 'white',
                'border_color': border_color,
                'border': 1
            })
            
            time_format_even = workbook.add_format({
                'num_format': 'hh:mm:ss',
                'align': 'center',
                'bg_color': '#F2F2F2',
                'border_color': border_color,
                'border': 1
            })
            
            time_format_odd = workbook.add_format({
                'num_format': 'hh:mm:ss',
                'align': 'center',
                'bg_color': 'white',
                'border_color': border_color,
                'border': 1
            })
            
            # Apply header format
            for col_num, value in enumerate(df.columns.values):
                if value == 'Play Name':
                    worksheet.write(0, col_num, value, header_format_centered)
                else:
                    worksheet.write(0, col_num, value, header_format_left)
            
            # Apply content row formats (starting from row 1)
            for row_num in range(len(df)):
                for col_num, col in enumerate(df.columns):
                    value = df.iloc[row_num, col_num]
                    is_even_row = row_num % 2 == 0
                    
                    # Handle NaN/None values
                    if pd.isna(value):
                        value = ''
                    
                    if col == 'Play Name':
                        row_format = even_row_format_left if is_even_row else odd_row_format_left
                        worksheet.write(row_num + 1, col_num, value, row_format)
                    elif 'Strike' in col:
                        strike_format = strike_format_even if is_even_row else strike_format_odd
                        if pd.isna(value) or value == '':
                            worksheet.write_blank(row_num + 1, col_num, None, strike_format)
                        else:
                            try:
                                value = float(value)
                                worksheet.write_number(row_num + 1, col_num, value, strike_format)
                            except (ValueError, TypeError):
                                worksheet.write(row_num + 1, col_num, value, strike_format)
                    elif 'Profit/Loss' in col:
                        try:
                            value = float(value) if not pd.isna(value) else 0.0
                            if value == 0:
                                # Write blank cell with even/odd background
                                pl_format = money_format_even if is_even_row else money_format_odd
                                worksheet.write_blank(row_num + 1, col_num, None, pl_format)
                            else:
                                # Use profit/loss format based on value
                                if value > 0:
                                    pl_format = profit_format_even if is_even_row else profit_format_odd
                                else:
                                    pl_format = loss_format_even if is_even_row else loss_format_odd
                                worksheet.write_number(row_num + 1, col_num, value, pl_format)
                        except (ValueError, TypeError):
                            worksheet.write(row_num + 1, col_num, value, money_format_even if is_even_row else money_format_odd)
                    elif any(term in col for term in ['Price', 'Premium', 'Prem.']):
                        money_format = money_format_even if is_even_row else money_format_odd
                        if pd.isna(value) or value == '':
                            worksheet.write_blank(row_num + 1, col_num, None, money_format)
                        else:
                            try:
                                value = float(value)
                                worksheet.write_number(row_num + 1, col_num, value, money_format)
                            except (ValueError, TypeError):
                                worksheet.write(row_num + 1, col_num, value, money_format)
                    elif 'Date' in col:
                        date_format = date_format_even if is_even_row else date_format_odd
                        if pd.isna(value) or value == '':
                            worksheet.write_blank(row_num + 1, col_num, None, date_format)
                        else:
                            worksheet.write(row_num + 1, col_num, value, date_format)
                    elif 'Time' in col:
                        time_format = time_format_even if is_even_row else time_format_odd
                        if pd.isna(value) or value == '':
                            worksheet.write_blank(row_num + 1, col_num, None, time_format)
                        else:
                            worksheet.write(row_num + 1, col_num, value, time_format)
                    elif 'P/L %' in col:
                        try:
                            value = float(value) if not pd.isna(value) else 0.0
                            if value == 0:
                                # Write blank cell with even/odd background
                                pl_format = money_format_even if is_even_row else money_format_odd
                                worksheet.write_blank(row_num + 1, col_num, None, pl_format)
                            else:
                                # Use profit/loss format based on value
                                if value > 0:
                                    pl_format = profit_pct_format_even if is_even_row else profit_pct_format_odd
                                else:
                                    pl_format = loss_pct_format_even if is_even_row else loss_pct_format_odd
                                worksheet.write_number(row_num + 1, col_num, value/100, pl_format)
                        except (ValueError, TypeError):
                            worksheet.write(row_num + 1, col_num, value, money_format_even if is_even_row else money_format_odd)
                    elif 'P/L $' in col:
                        try:
                            value = float(value) if not pd.isna(value) else 0.0
                            if value == 0:
                                # Write blank cell with even/odd background
                                pl_format = money_format_even if is_even_row else money_format_odd
                                worksheet.write_blank(row_num + 1, col_num, None, pl_format)
                            else:
                                # Use profit/loss format based on value
                                if value > 0:
                                    pl_format = profit_format_even if is_even_row else profit_format_odd
                                else:
                                    pl_format = loss_format_even if is_even_row else loss_format_odd
                                worksheet.write_number(row_num + 1, col_num, value, pl_format)
                        except (ValueError, TypeError):
                            worksheet.write(row_num + 1, col_num, value, money_format_even if is_even_row else money_format_odd)
                    else:
                        row_format = even_row_format if is_even_row else odd_row_format
                        worksheet.write(row_num + 1, col_num, value, row_format)
            
            # Define column width overrides (in characters)
            column_width_overrides = {
                'Symbol': 9,
                'Trade': 7.5,
                'Strike': 7.5,
                'Expiration': 11.5,
                '#': 3.5,
                'Open Date': 12,
                'Open Time': 12,
                'Close Date': 12,
                'Close Time': 12,
                'Open Price': 12.25,
                'Close Price': 12.25,
                'Open Prem.': 13,
                'Close Prem.': 13,
                'Open Δ': 10,
                'Open Θ': 10,
                'Status': 10,
                'Close': 7.5,
                'Condition': 12,
                'P/L %': 10,
                'P/L $': 12,
                'Status': 8
            }
            
            # Set column widths without setting column formats
            for i, col in enumerate(df.columns):
                # Check if column has a width override
                if col in column_width_overrides:
                    width = column_width_overrides[col]
                else:
                    # Get maximum length of column content
                    max_length = max(
                        df[col].astype(str).apply(len).max(),
                        len(str(col))
                    ) + 2
                    width = min(max_length, 40)
                
                worksheet.set_column(i, i, width)
            
            # Freeze the header row
            worksheet.freeze_panes(1, 0)
            
            # Add autofilter
            worksheet.autofilter(0, 0, len(df), len(df.columns) - 1)
        
        # Save a copy to the desktop if requested
        if save_to_desktop:
            desktop_file = os.path.join(desktop_path, f"trade_log_{timestamp}.xlsx")
            shutil.copy(export_path, desktop_file)
            result['desktop_file'] = desktop_file
        
        result['main_file'] = export_path
        return result

    def get_unique_strategies(self) -> List[str]:
        """Get list of unique strategies from the trade log.
        
        Returns:
            List of strategy names found in the data, sorted alphabetically.
        """
        try:
            df = pd.read_csv(self.csv_path)
            if 'strategy' in df.columns:
                strategies = df['strategy'].dropna().unique().tolist()
                return sorted([str(s) for s in strategies if s])
            return []
        except Exception as e:
            logging.error(f"Error getting unique strategies: {str(e)}")
            return []

    def _create_summary_stats(self, strategy_filter: str = None) -> pd.DataFrame:
        """Create summary statistics from the trade log.
        
        Args:
            strategy_filter: Optional strategy name to filter by. None or "All" shows all.
        """
        try:
            df = pd.read_csv(self.csv_path)
            
            # Apply strategy filter if specified
            if strategy_filter and strategy_filter != "All" and 'strategy' in df.columns:
                df = df[df['strategy'] == strategy_filter]
            
            # Calculate basic statistics
            total_trades = int(len(df))
            winning_trades = int(len(df[df['profit_loss'] > 0])) if total_trades > 0 else 0
            win_rate = float(winning_trades / total_trades * 100) if total_trades > 0 else 0.0
            total_pl = float(df['profit_loss'].sum()) if total_trades > 0 else 0.0
            
            # Return as a DataFrame with explicit types
            stats_df = pd.DataFrame({
                'total_trades': [total_trades],
                'winning_trades': [winning_trades],
                'win_rate': [win_rate],
                'total_pl': [total_pl]
            })
            
            # Convert numeric columns to appropriate types
            stats_df['total_trades'] = stats_df['total_trades'].astype(int)
            stats_df['winning_trades'] = stats_df['winning_trades'].astype(int)
            stats_df['win_rate'] = stats_df['win_rate'].astype(float)
            stats_df['total_pl'] = stats_df['total_pl'].astype(float)
            
            return stats_df
            
        except Exception as e:
            logging.error(f"Error calculating summary stats: {str(e)}")
            raise
            
    def get_export_history(self):
        """
        Get a list of all exported trade logs
        
        Returns:
            list: List of dictionaries containing export information
        """
        exports = []
        
        # Check if log directory exists
        if not os.path.exists(self.log_directory):
            return exports
            
        # Look for trade_log_* directories
        for item in os.listdir(self.log_directory):
            item_path = os.path.join(self.log_directory, item)
            
            # Check if it's a directory and matches our naming pattern
            if os.path.isdir(item_path) and item.startswith("trade_log_"):
                # Extract timestamp from directory name
                try:
                    timestamp_str = item.replace("trade_log_", "")
                    timestamp = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
                    
                    # Check for CSV and Excel files
                    csv_path = os.path.join(item_path, "trade_log.csv")
                    excel_path = os.path.join(item_path, "trade_log.xlsx")
                    
                    export_info = {
                        "timestamp": timestamp,
                        "directory": item_path,
                        "csv_exists": os.path.exists(csv_path),
                        "excel_exists": os.path.exists(excel_path),
                        "csv_path": csv_path if os.path.exists(csv_path) else None,
                        "excel_path": excel_path if os.path.exists(excel_path) else None
                    }
                    
                    exports.append(export_info)
                except (ValueError, IndexError):
                    # Skip directories that don't match our expected format
                    continue
                    
        # Sort by timestamp (newest first)
        exports.sort(key=lambda x: x["timestamp"], reverse=True)
        return exports
