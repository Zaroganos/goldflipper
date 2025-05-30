from datetime import datetime
import pandas as pd
import os
import json
import shutil
from typing import List, Dict, Any
import logging

class PlayLogger:
    def __init__(self, base_directory=None, save_to_desktop=True):
        if base_directory is None:
            # Get the project root directory
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            self.base_directory = os.path.join(project_root, "goldflipper", "plays")
        else:
            self.base_directory = base_directory
        
        # Main log directory
        self.log_directory = os.path.join(os.path.dirname(__file__), "logs")
        
        # Create log directory if it doesn't exist
        if not os.path.exists(self.log_directory):
            os.makedirs(self.log_directory)
        
        # Current working log file
        self.csv_path = os.path.join(self.log_directory, "trade_log.csv")
        
        # Save to desktop option
        self.save_to_desktop = save_to_desktop
            
        # Initialize or load existing CSV
        if not os.path.exists(self.csv_path):
            self._create_empty_log()
    
    def _create_empty_log(self):
        """Initialize empty CSV with columns"""
        columns = [
            'play_name', 'symbol', 'trade_type', 'strike_price',
            'expiration_date', 'contracts',
            'date_atOpen', 'time_atOpen',  # Split datetime_atOpen
            'date_atClose', 'time_atClose',  # Split datetime_atClose
            'price_atOpen', 'price_atClose',
            'premium_atOpen', 'premium_atClose',
            'delta_atOpen', 'theta_atOpen',
            'close_type', 'close_condition',
            'profit_loss_pct', 'profit_loss',
            'status'
        ]
        df = pd.DataFrame(columns=columns)
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
        imported_count = 0
        
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
                            self.log_play(play_data, status)
                            imported_count += 1
                    except Exception as e:
                        print(f"Error processing {file_path}: {str(e)}")
        
        print(f"Total plays imported: {imported_count}")
        return imported_count
    
    def log_play(self, play_data: Dict[str, Any], status: str):
        """Log a single play to CSV"""
        logging_data = play_data.get('logging', {})
        
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
        
        # Get premium values, checking both direct and nested locations
        premium_open = logging_data.get('premium_atOpen')
        premium_close = logging_data.get('premium_atClose')
        
        # If not in logging_data, check if they're directly in play_data
        if premium_open is None and 'premium_atOpen' in play_data:
            premium_open = play_data['premium_atOpen']
        if premium_close is None and 'premium_atClose' in play_data:
            premium_close = play_data['premium_atClose']
            
        # Calculate profit/loss percentage
        pl_pct = 0.0
        if premium_open and premium_close and premium_open != 0:
            pl_pct = ((premium_close - premium_open) / abs(premium_open)) * 100
            
        # Calculate absolute profit/loss
        pl_dollars = self._calculate_pl(play_data)

        play_entry = {
            'play_name': play_data['play_name'],
            'symbol': play_data['symbol'],
            'trade_type': play_data['trade_type'],
            'strike_price': float(play_data['strike_price']),
            'expiration_date': play_data['expiration_date'],
            'contracts': play_data['contracts'],
            'date_atOpen': date_open,
            'time_atOpen': time_open,
            'date_atClose': date_close,
            'time_atClose': time_close,
            'price_atOpen': logging_data.get('price_atOpen'),
            'price_atClose': logging_data.get('price_atClose'),
            'premium_atOpen': premium_open,
            'premium_atClose': premium_close,
            'delta_atOpen': logging_data.get('delta_atOpen'),
            'theta_atOpen': logging_data.get('theta_atOpen'),
            'close_type': logging_data.get('close_type'),
            'close_condition': logging_data.get('close_condition'),
            'profit_loss_pct': pl_pct,
            'profit_loss': pl_dollars,
            'status': status
        }
        
        # Update dtypes
        dtypes = {
            'play_name': str,
            'symbol': str,
            'trade_type': str,
            'strike_price': float,
            'expiration_date': str,
            'contracts': int,
            'date_atOpen': str,
            'time_atOpen': str,
            'date_atClose': str,
            'time_atClose': str,
            'price_atOpen': float,
            'price_atClose': float,
            'premium_atOpen': float,
            'premium_atClose': float,
            'delta_atOpen': float,
            'theta_atOpen': float,
            'close_type': str,
            'close_condition': str,
            'profit_loss_pct': float,
            'profit_loss': float,
            'status': str
        }
        
        # Read existing DataFrame and set dtypes
        df = pd.read_csv(self.csv_path).astype(dtypes)
        
        # Create new DataFrame with explicit dtypes
        new_entry = pd.DataFrame([play_entry], dtype=object).astype(dtypes)
        
        # Concatenate with existing DataFrame
        df = pd.concat([df, new_entry], ignore_index=True)
        df.to_csv(self.csv_path, index=False)
    
    def _calculate_pl(self, play_data: Dict[str, Any]) -> float:
        """Calculate profit/loss in dollars"""
        # First check if the data is in the new format (direct in play_data)
        if 'premium_atOpen' in play_data and 'premium_atClose' in play_data:
            premium_open = play_data['premium_atOpen']
            premium_close = play_data['premium_atClose']
            contracts = play_data['contracts']
            
            if premium_open is not None and premium_close is not None and contracts is not None:
                return (premium_close - premium_open) * contracts * 100
        
        # Then check if it's in the old format (nested in logging)
        logging_data = play_data.get('logging', {})
        if logging_data.get('premium_atOpen') is not None and logging_data.get('premium_atClose') is not None:
            premium_open = logging_data['premium_atOpen']
            premium_close = logging_data['premium_atClose']
            contracts = play_data['contracts']
            
            if premium_open is not None and premium_close is not None and contracts is not None:
                return (premium_close - premium_open) * contracts * 100
                
        return 0.0

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
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # Define friendly column names mapping
        column_mapping = {
            'play_name': 'Play Name',
            'symbol': 'Symbol',
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

    def _create_summary_stats(self) -> pd.DataFrame:
        """Create summary statistics from the trade log"""
        try:
            df = pd.read_csv(self.csv_path)
            
            # Calculate basic statistics
            total_trades = int(len(df))
            winning_trades = int(len(df[df['profit_loss'] > 0]))
            win_rate = float(winning_trades / total_trades * 100) if total_trades > 0 else 0.0
            total_pl = float(df['profit_loss'].sum())
            
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
