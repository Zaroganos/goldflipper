import os
import json
import random
from datetime import datetime, timedelta
import sys

# Add the project root to the Python path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(project_root)

from goldflipper.config.config import config
from goldflipper.utils.display import TerminalDisplay as display
from goldflipper.data.market.manager import MarketDataManager
import logging

class AutoPlayCreator:
    def __init__(self):
        """Initialize the AutoPlayCreator with configuration settings."""
        if not config._config:
            raise ValueError("Configuration not loaded. Please ensure config.py is properly initialized.")
            
        # Prefer safe accessor for config
        self.settings = config.get('auto_play_creator', default=None)
        if not self.settings:
            raise ValueError("Auto Play Creator settings not found in configuration")
        
        if not self.settings.get('enabled', False):
            raise ValueError("Auto Play Creator is disabled in settings")
            
        # Symbol pools
        self.test_symbols = self.settings.get('test_symbols', ['SPY'])
        self.watchlist_symbols = config.get('watchlist', default=[]) or []
        self.use_watchlist = self.settings.get('use_watchlist', True)

        self.entry_buffer = self.settings.get('entry_buffer', 0.01)
        self.expiration_days = self.settings.get('expiration_days', 7)
        self.take_profit_pct = self.settings.get('take_profit_pct', 1.0)
        self.stop_loss_pct = self.settings.get('stop_loss_pct', 0.5)

        # Simulate-real overrides (used when execution_mode is simulate_real or oco_peer_set)
        sim = self.settings.get('simulate_real', {}) or {}
        self.entry_buffer_sim = sim.get('entry_buffer', self.entry_buffer)
        self.take_profit_pct_sim = sim.get('take_profit_pct', self.take_profit_pct)
        self.stop_loss_pct_sim = sim.get('stop_loss_pct', self.stop_loss_pct)
        
        # Add execution mode
        self.execution_mode = None  # Will be set later
        
        # Validate stop loss types in settings
        valid_sl_types = ['STOP', 'LIMIT']  # We'll add 'CONTINGENCY' later when implemented
        configured_sl_types = self.settings.get('stop_loss_types', ['STOP'])
        invalid_types = [t for t in configured_sl_types if t not in valid_sl_types]
        if invalid_types:
            raise ValueError(f"Invalid stop loss types in settings: {invalid_types}. Valid types are: {valid_sl_types}")

        # Market data manager
        self.market_data = MarketDataManager()
        
    def get_market_data(self, symbol):
        """Fetch current market data (price and option chain) for a symbol via MarketDataManager."""
        try:
            # Price via manager (provider + cache + fallback)
            current_price = self.market_data.get_stock_price(symbol)
            if current_price is None:
                raise ValueError(f"Could not get price for {symbol}")

            # Target expiry window and available expirations
            target_dt = datetime.now() + timedelta(days=self.expiration_days)
            expirations = self.market_data.get_option_expirations(symbol) or []

            chosen_expiry = None
            if expirations:
                # Normalize to datetime and choose the nearest to target
                def to_dt(s):
                    try:
                        return datetime.strptime(str(s), '%Y-%m-%d')
                    except Exception:
                        return None
                dated = [(e, to_dt(e)) for e in expirations]
                valid = [t for t in dated if t[1] is not None]
                if valid:
                    chosen_expiry = min(valid, key=lambda t: abs(t[1] - target_dt))[0]

            # Build candidate expirations (chosen first, then others by closeness)
            def to_dt(s):
                try:
                    return datetime.strptime(str(s), '%Y-%m-%d')
                except Exception:
                    return None
            candidate_exps = []
            if chosen_expiry:
                candidate_exps.append(chosen_expiry)
            if expirations:
                remaining = [e for e in expirations if e != chosen_expiry]
                dated = [(e, to_dt(e)) for e in remaining]
                valid = [t for t in dated if t[1] is not None]
                candidate_exps.extend([e for e, _ in sorted(valid, key=lambda t: abs(t[1] - target_dt))])

            selected_calls = None
            selected_puts = None
            selected_expiration = None

            # Try each candidate expiration until any side has rows
            for exp in candidate_exps:
                try:
                    chain = self.market_data._try_providers('get_option_chain', symbol, exp)
                except Exception:
                    chain = None
                if not chain or chain.get('calls') is None or chain.get('puts') is None:
                    continue
                calls_df = chain['calls']
                puts_df = chain['puts']
                if (calls_df is not None and not calls_df.empty) or (puts_df is not None and not puts_df.empty):
                    selected_calls = calls_df
                    selected_puts = puts_df
                    selected_expiration = exp
                    break

            # Final fallback: unfiltered chain
            if selected_calls is None and selected_puts is None:
                try:
                    chain = self.market_data._try_providers('get_option_chain', symbol, None)
                except Exception:
                    chain = None
                if chain and chain.get('calls') is not None and chain.get('puts') is not None:
                    calls_df = chain['calls']
                    puts_df = chain['puts']
                    if (calls_df is not None and not calls_df.empty) or (puts_df is not None and not puts_df.empty):
                        selected_calls = calls_df
                        selected_puts = puts_df
                        selected_expiration = ''

            if selected_calls is None and selected_puts is None:
                raise ValueError(f"No options available for {symbol}")

            return {
                'symbol': symbol,
                'price': float(current_price),
                'calls': selected_calls,
                'puts': selected_puts,
                'expiration': selected_expiration or ''
            }
        except Exception as e:
            logging.error(f"Error fetching market data for {symbol}: {str(e)}")
            return None
            
    def find_nearest_strike(self, options_data, current_price):
        """Find the nearest strike price to current price."""
        if options_data is None or options_data.empty or 'strike' not in options_data.columns:
            raise ValueError("No option strikes available")
        strikes = options_data['strike'].values
        if len(strikes) == 0:
            raise ValueError("No option strikes available")
        return strikes[abs(strikes - current_price).argmin()]
        
    def get_enabled_tp_sl_types(self):
        """Get the enabled TP-SL types from settings."""
        return self.settings.get('TP-SL_types', ['PREMIUM_PCT'])

    def generate_tp_sl_values(self, entry_price, trade_type='CALL'):
        """Generate TP/SL values based on enabled types."""
        enabled_types = self.get_enabled_tp_sl_types()
        # Choose TP/SL pct based on mode
        sim_mode = self.execution_mode in ('simulate_real', 'oco_peer_set')
        tp_pct_val = self.take_profit_pct_sim if sim_mode else self.take_profit_pct
        sl_pct_val = self.stop_loss_pct_sim if sim_mode else self.stop_loss_pct
        # Randomly select how many types to use (at least 1, up to all enabled types)
        num_types = random.randint(1, len(enabled_types))
        selected_types = random.sample(enabled_types, num_types)
        
        tp_values = {
            'TP_option_prem': 0.0,  # Initialize with 0.0 instead of None
            'premium_pct': 0.0
        }
        sl_values = {
            'SL_option_prem': 0.0,  # Initialize with 0.0 instead of None
            'premium_pct': 0.0
        }
        
        for tp_type in selected_types:
            if tp_type == 'STOCK_PRICE':
                # Calculate actual price targets
                tp_values['stock_price'] = round(entry_price * (1 + tp_pct_val/100), 2) if trade_type == 'CALL' \
                                         else round(entry_price * (1 - tp_pct_val/100), 2)
                sl_values['stock_price'] = round(entry_price * (1 - sl_pct_val/100), 2) if trade_type == 'CALL' \
                                         else round(entry_price * (1 + sl_pct_val/100), 2)
            
            elif tp_type == 'PREMIUM_PCT':
                tp_values['premium_pct'] = tp_pct_val
                sl_values['premium_pct'] = sl_pct_val
            
            elif tp_type == 'STOCK_PRICE_PCT':
                # Set both percentage and calculated target prices
                tp_values['stock_price_pct'] = tp_pct_val
                sl_values['stock_price_pct'] = sl_pct_val
                
                # Calculate and set actual price targets
                tp_values['stock_price'] = round(entry_price * (1 + tp_pct_val/100), 2) if trade_type == 'CALL' \
                                         else round(entry_price * (1 - tp_pct_val/100), 2)
                sl_values['stock_price'] = round(entry_price * (1 - sl_pct_val/100), 2) if trade_type == 'CALL' \
                                         else round(entry_price * (1 + sl_pct_val/100), 2)
        
        return tp_values, sl_values

    def create_play_data(self, market_data, trade_type='CALL'):
        """Create a single play based on market data."""
        current_price = market_data['price']
        options = market_data['calls'] if trade_type == 'CALL' else market_data['puts']
        if options is None or options.empty:
            raise ValueError("No options data available for selected trade type")
        strike = self.find_nearest_strike(options, current_price)
        # Select the row matching the nearest strike (fallback guarded for empty already)
        nearest_idx = (options['strike'] - current_price).abs().idxmin()
        nearest_row = options.loc[nearest_idx]
        
        # Set entry price based on execution mode
        if self.execution_mode == "pure_execution":
            entry_price = current_price
        else:  # simulate_real
            # Treat oco_peer_set same as simulate_real for price jitter
            jitter = self.entry_buffer_sim if self.entry_buffer_sim is not None else self.entry_buffer
            entry_price = current_price * (1 + random.uniform(-jitter, jitter))
        
        # Generate TP/SL values based on enabled types
        tp_values, sl_values = self.generate_tp_sl_values(entry_price, trade_type)
        # Determine if this play should use simulate-real defaults for TP/SL fallbacks
        sim_mode = self.execution_mode in ('simulate_real', 'oco_peer_set')
        
        # Build a consistent OCC symbol and only use provider symbol if it matches the chosen side
        provider_symbol = nearest_row.get('symbol') or ''
        selected_exp_str = str(nearest_row.get('expiration') or market_data.get('expiration') or '')
        if not selected_exp_str:
            raise ValueError("Cannot determine expiration for option symbol construction")
        expiration_date = datetime.strptime(selected_exp_str, '%Y-%m-%d')
        strike_tenths_cents = int(round(float(strike) * 1000))
        padded_strike = f"{strike_tenths_cents:08d}"
        option_type = "C" if trade_type == "CALL" else "P"
        occ_symbol = f"{market_data['symbol']}{expiration_date.strftime('%y%m%d')}{option_type}{padded_strike}"

        def provider_symbol_matches_side(sym: str, side: str) -> bool:
            try:
                # OCC format places type at -9 position
                return (sym[-9] == 'C' and side == 'CALL') or (sym[-9] == 'P' and side == 'PUT')
            except Exception:
                return False

        option_symbol = provider_symbol if provider_symbol and provider_symbol_matches_side(provider_symbol, trade_type) else occ_symbol
        
        # Initialize entry point with non-null values
        raw_entry_type = random.choice(self.settings.get('order_types', ['market']))
        if raw_entry_type == 'market':
            selected_order_type = 'market'
        else:
            selected_order_type = random.choice([
                'limit at bid', 'limit at mid', 'limit at ask', 'limit at last'
            ])

        entry_point = {
            "stock_price": round(entry_price, 2),
            "order_type": selected_order_type,
            "entry_premium": 0.0
        }
        
        # Initialize take profit with non-null values
        take_profit = {
            **tp_values,  # Unpack all TP values
            "order_type": "market",
            "TP_option_prem": 0.0,  # Initialize with 0.0
            "premium_pct": tp_values.get('premium_pct', 0.0),  # Ensure premium_pct exists
            "stock_price": tp_values.get('stock_price', round(entry_price * (1 + ((self.take_profit_pct_sim if sim_mode else self.take_profit_pct)/100)), 2))
        }
        
        # Initialize stop loss with non-null values
        stop_loss = {
            **sl_values,  # Unpack all SL values
            "SL_type": random.choice(self.settings.get('stop_loss_types', ['STOP'])),
            "order_type": "market",  # Default to market, will be updated based on SL_type
            "SL_option_prem": 0.0,  # Initialize with 0.0
            "premium_pct": sl_values.get('premium_pct', 0.0),  # Ensure premium_pct exists
            "stock_price": sl_values.get('stock_price', round(entry_price * (1 - ((self.stop_loss_pct_sim if sim_mode else self.stop_loss_pct)/100)), 2))
        }
        
        # Update stop loss order type based on SL_type
        if stop_loss["SL_type"] == "STOP":
            stop_loss["order_type"] = "market"
        elif stop_loss["SL_type"] == "LIMIT":
            stop_loss["order_type"] = "limit"
        
        play = {
            "play_name": self.generate_play_name(option_symbol),
            "symbol": market_data['symbol'],
            "expiration_date": datetime.strptime(market_data['expiration'], '%Y-%m-%d').strftime('%m/%d/%Y'),
            "trade_type": trade_type,
            "strike_price": str(strike),
            "option_contract_symbol": option_symbol,
            "contracts": 1,
            "play_expiration_date": datetime.strptime(market_data['expiration'], '%Y-%m-%d').strftime('%m/%d/%Y'),
            "entry_point": entry_point,
            "take_profit": take_profit,
            "stop_loss": stop_loss,
            "play_class": "SIMPLE",
            "strategy": "Option Swings",
            "creation_date": datetime.now().strftime('%Y-%m-%d'),
            "status": {
                "play_status": "NEW",
                "order_id": "",  # Initialize with empty string instead of None
                "order_status": "",  # Initialize with empty string instead of None
                "position_exists": False,
                "last_checked": "",  # Initialize with empty string instead of None
                "closing_order_id": "",  # Initialize with empty string instead of None
                "closing_order_status": "",  # Initialize with empty string instead of None
                "contingency_order_id": "",  # Initialize with empty string instead of None
                "contingency_order_status": "",  # Initialize with empty string instead of None
                "conditionals_handled": False
            },
            "creator": "auto"
        }
        
        return play
        
    def save_play(self, play):
        """Save the play to the appropriate directory."""
        # Resolve directories from config for alignment
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        plays_root = config.get('file_paths', 'plays_dir', default='plays')
        new_dir = config.get('file_paths', 'new_dir', default='new')
        plays_dir = os.path.join(base_dir, plays_root, new_dir)
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
        
        attempts = 0
        max_attempts = num_plays * 10  # avoid infinite loops; generous retries
        symbols_pool = self.watchlist_symbols if (self.use_watchlist and self.watchlist_symbols) else self.test_symbols

        while len(created_plays) < num_plays and attempts < max_attempts:
            attempts += 1
            symbol = random.choice(symbols_pool)

            market_data = self.get_market_data(symbol)
            if not market_data:
                continue

            trade_types_cfg = self.settings.get('trade_types', ['CALL'])
            has_calls = market_data.get('calls') is not None and not market_data['calls'].empty
            has_puts = market_data.get('puts') is not None and not market_data['puts'].empty

            if 'MIX' in trade_types_cfg:
                available_sides = []
                if has_calls:
                    available_sides.append('CALL')
                if has_puts:
                    available_sides.append('PUT')
                if not available_sides:
                    logging.warning(f"No options available for {symbol}; retrying...")
                    continue
                trade_type = random.choice(available_sides)
            else:
                desired = trade_types_cfg[0]
                if desired == 'CALL' and not has_calls and has_puts:
                    trade_type = 'PUT'
                elif desired == 'PUT' and not has_puts and has_calls:
                    trade_type = 'CALL'
                elif (desired == 'CALL' and has_calls) or (desired == 'PUT' and has_puts):
                    trade_type = desired
                else:
                    logging.warning(f"Desired side {desired} unavailable for {symbol}; retrying...")
                    continue

            try:
                play = self.create_play_data(market_data, trade_type)
                filepath = self.save_play(play)
                created_plays.append(filepath)
                display.success(f"Created play: {filepath}")
                logging.info(f"Created play: {filepath}")
            except Exception as e:
                display.error(f"Error creating play for {symbol}: {e}")
                logging.error(f"Error creating play for {symbol}: {e}")
                
        # If OCO peer set mode, add mutual OCO relationships among the created plays
        if self.execution_mode == 'oco_peer_set' and len(created_plays) > 1:
            try:
                filenames = [os.path.basename(p) for p in created_plays]
                for path in created_plays:
                    try:
                        with open(path, 'r') as f:
                            play_data = json.load(f)
                        # Ensure conditional_plays structure exists
                        if 'conditional_plays' not in play_data or not isinstance(play_data['conditional_plays'], dict):
                            play_data['conditional_plays'] = {}
                        existing = play_data['conditional_plays'].get('OCO_triggers', []) or []
                        # Peers are all other filenames
                        own = os.path.basename(path)
                        peers = [fn for fn in filenames if fn != own]
                        # Merge unique
                        merged = list({*existing, *peers})
                        play_data['conditional_plays']['OCO_triggers'] = merged
                        # Save back
                        with open(path, 'w') as f:
                            json.dump(play_data, f, indent=4)
                    except Exception as e:
                        logging.error(f"Failed to set OCO peers for {path}: {e}")
                display.info(f"Linked {len(created_plays)} plays as an OCO peer set")
                logging.info(f"Linked OCO peer set: {[os.path.basename(p) for p in created_plays]}")
            except Exception as e:
                logging.error(f"Error linking OCO peer set: {e}")

        return created_plays

    def generate_play_name(self, option_symbol):
        """Generate a play name following the standard convention with auto prefix and random suffix."""
        import random
        import string
        
        # Generate random 3-digit string
        random_suffix = ''.join(random.choices(string.digits, k=3))
        
        # Get current timestamp in the same format as play_creation_tool
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Combine components: AUTO_symbol_timestamp_randomsuffix
        return f"AUTO_{option_symbol}_{timestamp}_{random_suffix}"

def main():
    """Main function to create test plays."""
    try:
        creator = AutoPlayCreator()
        
        # Present mode options
        print("\nSelect execution mode:")
        print("1. Pure Execution Testing (Entry at current market price)")
        print("2. Simulate Real Plays")
        print("3. OCO Peer Sets (simulate + mutual OCO across the set)")
        
        while True:
            mode_choice = input("\nEnter your choice (1, 2, or 3): ").strip()
            if mode_choice in ['1', '2', '3']:
                break
            print("Invalid choice. Please enter 1, 2, or 3.")
        
        if mode_choice == '1':
            mode = "pure_execution"
        elif mode_choice == '2':
            mode = "simulate_real"
        else:
            mode = "oco_peer_set"
        
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
