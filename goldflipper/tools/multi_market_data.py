from typing import Dict, List, Optional, Any
import pandas as pd
from datetime import datetime
import yaml
import os
import sys
from rich.console import Console
from rich.table import Table
from rich import print as rprint
import time
import asyncio
import logging
import re

# Add the project root to the Python path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from goldflipper.data.market.providers.base import MarketDataProvider
from goldflipper.data.market.providers.alpaca_provider import AlpacaProvider
from goldflipper.data.market.providers.yfinance_provider import YFinanceProvider

class MarketDataComparator:
    """Compares market data from multiple providers"""
    
    def __init__(self):
        self.providers: Dict[str, MarketDataProvider] = {}
        self.settings = self._load_settings()
        asyncio.run(self._initialize_providers())
        
    def _load_settings(self) -> dict:
        """Load settings from YAML file"""
        config_path = os.path.join(project_root, 'goldflipper', 'config', 'settings.yaml')
        with open(config_path, 'r') as f:
            settings = yaml.safe_load(f)
        return settings['market_data_providers']
    
    async def _initialize_providers(self):
        """Initialize enabled providers from settings"""
        provider_map = {
            'alpaca': AlpacaProvider,
            'yfinance': YFinanceProvider
        }
        
        for provider_name, settings in self.settings['providers'].items():
            if settings['enabled'] and provider_name in provider_map:
                try:
                    provider = provider_map[provider_name]()
                    
                    # Handle async initialization if needed
                    if hasattr(provider, '_init_websocket'):
                        await provider._init_websocket()
                    
                    self.providers[provider_name] = provider
                    logging.info(f"Initialized {provider_name} provider")
                except Exception as e:
                    logging.error(f"Failed to initialize {provider_name} provider: {str(e)}")
    
    async def compare_stock_price(self, symbol: str) -> pd.DataFrame:
        """Compare stock price across providers"""
        data = []
        
        for name, provider in self.providers.items():
            try:
                price = await provider.get_stock_price(symbol)
                data.append({
                    'Provider': name,
                    'Symbol': symbol,
                    'Price': price,
                    'Timestamp': datetime.now()
                })
            except Exception as e:
                logging.error(f"Error getting price from {name}: {str(e)}")
                data.append({
                    'Provider': name,
                    'Symbol': symbol,
                    'Price': None,
                    'Timestamp': datetime.now(),
                    'Error': str(e)
                })
        
        return pd.DataFrame(data)
    
    def compare_option_chain(self, symbol: str, expiration_date: str) -> Dict[str, pd.DataFrame]:
        """Compare option chains across providers"""
        calls_data = []
        puts_data = []
        
        for name, provider in self.providers.items():
            try:
                chains = provider.get_option_chain(symbol, expiration_date)
                
                for type_name, chain in chains.items():
                    # Add provider and our known expiration date
                    chain['Provider'] = name
                    chain['expiration'] = expiration_date  # Add the correct expiration we know
                    
                    if type_name == 'calls':
                        calls_data.append(chain)
                    else:
                        puts_data.append(chain)
                        
            except Exception as e:
                logging.error(f"Error getting option chain from {name}: {str(e)}")
        
        return {
            'calls': pd.concat(calls_data, axis=0) if calls_data else pd.DataFrame(),
            'puts': pd.concat(puts_data, axis=0) if puts_data else pd.DataFrame()
        }
    
    def compare_historical_data(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        interval: str = "1m"
    ) -> pd.DataFrame:
        """Compare historical data across providers"""
        all_data = {}
        
        for name, provider in self.providers.items():
            try:
                df = provider.get_historical_data(symbol, start_date, end_date, interval)
                all_data[name] = df
            except Exception as e:
                logging.error(f"Error getting historical data from {name}: {str(e)}")
        
        # Combine all providers' data
        combined = pd.concat(all_data, axis=1)
        
        if self.settings['comparison']['log_differences']:
            self._log_historical_differences(combined, symbol)
        
        return combined
    
    def _log_price_differences(self, df: pd.DataFrame, symbol: str):
        """Log significant differences in price data"""
        if len(df) < 2:
            return
            
        max_diff_pct = (df['Price'].max() - df['Price'].min()) / df['Price'].min()
        if max_diff_pct > self.settings['comparison']['difference_threshold']:
            logging.warning(
                f"Significant price difference detected for {symbol}. "
                f"Max difference: {max_diff_pct:.2%}"
            )
    
    def _log_option_differences(self, calls: pd.DataFrame, puts: pd.DataFrame, symbol: str):
        """Log significant differences in option data"""
        for chain_type, data in [('calls', calls), ('puts', puts)]:
            if len(data) < 2:
                continue
                
            for col in ['bid', 'ask', 'last']:
                if col in data.columns:
                    grouped = data.groupby('strike')[col]
                    max_diff_pct = grouped.apply(lambda x: (x.max() - x.min()) / x.min() if x.min() != 0 else 0)
                    significant_diffs = max_diff_pct[max_diff_pct > self.settings['comparison']['difference_threshold']]
                    
                    if not significant_diffs.empty:
                        logging.warning(
                            f"Significant {chain_type} option {col} differences detected for {symbol} "
                            f"at strikes: {', '.join(map(str, significant_diffs.index))}"
                        )
    
    def _log_historical_differences(self, df: pd.DataFrame, symbol: str):
        """Log significant differences in historical data"""
        for col in ['Close', 'Volume']:
            if col in df.columns:
                providers = [name for name in self.providers.keys() if f"{name}/{col}" in df.columns]
                if len(providers) < 2:
                    continue
                    
                for i in range(len(providers)):
                    for j in range(i + 1, len(providers)):
                        col1 = f"{providers[i]}/{col}"
                        col2 = f"{providers[j]}/{col}"
                        diff_pct = abs(df[col1] - df[col2]) / df[col1]
                        max_diff = diff_pct.max()
                        
                        if max_diff > self.settings['comparison']['difference_threshold']:
                            logging.warning(
                                f"Significant {col} difference detected for {symbol} between "
                                f"{providers[i]} and {providers[j]}. Max difference: {max_diff:.2%}"
                            )

    async def cleanup(self):
        """Cleanup all providers"""
        for provider in self.providers.values():
            if hasattr(provider, 'cleanup'):
                try:
                    await provider.cleanup()
                except Exception as e:
                    logging.error(f"Error cleaning up provider: {str(e)}")

def display_menu():
    console = Console()
    console.print("\n[bold cyan]Market Data Comparison Tool[/bold cyan]")
    console.print("\n1. Compare Stock Prices")
    console.print("2. Compare Option Chains")
    console.print("3. Compare Historical Data")
    console.print("4. Exit")
    return console.input("\nSelect an option (1-4): ")

def get_symbol():
    return Console().input("\nEnter symbol (e.g., AAPL): ").upper()

def get_option_input() -> tuple:
    """Get option input either by contract symbol or individual components"""
    console = Console()
    contract = None  # Initialize contract variable
    
    # Ask user for input method
    choice = console.input("\nEnter option data by:\n1. Contract Symbol (e.g., AAPL240119C00180000)\n2. Symbol and Expiration\nChoice (1/2): ")
    
    if choice == "1":
        while True:
            contract = console.input("\nEnter option contract symbol: ").upper()
            # Validate contract symbol format
            if len(contract) >= 15:  # Basic length check
                try:
                    # Parse contract symbol using regex for more reliable parsing
                    pattern = r'^([A-Z]+)(\d{2})(\d{2})(\d{2})([CP])(\d+)$'
                    match = re.match(pattern, contract)
                    
                    if match:
                        symbol, year, month, day, option_type, strike_str = match.groups()
                        strike = float(strike_str) / 1000  # Convert strike to decimal
                        
                        # Convert date components to full date
                        expiry = datetime.strptime(f"20{year}{month}{day}", '%Y%m%d').strftime('%Y-%m-%d')
                        
                        logging.info(f"Parsed contract: Symbol={symbol}, Expiry={expiry}, Type={'call' if option_type == 'C' else 'put'}, Strike={strike}")
                        return symbol, expiry, 'call' if option_type == 'C' else 'put', strike, contract
                    else:
                        console.print("[red]Invalid contract symbol format. Expected format: SYMBOL[YY][MM][DD][C/P][STRIKE][000][/red]")
                except Exception as e:
                    console.print(f"[red]Error parsing contract symbol: {str(e)}[/red]")
            else:
                console.print("[red]Contract symbol too short. Expected format: SYMBOL[YY][MM][DD][C/P][STRIKE][000][/red]")
    
    elif choice == "2":
        # Original method
        symbol = console.input("\nEnter symbol (e.g., AAPL): ").upper()
        expiry = console.input("Enter expiration date (YYYY-MM-DD) or press Enter for nearest: ")
        return symbol, expiry, None, None, None
    
    else:
        console.print("[red]Invalid choice. Defaulting to symbol and expiration method.[/red]")
        return get_option_input()

def display_stock_comparison(df: pd.DataFrame):
    console = Console()
    if df.empty:
        console.print("\n[bold red]No data available from any provider.[/bold red]")
        return
        
    table = Table(title=f"Stock Price Comparison")
    
    # Define columns and their display names
    column_config = [
        ('Provider', 'Provider'),
        ('Symbol', 'Symbol'),
        ('Price', 'Price'),
        ('Timestamp', 'Timestamp'),
        ('Error', 'Error')  # Optional column
    ]
    
    # Add columns that exist in the DataFrame
    for col_name, display_name in column_config:
        if col_name in df.columns:
            table.add_column(display_name)
    
    # Add rows
    for _, row in df.iterrows():
        row_values = []
        for col_name, _ in column_config:
            if col_name in df.columns:
                value = row[col_name]
                # Format specific columns
                if col_name == 'Price' and pd.notnull(value):
                    value = f"${value:.2f}"
                elif col_name == 'Timestamp':
                    value = value.strftime("%Y-%m-%d %H:%M:%S")
                row_values.append(str(value) if pd.notnull(value) else '')
        table.add_row(*row_values)
    
    console.print(table)

def display_option_comparison(chains: Dict[str, pd.DataFrame], symbol: str, specific_strike: float = None):
    """Display option chain comparison with auto-sized columns"""
    console = Console(force_terminal=True, width=2000)
    
    for chain_type, df in chains.items():
        if df.empty:
            console.print(f"\n[yellow]No {chain_type} data available[/yellow]")
            continue
            
        # Filter for specific strike if provided
        if specific_strike is not None:
            df = df[df['strike'] == specific_strike]
            if df.empty:
                console.print(f"\n[yellow]No data found for strike price {specific_strike} in {chain_type}[/yellow]")
                continue
        
        # Create table with all columns from the provider
        table = Table(
            title=f"{chain_type.upper()} Options for {symbol}",
            show_header=True,
            header_style="bold cyan",
            show_lines=True,
            padding=(0, 2)
        )
        
        # Add all columns from the DataFrame
        for col in df.columns:
            table.add_column(col)
        
        # Add rows with raw values
        for _, row in df.iterrows():
            table.add_row(*[str(val) for val in row])
        
        console.print(table)
        console.print("\n")

def main():
    # Set up logging
    logging.basicConfig(level=logging.INFO)
    
    try:
        comparator = MarketDataComparator()
        console = Console()
        
        while True:
            choice = display_menu()
            
            if choice == "1":
                symbol = get_symbol()
                with console.status(f"Fetching stock prices for {symbol}..."):
                    df = asyncio.run(comparator.compare_stock_price(symbol))
                display_stock_comparison(df)
                
            elif choice == "2":
                symbol, expiry, option_type, strike, contract = get_option_input()
                with console.status(f"Fetching option chains for {symbol}..."):
                    chains = comparator.compare_option_chain(symbol, expiry)
                    
                    # If option_type is specified (from contract symbol), filter the chains
                    if option_type:
                        if option_type == 'call':
                            chains = {'calls': chains['calls']}
                        else:
                            chains = {'puts': chains['puts']}
                            
                display_option_comparison(chains, symbol, strike)
                
            elif choice == "3":
                symbol = get_symbol()
                days = console.input("Enter number of days to look back (default: 7): ")
                days = int(days) if days else 7
                
                end_date = datetime.now()
                start_date = end_date - pd.Timedelta(days=days)
                
                with console.status(f"Fetching historical data for {symbol}..."):
                    df = comparator.compare_historical_data(symbol, start_date, end_date)
                
                console.print(df)
                
            elif choice == "4":
                console.print("\n[bold green]Goodbye![/bold green]")
                # Cleanup before exit
                asyncio.run(comparator.cleanup())
                break
                
            else:
                console.print("\n[bold red]Invalid choice. Please try again.[/bold red]")
            
            time.sleep(1)  # Brief pause before showing menu again
            
    except Exception as e:
        logging.error("Main loop error", exc_info=True)
        Console().print(f"\n[bold red]An error occurred: {str(e)}[/bold red]")
    finally:
        # Clean up any async resources
        if 'comparator' in locals():
            asyncio.run(comparator.cleanup())

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        Console().print("\n[bold red]Program terminated by user.[/bold red]")
    except Exception as e:
        Console().print(f"\n[bold red]An error occurred: {str(e)}[/bold red]")
