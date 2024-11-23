import yfinance as yf
import logging
from datetime import datetime
import pandas as pd
import os
import json

pd.set_option('display.max_rows', None)

def display_options_chain(chain_data):
    """Display formatted options chain data."""
    relevant_cols = ['strike', 'lastPrice', 'bid', 'ask', 'volume', 'impliedVolatility']
    print("\nOptions Chain:")
    print(chain_data[relevant_cols].to_string(index=False))

def get_user_input():
    """Get user input for option parameters."""
    ticker = input("Enter ticker symbol (e.g. SPY): ").upper()
    stock = yf.Ticker(ticker)
    
    # Show available expiration dates
    print("\nAvailable expiration dates:")
    for i, date in enumerate(stock.options, 1):
        print(f"{i}. {date}")
    
    date_choice = int(input("\nSelect expiration date number: ")) - 1
    selected_date = stock.options[date_choice]
    
    # Get option type
    option_type = input("\nEnter option type (call/put): ").lower()
    while option_type not in ['call', 'put']:
        option_type = input("Invalid! Enter 'call' or 'put': ").lower()
        
    return ticker, selected_date, option_type

def get_option_premium_data(ticker, expiration_date=None, strike_price=None, option_type='call'):
    """
    Fetch option premium data for a specific option contract.
    
    Parameters:
    - ticker (str): Stock symbol
    - expiration_date (str, optional): Option expiration date in 'YYYY-MM-DD' format
    - strike_price (float, optional): Strike price of the option
    - option_type (str): 'call' or 'put', defaults to 'call'
    
    Returns:
    - dict: Option premium data including bid, ask, last price and volume
           Returns None if data unavailable
    """
    logging.info(f"Fetching option premium data for {ticker}...")
    
    try:
        stock = yf.Ticker(ticker)
        
        # Get available expiration dates
        available_dates = stock.options
        if not available_dates:
            logging.error(f"No option data available for {ticker}")
            return None
            
        # Use provided expiration date or default to nearest
        target_date = expiration_date if expiration_date in available_dates else available_dates[0]
        
        # Get option chain
        chain = stock.option_chain(target_date)
        
        # Select calls or puts
        options_data = chain.calls if option_type.lower() == 'call' else chain.puts
        
        # Filter by strike price if provided
        if strike_price:
            options_data = options_data[options_data['strike'] == float(strike_price)]
            
        if options_data.empty:
            logging.warning(f"No matching options found for {ticker} with given parameters")
            return None
            
        # Get first matching option
        option = options_data.iloc[0]
        
        premium_data = {
            'bid': option.bid,
            'ask': option.ask,
            'last_price': option.lastPrice,
            'volume': option.volume,
            'strike': option.strike,
            'expiration': target_date
        }
        
        logging.info(f"Option premium data fetched successfully for {ticker}")
        return premium_data
        
    except Exception as e:
        logging.error(f"Error fetching option premium data for {ticker}: {str(e)}")
        return None

def get_all_plays():
    """Get all plays from various play folders."""
    play_folders = ['new', 'open', 'temp']
    plays = []
    base_path = os.path.join(os.path.dirname(__file__), '..', 'plays')
    
    for folder in play_folders:
        folder_path = os.path.join(base_path, folder)
        if os.path.exists(folder_path):
            for filename in os.listdir(folder_path):
                if filename.endswith('.json'):
                    filepath = os.path.join(folder_path, filename)
                    with open(filepath, 'r') as f:
                        play_data = json.load(f)
                        plays.append({
                            'folder': folder,
                            'filename': filename,
                            'data': play_data
                        })
    return plays

def display_plays(plays):
    """Display available plays for selection."""
    print("\nAvailable Plays:")
    for i, play in enumerate(plays, 1):
        data = play['data']
        print(f"{i}. [{play['folder']}] {data['symbol']} {data['trade_type']} "
              f"${data['strike_price']} exp:{data['expiration_date']}")

def get_play_selection():
    """Get user input for play selection."""
    plays = get_all_plays()
    if not plays:
        print("No plays found")
        return None
        
    display_plays(plays)
    
    selection = input("\nSelect play number (or press Enter for manual input): ")
    if not selection:
        return None
        
    try:
        index = int(selection) - 1
        if 0 <= index < len(plays):
            return plays[index]
    except ValueError:
        pass
        
    print("Invalid selection, defaulting to manual input")
    return None

def main():
    """Main function to fetch and display option data."""
    play_data = get_play_selection()
    
    if play_data:
        # Extract data from selected play
        data = play_data['data']
        ticker = data['symbol']
        expiration_date = datetime.strptime(data['expiration_date'], '%m/%d/%Y').strftime('%Y-%m-%d')
        strike_price = float(data['strike_price'])
        option_type = data['trade_type'].lower()
    else:
        # Get manual input if no play selected
        ticker, expiration_date, option_type = get_user_input()
        strike_price = None

    try:
        # Fetch data
        stock = yf.Ticker(ticker)
        chain = stock.option_chain(expiration_date)
        
        # Get appropriate chain
        options_data = chain.calls if option_type == 'call' else chain.puts
        
        # Filter by strike if from play
        if strike_price:
            options_data = options_data[
                (options_data['strike'] >= strike_price - 1) & 
                (options_data['strike'] <= strike_price + 1)
            ]
        
        # Display chain
        display_options_chain(options_data)
            
    except Exception as e:
        logging.error(f"Error in main: {str(e)}")
        print(f"An error occurred: {str(e)}")

if __name__ == "__main__":
    main()