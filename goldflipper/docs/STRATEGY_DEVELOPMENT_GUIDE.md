# Strategy Development Guide

**Document Created:** 2025-12-01  
**Target Audience:** Developers adding new trading strategies to Goldflipper

---

## Overview

This guide explains how to create new trading strategies for the Goldflipper multi-strategy system. All strategies inherit from `BaseStrategy` and are discovered automatically by the `StrategyOrchestrator`.

### Architecture

```
StrategyOrchestrator
    ├── Discovers strategies via StrategyRegistry
    ├── Instantiates enabled strategies with shared resources
    ├── Calls evaluate_new_plays() for entry signals
    ├── Calls evaluate_open_plays() for exit signals
    └── Executes open_position() / close_position()

BaseStrategy (Abstract)
    ├── get_name() → "strategy_name"
    ├── get_config_section() → "config_section"
    ├── get_plays_base_dir() → "plays"
    ├── evaluate_new_plays(plays) → [plays_to_open]
    ├── evaluate_open_plays(plays) → [(play, conditions)]
    └── validate_play(play) → bool
```

---

## Quick Start: Minimal Strategy

Here's the minimal code to create a new strategy:

```python
# File: goldflipper/strategy/runners/my_strategy.py

from typing import Dict, Any, List, Tuple
from goldflipper.strategy.base import BaseStrategy, OrderAction
from goldflipper.strategy.registry import register_strategy


@register_strategy('my_strategy')
class MyStrategy(BaseStrategy):
    """Minimal strategy implementation."""
    
    def get_name(self) -> str:
        return "my_strategy"
    
    def get_config_section(self) -> str:
        return "my_strategy"  # Maps to settings.yaml section
    
    def get_plays_base_dir(self) -> str:
        return "plays"  # Use shared plays directory
    
    def evaluate_new_plays(self, plays: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Return plays that should be opened."""
        return []  # Stub: no entries
    
    def evaluate_open_plays(
        self, 
        plays: List[Dict[str, Any]]
    ) -> List[Tuple[Dict[str, Any], Dict[str, Any]]]:
        """Return (play, conditions) tuples for plays that should be closed."""
        return []  # Stub: no exits
```

---

## Step-by-Step Implementation

### Step 1: Create the Strategy File

Create a new file in `goldflipper/strategy/runners/`:

```
goldflipper/strategy/runners/my_strategy.py
```

### Step 2: Add Required Imports

```python
from typing import Dict, Any, List, Tuple, Optional
from datetime import datetime
import logging

from goldflipper.strategy.base import BaseStrategy, PlayStatus, OrderAction, PositionSide
from goldflipper.strategy.registry import register_strategy

# Optional: Import shared utilities
from goldflipper.strategy.shared import (
    evaluate_opening_strategy,
    evaluate_closing_strategy,
    save_play_improved,
    OrderExecutor,
)
```

### Step 3: Implement the Strategy Class

```python
@register_strategy('my_strategy')
class MyStrategy(BaseStrategy):
    """
    My Trading Strategy.
    
    Trade Direction: BUY_TO_OPEN → SELL_TO_CLOSE (long premium)
    Configuration: settings.yaml → my_strategy section
    """
    
    def __init__(
        self,
        config: Dict[str, Any],
        market_data: Any,
        brokerage_client: Any
    ):
        super().__init__(config, market_data, brokerage_client)
        # Strategy-specific initialization
        self.logger.info(f"MyStrategy initialized (enabled={self.is_enabled()})")
```

### Step 4: Implement Abstract Methods

#### `get_name()` - Strategy Identifier

```python
def get_name(self) -> str:
    """Return unique strategy identifier. Used for logging and registry."""
    return "my_strategy"
```

#### `get_config_section()` - Configuration Key

```python
def get_config_section(self) -> str:
    """Return settings.yaml section name."""
    return "my_strategy"  # Reads from config['my_strategy']
```

#### `get_plays_base_dir()` - Play Files Location

```python
def get_plays_base_dir(self) -> str:
    """Return base directory for plays. Contains new/, open/, closed/, etc."""
    return "plays"  # Shared directory (recommended for most strategies)
```

#### `evaluate_new_plays()` - Entry Logic

```python
def evaluate_new_plays(
    self, 
    plays: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Evaluate plays in NEW status and return those that should be opened.
    
    Args:
        plays: List of play dicts from plays/new/ folder
    
    Returns:
        List of plays meeting entry conditions
    """
    plays_to_open = []
    
    for play in plays:
        symbol = play.get('symbol', '')
        
        # Example: Check if current price is at entry target
        current_price = self.market_data.get_stock_price(symbol)
        entry_target = play.get('entry_point', {}).get('stock_price')
        
        if current_price and entry_target:
            buffer = 0.50  # Allow $0.50 tolerance
            if abs(current_price - entry_target) <= buffer:
                self.log_trade_action('ENTRY_SIGNAL', play, {
                    'current_price': current_price,
                    'target': entry_target
                })
                plays_to_open.append(play)
    
    return plays_to_open
```

#### `evaluate_open_plays()` - Exit Logic

```python
def evaluate_open_plays(
    self, 
    plays: List[Dict[str, Any]]
) -> List[Tuple[Dict[str, Any], Dict[str, Any]]]:
    """
    Evaluate open positions and return those that should be closed.
    
    Args:
        plays: List of play dicts from plays/open/ folder
    
    Returns:
        List of (play, close_conditions) tuples
        
        close_conditions must include:
        - should_close: bool
        - is_profit: bool (True if take profit)
        - is_primary_loss: bool (True if stop loss)
        - is_contingency_loss: bool (True if backup SL)
    """
    plays_to_close = []
    
    for play in plays:
        symbol = play.get('symbol', '')
        current_price = self.market_data.get_stock_price(symbol)
        
        # Check take profit
        tp_target = play.get('take_profit', {}).get('stock_price')
        trade_type = play.get('trade_type', 'CALL')
        
        tp_hit = False
        sl_hit = False
        
        if tp_target and current_price:
            if trade_type == 'CALL' and current_price >= tp_target:
                tp_hit = True
            elif trade_type == 'PUT' and current_price <= tp_target:
                tp_hit = True
        
        # Check stop loss
        sl_target = play.get('stop_loss', {}).get('stock_price')
        if sl_target and current_price:
            if trade_type == 'CALL' and current_price <= sl_target:
                sl_hit = True
            elif trade_type == 'PUT' and current_price >= sl_target:
                sl_hit = True
        
        if tp_hit or sl_hit:
            close_conditions = {
                'should_close': True,
                'is_profit': tp_hit,
                'is_primary_loss': sl_hit,
                'is_contingency_loss': False,
                'sl_type': 'LIMIT' if sl_hit else None
            }
            plays_to_close.append((play, close_conditions))
    
    return plays_to_close
```

### Step 5: Add Configuration Section

Add to `config/settings.yaml`:

```yaml
my_strategy:
  enabled: false    # Set to true to activate
  # Strategy-specific settings
  entry_buffer: 0.50
  take_profit_pct: 25
  stop_loss_pct: 15
```

### Step 6: Register for Discovery

Add the module name to `strategy/registry.py` in the `runner_modules` list:

```python
runner_modules = [
    'option_swings',
    'option_swings_auto',
    'momentum',
    'sell_puts',
    'spreads',
    'my_strategy',  # Add your strategy here
]
```

---

## Trade Direction (Long vs Short Strategies)

### Long Premium Strategies (BTO → STC)

Default for most strategies. Buy options and profit when premium increases.

```python
# Uses base class defaults - no override needed
# get_default_entry_action() returns OrderAction.BUY_TO_OPEN
# get_default_exit_action() returns OrderAction.SELL_TO_CLOSE
```

**Examples:** option_swings, momentum, option_swings_auto

### Short Premium Strategies (STO → BTC)

Sell/write options and profit when premium decreases (or expires worthless).

```python
def get_default_entry_action(self) -> OrderAction:
    """Override for short premium strategy."""
    return OrderAction.SELL_TO_OPEN

def get_default_exit_action(self) -> OrderAction:
    """Corresponding exit action."""
    return OrderAction.BUY_TO_CLOSE
```

**Examples:** sell_puts, covered_calls

### Order Action Reference

| Action | Code | Direction | Use Case |
|--------|------|-----------|----------|
| BUY_TO_OPEN | `OrderAction.BUY_TO_OPEN` | Open Long | Buy calls/puts to profit from premium increase |
| SELL_TO_CLOSE | `OrderAction.SELL_TO_CLOSE` | Close Long | Exit long position by selling |
| SELL_TO_OPEN | `OrderAction.SELL_TO_OPEN` | Open Short | Sell/write options to collect premium |
| BUY_TO_CLOSE | `OrderAction.BUY_TO_CLOSE` | Close Short | Exit short position by buying back |

---

## Using Shared Utilities

The `strategy/shared/` module provides reusable functions:

### Evaluation Functions

```python
from goldflipper.strategy.shared import (
    evaluate_opening_strategy,
    evaluate_closing_strategy,
    calculate_and_store_price_levels,
    calculate_and_store_premium_levels,
)

# Use in evaluate_new_plays():
should_enter = evaluate_opening_strategy(
    symbol=symbol,
    play=play,
    get_stock_price_fn=self._get_stock_price  # Your price function
)

# Use in evaluate_open_plays():
close_conditions = evaluate_closing_strategy(
    symbol=symbol,
    play=play,
    play_file=play_file,
    get_stock_price_fn=self._get_stock_price,
    get_option_data_fn=self._get_option_data,
    save_play_fn=save_play_improved
)
```

### Play Management

```python
from goldflipper.strategy.shared import (
    PlayManager,
    save_play,
    save_play_improved,
    move_play_to_open,
    move_play_to_closed,
)

# Save play with changes
save_play_improved(play_file, play)

# Move play between folders
move_play_to_open(play_file)
```

### Order Execution

```python
from goldflipper.strategy.shared import OrderExecutor

executor = OrderExecutor(
    client=self.client,
    market_data=self.market_data
)

# Orders are typically handled by orchestrator, but available if needed
```

---

## Market Condition Screening

Strategies that auto-scan for entries can gate plays through VWAP, Volume Profile, and
Greeks-based conditions. These evaluators live in `strategy/shared/market_conditions.py`
and are exported from `strategy/shared`.

### Available Evaluators

| Evaluator | Guards Against |
|-----------|---------------|
| `evaluate_vwap_condition` | Entering calls below VWAP / puts above VWAP; price too far from VWAP |
| `evaluate_volume_profile_condition` | Entering outside value area; calls below POC / puts above POC |
| `evaluate_greek_conditions` | Low/high delta; gamma squeeze; gamma fade; delta fade; parabolic extension |

### Usage Pattern in `evaluate_new_plays()`

```python
from goldflipper.strategy.shared import (
    evaluate_vwap_condition,
    evaluate_volume_profile_condition,
    evaluate_greek_conditions,
)

def evaluate_new_plays(self, plays):
    plays_to_open = []
    for play in plays:
        symbol = play.get('symbol', '')
        playbook = self.get_playbook_for_play(play)
        cfg = playbook.option_swings_config  # or momentum_config, etc.

        # VWAP screen
        vwap_result = evaluate_vwap_condition(
            self.market_data, symbol, play, cfg.vwap.to_dict()
        )
        if not vwap_result['passed']:
            self.logger.info(f"VWAP screen failed for {symbol}: {vwap_result['reason']}")
            continue

        # Volume Profile screen
        vp_result = evaluate_volume_profile_condition(
            self.market_data, symbol, play, cfg.volume_profile.to_dict()
        )
        if not vp_result['passed']:
            self.logger.info(f"VP screen failed for {symbol}: {vp_result['reason']}")
            continue

        # Greeks screen
        greek_result = evaluate_greek_conditions(
            self.market_data, symbol, play, cfg.greek_conditions.to_dict()
        )
        if not greek_result['passed']:
            self.logger.info(f"Greek screen failed: {greek_result['flags']}")
            continue

        plays_to_open.append(play)
    return plays_to_open
```

### Behaviour Guarantees

- All evaluators return `passed=True` when data is unavailable (permissive by default),
  so a data gap never silently blocks all trades.
- Each evaluator respects an `enabled` flag — if `False`, returns `passed=True` immediately
  without making any market data calls.
- Results include rich context (`vwap`, `poc`, `delta`, `flags`, etc.) for logging.

### Playbook Config Dataclasses

`VWAPConfig`, `VolumeProfileConfig`, and `GreekConditionsConfig` in
`strategy/playbooks/schema.py` are nested fields on `OptionSwingsConfig` and `MomentumConfig`.
They default to `enabled: false` so existing playbooks are unaffected until you opt in.

Configure them in your playbook YAML:

```yaml
option_swings_config:
  vwap:
    enabled: true
    require_price_above_vwap: true   # CALL entries only
    require_price_below_vwap: true   # PUT entries only
    proximity_pct: 3.0               # Must be within ±3% of VWAP

  volume_profile:
    enabled: true
    call_requires_above_poc: true
    put_requires_below_poc: true

  greek_conditions:
    enabled: true
    min_delta: 0.30
    max_delta: 0.50
    check_gamma_squeeze: true
    gamma_squeeze_blocks_entry: false  # Log only, don't block
    check_parabolic: true
    parabolic_blocks_entry: true
```

See `strategy/playbooks/option_swings/pb_v3.yaml` and
`strategy/playbooks/momentum/goldflipper_gap_move.yaml` for full annotated examples.

---

## Playbook Support

Strategies can use playbooks for configurable parameters:

### Loading Playbooks

```python
# In your strategy:
playbook = self.get_playbook_for_play(play)

# Get specific setting with dot-notation
tp_pct = self.get_playbook_setting(play, 'exit.take_profit_pct', default=50.0)
sl_pct = self.get_playbook_setting(play, 'exit.stop_loss_pct', default=25.0)
```

### Creating Playbook Files

Create YAML files in `strategy/playbooks/{strategy_name}/`:

```yaml
# strategy/playbooks/my_strategy/default.yaml
name: "My Strategy Default"
version: "1.0"

entry:
  order_type: "limit at mid"
  buffer: 0.50

exit:
  take_profit_pct: 25
  stop_loss_pct: 15

risk:
  max_contracts: 5
  max_position_pct: 5
```

---

## Optional Overrides

### Custom Validation

```python
def validate_play(self, play: Dict[str, Any]) -> bool:
    """Add strategy-specific validation."""
    if not super().validate_play(play):
        return False
    
    # My strategy requires custom_field
    if 'custom_field' not in play:
        self.logger.warning("Play missing custom_field")
        return False
    
    return True
```

### Execution Priority

```python
def get_priority(self) -> int:
    """
    Lower = runs earlier.
    - 10: High priority (primary strategies)
    - 50: Medium priority
    - 100: Default
    - 200: Low priority (cleanup tasks)
    """
    return 50
```

### Lifecycle Hooks

```python
def on_cycle_start(self) -> None:
    """Called at start of each orchestrator cycle."""
    super().on_cycle_start()
    # Refresh caches, log cycle start, etc.

def on_cycle_end(self) -> None:
    """Called at end of each orchestrator cycle."""
    super().on_cycle_end()
    # Cleanup, metrics, etc.
```

---

## Testing Your Strategy

### Unit Tests

Create tests in `goldflipper/tests/`:

```python
# tests/test_my_strategy.py
import unittest
from unittest.mock import Mock, patch

class TestMyStrategy(unittest.TestCase):
    
    def setUp(self):
        self.mock_config = {
            'my_strategy': {'enabled': True}
        }
        self.mock_market_data = Mock()
        self.mock_client = Mock()
    
    def test_strategy_name(self):
        from goldflipper.strategy.runners.my_strategy import MyStrategy
        
        strategy = MyStrategy(
            self.mock_config,
            self.mock_market_data,
            self.mock_client
        )
        self.assertEqual(strategy.get_name(), "my_strategy")
    
    def test_entry_evaluation(self):
        # Test your entry logic with mock data
        pass
```

### Dry-Run Testing

Enable dry-run mode in settings.yaml:

```yaml
strategy_orchestration:
  enabled: true
  dry_run: true  # No actual orders
  
my_strategy:
  enabled: true
```

Run the system and check logs for `[DRY-RUN]` entries.

---

## Play File Schema

Plays are JSON files stored in `plays/{status}/`. Minimum required fields:

```json
{
  "symbol": "AAPL",
  "trade_type": "CALL",
  "strike_price": 200,
  "expiration_date": "12/20/2024",
  "contracts": 1,
  "status": {
    "current_status": "NEW"
  },
  "entry_point": {
    "order_type": "market",
    "stock_price": 195.00
  },
  "take_profit": {
    "stock_price": 205.00
  },
  "stop_loss": {
    "stock_price": 190.00
  }
}
```

### Strategy-Specific Fields

Add `strategy` field to identify which strategy handles this play:

```json
{
  "strategy": "my_strategy",
  "playbook": "default",
  // ... other fields
}
```

---

## Reference: Existing Strategies

| Strategy | File | Direction | Description |
|----------|------|-----------|-------------|
| option_swings | `runners/option_swings.py` | BTO→STC | Manual option swings (~450 lines) |
| option_swings_auto | `runners/option_swings_auto.py` | BTO→STC | Automated swings (stub) |
| momentum | `runners/momentum.py` | BTO→STC | Gap/momentum trades |
| sell_puts | `runners/sell_puts.py` | STO→BTC | Cash-secured puts (~600 lines) |
| spreads | `runners/spreads.py` | Multi-leg | Multi-leg spreads (~690 lines) |

---

## Checklist: Adding a New Strategy

- [ ] Create `strategy/runners/my_strategy.py`
- [ ] Implement `get_name()`, `get_config_section()`, `get_plays_base_dir()`
- [ ] Implement `evaluate_new_plays()` with entry logic
- [ ] Implement `evaluate_open_plays()` with exit logic
- [ ] Add `@register_strategy('my_strategy')` decorator
- [ ] Add module to `registry.py` `runner_modules` list
- [ ] Add config section to `settings.yaml`
- [ ] (Optional) Create playbook files in `strategy/playbooks/my_strategy/`
- [ ] (Optional) Create play template in `tools/templates/`
- [ ] Write unit tests
- [ ] Test with dry-run mode enabled
- [ ] Document strategy in this guide or separate doc

---

## Troubleshooting

### Strategy Not Loading

1. Check `@register_strategy` decorator is present
2. Verify module is in `registry.py` `runner_modules` list
3. Check for import errors: `python -c "from goldflipper.strategy.runners.my_strategy import MyStrategy"`

### Strategy Not Running

1. Verify `strategy_orchestration.enabled: true` in settings.yaml
2. Verify `my_strategy.enabled: true` in settings.yaml
3. Check logs for initialization messages

### Entry/Exit Not Triggering

1. Enable debug logging for your strategy
2. Use dry-run mode to see what WOULD happen
3. Check that market data is returning valid prices
4. Verify play files have correct field structure

---

## Support

- **Implementation Doc:** `goldflipper/docs/MULTI_STRATEGY_IMPLEMENTATION.md`
- **Base Class:** `goldflipper/strategy/base.py`
- **Registry:** `goldflipper/strategy/registry.py`
- **Example (Full):** `goldflipper/strategy/runners/option_swings.py`
- **Example (Stub):** `goldflipper/strategy/runners/option_swings_auto.py`
