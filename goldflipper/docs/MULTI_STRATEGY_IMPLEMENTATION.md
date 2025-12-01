# Multi-Strategy Implementation Plan

**Document Created:** 2025-11-29  
**Last Updated:** 2025-12-01  
**Status:** Phase 6 In Progress - Strategy Implementation  
**Breaking Changes:** None (fully additive, backward compatible)  
**Current Phase:** Phase 6 (Strategy Implementation) - Momentum complete, Play tools next

---

## Overview

This document tracks the implementation of multi-strategy support for Goldflipper. The goal is to enable multiple trading strategies (option swings, momentum, sell puts, spreads, etc.) to run either sequentially or in parallel, while maintaining full backward compatibility with the existing option swings implementation.

### Design Principles

1. **Non-destructive migration** - Existing functionality must continue working unchanged
2. **Shared infrastructure** - Market data, brokerage client, and config remain centralized
3. **Strategy isolation** - Each strategy is self-contained and can be enabled/disabled independently
4. **Gradual adoption** - New system can run alongside old until validated

---

## Architecture Summary

### Code Structure
```
goldflipper/
├── core.py                      # Phase 2: Thin wrappers calling shared modules
├── strategy/
│   ├── __init__.py              # Updated exports
│   ├── base.py                  # NEW: Abstract base class
│   ├── orchestrator.py          # NEW: Multi-strategy coordinator
│   ├── registry.py              # NEW: Strategy discovery
│   ├── trailing.py              # Existing - refactor later to shared
│   ├── shared/                  # NEW: Extracted shared utilities (Phase 2)
│   │   ├── __init__.py          # ✅ Complete - All exports
│   │   ├── play_manager.py      # ✅ Complete - Play file operations
│   │   ├── order_executor.py    # ✅ Complete - Order placement helpers
│   │   ├── evaluation.py        # ✅ Complete - TP/SL evaluation helpers
│   │   ├── trailing_manager.py  # FUTURE: Strategy-agnostic trailing
│   │   └── stop_loss_manager.py # FUTURE: Strategy-agnostic SL types
│   └── runners/                 # NEW: Strategy implementations
│       ├── __init__.py
│       ├── option_swings.py     # Pending - Current strategy, to be extracted
│       ├── option_swings_auto.py
│       ├── momentum.py
│       ├── sell_puts.py
│       └── spreads.py
```

### Play Directory Structure (Account-Based)
```
plays/
├── account_1/                    # Live account (alpaca.accounts.live)
│   ├── shared/                   # Shared pool - legacy/cross-strategy plays
│   │   ├── new/
│   │   ├── pending-opening/
│   │   ├── open/
│   │   ├── pending-closing/
│   │   ├── closed/
│   │   ├── expired/
│   │   └── temp/
│   ├── option_swings/            # Strategy-specific directories
│   │   ├── new/
│   │   ├── open/
│   │   └── ...
│   ├── momentum/
│   ├── sell_puts/
│   └── spreads/
├── account_2/                    # Paper account 1 (alpaca.accounts.paper_1)
│   └── ... (same structure)
├── account_3/                    # Paper account 2 (alpaca.accounts.paper_2)
│   └── ...
└── account_4/                    # Paper account 3 (alpaca.accounts.paper_3)
    └── ...
```

**Account Mapping (settings.yaml → directory):**
- `live` → `account_1/`
- `paper_1` → `account_2/`
- `paper_2` → `account_3/`
- `paper_3` → `account_4/`

---

## Implementation Phases

### Phase 1: Base Infrastructure (Non-Breaking) ✅ COMPLETE

Create the foundational classes that define the multi-strategy system. These files are purely additive and don't affect existing code.

| Task | File | Status | Notes |
|------|------|--------|-------|
| Abstract base class | `strategy/base.py` | ✅ Done | Strategy interface definition |
| Strategy registry | `strategy/registry.py` | ✅ Done | Discovery & registration |
| Orchestrator | `strategy/orchestrator.py` | ✅ Done | Multi-strategy coordination |
| Update exports | `strategy/__init__.py` | ✅ Done | Export new modules |
| Shared utils dir | `strategy/shared/__init__.py` | ✅ Done | Placeholder for extraction |
| Runners dir | `strategy/runners/__init__.py` | ✅ Done | Strategy implementations |
| Config section | `config/settings.yaml` | ✅ Done | strategy_orchestration section |

**Validation Criteria:**
- [x] All new files import without errors
- [x] Existing `trailing.py` functionality unchanged
- [x] `from goldflipper.strategy import BaseStrategy, StrategyOrchestrator` works
- [x] No changes to `core.py` or `run.py`

---

### Phase 2: Shared Utilities Extraction (Non-Breaking) ✅ COMPLETE

Extract reusable code from `core.py` into `strategy/shared/`. Original functions in `core.py` become thin wrappers.

| Task | Source (core.py) | Target | Status |
|------|------------------|--------|--------|
| Play file operations | `move_play_to_*`, `save_play`, `load_play` | `shared/play_manager.py` | ✅ Done |
| Order execution helpers | Order type determination, limit price calculation | `shared/order_executor.py` | ✅ Done |
| Evaluation helpers | `evaluate_opening_strategy`, `evaluate_closing_strategy` | `shared/evaluation.py` | ✅ Done |
| Price/premium calculations | `calculate_and_store_*` | `shared/evaluation.py` | ✅ Done |
| Thin wrappers in core.py | All extracted functions | core.py | ✅ Done |

**Approach:**
1. Create new module with extracted logic
2. Update `core.py` function to call new module (thin wrapper)
3. Test that existing behavior is unchanged
4. Repeat for next function

**Files Created:**
- `strategy/shared/play_manager.py` (560 lines)
  - `PlayManager` class with account-aware directory routing
  - `PlayStatus` enum for status management
  - `UUIDEncoder` for JSON serialization
  - Standalone functions: `save_play()`, `save_play_improved()`, `move_play_to_*()` (7 functions)
  
- `strategy/shared/evaluation.py` (538 lines)
  - `evaluate_opening_strategy()` - Entry condition evaluation
  - `evaluate_closing_strategy()` - Exit condition evaluation (TP/SL/contingency)
  - `calculate_and_store_price_levels()` - Stock price target calculations
  - `calculate_and_store_premium_levels()` - Option premium target calculations
  
- `strategy/shared/order_executor.py` (483 lines)
  - `OrderExecutor` class for order placement operations
  - `determine_limit_price()` - Helper for limit price determination
  - `get_entry_premium()` - Entry premium calculation
  - Order creation and position state management helpers
  
- `strategy/shared/__init__.py` - Complete exports for all shared modules

**Files Modified:**
- `core.py` - Converted 12+ functions to thin wrappers:
  - `save_play()`, `save_play_improved()`
  - `move_play_to_new()`, `move_play_to_pending_opening()`, `move_play_to_open()`
  - `move_play_to_pending_closing()`, `move_play_to_closed()`, `move_play_to_expired()`, `move_play_to_temp()`
  - `evaluate_opening_strategy()`, `evaluate_closing_strategy()`
  - `calculate_and_store_price_levels()`, `calculate_and_store_premium_levels()`
  - `UUIDEncoder` (now inherits from shared module)

**Key Features:**
- All shared modules support dependency injection for testing
- Both class-based (`PlayManager`, `OrderExecutor`) and standalone function interfaces
- Full backward compatibility - existing code using `from goldflipper.core import save_play` works unchanged
- Thin wrappers preserve exact original behavior

**Validation Criteria:**
- [ ] All existing tests pass
- [ ] `monitor_plays_continuously()` works identically
- [ ] Play state transitions work correctly
- [ ] Order placement works correctly

---

### Phase 3: Configuration Updates (Non-Breaking) ✅ COMPLETE

Add new configuration sections to `settings.yaml` for strategy orchestration.

| Task | Status |
|------|--------|
| Add `strategy_orchestration` section | ✅ Done (Phase 1) |
| Add `momentum` config stub | ✅ Done (Phase 1) |
| Add `option_swings_auto` config stub | ✅ Done (Phase 1) |
| Add `sell_puts` config stub | ✅ Done (Phase 1) |
| Add `spreads` config stub | ✅ Done (Phase 1) |

**Validation Criteria:**
- [x] Config loads without errors
- [x] Existing `options_swings` section unchanged
- [x] New sections have `enabled: false` by default

**Note:** All configuration sections were added during Phase 1. Phase 3 validation confirmed they are complete.

---

### Phase 4: Strategy Runner Implementation (Non-Breaking)

Create strategy runner classes. These are new files that don't affect existing code.

| Strategy | File | Priority | Status |
|----------|------|----------|--------|
| Option Swings | `runners/option_swings.py` | P0 - First | ✅ Done |
| Option Swings Auto | `runners/option_swings_auto.py` | P1 | ✅ Done (stub) |
| Momentum | `runners/momentum.py` | P2 | ✅ Done (stub) |
| Sell Puts | `runners/sell_puts.py` | P2 | ✅ Done (full) |
| Spreads | `runners/spreads.py` | P3 | ✅ Done (stub) |

**Validation Criteria:**
- [x] Each runner implements `BaseStrategy` interface
- [x] Runners can be instantiated without errors
- [x] Runners registered in `StrategyRegistry`

**Notes:**
- `option_swings.py`: Full implementation with entry/exit evaluation logic
- `sell_puts.py`: Full TastyTrade-style implementation (STO/BTC, inverted TP/SL, DTE mgmt)
- Other runners: Stub implementations that register correctly but return empty results
- All stubs have `enabled: false` in config by default

---

### Phase 5: Integration (Non-Breaking with fallback_to_legacy)

Wire the orchestrator into the main execution flow.

| Task | Status |
|------|--------|
| Create `run_multi.py` as new entry point | ✅ Done |
| Update orchestrator to execute trades | ✅ Done |
| Update `run.py` to use orchestrator | ✅ Done |
| Test orchestrator with single strategy | 🔲 Pending |
| Test parallel execution mode | 🔲 Pending |
| Deprecate direct `core.py` calls | 🔲 Pending |

**Implementation Details:**
- `run_multi.py`: Standalone entry point with orchestration support
- `run.py`: Updated to check `strategy_orchestration.enabled` and use orchestrator when enabled
- `orchestrator._execute_strategy()`: Now calls `strategy.open_position()` and `strategy.close_position()`
- Handles expired plays, pending plays, and trade execution
- Falls back to legacy `monitor_plays_continuously()` if orchestrator fails (when `fallback_to_legacy: true`)

**Validation Criteria:**
- [ ] Single strategy mode works identically to current system
- [ ] Multiple strategies can run sequentially
- [ ] Parallel mode doesn't cause race conditions
- [ ] Market data caching works across strategies
- [ ] All play state transitions work correctly

---

### Phase 6: Strategy Implementation & Play Tools

**USER PRIORITY ORDER (2025-11-30):**
1. Define playbook schema and strategy-specific play templates
2. Implement real strategy logic (Priority: `sell_puts`, `momentum` for gap moves)
3. Update play creation tooling
4. Unit tests

| Task | Priority | Status |
|------|----------|--------|
| Define playbook schema and loader | P0 | ✅ Done |
| Create strategy-specific play templates | P0 | ✅ Done |
| Implement `sell_puts.py` with real logic | P1 | ✅ Done |
| Implement `momentum.py` with real logic (gap moves) | P1 | ✅ Done |
| Create playbooks for each strategy | P1 | ✅ Done (sell_puts, momentum) |
| Add `playbook` field to play templates | P1 | ✅ Done |
| Update Auto Play Creator for multi-strategy | P2 | 🔲 Pending |
| Update CSV Ingestor for multi-strategy | P2 | 🔲 Pending |
| Update original play creation tool | P2 | 🔲 Pending |
| Unit tests for orchestrator | P3 | 🔲 Pending |
| Implement `spreads.py` with real logic | P4 | 🔲 Pending |
| Implement `option_swings_auto.py` with real logic | P4 | 🔲 Pending |

**Playbook System (Implemented 2025-11-30):**

Files created:
- `strategy/playbooks/schema.py` - Dataclass definitions (Playbook, EntryConfig, ExitConfig, RiskConfig, SellPutsConfig, MomentumConfig)
- `strategy/playbooks/loader.py` - PlaybookLoader class with caching, path resolution
- `strategy/playbooks/__init__.py` - Module exports
- `strategy/playbooks/sell_puts/default.yaml` - TastyTrade-style 30-delta puts
- `strategy/playbooks/sell_puts/tasty_30_delta.yaml` - Strict TastyTrade methodology
- `strategy/playbooks/momentum/default.yaml` - Generic manual-entry momentum
- `strategy/playbooks/momentum/gap_move.yaml` - Gap continuation (trade WITH gap)
- `strategy/playbooks/momentum/gap_fade.yaml` - Gap fade/mean reversion (trade AGAINST gap)

BaseStrategy updated with:
- `get_playbook_for_play(play)` - Load playbook for a play
- `get_default_playbook()` - Load strategy's default playbook
- `get_playbook_setting(play, path, default)` - Get setting via dot-notation

**Momentum Strategy Implementation (2025-12-01):**

The momentum strategy (`strategy/runners/momentum.py`) is a general-purpose long premium 
strategy (BTO → STC) with playbook-driven momentum types. The specific momentum type 
determines entry evaluation logic.

Architecture:
```
MomentumStrategy (general BTO/STC runner)
    ├── momentum_type: "gap"      → _evaluate_gap_entry()      [IMPLEMENTED]
    ├── momentum_type: "squeeze"  → _evaluate_squeeze_entry()  [STUB - FUTURE]
    ├── momentum_type: "ema_cross"→ _evaluate_ema_cross_entry()[STUB - FUTURE]
    └── momentum_type: "manual"   → _evaluate_entry_conditions()[DEFAULT]
```

MomentumConfig (in `schema.py`) includes:
- `momentum_type` - Determines entry evaluation: "gap", "squeeze", "ema_cross", "manual"
- Gap-specific settings (only used when momentum_type: "gap"):
  - `gap_type` - "up", "down", "any"
  - `min_gap_pct`, `max_gap_pct` - Gap size thresholds
  - `trade_direction` - "with_gap" (continuation) or "fade_gap" (mean reversion)
  - `wait_for_confirmation`, `confirmation_period_minutes` - Entry timing
- Common settings: `dte_min`, `dte_max`, `same_day_exit`, `max_hold_days`

Gap Move Logic (momentum_type: "gap"):
- Validates `gap_info` section in play (gap_type, gap_pct, trade_direction)
- Checks gap size against min/max thresholds from playbook
- Optionally waits for confirmation period after market open
- Entry: Stock price near entry target (uses shared `evaluate_opening_strategy`)
- Exit: Premium-based TP/SL + time-based exits (same-day, max hold days)

Playbooks:
- `gap_move.yaml` - Trade WITH gap direction (continuation)
- `gap_fade.yaml` - Trade AGAINST gap direction (mean reversion)
- `default.yaml` - Manual entry (no gap validation, just price conditions)

Play File Requirements (for gap momentum):
```json
{
  "strategy": "momentum",
  "playbook": "gap_move",
  "gap_info": {
    "gap_type": "up",
    "gap_pct": 3.5,
    "previous_close": 150.00,
    "gap_open": 155.25,
    "trade_direction": "with_gap"
  }
}
```

**Play Templates (Implemented 2025-11-30):**

Templates in `tools/templates/`:
- `play_template_base.json` - Base template with `strategy` and `playbook` fields
- `play_template_option_swings.json` - Option swings (BTO/STC)
- `play_template_sell_puts.json` - Cash-secured puts (STO/BTC) with collateral tracking
- `play_template_momentum.json` - Gap/momentum trades with gap_info section
- `play_template_spreads.json` - Multi-leg spreads with legs array

Key additions to play templates:
- `strategy` field - Identifies strategy type
- `playbook` field - References playbook name (e.g., "default", "tasty_30_delta")
- `action` field - BTO/STC/STO/BTC order action
- Strategy-specific sections (gap_info, collateral, legs, etc.)

**Play Creation Tools Requirements:**
- All play creation tools must deposit plays into the **currently active account's plays directory** by default
- Tools should **confirm with user** before depositing (show target directory, allow override)
- Support generating plays for any enabled strategy type
- Use strategy-specific templates from `tools/templates/`
- Set `playbook` field to link play to its parameter source

---

### Phase 7: Trade Logger & Analytics

| Task | Status |
|------|--------|
| Update trade logger for multi-strategy support | 🔲 Pending |
| Update trade logger for multi-account support | 🔲 Pending |
| Revamp trade logger GUI with filtering | 🔲 Pending |
| Add strategy/account filter controls | 🔲 Pending |

**Trade Logger Requirements:**
- Pull plays from all strategies and all accounts
- GUI should allow user to filter by:
  - Strategy type(s)
  - Account(s)
  - Date range
  - Play status
- Continue using play files as source of truth (read `logging` section from each play)
- Future: More sophisticated analytics (P&L by strategy, win rate, etc.)

---

### Phase 8: Cleanup & Documentation

| Task | Status |
|------|--------|
| Remove deprecated code from `core.py` | 🔲 Pending |
| Update `DEVELOPMENT.md` | 🔲 Pending |
| Add strategy development guide | 🔲 Pending |
| Update `README.md` | 🔲 Pending |
| Add unit tests for orchestrator | 🔲 Pending |
| Add dry-run mode for market-closed testing | 🔲 Pending |

**Note:** Deprecated code cleanup should only happen AFTER the new system is confirmed working in production.

---

## File Specifications

### `strategy/base.py`

```python
class BaseStrategy(ABC):
    """Abstract base class for all trading strategies."""
    
    @abstractmethod
    def get_name(self) -> str: ...
    
    @abstractmethod
    def get_config_section(self) -> str: ...
    
    @abstractmethod
    def get_plays_base_dir(self) -> str: ...
    
    @abstractmethod
    def evaluate_new_plays(self, plays: List[Dict]) -> List[Dict]: ...
    
    @abstractmethod
    def evaluate_open_plays(self, plays: List[Dict]) -> List[tuple]: ...
    
    def get_priority(self) -> int: ...
    def is_enabled(self) -> bool: ...
    def on_cycle_start(self): ...
    def on_cycle_end(self): ...
    def validate_play(self, play: Dict) -> bool: ...
```

### `strategy/registry.py`

```python
class StrategyRegistry:
    """Registry for strategy discovery and management."""
    
    @classmethod
    def register(cls, name: str, strategy_class): ...
    
    @classmethod
    def get(cls, name: str): ...
    
    @classmethod
    def get_all_strategies(cls): ...
    
    @classmethod
    def discover(cls): ...

def register_strategy(name: str):
    """Decorator for strategy registration."""
    ...
```

### `strategy/orchestrator.py`

```python
class StrategyOrchestrator:
    """Coordinates execution of multiple trading strategies."""
    
    def initialize(self): ...
    def run_cycle(self): ...
    def _run_sequential(self): ...
    def _run_parallel(self): ...
    def _execute_strategy(self, strategy): ...
```

---

## Configuration Schema

```yaml
# settings.yaml additions

strategy_orchestration:
  enabled: true                  # Master switch for multi-strategy mode
  mode: "sequential"             # "sequential" | "parallel"
  max_parallel_workers: 3        # Max concurrent when parallel
  fallback_to_legacy: true       # Use core.py if orchestrator fails

momentum:
  enabled: false
  # ... strategy-specific settings

option_swings_auto:
  enabled: false
  # ... strategy-specific settings

sell_puts:
  enabled: false
  # ... strategy-specific settings

spreads:
  enabled: false
  # ... strategy-specific settings
```

---

## Testing Strategy

### Unit Tests (New)

- `tests/test_strategy_base.py` - BaseStrategy interface
- `tests/test_strategy_registry.py` - Registration/discovery
- `tests/test_strategy_orchestrator.py` - Orchestration logic

### Integration Tests

- Test with `strategy_orchestration.enabled: false` (legacy mode)
- Test with single strategy enabled
- Test with multiple strategies enabled
- Test parallel vs sequential execution

### Regression Tests

- Ensure all existing tests pass throughout migration
- Manually test play lifecycle (new → open → closed)
- Verify order placement works

---

## Rollback Plan

If issues arise during Phase 5 integration:

1. Set `strategy_orchestration.enabled: false` in config
2. System falls back to existing `core.py` behavior
3. Investigate and fix issues in orchestrator
4. Re-enable when fixed

The fallback mechanism ensures production stability during migration.

---

## Progress Log

| Date | Phase | Work Done | Notes |
|------|-------|-----------|-------|
| 2025-11-29 | 1 | Created implementation plan | Document created |
| 2025-11-29 | 1 | Created strategy/base.py | BaseStrategy ABC with full interface |
| 2025-11-29 | 1 | Created strategy/registry.py | StrategyRegistry with @register_strategy decorator |
| 2025-11-29 | 1 | Created strategy/orchestrator.py | StrategyOrchestrator with seq/parallel modes |
| 2025-11-29 | 1 | Created strategy/shared/__init__.py | Placeholder for shared utilities |
| 2025-11-29 | 1 | Created strategy/runners/__init__.py | Placeholder for strategy runners |
| 2025-11-29 | 1 | Updated strategy/__init__.py | Exports for new modules |
| 2025-11-29 | 1 | Updated settings.yaml | Added strategy_orchestration + strategy stubs |
| 2025-11-29 | 1 | **Phase 1 Complete** | All base infrastructure in place |
| 2025-11-29 | - | Design decisions finalized | Account-based dirs, strategy independence, future refactors |
| 2025-11-30 | 2 | Created strategy/shared/play_manager.py | PlayManager class + move/save functions |
| 2025-11-30 | 2 | Created strategy/shared/evaluation.py | evaluate_opening/closing + calc functions |
| 2025-11-30 | 2 | Created strategy/shared/order_executor.py | OrderExecutor class + order helpers |
| 2025-11-30 | 2 | Updated strategy/shared/__init__.py | Exports for all shared modules |
| 2025-11-30 | 2 | Updated core.py | Thin wrappers calling shared modules |
| 2025-11-30 | 2 | **Phase 2 Complete** | Shared utilities extracted, backward compatible |
| 2025-11-30 | 3 | Validated config sections | All sections from Phase 1 confirmed working |
| 2025-11-30 | 3 | **Phase 3 Complete** | Config validation passed, ready for Phase 4 |
| 2025-11-30 | 4 | Created strategy/runners/option_swings.py | Full BaseStrategy implementation for manual option swings |
| 2025-11-30 | 4 | Created strategy/runners/option_swings_auto.py | Stub implementation for automated option swings |
| 2025-11-30 | 4 | Created strategy/runners/momentum.py | Stub implementation for momentum strategy |
| 2025-11-30 | 4 | Created strategy/runners/sell_puts.py | Stub implementation for cash-secured puts |
| 2025-11-30 | 4 | Created strategy/runners/spreads.py | Stub implementation for options spreads |
| 2025-11-30 | 4 | **Phase 4 Complete** | All 5 strategy runners created and registered |
| 2025-11-30 | 5 | Created run_multi.py | New entry point with orchestration support |
| 2025-11-30 | 5 | Updated orchestrator._execute_strategy() | Now executes trades via strategy methods |
| 2025-11-30 | 5 | Updated run.py | Orchestration support with fallback to legacy |
| 2025-11-30 | 6 | Added OrderAction enum | BTO/STC/STO/BTC trade direction support |
| 2025-11-30 | 6 | Added PositionSide enum | LONG/SHORT position classification |
| 2025-11-30 | 6 | Updated BaseStrategy | Added order action methods and helpers |
| 2025-11-30 | 6 | Updated SellPutsStrategy | Now uses STO/BTC for short premium |
| 2025-11-30 | 6 | Updated SpreadsStrategy | Multi-leg support with SpreadType/SpreadLeg |
| 2025-11-30 | 6 | Updated OrderExecutor | action parameter for entry/exit orders |
| 2025-11-30 | 6 | Created strategy/playbooks/schema.py | Playbook, EntryConfig, ExitConfig, RiskConfig dataclasses |
| 2025-11-30 | 6 | Created strategy/playbooks/loader.py | PlaybookLoader with caching and path resolution |
| 2025-11-30 | 6 | Created sell_puts playbooks | default.yaml, tasty_30_delta.yaml |
| 2025-11-30 | 6 | Created momentum playbooks | default.yaml, gap_fade.yaml |
| 2025-11-30 | 6 | Created tools/templates/ | Strategy-specific play templates (base, option_swings, sell_puts, momentum, spreads) |
| 2025-11-30 | 6 | Updated BaseStrategy | Added playbook loading methods (get_playbook_for_play, get_playbook_setting) |
| 2025-12-01 | 6 | Implemented sell_puts.py | Full TastyTrade-style implementation (~600 lines) |
| 2025-12-01 | 6 | sell_puts features | Entry evaluation, inverted TP/SL for short premium, DTE mgmt, ITM checks |
| 2025-11-30 | 6 | **Phase 6 Partial Complete** | Playbook schema + templates done, sell_puts done, other strategies pending |

---

## Design Decisions

### 1. Play Directory Structure (DECIDED)

**Decision:** Hybrid approach - both shared pools AND individual strategy directories, organized by account.

```
plays/
├── account_1/                    # Live account
│   ├── shared/                   # Shared pool (legacy compatibility)
│   │   ├── new/
│   │   ├── open/
│   │   └── ...
│   ├── option_swings/            # Strategy-specific
│   │   ├── new/
│   │   └── ...
│   ├── momentum/
│   └── ...
├── account_2/                    # Paper account 1
│   ├── shared/
│   └── ...
├── account_3/                    # Paper account 2
└── account_4/                    # Paper account 3
```

**Account Numbering:**
- Account 1 = Live account
- Account 2, 3, 4 = Paper accounts (maps to paper_1, paper_2, paper_3 in config)

**Migration Path:**
1. Current `plays/` becomes `plays/account_X/shared/` based on active account
2. Strategy-specific dirs created on-demand when strategies are enabled
3. Strategies can choose to use shared pool OR their own directory

### 2. Strategy Independence (DECIDED)

**Decision:** Strategies run independently. Conflict resolution (same symbol, etc.) is deferred to future implementation.

**Note for future:** Consider adding a `SymbolLockManager` or similar to prevent multiple strategies from opening conflicting positions on the same underlying.

### 3. Trailing Stops (DECIDED - Future Refactor)

**Decision:** Make `trailing.py` strategy-agnostic. Currently embedded in option_swings logic but should be refactored to be a shared utility that any strategy can use.

**Future Work:**
- Extract trailing stop logic into `strategy/shared/trailing_stops_manager.py`
- Strategies call `TrailingManager.update(play)` during their monitoring
- Keep existing `trailing.py` for backward compatibility during transition

### 4. Contingency Stop Loss (DECIDED - Future Refactor)

**Decision:** Similar to trailing stops, refactor contingency SL system to be strategy-agnostic.

**Future Work:**
- Create `strategy/shared/stop_loss_manager.py`
- Support multiple SL types: STOP, LIMIT, CONTINGENCY
- Strategies configure SL behavior via play data, manager handles execution

### 5. Conditional Orders -- OCO and OSO, aka OTO -- (DECIDED - Future Refactor)

**Decision:** Similar to trailing stops and contingency SL, refactor the OCO/OSO system to also be strategy-agnostic.

**Future Work:**
- Create `strategy/shared/conditional_order_manager.py`
- Support branching bracket orders where applicable (OCO, OSO) with peer OCO sets (with auto-reloading), etc.
- Strategies that support conditional orders will have the conditional triggers routed by the manager

### 6. Trade Direction Model (DECIDED - Implemented 2025-11-30)

**Decision:** Implement explicit trade direction support via `OrderAction` enum to handle both long (BTO/STC) and short (STO/BTC) strategies.

**Background:** Options trading has four fundamental order actions:

| Action | Full Name | Direction | Use Case |
|--------|-----------|-----------|----------|
| **BTO** | Buy to Open | Open Long | Buy calls/puts to profit from premium increase |
| **STC** | Sell to Close | Close Long | Exit long position by selling premium |
| **STO** | Sell to Open | Open Short | Sell/write options to collect premium |
| **BTC** | Buy to Close | Close Short | Exit short position by buying back |

**Implementation:**

1. **`OrderAction` enum** (`strategy/base.py`):
   ```python
   class OrderAction(Enum):
       BUY_TO_OPEN = "BTO"
       SELL_TO_CLOSE = "STC"
       SELL_TO_OPEN = "STO"
       BUY_TO_CLOSE = "BTC"
   ```
   - Includes helper methods: `is_buy()`, `is_sell()`, `is_long()`, `is_short()`
   - Conversion: `get_closing_action()`, `get_opening_action()`
   - Parsing: `from_string()` for play file compatibility

2. **`PositionSide` enum** (`strategy/base.py`):
   ```python
   class PositionSide(Enum):
       LONG = "long"
       SHORT = "short"
   ```

3. **BaseStrategy methods**:
   - `get_default_entry_action()` → Strategy's default entry action
   - `get_default_exit_action()` → Corresponding exit action
   - `get_entry_action_for_play(play)` → Per-play override support
   - `get_exit_action_for_play(play)` → Derives from entry action
   - `is_long_strategy()`, `is_short_strategy()` → Quick checks

4. **Strategy defaults**:
   - `OptionSwingsStrategy`: BTO → STC (long premium, default)
   - `MomentumStrategy`: BTO → STC (long premium, default)
   - `OptionSwingsAutoStrategy`: BTO → STC (long premium, default)
   - `SellPutsStrategy`: **STO → BTC** (short premium)
   - `SpreadsStrategy`: Multi-leg (each leg has own action)

5. **OrderExecutor updates** (`strategy/shared/order_executor.py`):
   - `create_entry_order(action=OrderAction)` - Accepts optional action
   - `create_exit_order(action=OrderAction)` - Accepts optional action
   - `order_action_to_side()` - Converts to Alpaca `OrderSide`
   - Defaults to BTO/STC for backward compatibility

6. **Multi-leg support** (`spreads.py`):
   - `SpreadType` enum for spread classification
   - `SpreadLeg` class with per-leg `OrderAction`
   - `is_credit_spread()`, `get_closing_legs()` helpers

**Play File Support:**

Plays can optionally specify action:
```json
{
  "symbol": "AAPL",
  "trade_type": "PUT",
  "action": "STO",        // Optional: override strategy default
  "entry_point": { ... }
}
```

If `action` is not specified, the strategy's default is used.

**P&L Implications:**

| Position | Profit When | Loss When |
|----------|-------------|-----------|
| Long (BTO) | Premium ↑ | Premium ↓ |
| Short (STO) | Premium ↓ or expires worthless | Premium ↑ |

**Risk Profiles:**

- **Long options**: Max loss = premium paid (limited risk)
- **Short options**: Max loss = varies (undefined for naked calls, strike-premium for puts)

---

## References

- Existing `core.py` (2,155 lines after Phase 2) - Now contains thin wrappers calling shared modules
- `strategy/shared/play_manager.py` (560 lines) - Play file operations
- `strategy/shared/evaluation.py` (538 lines) - TP/SL evaluation logic
- `strategy/shared/order_executor.py` (~550 lines) - Order placement with OrderAction support
- `strategy/base.py` - BaseStrategy ABC + OrderAction/PositionSide enums
- `data/market/manager.py` - Market data abstraction
- `config/settings.yaml` - Configuration schema
- `strategy/trailing.py` - Trailing stops implementation (future: refactor to shared)

---

## Handoff Prompt for Next AI Instance

```
CONTEXT: Goldflipper Multi-Strategy Implementation

We're adding multi-strategy support to an options trading system. Phases 1-5 are COMPLETE.
Trade Direction Model has been implemented (Phase 6 partial).

KEY FILES TO READ FIRST:
1. goldflipper/docs/MULTI_STRATEGY_IMPLEMENTATION.md - Full implementation plan (this file)
2. goldflipper/strategy/base.py - BaseStrategy abstract class (Phase 1)
3. goldflipper/strategy/orchestrator.py - StrategyOrchestrator (Phase 1)
4. goldflipper/strategy/registry.py - @register_strategy decorator (Phase 1)
5. goldflipper/strategy/shared/ - Extracted shared utilities (Phase 2)
   - play_manager.py - Play file operations (560 lines)
   - evaluation.py - TP/SL evaluation (538 lines)
   - order_executor.py - Order placement helpers (483 lines)
   - __init__.py - Complete exports
6. goldflipper/core.py - Now contains thin wrappers calling shared modules (Phase 2)
7. goldflipper/strategy/runners/ - Strategy runner implementations (Phase 4)
   - option_swings.py - Full implementation (~450 lines, BTO/STC)
   - option_swings_auto.py - Stub (BTO/STC long premium)
   - momentum.py - Stub (BTO/STC long premium)
   - sell_puts.py - Stub (STO/BTC short premium)
   - spreads.py - Stub with SpreadType/SpreadLeg multi-leg support

PHASE 1 COMPLETE (2025-11-29):
- BaseStrategy ABC with full interface (get_name, get_config_section, evaluate_new_plays, etc.)
- StrategyRegistry with @register_strategy decorator and auto-discovery
- StrategyOrchestrator with sequential/parallel execution modes
- Config section added (strategy_orchestration.enabled: false)

PHASE 2 COMPLETE (2025-11-30):
- strategy/shared/play_manager.py: PlayManager class + move/save functions
- strategy/shared/evaluation.py: evaluate_opening/closing + calc functions
- strategy/shared/order_executor.py: OrderExecutor class + order helpers
- core.py converted to thin wrappers (backward compatible)

PHASE 3 COMPLETE (2025-11-30):
- All config sections validated (added in Phase 1)
- strategy_orchestration, momentum, sell_puts, spreads, option_swings_auto all present
- All have enabled: false by default

PHASE 4 COMPLETE (2025-11-30):
- strategy/runners/option_swings.py: Full BaseStrategy implementation
  * evaluate_new_plays() - Entry condition evaluation
  * evaluate_open_plays() - Exit condition evaluation (TP/SL)
  * Delegates to shared modules for logic
  * Delegates to core.py for order execution (backward compat)
- strategy/runners/option_swings_auto.py: Stub (returns empty lists)
- strategy/runners/momentum.py: Full implementation with playbook-driven momentum types
- strategy/runners/sell_puts.py: Full TastyTrade-style implementation (STO/BTC)
- strategy/runners/spreads.py: Stub with multi-leg support
- All 5 strategies register correctly via StrategyRegistry.discover()

TRADE DIRECTION MODEL (2025-11-30):
- OrderAction enum: BTO, STC, STO, BTC (strategy/base.py)
- PositionSide enum: LONG, SHORT
- BaseStrategy: get_default_entry_action(), get_exit_action_for_play(), etc.
- Strategy defaults:
  * option_swings, momentum, option_swings_auto: BTO → STC (long)
  * sell_puts: STO → BTC (short)
  * spreads: Multi-leg (SpreadType, SpreadLeg classes)
- OrderExecutor: create_entry_order(action=), create_exit_order(action=)
- Play files can override via "action": "STO" field

CURRENT STATE:
- All infrastructure in place (Phases 1-5 complete)
- Trade Direction Model implemented (OrderAction, PositionSide enums)
- All strategy runners created with explicit order actions
- No breaking changes - existing system continues working
- strategy_orchestration.enabled: false means legacy mode
- Awaiting market hours for Phase 5 live testing

PHASE 5 COMPLETE (2025-11-30) - AWAITING MARKET TESTING:
- run_multi.py: Created as standalone orchestrated entry point
- run.py: Updated to use orchestrator when strategy_orchestration.enabled: true
- orchestrator._execute_strategy(): Now executes trades via strategy.open_position() / close_position()
- Handles expired plays, pending plays, and trade execution
- Falls back to legacy mode if orchestrator fails (when fallback_to_legacy: true)
- Both entry points start without errors (verified)

The orchestrator is now wired into both run.py and run_multi.py.
When strategy_orchestration.enabled: true:
1. Discovers and instantiates enabled strategies
2. Loads plays from appropriate directories  
3. Calls evaluate_new_plays() and evaluate_open_plays()
4. Executes open_position() / close_position() based on results
5. Handles expired plays and pending plays
6. Falls back to legacy mode if errors occur (configurable)

REMAINING PHASE 5 TESTING (requires market hours):
1. Test orchestrator with single strategy (option_swings enabled)
2. Test parallel execution mode
3. Verify play state transitions work correctly

PHASE 6 PROGRESS (2025-12-01):
- ✅ Playbook schema and loader implemented
- ✅ Strategy-specific play templates created
- ✅ sell_puts.py: Full TastyTrade-style implementation
- ✅ momentum.py: Full implementation with playbook-driven momentum types
  * Supports momentum_type: "gap", "squeeze", "ema_cross", "manual"
  * Gap momentum fully implemented (gap_move.yaml, gap_fade.yaml playbooks)
  * Squeeze/EMA cross are stubs for future implementation
- ✅ Play Creation Tools Updated (2025-12-01):
  * CSV Templates created:
    - reference/API_Template_2025_ShortPuts.csv - Short puts template
    - reference/API_Template_2025_MomentumGap.csv - Gap momentum template
  * Auto Play Creator (tools/auto_play_creator.py) updated:
    - Strategy selection menu (option_swings, momentum, sell_puts)
    - Playbook selection for momentum (gap_move, gap_fade, manual)
    - Gap detection via calculate_gap_info() using market data manager
    - Trade type auto-selection based on gap direction and playbook
    - Strategy-specific play creation methods
  * Multi-Strategy CSV Ingestion (tools/play_csv_ingestion_multi.py) created:
    - Auto-detects strategy from CSV content
    - Parses sell_puts and momentum CSV formats
    - Falls back to original ingestion for option_swings
    - Validates plays before saving
- 🔲 spreads.py: Still a stub (multi-leg infrastructure in place)
- 🔲 option_swings_auto.py: Still a stub (lower priority)

NEXT PRIORITIES:
1. **Market testing** - Test orchestrator with live market data:
   - Single strategy mode (option_swings)
   - Multiple strategies in parallel
   - Verify play state transitions
   - Test new play creation tools with real data
2. **Update Trade Logger** - Pull from all strategies/accounts, add GUI filtering
3. **Unit tests** - Test orchestrator and strategy logic without live market
4. **Implement spreads.py** - Multi-leg spread support (P4)
5. **Dry-run mode** (optional) - For testing when market is closed

PLAY CREATION TOOL REQUIREMENTS (for momentum/gap plays) - ✅ IMPLEMENTED:
- ✅ Detect pre-market gap using previous close vs current open/pre-market price
- ✅ Calculate gap_pct = ((current - previous_close) / previous_close) * 100
- ✅ Determine gap_type: "up" if positive, "down" if negative
- ✅ Set trade_direction based on selected playbook:
  * gap_move → "with_gap"
  * gap_fade → "fade_gap"
- ✅ Select appropriate option type (get_trade_type_for_gap()):
  * with_gap + gap up → CALL
  * with_gap + gap down → PUT
  * fade_gap + gap up → PUT
  * fade_gap + gap down → CALL
- ✅ Populate entry_point, take_profit, stop_loss from strategy defaults

NEW FILES CREATED:
- goldflipper/reference/API_Template_2025_ShortPuts.csv
- goldflipper/reference/API_Template_2025_MomentumGap.csv
- goldflipper/tools/play_csv_ingestion_multi.py

UPDATED FILES:
- goldflipper/tools/auto_play_creator.py (added multi-strategy support)
- goldflipper/trade_logging/trade_logger.py (multi-strategy support):
  * Added 'strategy' and 'action' columns to CSV schema
  * log_play() now extracts strategy/action from play data
  * get_unique_strategies() returns list of strategies in log
  * _create_summary_stats() accepts strategy_filter parameter
  * Excel export includes Strategy and Action columns
- goldflipper/trade_logging/trade_logger_ui.py (multi-strategy support):
  * Added Strategy Filter dropdown in Export Options
  * Summary stats filter by selected strategy
  * Strategy list updates on data refresh

BUG FIXES:
  * Config values (entry_buffer, take_profit_pct, stop_loss_pct) were read as strings from YAML
  * Added explicit float()/int() casts in __init__ (lines 58-73) for all numeric config values

KNOWN ISSUES:
- Linter error due to incomplete type annotations in alpaca-py library.

CRITICAL REQUIREMENTS:
- Make all changes NON-BREAKING until validated
- Existing system must continue working when orchestration disabled
- Test backward compatibility after each change
- Use fallback_to_legacy: true for safety during transition
- Only once the new system is confirmed working should the deprecated code be cleaned up.
```
