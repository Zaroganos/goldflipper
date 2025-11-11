import os
import json
import re
from datetime import datetime
import platform
import subprocess
import yaml
import sys

# Add the project root to the Python path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(project_root)

from goldflipper.utils.display import TerminalDisplay

def get_input(prompt, input_type=str, validation=None, error_message="Invalid input. Please try again.", optional=False):
    """
    Helper function to get validated input from the user.

    Parameters:
    - prompt (str): The message to show the user.
    - input_type (type): The type to convert the input into (e.g., int, float, str).
    - validation (function): A function that takes the input and returns True if valid, False otherwise.
    - error_message (str): The message to show if validation fails.
    - optional (bool): If True, allows the user to skip input by entering nothing.

    Returns:
    - The validated input converted to input_type, or None if optional and skipped.
    """
    while True:
        user_input = input(prompt).strip()
        if optional and user_input == "":
            return None
        try:
            converted_input = input_type(user_input)
            if validation and not validation(converted_input):
                TerminalDisplay.error(error_message, show_timestamp=False)
            else:
                return converted_input
        except ValueError:
            TerminalDisplay.error(error_message, show_timestamp=False)

def validate_choice(choice, options):
    """
    Validates if the user's choice is within the allowed options.

    Parameters:
    - choice (str): The user's choice.
    - options (list): The list of allowed options.

    Returns:
    - bool: True if valid, False otherwise.
    """
    return choice.upper() in options

def sanitize_filename(name):
    """
    Sanitize the filename by removing or replacing invalid characters.

    Parameters:
    - name (str): The original filename.

    Returns:
    - str: The sanitized filename.
    """
    # Remove any character that is not alphanumeric, underscore, or hyphen
    sanitized = re.sub(r'[^\w\-]', '_', name)
    return sanitized

def clean_ticker_symbol(symbol):
    """
    Clean a ticker symbol by removing leading '$' and converting to uppercase.
    
    Args:
        symbol (str): The ticker symbol to clean
        
    Returns:
        str: The cleaned ticker symbol
    """
    return symbol.strip().lstrip('$').upper()

def create_option_contract_symbol(symbol, expiration_date, strike_price, trade_type):
    """
    Generate the option contract symbol based on user inputs.
    Format: {SYMBOL}{YYMMDD}{C/P}{STRIKE_PRICE_PADDED}
    Example: SPY240621P00550000 (for $550.00 strike price)
    """
    try:
        # Parse and format the expiration date
        exp_date = datetime.strptime(expiration_date, "%m/%d/%Y")
        formatted_date = exp_date.strftime("%y%m%d")
    except ValueError:
        raise ValueError("Invalid expiration date format. Please use MM/DD/YYYY.")

    # Determine the option type (Call or Put)
    option_type = "C" if trade_type.upper() == "CALL" else "P"

    try:
        # Convert strike price to tenths of cents by multiplying by 1000
        strike_tenths_cents = int(round(float(strike_price) * 1000))
    except ValueError:
        raise ValueError("Invalid strike price. Please enter a numeric value.")

    # Format as an 8-digit number with leading zeros
    padded_strike = f"{strike_tenths_cents:08d}"

    # Clean the symbol
    cleaned_symbol = clean_ticker_symbol(symbol)

    # Assemble the final option contract symbol
    final_symbol = f"{cleaned_symbol}{formatted_date}{option_type}{padded_strike}"

    return final_symbol

def get_price_condition_type():
    """Get user's choice for price condition type."""
    print("\nSelect price condition type(s):")
    print("1. Stock price (absolute value)")
    print("2. Option premium %")
    print("3. Stock price % movement")
    print("Enter your choices (separated by space, comma, or dash). Examples: '1 2 3' or '1,2' or '1-3'")
    
    while True:
        user_input = get_input(
            "Choice(s): ",
            str,
            validation=lambda x: True,  # We'll validate the parsed result
            error_message="Invalid input format."
        ).strip()
        
        # Parse the input
        try:
            choices = set()
            # Split by comma first, then handle each part
            for part in user_input.replace(' ', ',').split(','):
                if '-' in part:
                    # Handle range (e.g., "1-3")
                    start, end = map(int, part.split('-'))
                    choices.update(range(start, end + 1))
                elif part:  # Skip empty parts
                    choices.add(int(part))
            
            # Validate choices
            if not choices:
                print("Please select at least one option.")
                continue
                
            if not all(1 <= choice <= 3 for choice in choices):
                print("Choices must be between 1 and 3.")
                continue
                
            return sorted(list(choices))  # Return sorted list of unique choices
            
        except ValueError:
            print("Invalid input format. Please use numbers 1-3 separated by space, comma, or dash.")
            continue

def get_premium_percentage():
    """Get premium percentage from user."""
    return get_input(
        "Enter the premium percentage: ",
        float,
        validation=lambda x: 0 < x <= 100,
        error_message="Please enter a percentage between 0 and 100. If you want a higher %, ask iliya to code it in."
    )

def get_order_type_choice(is_stop_loss=False, transaction_type=""):
    """Get user's choice for order type (market/limit).
    
    Args:
        is_stop_loss (bool): If True, adds warning about market orders being safer for SL
        transaction_type (str): The type of transaction (Entry, Take Profit, Stop Loss)
    """
    prompt = f"\nSelect order type for {transaction_type}:"
    prompt += "\n1. Market order"
    prompt += "\n2. Limit order at bid price (default)"
    prompt += "\n3. Limit order at last traded price"
    prompt += "\n4. Limit order at ask price"
    prompt += "\n5. Limit order at mid price (between bid and ask)"
    prompt += "\nChoice (1/2/3/4/5) [2]: "
    
    choice = get_input(
        prompt,
        int,
        validation=lambda x: x in [1, 2, 3, 4, 5],
        error_message="Please enter 1 for market, 2 for limit at bid, 3 for limit at last, 4 for limit at ask, or 5 for limit at mid.",
        optional=True
    )
    
    # If optional input is skipped (None returned), default to 2 (limit at bid)
    if choice is None:
        return 'limit at bid'
    return {
        1: 'market',
        2: 'limit at bid',
        3: 'limit at last',
        4: 'limit at ask',
        5: 'limit at mid'
    }[choice]

def get_sl_type_choice():
    """Get user's choice for stop loss execution type (STOP/LIMIT/CONTINGENCY)."""
    print("\nSelect Stop Loss Type:")
    print("1. Stop (market order when price is hit)")
    print("2. Limit (limit order when price is hit)")
    print("3. Contingency (primary limit order with backup market order at a worse price)")
    
    return get_input(
        "Choice (1/2/3): ",
        int,
        validation=lambda x: x in [1, 2, 3],
        error_message="Please enter 1 for 'Stop' (Market Order), 2 for 'Limit' (Limit Order), or 3 for 'Contingency' (Primary Limit Order with backup Market Order)."
    )

def validate_contingency_prices(main_price, backup_price, is_stock_price, trade_type):
    """
    Validate that the backup price is worse than the main price.
    
    Args:
        main_price (float): Primary stop loss price
        backup_price (float): Backup/safety stop loss price
        is_stock_price (bool): True if validating stock prices, False for premium percentages
        trade_type (str): 'CALL' or 'PUT'
    
    Returns:
        bool: True if valid, False if invalid
    """
    if is_stock_price:
        if trade_type == 'CALL':
            return backup_price < main_price  # Lower stock price is worse for calls
        else:  # PUT
            return backup_price > main_price  # Higher stock price is worse for puts
    else:  # Premium percentage
        return backup_price > main_price  # Higher percentage means bigger loss

def get_multiple_tp_choice():
    """Get user's choice for using multiple take profits."""
    return get_input(
        "\nWould you like to set multiple Take Profit levels? (Y/N): ",
        str,
        validation=lambda x: x.upper() in ['Y', 'N'],
        error_message="Please enter Y or N."
    ).upper() == 'Y'

def get_number_of_tps():
    """Get the number of take profit levels desired."""
    return get_input(
        "\nHow many Take Profit levels would you like to set? (2-5): ",
        int,
        validation=lambda x: 2 <= x <= 5,
        error_message="Please enter a number between 2 and 5."
    )

class FileHandler:
    """Handles file operations for play configurations."""
    
    def __init__(self, base_dir=None):
        if base_dir is None:
            self.base_dir = os.path.join(project_root, 'plays')
        else:
            self.base_dir = base_dir
        
        # Ensure the plays directory exists
        os.makedirs(self.base_dir, exist_ok=True)
    
    def save_play(self, play, filename):
        """Save the play configuration to a JSON file."""
        filepath = os.path.join(self.base_dir, filename)
        
        try:
            with open(filepath, 'w') as f:
                json.dump(play, f, indent=4)
            TerminalDisplay.success(f"Play saved successfully to: {filepath}", show_timestamp=False)
            return True
        except Exception as e:
            TerminalDisplay.error(f"Error saving play: {str(e)}", show_timestamp=False)
            return False

class PlayBuilder:
    """Handles the construction and validation of option play configurations."""
    
    def __init__(self, strategy_choice: str = "1"):
        """
        Initialize PlayBuilder.
        
        Args:
            strategy_choice: Strategy choice ("1" for Option Swings, "2" for Short Puts)
        """
        self.play = {}
        self.settings = self._load_settings()
        self.file_handler = FileHandler()
        self.tp_cache = []  # Cache for storing multiple TP configurations
        self.strategy_choice = strategy_choice
    
    def _load_settings(self):
        """Load settings from yaml file."""
        settings_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'settings.yaml')
        
        try:
            if not os.path.exists(settings_path):
                TerminalDisplay.error(f"Settings file not found at: {settings_path}", show_timestamp=False)
                raise FileNotFoundError(f"Settings file not found at: {settings_path}")

            with open(settings_path, 'r') as f:
                settings = yaml.safe_load(f)
                
            # Validate essential settings structure
            if not isinstance(settings, dict):
                raise ValueError("Settings file must contain a valid YAML dictionary")
                
            # Validate required settings sections
            required_sections = ['options_swings']
            missing_sections = [section for section in required_sections if section not in settings]
            
            if missing_sections:
                raise ValueError(f"Missing required settings sections: {', '.join(missing_sections)}")
                
            # Validate Take_Profit settings
            if 'Take_Profit' not in settings.get('options_swings', {}):
                TerminalDisplay.warning("Take_Profit settings not found. Multiple TPs will be disabled.", show_timestamp=False)
                settings['options_swings']['Take_Profit'] = {'multiple_TPs': False}
                
            return settings
            
        except yaml.YAMLError as e:
            TerminalDisplay.error(f"Error parsing settings file: {e}", show_timestamp=False)
            # Return default settings
            return {'options_swings': {'Take_Profit': {'multiple_TPs': False}}}
            
        except Exception as e:
            TerminalDisplay.error(f"Unexpected error loading settings: {e}", show_timestamp=False)
            # Return default settings
            return {'options_swings': {'Take_Profit': {'multiple_TPs': False}}}
    
    def build_base_play(self):
        """Collect and validate basic play information."""
        # Branch based on strategy choice
        if self.strategy_choice == "2":
            # Short Puts strategy
            return self.build_short_put_play()
        else:
            # Option Swings strategy (existing logic)
            return self._build_option_swings_play()
    
    def _build_option_swings_play(self):
        """Build Option Swings play (existing LONG strategy)."""
        raw_symbol = get_input(
            "Enter the ticker symbol (e.g., SPY or $SPY): ",
            str,
            validation=lambda x: len(x) > 0,
            error_message="Ticker symbol cannot be empty."
        )
        self.play['symbol'] = clean_ticker_symbol(raw_symbol)

        self.play['trade_type'] = get_input(
            "Enter the trade type (CALL or PUT): ",
            str,
            validation=lambda x: validate_choice(x, ["CALL", "PUT"]),
            error_message="Invalid trade type. Please enter 'CALL' or 'PUT'."
        ).upper()

        # Entry point setup
        TerminalDisplay.info("\nSetting Entry Point Parameters:", show_timestamp=False)
        self.play['entry_point'] = {}
        self.play['entry_point']['stock_price'] = get_input(
            "Enter the entry stock price: ",
            float,
            error_message="Please enter a valid number for the entry price."
        )
        self.play['entry_point']['order_type'] = get_order_type_choice(transaction_type="Entry")

        self._add_strike_price()
        self._add_expiration_date()
        self._add_contracts()
        self._generate_contract_symbol()
        self._set_play_name()
        self._add_play_class()
        self._add_play_metadata()
        
        # Set position side for Option Swings
        self.play['position_side'] = 'LONG'

        return self.play
    
    def _add_strike_price(self):
        """Add strike price to the play configuration."""
        self.play['strike_price'] = str(get_input(
            "Enter the strike price: ",
            float,
            error_message="Please enter a valid number for the strike price."
        ))

    def _add_expiration_date(self):
        """Add expiration date to the play configuration."""
        self.play['expiration_date'] = get_input(
            "Enter the option contract expiration date (MM/DD/YYYY): ",
            str,
            validation=lambda x: datetime.strptime(x, "%m/%d/%Y"),
            error_message="Please enter a valid date in MM/DD/YYYY format."
        )

    def _add_contracts(self):
        """Add number of contracts to the play configuration."""
        self.play['contracts'] = get_input(
            "Enter the number of contracts: ",
            int,
            validation=lambda x: x > 0,
            error_message="Please enter a positive integer for the number of contracts."
        )

    def _generate_contract_symbol(self):
        """Generate and add the option contract symbol to the play configuration."""
        try:
            self.play['option_contract_symbol'] = create_option_contract_symbol(
                self.play['symbol'],
                self.play['expiration_date'],
                self.play['strike_price'],
                self.play['trade_type']
            )
            TerminalDisplay.success(f"Generated option contract symbol: {self.play['option_contract_symbol']}", show_timestamp=False)
        except ValueError as ve:
            TerminalDisplay.error(f"Error generating option contract symbol: {ve}", show_timestamp=False)
            raise

    def _set_play_name(self, play_name_input=None):
        """Set the play name and generate filename."""
        if play_name_input is None:
            play_name_input = get_input(
                "Enter the play's name (optional, press Enter to skip): ",
                str,
                validation=lambda x: True,
                error_message="Invalid input.",
                optional=True
            )

        if play_name_input:
            self.play['play_name'] = play_name_input
            self.filename = sanitize_filename(self.play['play_name']) + ".json"
        else:
            system_time = datetime.now().strftime('%Y%m%d_%H%M%S')
            default_name = f"{self.play['option_contract_symbol']}_{system_time}"
            self.play['play_name'] = default_name
            self.filename = default_name + ".json"
        
        TerminalDisplay.success(f"Generated play name: {self.play['play_name']}", show_timestamp=False)
    
    def get_tp_parameters(self, tp_number=None, total_tps=None, total_contracts=None):
        """Get take profit parameters from user.
        
        Args:
            tp_number (int, optional): The current TP number (for multiple TPs)
            total_tps (int, optional): Total number of TPs being created
            total_contracts (int, optional): Total number of contracts available
        
        Returns:
            dict: Take profit parameters
        """
        tp_data = {}  # Initialize empty dict instead of one with null values

        if tp_number is not None:
            print(f"\nSetting Take Profit #{tp_number} of {total_tps}")
            tp_data['TP_number'] = tp_number
            tp_data['total_TPs'] = total_tps

            # Handle contracts allocation for this TP level
            remaining_tps = total_tps - tp_number + 1
            remaining_contracts = total_contracts - sum(tp['contracts'] for tp in self.tp_cache)
            
            while True:
                if tp_number == total_tps:  # Last TP level
                    tp_contracts = remaining_contracts
                    print(f"Automatically allocating remaining {tp_contracts} contract(s) to final TP level")
                else:
                    tp_contracts = get_input(
                        f"Enter number of contracts for TP #{tp_number} ({remaining_contracts} remaining, {remaining_tps} TP levels left): ",
                        int,
                        validation=lambda x: 0 < x <= remaining_contracts,
                        error_message=f"Please enter a number between 1 and {remaining_contracts}"
                    )
                
                if tp_contracts <= remaining_contracts:
                    tp_data['contracts'] = tp_contracts
                    break
                
                print(f"Error: Cannot allocate more contracts than remaining ({remaining_contracts})")

        tp_price_types = get_price_condition_type()

        if 1 in tp_price_types:  # Absolute stock price
            tp_stock_price = get_input(
                f"Enter take profit stock price{f' #{tp_number}' if tp_number else ''}: ",
                float,
                validation=lambda x: x > 0,
                error_message="Please enter a valid positive number for the take profit stock price."
            )
            tp_data['stock_price'] = tp_stock_price

        if 3 in tp_price_types:  # Stock price % movement
            tp_stock_price_pct = get_input(
                f"Enter take profit stock price percentage movement{f' #{tp_number}' if tp_number else ''}: ",
                float,
                validation=lambda x: x > 0,
                error_message="Please enter a valid positive percentage"
            )
            tp_data['stock_price_pct'] = tp_stock_price_pct

        if 2 in tp_price_types:  # Option premium %
            tp_premium_pct = get_premium_percentage()
            tp_data['premium_pct'] = tp_premium_pct

        # Always set order type
        tp_data['order_type'] = get_order_type_choice(
            transaction_type=f"Take Profit{f' #{tp_number}' if tp_number else ''}"
        )

        return tp_data

    def add_take_profits(self):
        """Add take profit configuration to the play."""
        TerminalDisplay.header("Take Profit Configuration", show_timestamp=False)
        
        multiple_tps_enabled = self.settings.get('options_swings', {}).get('Take_Profit', {}).get('multiple_TPs', False)
        
        if multiple_tps_enabled and get_multiple_tp_choice():
            self._handle_multiple_take_profits()
        else:
            self.tp_cache = [self.get_tp_parameters()]  # Single TP stored in cache
        
        # Trailing prompt (per-play): optional override for activation threshold
        trailing_input = get_input(
            "\nTrailing activation (prem%): leave blank to disable trailing for this play, enter % (e.g., 50) to enable, or 'x'/'y' for default: ",
            str,
            validation=lambda x: True,
            error_message="Invalid input.",
            optional=True
        )
        tp_section = self.tp_cache[0] if self.tp_cache else {}
        if trailing_input is not None and trailing_input != "":
            val = trailing_input.strip().lower()
            if val in ("x", "y"):
                # Use global default; mark enabled
                tp_section.setdefault('trailing_config', {})['enabled'] = True
                # Do not set per-play threshold so global applies
            else:
                try:
                    pct = float(val)
                    if pct > 0:
                        tp_section.setdefault('trailing_config', {})['enabled'] = True
                        # Store per-play override used by trailing manager
                        tp_section['trailing_activation_pct'] = pct
                except ValueError:
                    TerminalDisplay.warning("Ignoring trailing input; not a number/x/y.", show_timestamp=False)
        # Persist back
        if self.tp_cache:
            self.tp_cache[0] = tp_section
        
        return self.play

    def _handle_multiple_take_profits(self):
        """Handle configuration of multiple take profit levels."""
        num_tps = get_number_of_tps()
        total_contracts = self.play['contracts']  # Get total contracts from base play
        
        for i in range(num_tps):
            tp_data = self.get_tp_parameters(tp_number=i+1, total_tps=num_tps, total_contracts=total_contracts)
            self.tp_cache.append(tp_data)
        
        # Remove the contracts from the base play since they're now distributed across TPs
        del self.play['contracts']
    
    def add_stop_loss(self):
        """Add stop loss configuration to the play."""
        TerminalDisplay.header("Stop Loss Configuration", show_timestamp=False)
        
        sl_price_types = get_price_condition_type()
        sl_type = get_sl_type_choice()
        
        sl_data = {
            'SL_type': 'STOP' if sl_type == 1 else 'LIMIT' if sl_type == 2 else 'CONTINGENCY'
        }
        
        if sl_data['SL_type'] in ['STOP', 'LIMIT']:
            # Single set of conditions
            if 1 in sl_price_types:  # Absolute stock price
                sl_stock_price = get_input(
                    "Enter stop loss stock price: ",
                    float,
                    validation=lambda x: x > 0,
                    error_message="Please enter a valid positive number for the stop loss stock price."
                )
                sl_data['stock_price'] = sl_stock_price

            if 3 in sl_price_types:  # Stock price % movement
                sl_stock_price_pct = get_input(
                    "Enter stop loss stock price percentage movement: ",
                    float,
                    validation=lambda x: x > 0,
                    error_message="Please enter a valid positive percentage"
                )
                sl_data['stock_price_pct'] = sl_stock_price_pct

            if 2 in sl_price_types:  # Option premium %
                sl_premium_pct = get_premium_percentage()
                sl_data['premium_pct'] = sl_premium_pct

        else:  # CONTINGENCY type needs two sets of conditions
            if 1 in sl_price_types:  # Absolute stock price
                TerminalDisplay.info("\nEnter main stop loss conditions:", show_timestamp=False)
                main_stock_price = get_input(
                    "Enter main stop loss stock price: ",
                    float,
                    validation=lambda x: x > 0,
                    error_message="Please enter a valid positive number for the main stop loss stock price."
                )
                
                while True:
                    TerminalDisplay.info("\nEnter backup/safety stop loss conditions (must be worse than main price):", show_timestamp=False)
                    backup_stock_price = get_input(
                        f"Enter backup stop loss stock price ({'lower' if self.play['trade_type'] == 'CALL' else 'higher'} than {main_stock_price}): ",
                        float,
                        validation=lambda x: x > 0,
                        error_message="Please enter a valid positive number for the backup stop loss stock price."
                    )
                    
                    if validate_contingency_prices(main_stock_price, backup_stock_price, True, self.play['trade_type']):
                        break
                    TerminalDisplay.error(f"Error: Backup price must be {'lower' if self.play['trade_type'] == 'CALL' else 'higher'} than the main price ({main_stock_price}) for a {self.play['trade_type']}", show_timestamp=False)
                
                sl_data['stock_price'] = main_stock_price
                sl_data['contingency_stock_price'] = backup_stock_price

            if 3 in sl_price_types:  # Stock price % movement
                TerminalDisplay.info("\nEnter main stop loss conditions:", show_timestamp=False)
                main_stock_price_pct = get_input(
                    "Enter main stop loss stock price percentage movement: ",
                    float,
                    validation=lambda x: x > 0,
                    error_message="Please enter a valid positive percentage"
                )
                
                while True:
                    TerminalDisplay.info("\nEnter backup/safety stop loss conditions (must represent a bigger movement):", show_timestamp=False)
                    backup_stock_price_pct = get_input(
                        "Enter backup stop loss stock price percentage movement (must be higher than main %): ",
                        float,
                        validation=lambda x: x > main_stock_price_pct,
                        error_message=f"Please enter a percentage higher than {main_stock_price_pct}%"
                    )
                    
                    if backup_stock_price_pct > main_stock_price_pct:
                        break
                    TerminalDisplay.error(f"Error: Backup percentage ({backup_stock_price_pct}%) must be higher than main percentage ({main_stock_price_pct}%)", show_timestamp=False)
                
                sl_data['stock_price_pct'] = main_stock_price_pct
                sl_data['contingency_stock_price_pct'] = backup_stock_price_pct

            if 2 in sl_price_types:  # Option premium %
                TerminalDisplay.info("\nEnter main stop loss conditions:", show_timestamp=False) if len(sl_price_types) == 1 else None
                main_premium = get_premium_percentage()
                
                while True:
                    TerminalDisplay.info("\nEnter backup/safety stop loss conditions (must represent a bigger loss):", show_timestamp=False)
                    TerminalDisplay.info(f"Current main stop loss is at {main_premium}% loss from entry", show_timestamp=False)
                    TerminalDisplay.info(f"Backup must be higher than {main_premium}% (representing a bigger loss)", show_timestamp=False)
                    backup_premium = get_premium_percentage()
                    
                    if validate_contingency_prices(main_premium, backup_premium, False, self.play['trade_type']):
                        break
                    TerminalDisplay.error(f"Error: Backup loss percentage ({backup_premium}%) must be higher than main loss percentage ({main_premium}%) to represent a bigger loss", show_timestamp=False)
                
                sl_data['premium_pct'] = main_premium
                sl_data['contingency_premium_pct'] = backup_premium

        # Set order type(s) based on SL_type
        if sl_data['SL_type'] == 'STOP':
            sl_data['order_type'] = 'market'
        elif sl_data['SL_type'] == 'LIMIT':
            sl_data['order_type'] = get_order_type_choice(is_stop_loss=True, transaction_type="Stop Loss")
        else:  # CONTINGENCY
            # For contingency, we need to let user choose between 'limit at bid' and 'limit at last' for primary order
            primary_order_type = get_order_type_choice(is_stop_loss=True, transaction_type="Primary Stop Loss")
            sl_data['order_type'] = [primary_order_type, 'market']  # Second order always market

        self.play['stop_loss'] = sl_data
        return self.play
    
    def _add_play_class(self):
        """Add play class by determining if it should go to NEW or TEMP folder."""
        TerminalDisplay.info("\nConditional Plays:", show_timestamp=False)
        TerminalDisplay.info("- NEW: For standalone play, or play that will become primary class (default)", show_timestamp=False)
        TerminalDisplay.info("- TEMP: For play activated by position opening trigger of other play(s) (OTO plays)", show_timestamp=False)
        TerminalDisplay.info("\nNote: To set up OCO/OTO relationships between plays, use the Play Edit Tool after creation.", show_timestamp=False)

        storage_choice = get_input(
            "\nWhere should this play be stored? (NEW/TEMP) or press Enter for NEW: ",
            str,
            validation=lambda x: x.upper() in ["NEW", "TEMP", ""] if x else True,  # Allow empty string
            error_message="Please enter either 'NEW', 'TEMP', or press Enter.",
            optional=True
        )

        # If no input (Enter pressed) or explicitly "NEW", set to NEW
        if not storage_choice or storage_choice.upper() == "NEW":  # Handle None case
            self.play['play_class'] = "SIMPLE"  # Can be changed to PRIMARY later in edit tool
        else:  # TEMP
            self.play['play_class'] = "OTO"     # Will be linked to a primary play later

        # Initialize empty conditional_plays dict (relationships will be set in edit tool)
        self.play['conditional_plays'] = {}

    def build_short_put_play(self):
        """Build Short Puts play using automated option selection."""
        from goldflipper.strategy.short_puts import find_short_put_option
        from goldflipper.config.config import config
        from goldflipper.data.market.manager import MarketDataManager
        
        TerminalDisplay.header("Short Puts Strategy - Play Creation", show_timestamp=False)
        
        # Get symbol (default to SPY if configured)
        short_puts_config = config.get('short_puts', {})
        default_symbol = short_puts_config.get('default_symbol', 'SPY')
        
        raw_symbol = get_input(
            f"Enter the ticker symbol (e.g., SPY or $SPY) [default: {default_symbol}]: ",
            str,
            validation=lambda x: len(x) > 0,
            error_message="Ticker symbol cannot be empty.",
            optional=True
        )
        
        if not raw_symbol:
            raw_symbol = default_symbol
        
        symbol = clean_ticker_symbol(raw_symbol)
        self.play['symbol'] = symbol
        
        # Set trade type to PUT for short puts
        self.play['trade_type'] = 'PUT'
        
        # Get number of contracts
        self._add_contracts()
        
        # Find matching short put option
        TerminalDisplay.info(f"Searching for matching short put option for {symbol}...", show_timestamp=False)
        market_data_manager = MarketDataManager()
        
        target_dte = short_puts_config.get('target_dte', 45)
        target_delta = short_puts_config.get('target_delta', 0.30)
        iv_rank_threshold = short_puts_config.get('iv_rank_threshold', 50)
        
        option_data = find_short_put_option(
            symbol,
            target_dte=target_dte,
            target_delta=target_delta,
            iv_rank_threshold=iv_rank_threshold,
            market_data_manager=market_data_manager
        )
        
        if not option_data:
            TerminalDisplay.error(f"Could not find a matching short put option for {symbol}. Please check entry conditions.", show_timestamp=False)
            raise ValueError(f"No matching short put option found for {symbol}")
        
        # Populate play with option data
        self.play['strike_price'] = option_data['strike_price']
        self.play['expiration_date'] = option_data['expiration_date_formatted']
        self.play['option_contract_symbol'] = option_data['option_contract_symbol']
        
        # Entry point setup for SHORT positions (SELL to open)
        TerminalDisplay.info("\nSetting Entry Point Parameters:", show_timestamp=False)
        current_price = market_data_manager.get_stock_price(symbol)
        
        self.play['entry_point'] = {
            'stock_price': current_price,
            'order_type': 'limit at ask',  # For SHORT: sell at ask (receive premium)
            'entry_credit': option_data['ask']  # Store credit received (for SHORT positions)
        }
        
        # Set position side to SHORT
        self.play['position_side'] = 'SHORT'
        
        # Set play name
        self._set_play_name()
        
        # Set play class (always SIMPLE for short puts initially)
        self.play['play_class'] = 'SIMPLE'
        self.play['conditional_plays'] = {}
        
        # Add play metadata
        self.play['strategy'] = 'Short Puts'
        self.play['creation_date'] = datetime.now().strftime('%Y-%m-%d')
        self.play['creator'] = 'user'
        
        # Set play expiration date (same as option expiration)
        self.play['play_expiration_date'] = option_data['expiration_date_formatted']
        
        # Initialize status
        self.play['status'] = {
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
        }
        
        TerminalDisplay.success(f"Short put option selected: {option_data['option_contract_symbol']}", show_timestamp=False)
        TerminalDisplay.info(f"  Strike: ${option_data['strike_price']}, DTE: {option_data['dte']}, "
                           f"Delta: {option_data['abs_delta']:.3f}, IV Rank: {option_data['iv_rank']:.1f}%", show_timestamp=False)
        
        return self.play
    
    def _add_play_metadata(self):
        """Add strategy, creation date, and status information."""
        # Only set strategy if not already set (for short puts)
        if 'strategy' not in self.play:
            self.play['strategy'] = (
                'Option Swings' if self.play['play_class'] == 'SIMPLE' else
                'Branching Brackets Option Swings'
            )
        # Only set creation_date and creator if not already set
        if 'creation_date' not in self.play:
            self.play['creation_date'] = datetime.now().strftime('%Y-%m-%d')
        if 'creator' not in self.play:
            self.play['creator'] = 'user'

        # Only set status if not already set (for short puts)
        if 'status' not in self.play:
            play_status = 'TEMP' if self.play['play_class'] == 'OTO' else 'NEW'
            self.play['status'] = {
                "play_status": play_status,
                "order_id": None,
                "order_status": None,
                "position_exists": False,
                "last_checked": None,
                "closing_order_id": None,
                "closing_order_status": None,
                "contingency_order_id": None,
                "contingency_order_status": None,
                "conditionals_handled": False
            }

        # Add play expiration date
        self.play['play_expiration_date'] = get_input(
            f"Enter the play's expiration date (MM/DD/YYYY), or press Enter to make it {self.play['expiration_date']} by default.): ",
            str,
            validation=lambda x: datetime.strptime(x, "%m/%d/%Y"),  # Validates date format
            error_message="Please enter a valid date in MM/DD/YYYY format.",
            optional=True
        )
        
        # Set default to previously entered expiration_date if no input is provided
        if not self.play['play_expiration_date']:
            self.play['play_expiration_date'] = self.play['expiration_date']
        
        TerminalDisplay.success(f"Set play expiration date: {self.play['play_expiration_date']}", show_timestamp=False)

    def _add_short_put_tp_sl(self):
        """Add take profit and stop loss for Short Puts strategy based on configuration."""
        from goldflipper.config.config import config
        
        short_puts_config = config.get('short_puts', {})
        profit_target_pct = short_puts_config.get('profit_target_pct', 50.0)
        stop_loss_enabled = short_puts_config.get('stop_loss_enabled', True)
        stop_loss_multiplier = short_puts_config.get('stop_loss_multiplier', 2.0)
        
        entry_credit = self.play['entry_point'].get('entry_credit', 0.0)
        
        # Take Profit: 50% of premium (premium decreases)
        # For SHORT: TP triggers when premium drops to 50% of entry credit
        tp_premium_target = entry_credit * (1 - profit_target_pct / 100.0)
        
        take_profit = {
            'premium_pct': profit_target_pct,
            'order_type': 'limit at bid',  # For SHORT: buy back at bid (close position)
            'TP_option_prem': tp_premium_target
        }
        
        # Add to cache for save() method
        self.tp_cache = [take_profit]
        
        # Stop Loss: 2x premium (premium increases)
        if stop_loss_enabled:
            sl_premium_target = entry_credit * stop_loss_multiplier
            stop_loss = {
                'premium_pct': (stop_loss_multiplier - 1.0) * 100.0,  # Percentage loss
                'order_type': 'market',  # Market order for stop loss
                'SL_type': 'STOP',
                'SL_option_prem': sl_premium_target
            }
            self.play['stop_loss'] = stop_loss
        else:
            self.play['stop_loss'] = None
        
        TerminalDisplay.info(f"Short Puts TP/SL configured: TP at {profit_target_pct}% of premium, "
                           f"SL at {stop_loss_multiplier}x premium", show_timestamp=False)

    def save(self):
        """Save the play configuration(s)."""
        base_play_name = self.play['play_name']
        base_filename = self.filename.replace('.json', '')
        
        # Determine the appropriate directory based on play class
        if self.play['play_class'] == 'OTO':
            plays_dir = os.path.join(os.path.dirname(__file__), '..', 'plays', 'temp')
        else:
            plays_dir = os.path.join(os.path.dirname(__file__), '..', 'plays', 'new')
        
        os.makedirs(plays_dir, exist_ok=True)
        
        # For each cached TP configuration, create and save a separate play file
        for i, tp_config in enumerate(self.tp_cache, 1):
            current_play = self.play.copy()
            
            # If multiple TPs, append number to play name and filename
            if len(self.tp_cache) > 1:
                current_play['play_name'] = f"{base_play_name}_TP{i}"
                current_filename = f"{base_filename}_TP{i}.json"
            else:
                current_filename = self.filename
            
            # Extract contracts from TP config and put it at root level
            if 'contracts' in tp_config:
                current_play['contracts'] = tp_config['contracts']
                del tp_config['contracts']  # Remove it from TP config
            
            current_play['take_profit'] = tp_config
            
            filepath = os.path.join(plays_dir, current_filename)
            try:
                with open(filepath, 'w') as f:
                    json.dump(current_play, f, indent=4)
                TerminalDisplay.success(f"Play saved successfully to: {filepath}", show_timestamp=False)
                
                # Open the file in text editor
                try:
                    if platform.system() == "Windows":
                        subprocess.run(["notepad.exe", filepath])
                    elif platform.system() == "Darwin":  # macOS
                        subprocess.run(["open", "-t", filepath])
                    else:  # Linux
                        subprocess.run(["xdg-open", filepath])
                    TerminalDisplay.info("Opening play file in text editor...", show_timestamp=False)
                except Exception as e:
                    TerminalDisplay.warning(f"Could not open file automatically: {e}", show_timestamp=False)
                    
            except Exception as e:
                TerminalDisplay.error(f"Error saving play: {str(e)}", show_timestamp=False)
                return False
        
        return True

def create_play():
    """
    Interactive tool to create a play for options trading, following the minimal template.
    """
    TerminalDisplay.header("Options Play Creation Tool", show_timestamp=False)
    
    while True:
        try:
            # Get strategy choice
            strategy_choice = get_input(
                "Select strategy:\n1. Option Swings (Long)\n2. Short Puts\nEnter choice (1 or 2) [default: 1]: ",
                str,
                validation=lambda x: x in ["1", "2", ""],
                error_message="Please enter 1 or 2.",
                optional=True
            )
            
            if not strategy_choice:
                strategy_choice = "1"  # Default to Option Swings
            
            builder = PlayBuilder(strategy_choice=strategy_choice)
            play = builder.build_base_play()
            
            # For Short Puts, TP/SL are pre-configured based on strategy rules
            # For Option Swings, use interactive TP/SL setup
            if strategy_choice == "2":
                # Short Puts: Set TP/SL based on strategy configuration
                builder._add_short_put_tp_sl()
            else:
                # Option Swings: Interactive TP/SL setup
                builder.add_take_profits()  # Now stores TPs in cache
                builder.add_stop_loss()
            
            if builder.save():
                # Ask if user wants to create another play
                another_play = get_input(
                    "Do you want to create another play? (Y/N): ",
                    str,
                    validation=lambda x: x.upper() in ["Y", "N"],
                    error_message="Please enter 'Y' or 'N'."
                ).upper()

                if another_play == "Y":
                    os.system('cls' if platform.system() == "Windows" else 'clear')  # Clear the screen
                    continue
                else:
                    TerminalDisplay.info("Exiting the play creation tool.", show_timestamp=False)
                    break
            return None
            
        except ValueError as ve:
            TerminalDisplay.error(f"Error creating play: {ve}", show_timestamp=False)
            return None

if __name__ == "__main__":
    create_play()