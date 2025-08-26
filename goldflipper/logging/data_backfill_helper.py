#!/usr/bin/env python3
"""
Data Backfill Helper for Trade Logger

This module provides functionality to backfill missing market data (especially Greeks)
by making historical API calls to the configured market data provider.

Primary use case: Fill in missing delta_atOpen and theta_atOpen values by querying
the MarketDataApp API with the historical date from the play's opening timestamp.
"""

import os
import sys
import logging
from datetime import datetime, date
from typing import Dict, Any, Optional, List, Tuple
import pandas as pd

# Add the project root to Python path for imports
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(project_root)

from goldflipper.data.market.manager import MarketDataManager
from goldflipper.data.market.providers.marketdataapp_provider import MarketDataAppProvider
from goldflipper.config.config import config
from goldflipper.utils.display import TerminalDisplay as display


class DataBackfillHelper:
    """
    Helper class to backfill missing market data from play files using historical API calls.
    
    This class specializes in retrieving missing Greeks (delta, theta) and other market data
    by making targeted API calls to MarketDataApp using historical dates.
    """
    
    def __init__(self):
        """Initialize the backfill helper with market data manager"""
        self.market_manager = MarketDataManager()
        
        # Get the primary provider (should be MarketDataApp)
        provider_name = config.get('market_data_providers', 'primary_provider', default='marketdataapp')
        self.provider_name = provider_name
        
        # Initialize counters for tracking
        self.stats = {
            'total_processed': 0,
            'missing_greeks_found': 0,
            'successful_backfills': 0,
            'failed_backfills': 0,
            'api_errors': 0,
            'invalid_dates': 0,
            'missing_symbols': 0
        }
        
        logging.info(f"DataBackfillHelper initialized with provider: {provider_name}")
    
    def check_missing_data(self, play_data: Dict[str, Any]) -> Dict[str, bool]:
        """
        Analyze a play file to identify what data is missing.
        
        Args:
            play_data: Dictionary containing play file data
            
        Returns:
            Dictionary indicating what data types are missing
        """
        missing = {
            'delta_atOpen': False,
            'theta_atOpen': False,
            'premium_atOpen': False,
            'price_atOpen': False,
            'datetime_atOpen': False,
            'has_option_symbol': False,
            'has_opening_date': False
        }
        
        logging_data = play_data.get('logging', {})
        entry_point = play_data.get('entry_point', {})
        
        # Check for missing Greeks
        missing['delta_atOpen'] = (
            logging_data.get('delta_atOpen') is None or 
            logging_data.get('delta_atOpen') == 0.0
        )
        
        missing['theta_atOpen'] = (
            logging_data.get('theta_atOpen') is None or 
            logging_data.get('theta_atOpen') == 0.0
        )
        
        # Check for missing pricing data
        missing['premium_atOpen'] = (
            logging_data.get('premium_atOpen') is None and
            entry_point.get('entry_premium') is None
        )
        
        missing['price_atOpen'] = (
            logging_data.get('price_atOpen') is None and
            entry_point.get('entry_stock_price') is None and
            entry_point.get('stock_price') is None
        )
        
        # Check for missing datetime
        missing['datetime_atOpen'] = logging_data.get('datetime_atOpen') is None

        # Required fields present at creation/open
        missing['has_option_symbol'] = bool(play_data.get('option_contract_symbol'))
        missing['has_opening_date'] = logging_data.get('datetime_atOpen') is not None
        
        return missing
    
    def construct_option_symbol(self, play_data: Dict[str, Any]) -> Optional[str]:
        """
        Construct the OCC option symbol from play data.
        
        Args:
            play_data: Dictionary containing play file data
            
        Returns:
            OCC option symbol string, or None if cannot be constructed
        """
        try:
            # First, check if the option symbol is already provided
            if 'option_contract_symbol' in play_data:
                return play_data['option_contract_symbol']
            
            # Otherwise, construct from individual components
            symbol = play_data.get('symbol', '').upper()
            trade_type = play_data.get('trade_type', '').lower()
            strike_price = float(play_data.get('strike_price', 0))
            expiration_date_str = play_data.get('expiration_date', '')
            
            if not all([symbol, trade_type, strike_price, expiration_date_str]):
                logging.warning(f"Missing required data to construct option symbol: {play_data.get('play_name', 'Unknown')}")
                return None
            
            # Parse expiration date (expected format: MM/DD/YYYY)
            try:
                expiration_date = datetime.strptime(expiration_date_str, "%m/%d/%Y").date()
            except ValueError:
                logging.warning(f"Invalid expiration date format: {expiration_date_str}")
                return None
            
            # Format as YYMMDD
            exp_str = expiration_date.strftime("%y%m%d")
            
            # Option type (C for call, P for put)
            option_type = 'C' if trade_type == 'call' else 'P'
            
            # Strike price in thousandths (multiply by 1000, format as 8 digits)
            strike_formatted = f"{int(strike_price * 1000):08d}"
            
            # Construct OCC symbol: SYMBOL + YYMMDD + C/P + STRIKE
            option_symbol = f"{symbol}{exp_str}{option_type}{strike_formatted}"
            
            logging.debug(f"Constructed option symbol: {option_symbol}")
            return option_symbol
            
        except Exception as e:
            logging.error(f"Error constructing option symbol: {str(e)}")
            return None
    
    def get_historical_option_data(
        self, 
        option_symbol: str, 
        historical_date: date
    ) -> Optional[Dict[str, float]]:
        """
        Fetch historical option data for a specific date.
        
        Args:
            option_symbol: OCC option symbol
            historical_date: Date for which to fetch historical data
            
        Returns:
            Dictionary containing option data including Greeks, or None if failed
        """
        try:
            # Use MarketDataApp provider directly for historical data
            provider = self.market_manager.provider
            
            if not isinstance(provider, MarketDataAppProvider):
                logging.warning(f"Provider {self.provider_name} may not support historical Greeks")
                return None
            
            # Build URL with historical date parameter
            date_str = historical_date.strftime("%Y-%m-%d")
            url = f"{provider.base_url}/options/quotes/{option_symbol}/"
            params = {'date': date_str}
            
            logging.info(f"Fetching historical data for {option_symbol} on {date_str}")
            
            response = provider._make_request(url, params)
            
            if response.status_code in (200, 203):
                data = response.json()
                if data.get('s') == 'ok':
                    # Extract the data (API returns arrays)
                    result = {
                        'delta': data.get('delta', [None])[0],
                        'theta': data.get('theta', [None])[0],
                        'gamma': data.get('gamma', [None])[0],
                        'vega': data.get('vega', [None])[0],
                        'rho': data.get('rho', [None])[0],
                        'bid': data.get('bid', [None])[0],
                        'ask': data.get('ask', [None])[0],
                        'last': data.get('last', [None])[0],
                        'iv': data.get('iv', [None])[0],
                        'underlyingPrice': data.get('underlyingPrice', [None])[0]
                    }
                    
                    # Filter out None values
                    result = {k: v for k, v in result.items() if v is not None}
                    
                    logging.info(f"Successfully retrieved historical data: delta={result.get('delta')}, theta={result.get('theta')}")
                    return result
                else:
                    logging.warning(f"API returned error for {option_symbol} on {date_str}: {data.get('errmsg', 'Unknown error')}")
                    return None
            elif response.status_code == 204:
                logging.warning(f"No historical data available for {option_symbol} on {date_str}")
                return None
            else:
                logging.error(f"API request failed for {option_symbol} on {date_str}: {response.status_code}")
                return None
                
        except Exception as e:
            logging.error(f"Error fetching historical data for {option_symbol}: {str(e)}")
            self.stats['api_errors'] += 1
            return None
    
    def backfill_play_data(self, play_data: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
        """
        Attempt to backfill missing data for a single play.
        
        Args:
            play_data: Dictionary containing play file data
            
        Returns:
            Tuple of (success_flag, updated_play_data)
        """
        self.stats['total_processed'] += 1
        
        # Only backfill if the play was actually opened per entry premium
        entry_point = play_data.get('entry_point', {}) or {}
        entry_premium = entry_point.get('entry_premium')
        try:
            opened_by_entry_premium = float(entry_premium) > 0 if entry_premium is not None else False
        except (TypeError, ValueError):
            opened_by_entry_premium = False
        if not opened_by_entry_premium:
            return True, play_data

        # Check what data is missing (closed plays only)
        missing = self.check_missing_data(play_data)
        
        # Skip if no Greeks are missing
        if not (missing['delta_atOpen'] or missing['theta_atOpen']):
            logging.debug(f"Play {play_data.get('play_name', 'Unknown')} has complete Greeks data")
            return True, play_data
        
        self.stats['missing_greeks_found'] += 1
        
        # Check if we have the required data to make API calls
        if not missing['has_option_symbol']:
            logging.warning(f"Play {play_data.get('play_name', 'Unknown')} missing option symbol")
            self.stats['missing_symbols'] += 1
            return False, play_data
        
        if not missing['has_opening_date']:
            logging.warning(f"Play {play_data.get('play_name', 'Unknown')} missing opening date")
            self.stats['invalid_dates'] += 1
            return False, play_data
        
        # Use recorded option symbol from play creation
        option_symbol = play_data.get('option_contract_symbol')
        if not option_symbol:
            self.stats['missing_symbols'] += 1
            return False, play_data
        
        # Parse the opening datetime
        try:
            datetime_str = play_data['logging']['datetime_atOpen']
            opening_datetime = pd.to_datetime(datetime_str)
            opening_date = opening_datetime.date()
        except (ValueError, KeyError) as e:
            logging.error(f"Invalid opening datetime: {str(e)}")
            self.stats['invalid_dates'] += 1
            return False, play_data
        
        # Fetch historical data
        historical_data = self.get_historical_option_data(option_symbol, opening_date)
        
        if not historical_data:
            self.stats['failed_backfills'] += 1
            return False, play_data
        
        # Update the play data with retrieved information
        updated_play = play_data.copy()
        
        # Ensure logging section exists
        if 'logging' not in updated_play:
            updated_play['logging'] = {}
        
        # Update Greeks if missing and available
        if missing['delta_atOpen'] and 'delta' in historical_data:
            updated_play['logging']['delta_atOpen'] = historical_data['delta']
            logging.info(f"Updated delta_atOpen: {historical_data['delta']}")
        
        if missing['theta_atOpen'] and 'theta' in historical_data:
            updated_play['logging']['theta_atOpen'] = historical_data['theta']
            logging.info(f"Updated theta_atOpen: {historical_data['theta']}")
        
        # Optionally update other missing data
        if missing['premium_atOpen'] and 'last' in historical_data:
            updated_play['logging']['premium_atOpen'] = historical_data['last']
            logging.info(f"Updated premium_atOpen: {historical_data['last']}")
        
        if missing['price_atOpen'] and 'underlyingPrice' in historical_data:
            updated_play['logging']['price_atOpen'] = historical_data['underlyingPrice']
            logging.info(f"Updated price_atOpen: {historical_data['underlyingPrice']}")
        
        self.stats['successful_backfills'] += 1
        return True, updated_play
    
    def backfill_multiple_plays(self, plays_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Backfill data for multiple plays.
        
        Args:
            plays_data: List of play data dictionaries
            
        Returns:
            List of updated play data dictionaries
        """
        updated_plays = []
        
        logging.info(f"Starting backfill process for {len(plays_data)} plays")
        display.info(f"🔄 Starting data backfill for {len(plays_data)} plays...")
        
        for i, play_data in enumerate(plays_data):
            play_name = play_data.get('play_name', f'Play_{i}')
            
            try:
                success, updated_play = self.backfill_play_data(play_data)
                updated_plays.append(updated_play)
                
                # Progress reporting
                if (i + 1) % 10 == 0 or i == len(plays_data) - 1:
                    progress = ((i + 1) / len(plays_data)) * 100
                    display.info(f"📊 Progress: {progress:.1f}% ({i + 1}/{len(plays_data)})")
                
            except Exception as e:
                logging.error(f"Error processing play {play_name}: {str(e)}")
                updated_plays.append(play_data)  # Keep original if error occurs
                self.stats['failed_backfills'] += 1
        
        # Report final statistics
        self.report_stats()
        
        return updated_plays
    
    def report_stats(self):
        """Report backfill statistics"""
        stats = self.stats
        
        display.info(f"\n📈 **Data Backfill Complete**")
        display.info(f"   Total plays processed: {stats['total_processed']}")
        display.info(f"   Plays with missing Greeks: {stats['missing_greeks_found']}")
        display.info(f"   Successful backfills: {stats['successful_backfills']}")
        display.info(f"   Failed backfills: {stats['failed_backfills']}")
        
        if stats['api_errors'] > 0:
            display.warning(f"   API errors: {stats['api_errors']}")
        if stats['invalid_dates'] > 0:
            display.warning(f"   Invalid dates: {stats['invalid_dates']}")
        if stats['missing_symbols'] > 0:
            display.warning(f"   Missing symbols: {stats['missing_symbols']}")
        
        success_rate = (stats['successful_backfills'] / max(stats['missing_greeks_found'], 1)) * 100
        display.info(f"   Success rate: {success_rate:.1f}%")
        
        logging.info(f"Backfill statistics: {stats}")


def backfill_play_data(play_data: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
    """
    Convenience function to backfill a single play's data.
    
    Args:
        play_data: Dictionary containing play file data
        
    Returns:
        Tuple of (success_flag, updated_play_data)
    """
    helper = DataBackfillHelper()
    return helper.backfill_play_data(play_data)


def backfill_plays_list(plays_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Convenience function to backfill multiple plays' data.
    
    Args:
        plays_data: List of play data dictionaries
        
    Returns:
        List of updated play data dictionaries
    """
    helper = DataBackfillHelper()
    return helper.backfill_multiple_plays(plays_data)


if __name__ == "__main__":
    """
    Test the backfill helper with some sample data
    """
    import json
    
    # Example of how to use the helper
    logging.basicConfig(level=logging.INFO)
    
    # Load a sample play file for testing
    sample_play_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), 
        "plays", "closed", "SPOT-call-1-20250820-0802.json"
    )
    
    if os.path.exists(sample_play_path):
        with open(sample_play_path, 'r') as f:
            sample_play = json.load(f)
        
        helper = DataBackfillHelper()
        success, updated_play = helper.backfill_play_data(sample_play)
        
        print(f"Backfill success: {success}")
        if success:
            print("Updated Greeks:")
            logging_data = updated_play.get('logging', {})
            print(f"  Delta: {logging_data.get('delta_atOpen')}")
            print(f"  Theta: {logging_data.get('theta_atOpen')}")
    else:
        print("Sample play file not found - cannot run test")
