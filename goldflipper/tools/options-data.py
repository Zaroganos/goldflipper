import os
import sys

# Get the absolute path to the project root directory
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
# Add the project root to Python path
sys.path.insert(0, project_root)

import yfinance as yf
import logging
from datetime import datetime
import pandas as pd
import json
import time
from goldflipper.utils.display import TerminalDisplay as display

def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

def load_plays(status=None):
    """
    Load plays from NEW and OPEN folders.
    
    Args:
        status (str, optional): 'new' or 'open' to filter plays. None for both.
    """
    plays = []
    base_path = os.path.join(os.path.dirname(__file__), '..', 'plays')
    folders = ['new', 'open'] if status is None else [status.lower()]
    
    for folder in folders:
        folder_path = os.path.join(base_path, folder)
        if os.path.exists(folder_path):
            for filename in os.listdir(folder_path):
                if filename.endswith('.json'):
                    filepath = os.path.join(folder_path, folder, filename)
                    try:
                        with open(filepath, 'r') as f:
                            play_data = json.load(f)
                            play_data['status'] = folder
                            play_data['filename'] = filename
                            plays.append(play_data)
                    except Exception as e:
                        display.error(f"Error loading play {filename}: {e}")
                        logging.error(f"Error loading play {filename}: {e}")
    
    return plays

def get_option_data(ticker, expiration_date, strike_price, option_type, max_retries=3):
    """
    Fetch option data with retry logic.
    """
    for attempt in range(max_retries):
        try:
            if attempt > 0:
                time.sleep(2)
                
            stock = yf.Ticker(ticker)
            chain = stock.option_chain(expiration_date)
            
            options_data = chain.calls if option_type.lower() == 'call' else chain.puts
            current_price = stock.info.get('regularMarketPrice')
            
            # Filter for specific strike
            option = options_data[options_data['strike'] == float(strike_price)]
            
            if not option.empty:
                return {
                    'current_stock_price': current_price,
                    'bid': option.iloc[0]['bid'],
                    'ask': option.iloc[0]['ask'],
                    'last_price': option.iloc[0]['lastPrice'],
                    'volume': option.iloc[0]['volume'],
                    'open_interest': option.iloc[0]['openInterest'],
                    'implied_volatility': option.iloc[0]['impliedVolatility']
                }
            
            logging.warning(f"No option found for {ticker} at strike {strike_price}")
            display.error(f"No option found for {ticker} at strike {strike_price}")
            return None
            
        except Exception as e:
            logging.error(f"Attempt {attempt + 1}/{max_retries} failed: {e}")
            display.error(f"Attempt {attempt + 1}/{max_retries} failed: {e}")
            if attempt == max_retries - 1:
                return None

def calculate_option_levels(option_data, play):
    """
    Calculate entry, TP, and SL levels based on option premium.
    """
    if not option_data:
        return None
        
    # Calculate mid price as theoretical entry
    entry_price = (option_data['bid'] + option_data['ask']) / 2
    
    # Get TP/SL percentages from play or use defaults
    tp_percent = float(play.get('tp_percent', 0.5))  # 50% profit default
    sl_percent = float(play.get('sl_percent', 0.25))  # 25% loss default
    
    return {
        'entry_price': entry_price,
        'tp_price': entry_price * (1 + tp_percent),
        'sl_price': entry_price * (1 - sl_percent),
        'current_premium': entry_price
    }

def analyze_play(play):
    """
    Analyze a single play and return relevant data.
    """
    try:
        # Convert date format
        expiration_date = datetime.strptime(
            play['expiration_date'], 
            '%m/%d/%Y'
        ).strftime('%Y-%m-%d')
        
        # Get option data
        option_data = get_option_data(
            ticker=play['symbol'],
            expiration_date=expiration_date,
            strike_price=float(play['strike_price']),
            option_type=play['trade_type']
        )
        
        if not option_data:
            return None
            
        # Calculate levels
        levels = calculate_option_levels(option_data, play)
        
        return {
            'play_id': play['filename'],
            'status': play['status'],
            'symbol': play['symbol'],
            'option_data': option_data,
            'levels': levels,
            'analysis_time': datetime.now().isoformat()
        }
        
    except Exception as e:
        logging.error(f"Error analyzing play {play.get('filename', 'unknown')}: {e}")
        display.error(f"Error analyzing play {play.get('filename', 'unknown')}: {e}")
        return None

def main():
    setup_logging()
    logging.info("Starting options data analysis...")
    
    # Load all active plays
    plays = load_plays()
    
    if not plays:
        logging.info("No plays found to analyze")
        return
        
    results = []
    for play in plays:
        analysis = analyze_play(play)
        if analysis:
            results.append(analysis)
            
            # Log detailed information
            logging.info(f"\nAnalysis for {play['symbol']} {play['trade_type']}:")
            display.info(f"\nAnalysis for {play['symbol']} {play['trade_type']}:")
            logging.info(f"Current Stock Price: ${analysis['option_data']['current_stock_price']:.2f}")
            display.info(f"Current Stock Price: ${analysis['option_data']['current_stock_price']:.2f}")
            logging.info(f"Option Premium: ${analysis['levels']['current_premium']:.2f}")
            display.info(f"Option Premium: ${analysis['levels']['current_premium']:.2f}")
            logging.info(f"Entry: ${analysis['levels']['entry_price']:.2f}")
            display.info(f"Entry: ${analysis['levels']['entry_price']:.2f}")
            logging.info(f"TP: ${analysis['levels']['tp_price']:.2f}")
            display.info(f"TP: ${analysis['levels']['tp_price']:.2f}")
            logging.info(f"SL: ${analysis['levels']['sl_price']:.2f}")
            display.info(f"SL: ${analysis['levels']['sl_price']:.2f}")
    
    logging.info(f"Analysis completed for {len(results)} plays")
    display.info(f"Analysis completed for {len(results)} plays")
    return results

if __name__ == "__main__":
    main()
