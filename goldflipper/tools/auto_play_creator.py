import os
import json
import random
from datetime import datetime, timedelta
import yfinance as yf
import sys

# Add the project root to the Python path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(project_root)

from goldflipper.config.config import config
from goldflipper.utils.display import TerminalDisplay as display
import logging

class AutoPlayCreator:
    def __init__(self):
        """Initialize the AutoPlayCreator with configuration settings."""
        if not config._config:
            raise ValueError("Configuration not loaded. Please ensure config.py is properly initialized.")
            
        self.settings = config._config.get('auto_play_creator')
        if not self.settings:
            raise ValueError("Auto Play Creator settings not found in configuration")
        
        if not self.settings.get('enabled', False):
            raise ValueError("Auto Play Creator is disabled in settings")
            
        self.test_symbols = self.settings.get('test_symbols', ['SPY'])
        self.entry_buffer = self.settings.get('entry_buffer', 0.01)
        self.expiration_days = self.settings.get('expiration_days', 7)
        self.take_profit_pct = self.settings.get('take_profit_pct', 1.0)
        self.stop_loss_pct = self.settings.get('stop_loss_pct', 0.5)
        
        # Add execution mode
        self.execution_mode = None  # Will be set later
        
    def get_market_data(self, symbol):
        """Fetch current market data for a symbol."""
        try:
            ticker = yf.Ticker(symbol)
            # First try to get the regular market price
            current_price = ticker.info.get('regularMarketPrice')
            
            # If that fails, try to get the current price from history
            if not current_price:
                hist = ticker.history(period='1d')
                if not hist.empty:
                    current_price = hist['Close'].iloc[-1]
            
            if not current_price:
                raise ValueError(f"Could not get price for {symbol}")
                
            # Get option chain for nearest expiration
            expiry = (datetime.now() + timedelta(days=self.expiration_days)).strftime('%Y-%m-%d')
            
            try:
                chain = ticker.option_chain(expiry)
            except Exception as e:
                # If exact expiry not found, get the nearest available expiration
                available_dates = ticker.options
                if not available_dates:
                    raise ValueError(f"No options available for {symbol}")
                
                # Find the nearest expiration date
                expiry = min(available_dates, key=lambda d: abs(datetime.strptime(d, '%Y-%m-%d') - 
                                                              (datetime.now() + timedelta(days=self.expiration_days))))
                chain = ticker.option_chain(expiry)
            
            return {
                'symbol': symbol,
                'price': current_price,
                'calls': chain.calls,
                'puts': chain.puts,
                'expiration': expiry
            }
        except Exception as e:
            logging.error(f"Error fetching market data for {symbol}: {str(e)}")
            return None
            
    def find_nearest_strike(self, options_data, current_price):
        """Find the nearest strike price to current price."""
        strikes = options_data['strike'].values
        return strikes[abs(strikes - current_price).argmin()]
        
    def create_play_data(self, market_data, trade_type='CALL'):
        """Create a single play based on market data."""
        current_price = market_data['price']
        options = market_data['calls'] if trade_type == 'CALL' else market_data['puts']
        strike = self.find_nearest_strike(options, current_price)
        
        # Set entry price based on execution mode
        if self.execution_mode == "pure_execution":
            entry_price = current_price
        else:  # simulate_real
            entry_price = current_price * (1 + random.uniform(-self.entry_buffer, self.entry_buffer))
        
        # Generate option contract symbol using the same format as play-creation-tool
        expiration_date = datetime.strptime(market_data['expiration'], '%Y-%m-%d')
        strike_tenths_cents = int(round(float(strike) * 1000))
        padded_strike = f"{strike_tenths_cents:08d}"
        option_type = "C" if trade_type == "CALL" else "P"
        option_symbol = f"{market_data['symbol']}{expiration_date.strftime('%y%m%d')}{option_type}{padded_strike}"
        
        logging.info(f"Generated option contract symbol: {option_symbol}")
        
        play = {
            "play_name": f"AUTO_{market_data['symbol']}_{trade_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "symbol": market_data['symbol'],
            "expiration_date": datetime.strptime(market_data['expiration'], '%Y-%m-%d').strftime('%m/%d/%Y'),
            "trade_type": trade_type,
            "strike_price": str(strike),
            "option_contract_symbol": option_symbol,
            "contracts": 1,
            "play_expiration_date": datetime.strptime(market_data['expiration'], '%Y-%m-%d').strftime('%m/%d/%Y'),
            "entry_point": {
                "stock_price": round(entry_price, 2),
                "order_type": random.choice(self.settings.get('order_types', ['market'])),
                "entry_premium": None  # Will be populated when order is placed
            },
            "take_profit": {
                "stock_price": round(entry_price * (1 + self.take_profit_pct/100), 2) if trade_type == 'CALL' 
                             else round(entry_price * (1 - self.take_profit_pct/100), 2),
                "premium_pct": self.take_profit_pct,
                "order_type": "market",
                "TP_option_prem": None
            },
            "stop_loss": {
                "SL_type": random.choice(self.settings.get('stop_loss_types', ['STOP'])),
                "stock_price": round(entry_price * (1 - self.stop_loss_pct/100), 2) if trade_type == 'CALL'
                             else round(entry_price * (1 + self.stop_loss_pct/100), 2),
                "premium_pct": self.stop_loss_pct,
                "order_type": "market",
                "SL_option_prem": None
            },
            "play_class": "SIMPLE",
            "strategy": "Option Swings",
            "creation_date": datetime.now().strftime('%Y-%m-%d'),
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
            "creator": "auto"
        }
        
        return play
        
    def save_play(self, play):
        """Save the play to the appropriate directory."""
        plays_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'plays', 'new')
        os.makedirs(plays_dir, exist_ok=True)
        
        filename = f"{play['play_name']}.json"
        filepath = os.path.join(plays_dir, filename)
        
        with open(filepath, 'w') as f:
            json.dump(play, f, indent=4)
            
        return filepath
        
    def create_test_plays(self, num_plays=1, mode="pure_execution"):
        """Create multiple test plays."""
        self.execution_mode = mode
        created_plays = []
        
        for _ in range(num_plays):
            # Select random symbol and trade type
            symbol = random.choice(self.test_symbols)
            trade_type = random.choice(['CALL', 'PUT']) if 'MIX' in self.settings.get('trade_types', []) \
                        else self.settings.get('trade_types', ['CALL'])[0]
            
            # Get market data
            market_data = self.get_market_data(symbol)
            if not market_data:
                continue
                
            # Create and save play
            try:
                play = self.create_play_data(market_data, trade_type)
                filepath = self.save_play(play)
                created_plays.append(filepath)
                display.success(f"Created play: {filepath}")
                logging.info(f"Created play: {filepath}")
            except Exception as e:
                display.error(f"Error creating play for {symbol}: {e}")
                logging.error(f"Error creating play for {symbol}: {e}")
                
        return created_plays

def main():
    """Main function to create test plays."""
    try:
        creator = AutoPlayCreator()
        
        # Present mode options
        print("\nSelect execution mode:")
        print("1. Pure Execution Testing (Entry at current market price)")
        print("2. Simulate Real Plays")
        
        while True:
            mode_choice = input("\nEnter your choice (1 or 2): ").strip()
            if mode_choice in ['1', '2']:
                break
            print("Invalid choice. Please enter 1 or 2.")
        
        mode = "pure_execution" if mode_choice == '1' else "simulate_real"
        
        while True:
            try:
                num_plays = int(input("\nEnter number of test plays to create: "))
                if num_plays > 0:
                    break
                print("Please enter a positive number.")
            except ValueError:
                print("Please enter a valid number.")
        
        created_plays = creator.create_test_plays(num_plays, mode)
        
        display.info(f"\nCreated {len(created_plays)} test plays in {mode} mode:")
        for play in created_plays:
            display.info(f"- {play}")
            
    except Exception as e:
        display.error(f"Error in auto play creation: {e}")
        logging.error(f"Error in auto play creation: {e}")

if __name__ == "__main__":
    main()
