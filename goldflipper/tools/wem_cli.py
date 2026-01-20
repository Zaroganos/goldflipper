#!/usr/bin/env python3
"""
WEM/KEP/HPS CLI Tool - Headless Weekly Expected Moves Analysis

Run WEM calculations, KEP analysis, and HPS validation from command line
without requiring the Streamlit web interface.

Usage:
    python -m goldflipper.tools.wem_cli --help
    python -m goldflipper.tools.wem_cli --output wem_output.xlsx
    python -m goldflipper.tools.wem_cli --symbols SPY,QQQ,NVDA --output wem.json
    python -m goldflipper.tools.wem_cli --tickers-file default_tickers.txt --kep --hps --output analysis.xlsx
"""

import argparse
import json
import logging
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
import pandas as pd

# Set up paths before imports (noqa: E402 - imports must come after path setup)
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from goldflipper.database.connection import get_db_connection, init_db  # noqa: E402
from goldflipper.database.models import WEMStock  # noqa: E402
from goldflipper.data.market.manager import MarketDataManager  # noqa: E402
from goldflipper.utils.market_holidays import (  # noqa: E402
    find_next_friday_expiration,
    find_previous_friday,
)

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


# ============================================================================
# MARKET DATA MANAGER (Headless version without Streamlit caching)
# ============================================================================

_market_data_manager: Optional[MarketDataManager] = None


def get_market_data_manager() -> Optional[MarketDataManager]:
    """Get or create MarketDataManager instance (headless, no Streamlit)."""
    global _market_data_manager
    if _market_data_manager is None:
        try:
            _market_data_manager = MarketDataManager()
            if not _market_data_manager.providers:
                logger.error("No market data providers configured")
                return None
            logger.info(f"Initialized providers: {list(_market_data_manager.providers.keys())}")
        except Exception as e:
            logger.error(f"Failed to initialize MarketDataManager: {e}")
            return None
    return _market_data_manager


# ============================================================================
# CORE WEM FUNCTIONS (extracted from web/pages/6_📊_WEM.py)
# ============================================================================

def _robust_mid(option_row: pd.Series) -> Optional[float]:
    """Compute a robust mid for an option row."""
    bid = option_row.get('bid')
    ask = option_row.get('ask')
    last = option_row.get('last')
    
    if bid is not None and ask is not None and bid > 0 and ask > 0:
        return (bid + ask) / 2
    if last is not None and last > 0:
        return last
    if ask is not None and ask > 0:
        return ask
    if bid is not None and bid > 0:
        return bid
    return None


def get_wem_stocks_from_db() -> List[Dict[str, Any]]:
    """Get all WEM stocks from database."""
    with get_db_connection() as session:
        stocks = session.query(WEMStock).all()
        return [stock.to_dict() for stock in stocks]


def get_symbols_from_file(filepath: str) -> List[str]:
    """Load ticker symbols from a text file (one per line)."""
    path = Path(filepath)
    if not path.exists():
        # Try relative to wem_template directory
        template_path = PROJECT_ROOT / 'web' / 'wem_template' / filepath
        if template_path.exists():
            path = template_path
        else:
            raise FileNotFoundError(f"Ticker file not found: {filepath}")
    
    symbols = []
    with open(path, 'r') as f:
        for line in f:
            symbol = line.strip().upper()
            if symbol and not symbol.startswith('#'):
                symbols.append(symbol)
    return symbols


def _get_previous_friday_close_price(symbol: str, previous_friday_date: datetime) -> Optional[float]:
    """Get the closing price for a symbol on the previous Friday."""
    manager = get_market_data_manager()
    if not manager:
        return None
    
    try:
        # Try yfinance historical data
        for provider_name, provider in manager.providers.items():
            if hasattr(provider, 'get_historical_data'):
                try:
                    start_date = previous_friday_date - timedelta(days=1)
                    end_date = previous_friday_date + timedelta(days=1)
                    df = provider.get_historical_data(symbol, start_date, end_date, interval='1d')
                    if df is not None and not df.empty:
                        # Find the close column
                        close_col = None
                        for col in ['close', 'Close', 'adj_close', 'Adj Close']:
                            if col in df.columns:
                                close_col = col
                                break
                        if close_col:
                            # Get the value for the Friday date
                            friday_str = previous_friday_date.strftime('%Y-%m-%d')
                            if hasattr(df.index, 'strftime'):
                                df_dates = df.index.strftime('%Y-%m-%d')
                                mask = df_dates == friday_str
                                if mask.any():
                                    return float(df.loc[mask, close_col].iloc[0])
                            # Fallback: just get last value
                            return float(df[close_col].iloc[-1])
                except Exception as e:
                    logger.debug(f"Provider {provider_name} failed for historical: {e}")
                    continue
        
        # Fallback: use current price
        return manager.get_stock_price(symbol, regular_hours_only=True)
    except Exception as e:
        logger.warning(f"Could not get Friday close for {symbol}: {e}")
        return None


def _get_weekly_option_chain(symbol: str, expiration_date: datetime) -> Dict[str, pd.DataFrame]:
    """Get weekly option chain for a specific expiration date."""
    manager = get_market_data_manager()
    if not manager:
        return {'calls': pd.DataFrame(), 'puts': pd.DataFrame()}
    
    exp_str = expiration_date.strftime('%Y-%m-%d')
    
    for provider_name, provider in manager.providers.items():
        if hasattr(provider, 'get_option_chain'):
            try:
                chain = provider.get_option_chain(symbol, exp_str)
                if chain is not None:
                    if isinstance(chain, dict):
                        calls = chain.get('calls', pd.DataFrame())
                        puts = chain.get('puts', pd.DataFrame())
                    elif isinstance(chain, tuple) and len(chain) == 2:
                        calls, puts = chain
                    else:
                        continue
                    
                    if not calls.empty or not puts.empty:
                        logger.debug(f"Got option chain from {provider_name}")
                        return {'calls': calls, 'puts': puts}
            except Exception as e:
                logger.debug(f"Provider {provider_name} failed for option chain: {e}")
                continue
    
    return {'calls': pd.DataFrame(), 'puts': pd.DataFrame()}


def _extract_required_options(calls: pd.DataFrame, puts: pd.DataFrame, 
                             current_price: float, symbol: str) -> Optional[Dict[str, Any]]:
    """Extract ATM and ITM options for WEM calculation."""
    if calls.empty or puts.empty:
        logger.warning(f"Empty option chain for {symbol}")
        return None
    
    # Normalize column names
    calls = calls.copy()
    puts = puts.copy()
    calls.columns = calls.columns.str.lower()
    puts.columns = puts.columns.str.lower()
    
    if 'strike' not in calls.columns or 'strike' not in puts.columns:
        logger.error(f"No strike column in option chain for {symbol}")
        return None
    
    # Find ATM strike
    call_strikes = sorted(calls['strike'].unique())
    atm_strike = min(call_strikes, key=lambda x: abs(x - current_price))
    
    # Get ATM options
    atm_call = calls[calls['strike'] == atm_strike]
    atm_put = puts[puts['strike'] == atm_strike]
    
    if atm_call.empty or atm_put.empty:
        logger.warning(f"Could not find ATM options at strike {atm_strike} for {symbol}")
        return None
    
    # Find ITM strikes (adjacent to ATM)
    atm_idx = call_strikes.index(atm_strike)
    itm_call_strike = call_strikes[atm_idx - 1] if atm_idx > 0 else call_strikes[0]
    itm_put_strike = call_strikes[atm_idx + 1] if atm_idx < len(call_strikes) - 1 else call_strikes[-1]
    
    itm_call = calls[calls['strike'] == itm_call_strike]
    itm_put = puts[puts['strike'] == itm_put_strike]
    
    if itm_call.empty or itm_put.empty:
        logger.warning(f"Could not find ITM options for {symbol}")
        return None
    
    return {
        'atm_call': atm_call.iloc[0],
        'atm_put': atm_put.iloc[0],
        'itm_call': itm_call.iloc[0],
        'itm_put': itm_put.iloc[0],
        'atm_strike': atm_strike,
        'itm_call_strike': itm_call_strike,
        'itm_put_strike': itm_put_strike
    }


def _calculate_delta_16_values(option_chain: Dict[str, pd.DataFrame], 
                               expiration_date: str,
                               spot_price: float) -> Optional[Dict[str, Any]]:
    """Find Delta 16+/- options from the chain."""
    calls = option_chain.get('calls', pd.DataFrame())
    puts = option_chain.get('puts', pd.DataFrame())
    
    if calls.empty or puts.empty:
        return None
    
    # Normalize columns
    calls = calls.copy()
    puts = puts.copy()
    calls.columns = calls.columns.str.lower()
    puts.columns = puts.columns.str.lower()
    
    if 'delta' not in calls.columns or 'delta' not in puts.columns:
        logger.debug("No delta column in option chain")
        return None
    
    # Find call closest to delta 0.16
    calls_with_delta = calls[calls['delta'].notna() & (calls['delta'] > 0)]
    if calls_with_delta.empty:
        return None
    
    delta_16_plus_idx = (calls_with_delta['delta'] - 0.16).abs().idxmin()
    delta_16_plus = calls_with_delta.loc[delta_16_plus_idx]
    
    # Find put closest to delta -0.16
    puts_with_delta = puts[puts['delta'].notna() & (puts['delta'] < 0)]
    if puts_with_delta.empty:
        return None
    
    delta_16_minus_idx = (puts_with_delta['delta'] + 0.16).abs().idxmin()
    delta_16_minus = puts_with_delta.loc[delta_16_minus_idx]
    
    return {
        'delta_16_plus': {
            'strike': float(delta_16_plus['strike']),
            'delta': float(delta_16_plus['delta']),
            'delta_accuracy': abs(float(delta_16_plus['delta']) - 0.16)
        },
        'delta_16_minus': {
            'strike': float(delta_16_minus['strike']),
            'delta': float(delta_16_minus['delta']),
            'delta_accuracy': abs(float(delta_16_minus['delta']) + 0.16)
        }
    }


def calculate_wem_for_symbol(symbol: str, use_friday_close: bool = True) -> Optional[Dict[str, Any]]:
    """
    Calculate Weekly Expected Move for a single symbol.
    
    Args:
        symbol: Stock ticker symbol
        use_friday_close: Use previous Friday's close (standard) or most recent price
        
    Returns:
        Dictionary with WEM calculation results or None if failed
    """
    logger.info(f"Calculating WEM for {symbol}")
    
    manager = get_market_data_manager()
    if not manager:
        logger.error("No market data manager available")
        return None
    
    try:
        # Step 1: Get base price
        if use_friday_close:
            previous_friday = find_previous_friday()
            current_price = _get_previous_friday_close_price(symbol, previous_friday)
            if current_price is None:
                logger.warning(f"Friday close not available for {symbol}, using current price")
                current_price = manager.get_stock_price(symbol, regular_hours_only=True)
        else:
            current_price = manager.get_stock_price(symbol, regular_hours_only=True)
        
        if current_price is None or current_price <= 0:
            logger.error(f"Could not get price for {symbol}")
            return None
        
        current_price = float(current_price)
        logger.info(f"{symbol} price: ${current_price:.2f}")
        
        # Step 2: Get expiration date
        next_friday = find_next_friday_expiration()
        
        # Step 3: Get option chain
        option_chain = _get_weekly_option_chain(symbol, next_friday)
        calls = option_chain.get('calls', pd.DataFrame())
        puts = option_chain.get('puts', pd.DataFrame())
        
        if calls.empty or puts.empty:
            logger.error(f"No option chain available for {symbol}")
            return None
        
        # Step 4: Extract required options
        options = _extract_required_options(calls, puts, current_price, symbol)
        if not options:
            logger.error(f"Could not extract required options for {symbol}")
            return None
        
        # Step 5: Calculate straddle and strangle
        atm_call_mid = _robust_mid(options['atm_call'])
        atm_put_mid = _robust_mid(options['atm_put'])
        itm_call_mid = _robust_mid(options['itm_call'])
        itm_put_mid = _robust_mid(options['itm_put'])
        
        if None in (atm_call_mid, atm_put_mid, itm_call_mid, itm_put_mid):
            logger.error(f"Could not compute option mids for {symbol}")
            return None
        
        straddle = atm_call_mid + atm_put_mid
        strangle = itm_call_mid + itm_put_mid
        wem_points = (straddle + strangle) / 2
        
        # Step 6: Calculate WEM spread and ranges
        wem_spread = wem_points / current_price
        straddle_1 = current_price - wem_points  # Lower bound
        straddle_2 = current_price + wem_points  # Upper bound
        
        # Step 7: Calculate Delta 16 values
        delta_16_results = _calculate_delta_16_values(option_chain, next_friday.strftime('%Y-%m-%d'), current_price)
        
        delta_16_plus = None
        delta_16_minus = None
        delta_range = None
        delta_range_pct = None
        
        if delta_16_results:
            delta_16_plus = delta_16_results['delta_16_plus']['strike']
            delta_16_minus = delta_16_results['delta_16_minus']['strike']
            delta_range = delta_16_plus - delta_16_minus
            delta_range_pct = delta_range / current_price
        
        logger.info(f"{symbol} WEM: ${wem_points:.2f} ({wem_spread:.2%}), Range: ${straddle_1:.2f} - ${straddle_2:.2f}")
        
        return {
            'symbol': symbol,
            'atm_price': current_price,
            'straddle': straddle,
            'strangle': strangle,
            'wem_points': wem_points,
            'wem_spread': wem_spread,
            'expected_range_low': straddle_1,
            'expected_range_high': straddle_2,
            'straddle_1': straddle_1,
            'straddle_2': straddle_2,
            'atm_strike': options['atm_strike'],
            'itm_call_strike': options['itm_call_strike'],
            'itm_put_strike': options['itm_put_strike'],
            'delta_16_plus': delta_16_plus,
            'delta_16_minus': delta_16_minus,
            'delta_range': delta_range,
            'delta_range_pct': delta_range_pct,
            'expiration_date': next_friday.strftime('%Y-%m-%d'),
            'calculation_timestamp': datetime.now(timezone.utc).isoformat(),
            'meta_data': {
                'calculation_method': 'cli_headless',
                'use_friday_close': use_friday_close,
                'expiration_date': next_friday.isoformat()
            }
        }
        
    except Exception as e:
        logger.error(f"Error calculating WEM for {symbol}: {e}", exc_info=True)
        return None


def calculate_wem_batch(symbols: List[str], use_friday_close: bool = True) -> List[Dict[str, Any]]:
    """Calculate WEM for multiple symbols."""
    results = []
    total = len(symbols)
    
    for i, symbol in enumerate(symbols, 1):
        logger.info(f"Processing {i}/{total}: {symbol}")
        result = calculate_wem_for_symbol(symbol, use_friday_close)
        if result:
            results.append(result)
        else:
            # Create stub record for failed calculations
            results.append({
                'symbol': symbol,
                'atm_price': None,
                'wem_points': None,
                'wem_spread': None,
                'error': 'Calculation failed'
            })
    
    return results


# ============================================================================
# KEP/HPS INTEGRATION
# ============================================================================

def run_kep_analysis(wem_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Run KEP analysis on WEM results."""
    try:
        from web.components.kep_analysis import batch_analyze_kep
        import yfinance as yf
        
        def ohlc_provider(symbol: str) -> Optional[pd.DataFrame]:
            try:
                ticker = yf.Ticker(symbol)
                return ticker.history(period="3mo", interval="1d")
            except Exception:
                return None
        
        def quote_provider(symbol: str) -> Optional[Dict]:
            try:
                ticker = yf.Ticker(symbol)
                info = ticker.info
                return {
                    'high_52': info.get('fiftyTwoWeekHigh'),
                    'low_52': info.get('fiftyTwoWeekLow'),
                    'prior_day_high': info.get('dayHigh'),
                    'prior_day_low': info.get('dayLow')
                }
            except Exception:
                return None
        
        # Filter out failed WEM calculations
        valid_wem = [w for w in wem_results if w.get('wem_points') is not None]
        
        kep_scores = batch_analyze_kep(
            symbols_data=valid_wem,
            ohlc_provider=ohlc_provider,
            quote_provider=quote_provider,
            proximity_threshold=0.02
        )
        
        return [score.to_dict() for score in kep_scores]
        
    except ImportError as e:
        logger.warning(f"KEP analysis not available: {e}")
        return []
    except Exception as e:
        logger.error(f"KEP analysis failed: {e}")
        return []


def run_hps_analysis(kep_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Run HPS analysis on KEP results."""
    try:
        from web.components.hps_analysis import batch_analyze_hps
        import yfinance as yf
        
        def ohlc_provider(symbol: str) -> Optional[pd.DataFrame]:
            try:
                ticker = yf.Ticker(symbol)
                return ticker.history(period="3mo", interval="1d")
            except Exception:
                return None
        
        hps_results = batch_analyze_hps(
            kep_results=kep_results,
            ohlc_provider=ohlc_provider
        )
        
        return [result.to_dict() for result in hps_results]
        
    except ImportError as e:
        logger.warning(f"HPS analysis not available: {e}")
        return []
    except Exception as e:
        logger.error(f"HPS analysis failed: {e}")
        return []


# ============================================================================
# EXPORT FUNCTIONS
# ============================================================================

def export_to_json(data: Dict[str, Any], output_path: str) -> None:
    """Export results to JSON file."""
    with open(output_path, 'w') as f:
        json.dump(data, f, indent=2, default=str)
    logger.info(f"Exported to {output_path}")


def export_to_excel(data: Dict[str, Any], output_path: str) -> None:
    """Export results to Excel file."""
    try:
        with pd.ExcelWriter(output_path, engine='xlsxwriter') as writer:
            # WEM Sheet
            if 'wem' in data and data['wem']:
                wem_df = pd.DataFrame(data['wem'])
                # Select key columns for display
                display_cols = ['symbol', 'atm_price', 'wem_points', 'wem_spread', 
                               'straddle_1', 'straddle_2', 'delta_16_minus', 'delta_16_plus',
                               'expiration_date']
                display_cols = [c for c in display_cols if c in wem_df.columns]
                wem_df[display_cols].to_excel(writer, sheet_name='WEM', index=False)
                logger.info(f"Wrote WEM sheet with {len(wem_df)} rows")
            
            # KEP Sheet
            if 'kep' in data and data['kep']:
                kep_df = pd.DataFrame(data['kep'])
                kep_df.to_excel(writer, sheet_name='KEP', index=False)
                logger.info(f"Wrote KEP sheet with {len(kep_df)} rows")
            
            # HPS Sheet
            if 'hps' in data and data['hps']:
                hps_df = pd.DataFrame(data['hps'])
                hps_df.to_excel(writer, sheet_name='HPS', index=False)
                logger.info(f"Wrote HPS sheet with {len(hps_df)} rows")
            
            # Metadata sheet
            meta_df = pd.DataFrame([{
                'generated_at': datetime.now().isoformat(),
                'previous_friday': find_previous_friday().strftime('%Y-%m-%d'),
                'next_expiration': find_next_friday_expiration().strftime('%Y-%m-%d'),
                'symbols_count': len(data.get('wem', [])),
                'tool': 'wem_cli.py'
            }])
            meta_df.to_excel(writer, sheet_name='Metadata', index=False)
        
        logger.info(f"Exported to {output_path}")
        
    except Exception as e:
        logger.error(f"Excel export failed: {e}")
        # Fallback to JSON
        json_path = output_path.replace('.xlsx', '.json').replace('.xls', '.json')
        export_to_json(data, json_path)


# ============================================================================
# CLI ENTRYPOINT
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='WEM/KEP/HPS CLI Tool - Headless Weekly Expected Moves Analysis',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m goldflipper.tools.wem_cli --output wem.xlsx
  python -m goldflipper.tools.wem_cli --symbols SPY,QQQ,NVDA --output wem.json
  python -m goldflipper.tools.wem_cli --tickers-file default_tickers.txt --kep --hps --output analysis.xlsx
  python -m goldflipper.tools.wem_cli --from-db --output db_wem.xlsx
        """
    )
    
    # Input options (mutually exclusive)
    input_group = parser.add_mutually_exclusive_group()
    input_group.add_argument(
        '--symbols', '-s',
        type=str,
        help='Comma-separated list of ticker symbols (e.g., SPY,QQQ,NVDA)'
    )
    input_group.add_argument(
        '--tickers-file', '-f',
        type=str,
        help='Path to file with ticker symbols (one per line)'
    )
    input_group.add_argument(
        '--from-db',
        action='store_true',
        help='Use symbols from the WEM database table'
    )
    
    # Analysis options
    parser.add_argument(
        '--kep',
        action='store_true',
        help='Run KEP (Key Entry Points) analysis on WEM results'
    )
    parser.add_argument(
        '--hps',
        action='store_true',
        help='Run HPS (High Probability Setups) analysis on KEP results'
    )
    
    # Output options
    parser.add_argument(
        '--output', '-o',
        type=str,
        default='wem_output.xlsx',
        help='Output file path (.xlsx or .json)'
    )
    
    # Calculation options
    parser.add_argument(
        '--use-current-price',
        action='store_true',
        help='Use current price instead of previous Friday close'
    )
    
    # Logging options
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )
    parser.add_argument(
        '--quiet', '-q',
        action='store_true',
        help='Suppress non-error output'
    )
    
    args = parser.parse_args()
    
    # Configure logging level
    if args.quiet:
        logging.getLogger().setLevel(logging.ERROR)
    elif args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Initialize database
    try:
        init_db()
    except Exception as e:
        logger.warning(f"Database initialization: {e}")
    
    # Determine symbols to process
    symbols = []
    
    if args.symbols:
        symbols = [s.strip().upper() for s in args.symbols.split(',')]
        logger.info(f"Processing {len(symbols)} symbols from command line")
    elif args.tickers_file:
        symbols = get_symbols_from_file(args.tickers_file)
        logger.info(f"Loaded {len(symbols)} symbols from {args.tickers_file}")
    elif args.from_db:
        db_stocks = get_wem_stocks_from_db()
        symbols = [s['symbol'] for s in db_stocks]
        logger.info(f"Loaded {len(symbols)} symbols from database")
    else:
        # Default: use default_tickers.txt
        try:
            symbols = get_symbols_from_file('default_tickers.txt')
            logger.info(f"Loaded {len(symbols)} symbols from default_tickers.txt")
        except FileNotFoundError:
            logger.error("No symbols specified. Use --symbols, --tickers-file, or --from-db")
            sys.exit(1)
    
    if not symbols:
        logger.error("No symbols to process")
        sys.exit(1)
    
    # Run WEM calculations
    use_friday_close = not args.use_current_price
    logger.info(f"Starting WEM calculation for {len(symbols)} symbols")
    logger.info(f"Price mode: {'Previous Friday close' if use_friday_close else 'Current price'}")
    
    wem_results = calculate_wem_batch(symbols, use_friday_close)
    
    successful = sum(1 for r in wem_results if r.get('wem_points') is not None)
    logger.info(f"WEM calculation complete: {successful}/{len(symbols)} successful")
    
    # Prepare output data
    output_data = {
        'wem': wem_results,
        'generated_at': datetime.now().isoformat(),
        'previous_friday': find_previous_friday().strftime('%Y-%m-%d'),
        'next_expiration': find_next_friday_expiration().strftime('%Y-%m-%d')
    }
    
    # Run KEP analysis if requested
    if args.kep:
        logger.info("Running KEP analysis...")
        kep_results = run_kep_analysis(wem_results)
        output_data['kep'] = kep_results
        logger.info(f"KEP analysis complete: {len(kep_results)} results")
    
    # Run HPS analysis if requested
    if args.hps:
        if 'kep' not in output_data or not output_data['kep']:
            logger.warning("HPS requires KEP analysis. Running KEP first...")
            kep_results = run_kep_analysis(wem_results)
            output_data['kep'] = kep_results
        
        logger.info("Running HPS analysis...")
        hps_results = run_hps_analysis(output_data['kep'])
        output_data['hps'] = hps_results
        logger.info(f"HPS analysis complete: {len(hps_results)} results")
    
    # Export results
    output_path = args.output
    if output_path.endswith('.json'):
        export_to_json(output_data, output_path)
    else:
        export_to_excel(output_data, output_path)
    
    logger.info("Done!")
    
    # Print summary
    print("=" * 60)
    print("WEM CLI Analysis Complete")
    print("=" * 60)
    print(f"Symbols processed: {len(symbols)}")
    print(f"Successful WEM calculations: {successful}")
    if args.kep:
        print(f"KEP candidates: {len(output_data.get('kep', []))}")
    if args.hps:
        trade_count = sum(1 for h in output_data.get('hps', []) if h.get('recommendation') == 'TRADE')
        print(f"HPS TRADE recommendations: {trade_count}")
    print(f"Output file: {output_path}")
    print("=" * 60 + "\n")


if __name__ == '__main__':
    main()
