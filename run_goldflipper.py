#!/usr/bin/env python
"""
This alias file serves as the top-level entry point for the Goldflipper TUI.
It imports the TUI from the goldflipper package and runs it, or launches a tool or
the trading system based on the command line arguments.
"""

import sys, os, argparse

if getattr(sys, 'frozen', False):
    # When running as a bundled executable, add sys._MEIPASS to sys.path.
    base_path = sys._MEIPASS
    sys.path.insert(0, base_path)
    # Insert the project root (one level up from sys.executable).
    project_root = os.path.abspath(os.path.join(os.path.dirname(sys.executable), '..'))
    sys.path.insert(0, project_root)
else:
    # In development, ensure the project root is in sys.path.
    project_root = os.path.abspath(os.path.dirname(__file__))
    sys.path.insert(0, project_root)

from goldflipper.goldflipper_tui import GoldflipperTUI
from goldflipper.run import run_trading_system  # Trading system launcher.

def main():
    parser = argparse.ArgumentParser(description="GoldFlipper")
    parser.add_argument("--interface", choices=["tui", "trading"], default="tui",
                        help="Choose the interface to run")
    parser.add_argument("--tool", type=str,
                        choices=["option_data_fetcher", "play_creation", "view_plays",
                                 "auto_play_creator", "get_alpaca_info", "trade_logger",
                                 "market_data_compare", "chart_viewer"],
                        help="Run a specific tool")
    # (Include any other arguments you need, e.g. service modes)
    args = parser.parse_args()

    if args.tool:
        # Dispatch to the appropriate tool.
        if args.tool == "option_data_fetcher":
            from goldflipper.tools.option_data_fetcher import main as tool_main
            tool_main()
        elif args.tool == "play_creation":
            from goldflipper.tools.play_creation_tool import main as tool_main
            tool_main()
        elif args.tool == "view_plays":
            from goldflipper.tools.view_plays import main as tool_main
            tool_main()
        elif args.tool == "auto_play_creator":
            from goldflipper.tools.auto_play_creator import main as tool_main
            tool_main()
        elif args.tool == "get_alpaca_info":
            from goldflipper.tools.get_alpaca_info import main as tool_main
            tool_main()
        elif args.tool == "trade_logger":
            from goldflipper.logging.trade_logger import main as tool_main
            tool_main()
        elif args.tool == "market_data_compare":
            from goldflipper.tools.multi_market_data import main as tool_main
            tool_main()
        elif args.tool == "chart_viewer":
            from goldflipper.chart.chart_viewer import main as tool_main
            tool_main()
        return  # Exit after finishing the tool.

    # If no tool is specified, proceed based on the interface mode.
    if args.interface == "tui":
        app = GoldflipperTUI()
        app.run()
    elif args.interface == "trading":
        run_trading_system(console_mode=True)
    # (Service options remain if needed.)

if __name__ == '__main__':
    main() 