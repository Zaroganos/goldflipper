"""
Goldflipper Play Creator GUI

A Tkinter-based GUI for creating option plays with multi-strategy support.
Replaces terminal-based play creation with a modern point-and-click interface.

Features:
- Strategy selection (option_swings, sell_puts, momentum, spreads)
- Real-time market data integration
- Option chain browser with Greeks
- Auto-populated fields from playbook defaults
- Validation and preview before play creation
- Template save/load functionality

Author: Goldflipper
Created: 2025-12-01
"""

import copy
import json
import logging
import os
import sys
import tkinter as tk
from datetime import datetime, timedelta
from enum import Enum
from tkinter import filedialog, messagebox, ttk
from typing import Any

# Add the project root to the Python path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(project_root)

from goldflipper.config.config import config
from goldflipper.data.market.manager import MarketDataManager
from goldflipper.utils.exe_utils import get_play_subdir

# =============================================================================
# Enums and Constants
# =============================================================================


class StrategyType(Enum):
    """Available strategies for play creation."""

    OPTION_SWINGS = "option_swings"
    MOMENTUM = "momentum"
    SELL_PUTS = "sell_puts"
    SPREADS = "spreads"  # Stub for future


class PlaybookType(Enum):
    """Available playbooks by strategy."""

    # Option Swings
    OPTION_SWINGS_DEFAULT = "default"
    OPTION_SWINGS_PB_V3 = "pb_v3"
    OPTION_SWINGS_PB_V3_LONG = "pb_v3_long"

    # Momentum
    MOMENTUM_GAP_MOVE = "gap_move"
    MOMENTUM_GAP_FADE = "gap_fade"
    MOMENTUM_GOLDFLIPPER_GAP = "goldflipper_gap_move"
    MOMENTUM_MANUAL = "manual"

    # Sell Puts
    SELL_PUTS_DEFAULT = "default"
    SELL_PUTS_TASTY_30 = "tasty_30_delta"


# Custom (dialed-in) playbooks vs basic templates
# Custom playbooks have been specifically tuned and tested
CUSTOM_PLAYBOOKS = {
    "goldflipper_gap_move",  # Goldflipper Gap Move - straddle + OI confirmation
    # Future: "goldflipper_option_swing" when implemented
}

STRATEGY_PLAYBOOKS = {
    StrategyType.OPTION_SWINGS: [
        ("Default", "default", "template"),
        ("Playbook v3 (Short Swing)", "pb_v3", "template"),
        ("Playbook v3 (Long Swing)", "pb_v3_long", "template"),
    ],
    StrategyType.MOMENTUM: [
        ("Gap Move (with gap)", "gap_move", "template"),
        ("Gap Fade (against gap)", "gap_fade", "template"),
        ("⭐ Goldflipper Gap Move", "goldflipper_gap_move", "custom"),
        ("Manual Entry", "manual", "template"),
    ],
    StrategyType.SELL_PUTS: [("Default (30-delta)", "default", "template"), ("Tasty 30-Delta", "tasty_30_delta", "template")],
    StrategyType.SPREADS: [("Default", "default", "template")],
}

STRATEGY_DESCRIPTIONS = {
    StrategyType.OPTION_SWINGS: "Manual option swing trades according to the official playbook.",
    StrategyType.MOMENTUM: "Momentum trades: Auto-detects gaps and trades with or against direction.",
    StrategyType.SELL_PUTS: "TastyTrade-style cash-secured puts. Sells OTM puts to collect premium.",
    StrategyType.SPREADS: "Multi-leg spread strategies (not yet implemented).",
}

ORDER_TYPES = [
    ("Market", "market"),
    ("Limit at Bid", "limit at bid"),
    ("Limit at Ask", "limit at ask"),
    ("Limit at Mid", "limit at mid"),
    ("Limit at Last", "limit at last"),
]


# =============================================================================
# Main GUI Class
# =============================================================================


class PlayCreatorGUI:
    """Tkinter GUI for creating option plays."""

    def __init__(self):
        """Initialize the Play Creator GUI."""
        self.root = tk.Tk()
        self.root.title("Play Creator")
        self.root.geometry("1500x900")  # Wider for 3-column layout
        self.root.minsize(1300, 700)

        # Initialize market data
        try:
            self.market_data = MarketDataManager()
        except Exception as e:
            logging.error(f"Failed to initialize MarketDataManager: {e}")
            self.market_data = None

        # Load configuration
        self.settings = config.get("auto_play_creator", default={})
        # Use account-aware plays directory
        self.plays_dir = str(get_play_subdir("new"))
        self.templates_dir = os.path.join(os.path.dirname(__file__), "templates")

        # Ensure plays directory exists (get_play_subdir already creates it)
        os.makedirs(self.plays_dir, exist_ok=True)

        # State variables
        self.current_strategy = tk.StringVar(value=StrategyType.OPTION_SWINGS.value)
        self.current_playbook = tk.StringVar(value="default")
        self.symbol = tk.StringVar()
        self.expiration = tk.StringVar()
        self.trade_type = tk.StringVar(value="CALL")
        self.strike_price = tk.StringVar()
        self.contracts = tk.IntVar(value=1)
        self.entry_order_type = tk.StringVar(value="Limit at Bid")
        self.tp_pct = tk.DoubleVar(value=50.0)
        self.sl_pct = tk.DoubleVar(value=25.0)

        # Entry price state variables
        self.entry_price = tk.DoubleVar(value=0.0)  # Option premium at entry
        self.option_bid = tk.DoubleVar(value=0.0)
        self.option_ask = tk.DoubleVar(value=0.0)
        self.option_last = tk.DoubleVar(value=0.0)
        self.option_mid = tk.DoubleVar(value=0.0)
        self.selected_delta = tk.DoubleVar(value=0.0)
        self.selected_theta = tk.DoubleVar(value=0.0)
        self.selected_iv = tk.DoubleVar(value=0.0)

        # Calculated TP/SL absolute prices
        self.tp_price = tk.DoubleVar(value=0.0)  # Calculated absolute TP price
        self.sl_price = tk.DoubleVar(value=0.0)  # Calculated absolute SL price

        # Stock price percentage conditions
        self.use_stock_pct_tp = tk.BooleanVar(value=False)
        self.use_stock_pct_sl = tk.BooleanVar(value=False)
        self.tp_stock_pct = tk.DoubleVar(value=5.0)  # Stock price change %
        self.sl_stock_pct = tk.DoubleVar(value=-3.0)  # Stock price change %

        # Advanced options state variables
        self.play_expiration = tk.StringVar()  # Separate from option expiration
        self.play_class = tk.StringVar(value="SIMPLE")  # SIMPLE or OTO
        self.sl_type = tk.StringVar(value="STOP")  # STOP, LIMIT, CONTINGENCY
        self.contingency_sl_pct = tk.DoubleVar(value=50.0)  # Backup SL for contingency
        self.tp_order_type = tk.StringVar(value="Limit at Mid")
        self.sl_order_type = tk.StringVar(value="Market")
        self.use_stock_price_tp = tk.BooleanVar(value=False)
        self.use_stock_price_sl = tk.BooleanVar(value=False)
        self.tp_stock_price = tk.DoubleVar(value=0.0)
        self.sl_stock_price = tk.DoubleVar(value=0.0)
        self.trailing_tp_enabled = tk.BooleanVar(value=False)
        self.trailing_tp_activation_pct = tk.DoubleVar(value=20.0)
        self.trailing_sl_enabled = tk.BooleanVar(value=False)
        self.trailing_sl_activation_pct = tk.DoubleVar(value=10.0)
        self.multiple_tps_enabled = tk.BooleanVar(value=False)
        self.num_tp_levels = tk.IntVar(value=2)
        self.tp_levels_data = []  # List of dicts: [{pct, contracts}, ...]

        # Dynamic TP/SL state (stub for future implementations)
        self.dynamic_tp_sl_enabled = tk.BooleanVar(value=False)

        # Dynamic GTD state variables
        self.dynamic_gtd_enabled = tk.BooleanVar(value=False)
        self.gtd_max_hold_days_enabled = tk.BooleanVar(value=False)
        self.gtd_max_hold_days = tk.IntVar(value=5)
        self.gtd_dte_close_enabled = tk.BooleanVar(value=False)
        self.gtd_dte_close_at = tk.IntVar(value=7)
        self.gtd_theta_threshold_enabled = tk.BooleanVar(value=False)
        self.gtd_theta_max_pct = tk.DoubleVar(value=2.0)
        self.gtd_pl_time_stop_enabled = tk.BooleanVar(value=False)
        self.gtd_pl_time_stop_days = tk.IntVar(value=3)
        self.gtd_profit_extension_enabled = tk.BooleanVar(value=False)
        self.gtd_profit_extension_min_pct = tk.DoubleVar(value=10.0)
        self.gtd_profit_extension_days = tk.IntVar(value=3)
        self.gtd_loss_shortening_enabled = tk.BooleanVar(value=False)
        self.gtd_loss_threshold_pct = tk.DoubleVar(value=-10.0)
        self.gtd_loss_shorten_days = tk.IntVar(value=2)
        self.gtd_rolling_enabled = tk.BooleanVar(value=False)
        self.gtd_rolling_extension_days = tk.IntVar(value=1)
        self.gtd_earnings_enabled = tk.BooleanVar(value=False)
        self.gtd_earnings_days_before = tk.IntVar(value=1)
        self.gtd_weekend_theta_enabled = tk.BooleanVar(value=False)
        self.gtd_weekend_min_dte = tk.IntVar(value=14)
        self.gtd_iv_crush_enabled = tk.BooleanVar(value=False)
        self.gtd_iv_crush_max_rank = tk.DoubleVar(value=80.0)
        self.gtd_half_life_enabled = tk.BooleanVar(value=False)
        self.gtd_half_life_fraction = tk.DoubleVar(value=0.5)

        # OCO/OTO relationship state
        self.oco_plays = tk.StringVar(value="")  # Comma-separated play names
        self.oto_parent = tk.StringVar(value="")  # Parent play for OTO
        self.oto_trigger_condition = tk.StringVar(value="on_fill")  # on_fill, on_tp, on_sl
        self.oco_peer_set_numbers = tk.StringVar(value="")  # Comma-separated OCO peer set numbers (e.g., "1,2,3")

        # Market data state
        self.current_price = tk.StringVar(value="--")
        self.bid_price = tk.StringVar(value="--")
        self.ask_price = tk.StringVar(value="--")
        self.gap_pct = tk.StringVar(value="--")
        self.gap_type = tk.StringVar(value="--")
        self.previous_close = tk.StringVar(value="--")

        # Momentum-specific configuration (simplified: confirmation_minutes controls entry delay)
        self.momentum_confirmation_minutes = tk.IntVar(value=15)  # 0=immediate, 60=full first hour
        self.momentum_lunch_break_enabled = tk.BooleanVar(value=True)
        self.momentum_lunch_start_hour = tk.IntVar(value=12)
        self.momentum_lunch_start_minute = tk.IntVar(value=0)
        self.momentum_lunch_end_hour = tk.IntVar(value=13)
        self.momentum_lunch_end_minute = tk.IntVar(value=0)

        # Goldflipper Gap Move custom configuration
        self.goldflipper_gap_straddle_enabled = tk.BooleanVar(value=True)
        self.goldflipper_gap_min_straddle_ratio = tk.DoubleVar(value=1.0)
        self.goldflipper_gap_oi_enabled = tk.BooleanVar(value=True)
        self.goldflipper_gap_min_directional_oi = tk.IntVar(value=500)
        self.goldflipper_gap_min_oi_ratio = tk.DoubleVar(value=1.0)

        # Advanced Momentum Parameters (displayed in Advanced Settings panel)
        # Gap filtering (only for "default" playbook where gap direction is manual)
        self.adv_min_gap_pct = tk.DoubleVar(value=1.0)
        self.adv_max_gap_pct = tk.DoubleVar(value=10.0)
        self.adv_max_gap_pct_enabled = tk.BooleanVar(value=False)

        # Time-based exit controls
        self.adv_same_day_exit = tk.BooleanVar(value=False)
        self.adv_max_hold_days_enabled = tk.BooleanVar(value=True)
        self.adv_max_hold_days = tk.IntVar(value=5)

        # Entry timing
        self.adv_avoid_first_minutes = tk.IntVar(value=5)
        self.adv_avoid_last_minutes = tk.IntVar(value=60)

        # Option selection DTE range
        self.adv_dte_min = tk.IntVar(value=7)
        self.adv_dte_max = tk.IntVar(value=21)

        # Option chain data
        self.option_chain_data = None
        self.expirations_list = []

        # Setup UI
        self._setup_ui()

        # Bind events
        self._bind_events()

    def _setup_ui(self):
        """Setup the main UI layout with 3 columns."""
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        # Main container with scrollbar
        self.main_canvas = tk.Canvas(self.root)
        scrollbar = ttk.Scrollbar(self.root, orient="vertical", command=self.main_canvas.yview)
        self.main_frame = ttk.Frame(self.main_canvas, padding="10")

        self.main_frame.bind("<Configure>", lambda e: self.main_canvas.configure(scrollregion=self.main_canvas.bbox("all")))

        # Create window and store the ID for resizing
        self.canvas_window = self.main_canvas.create_window((0, 0), window=self.main_frame, anchor="nw")
        self.main_canvas.configure(yscrollcommand=scrollbar.set)

        # Bind canvas resize to stretch main_frame horizontally
        self.main_canvas.bind("<Configure>", self._on_canvas_configure)

        self.main_canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")

        # Configure main frame grid - 3 columns
        self.main_frame.columnconfigure(0, weight=1)  # Left - config
        self.main_frame.columnconfigure(1, weight=1)  # Middle - option chain, risk, conditionals
        self.main_frame.columnconfigure(2, weight=1)  # Right - preview

        # Header
        self._create_header()

        # Left column - Strategy, Gap Info, Play Configuration
        left_frame = ttk.Frame(self.main_frame)
        left_frame.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        left_frame.columnconfigure(0, weight=1)

        # Strategy Selection Panel
        self._create_strategy_panel(left_frame)

        # Symbol & Market Data Panel (gap info for momentum only)
        self._create_market_data_panel(left_frame)

        # Play Configuration Panel (Basic, Entry, TP, SL - no conditionals)
        self._create_config_panel(left_frame)

        # Middle column - Option Chain, Risk Summary, Action Buttons, Conditional Orders, Other Options
        middle_frame = ttk.Frame(self.main_frame)
        middle_frame.grid(row=1, column=1, sticky="nsew", padx=5, pady=5)
        middle_frame.columnconfigure(0, weight=1)
        middle_frame.rowconfigure(0, weight=0)  # Option chain
        middle_frame.rowconfigure(1, weight=0)  # Risk summary
        middle_frame.rowconfigure(2, weight=0)  # Action buttons
        middle_frame.rowconfigure(3, weight=0)  # Conditional orders
        middle_frame.rowconfigure(4, weight=1)  # Other options + spacer

        # Option Chain Browser
        self._create_option_chain_panel(middle_frame)

        # Risk Summary Panel
        self._create_risk_summary_panel(middle_frame)

        # Action Buttons Panel (between risk summary and conditional orders)
        self._create_action_buttons_panel(middle_frame)

        # Conditional Orders Panel
        self._create_conditional_orders_panel(middle_frame)

        # Other Options Panel
        self._create_other_options_panel(middle_frame)

        # Right column - Play Preview + Advanced Settings
        right_frame = ttk.Frame(self.main_frame)
        right_frame.grid(row=1, column=2, sticky="nsew", padx=5, pady=5)
        right_frame.columnconfigure(0, weight=1)
        right_frame.rowconfigure(0, weight=1)  # Preview takes most height
        right_frame.rowconfigure(1, weight=0)  # Advanced settings fixed height

        # Validation & Preview Panel
        self._create_preview_panel(right_frame)

        # Advanced Settings Panel (below preview, for momentum strategy)
        self._create_advanced_settings_panel(right_frame)

    def _create_header(self):
        """Create the header with title and option contract preview."""
        header_frame = ttk.Frame(self.main_frame)
        header_frame.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 10))
        header_frame.columnconfigure(1, weight=1)

        # Left side - Title
        title_label = ttk.Label(header_frame, text="Play Creator:", font=("Helvetica", 16, "bold"))
        title_label.grid(row=0, column=0, sticky="w")

        # Center - Option Contract Preview (dynamically updated)
        self.contract_preview_label = ttk.Label(header_frame, text="[ No contract selected ]", font=("Helvetica", 14, "bold"), foreground="#0066cc")
        self.contract_preview_label.grid(row=0, column=1, sticky="w", padx=10)

        # Right side - Status indicator
        self.status_label = ttk.Label(header_frame, text="Ready", foreground="green")
        self.status_label.grid(row=0, column=2, sticky="e", padx=10)

    def _create_strategy_panel(self, parent):
        """Create the strategy selection panel."""
        frame = ttk.LabelFrame(parent, text="Strategy Selection", padding="10")
        frame.grid(row=0, column=0, sticky="ew", pady=5)
        frame.columnconfigure(1, weight=1)

        # Strategy dropdown
        ttk.Label(frame, text="Strategy:").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        strategy_combo = ttk.Combobox(frame, textvariable=self.current_strategy, values=[s.value for s in StrategyType], state="readonly", width=25)
        strategy_combo.grid(row=0, column=1, sticky="ew", padx=5, pady=5)
        strategy_combo.bind("<<ComboboxSelected>>", self._on_strategy_changed)

        # Playbook dropdown with type indicator
        ttk.Label(frame, text="Playbook:").grid(row=1, column=0, sticky="w", padx=5, pady=5)
        playbook_frame = ttk.Frame(frame)
        playbook_frame.grid(row=1, column=1, sticky="ew", padx=5, pady=5)

        self.playbook_combo = ttk.Combobox(playbook_frame, textvariable=self.current_playbook, state="readonly", width=25)
        self.playbook_combo.pack(side=tk.LEFT)
        self.playbook_combo.bind("<<ComboboxSelected>>", self._on_playbook_changed)

        # Playbook type indicator label (CUSTOM vs TEMPLATE)
        self.playbook_type_label = tk.Label(playbook_frame, text="TEMPLATE", font=("Helvetica", 8, "bold"), fg="gray", padx=5)
        self.playbook_type_label.pack(side=tk.LEFT, padx=(5, 0))

        # Strategy description
        self.strategy_desc_label = ttk.Label(frame, text=STRATEGY_DESCRIPTIONS[StrategyType.OPTION_SWINGS], wraplength=350, foreground="gray")
        self.strategy_desc_label.grid(row=2, column=0, columnspan=2, sticky="w", padx=5, pady=5)

        # Update playbook options
        self._update_playbook_options()

    def _create_market_data_panel(self, parent):
        """Create the gap info panel (only visible for momentum strategy)."""
        # Gap info frame (for momentum strategy only)
        self.gap_frame = ttk.LabelFrame(parent, text="Gap Info (Momentum)", padding="5")
        self.gap_frame.grid(row=1, column=0, sticky="ew", pady=5)

        gap_inner = ttk.Frame(self.gap_frame)
        gap_inner.pack(fill=tk.X)

        ttk.Label(gap_inner, text="Gap:").pack(side=tk.LEFT, padx=5)
        self.gap_pct_label = ttk.Label(gap_inner, textvariable=self.gap_pct, font=("Helvetica", 10, "bold"))
        self.gap_pct_label.pack(side=tk.LEFT)

        ttk.Label(gap_inner, text="Type:").pack(side=tk.LEFT, padx=(20, 5))
        ttk.Label(gap_inner, textvariable=self.gap_type).pack(side=tk.LEFT)

        ttk.Label(gap_inner, text="Prev Close:").pack(side=tk.LEFT, padx=(20, 5))
        ttk.Label(gap_inner, textvariable=self.previous_close).pack(side=tk.LEFT)

        # Momentum Config Panel (only visible for momentum)
        self._create_momentum_config_panel(parent)

        # Initially hide gap/momentum frames (only show for momentum)
        self._update_gap_visibility()

    def _create_momentum_config_panel(self, parent):
        """Create Momentum-specific configuration panel - placeholder, actual UI in Other Options."""
        # Create a hidden frame as placeholder for compatibility
        self.momentum_config_frame = ttk.Frame(parent)
        self.momentum_config_frame.grid(row=1, column=0, sticky="ew", pady=0)
        self.momentum_config_frame.grid_remove()

        # Goldflipper Gap config frame - placeholder for compatibility
        self.goldflipper_gap_config_frame = ttk.Frame(parent)
        self.goldflipper_gap_config_frame.grid(row=2, column=0, sticky="ew", pady=0)
        self.goldflipper_gap_config_frame.grid_remove()

    def _create_config_panel(self, parent):
        """Create the play configuration panel."""
        frame = ttk.LabelFrame(parent, text="Play Configuration", padding="10")
        frame.grid(row=2, column=0, sticky="ew", pady=5)
        frame.columnconfigure(1, weight=1)

        row = 0

        # Contract Expiration (renamed from Expiration)
        ttk.Label(frame, text="Contract Expiration:").grid(row=row, column=0, sticky="w", padx=5, pady=3)
        exp_frame = ttk.Frame(frame)
        exp_frame.grid(row=row, column=1, sticky="ew", padx=5, pady=3)
        self.expiration_combo = ttk.Combobox(exp_frame, textvariable=self.expiration, state="readonly", width=12)
        self.expiration_combo.pack(side=tk.LEFT)
        self.expiration_combo.bind("<<ComboboxSelected>>", self._on_expiration_changed)
        self.dte_label = ttk.Label(exp_frame, text="", foreground="gray")
        self.dte_label.pack(side=tk.LEFT, padx=10)
        row += 1

        # Trade type
        ttk.Label(frame, text="Trade Type:").grid(row=row, column=0, sticky="w", padx=5, pady=3)
        type_frame = ttk.Frame(frame)
        type_frame.grid(row=row, column=1, sticky="w", padx=5, pady=3)

        ttk.Radiobutton(type_frame, text="CALL", variable=self.trade_type, value="CALL", command=self._on_trade_type_changed).pack(
            side=tk.LEFT, padx=5
        )
        ttk.Radiobutton(type_frame, text="PUT", variable=self.trade_type, value="PUT", command=self._on_trade_type_changed).pack(side=tk.LEFT, padx=5)
        row += 1

        # Strike price
        ttk.Label(frame, text="Strike Price:").grid(row=row, column=0, sticky="w", padx=5, pady=3)
        self.strike_combo = ttk.Combobox(frame, textvariable=self.strike_price, width=10)
        self.strike_combo.grid(row=row, column=1, sticky="w", padx=5, pady=3)
        self.strike_combo.bind("<<ComboboxSelected>>", self._on_strike_changed)
        row += 1

        # Contracts
        ttk.Label(frame, text="Contracts:").grid(row=row, column=0, sticky="w", padx=5, pady=3)
        contracts_spin = ttk.Spinbox(frame, textvariable=self.contracts, from_=1, to=100, width=10, command=self._on_contracts_changed)
        contracts_spin.grid(row=row, column=1, sticky="w", padx=5, pady=3)
        row += 1

        # Play Expiration (moved from advanced options)
        ttk.Label(frame, text="Play Expiration:").grid(row=row, column=0, sticky="w", padx=5, pady=3)
        play_exp_frame = ttk.Frame(frame)
        play_exp_frame.grid(row=row, column=1, sticky="w", padx=5, pady=3)

        self.play_exp_entry = ttk.Entry(play_exp_frame, textvariable=self.play_expiration, width=12)
        self.play_exp_entry.pack(side=tk.LEFT)
        ttk.Label(play_exp_frame, text="MM/DD/YYYY (blank=contract exp)", foreground="gray", font=("Helvetica", 8)).pack(side=tk.LEFT, padx=5)
        row += 1

        # === DYNAMIC GTD SECTION ===
        gtd_check = ttk.Checkbutton(
            frame, text="Dynamic GTD (adjust play expiration dynamically)", variable=self.dynamic_gtd_enabled, command=self._toggle_gtd_panel
        )
        gtd_check.grid(row=row, column=0, columnspan=2, sticky="w", padx=5, pady=3)
        row += 1

        # GTD methods panel (hidden by default)
        self._gtd_frame = ttk.LabelFrame(frame, text="Dynamic GTD Methods", padding=5)
        self._gtd_frame.grid(row=row, column=0, columnspan=2, sticky="ew", padx=5, pady=3)
        self._gtd_frame.grid_remove()  # Hidden initially
        self._build_gtd_methods_panel(self._gtd_frame)
        row += 1

        # Separator before Entry section
        ttk.Separator(frame, orient="horizontal").grid(row=row, column=0, columnspan=2, sticky="ew", pady=8)
        row += 1

        # === ENTRY SECTION ===
        entry_header = ttk.Label(frame, text="Entry", font=("Helvetica", 9, "bold"))
        entry_header.grid(row=row, column=0, columnspan=2, sticky="w", padx=5, pady=2)
        row += 1

        # Entry order type
        ttk.Label(frame, text="Order Type:").grid(row=row, column=0, sticky="w", padx=5, pady=3)
        order_combo = ttk.Combobox(frame, textvariable=self.entry_order_type, values=[ot[0] for ot in ORDER_TYPES], state="readonly", width=15)
        order_combo.grid(row=row, column=1, sticky="w", padx=5, pady=3)
        order_combo.bind("<<ComboboxSelected>>", self._on_entry_order_type_changed)
        row += 1

        # Option prices display (bid/ask/mid/last)
        prices_frame = ttk.Frame(frame)
        prices_frame.grid(row=row, column=0, columnspan=2, sticky="ew", padx=5, pady=3)

        ttk.Label(prices_frame, text="Bid:", foreground="gray").pack(side=tk.LEFT, padx=(0, 2))
        self.bid_display = ttk.Label(prices_frame, text="--", font=("Helvetica", 9))
        self.bid_display.pack(side=tk.LEFT, padx=(0, 10))

        ttk.Label(prices_frame, text="Ask:", foreground="gray").pack(side=tk.LEFT, padx=(0, 2))
        self.ask_display = ttk.Label(prices_frame, text="--", font=("Helvetica", 9))
        self.ask_display.pack(side=tk.LEFT, padx=(0, 10))

        ttk.Label(prices_frame, text="Mid:", foreground="gray").pack(side=tk.LEFT, padx=(0, 2))
        self.mid_display = ttk.Label(prices_frame, text="--", font=("Helvetica", 9, "bold"))
        self.mid_display.pack(side=tk.LEFT, padx=(0, 10))

        ttk.Label(prices_frame, text="Last:", foreground="gray").pack(side=tk.LEFT, padx=(0, 2))
        self.last_display = ttk.Label(prices_frame, text="--", font=("Helvetica", 9))
        self.last_display.pack(side=tk.LEFT)
        row += 1

        # Entry price (editable)
        ttk.Label(frame, text="Entry Price:").grid(row=row, column=0, sticky="w", padx=5, pady=3)
        entry_price_frame = ttk.Frame(frame)
        entry_price_frame.grid(row=row, column=1, sticky="ew", padx=5, pady=3)

        ttk.Label(entry_price_frame, text="$").pack(side=tk.LEFT)
        self.entry_price_spin = ttk.Spinbox(
            entry_price_frame, textvariable=self.entry_price, from_=0.01, to=1000.0, increment=0.05, width=10, command=self._on_entry_price_changed
        )
        self.entry_price_spin.pack(side=tk.LEFT)
        self.entry_price_spin.bind("<FocusOut>", lambda e: self._on_entry_price_changed())
        ttk.Label(entry_price_frame, text="per contract", foreground="gray").pack(side=tk.LEFT, padx=5)
        row += 1

        # Separator before TP/SL section
        ttk.Separator(frame, orient="horizontal").grid(row=row, column=0, columnspan=2, sticky="ew", pady=8)
        row += 1

        # === TAKE PROFIT SECTION ===
        tp_header = ttk.Label(frame, text="Take Profit Conditions", font=("Helvetica", 9, "bold"))
        tp_header.grid(row=row, column=0, columnspan=2, sticky="w", padx=5, pady=2)
        row += 1

        # TP Premium % with calculated price
        tp_prem_frame = ttk.Frame(frame)
        tp_prem_frame.grid(row=row, column=0, columnspan=2, sticky="ew", padx=5, pady=3)

        ttk.Label(tp_prem_frame, text="Premium Gain:").pack(side=tk.LEFT)
        tp_spin = ttk.Spinbox(tp_prem_frame, textvariable=self.tp_pct, from_=1, to=500, increment=5, width=6, command=self._on_tp_sl_changed)
        tp_spin.pack(side=tk.LEFT, padx=5)
        tp_spin.bind("<FocusOut>", lambda e: self._on_tp_sl_changed())
        ttk.Label(tp_prem_frame, text="%  →").pack(side=tk.LEFT)
        self.tp_price_label = ttk.Label(tp_prem_frame, text="$--", font=("Helvetica", 9, "bold"), foreground="green")
        self.tp_price_label.pack(side=tk.LEFT, padx=5)
        row += 1

        # TP Stock Price Absolute
        tp_stock_abs_frame = ttk.Frame(frame)
        tp_stock_abs_frame.grid(row=row, column=0, columnspan=2, sticky="ew", padx=5, pady=2)

        ttk.Checkbutton(tp_stock_abs_frame, text="Stock Price Target:", variable=self.use_stock_price_tp, command=self._on_stock_price_toggle).pack(
            side=tk.LEFT
        )
        ttk.Label(tp_stock_abs_frame, text="$").pack(side=tk.LEFT, padx=(5, 0))
        self.tp_stock_entry = ttk.Entry(tp_stock_abs_frame, textvariable=self.tp_stock_price, width=10, state="disabled")
        self.tp_stock_entry.pack(side=tk.LEFT)
        row += 1

        # TP Stock Price Percentage
        tp_stock_pct_frame = ttk.Frame(frame)
        tp_stock_pct_frame.grid(row=row, column=0, columnspan=2, sticky="ew", padx=5, pady=2)

        ttk.Checkbutton(tp_stock_pct_frame, text="Stock Price Change:", variable=self.use_stock_pct_tp, command=self._on_stock_pct_toggle).pack(
            side=tk.LEFT
        )
        self.tp_stock_pct_spin = ttk.Spinbox(
            tp_stock_pct_frame, textvariable=self.tp_stock_pct, from_=-50, to=50, increment=0.5, width=8, state="disabled"
        )
        self.tp_stock_pct_spin.pack(side=tk.LEFT, padx=5)
        ttk.Label(tp_stock_pct_frame, text="%", foreground="gray").pack(side=tk.LEFT)
        self.tp_stock_pct_target_label = ttk.Label(tp_stock_pct_frame, text="", foreground="gray")
        self.tp_stock_pct_target_label.pack(side=tk.LEFT, padx=5)
        row += 1

        # TP Order Type
        tp_order_frame = ttk.Frame(frame)
        tp_order_frame.grid(row=row, column=0, columnspan=2, sticky="ew", padx=5, pady=2)

        ttk.Label(tp_order_frame, text="Exit Order:").pack(side=tk.LEFT)
        tp_order_combo = ttk.Combobox(
            tp_order_frame, textvariable=self.tp_order_type, values=[ot[0] for ot in ORDER_TYPES], state="readonly", width=15
        )
        tp_order_combo.pack(side=tk.LEFT, padx=5)
        row += 1

        # Trailing TP (collapsible)
        trailing_tp_frame = ttk.Frame(frame)
        trailing_tp_frame.grid(row=row, column=0, columnspan=2, sticky="ew", padx=5, pady=2)

        ttk.Checkbutton(trailing_tp_frame, text="Trailing TP", variable=self.trailing_tp_enabled, command=self._on_trailing_tp_toggle).pack(
            side=tk.LEFT
        )
        ttk.Label(trailing_tp_frame, text="Activation %:").pack(side=tk.LEFT, padx=(10, 2))
        self.trailing_tp_spin = ttk.Spinbox(
            trailing_tp_frame, textvariable=self.trailing_tp_activation_pct, from_=5, to=100, increment=5, width=6, state="disabled"
        )
        self.trailing_tp_spin.pack(side=tk.LEFT, padx=2)
        ttk.Label(trailing_tp_frame, text="% gain activates trail", foreground="gray", font=("Helvetica", 8)).pack(side=tk.LEFT, padx=5)
        row += 1

        # Multiple TPs (collapsible)
        multi_tp_header = ttk.Frame(frame)
        multi_tp_header.grid(row=row, column=0, columnspan=2, sticky="ew", padx=5, pady=2)

        ttk.Checkbutton(multi_tp_header, text="Multiple TP Levels", variable=self.multiple_tps_enabled, command=self._on_multi_tp_toggle).pack(
            side=tk.LEFT
        )
        ttk.Label(multi_tp_header, text="# of TPs:").pack(side=tk.LEFT, padx=(10, 2))
        self.num_tps_spin = ttk.Spinbox(
            multi_tp_header, textvariable=self.num_tp_levels, from_=2, to=5, width=4, state="disabled", command=self._rebuild_tp_levels_ui
        )
        self.num_tps_spin.pack(side=tk.LEFT, padx=2)
        self.num_tps_spin.bind("<Return>", lambda e: self._rebuild_tp_levels_ui())
        row += 1

        # Dynamic TP levels container (shown when multiple TPs enabled)
        self.tp_levels_container = ttk.Frame(frame)
        self.tp_levels_container.grid(row=row, column=0, columnspan=2, sticky="ew", padx=5, pady=2)
        self.tp_level_widgets = []  # Store widgets for cleanup
        self.tp_levels_container.grid_remove()  # Initially hidden
        row += 1

        # Dynamic TP toggle (stub)
        dynamic_tp_frame = ttk.Frame(frame)
        dynamic_tp_frame.grid(row=row, column=0, columnspan=2, sticky="ew", padx=5, pady=2)

        ttk.Checkbutton(
            dynamic_tp_frame,
            text="Dynamic TP",
            variable=self.dynamic_tp_sl_enabled,  # Shares state with SL for now
            command=self._on_dynamic_toggle,
        ).pack(side=tk.LEFT)
        ttk.Label(dynamic_tp_frame, text="(future: time decay, IV-adjusted)", foreground="gray", font=("Helvetica", 8)).pack(side=tk.LEFT, padx=5)
        row += 1

        # Separator
        ttk.Separator(frame, orient="horizontal").grid(row=row, column=0, columnspan=2, sticky="ew", pady=8)
        row += 1

        # === STOP LOSS SECTION ===
        sl_header = ttk.Label(frame, text="Stop Loss Conditions", font=("Helvetica", 9, "bold"))
        sl_header.grid(row=row, column=0, columnspan=2, sticky="w", padx=5, pady=2)
        row += 1

        # SL Premium % with calculated price
        sl_prem_frame = ttk.Frame(frame)
        sl_prem_frame.grid(row=row, column=0, columnspan=2, sticky="ew", padx=5, pady=3)

        ttk.Label(sl_prem_frame, text="Premium Loss:").pack(side=tk.LEFT)
        sl_spin = ttk.Spinbox(sl_prem_frame, textvariable=self.sl_pct, from_=1, to=200, increment=5, width=6, command=self._on_tp_sl_changed)
        sl_spin.pack(side=tk.LEFT, padx=5)
        sl_spin.bind("<FocusOut>", lambda e: self._on_tp_sl_changed())
        ttk.Label(sl_prem_frame, text="%  →").pack(side=tk.LEFT)
        self.sl_price_label = ttk.Label(sl_prem_frame, text="$--", font=("Helvetica", 9, "bold"), foreground="red")
        self.sl_price_label.pack(side=tk.LEFT, padx=5)
        row += 1

        # SL Stock Price Absolute
        sl_stock_abs_frame = ttk.Frame(frame)
        sl_stock_abs_frame.grid(row=row, column=0, columnspan=2, sticky="ew", padx=5, pady=2)

        ttk.Checkbutton(sl_stock_abs_frame, text="Stock Price Target:", variable=self.use_stock_price_sl, command=self._on_stock_price_toggle).pack(
            side=tk.LEFT
        )
        ttk.Label(sl_stock_abs_frame, text="$").pack(side=tk.LEFT, padx=(5, 0))
        self.sl_stock_entry = ttk.Entry(sl_stock_abs_frame, textvariable=self.sl_stock_price, width=10, state="disabled")
        self.sl_stock_entry.pack(side=tk.LEFT)
        row += 1

        # SL Stock Price Percentage
        sl_stock_pct_frame = ttk.Frame(frame)
        sl_stock_pct_frame.grid(row=row, column=0, columnspan=2, sticky="ew", padx=5, pady=2)

        ttk.Checkbutton(sl_stock_pct_frame, text="Stock Price Change:", variable=self.use_stock_pct_sl, command=self._on_stock_pct_toggle).pack(
            side=tk.LEFT
        )
        self.sl_stock_pct_spin = ttk.Spinbox(
            sl_stock_pct_frame, textvariable=self.sl_stock_pct, from_=-50, to=50, increment=0.5, width=8, state="disabled"
        )
        self.sl_stock_pct_spin.pack(side=tk.LEFT, padx=5)
        ttk.Label(sl_stock_pct_frame, text="%", foreground="gray").pack(side=tk.LEFT)
        self.sl_stock_pct_target_label = ttk.Label(sl_stock_pct_frame, text="", foreground="gray")
        self.sl_stock_pct_target_label.pack(side=tk.LEFT, padx=5)
        row += 1

        # SL Type (moved from advanced options)
        sl_type_frame = ttk.Frame(frame)
        sl_type_frame.grid(row=row, column=0, columnspan=2, sticky="ew", padx=5, pady=2)

        ttk.Label(sl_type_frame, text="SL Type:").pack(side=tk.LEFT)
        ttk.Radiobutton(sl_type_frame, text="STOP", variable=self.sl_type, value="STOP", command=self._on_sl_type_changed).pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(sl_type_frame, text="LIMIT", variable=self.sl_type, value="LIMIT", command=self._on_sl_type_changed).pack(
            side=tk.LEFT, padx=5
        )
        ttk.Radiobutton(sl_type_frame, text="CONTINGENCY", variable=self.sl_type, value="CONTINGENCY", command=self._on_sl_type_changed).pack(
            side=tk.LEFT, padx=5
        )
        row += 1

        # Contingency backup SL (shown only when CONTINGENCY selected)
        self.contingency_frame = ttk.Frame(frame)
        self.contingency_frame.grid(row=row, column=0, columnspan=2, sticky="ew", padx=5, pady=2)

        ttk.Label(self.contingency_frame, text="Backup SL %:").pack(side=tk.LEFT, padx=5)
        ttk.Spinbox(self.contingency_frame, textvariable=self.contingency_sl_pct, from_=1, to=200, increment=5, width=6).pack(side=tk.LEFT, padx=2)
        ttk.Label(self.contingency_frame, text="(must be > main SL%)", foreground="gray", font=("Helvetica", 8)).pack(side=tk.LEFT, padx=5)
        self.contingency_frame.grid_remove()  # Initially hidden
        row += 1

        # SL Order Type
        sl_order_frame = ttk.Frame(frame)
        sl_order_frame.grid(row=row, column=0, columnspan=2, sticky="ew", padx=5, pady=2)

        ttk.Label(sl_order_frame, text="Exit Order:").pack(side=tk.LEFT)
        self.sl_order_combo = ttk.Combobox(
            sl_order_frame, textvariable=self.sl_order_type, values=[ot[0] for ot in ORDER_TYPES], state="readonly", width=15
        )
        self.sl_order_combo.pack(side=tk.LEFT, padx=5)
        row += 1

        # Trailing SL (collapsible)
        trailing_sl_frame = ttk.Frame(frame)
        trailing_sl_frame.grid(row=row, column=0, columnspan=2, sticky="ew", padx=5, pady=2)

        ttk.Checkbutton(trailing_sl_frame, text="Trailing SL", variable=self.trailing_sl_enabled, command=self._on_trailing_sl_toggle).pack(
            side=tk.LEFT
        )
        ttk.Label(trailing_sl_frame, text="Activation %:").pack(side=tk.LEFT, padx=(10, 2))
        self.trailing_sl_spin = ttk.Spinbox(
            trailing_sl_frame, textvariable=self.trailing_sl_activation_pct, from_=5, to=50, increment=5, width=6, state="disabled"
        )
        self.trailing_sl_spin.pack(side=tk.LEFT, padx=2)
        ttk.Label(trailing_sl_frame, text="% loss activates trail", foreground="gray", font=("Helvetica", 8)).pack(side=tk.LEFT, padx=5)
        row += 1

        # Dynamic SL toggle (stub)
        dynamic_sl_frame = ttk.Frame(frame)
        dynamic_sl_frame.grid(row=row, column=0, columnspan=2, sticky="ew", padx=5, pady=2)

        ttk.Checkbutton(
            dynamic_sl_frame,
            text="Dynamic SL",
            variable=self.dynamic_tp_sl_enabled,  # Shares state with TP for now
            command=self._on_dynamic_toggle,
        ).pack(side=tk.LEFT)
        ttk.Label(dynamic_sl_frame, text="(future: time decay, IV-adjusted)", foreground="gray", font=("Helvetica", 8)).pack(side=tk.LEFT, padx=5)

    def _format_iv(self, row) -> str:
        """Format IV from row data, checking multiple possible key names."""
        iv = row.get("iv") or row.get("implied_volatility") or row.get("impliedVolatility") or 0
        if iv:
            return f"{iv * 100:.1f}%"
        return "--"

    def _on_sl_type_changed(self):
        """Handle stop loss type change."""
        sl_type = self.sl_type.get()
        if sl_type == "CONTINGENCY":
            self.contingency_frame.grid()
            self.sl_order_combo.config(state="disabled")
            self.sl_order_type.set("Limit at Mid")  # Primary is limit
        else:
            self.contingency_frame.grid_remove()
            self.sl_order_combo.config(state="readonly")
            if sl_type == "STOP":
                self.sl_order_type.set("Market")

    def _on_stock_price_toggle(self):
        """Toggle stock price entry fields."""
        if self.use_stock_price_tp.get():
            self.tp_stock_entry.config(state="normal")
        else:
            self.tp_stock_entry.config(state="disabled")

        if self.use_stock_price_sl.get():
            self.sl_stock_entry.config(state="normal")
        else:
            self.sl_stock_entry.config(state="disabled")

    def _on_trailing_tp_toggle(self):
        """Toggle trailing TP settings."""
        if self.trailing_tp_enabled.get():
            self.trailing_tp_spin.config(state="normal")
        else:
            self.trailing_tp_spin.config(state="disabled")

    def _on_trailing_sl_toggle(self):
        """Toggle trailing SL settings."""
        if self.trailing_sl_enabled.get():
            self.trailing_sl_spin.config(state="normal")
        else:
            self.trailing_sl_spin.config(state="disabled")

    def _on_multi_tp_toggle(self):
        """Toggle multiple TP settings."""
        if self.multiple_tps_enabled.get():
            self.num_tps_spin.config(state="normal")
            self.tp_levels_container.grid()
            self._rebuild_tp_levels_ui()
        else:
            self.num_tps_spin.config(state="disabled")
            self.tp_levels_container.grid_remove()
            self._clear_tp_levels_ui()

    def _on_dynamic_toggle(self):
        """Toggle dynamic TP/SL (stub - no implementation yet)."""
        # For now, this just updates the preview to show dynamic config in play data
        self._update_preview()

    def _rebuild_tp_levels_ui(self):
        """Rebuild the dynamic TP levels input UI."""
        self._clear_tp_levels_ui()

        num_levels = self.num_tp_levels.get()
        total_contracts = self.contracts.get()

        # Header row
        header_frame = ttk.Frame(self.tp_levels_container)
        header_frame.pack(fill=tk.X, pady=(0, 5))
        ttk.Label(header_frame, text="Level", width=8).pack(side=tk.LEFT, padx=2)
        ttk.Label(header_frame, text="TP %", width=10).pack(side=tk.LEFT, padx=2)
        ttk.Label(header_frame, text="Contracts", width=10).pack(side=tk.LEFT, padx=2)
        ttk.Label(header_frame, text="% of Total", width=10).pack(side=tk.LEFT, padx=2)

        self.tp_level_widgets.append(header_frame)
        self.tp_levels_data = []

        # Calculate default contract distribution
        contracts_per_level = total_contracts // num_levels
        remainder = total_contracts % num_levels

        # Default TP percentages (escalating)
        default_tps = [25, 50, 75, 100, 150]

        for i in range(num_levels):
            level_data = {
                "pct_var": tk.DoubleVar(value=default_tps[i] if i < len(default_tps) else 50 + i * 25),
                "contracts_var": tk.IntVar(value=contracts_per_level + (1 if i < remainder else 0)),
            }
            self.tp_levels_data.append(level_data)

            level_frame = ttk.Frame(self.tp_levels_container)
            level_frame.pack(fill=tk.X, pady=2)

            ttk.Label(level_frame, text=f"TP {i + 1}:", width=8).pack(side=tk.LEFT, padx=2)

            pct_spin = ttk.Spinbox(level_frame, textvariable=level_data["pct_var"], from_=5, to=500, increment=5, width=8)
            pct_spin.pack(side=tk.LEFT, padx=2)

            contracts_spin = ttk.Spinbox(
                level_frame,
                textvariable=level_data["contracts_var"],
                from_=0,
                to=total_contracts,
                width=8,
                command=lambda: self._update_tp_percentages(),
            )
            contracts_spin.pack(side=tk.LEFT, padx=2)
            contracts_spin.bind("<FocusOut>", lambda e: self._update_tp_percentages())

            # Percentage of total label
            pct_label = ttk.Label(level_frame, text="--", width=10)
            pct_label.pack(side=tk.LEFT, padx=2)
            level_data["pct_label"] = pct_label

            self.tp_level_widgets.append(level_frame)

        # Validation row
        validation_frame = ttk.Frame(self.tp_levels_container)
        validation_frame.pack(fill=tk.X, pady=(5, 0))
        self.tp_validation_label = ttk.Label(validation_frame, text="", foreground="gray")
        self.tp_validation_label.pack(side=tk.LEFT)
        ttk.Button(validation_frame, text="Auto-Distribute", command=self._auto_distribute_contracts).pack(side=tk.RIGHT, padx=5)

        self.tp_level_widgets.append(validation_frame)
        self._update_tp_percentages()

    def _clear_tp_levels_ui(self):
        """Clear the TP levels dynamic UI."""
        for widget in self.tp_level_widgets:
            widget.destroy()
        self.tp_level_widgets = []
        self.tp_levels_data = []

    def _update_tp_percentages(self):
        """Update the percentage labels and validate contracts."""
        total_contracts = self.contracts.get()
        allocated = 0

        for level_data in self.tp_levels_data:
            contracts = level_data["contracts_var"].get()
            allocated += contracts

            if total_contracts > 0:
                pct = (contracts / total_contracts) * 100
                level_data["pct_label"].config(text=f"{pct:.0f}%")
            else:
                level_data["pct_label"].config(text="--")

        # Validate total
        if hasattr(self, "tp_validation_label"):
            if allocated == total_contracts:
                self.tp_validation_label.config(text=f"✓ {allocated}/{total_contracts} contracts allocated", foreground="green")
            elif allocated < total_contracts:
                self.tp_validation_label.config(
                    text=f"⚠ {allocated}/{total_contracts} allocated ({total_contracts - allocated} remaining)", foreground="orange"
                )
            else:
                self.tp_validation_label.config(
                    text=f"✗ {allocated}/{total_contracts} - over-allocated by {allocated - total_contracts}", foreground="red"
                )

    def _auto_distribute_contracts(self):
        """Auto-distribute contracts evenly across TP levels."""
        total_contracts = self.contracts.get()
        num_levels = len(self.tp_levels_data)

        if num_levels == 0:
            return

        contracts_per_level = total_contracts // num_levels
        remainder = total_contracts % num_levels

        for i, level_data in enumerate(self.tp_levels_data):
            # Distribute remainder to earlier levels
            level_data["contracts_var"].set(contracts_per_level + (1 if i < remainder else 0))

        self._update_tp_percentages()

    def _browse_parent_play(self):
        """Browse for a parent play file for OTO relationship."""
        # Look in temp and new directories
        initial_dir = os.path.join(project_root, "goldflipper", "plays")

        filename = filedialog.askopenfilename(title="Select Parent Play", filetypes=[("JSON files", "*.json")], initialdir=initial_dir)

        if filename:
            # Extract just the play name without path and extension
            play_name = os.path.splitext(os.path.basename(filename))[0]
            self.oto_parent.set(play_name)

    def _browse_oco_play(self):
        """Browse for OCO peer plays from NEW folder."""
        initial_dir = os.path.join(project_root, "goldflipper", "plays", "new")

        filename = filedialog.askopenfilename(
            title="Select OCO Peer Play (from NEW plays)", filetypes=[("JSON files", "*.json")], initialdir=initial_dir
        )

        if filename:
            play_name = os.path.splitext(os.path.basename(filename))[0]
            # Add to listbox if not already present
            current_items = list(self.oco_listbox.get(0, tk.END))
            if play_name not in current_items:
                self.oco_listbox.insert(tk.END, play_name)
                self._update_oco_plays_var()

    def _remove_oco_play(self):
        """Remove selected OCO peer play."""
        selection = self.oco_listbox.curselection()
        if selection:
            self.oco_listbox.delete(selection[0])
            self._update_oco_plays_var()

    def _update_oco_plays_var(self):
        """Update the oco_plays StringVar from listbox contents."""
        items = list(self.oco_listbox.get(0, tk.END))
        self.oco_plays.set(",".join(items))

    def _auto_populate_oco_peers(self):
        """Auto-populate OCO peers listbox based on OCO peer set numbers.

        Scans plays in new/ and temp/ folders for plays with matching
        oco_peer_set_numbers and adds them to the OCO peers list.
        This mirrors the CSV ingestion behavior where plays with the same
        OCO set number are automatically linked.
        """
        peer_set_str = self.oco_peer_set_numbers.get().strip()
        if not peer_set_str:
            messagebox.showinfo("No Peer Set", 'Please enter OCO peer set number(s) first.\n\nExample: "1" or "1,2" for multiple sets.')
            return

        # Parse the peer set numbers
        try:
            peer_set_nums = []
            for part in peer_set_str.replace(";", ",").split(","):
                part = part.strip()
                if part:
                    peer_set_nums.append(int(part))
        except ValueError:
            messagebox.showerror("Invalid Input", 'Please enter valid numbers separated by commas.\n\nExample: "1" or "1,2,3"')
            return

        if not peer_set_nums:
            return

        # Scan for matching plays
        matching_plays = self._scan_plays_for_oco_peer_sets(peer_set_nums)

        if not matching_plays:
            messagebox.showinfo(
                "No Matches",
                f"No plays found with OCO peer set number(s): {peer_set_nums}\n\nPlays must have 'oco_peer_set_numbers' field to be matched.",
            )
            return

        # Get current items in listbox
        current_items = set(self.oco_listbox.get(0, tk.END))

        # Add matching plays that aren't already in the list
        added_count = 0
        for play_name in matching_plays:
            if play_name not in current_items:
                self.oco_listbox.insert(tk.END, play_name)
                added_count += 1

        self._update_oco_plays_var()

        if added_count > 0:
            messagebox.showinfo("Peers Added", f"Added {added_count} matching play(s) to OCO peers.\n\nTotal peers: {self.oco_listbox.size()}")
        else:
            messagebox.showinfo("No New Peers", "All matching plays are already in the OCO peers list.")

    def _scan_plays_for_oco_peer_sets(self, target_set_numbers: list[int]) -> list[str]:
        """Scan plays folders for plays with matching OCO peer set numbers.

        Args:
            target_set_numbers: List of OCO peer set numbers to match.

        Returns:
            List of play names (without .json extension) that match any of the
            target set numbers.
        """
        matching_plays = []
        base_dir = os.path.join(project_root, "goldflipper", "plays")

        # Scan both new/ and temp/ folders
        folders_to_scan = ["new", "temp"]

        for folder in folders_to_scan:
            folder_path = os.path.join(base_dir, folder)
            if not os.path.exists(folder_path):
                continue

            for filename in os.listdir(folder_path):
                if not filename.endswith(".json"):
                    continue

                filepath = os.path.join(folder_path, filename)
                try:
                    with open(filepath) as f:
                        play_data = json.load(f)

                    # Check for oco_peer_set_numbers field
                    play_peer_sets = play_data.get("oco_peer_set_numbers", [])

                    # Handle both list and comma-separated string formats
                    if isinstance(play_peer_sets, str):
                        play_peer_sets = [int(x.strip()) for x in play_peer_sets.split(",") if x.strip().isdigit()]
                    elif not isinstance(play_peer_sets, list):
                        play_peer_sets = []

                    # Check for any matching set numbers
                    if any(num in play_peer_sets for num in target_set_numbers):
                        play_name = os.path.splitext(filename)[0]
                        if play_name not in matching_plays:
                            matching_plays.append(play_name)

                except (OSError, json.JSONDecodeError, KeyError) as e:
                    # Skip invalid files
                    logging.debug(f"Skipping {filename}: {e}")
                    continue

        return matching_plays

    def _get_oco_peer_set_numbers_list(self) -> list[int]:
        """Parse OCO peer set numbers from the entry field into a list of integers.

        Returns:
            List of OCO peer set numbers, or empty list if none specified.
        """
        peer_set_str = self.oco_peer_set_numbers.get().strip()
        if not peer_set_str:
            return []

        try:
            result = []
            for part in peer_set_str.replace(";", ",").split(","):
                part = part.strip()
                if part:
                    result.append(int(part))
            return result
        except ValueError:
            return []

    def _browse_oso_play(self):
        """Browse for OSO (OTO) plays from TEMP folder."""
        initial_dir = os.path.join(project_root, "goldflipper", "plays", "temp")
        os.makedirs(initial_dir, exist_ok=True)  # Ensure temp folder exists

        filename = filedialog.askopenfilename(
            title="Select OSO/OTO Play (from TEMP plays)", filetypes=[("JSON files", "*.json")], initialdir=initial_dir
        )

        if filename:
            play_name = os.path.splitext(os.path.basename(filename))[0]
            # Add to listbox if not already present
            current_items = list(self.oso_listbox.get(0, tk.END))
            if play_name not in current_items:
                self.oso_listbox.insert(tk.END, play_name)

    def _remove_oso_play(self):
        """Remove selected OSO (OTO) play."""
        selection = self.oso_listbox.curselection()
        if selection:
            self.oso_listbox.delete(selection[0])

    def _on_play_class_changed(self):
        """Handle play class change (SIMPLE vs OTO)."""
        # OTO plays use the OSO listbox to specify child plays
        # No special UI change needed - the OSO section is always visible
        pass

    def _build_conditional_plays(self) -> dict[str, Any]:
        """Build the conditional_plays section for OCO/OTO relationships."""
        conditional = {}

        # OCO (One-Cancels-Other) relationship from listbox
        oco_list = list(self.oco_listbox.get(0, tk.END))
        if oco_list:
            conditional["oco"] = {
                "peer_plays": oco_list,
                "cancel_on": "any_fill",  # Cancel peers when this play fills
            }

        # OSO/OTO (One-Sends-Other / One-Triggers-Other) relationship from listbox
        oso_list = list(self.oso_listbox.get(0, tk.END))
        if oso_list:
            conditional["oso"] = {
                "child_plays": oso_list,
                "trigger_on": "fill",  # Trigger children when this play fills
            }

        # Legacy OTO parent support (for backward compatibility)
        oto_parent = self.oto_parent.get().strip()
        if oto_parent:
            conditional["oto"] = {"parent_play": oto_parent, "trigger_condition": self.oto_trigger_condition.get(), "triggered": False}

        return conditional

    def _infer_play_class(self) -> str:
        """Infer play class from conditional orders.

        OTO = This play IS a child, waiting to be triggered by a parent (goes to TEMP).
        SIMPLE = This play executes on its own, possibly triggering children (goes to NEW).

        Note: Having OSO children doesn't make this play OTO - it's still SIMPLE but
        will trigger children when it fills. OTO is when THIS play has a parent.
        """
        # Check if this play has a parent (i.e., is a child waiting to be triggered)
        oto_parent = self.oto_parent.get().strip()
        if oto_parent:
            return "OTO"
        return "SIMPLE"

    def _create_option_chain_panel(self, parent):
        """Create the option chain browser panel."""
        frame = ttk.LabelFrame(parent, text="Option Chain Browser", padding="10")
        frame.grid(row=0, column=0, sticky="ew", pady=5)
        frame.columnconfigure(0, weight=1)

        # Filter frame - includes symbol, price, delta range, and refresh
        filter_frame = ttk.Frame(frame)
        filter_frame.grid(row=0, column=0, sticky="ew", pady=5)

        # Symbol entry (left side)
        ttk.Label(filter_frame, text="Symbol:").pack(side=tk.LEFT, padx=(0, 2))
        symbol_entry = ttk.Entry(filter_frame, textvariable=self.symbol, width=8)
        symbol_entry.pack(side=tk.LEFT, padx=(0, 5))
        symbol_entry.bind("<Return>", lambda e: self._fetch_market_data())

        ttk.Button(filter_frame, text="Fetch", command=self._fetch_market_data, width=5).pack(side=tk.LEFT, padx=(0, 10))

        # Price display
        ttk.Label(filter_frame, text="Price:", foreground="gray").pack(side=tk.LEFT, padx=(0, 2))
        ttk.Label(filter_frame, textvariable=self.current_price, font=("Helvetica", 9, "bold")).pack(side=tk.LEFT, padx=(0, 5))

        ttk.Label(filter_frame, text="Bid:", foreground="gray").pack(side=tk.LEFT, padx=(0, 2))
        ttk.Label(filter_frame, textvariable=self.bid_price, font=("Helvetica", 9)).pack(side=tk.LEFT, padx=(0, 5))

        ttk.Label(filter_frame, text="Ask:", foreground="gray").pack(side=tk.LEFT, padx=(0, 2))
        ttk.Label(filter_frame, textvariable=self.ask_price, font=("Helvetica", 9)).pack(side=tk.LEFT, padx=(0, 15))

        # Delta range (moved to right side)
        ttk.Label(filter_frame, text="Delta:").pack(side=tk.LEFT, padx=(0, 2))
        self.delta_min = tk.DoubleVar(value=0.20)
        self.delta_max = tk.DoubleVar(value=0.80)

        ttk.Spinbox(filter_frame, textvariable=self.delta_min, from_=0.0, to=1.0, increment=0.05, width=5).pack(side=tk.LEFT, padx=2)

        ttk.Label(filter_frame, text="-").pack(side=tk.LEFT)

        ttk.Spinbox(filter_frame, textvariable=self.delta_max, from_=0.0, to=1.0, increment=0.05, width=5).pack(side=tk.LEFT, padx=2)

        ttk.Button(filter_frame, text="Refresh Chain", command=self._refresh_option_chain).pack(side=tk.RIGHT, padx=5)

        # Option chain treeview
        tree_frame = ttk.Frame(frame)
        tree_frame.grid(row=1, column=0, sticky="nsew", pady=5)
        tree_frame.columnconfigure(0, weight=1)
        tree_frame.rowconfigure(0, weight=1)

        columns = ("Strike", "Bid", "Ask", "Last", "Delta", "Theta", "IV", "Volume", "OI")
        self.chain_tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=8)

        # Configure columns
        col_widths = {"Strike": 70, "Bid": 60, "Ask": 60, "Last": 60, "Delta": 60, "Theta": 60, "IV": 60, "Volume": 60, "OI": 60}
        for col in columns:
            self.chain_tree.heading(col, text=col, command=lambda c=col: self._sort_chain(c))
            self.chain_tree.column(col, width=col_widths.get(col, 60), anchor="center")

        # Scrollbars
        v_scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=self.chain_tree.yview)
        h_scroll = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.chain_tree.xview)
        self.chain_tree.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)

        self.chain_tree.grid(row=0, column=0, sticky="nsew")
        v_scroll.grid(row=0, column=1, sticky="ns")
        h_scroll.grid(row=1, column=0, sticky="ew")

        # Bind selection event
        self.chain_tree.bind("<<TreeviewSelect>>", self._on_chain_select)
        self.chain_tree.bind("<Double-1>", self._on_chain_double_click)

        # Selected option info (legend removed - double-click hint was redundant)
        legend_frame = ttk.Frame(frame)
        legend_frame.grid(row=2, column=0, sticky="ew", pady=5)

        ttk.Label(legend_frame, text="ATM=green | ITM=orange | OTM=white", foreground="gray", font=("Helvetica", 8)).pack(side=tk.LEFT)

        # Selected option info
        self.selected_option_label = ttk.Label(legend_frame, text="Double-click row to select", font=("Helvetica", 9), foreground="gray")
        self.selected_option_label.pack(side=tk.RIGHT, padx=10)

    def _create_preview_panel(self, parent):
        """Create the validation and preview panel (upper right column)."""
        frame = ttk.LabelFrame(parent, text="Play Preview", padding="10")
        frame.grid(row=0, column=0, sticky="nsew", pady=5)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)

        # JSON preview text - reduced height to make room for advanced settings
        self.preview_text = tk.Text(frame, height=28, width=45, wrap=tk.WORD)
        self.preview_text.grid(row=0, column=0, sticky="nsew")

        preview_scroll = ttk.Scrollbar(frame, orient="vertical", command=self.preview_text.yview)
        preview_scroll.grid(row=0, column=1, sticky="ns")
        self.preview_text.configure(yscrollcommand=preview_scroll.set)

        # Validation messages
        self.validation_frame = ttk.Frame(frame)
        self.validation_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=5)

        self.validation_label = ttk.Label(self.validation_frame, text="Enter symbol and fetch data to preview play", foreground="gray")
        self.validation_label.pack(side=tk.LEFT)

        ttk.Button(self.validation_frame, text="Update Preview", command=self._update_preview).pack(side=tk.RIGHT, padx=5)

    def _create_advanced_settings_panel(self, parent):
        """Create the advanced settings panel for momentum strategy (below preview)."""
        self.advanced_settings_frame = ttk.LabelFrame(parent, text="Advanced Settings (Momentum)", padding="10")
        self.advanced_settings_frame.grid(row=1, column=0, sticky="nsew", pady=5)
        self.advanced_settings_frame.columnconfigure(0, weight=1)
        self.advanced_settings_frame.columnconfigure(1, weight=1)

        # === Row 0: Gap Size Filtering ===
        gap_filter_frame = ttk.Frame(self.advanced_settings_frame)
        gap_filter_frame.grid(row=0, column=0, columnspan=2, sticky="ew", pady=2)

        ttk.Label(gap_filter_frame, text="Gap Size:").pack(side=tk.LEFT, padx=(0, 5))
        ttk.Label(gap_filter_frame, text="Min:").pack(side=tk.LEFT)
        ttk.Spinbox(gap_filter_frame, textvariable=self.adv_min_gap_pct, from_=0.5, to=10.0, increment=0.5, width=5).pack(side=tk.LEFT, padx=2)
        ttk.Label(gap_filter_frame, text="%").pack(side=tk.LEFT)

        ttk.Checkbutton(gap_filter_frame, text="Max:", variable=self.adv_max_gap_pct_enabled).pack(side=tk.LEFT, padx=(15, 0))
        self.adv_max_gap_spinbox = ttk.Spinbox(gap_filter_frame, textvariable=self.adv_max_gap_pct, from_=2.0, to=20.0, increment=0.5, width=5)
        self.adv_max_gap_spinbox.pack(side=tk.LEFT, padx=2)
        ttk.Label(gap_filter_frame, text="%").pack(side=tk.LEFT)

        # === Row 1: Time-Based Exit Controls ===
        time_exit_frame = ttk.Frame(self.advanced_settings_frame)
        time_exit_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=2)

        ttk.Checkbutton(time_exit_frame, text="Same-Day Exit", variable=self.adv_same_day_exit).pack(side=tk.LEFT, padx=(0, 15))

        ttk.Checkbutton(time_exit_frame, text="Max Hold Days:", variable=self.adv_max_hold_days_enabled).pack(side=tk.LEFT)
        ttk.Spinbox(time_exit_frame, textvariable=self.adv_max_hold_days, from_=1, to=30, increment=1, width=4).pack(side=tk.LEFT, padx=2)

        # === Row 2: Entry Timing ===
        entry_timing_frame = ttk.Frame(self.advanced_settings_frame)
        entry_timing_frame.grid(row=2, column=0, columnspan=2, sticky="ew", pady=2)

        ttk.Label(entry_timing_frame, text="Avoid Entry:").pack(side=tk.LEFT, padx=(0, 5))
        ttk.Label(entry_timing_frame, text="First").pack(side=tk.LEFT)
        ttk.Spinbox(entry_timing_frame, textvariable=self.adv_avoid_first_minutes, from_=0, to=60, increment=5, width=4).pack(side=tk.LEFT, padx=2)
        ttk.Label(entry_timing_frame, text="min").pack(side=tk.LEFT)

        ttk.Label(entry_timing_frame, text="Last").pack(side=tk.LEFT, padx=(15, 0))
        ttk.Spinbox(entry_timing_frame, textvariable=self.adv_avoid_last_minutes, from_=0, to=120, increment=15, width=4).pack(side=tk.LEFT, padx=2)
        ttk.Label(entry_timing_frame, text="min").pack(side=tk.LEFT)

        # === Row 3: DTE Range ===
        dte_frame = ttk.Frame(self.advanced_settings_frame)
        dte_frame.grid(row=3, column=0, columnspan=2, sticky="ew", pady=2)

        ttk.Label(dte_frame, text="DTE Range:").pack(side=tk.LEFT, padx=(0, 5))
        ttk.Spinbox(dte_frame, textvariable=self.adv_dte_min, from_=1, to=60, increment=1, width=4).pack(side=tk.LEFT, padx=2)
        ttk.Label(dte_frame, text="-").pack(side=tk.LEFT)
        ttk.Spinbox(dte_frame, textvariable=self.adv_dte_max, from_=7, to=90, increment=1, width=4).pack(side=tk.LEFT, padx=2)
        ttk.Label(dte_frame, text="days").pack(side=tk.LEFT)

        # Info label
        info_label = ttk.Label(
            self.advanced_settings_frame, text="These settings override playbook defaults for this play.", foreground="gray", font=("Helvetica", 8)
        )
        info_label.grid(row=4, column=0, columnspan=2, sticky="w", pady=(5, 0))

        # Initially hide (only show for momentum strategy)
        self.advanced_settings_frame.grid_remove()

    def _create_risk_summary_panel(self, parent):
        """Create the risk summary panel (below option chain)."""
        frame = ttk.LabelFrame(parent, text="Risk Summary", padding="10")
        frame.grid(row=1, column=0, sticky="ew", pady=5)
        frame.columnconfigure(0, weight=1)

        # Risk calculation (horizontal)
        risk_frame = ttk.Frame(frame)
        risk_frame.pack(fill=tk.X)

        self.risk_labels = {}
        risk_items = [
            ("Max Risk:", "max_risk"),
            ("Max Profit:", "max_profit"),
            ("Break Even:", "break_even"),
            ("BP Req:", "buying_power"),
        ]

        for label, key in risk_items:
            ttk.Label(risk_frame, text=label, font=("Helvetica", 9)).pack(side=tk.LEFT, padx=(5, 0))
            self.risk_labels[key] = ttk.Label(risk_frame, text="--", font=("Helvetica", 9, "bold"))
            self.risk_labels[key].pack(side=tk.LEFT, padx=(0, 15))

    def _create_action_buttons_panel(self, parent):
        """Create the action buttons panel (between risk summary and conditional orders)."""
        frame = ttk.LabelFrame(parent, text="Actions", padding="10")
        frame.grid(row=2, column=0, sticky="ew", pady=5)
        frame.columnconfigure(0, weight=1)

        # Center the buttons
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(anchor="center", pady=5)

        self.create_btn = ttk.Button(btn_frame, text="Create Play", command=self._create_play, width=14)
        self.create_btn.pack(side=tk.LEFT, padx=5, pady=3)

        ttk.Button(btn_frame, text="Save Template", command=self._save_template, width=14).pack(side=tk.LEFT, padx=5, pady=3)

        ttk.Button(btn_frame, text="Load Template", command=self._load_template, width=14).pack(side=tk.LEFT, padx=5, pady=3)

        ttk.Button(btn_frame, text="Clear All", command=self._clear_all, width=14).pack(side=tk.LEFT, padx=5, pady=3)

    def _create_conditional_orders_panel(self, parent):
        """Create the conditional orders panel (OCO/OSO)."""
        frame = ttk.LabelFrame(parent, text="Conditional Orders", padding="10")
        frame.grid(row=3, column=0, sticky="ew", pady=5)
        frame.columnconfigure(0, weight=1)

        # OCO Peer Set Number input (for automatic grouping like CSV ingestion)
        peer_set_frame = ttk.Frame(frame)
        peer_set_frame.pack(fill=tk.X, pady=(0, 5))

        ttk.Label(peer_set_frame, text="OCO Peer Set #:").pack(side=tk.LEFT)
        self.oco_peer_set_entry = ttk.Entry(peer_set_frame, textvariable=self.oco_peer_set_numbers, width=12)
        self.oco_peer_set_entry.pack(side=tk.LEFT, padx=5)

        ttk.Button(peer_set_frame, text="Auto-Populate", command=self._auto_populate_oco_peers, width=12).pack(side=tk.LEFT, padx=5)

        ttk.Label(peer_set_frame, text='(Enter set numbers e.g. "1" or "1,2" to find matching plays)', foreground="gray", font=("Helvetica", 8)).pack(
            side=tk.LEFT, padx=5
        )

        # OCO (One-Cancels-Other)
        oco_frame = ttk.Frame(frame)
        oco_frame.pack(fill=tk.X, pady=2)

        ttk.Label(oco_frame, text="OCO Peers:").pack(side=tk.LEFT)
        self.oco_listbox = tk.Listbox(oco_frame, height=2, width=25)
        self.oco_listbox.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)

        oco_btn_frame = ttk.Frame(oco_frame)
        oco_btn_frame.pack(side=tk.LEFT, padx=5)
        ttk.Button(oco_btn_frame, text="Add", command=self._browse_oco_play, width=8).pack(pady=1)
        ttk.Button(oco_btn_frame, text="Remove", command=self._remove_oco_play, width=8).pack(pady=1)

        # OSO/OTO (One-Sends-Other / One-Triggers-Other)
        oso_frame = ttk.Frame(frame)
        oso_frame.pack(fill=tk.X, pady=2)

        ttk.Label(oso_frame, text="OSO (OTO):").pack(side=tk.LEFT)
        self.oso_listbox = tk.Listbox(oso_frame, height=2, width=25)
        self.oso_listbox.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)

        oso_btn_frame = ttk.Frame(oso_frame)
        oso_btn_frame.pack(side=tk.LEFT, padx=5)
        ttk.Button(oso_btn_frame, text="Add", command=self._browse_oso_play, width=8).pack(pady=1)
        ttk.Button(oso_btn_frame, text="Remove", command=self._remove_oso_play, width=8).pack(pady=1)

        # OCO Peer Sets Config display from settings
        oco_config = self._get_oco_peer_set_config()
        config_text = (
            "[ SETTINGS ] OCO Peer Sets automatic reloading configured: "
            f"TP {oco_config.get('take_profit_pct', 50)}% | "
            f"SL {oco_config.get('stop_loss_pct', 30)}% | "
            f"Entry Buffer {oco_config.get('entry_buffer', 0.05) * 100:.0f}%"
        )
        self.oco_config_label = ttk.Label(frame, text=config_text, foreground="blue", font=("Helvetica", 8))
        self.oco_config_label.pack(fill=tk.X, pady=(5, 0))

    def _get_oco_peer_set_config(self) -> dict[str, Any]:
        """Get OCO peer set configuration from settings."""
        try:
            oco_config = config.get("auto_play_creator.oco_peer_set", default={})
            if oco_config is None:
                oco_config = {}
            return {
                "take_profit_pct": oco_config.get("take_profit_pct", 50.0) if isinstance(oco_config, dict) else 50.0,
                "stop_loss_pct": oco_config.get("stop_loss_pct", 30.0) if isinstance(oco_config, dict) else 30.0,
                "entry_buffer": oco_config.get("entry_buffer", 0.05) if isinstance(oco_config, dict) else 0.05,
            }
        except Exception:
            return {"take_profit_pct": 50.0, "stop_loss_pct": 30.0, "entry_buffer": 0.05}

    def _create_other_options_panel(self, parent):
        """Create the other options panel with strategy-specific config."""
        self.other_options_frame = ttk.LabelFrame(parent, text="Other Options", padding="10")
        self.other_options_frame.grid(row=4, column=0, sticky="nsew", pady=5)
        self.other_options_frame.columnconfigure(0, weight=1)

        # === Momentum Timing Config (shown only for momentum strategy) ===
        self.momentum_options_frame = ttk.LabelFrame(self.other_options_frame, text="Momentum Timing", padding="5")
        self.momentum_options_frame.pack(fill=tk.X, pady=(0, 5))

        # Row 1: No Entry Until X:XX AM (consolidates wait for confirmation + first hour)
        entry_time_frame = ttk.Frame(self.momentum_options_frame)
        entry_time_frame.pack(fill=tk.X, pady=2)

        ttk.Label(entry_time_frame, text="No Entry Until:").pack(side=tk.LEFT, padx=5)
        ttk.Spinbox(entry_time_frame, textvariable=self.momentum_confirmation_minutes, from_=0, to=120, width=4).pack(side=tk.LEFT, padx=2)
        ttk.Label(entry_time_frame, text="mins after 9:30 AM", foreground="gray").pack(side=tk.LEFT, padx=2)

        # Row 2: Lunch Break Restriction
        lunch_frame = ttk.Frame(self.momentum_options_frame)
        lunch_frame.pack(fill=tk.X, pady=2)

        ttk.Checkbutton(lunch_frame, text="Lunch Break:", variable=self.momentum_lunch_break_enabled).pack(side=tk.LEFT, padx=5)

        ttk.Spinbox(lunch_frame, textvariable=self.momentum_lunch_start_hour, from_=9, to=15, width=3).pack(side=tk.LEFT)
        ttk.Label(lunch_frame, text=":").pack(side=tk.LEFT)
        ttk.Spinbox(lunch_frame, textvariable=self.momentum_lunch_start_minute, from_=0, to=59, width=3).pack(side=tk.LEFT)
        ttk.Label(lunch_frame, text="-").pack(side=tk.LEFT, padx=3)
        ttk.Spinbox(lunch_frame, textvariable=self.momentum_lunch_end_hour, from_=10, to=16, width=3).pack(side=tk.LEFT)
        ttk.Label(lunch_frame, text=":").pack(side=tk.LEFT)
        ttk.Spinbox(lunch_frame, textvariable=self.momentum_lunch_end_minute, from_=0, to=59, width=3).pack(side=tk.LEFT)
        ttk.Label(lunch_frame, text="ET", foreground="gray").pack(side=tk.LEFT, padx=3)

        # Initially hide momentum options
        self.momentum_options_frame.pack_forget()

        # === Goldflipper Gap Move Config (shown only for that playbook) ===
        self.goldflipper_options_frame = ttk.LabelFrame(self.other_options_frame, text="⭐ Goldflipper Gap Move", padding="5")
        self.goldflipper_options_frame.pack(fill=tk.X, pady=(0, 5))

        # Straddle check row
        straddle_frame = ttk.Frame(self.goldflipper_options_frame)
        straddle_frame.pack(fill=tk.X, pady=2)

        ttk.Checkbutton(straddle_frame, text="Straddle Check:", variable=self.goldflipper_gap_straddle_enabled).pack(side=tk.LEFT, padx=5)
        ttk.Label(straddle_frame, text="Min Ratio:").pack(side=tk.LEFT, padx=(5, 2))
        ttk.Spinbox(straddle_frame, textvariable=self.goldflipper_gap_min_straddle_ratio, from_=0.5, to=3.0, increment=0.1, width=5).pack(
            side=tk.LEFT
        )

        # OI check row
        oi_frame = ttk.Frame(self.goldflipper_options_frame)
        oi_frame.pack(fill=tk.X, pady=2)

        ttk.Checkbutton(oi_frame, text="Open Interest:", variable=self.goldflipper_gap_oi_enabled).pack(side=tk.LEFT, padx=5)
        ttk.Label(oi_frame, text="Min OI:").pack(side=tk.LEFT, padx=(5, 2))
        ttk.Spinbox(oi_frame, textvariable=self.goldflipper_gap_min_directional_oi, from_=100, to=5000, increment=100, width=6).pack(side=tk.LEFT)
        ttk.Label(oi_frame, text="Ratio:").pack(side=tk.LEFT, padx=(5, 2))
        ttk.Spinbox(oi_frame, textvariable=self.goldflipper_gap_min_oi_ratio, from_=0.5, to=3.0, increment=0.1, width=5).pack(side=tk.LEFT)

        # Auto contract selection info
        auto_info = ttk.Label(
            self.goldflipper_options_frame,
            text="Auto-selects ATM contract ≤14 DTE based on gap direction",
            foreground="#DAA520",
            font=("Helvetica", 8),
        )
        auto_info.pack(fill=tk.X, padx=5, pady=(2, 0))

        # Initially hide goldflipper options
        self.goldflipper_options_frame.pack_forget()

        # Placeholder when no strategy-specific options
        self.no_options_label = ttk.Label(
            self.other_options_frame, text="No additional options for this strategy/playbook.", foreground="gray", font=("Helvetica", 8)
        )
        self.no_options_label.pack(anchor="w")

    # =========================================================================
    # Event Handlers
    # =========================================================================

    def _on_canvas_configure(self, event):
        """Handle canvas resize - stretch main_frame to fill available width."""
        # Update the width of the canvas window to match canvas width
        self.main_canvas.itemconfig(self.canvas_window, width=event.width)

    def _bind_events(self):
        """Bind keyboard and other events."""
        self.root.bind("<F5>", lambda e: self._fetch_market_data())
        self.root.bind("<Control-s>", lambda e: self._create_play())
        self.root.bind("<Control-n>", lambda e: self._clear_all())

    def _on_strategy_changed(self, event=None):
        """Handle strategy selection change."""
        strategy_str = self.current_strategy.get()

        # Update description
        try:
            strategy = StrategyType(strategy_str)
            self.strategy_desc_label.config(text=STRATEGY_DESCRIPTIONS.get(strategy, ""))
        except ValueError:
            pass

        # Update playbook options
        self._update_playbook_options()

        # Update gap visibility
        self._update_gap_visibility()

        # Update trade type for sell_puts (always PUT)
        if strategy_str == StrategyType.SELL_PUTS.value:
            self.trade_type.set("PUT")

        # Update preview
        self._update_preview()

    def _get_playbook_value_from_display(self, display_name: str) -> str:
        """Map playbook display name to internal value."""
        try:
            strategy = StrategyType(self.current_strategy.get())
            playbooks = STRATEGY_PLAYBOOKS.get(strategy, [])
            for pb in playbooks:
                if pb[0] == display_name:  # pb[0] is display name, pb[1] is value
                    return pb[1]
        except (ValueError, KeyError):
            pass
        return display_name  # Fallback to display name if not found

    def _on_playbook_changed(self, event=None):
        """Handle playbook selection change."""
        # Map display name to internal value (Combobox textvariable stores display text)
        display_name = self.current_playbook.get()
        playbook = self._get_playbook_value_from_display(display_name)
        strategy_str = self.current_strategy.get()

        # Load playbook defaults
        self._load_playbook_defaults(strategy_str, playbook)

        # Update playbook type indicator (CUSTOM vs TEMPLATE)
        self._update_playbook_type_indicator(playbook)

        # Update visibility of strategy-specific panels (e.g., Goldflipper Gap Move config)
        self._update_gap_visibility()

        # Auto-select contract for Goldflipper Gap Move (user can still change it)
        if playbook == "goldflipper_gap_move":
            self._auto_select_goldflipper_contract()

        # Update preview
        self._update_preview()

    def _auto_select_goldflipper_contract(self):
        """Auto-select contract for Goldflipper Gap Move based on gap direction and ATM strike.

        Called when playbook changes to goldflipper_gap_move OR after market data is fetched.
        - Trade type: set from gap direction (UP→CALL, DOWN→PUT)
        - Expiration: first available ≤14 DTE
        - Strike: ATM (select row in treeview and populate all fields)
        """
        # Set trade type based on gap direction (if gap data available)
        gap_type = self.gap_type.get().upper()
        if gap_type == "UP":
            self.trade_type.set("CALL")
        elif gap_type == "DOWN":
            self.trade_type.set("PUT")

        # Auto-select expiration ≤14 DTE (without triggering chain refresh here)
        if self.expirations_list:
            today = datetime.now()
            for exp in self.expirations_list:
                try:
                    exp_date = datetime.strptime(exp, "%Y-%m-%d")
                    dte = (exp_date - today).days
                    if 0 < dte <= 14:
                        self.expiration.set(exp)
                        break
                except ValueError:
                    continue

        # Auto-select ATM strike in the treeview
        try:
            current_price = float(self.current_price.get().replace("$", "").replace("--", "0"))
            if current_price > 0 and self.chain_tree.get_children():
                # Find ATM strike row
                best_item = None
                best_diff = float("inf")
                for item_id in self.chain_tree.get_children():
                    item_values = self.chain_tree.item(item_id, "values")
                    if item_values:
                        try:
                            strike = float(item_values[0])
                            diff = abs(strike - current_price)
                            if diff < best_diff:
                                best_diff = diff
                                best_item = item_id
                        except (ValueError, IndexError):
                            continue

                if best_item:
                    # Select the row, scroll to it, and trigger double-click to populate fields
                    self.chain_tree.selection_set(best_item)
                    self.chain_tree.see(best_item)
                    self._on_chain_double_click()  # Populates strike, entry price, greeks, updates preview
        except (ValueError, TypeError):
            pass

        self._update_contract_preview()

    def _on_expiration_changed(self, event=None):
        """Handle expiration selection change."""
        # Update DTE label
        expiration = self.expiration.get()
        if expiration:
            try:
                exp_date = datetime.strptime(expiration, "%Y-%m-%d")
                dte = (exp_date - datetime.now()).days
                self.dte_label.config(text=f"({dte} DTE)")
            except ValueError:
                self.dte_label.config(text="")
        else:
            self.dte_label.config(text="")

        self._refresh_option_chain()
        self._update_preview()
        self._update_contract_preview()

    def _on_trade_type_changed(self):
        """Handle trade type change."""
        self._refresh_option_chain()
        self._update_preview()
        self._update_contract_preview()

    def _on_strike_changed(self, event=None):
        """Handle strike price change."""
        # Try to populate option data from chain if available
        self._populate_option_from_chain()
        self._update_preview()
        self._update_risk_summary()
        self._update_contract_preview()

    def _on_contracts_changed(self):
        """Handle contracts change."""
        self._update_risk_summary()
        self._update_preview()
        if self.multiple_tps_enabled.get():
            self._rebuild_tp_levels_ui()

    def _on_entry_order_type_changed(self, event=None):
        """Handle entry order type change - update entry price based on selected type."""
        entry_type = self.entry_order_type.get()
        bid = self.option_bid.get()
        ask = self.option_ask.get()
        mid = self.option_mid.get()
        last = self.option_last.get()

        if mid > 0 or last > 0:  # Only update if we have option data
            if entry_type == "Market":
                self.entry_price.set(round(mid if mid > 0 else last, 2))
            elif entry_type == "Limit at Bid":
                self.entry_price.set(round(bid, 2))
            elif entry_type == "Limit at Ask":
                self.entry_price.set(round(ask, 2))
            elif entry_type == "Limit at Last":
                self.entry_price.set(round(last, 2))
            else:  # Limit at Mid
                self.entry_price.set(round(mid, 2))

            self._calculate_tp_sl_prices()
            self._update_price_displays()
            self._update_preview()

    def _on_entry_price_changed(self):
        """Handle entry price change."""
        self._calculate_tp_sl_prices()
        self._update_risk_summary()
        self._update_preview()

    def _on_tp_sl_changed(self):
        """Handle TP/SL percentage change."""
        self._calculate_tp_sl_prices()
        self._update_stock_pct_targets()
        self._update_risk_summary()
        self._update_preview()

    def _on_stock_pct_toggle(self):
        """Toggle stock price percentage entry fields."""
        if self.use_stock_pct_tp.get():
            self.tp_stock_pct_spin.config(state="normal")
            self._update_stock_pct_targets()
        else:
            self.tp_stock_pct_spin.config(state="disabled")
            self.tp_stock_pct_target_label.config(text="")

        if self.use_stock_pct_sl.get():
            self.sl_stock_pct_spin.config(state="normal")
            self._update_stock_pct_targets()
        else:
            self.sl_stock_pct_spin.config(state="disabled")
            self.sl_stock_pct_target_label.config(text="")

        self._update_preview()

    def _populate_option_from_chain(self):
        """Populate option data from chain based on selected strike."""
        strike_str = self.strike_price.get()
        if not strike_str or self.option_chain_data is None:
            return

        try:
            strike = float(strike_str)
            row = self.option_chain_data[abs(self.option_chain_data["strike"] - strike) < 0.01]
            if not row.empty:
                row = row.iloc[0]
                bid = row.get("bid", 0)
                ask = row.get("ask", 0)
                last = row.get("last", 0)
                delta = abs(row.get("delta", 0))
                theta = row.get("theta", 0)
                # Check multiple possible key names for IV
                iv = row.get("iv") or row.get("implied_volatility") or row.get("impliedVolatility") or 0

                self.option_bid.set(bid)
                self.option_ask.set(ask)
                self.option_last.set(last)
                mid = (bid + ask) / 2 if bid and ask else last
                self.option_mid.set(round(mid, 2))

                self.selected_delta.set(round(delta, 3))
                self.selected_theta.set(round(theta, 3))
                self.selected_iv.set(round(iv * 100, 1) if iv else 0)

                # Set entry price based on order type
                self._on_entry_order_type_changed()
                self._update_price_displays()
                self._update_selected_option_display()
        except Exception:
            pass

    def _update_price_displays(self):
        """Update the bid/ask/mid/last display labels."""
        bid = self.option_bid.get()
        ask = self.option_ask.get()
        mid = self.option_mid.get()
        last = self.option_last.get()

        self.bid_display.config(text=f"${bid:.2f}" if bid > 0 else "--")
        self.ask_display.config(text=f"${ask:.2f}" if ask > 0 else "--")
        self.mid_display.config(text=f"${mid:.2f}" if mid > 0 else "--")
        self.last_display.config(text=f"${last:.2f}" if last > 0 else "--")

    def _update_stock_pct_targets(self):
        """Update the calculated stock price targets based on percentage change."""
        try:
            current_price = float(self.current_price.get().replace("$", "").replace("--", "0"))
            if current_price > 0:
                if self.use_stock_pct_tp.get():
                    tp_pct = self.tp_stock_pct.get()
                    tp_target = current_price * (1 + tp_pct / 100)
                    self.tp_stock_pct_target_label.config(text=f"→ ${tp_target:.2f}")

                if self.use_stock_pct_sl.get():
                    sl_pct = self.sl_stock_pct.get()
                    sl_target = current_price * (1 + sl_pct / 100)
                    self.sl_stock_pct_target_label.config(text=f"→ ${sl_target:.2f}")
        except Exception:
            pass

    def _on_chain_select(self, event=None):
        """Handle option chain row selection."""
        selection = self.chain_tree.selection()
        if selection:
            item = self.chain_tree.item(selection[0])
            values = item["values"]
            if values:
                strike = values[0]
                delta = values[4]
                self.selected_option_label.config(text=f"Selected: {strike} strike (Δ={delta})")

    def _on_chain_double_click(self, event=None):
        """Handle double-click on option chain row - pre-fill all relevant values."""
        selection = self.chain_tree.selection()
        if selection:
            item = self.chain_tree.item(selection[0])
            values = item["values"]
            if values and len(values) >= 9:
                # Parse values: (Strike, Bid, Ask, Last, Delta, Theta, IV, Volume, OI)
                strike = str(values[0])
                bid = float(str(values[1]).replace("--", "0"))
                ask = float(str(values[2]).replace("--", "0"))
                last = float(str(values[3]).replace("--", "0"))
                delta = float(str(values[4]).replace("--", "0"))
                theta = float(str(values[5]).replace("--", "0"))
                iv_str = str(values[6]).replace("%", "").replace("--", "0")
                iv = float(iv_str) / 100 if iv_str else 0

                # Set strike price
                self.strike_price.set(strike)

                # Set option price data
                self.option_bid.set(bid)
                self.option_ask.set(ask)
                self.option_last.set(last)
                mid = (bid + ask) / 2 if bid and ask else last
                self.option_mid.set(round(mid, 2))

                # Set entry price based on order type
                entry_type = self.entry_order_type.get()
                if entry_type == "Market":
                    self.entry_price.set(round(mid if mid > 0 else last, 2))
                elif entry_type == "Limit at Bid":
                    self.entry_price.set(round(bid, 2))
                elif entry_type == "Limit at Ask":
                    self.entry_price.set(round(ask, 2))
                elif entry_type == "Limit at Last":
                    self.entry_price.set(round(last, 2))
                else:  # Limit at Mid
                    self.entry_price.set(round(mid, 2))

                # Set Greeks
                self.selected_delta.set(round(delta, 3))
                self.selected_theta.set(round(theta, 3))
                self.selected_iv.set(round(iv * 100, 1))

                # Calculate TP/SL absolute prices
                self._calculate_tp_sl_prices()

                # Update UI elements
                self._update_preview()
                self._update_risk_summary()
                self._update_selected_option_display()

    # =========================================================================
    # Data Operations
    # =========================================================================

    def _fetch_market_data(self):
        """Fetch market data for the entered symbol."""
        symbol = self.symbol.get().strip().upper().lstrip("$")  # Strip $ prefix
        if not symbol:
            messagebox.showwarning("Input Required", "Please enter a symbol.")
            return

        self.symbol.set(symbol)  # Update field with sanitized symbol
        self._set_status("Fetching data...", "blue")
        self.root.update()

        try:
            if not self.market_data:
                raise ValueError("Market data manager not initialized")

            # Fetch current price
            price = self.market_data.get_stock_price(symbol)
            if price is None:
                raise ValueError(f"Could not fetch price for {symbol}")

            self.current_price.set(f"${price:.2f}")

            # Fetch expirations
            expirations = self.market_data.get_option_expirations(symbol) or []
            self.expirations_list = expirations
            self.expiration_combo["values"] = expirations

            if expirations:
                # Select expiration closest to 14 days out
                target_date = datetime.now() + timedelta(days=14)
                closest = min(expirations, key=lambda x: abs(datetime.strptime(str(x), "%Y-%m-%d") - target_date))
                self.expiration.set(closest)

            # Fetch gap info for momentum
            if self.current_strategy.get() == StrategyType.MOMENTUM.value:
                self._fetch_gap_info(symbol, price)

            # Refresh option chain
            self._refresh_option_chain()

            # For Goldflipper Gap Move: ensure contract is auto-selected after chain loads
            playbook_value = self._get_playbook_value_from_display(self.current_playbook.get())
            if playbook_value == "goldflipper_gap_move":
                self._auto_select_goldflipper_contract()

            # Update contract preview in header
            self._update_contract_preview()

            self._set_status("Data loaded successfully", "green")

        except Exception as e:
            logging.error(f"Error fetching market data: {e}")
            self._set_status(f"Error: {str(e)}", "red")
            messagebox.showerror("Data Error", f"Failed to fetch market data:\n{str(e)}")

    def _fetch_gap_info(self, symbol: str, current_price: float):
        """Fetch gap information for momentum strategy."""
        if self.market_data is None:
            return
        try:
            prev_close = self.market_data.get_previous_close(symbol)
            if prev_close:
                gap_amount = current_price - prev_close
                gap_pct = (gap_amount / prev_close) * 100

                self.previous_close.set(f"${prev_close:.2f}")
                self.gap_pct.set(f"{gap_pct:+.2f}%")

                if gap_pct > 0:
                    self.gap_type.set("UP")
                    self.gap_pct_label.configure(foreground="green")
                elif gap_pct < 0:
                    self.gap_type.set("DOWN")
                    self.gap_pct_label.configure(foreground="red")
                else:
                    self.gap_type.set("FLAT")
                    self.gap_pct_label.configure(foreground="gray")

                # Auto-select trade type based on playbook
                self._auto_select_trade_type(gap_pct)
        except Exception as e:
            logging.warning(f"Could not fetch gap info: {e}")

    def _auto_select_trade_type(self, gap_pct: float):
        """Auto-select trade type based on gap and playbook."""
        playbook = self._get_playbook_value_from_display(self.current_playbook.get())
        gap_up = gap_pct > 0

        if playbook == "gap_move" or playbook == "goldflipper_gap_move":
            # Trade with gap: gap up = CALL, gap down = PUT
            self.trade_type.set("CALL" if gap_up else "PUT")
        elif playbook == "gap_fade":
            # Trade against gap: gap up = PUT, gap down = CALL
            self.trade_type.set("PUT" if gap_up else "CALL")

    def _refresh_option_chain(self):
        """Refresh the option chain display."""
        symbol = self.symbol.get().strip()
        expiration = self.expiration.get()

        if not symbol or not expiration:
            return

        try:
            # Clear existing data
            for item in self.chain_tree.get_children():
                self.chain_tree.delete(item)

            # Fetch chain data
            if self.market_data is None:
                self._set_status("Market data not available", "red")
                return
            chain = self.market_data._try_providers("get_option_chain", symbol, expiration)

            if not chain:
                self._set_status("No option chain data available", "orange")
                return

            # Get the appropriate side
            trade_type = self.trade_type.get()
            options_df = chain.get("calls" if trade_type == "CALL" else "puts")

            if options_df is None or options_df.empty:
                self._set_status(f"No {trade_type} options available", "orange")
                return

            self.option_chain_data = options_df

            # Get current price for ATM highlighting
            current_price = float(self.current_price.get().replace("$", "").replace("--", "0"))

            # Populate tree
            delta_min = self.delta_min.get()
            delta_max = self.delta_max.get()

            strikes_added = []
            for _, row in options_df.iterrows():
                strike = row.get("strike", 0)
                delta = abs(row.get("delta", 0.5))

                # Filter by delta range
                if delta_min <= delta <= delta_max:
                    values = (
                        f"{strike:.2f}",
                        f"{row.get('bid', 0):.2f}",
                        f"{row.get('ask', 0):.2f}",
                        f"{row.get('last', 0):.2f}",
                        f"{delta:.3f}",
                        f"{row.get('theta', 0):.3f}",
                        self._format_iv(row),
                        f"{int(row.get('volume', 0))}",
                        f"{int(row.get('open_interest', 0))}",
                    )

                    # Tag for highlighting
                    tags = ()
                    if current_price > 0:
                        if abs(strike - current_price) / current_price < 0.02:
                            tags = ("atm",)
                        elif (trade_type == "CALL" and strike < current_price) or (trade_type == "PUT" and strike > current_price):
                            tags = ("itm",)
                        else:
                            tags = ("otm",)

                    self.chain_tree.insert("", "end", values=values, tags=tags)
                    strikes_added.append(strike)

            # Configure tag styles
            self.chain_tree.tag_configure("atm", background="#E8F5E9")
            self.chain_tree.tag_configure("itm", background="#FFF3E0")
            self.chain_tree.tag_configure("otm", background="#FFFFFF")

            # Update strike combo
            self.strike_combo["values"] = [f"{s:.2f}" for s in sorted(strikes_added)]

            # Auto-select ATM strike if none selected, or always for Goldflipper Gap Move
            is_goldflipper = self._get_playbook_value_from_display(self.current_playbook.get()) == "goldflipper_gap_move"
            if current_price > 0 and strikes_added and (is_goldflipper or not self.strike_price.get()):
                nearest_strike = min(strikes_added, key=lambda x: abs(x - current_price))
                self.strike_price.set(f"{nearest_strike:.2f}")

                # For Goldflipper: select the row in treeview and populate all fields
                if is_goldflipper:
                    # Find and select the matching row in the chain_tree
                    for item_id in self.chain_tree.get_children():
                        item_values = self.chain_tree.item(item_id, "values")
                        if item_values and abs(float(item_values[0]) - nearest_strike) < 0.01:
                            self.chain_tree.selection_set(item_id)
                            self.chain_tree.see(item_id)  # Scroll to make visible
                            # Trigger double-click handler to populate all fields
                            self._on_chain_double_click()
                            break

            self._set_status(f"Loaded {len(strikes_added)} options", "green")

        except Exception as e:
            logging.error(f"Error refreshing option chain: {e}")
            self._set_status(f"Chain error: {str(e)}", "red")

    def _sort_chain(self, column):
        """Sort option chain by column."""
        items = [(self.chain_tree.set(item, column), item) for item in self.chain_tree.get_children("")]

        # Try numeric sort
        try:
            items.sort(key=lambda t: float(str(t[0]).replace("%", "").replace("$", "").replace("--", "0")))
        except ValueError:
            items.sort()

        for index, (_, item) in enumerate(items):
            self.chain_tree.move(item, "", index)

    # =========================================================================
    # UI Updates
    # =========================================================================

    def _update_playbook_options(self):
        """Update playbook dropdown based on selected strategy."""
        try:
            strategy = StrategyType(self.current_strategy.get())
            playbooks = STRATEGY_PLAYBOOKS.get(strategy, [])

            # Extract display names (first element of each tuple)
            self.playbook_combo["values"] = [pb[0] for pb in playbooks]

            if playbooks:
                self.current_playbook.set(playbooks[0][1])
                self.playbook_combo.current(0)
                # Update type indicator for the first playbook
                self._update_playbook_type_indicator(playbooks[0][1])
                # Load defaults for the first playbook
                self._load_playbook_defaults(self.current_strategy.get(), playbooks[0][1])

        except ValueError:
            pass

    def _update_playbook_type_indicator(self, playbook_value: str):
        """Update the playbook type indicator label (CUSTOM vs TEMPLATE)."""
        if playbook_value in CUSTOM_PLAYBOOKS:
            self.playbook_type_label.config(text="CUSTOM", fg="#DAA520")  # Gold color
        else:
            self.playbook_type_label.config(text="TEMPLATE", fg="gray")

    def _update_gap_visibility(self):
        """Show/hide gap frame and strategy-specific options in Other Options panel."""
        is_momentum = self.current_strategy.get() == StrategyType.MOMENTUM.value
        playbook_value = (
            self._get_playbook_value_from_display(self.current_playbook.get())
            if hasattr(self, "_get_playbook_value_from_display")
            else self.current_playbook.get()
        )
        is_goldflipper_gap = playbook_value == "goldflipper_gap_move"

        # Show/hide gap frame (left column)
        if hasattr(self, "gap_frame"):
            if is_momentum:
                self.gap_frame.grid()
            else:
                self.gap_frame.grid_remove()

        # Show/hide strategy-specific options in Other Options panel (middle column)
        # These are created in _create_other_options_panel which runs after _create_strategy_panel
        if not hasattr(self, "momentum_options_frame"):
            return

        if is_momentum:
            self.momentum_options_frame.pack(fill=tk.X, pady=(0, 5))
            self.no_options_label.pack_forget()
            if is_goldflipper_gap:
                self.goldflipper_options_frame.pack(fill=tk.X, pady=(0, 5))
            else:
                self.goldflipper_options_frame.pack_forget()
        else:
            self.momentum_options_frame.pack_forget()
            self.goldflipper_options_frame.pack_forget()
            self.no_options_label.pack(anchor="w")

        # Show/hide Advanced Settings panel (right column, below preview)
        if hasattr(self, "advanced_settings_frame"):
            if is_momentum:
                self.advanced_settings_frame.grid()
            else:
                self.advanced_settings_frame.grid_remove()

    def _update_contract_preview(self):
        """Update the option contract preview in the header."""
        symbol = self.symbol.get().strip().upper()
        strike = self.strike_price.get()
        expiration = self.expiration.get()
        trade_type = self.trade_type.get()

        if not symbol or not strike or not expiration:
            self.contract_preview_label.config(text="[ No contract selected ]", foreground="#999999")
            return

        try:
            # Build option symbol
            strike_float = float(strike)
            exp_dt = datetime.strptime(expiration, "%Y-%m-%d")
            strike_tenths = int(round(strike_float * 1000))
            option_type = "C" if trade_type == "CALL" else "P"
            option_symbol = f"{symbol}{exp_dt.strftime('%y%m%d')}{option_type}{strike_tenths:08d}"

            # Display in a user-friendly format
            display_text = f"( {option_symbol} )"
            self.contract_preview_label.config(text=display_text, foreground="#0066cc")
        except Exception:
            self.contract_preview_label.config(text="[ Invalid contract ]", foreground="#cc0000")

    def _calculate_tp_sl_prices(self):
        """Calculate absolute TP/SL prices based on entry price and percentages."""
        entry = self.entry_price.get()
        strategy = self.current_strategy.get()
        tp_pct = self.tp_pct.get()
        sl_pct = self.sl_pct.get()

        if entry > 0:
            if strategy == StrategyType.SELL_PUTS.value:
                # Short premium: TP when price decreases, SL when price increases
                self.tp_price.set(round(entry * (1 - tp_pct / 100), 2))
                self.sl_price.set(round(entry * (1 + sl_pct / 100), 2))
            else:
                # Long premium: TP when price increases, SL when price decreases
                self.tp_price.set(round(entry * (1 + tp_pct / 100), 2))
                self.sl_price.set(round(entry * (1 - sl_pct / 100), 2))

            # Update UI labels if they exist
            if hasattr(self, "tp_price_label"):
                self.tp_price_label.config(text=f"${self.tp_price.get():.2f}")
            if hasattr(self, "sl_price_label"):
                self.sl_price_label.config(text=f"${self.sl_price.get():.2f}")

    def _update_selected_option_display(self):
        """Update the selected option info display with full details."""
        entry = self.entry_price.get()
        strike = self.strike_price.get()
        delta = self.selected_delta.get()
        theta = self.selected_theta.get()
        iv = self.selected_iv.get()

        if entry > 0:
            info_parts = [f"Strike: {strike}", f"Entry: ${entry:.2f}", f"Δ={delta:.3f}", f"θ={theta:.3f}", f"IV={iv:.1f}%"]
            self.selected_option_label.config(text=" | ".join(info_parts))
        else:
            self.selected_option_label.config(text="No option selected")

    def _update_preview(self):
        """Update the play preview."""
        try:
            play_data = self._build_play_data()

            if play_data:
                # Pretty print JSON
                preview_json = json.dumps(play_data, indent=2, default=str)

                self.preview_text.delete(1.0, tk.END)
                self.preview_text.insert(tk.END, preview_json)

                # Validate
                validation_result = self._validate_play(play_data)
                self._show_validation_result(validation_result)
            else:
                self.preview_text.delete(1.0, tk.END)
                self.preview_text.insert(tk.END, "Enter symbol and fetch data to preview play")

        except Exception as e:
            logging.error(f"Error updating preview: {e}")
            self.preview_text.delete(1.0, tk.END)
            self.preview_text.insert(tk.END, f"Error generating preview:\n{str(e)}")

    def _update_risk_summary(self):
        """Update the risk summary display."""
        try:
            contracts = self.contracts.get()
            strike = float(self.strike_price.get() or 0)

            # Get option premium - use entry_price if set
            premium = self.entry_price.get()
            if premium <= 0:
                premium = self._get_selected_option_premium()

            strategy = self.current_strategy.get()

            if strategy == StrategyType.SELL_PUTS.value:
                # Short put: max loss = strike - premium, max profit = premium
                max_profit = premium * 100 * contracts
                max_loss = (strike - premium) * 100 * contracts
                buying_power = strike * 100 * contracts  # Cash-secured
                break_even = strike - premium
            else:
                # Long option: max loss = premium, max profit = unlimited (use TP%)
                max_loss = premium * 100 * contracts
                max_profit = premium * (self.tp_pct.get() / 100) * 100 * contracts
                buying_power = max_loss
                break_even = strike + premium if self.trade_type.get() == "CALL" else strike - premium

            self.risk_labels["max_risk"].config(text=f"${max_loss:.2f}")
            self.risk_labels["max_profit"].config(text=f"${max_profit:.2f}")
            self.risk_labels["break_even"].config(text=f"${break_even:.2f}")
            self.risk_labels["buying_power"].config(text=f"${buying_power:.2f}")

        except Exception:
            for key in self.risk_labels:
                self.risk_labels[key].config(text="--")

    def _get_selected_option_premium(self) -> float:
        """Get the premium for the currently selected option."""
        try:
            strike = float(self.strike_price.get())

            if self.option_chain_data is not None and not self.option_chain_data.empty:
                row = self.option_chain_data[abs(self.option_chain_data["strike"] - strike) < 0.01]
                if not row.empty:
                    # Use mid price
                    bid = row.iloc[0].get("bid", 0)
                    ask = row.iloc[0].get("ask", 0)
                    return (bid + ask) / 2 if bid and ask else row.iloc[0].get("last", 0)
        except Exception:
            pass
        return 0.0

    def _set_status(self, message: str, color: str = "black"):
        """Set the status label."""
        self.status_label.config(text=message, foreground=color)

    # =========================================================================
    # Dynamic GTD GUI Helpers
    # =========================================================================

    def _toggle_gtd_panel(self):
        """Show/hide the Dynamic GTD methods panel."""
        if self.dynamic_gtd_enabled.get():
            self._gtd_frame.grid()
        else:
            self._gtd_frame.grid_remove()

    def _build_gtd_methods_panel(self, parent):
        """Build the collapsible panel with GTD method checkboxes and params."""
        methods = [
            ("Max Hold Days", self.gtd_max_hold_days_enabled, [("Max days:", self.gtd_max_hold_days, 1, 365)]),
            ("DTE-Based Close", self.gtd_dte_close_enabled, [("Close at DTE:", self.gtd_dte_close_at, 0, 90)]),
            ("Theta Decay Threshold", self.gtd_theta_threshold_enabled, [("Max theta %:", self.gtd_theta_max_pct, 0.1, 50.0)]),
            ("P/L Time Stop", self.gtd_pl_time_stop_enabled, [("Max days to TP:", self.gtd_pl_time_stop_days, 1, 90)]),
            (
                "Profit Extension",
                self.gtd_profit_extension_enabled,
                [("Min profit %:", self.gtd_profit_extension_min_pct, 0, 100), ("Extension days:", self.gtd_profit_extension_days, 1, 30)],
            ),
            (
                "Loss Shortening",
                self.gtd_loss_shortening_enabled,
                [("Loss threshold %:", self.gtd_loss_threshold_pct, -100, 0), ("Shorten days:", self.gtd_loss_shorten_days, 1, 30)],
            ),
            ("Rolling GTD", self.gtd_rolling_enabled, [("Extension days:", self.gtd_rolling_extension_days, 1, 7)]),
            ("Earnings/Event Close", self.gtd_earnings_enabled, [("Days before:", self.gtd_earnings_days_before, 0, 10)]),
            ("Weekend Theta Avoidance", self.gtd_weekend_theta_enabled, [("Min DTE concern:", self.gtd_weekend_min_dte, 1, 90)]),
            ("IV Crush Prevention", self.gtd_iv_crush_enabled, [("Max IV rank:", self.gtd_iv_crush_max_rank, 0, 100)]),
            ("Half-Life", self.gtd_half_life_enabled, [("Fraction:", self.gtd_half_life_fraction, 0.1, 0.9)]),
        ]

        for _idx, (label, enabled_var, params) in enumerate(methods):
            method_frame = ttk.Frame(parent)
            method_frame.pack(fill=tk.X, pady=1)

            ttk.Checkbutton(method_frame, text=label, variable=enabled_var).pack(side=tk.LEFT)

            for param_label, param_var, param_min, param_max in params:
                ttk.Label(method_frame, text=f"  {param_label}", foreground="gray", font=("Helvetica", 8)).pack(side=tk.LEFT, padx=(8, 0))
                spin = ttk.Spinbox(
                    method_frame,
                    textvariable=param_var,
                    from_=param_min,
                    to=param_max,
                    width=6,
                    increment=1 if isinstance(param_var, tk.IntVar) else 0.5,
                )
                spin.pack(side=tk.LEFT, padx=2)

    def _build_dynamic_gtd_data(self) -> dict[str, Any]:
        """Build the dynamic_gtd section for play JSON from GUI state."""
        if not self.dynamic_gtd_enabled.get():
            return {"enabled": False, "methods": [], "method_states": {}, "effective_date": None, "last_evaluated": None}

        methods = []

        if self.gtd_max_hold_days_enabled.get():
            methods.append({"method": "max_hold_days", "enabled": True, "params": {"max_days": self.gtd_max_hold_days.get()}})
        if self.gtd_dte_close_enabled.get():
            methods.append({"method": "dte_based_close", "enabled": True, "params": {"close_at_dte": self.gtd_dte_close_at.get()}})
        if self.gtd_theta_threshold_enabled.get():
            methods.append({"method": "theta_decay_threshold", "enabled": True, "params": {"max_theta_pct": self.gtd_theta_max_pct.get()}})
        if self.gtd_pl_time_stop_enabled.get():
            methods.append({"method": "pl_time_stop", "enabled": True, "params": {"max_days_to_tp": self.gtd_pl_time_stop_days.get()}})
        if self.gtd_profit_extension_enabled.get():
            methods.append(
                {
                    "method": "profit_conditional_extension",
                    "enabled": True,
                    "params": {"min_profit_pct": self.gtd_profit_extension_min_pct.get(), "extension_days": self.gtd_profit_extension_days.get()},
                }
            )
        if self.gtd_loss_shortening_enabled.get():
            methods.append(
                {
                    "method": "loss_conditional_shortening",
                    "enabled": True,
                    "params": {"loss_threshold_pct": self.gtd_loss_threshold_pct.get(), "shorten_days": self.gtd_loss_shorten_days.get()},
                }
            )
        if self.gtd_rolling_enabled.get():
            methods.append(
                {
                    "method": "rolling_gtd",
                    "enabled": True,
                    "params": {"extension_days": self.gtd_rolling_extension_days.get(), "breakeven_buffer_pct": 0.0},
                }
            )
        if self.gtd_earnings_enabled.get():
            methods.append(
                {
                    "method": "earnings_event_based",
                    "enabled": True,
                    "params": {"close_days_before": self.gtd_earnings_days_before.get(), "event_types": ["earnings", "fomc"]},
                }
            )
        if self.gtd_weekend_theta_enabled.get():
            methods.append(
                {
                    "method": "weekend_theta_avoidance",
                    "enabled": True,
                    "params": {"close_on_friday": True, "min_dte_for_concern": self.gtd_weekend_min_dte.get()},
                }
            )
        if self.gtd_iv_crush_enabled.get():
            methods.append(
                {
                    "method": "iv_crush_prevention",
                    "enabled": True,
                    "params": {"max_iv_rank": self.gtd_iv_crush_max_rank.get(), "close_if_iv_dropping": False},
                }
            )
        if self.gtd_half_life_enabled.get():
            methods.append({"method": "half_life_method", "enabled": True, "params": {"fraction": self.gtd_half_life_fraction.get()}})

        return {
            "enabled": True,
            "methods": methods,
            "method_states": {},
            "effective_date": None,
            "last_evaluated": None,
        }

    # =========================================================================
    # Play Building
    # =========================================================================

    def _build_play_data(self) -> dict[str, Any] | None:
        """Build play data from current form values."""
        symbol = self.symbol.get().strip()
        if not symbol:
            return None

        strike = self.strike_price.get()
        if not strike:
            return None

        try:
            strike_float = float(strike)
        except ValueError:
            return None

        expiration = self.expiration.get()
        if not expiration:
            return None

        strategy = self.current_strategy.get()
        playbook = self._get_playbook_value_from_display(self.current_playbook.get())
        trade_type = self.trade_type.get()
        contracts = self.contracts.get()

        # Build option symbol
        exp_dt = datetime.strptime(expiration, "%Y-%m-%d")
        strike_tenths = int(round(strike_float * 1000))
        option_type = "C" if trade_type == "CALL" else "P"
        option_symbol = f"{symbol}{exp_dt.strftime('%y%m%d')}{option_type}{strike_tenths:08d}"

        # Get current price
        try:
            current_price = float(self.current_price.get().replace("$", "").replace("--", "0"))
        except ValueError:
            current_price = 0

        # Get premium - use entry_price if set, otherwise fall back to chain lookup
        premium = self.entry_price.get()
        if premium <= 0:
            premium = self._get_selected_option_premium()

        # Determine action
        action = "STO" if strategy == StrategyType.SELL_PUTS.value else "BTO"

        # Build entry point
        entry_order_type = self.entry_order_type.get()
        # Map display name to value
        order_type_map = {ot[0]: ot[1] for ot in ORDER_TYPES}
        entry_order_value = order_type_map.get(entry_order_type, "limit at bid")

        entry_point = {
            "stock_price": round(current_price, 2),
            "order_type": entry_order_value,
            "entry_premium": round(premium, 2),
            "entry_stock_price": round(current_price, 2),
        }

        # Build TP/SL with advanced options
        tp_pct = self.tp_pct.get()
        sl_pct = self.sl_pct.get()

        # Map order type display names to values
        order_type_map = {ot[0]: ot[1] for ot in ORDER_TYPES}
        tp_order_value = order_type_map.get(self.tp_order_type.get(), "limit at mid")
        sl_order_value = order_type_map.get(self.sl_order_type.get(), "market")

        # Determine TP type
        if self.dynamic_tp_sl_enabled.get():
            tp_type = "DYNAMIC"
        elif self.multiple_tps_enabled.get():
            tp_type = "Multiple"
        else:
            tp_type = "Single"

        take_profit = {
            "TP_type": tp_type,
            "premium_pct": tp_pct,
            "order_type": tp_order_value,
            "TP_option_prem": round(premium * (1 + tp_pct / 100), 2) if action == "BTO" else round(premium * (1 - tp_pct / 100), 2),
        }

        # Add dynamic configuration placeholder if enabled (stub - no methods yet)
        if self.dynamic_tp_sl_enabled.get():
            take_profit["dynamic_config"] = {
                "enabled": True,
                "dynamic_method": None,  # Future: 'time_decay', 'iv_adjusted', 'model_v1', etc.
                "creation_premium": round(premium, 2),
                "creation_date": datetime.now().strftime("%Y-%m-%d"),
            }

        # Add multiple TP levels if enabled
        if self.multiple_tps_enabled.get() and self.tp_levels_data:
            take_profit["levels"] = []
            for i, level_data in enumerate(self.tp_levels_data):
                level_pct = level_data["pct_var"].get()
                level_contracts = level_data["contracts_var"].get()
                take_profit["levels"].append(
                    {
                        "level": i + 1,
                        "premium_pct": level_pct,
                        "contracts": level_contracts,
                        "TP_option_prem": round(premium * (1 + level_pct / 100), 2) if action == "BTO" else round(premium * (1 - level_pct / 100), 2),
                        "order_type": tp_order_value,
                        "filled": False,
                    }
                )

        # Add stock price target if enabled
        if self.use_stock_price_tp.get() and self.tp_stock_price.get() > 0:
            take_profit["stock_price"] = self.tp_stock_price.get()

        # Add stock price percentage target if enabled
        if self.use_stock_pct_tp.get():
            tp_stock_pct = self.tp_stock_pct.get()
            take_profit["stock_price_pct"] = tp_stock_pct
            take_profit["stock_price_target"] = round(current_price * (1 + tp_stock_pct / 100), 2)

        # Add trailing TP config if enabled
        if self.trailing_tp_enabled.get():
            take_profit["trailing_config"] = {
                "enabled": True,
                "trail_type": "percentage",
                "activation_threshold_pct": self.trailing_tp_activation_pct.get(),
                "trail_distance_pct": 10.0,
                "update_frequency_seconds": 30,
            }
            take_profit["trailing_activation_pct"] = self.trailing_tp_activation_pct.get()

        # Get stop loss type from advanced options
        sl_type = self.sl_type.get()
        # Override SL type if dynamic is enabled
        if self.dynamic_tp_sl_enabled.get():
            sl_type = "DYNAMIC"

        stop_loss = {
            "SL_type": sl_type,
            "premium_pct": sl_pct,
            "order_type": sl_order_value if sl_type not in ("CONTINGENCY", "DYNAMIC") else ["limit at mid", "market"],
            "SL_option_prem": round(premium * (1 - sl_pct / 100), 2) if action == "BTO" else round(premium * (1 + sl_pct / 100), 2),
        }

        # Add dynamic configuration placeholder if enabled (stub - no methods yet)
        if self.dynamic_tp_sl_enabled.get():
            stop_loss["dynamic_config"] = {
                "enabled": True,
                "dynamic_method": None,  # Future: 'time_decay', 'iv_adjusted', 'model_v1', etc.
                "creation_premium": round(premium, 2),
                "creation_date": datetime.now().strftime("%Y-%m-%d"),
            }

        # Add stock price target if enabled
        if self.use_stock_price_sl.get() and self.sl_stock_price.get() > 0:
            stop_loss["stock_price"] = self.sl_stock_price.get()

        # Add stock price percentage target if enabled
        if self.use_stock_pct_sl.get():
            sl_stock_pct = self.sl_stock_pct.get()
            stop_loss["stock_price_pct"] = sl_stock_pct
            stop_loss["stock_price_target"] = round(current_price * (1 + sl_stock_pct / 100), 2)

        # Add contingency backup if CONTINGENCY type
        if sl_type == "CONTINGENCY":
            contingency_pct = self.contingency_sl_pct.get()
            stop_loss["contingency_premium_pct"] = contingency_pct
            stop_loss["contingency_SL_option_prem"] = (
                round(premium * (1 - contingency_pct / 100), 2) if action == "BTO" else round(premium * (1 + contingency_pct / 100), 2)
            )
            if self.use_stock_price_sl.get() and self.sl_stock_price.get() > 0:
                # Calculate a worse backup stock price
                backup_offset = 0.02  # 2% worse
                if trade_type == "CALL":
                    stop_loss["contingency_stock_price"] = round(self.sl_stock_price.get() * (1 - backup_offset), 2)
                else:
                    stop_loss["contingency_stock_price"] = round(self.sl_stock_price.get() * (1 + backup_offset), 2)

        # Build play
        play = {
            "creator": "gui",
            "play_name": f"{option_symbol}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "symbol": symbol,
            "strategy": strategy,
            "playbook": playbook,
            "expiration_date": exp_dt.strftime("%m/%d/%Y"),
            "trade_type": trade_type,
            "action": action,
            "strike_price": str(strike_float),
            "option_contract_symbol": option_symbol,
            "contracts": contracts,
            "play_expiration_date": self.play_expiration.get() if self.play_expiration.get() else exp_dt.strftime("%m/%d/%Y"),
            "dynamic_gtd": self._build_dynamic_gtd_data(),
            "entry_point": entry_point,
            "take_profit": take_profit,
            "stop_loss": stop_loss,
            "play_class": self._infer_play_class(),
            "conditional_plays": self._build_conditional_plays(),
            "oco_peer_set_numbers": self._get_oco_peer_set_numbers_list(),
            "creation_date": datetime.now().strftime("%Y-%m-%d"),
            "status": {
                "play_status": "TEMP" if self._infer_play_class() == "OTO" else "NEW",
                "order_id": None,
                "position_uuid": None,
                "order_status": None,
                "position_exists": False,
                "closing_order_id": None,
                "closing_order_status": None,
                "contingency_order_id": None,
                "contingency_order_status": None,
                "conditionals_handled": False,
            },
            "logging": {
                "delta_atOpen": 0.0,
                "theta_atOpen": 0.0,
                "datetime_atOpen": None,
                "price_atOpen": 0.0,
                "premium_atOpen": 0.0,
                "datetime_atClose": None,
                "price_atClose": 0.0,
                "premium_atClose": 0.0,
                "close_type": None,
                "close_condition": None,
            },
        }

        # Add momentum-specific fields
        if strategy == StrategyType.MOMENTUM.value:
            gap_pct_str = self.gap_pct.get().replace("%", "").replace("+", "")
            try:
                gap_pct_val = float(gap_pct_str)
            except ValueError:
                gap_pct_val = 0.0

            play["gap_info"] = {
                "gap_type": self.gap_type.get().lower(),
                "gap_pct": gap_pct_val,
                "previous_close": float(self.previous_close.get().replace("$", "").replace("--", "0")),
                "gap_open": current_price,
                "trade_direction": "with_gap"
                if playbook in ("gap_move", "goldflipper_gap_move")
                else "fade_gap"
                if playbook == "gap_fade"
                else "manual",
            }

            # Add momentum timing configuration
            # "No Entry Until X mins after open" replaces separate wait_for_confirmation and first_hour_restriction
            confirmation_mins = self.momentum_confirmation_minutes.get()
            play["momentum_config"] = {
                "momentum_type": "goldflipper_gap"
                if playbook == "goldflipper_gap_move"
                else "gap"
                if playbook in ("gap_move", "gap_fade")
                else "manual",
                "wait_for_confirmation": confirmation_mins > 0,
                "confirmation_period_minutes": confirmation_mins,
                "lunch_break_restriction": self.momentum_lunch_break_enabled.get(),
                "lunch_break_start_hour": self.momentum_lunch_start_hour.get(),
                "lunch_break_start_minute": self.momentum_lunch_start_minute.get(),
                "lunch_break_end_hour": self.momentum_lunch_end_hour.get(),
                "lunch_break_end_minute": self.momentum_lunch_end_minute.get(),
                "first_hour_restriction": confirmation_mins >= 60,  # 60 mins = full first hour
                # Advanced settings (from Advanced Settings panel)
                "min_gap_pct": self.adv_min_gap_pct.get(),
                "max_gap_pct": self.adv_max_gap_pct.get() if self.adv_max_gap_pct_enabled.get() else None,
                "same_day_exit": self.adv_same_day_exit.get(),
                "max_hold_days": self.adv_max_hold_days.get() if self.adv_max_hold_days_enabled.get() else None,
                "dte_min": self.adv_dte_min.get(),
                "dte_max": self.adv_dte_max.get(),
                "avoid_first_minutes": self.adv_avoid_first_minutes.get(),
                "avoid_last_minutes": self.adv_avoid_last_minutes.get(),
            }

            # Add Goldflipper Gap Move-specific config
            if playbook == "goldflipper_gap_move":
                play["momentum_config"]["straddle_config"] = {
                    "enabled": self.goldflipper_gap_straddle_enabled.get(),
                    "min_gap_vs_straddle_ratio": self.goldflipper_gap_min_straddle_ratio.get(),
                }
                play["momentum_config"]["open_interest_config"] = {
                    "enabled": self.goldflipper_gap_oi_enabled.get(),
                    "min_directional_oi": self.goldflipper_gap_min_directional_oi.get(),
                    "min_oi_ratio": self.goldflipper_gap_min_oi_ratio.get(),
                }
                # Goldflipper Gap Move uses goldflipper_gap_info for straddle/OI data
                play["goldflipper_gap_info"] = {
                    "straddle_price": None,  # To be populated by auto_play_creator or market data
                    "stock_price_at_detection": current_price,
                    "call_open_interest": None,
                    "put_open_interest": None,
                }

        # Add sell_puts-specific fields
        if strategy == StrategyType.SELL_PUTS.value:
            play["collateral"] = {"required": True, "type": "cash", "amount": round(strike_float * 100 * contracts, 2), "calculated": True}
            play["management"] = {"close_at_dte": 21, "roll_if_itm": True, "accept_assignment": False}

        return play

    def _validate_play(self, play: dict[str, Any]) -> dict[str, Any]:
        """Validate play data."""
        result = {"valid": True, "errors": [], "warnings": []}

        # Check required fields
        required = ["symbol", "strike_price", "option_contract_symbol", "expiration_date"]
        for field in required:
            if not play.get(field):
                result["valid"] = False
                result["errors"].append(f"Missing required field: {field}")

        # Check contracts
        contracts = play.get("contracts", 0)
        if contracts < 1:
            result["valid"] = False
            result["errors"].append("Contracts must be at least 1")

        # Check premium
        entry_premium = play.get("entry_point", {}).get("entry_premium", 0)
        if entry_premium <= 0:
            result["warnings"].append("Entry premium is zero - verify option selection")

        # Check multiple TP levels allocation
        take_profit = play.get("take_profit", {})
        if take_profit.get("TP_type") == "Multiple" and "levels" in take_profit:
            levels = take_profit["levels"]
            total_allocated = sum(lvl.get("contracts", 0) for lvl in levels)
            if total_allocated != contracts:
                result["valid"] = False
                result["errors"].append(f"TP levels contracts ({total_allocated}) don't match total contracts ({contracts})")

        # Check OCO/OTO setup
        conditional = play.get("conditional_plays", {})
        if play.get("play_class") == "OTO":
            # OTO means this play IS a child waiting to be triggered by a parent
            if not conditional.get("oto", {}).get("parent_play"):
                result["warnings"].append("OTO play class inferred but no parent play specified")

        # Check expiration
        try:
            exp_date = datetime.strptime(play.get("expiration_date", ""), "%m/%d/%Y")
            if exp_date < datetime.now():
                result["valid"] = False
                result["errors"].append("Expiration date is in the past")
            elif (exp_date - datetime.now()).days > 60:
                result["warnings"].append("Expiration is more than 60 days out")
        except ValueError:
            result["valid"] = False
            result["errors"].append("Invalid expiration date format")

        return result

    def _show_validation_result(self, result: dict[str, Any]):
        """Display validation result."""
        if result["valid"] and not result["warnings"]:
            self.validation_label.config(text="✓ Play is valid and ready to create", foreground="green")
        elif result["valid"]:
            warnings = ", ".join(result["warnings"][:2])
            self.validation_label.config(text=f"⚠ Valid with warnings: {warnings}", foreground="orange")
        else:
            errors = ", ".join(result["errors"][:2])
            self.validation_label.config(text=f"✗ Invalid: {errors}", foreground="red")

    def _load_playbook_defaults(self, strategy: str, playbook: str):
        """Load default values from playbook configuration."""
        # Map playbook values to strategy-specific defaults
        defaults = {
            ("option_swings", "default"): {"tp_pct": 50.0, "sl_pct": 25.0},
            ("option_swings", "pb_v3"): {"tp_pct": 50.0, "sl_pct": 35.0},  # Playbook v3: 1:1.5 RRR, max 35% SL
            ("option_swings", "pb_v3_long"): {"tp_pct": 50.0, "sl_pct": 35.0},  # Same as pb_v3
            ("momentum", "gap_move"): {"tp_pct": 50.0, "sl_pct": 30.0},
            ("momentum", "gap_fade"): {"tp_pct": 25.0, "sl_pct": 20.0},
            ("momentum", "goldflipper_gap_move"): {"tp_pct": 40.0, "sl_pct": 25.0},
            ("momentum", "manual"): {"tp_pct": 50.0, "sl_pct": 30.0},
            ("sell_puts", "default"): {"tp_pct": 50.0, "sl_pct": 200.0},
            ("sell_puts", "tasty_30_delta"): {"tp_pct": 50.0, "sl_pct": 200.0},
        }

        key = (strategy, playbook)
        if key in defaults:
            self.tp_pct.set(defaults[key]["tp_pct"])
            self.sl_pct.set(defaults[key]["sl_pct"])

        # Load momentum-specific config defaults based on playbook
        if strategy == StrategyType.MOMENTUM.value:
            momentum_defaults = {
                # Simplified: confirmation_minutes controls "no entry until X mins after open"
                # 0 = immediate entry, 15 = 15 mins after open, 60 = full first hour
                "gap_move": {
                    "confirmation_minutes": 15,
                    "lunch_break": True,
                    "lunch_start_h": 12,
                    "lunch_start_m": 0,
                    "lunch_end_h": 13,
                    "lunch_end_m": 0,
                    # Advanced settings
                    "min_gap_pct": 1.0,
                    "max_gap_pct": 10.0,
                    "max_gap_enabled": False,
                    "same_day_exit": False,
                    "max_hold_days": 5,
                    "max_hold_enabled": True,
                    "avoid_first_min": 5,
                    "avoid_last_min": 60,
                    "dte_min": 7,
                    "dte_max": 21,
                },
                "gap_fade": {
                    "confirmation_minutes": 30,
                    "lunch_break": True,
                    "lunch_start_h": 12,
                    "lunch_start_m": 0,
                    "lunch_end_h": 13,
                    "lunch_end_m": 0,
                    # Advanced settings - gap fade uses mean reversion, shorter holds
                    "min_gap_pct": 2.0,
                    "max_gap_pct": 8.0,
                    "max_gap_enabled": True,
                    "same_day_exit": True,
                    "max_hold_days": 2,
                    "max_hold_enabled": True,
                    "avoid_first_min": 15,
                    "avoid_last_min": 30,
                    "dte_min": 7,
                    "dte_max": 14,
                },
                "goldflipper_gap_move": {
                    "confirmation_minutes": 60,  # Full first hour - no entries until 10:30 AM
                    "lunch_break": True,
                    "lunch_start_h": 12,
                    "lunch_start_m": 0,
                    "lunch_end_h": 13,
                    "lunch_end_m": 0,
                    # Advanced settings - Goldflipper uses straddle-based gap sizing
                    "min_gap_pct": 1.0,
                    "max_gap_pct": 10.0,
                    "max_gap_enabled": False,
                    "same_day_exit": False,
                    "max_hold_days": 3,
                    "max_hold_enabled": True,
                    "avoid_first_min": 5,
                    "avoid_last_min": 60,
                    "dte_min": 7,
                    "dte_max": 14,
                },
                "manual": {
                    "confirmation_minutes": 0,  # Immediate entry allowed
                    "lunch_break": True,
                    "lunch_start_h": 12,
                    "lunch_start_m": 0,
                    "lunch_end_h": 13,
                    "lunch_end_m": 0,
                    # Advanced settings - manual has relaxed defaults
                    "min_gap_pct": 0.5,
                    "max_gap_pct": 15.0,
                    "max_gap_enabled": False,
                    "same_day_exit": False,
                    "max_hold_days": 5,
                    "max_hold_enabled": True,
                    "avoid_first_min": 5,
                    "avoid_last_min": 60,
                    "dte_min": 7,
                    "dte_max": 21,
                },
            }
            if playbook in momentum_defaults:
                cfg = momentum_defaults[playbook]
                # Basic timing settings
                self.momentum_confirmation_minutes.set(cfg["confirmation_minutes"])
                self.momentum_lunch_break_enabled.set(cfg["lunch_break"])
                self.momentum_lunch_start_hour.set(cfg["lunch_start_h"])
                self.momentum_lunch_start_minute.set(cfg["lunch_start_m"])
                self.momentum_lunch_end_hour.set(cfg["lunch_end_h"])
                self.momentum_lunch_end_minute.set(cfg["lunch_end_m"])
                # Advanced settings
                self.adv_min_gap_pct.set(cfg["min_gap_pct"])
                self.adv_max_gap_pct.set(cfg["max_gap_pct"])
                self.adv_max_gap_pct_enabled.set(cfg["max_gap_enabled"])
                self.adv_same_day_exit.set(cfg["same_day_exit"])
                self.adv_max_hold_days.set(cfg["max_hold_days"])
                self.adv_max_hold_days_enabled.set(cfg["max_hold_enabled"])
                self.adv_avoid_first_minutes.set(cfg["avoid_first_min"])
                self.adv_avoid_last_minutes.set(cfg["avoid_last_min"])
                self.adv_dte_min.set(cfg["dte_min"])
                self.adv_dte_max.set(cfg["dte_max"])

    # =========================================================================
    # Actions
    # =========================================================================

    def _create_play(self):
        """Create and save the play."""
        play_data = self._build_play_data()

        if not play_data:
            messagebox.showwarning("Invalid Play", "Please fill in all required fields.")
            return

        # Validate
        validation = self._validate_play(play_data)
        if not validation["valid"]:
            errors = "\n".join(validation["errors"])
            messagebox.showerror("Validation Error", f"Cannot create play:\n{errors}")
            return

        # Confirm if warnings
        if validation["warnings"]:
            warnings = "\n".join(validation["warnings"])
            if not messagebox.askyesno("Warnings", f"Play has warnings:\n{warnings}\n\nCreate anyway?"):
                return

        # Determine save directory based on play class
        if play_data.get("play_class") == "OTO":
            save_dir = str(get_play_subdir("temp"))
        else:
            save_dir = self.plays_dir
        os.makedirs(save_dir, exist_ok=True)

        # Save to file
        try:
            filename = f"{play_data['play_name']}.json"
            filepath = os.path.join(save_dir, filename)

            with open(filepath, "w") as f:
                json.dump(play_data, f, indent=2, default=str)

            self._set_status(f"Play created: {filename}", "green")
            messagebox.showinfo("Success", f"Play created successfully!\n\nSaved to:\n{filepath}")

            # Ask if user wants to create another
            if messagebox.askyesno("Create Another?", "Would you like to create another play?"):
                self._clear_all()

        except Exception as e:
            logging.error(f"Error saving play: {e}")
            messagebox.showerror("Save Error", f"Failed to save play:\n{str(e)}")

    def _save_template(self):
        """Save current configuration as a template."""
        play_data = self._build_play_data()

        if not play_data:
            messagebox.showwarning("No Data", "Please configure a play first.")
            return

        # Remove instance-specific data
        template = copy.deepcopy(play_data)
        template.pop("play_name", None)
        template.pop("creation_date", None)
        template["status"] = {"play_status": "NEW"}

        # Add template info
        template["_template_info"] = {
            "name": f"{template.get('strategy', 'custom')} template",
            "created": datetime.now().strftime("%Y-%m-%d"),
            "description": "Custom template created via GUI",
        }

        # Ask for save location
        filename = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json")],
            initialdir=self.templates_dir,
            initialfile=f"template_{template.get('strategy', 'custom')}.json",
        )

        if filename:
            try:
                with open(filename, "w") as f:
                    json.dump(template, f, indent=2)
                messagebox.showinfo("Template Saved", f"Template saved to:\n{filename}")
            except Exception as e:
                messagebox.showerror("Save Error", f"Failed to save template:\n{str(e)}")

    def _load_template(self):
        """Load a template file."""
        filename = filedialog.askopenfilename(filetypes=[("JSON files", "*.json")], initialdir=self.templates_dir)

        if not filename:
            return

        try:
            with open(filename) as f:
                template = json.load(f)

            # Remove template info
            template.pop("_template_info", None)

            # Apply template values
            if "strategy" in template:
                self.current_strategy.set(template["strategy"])
                self._on_strategy_changed()

            if "playbook" in template:
                self.current_playbook.set(template["playbook"])

            if "trade_type" in template:
                self.trade_type.set(template["trade_type"])

            if "contracts" in template:
                self.contracts.set(template["contracts"])

            if "take_profit" in template and "premium_pct" in template["take_profit"]:
                self.tp_pct.set(template["take_profit"]["premium_pct"])

            if "stop_loss" in template and "premium_pct" in template["stop_loss"]:
                self.sl_pct.set(template["stop_loss"]["premium_pct"])

            self._set_status(f"Template loaded from {os.path.basename(filename)}", "green")
            messagebox.showinfo("Template Loaded", "Template applied successfully.\nEnter a symbol to continue.")

        except Exception as e:
            messagebox.showerror("Load Error", f"Failed to load template:\n{str(e)}")

    def _clear_all(self):
        """Clear all form fields."""
        self.symbol.set("")
        self.expiration.set("")
        self.strike_price.set("")
        self.contracts.set(1)
        self.current_price.set("--")
        self.bid_price.set("--")
        self.ask_price.set("--")
        self.gap_pct.set("--")
        self.gap_type.set("--")
        self.previous_close.set("--")

        # Reset entry price and option data
        self.entry_price.set(0.0)
        self.option_bid.set(0.0)
        self.option_ask.set(0.0)
        self.option_last.set(0.0)
        self.option_mid.set(0.0)
        self.selected_delta.set(0.0)
        self.selected_theta.set(0.0)
        self.selected_iv.set(0.0)
        self.tp_price.set(0.0)
        self.sl_price.set(0.0)

        # Reset price displays
        if hasattr(self, "bid_display"):
            self.bid_display.config(text="--")
        if hasattr(self, "ask_display"):
            self.ask_display.config(text="--")
        if hasattr(self, "mid_display"):
            self.mid_display.config(text="--")
        if hasattr(self, "last_display"):
            self.last_display.config(text="--")
        if hasattr(self, "tp_price_label"):
            self.tp_price_label.config(text="$--")
        if hasattr(self, "sl_price_label"):
            self.sl_price_label.config(text="$--")
        if hasattr(self, "dte_label"):
            self.dte_label.config(text="")

        # Reset stock price percentage options
        self.use_stock_pct_tp.set(False)
        self.use_stock_pct_sl.set(False)
        self.tp_stock_pct.set(5.0)
        self.sl_stock_pct.set(-3.0)
        if hasattr(self, "tp_stock_pct_spin"):
            self.tp_stock_pct_spin.config(state="disabled")
        if hasattr(self, "sl_stock_pct_spin"):
            self.sl_stock_pct_spin.config(state="disabled")
        if hasattr(self, "tp_stock_pct_target_label"):
            self.tp_stock_pct_target_label.config(text="")
        if hasattr(self, "sl_stock_pct_target_label"):
            self.sl_stock_pct_target_label.config(text="")

        # Reset advanced options
        self.play_expiration.set("")
        # Note: play_class is now inferred from conditional orders, no need to reset
        self.sl_type.set("STOP")
        self.contingency_sl_pct.set(50.0)
        self.entry_order_type.set("Limit at Bid")
        self.tp_order_type.set("Limit at Mid")
        self.sl_order_type.set("Market")
        self.use_stock_price_tp.set(False)
        self.use_stock_price_sl.set(False)
        self.tp_stock_price.set(0.0)
        self.sl_stock_price.set(0.0)
        self.trailing_tp_enabled.set(False)
        self.trailing_tp_activation_pct.set(20.0)
        self.trailing_sl_enabled.set(False)
        self.trailing_sl_activation_pct.set(10.0)
        self.multiple_tps_enabled.set(False)
        self.num_tp_levels.set(2)
        self.dynamic_tp_sl_enabled.set(False)
        self.oco_plays.set("")
        self.oto_parent.set("")
        self.oto_trigger_condition.set("on_fill")
        self.oco_peer_set_numbers.set("")

        # Reset advanced momentum settings
        self.adv_min_gap_pct.set(1.0)
        self.adv_max_gap_pct.set(10.0)
        self.adv_max_gap_pct_enabled.set(False)
        self.adv_same_day_exit.set(False)
        self.adv_max_hold_days_enabled.set(True)
        self.adv_max_hold_days.set(5)
        self.adv_avoid_first_minutes.set(5)
        self.adv_avoid_last_minutes.set(60)
        self.adv_dte_min.set(7)
        self.adv_dte_max.set(21)

        # Clear TP levels UI
        self._clear_tp_levels_ui()

        # Clear OCO/OSO listboxes
        if hasattr(self, "oco_listbox"):
            self.oco_listbox.delete(0, tk.END)
        if hasattr(self, "oso_listbox"):
            self.oso_listbox.delete(0, tk.END)

        # Reset panel states
        self._on_sl_type_changed()
        self._on_stock_price_toggle()
        self._on_trailing_tp_toggle()
        if hasattr(self, "trailing_sl_spin"):
            self._on_trailing_sl_toggle()
        self._on_multi_tp_toggle()

        # Clear option chain
        for item in self.chain_tree.get_children():
            self.chain_tree.delete(item)

        # Clear preview
        self.preview_text.delete(1.0, tk.END)

        # Reset risk
        for key in self.risk_labels:
            self.risk_labels[key].config(text="--")

        self.selected_option_label.config(text="No option selected")
        self.validation_label.config(text="Enter symbol and fetch data to preview play", foreground="gray")

        # Reset contract preview in header
        if hasattr(self, "contract_preview_label"):
            self.contract_preview_label.config(text="[ No contract selected ]", foreground="#999999")

        self._set_status("Ready", "green")

    def run(self):
        """Run the GUI application."""
        self.root.mainloop()


# =============================================================================
# Entry Point
# =============================================================================


def main():
    """Main entry point for the Play Creator GUI."""
    logging.basicConfig(level=logging.INFO)

    try:
        app = PlayCreatorGUI()
        app.run()
    except Exception as e:
        logging.error(f"Failed to start Play Creator GUI: {e}")
        messagebox.showerror("Startup Error", f"Failed to start application:\n{str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
