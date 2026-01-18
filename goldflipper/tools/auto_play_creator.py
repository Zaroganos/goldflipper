import os
import json
import random
import copy
from datetime import datetime, timedelta
import sys
from typing import Dict, Any, Optional, List, Tuple
from enum import Enum

# Add the project root to the Python path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) 
sys.path.append(project_root)

from goldflipper.config.config import config
from goldflipper.utils.display import TerminalDisplay as display
from goldflipper.utils.exe_utils import get_play_subdir
from goldflipper.data.market.manager import MarketDataManager
import logging


class StrategyType(Enum):
    """Available strategies for play creation."""
    OPTION_SWINGS = "option_swings"
    MOMENTUM = "momentum"
    SELL_PUTS = "sell_puts"
    # SPREADS = "spreads"  # Future support


class MomentumPlaybook(Enum):
    """Available playbooks for momentum strategy."""
    GAP_MOVE = "gap_move"           # Trade with the gap direction
    GAP_FADE = "gap_fade"           # Trade against the gap
    GOLDFLIPPER_GAP_MOVE = "goldflipper_gap_move"  # Goldflipper Gap Move: straddle + OI confirmation
    MANUAL = "manual"               # No auto-entry conditions


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
        
        # Strategy configuration
        self.current_strategy: StrategyType = StrategyType.OPTION_SWINGS
        self.current_playbook: Optional[MomentumPlaybook] = None
            
        # Symbol pools
        self.test_symbols = self.settings.get('test_symbols', ['SPY'])
        self.watchlist_symbols = config.get('watchlist', default=[]) or []
        self.use_watchlist = self.settings.get('use_watchlist', True)

        self.entry_buffer = float(self.settings.get('entry_buffer', 0.01))
        self.expiration_days = int(self.settings.get('expiration_days', 7))
        self.take_profit_pct = float(self.settings.get('take_profit_pct', 1.0))
        self.stop_loss_pct = float(self.settings.get('stop_loss_pct', 0.5))

        # Simulate-real overrides (used when execution_mode is simulate_real or oco_peer_set)
        sim = self.settings.get('simulate_real', {}) or {}
        self.entry_buffer_sim = float(sim.get('entry_buffer', self.entry_buffer))
        self.take_profit_pct_sim = float(sim.get('take_profit_pct', self.take_profit_pct))
        self.stop_loss_pct_sim = float(sim.get('stop_loss_pct', self.stop_loss_pct))
        
        # OCO peer set overrides (used only when execution_mode is oco_peer_set)
        oco = self.settings.get('oco_peer_set', {}) or {}
        self.entry_buffer_oco = float(oco['entry_buffer']) if oco.get('entry_buffer') is not None else None
        self.take_profit_pct_oco = float(oco['take_profit_pct']) if oco.get('take_profit_pct') is not None else None
        self.stop_loss_pct_oco = float(oco['stop_loss_pct']) if oco.get('stop_loss_pct') is not None else None
        
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
        
        # Load play templates
        self.templates_dir = os.path.join(
            os.path.dirname(__file__), 'templates'
        )
    
    # =========================================================================
    # Strategy Selection Methods
    # =========================================================================
    
    def set_strategy(self, strategy: StrategyType) -> None:
        """Set the active strategy for play creation."""
        self.current_strategy = strategy
        display.info(f"Strategy set to: {strategy.value}")
    
    def set_playbook(self, playbook: MomentumPlaybook) -> None:
        """Set the playbook for momentum strategy."""
        self.current_playbook = playbook
        display.info(f"Playbook set to: {playbook.value}")
    
    def get_strategy_display_name(self, strategy: StrategyType) -> str:
        """Get human-readable strategy name."""
        names = {
            StrategyType.OPTION_SWINGS: "Option Swings (BTO/STC)",
            StrategyType.MOMENTUM: "Momentum/Gap (BTO/STC)",
            StrategyType.SELL_PUTS: "Short Puts (STO/BTC)"
        }
        return names.get(strategy, strategy.value)
    
    def get_playbook_display_name(self, playbook: MomentumPlaybook) -> str:
        """Get human-readable playbook name."""
        names = {
            MomentumPlaybook.GAP_MOVE: "Gap Move (trade with gap)",
            MomentumPlaybook.GAP_FADE: "Gap Fade (trade against gap)",
            MomentumPlaybook.GOLDFLIPPER_GAP_MOVE: "⭐ Goldflipper Gap Move (straddle + OI)",
            MomentumPlaybook.MANUAL: "Manual Entry"
        }
        return names.get(playbook, playbook.value)
    
    # =========================================================================
    # Gap Analysis Methods
    # =========================================================================
    
    def calculate_gap_info(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Calculate gap information for a symbol using market data.
        
        Detects pre-market gap by comparing previous close to current price.
        
        Returns:
            Dict with gap_type, gap_pct, previous_close, gap_open, or None if unavailable
        """
        try:
            # Get current price
            current_price = self.market_data.get_stock_price(symbol)
            if current_price is None:
                display.warning(f"Could not get current price for {symbol}")
                return None
            
            # Get previous close from historical data
            previous_close = self._get_previous_close(symbol)
            if previous_close is None:
                display.warning(f"Could not get previous close for {symbol}")
                return None
            
            # Calculate gap - ensure both values are floats
            current_price = float(current_price)
            previous_close = float(previous_close)
            gap_amount = current_price - previous_close
            gap_pct = (gap_amount / previous_close) * 100
            
            if gap_pct > 0:
                gap_type = "up"
            elif gap_pct < 0:
                gap_type = "down"
            else:
                gap_type = "flat"
            
            return {
                'gap_type': gap_type,
                'gap_pct': round(gap_pct, 2),
                'previous_close': round(previous_close, 2),
                'gap_open': round(float(current_price), 2),
                'trade_direction': None,  # Set based on playbook
                'confirmation_time': None
            }
            
        except Exception as e:
            logging.error(f"Error calculating gap info for {symbol}: {e}")
            return None
    
    def _get_previous_close(self, symbol: str) -> Optional[float]:
        """Get previous day's closing price using MarketDataManager."""
        try:
            # Use the unified MarketDataManager's get_previous_close method
            return self.market_data.get_previous_close(symbol)
        except Exception as e:
            logging.debug(f"Error getting previous close: {e}")
            return None
    
    def get_trade_type_for_gap(
        self, 
        gap_type: str, 
        trade_direction: str
    ) -> str:
        """
        Determine option type (CALL/PUT) based on gap and direction.
        
        Args:
            gap_type: "up" or "down"
            trade_direction: "with_gap" or "fade_gap"
        
        Returns:
            "CALL" or "PUT"
        """
        if trade_direction == "with_gap":
            # Trade with the gap direction
            return "CALL" if gap_type == "up" else "PUT"
        else:  # fade_gap
            # Trade against the gap direction
            return "PUT" if gap_type == "up" else "CALL"
    
    def calculate_goldflipper_gap_data(
        self,
        symbol: str,
        current_price: float,
        calls_df,
        puts_df
    ) -> Dict[str, Any]:
        """
        Calculate Goldflipper Gap Move-specific data: ATM straddle price and open interest.
        
        Args:
            symbol: Stock symbol
            current_price: Current stock price
            calls_df: DataFrame of call options
            puts_df: DataFrame of put options
            
        Returns:
            Dict with straddle_price, call_open_interest, put_open_interest
        """
        result = {
            "straddle_price": None,
            "stock_price_at_detection": current_price,
            "call_open_interest": None,
            "put_open_interest": None,
            "atm_strike": None
        }
        
        try:
            if calls_df is None or puts_df is None:
                return result
            if calls_df.empty or puts_df.empty:
                return result
            
            # Find ATM strike (closest to current price)
            call_strikes = calls_df['strike'].values
            atm_strike = min(call_strikes, key=lambda x: abs(x - current_price))
            result["atm_strike"] = atm_strike
            
            # Get ATM call data
            atm_call = calls_df[calls_df['strike'] == atm_strike]
            if not atm_call.empty:
                atm_call_row = atm_call.iloc[0]
                call_bid = float(atm_call_row.get('bid', 0) or 0)
                call_ask = float(atm_call_row.get('ask', 0) or 0)
                call_mid = (call_bid + call_ask) / 2 if call_bid and call_ask else 0
                result["call_open_interest"] = int(atm_call_row.get('openInterest', 0) or 0)
            else:
                call_mid = 0
            
            # Get ATM put data
            atm_put = puts_df[puts_df['strike'] == atm_strike]
            if not atm_put.empty:
                atm_put_row = atm_put.iloc[0]
                put_bid = float(atm_put_row.get('bid', 0) or 0)
                put_ask = float(atm_put_row.get('ask', 0) or 0)
                put_mid = (put_bid + put_ask) / 2 if put_bid and put_ask else 0
                result["put_open_interest"] = int(atm_put_row.get('openInterest', 0) or 0)
            else:
                put_mid = 0
            
            # Calculate straddle price (ATM call + ATM put)
            if call_mid > 0 and put_mid > 0:
                result["straddle_price"] = round(call_mid + put_mid, 2)
            
            logging.info(
                f"[{symbol}] Goldflipper Gap Move data: ATM strike={atm_strike}, "
                f"straddle=${result['straddle_price']}, "
                f"call_OI={result['call_open_interest']}, put_OI={result['put_open_interest']}"
            )
            
        except Exception as e:
            logging.warning(f"Error calculating Goldflipper Gap Move data for {symbol}: {e}")
        
        return result
    
    # =========================================================================
    # Template Loading
    # =========================================================================
    
    def load_play_template(self, strategy: StrategyType) -> Dict[str, Any]:
        """Load the JSON play template for a strategy."""
        template_map = {
            StrategyType.OPTION_SWINGS: "play_template_option_swings.json",
            StrategyType.MOMENTUM: "play_template_momentum.json",
            StrategyType.SELL_PUTS: "play_template_sell_puts.json"
        }
        
        template_file = template_map.get(strategy)
        if not template_file:
            raise ValueError(f"No template for strategy: {strategy}")
        
        template_path = os.path.join(self.templates_dir, template_file)
        
        if not os.path.exists(template_path):
            raise FileNotFoundError(f"Template not found: {template_path}")
        
        with open(template_path, 'r') as f:
            template = json.load(f)
        
        # Remove template info section
        template.pop('_template_info', None)
        
        return template
        
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
        # Choose TP/SL pct based on mode (oco-specific overrides > simulate_real > base)
        sim_mode = self.execution_mode in ('simulate_real', 'oco_peer_set')
        oco_mode = self.execution_mode == 'oco_peer_set'
        if oco_mode and self.take_profit_pct_oco is not None:
            tp_pct_val = self.take_profit_pct_oco
        elif sim_mode:
            tp_pct_val = self.take_profit_pct_sim
        else:
            tp_pct_val = self.take_profit_pct

        if oco_mode and self.stop_loss_pct_oco is not None:
            sl_pct_val = self.stop_loss_pct_oco
        elif sim_mode:
            sl_pct_val = self.stop_loss_pct_sim
        else:
            sl_pct_val = self.stop_loss_pct
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
        """
        Create a single play based on market data and current strategy.
        
        Routes to strategy-specific creation method.
        """
        if self.current_strategy == StrategyType.OPTION_SWINGS:
            return self._create_option_swings_play(market_data, trade_type)
        elif self.current_strategy == StrategyType.MOMENTUM:
            return self._create_momentum_play(market_data, trade_type)
        elif self.current_strategy == StrategyType.SELL_PUTS:
            return self._create_sell_puts_play(market_data, trade_type)
        else:
            raise ValueError(f"Unsupported strategy: {self.current_strategy}")
    
    def _create_option_swings_play(self, market_data, trade_type='CALL'):
        """Create an Option Swings play (original logic)."""
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
        else:
            # For oco_peer_set, prefer oco-specific jitter; otherwise use simulate_real override; fallback to base
            if self.execution_mode == 'oco_peer_set' and self.entry_buffer_oco is not None:
                jitter: float = self.entry_buffer_oco
            else:
                jitter = self.entry_buffer_sim
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
        # All buy (entry) orders should be at the bid
        selected_order_type = 'limit at bid'

        entry_point = {
            "stock_price": round(entry_price, 2),
            "order_type": selected_order_type,
            "entry_premium": 0.0
        }
        
        # Initialize take profit with non-null values
        take_profit = {
            **tp_values,  # Unpack all TP values
            # All sell (TP) orders should be limit at mid
            "order_type": "limit at mid",
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
            stop_loss["order_type"] = "limit at mid"
        
        # Enforce explicit defaults: map any plain 'limit' to 'limit at mid'
        if isinstance(entry_point.get("order_type"), str) and entry_point["order_type"].strip().lower() == "limit":
            entry_point["order_type"] = "limit at mid"
        if isinstance(take_profit.get("order_type"), str) and take_profit["order_type"].strip().lower() == "limit":
            take_profit["order_type"] = "limit at mid"
        sl_ot = stop_loss.get("order_type")
        if isinstance(sl_ot, str) and sl_ot.strip().lower() == "limit":
            stop_loss["order_type"] = "limit at mid"
        elif isinstance(sl_ot, list) and len(sl_ot) >= 1 and isinstance(sl_ot[0], str) and sl_ot[0].strip().lower() == "limit":
            stop_loss["order_type"][0] = "limit at mid"
        
        play = {
            "play_name": self.generate_play_name(option_symbol),
            "symbol": market_data['symbol'],
            "expiration_date": datetime.strptime(market_data['expiration'], '%Y-%m-%d').strftime('%m/%d/%Y'),
            "trade_type": trade_type,
            "action": "BTO",  # Buy to Open for long positions
            "strike_price": str(strike),
            "option_contract_symbol": option_symbol,
            "contracts": 1,
            "play_expiration_date": datetime.strptime(market_data['expiration'], '%Y-%m-%d').strftime('%m/%d/%Y'),
            "entry_point": entry_point,
            "take_profit": take_profit,
            "stop_loss": stop_loss,
            "play_class": "SIMPLE",
            "strategy": "option_swings",
            "playbook": "default",
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
    
    def _create_momentum_play(self, market_data, trade_type='CALL'):
        """
        Create a Momentum/Gap play with gap_info populated.
        
        For gap plays, auto-detects gap and sets trade direction based on playbook.
        """
        symbol = market_data['symbol']
        current_price = market_data['price']
        options = market_data['calls'] if trade_type == 'CALL' else market_data['puts']
        
        if options is None or options.empty:
            raise ValueError("No options data available for selected trade type")
        
        strike = self.find_nearest_strike(options, current_price)
        nearest_idx = (options['strike'] - current_price).abs().idxmin()
        nearest_row = options.loc[nearest_idx]
        
        # Calculate gap info
        gap_info = self.calculate_gap_info(symbol)
        if gap_info is None:
            # Create default gap info if unavailable
            gap_info = {
                'gap_type': 'unknown',
                'gap_pct': 0.0,
                'previous_close': current_price,
                'gap_open': current_price,
                'trade_direction': 'manual',
                'confirmation_time': None
            }
        
        # Set trade direction based on playbook
        if self.current_playbook == MomentumPlaybook.GAP_MOVE:
            gap_info['trade_direction'] = 'with_gap'
        elif self.current_playbook == MomentumPlaybook.GOLDFLIPPER_GAP_MOVE:
            gap_info['trade_direction'] = 'with_gap'  # Goldflipper Gap Move also trades with gap
        elif self.current_playbook == MomentumPlaybook.GAP_FADE:
            gap_info['trade_direction'] = 'fade_gap'
        else:
            gap_info['trade_direction'] = 'manual'
        
        # Build option symbol
        selected_exp_str = str(nearest_row.get('expiration') or market_data.get('expiration') or '')
        expiration_date = datetime.strptime(selected_exp_str, '%Y-%m-%d')
        strike_tenths_cents = int(round(float(strike) * 1000))
        padded_strike = f"{strike_tenths_cents:08d}"
        option_type = "C" if trade_type == "CALL" else "P"
        option_symbol = f"{symbol}{expiration_date.strftime('%y%m%d')}{option_type}{padded_strike}"
        
        # Entry point
        entry_point = {
            "stock_price": round(current_price, 2),
            "order_type": "limit at ask",
            "entry_premium": 0.0,
            "entry_stock_price": round(current_price, 2),
            "target_delta": 0.55
        }
        
        # Take profit with trailing
        take_profit = {
            "TP_type": "Multiple",
            "premium_pct": self.take_profit_pct,
            "order_type": "limit at bid",
            "TP_option_prem": 0.0,
            "TP_levels": [
                {"pct": 25, "contracts_pct": 50},
                {"pct": 50, "contracts_pct": 100}
            ],
            "trailing_config": {
                "enabled": True,
                "trail_type": "percentage",
                "trail_distance_pct": 10.0,
                "activation_threshold_pct": 20.0,
                "update_frequency_seconds": 30
            },
            "trail_state": {
                "current_trail_level": None,
                "highest_favorable_price": None,
                "last_update_timestamp": None,
                "trail_activated": False
            },
            "trail_history": []
        }
        
        # Stop loss
        stop_loss = {
            "SL_type": "LIMIT",
            "premium_pct": self.stop_loss_pct,
            "order_type": "market",
            "SL_option_prem": 0.0,
            "trailing_config": {"enabled": False},
            "trail_state": {
                "current_trail_level": None,
                "highest_favorable_price": None,
                "last_update_timestamp": None,
                "breakeven_activated": False
            },
            "trail_history": []
        }
        
        # Time management
        if self.current_playbook == MomentumPlaybook.GOLDFLIPPER_GAP_MOVE:
            max_hold = 3  # Goldflipper Gap Move: shorter hold
        elif self.current_playbook == MomentumPlaybook.GAP_MOVE:
            max_hold = 5
        else:
            max_hold = 1  # Gap fade: same day
            
        time_management = {
            "same_day_exit": self.current_playbook == MomentumPlaybook.GAP_FADE,
            "max_hold_days": max_hold,
            "exit_before_close": True,
            "exit_minutes_before_close": 15
        }
        
        # Determine momentum type for config
        if self.current_playbook == MomentumPlaybook.GOLDFLIPPER_GAP_MOVE:
            momentum_type = "goldflipper_gap"
        elif self.current_playbook in (MomentumPlaybook.GAP_MOVE, MomentumPlaybook.GAP_FADE):
            momentum_type = "gap"
        else:
            momentum_type = "manual"
        
        # Build momentum config
        momentum_config = {
            "momentum_type": momentum_type,
            "wait_for_confirmation": True,
            "confirmation_period_minutes": 60 if self.current_playbook == MomentumPlaybook.GOLDFLIPPER_GAP_MOVE else 15,
            "lunch_break_restriction": True,
            "lunch_break_start_hour": 12,
            "lunch_break_start_minute": 0,
            "lunch_break_end_hour": 13,
            "lunch_break_end_minute": 0,
            "first_hour_restriction": self.current_playbook == MomentumPlaybook.GOLDFLIPPER_GAP_MOVE
        }
        
        # Add Goldflipper Gap Move-specific config
        if self.current_playbook == MomentumPlaybook.GOLDFLIPPER_GAP_MOVE:
            momentum_config["straddle_config"] = {
                "enabled": True,
                "min_gap_vs_straddle_ratio": 1.0
            }
            momentum_config["open_interest_config"] = {
                "enabled": True,
                "min_directional_oi": 500,
                "min_oi_ratio": 1.0
            }
        
        # Play name prefix
        play_prefix = "GFGM" if self.current_playbook == MomentumPlaybook.GOLDFLIPPER_GAP_MOVE else "GAP"
        
        play = {
            "play_name": self.generate_play_name(option_symbol, prefix=play_prefix),
            "symbol": symbol,
            "strategy": "momentum",
            "playbook": self.current_playbook.value if self.current_playbook else "manual",
            "expiration_date": expiration_date.strftime('%m/%d/%Y'),
            "trade_type": trade_type,
            "action": "BTO",
            "strike_price": str(strike),
            "option_contract_symbol": option_symbol,
            "contracts": 1,
            "play_expiration_date": expiration_date.strftime('%m/%d/%Y'),
            "entry_point": entry_point,
            "gap_info": gap_info,
            "momentum_config": momentum_config,
            "take_profit": take_profit,
            "stop_loss": stop_loss,
            "time_management": time_management,
            "play_class": "SIMPLE",
            "creation_date": datetime.now().strftime('%Y-%m-%d'),
            "conditional_plays": {
                "OCO_triggers": [],
                "OTO_triggers": []
            },
            "status": {
                "play_status": "NEW",
                "order_id": None,
                "position_uuid": None,
                "order_status": None,
                "position_exists": False,
                "closing_order_id": None,
                "closing_order_status": None,
                "contingency_order_id": None,
                "contingency_order_status": None,
                "conditionals_handled": False
            },
            "logging": {
                "delta_atOpen": 0.0,
                "theta_atOpen": 0.0,
                "datetime_atOpen": None,
                "price_atOpen": 0.0,
                "premium_atOpen": 0.0,
                "gap_filled_pct": None,
                "datetime_atClose": None,
                "price_atClose": 0.0,
                "premium_atClose": 0.0,
                "close_type": None,
                "close_condition": None,
                "hold_duration_hours": None
            },
            "creator": "auto"
        }
        
        # Add Goldflipper Gap Move-specific runtime data section with actual straddle/OI data
        if self.current_playbook == MomentumPlaybook.GOLDFLIPPER_GAP_MOVE:
            # Calculate actual straddle price and OI from option chain
            goldflipper_gap_data = self.calculate_goldflipper_gap_data(
                symbol=symbol,
                current_price=current_price,
                calls_df=market_data.get('calls'),
                puts_df=market_data.get('puts')
            )
            play["goldflipper_gap_info"] = goldflipper_gap_data
        
        return play
    
    def _create_sell_puts_play(self, market_data, trade_type='PUT'):
        """
        Create a Sell Puts (short premium) play.
        
        Uses STO/BTC order flow. Always creates PUT options.
        """
        symbol = market_data['symbol']
        current_price = market_data['price']
        options = market_data['puts']  # Always puts for this strategy
        
        if options is None or options.empty:
            raise ValueError("No puts data available for sell_puts strategy")
        
        # Find strike approximately 5-10% OTM (below current price)
        target_strike = current_price * 0.92  # ~8% OTM
        strike = self.find_nearest_strike(options, target_strike)
        nearest_idx = (options['strike'] - target_strike).abs().idxmin()
        nearest_row = options.loc[nearest_idx]
        
        # Build option symbol
        selected_exp_str = str(nearest_row.get('expiration') or market_data.get('expiration') or '')
        expiration_date = datetime.strptime(selected_exp_str, '%Y-%m-%d')
        strike_tenths_cents = int(round(float(strike) * 1000))
        padded_strike = f"{strike_tenths_cents:08d}"
        option_symbol = f"{symbol}{expiration_date.strftime('%y%m%d')}P{padded_strike}"
        
        # Calculate collateral required
        collateral = float(strike) * 100  # Per contract
        
        # Get premium estimate from option data
        entry_premium = nearest_row.get('bid', 0) or nearest_row.get('lastPrice', 0) or 0.50
        
        # Entry point for STO
        entry_point = {
            "stock_price": round(current_price, 2),
            "order_type": "limit at mid",
            "entry_premium": round(float(entry_premium), 2),
            "entry_stock_price": round(current_price, 2),
            "target_delta": 0.30,
            "target_dte": 45
        }
        
        # Take profit: buy back at 50% of credit received
        take_profit = {
            "TP_type": "Single",
            "premium_pct": 50.0,  # Close when premium drops 50%
            "order_type": "limit at mid",
            "TP_option_prem": 0.0,
            "trailing_config": {"enabled": False},
            "trail_state": {
                "current_trail_level": None,
                "highest_favorable_price": None,
                "last_update_timestamp": None,
                "trail_activated": False
            },
            "trail_history": []
        }
        
        # Stop loss: close if premium doubles (200% of original)
        stop_loss = {
            "SL_type": "LIMIT",
            "premium_pct": 200.0,  # Close if premium increases 200%
            "max_loss_multiple": 2.0,
            "order_type": "market",
            "SL_option_prem": 0.0,
            "trailing_config": {"enabled": False},
            "trail_state": {
                "current_trail_level": None,
                "highest_favorable_price": None,
                "last_update_timestamp": None,
                "breakeven_activated": False
            },
            "trail_history": []
        }
        
        # Position management
        management = {
            "close_at_dte": 21,  # Close at 21 DTE
            "roll_if_itm": True,
            "accept_assignment": False
        }
        
        # Collateral info
        collateral_info = {
            "required": True,
            "type": "cash",
            "amount": collateral,
            "calculated": True
        }
        
        play = {
            "play_name": self.generate_play_name(option_symbol, prefix="SP"),
            "symbol": symbol,
            "strategy": "sell_puts",
            "playbook": "default",
            "expiration_date": expiration_date.strftime('%m/%d/%Y'),
            "trade_type": "PUT",
            "action": "STO",  # Sell to Open
            "strike_price": str(strike),
            "option_contract_symbol": option_symbol,
            "contracts": 1,
            "play_expiration_date": expiration_date.strftime('%m/%d/%Y'),
            "entry_point": entry_point,
            "take_profit": take_profit,
            "stop_loss": stop_loss,
            "management": management,
            "collateral": collateral_info,
            "play_class": "SIMPLE",
            "creation_date": datetime.now().strftime('%Y-%m-%d'),
            "conditional_plays": {
                "OCO_triggers": [],
                "OTO_triggers": []
            },
            "status": {
                "play_status": "NEW",
                "order_id": None,
                "position_uuid": None,
                "order_status": None,
                "position_exists": False,
                "closing_order_id": None,
                "closing_order_status": None,
                "contingency_order_id": None,
                "contingency_order_status": None,
                "conditionals_handled": False
            },
            "logging": {
                "delta_atOpen": 0.0,
                "theta_atOpen": 0.0,
                "datetime_atOpen": None,
                "price_atOpen": 0.0,
                "premium_atOpen": 0.0,
                "credit_received": 0.0,
                "datetime_atClose": None,
                "price_atClose": 0.0,
                "premium_atClose": 0.0,
                "close_type": None,
                "close_condition": None,
                "profit_pct_of_max": None,
                "was_assigned": False
            },
            "creator": "auto"
        }
        
        return play
        
    def save_play(self, play):
        """Save the play to the appropriate directory (account-aware)."""
        # Use account-aware plays directory
        plays_dir = str(get_play_subdir('new'))
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

    def generate_play_name(self, option_symbol, prefix="AUTO"):
        """Generate a play name following the standard convention with prefix and random suffix."""
        import random
        import string
        
        # Generate random 3-digit string
        random_suffix = ''.join(random.choices(string.digits, k=3))
        
        # Get current timestamp in the same format as play_creation_tool
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Combine components: PREFIX_symbol_timestamp_randomsuffix
        return f"{prefix}_{option_symbol}_{timestamp}_{random_suffix}"

def select_strategy() -> StrategyType:
    """Interactive strategy selection."""
    print("\n" + "="*50)
    print("SELECT STRATEGY")
    print("="*50)
    print("1. Option Swings (BTO/STC) - Buy calls/puts, long premium")
    print("2. Momentum/Gap (BTO/STC) - Gap trading with auto-detection")
    print("3. Short Puts (STO/BTC) - Sell puts, collect premium")
    
    while True:
        choice = input("\nEnter strategy choice (1-3): ").strip()
        if choice == '1':
            return StrategyType.OPTION_SWINGS
        elif choice == '2':
            return StrategyType.MOMENTUM
        elif choice == '3':
            return StrategyType.SELL_PUTS
        print("Invalid choice. Please enter 1, 2, or 3.")


def select_momentum_playbook() -> MomentumPlaybook:
    """Interactive playbook selection for momentum strategy."""
    print("\n" + "="*50)
    print("SELECT MOMENTUM PLAYBOOK")
    print("="*50)
    print("1. Gap Move - Trade WITH the gap direction")
    print("   (Gap up → CALL, Gap down → PUT)")
    print("2. Gap Fade - Trade AGAINST the gap direction")
    print("   (Gap up → PUT, Gap down → CALL)")
    print("3. Manual - No auto-entry, just create play structure")
    
    while True:
        choice = input("\nEnter playbook choice (1-3): ").strip()
        if choice == '1':
            return MomentumPlaybook.GAP_MOVE
        elif choice == '2':
            return MomentumPlaybook.GAP_FADE
        elif choice == '3':
            return MomentumPlaybook.MANUAL
        print("Invalid choice. Please enter 1, 2, or 3.")


def main():
    """Main function to create test plays with multi-strategy support."""
    try:
        creator = AutoPlayCreator()
        
        # Strategy selection
        strategy = select_strategy()
        creator.set_strategy(strategy)
        
        # Playbook selection for momentum
        if strategy == StrategyType.MOMENTUM:
            playbook = select_momentum_playbook()
            creator.set_playbook(playbook)
        
        # Execution mode selection
        print("\n" + "="*50)
        print("SELECT EXECUTION MODE")
        print("="*50)
        print("1. Pure Execution Testing (Entry at current market price)")
        print("2. Simulate Real Plays (with buffer for entry conditions)")
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
        
        # Number of plays
        while True:
            try:
                num_plays = int(input("\nEnter number of test plays to create: "))
                if num_plays > 0:
                    break
                print("Please enter a positive number.")
            except ValueError:
                print("Please enter a valid number.")
        
        # Confirmation
        print("\n" + "="*50)
        print("CONFIRMATION")
        print("="*50)
        print(f"Strategy: {creator.get_strategy_display_name(strategy)}")
        if strategy == StrategyType.MOMENTUM and creator.current_playbook:
            print(f"Playbook: {creator.get_playbook_display_name(creator.current_playbook)}")
        print(f"Mode: {mode}")
        print(f"Number of plays: {num_plays}")
        
        confirm = input("\nProceed? (Y/N): ").strip().upper()
        if confirm != 'Y':
            print("Cancelled.")
            return
        
        # Create plays
        created_plays = creator.create_test_plays(num_plays, mode)
        
        display.info(f"\nCreated {len(created_plays)} test plays:")
        display.info(f"Strategy: {strategy.value}")
        for play in created_plays:
            display.info(f"- {play}")
            
    except Exception as e:
        display.error(f"Error in auto play creation: {e}")
        logging.error(f"Error in auto play creation: {e}", exc_info=True)

if __name__ == "__main__":
    main()
