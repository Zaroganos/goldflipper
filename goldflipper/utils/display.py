import logging
from datetime import datetime

from colorama import Fore, Style, init

# Initialize colorama for Windows
init()


class TerminalDisplay:
    COLORS = {
        "success": Fore.GREEN,
        "error": Fore.RED,
        "warning": Fore.YELLOW,
        "info": Fore.CYAN,
        "debug": Fore.WHITE,
        "header": Fore.MAGENTA,
        "price": Fore.LIGHTGREEN_EX,
        "status": Fore.WHITE,
    }

    @staticmethod
    def display(message, level="info", prefix=None, show_timestamp=True):
        """Display formatted message to terminal."""
        color = TerminalDisplay.COLORS.get(level, Fore.WHITE)

        # Format prefix if provided
        prefix_str = f"[{prefix}] " if prefix else ""

        # Add timestamp only if requested
        if show_timestamp:
            timestamp = datetime.now().strftime("%H:%M:%S")
            print(f"{color}{timestamp} {prefix_str}{message}{Style.RESET_ALL}")
        else:
            print(f"{color}{prefix_str}{message}{Style.RESET_ALL}")

        # Always log to file with timestamp
        if level == "error":
            logging.error(message)
        elif level == "warning":
            logging.warning(message)
        else:
            logging.info(message)

    @staticmethod
    def header(message, show_timestamp=True):
        """Display section header."""
        if show_timestamp:
            timestamp = datetime.now().strftime("%H:%M:%S")
            print(f"\n{TerminalDisplay.COLORS['header']}{timestamp} {'=' * 50}{Style.RESET_ALL}")
            print(f"{TerminalDisplay.COLORS['header']}{timestamp} {message}{Style.RESET_ALL}")
            print(f"{TerminalDisplay.COLORS['header']}{timestamp} {'=' * 50}{Style.RESET_ALL}\n")
        else:
            print(f"\n{TerminalDisplay.COLORS['header']}{'=' * 50}{Style.RESET_ALL}")
            print(f"{TerminalDisplay.COLORS['header']}{message}{Style.RESET_ALL}")
            print(f"{TerminalDisplay.COLORS['header']}{'=' * 50}{Style.RESET_ALL}\n")

        logging.info(f"\n{'=' * 50}\n{message}\n{'=' * 50}\n")

    @staticmethod
    def success(message, prefix=None, show_timestamp=True):
        """Display success message."""
        TerminalDisplay.display(message, "success", prefix, show_timestamp)

    @staticmethod
    def error(message, prefix=None, show_timestamp=True):
        """Display error message."""
        TerminalDisplay.display(message, "error", prefix, show_timestamp)

    @staticmethod
    def warning(message, prefix=None, show_timestamp=True):
        """Display warning message."""
        TerminalDisplay.display(message, "warning", prefix, show_timestamp)

    @staticmethod
    def info(message, prefix=None, show_timestamp=True):
        """Display info message."""
        TerminalDisplay.display(message, "info", prefix, show_timestamp)

    @staticmethod
    def price(message, prefix=None, show_timestamp=True):
        """Display price-related information."""
        TerminalDisplay.display(message, "price", prefix, show_timestamp)

    @staticmethod
    def status(message, prefix=None, show_timestamp=True):
        """Display status updates."""
        TerminalDisplay.display(message, "status", prefix, show_timestamp)
