from colorama import init, Fore, Back, Style
import logging
from datetime import datetime

# Initialize colorama for Windows compatibility
init()

class TerminalDisplay:
    # Color schemes
    COLORS = {
        'success': Fore.GREEN,
        'error': Fore.RED,
        'warning': Fore.YELLOW,
        'info': Fore.CYAN,
        'debug': Fore.WHITE,
        'header': Fore.MAGENTA,
        'price': Fore.LIGHTGREEN_EX,
        'status': Fore.LIGHTBLUE_EX
    }

    @staticmethod
    def display(message, level='info', prefix=None):
        """Display formatted message to terminal."""
        color = TerminalDisplay.COLORS.get(level, Fore.WHITE)
        timestamp = datetime.now().strftime('%H:%M:%S')
        
        # Format prefix if provided
        prefix_str = f"[{prefix}] " if prefix else ""
        
        # Print colored message to terminal
        print(f"{color}{timestamp} {prefix_str}{message}{Style.RESET_ALL}")
        
        # Also log to file without colors
        if level == 'error':
            logging.error(message)
        elif level == 'warning':
            logging.warning(message)
        else:
            logging.info(message)

    @staticmethod
    def header(message):
        """Display section header."""
        print("\n" + TerminalDisplay.COLORS['header'] + "=" * 50 + Style.RESET_ALL)
        print(TerminalDisplay.COLORS['header'] + message + Style.RESET_ALL)
        print(TerminalDisplay.COLORS['header'] + "=" * 50 + Style.RESET_ALL + "\n")
        logging.info(f"\n{'=' * 50}\n{message}\n{'=' * 50}\n")

    @staticmethod
    def success(message, prefix=None):
        """Display success message."""
        TerminalDisplay.display(message, 'success', prefix)

    @staticmethod
    def error(message, prefix=None):
        """Display error message."""
        TerminalDisplay.display(message, 'error', prefix)

    @staticmethod
    def warning(message, prefix=None):
        """Display warning message."""
        TerminalDisplay.display(message, 'warning', prefix)

    @staticmethod
    def info(message, prefix=None):
        """Display info message."""
        TerminalDisplay.display(message, 'info', prefix)

    @staticmethod
    def price(message, prefix=None):
        """Display price-related information."""
        TerminalDisplay.display(message, 'price', prefix)

    @staticmethod
    def status(message, prefix=None):
        """Display status updates."""
        TerminalDisplay.display(message, 'status', prefix) 