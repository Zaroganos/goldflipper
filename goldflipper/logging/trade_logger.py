from datetime import datetime
import pandas as pd
import os
import json
from typing import List, Dict, Any
import logging

class PlayLogger:
    def __init__(self, base_directory=None):
        if base_directory is None:
            # Get the project root directory
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            self.base_directory = os.path.join(project_root, "goldflipper", "plays")
        else:
            self.base_directory = base_directory
        
        self.log_directory = os.path.join(os.path.dirname(__file__), "logs")
        self.csv_path = os.path.join(self.log_directory, "trade_log.csv")
        
        # Create log directory if it doesn't exist
        if not os.path.exists(self.log_directory):
            os.makedirs(self.log_directory)
            
        # Initialize or load existing CSV
        if not os.path.exists(self.csv_path):
            self._create_empty_log()
    
    def _create_empty_log(self):
        """Initialize empty CSV with columns"""
        columns = [
            'play_name', 'symbol', 'trade_type', 'strike_price',
            'expiration_date', 'contracts', 'entry_stock_price',
            'datetime_atOpen', 'datetime_atClose', 'price_atOpen', 'price_atClose',
            'premium_atClose', 'delta_atOpen', 'theta_atOpen',
            'close_type', 'close_condition', 'profit_loss', 'status'
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
        entry_point = play_data.get('entry_point', {})
        
        play_entry = {
            'play_name': play_data['play_name'],
            'symbol': play_data['symbol'],
            'trade_type': play_data['trade_type'],
            'strike_price': float(play_data['strike_price']),
            'expiration_date': play_data['expiration_date'],
            'contracts': play_data['contracts'],
            'entry_stock_price': entry_point.get('entry_stock_price'),
            'datetime_atOpen': logging_data.get('datetime_atOpen'),
            'datetime_atClose': logging_data.get('datetime_atClose'),
            'price_atOpen': logging_data.get('price_atOpen'),
            'price_atClose': logging_data.get('price_atClose'),
            'premium_atClose': logging_data.get('premium_atClose'),
            'delta_atOpen': logging_data.get('delta_atOpen'),
            'theta_atOpen': logging_data.get('theta_atOpen'),
            'close_type': logging_data.get('close_type'),
            'close_condition': logging_data.get('close_condition'),
            'profit_loss': self._calculate_pl(play_data),
            'status': status
        }
        
        # Append to DataFrame and save
        df = pd.read_csv(self.csv_path)
        df = pd.concat([df, pd.DataFrame([play_entry])], ignore_index=True)
        df.to_csv(self.csv_path, index=False)
    
    def _calculate_pl(self, play_data: Dict[str, Any]) -> float:
        """Calculate profit/loss for the play"""
        logging_data = play_data.get('logging', {})
        if logging_data.get('premium_atClose') and logging_data.get('price_atOpen'):
            return (logging_data['premium_atClose'] - logging_data['price_atOpen']) * play_data['contracts'] * 100
        return 0.0

    def export_to_spreadsheet(self, format='csv'):
        """Export logs to spreadsheet format"""
        if format == 'csv':
            return self.csv_path
        elif format == 'excel':
            excel_path = os.path.join(self.log_directory, "trade_log.xlsx")
            df = pd.read_csv(self.csv_path)
            
            # Create Excel writer object with xlsxwriter engine
            with pd.ExcelWriter(excel_path, engine='xlsxwriter') as writer:
                df.to_excel(writer, index=False, sheet_name='Trade Log')
                
                # Get the xlsxwriter workbook and worksheet objects
                workbook = writer.book
                worksheet = writer.sheets['Trade Log']
                
                # Set column widths
                for i, col in enumerate(df.columns):
                    # Get maximum length of column content
                    max_length = max(
                        df[col].astype(str).apply(len).max(),  # max length of values
                        len(str(col))  # length of column name
                    ) + 2  # add a little extra space
                    
                    # Set column width (max 50 characters)
                    worksheet.set_column(i, i, min(max_length, 50))
            
            return excel_path

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
