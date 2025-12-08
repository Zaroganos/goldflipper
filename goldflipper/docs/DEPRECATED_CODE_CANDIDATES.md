# Deprecated Code Candidates

**Document Created:** 2025-12-01  
**Last Updated:** 2025-12-06  
**Status:** ✅ MIGRATION COMPLETE - Legacy fallback removed  
**Related:** Phase 8 Cleanup

---

## Overview

This document identifies code in `core.py` that was a candidate for deprecation. The multi-strategy migration is now **complete** as of 2025-12-06.

### Completed Removal (2025-12-06)

The following legacy code has been removed:
- ✅ `monitor_plays_continuously()` - Legacy main loop removed from `core.py`
- ✅ `fallback_to_legacy` config option removed from `settings.yaml`
- ✅ Legacy code paths removed from `run.py` and `run_multi.py`
- ✅ `run_legacy_monitoring()` removed from `run_multi.py`
- ✅ `--force-legacy` CLI option removed

### Remaining Dead Code (Future Cleanup)

The following functions are now dead code but still exist in `core.py` for reference:
- `execute_trade()` - Was called only by `monitor_plays_continuously()`
- `monitor_and_manage_position()` - Was called only by `execute_trade()`
- `handle_api_error()` - Was always unused

These can be removed in a future cleanup pass.

---

## 1. Thin Wrappers (Phase 2 Extraction)

These functions were converted to thin wrappers during Phase 2. They delegate to `strategy/shared/` modules but are kept for backward compatibility.

### Play Management Wrappers

| Function | Lines | Delegates To | Import Users |
|----------|-------|--------------|--------------|
| `save_play()` | 272-278 | `_shared_save_play` | Many |
| `save_play_improved()` | 281-287 | `_shared_save_play_improved` | Many |
| `move_play_to_new()` | 1080-1086 | `_shared_move_to_new` | Many |
| `move_play_to_pending_opening()` | 1088-1095 | `_shared_move_to_pending_opening` | Many |
| `move_play_to_open()` | 1097-1103 | `_shared_move_to_open` | Many |
| `move_play_to_pending_closing()` | 1105-1112 | `_shared_move_to_pending_closing` | Many |
| `move_play_to_closed()` | 1114-1121 | `_shared_move_to_closed` | Many |
| `move_play_to_expired()` | 1123-1130 | `_shared_move_to_expired` | Many |
| `move_play_to_temp()` | 1132-1139 | `_shared_move_to_temp` | Many |

### Evaluation Wrappers

| Function | Lines | Delegates To |
|----------|-------|--------------|
| `calculate_and_store_premium_levels()` | 247-253 | `_shared_calc_premium_levels` |
| `calculate_and_store_price_levels()` | 255-261 | `_shared_calc_price_levels` |
| `evaluate_opening_strategy()` | 289-295 | `_shared_eval_opening` |
| `evaluate_closing_strategy()` | 297-326 | `_shared_eval_closing` |

### Utility Wrappers

| Class/Function | Lines | Delegates To |
|----------------|-------|--------------|
| `class UUIDEncoder` | 263-270 | Inherits `_SharedUUIDEncoder` |

**Deprecation Status:** Keep wrappers until all external imports updated to use `strategy.shared.*` directly.

---

## 2. Unused Functions

### `handle_api_error()`

```python
# Lines 1429-1442
def handle_api_error(e, operation):
    """Handle API errors with appropriate logging and display."""
    # NOTE: Currently unused; reserved for potential centralized API error handling.
```

**Status:** Marked as unused in code comments. Candidate for removal.

---

## 3. Legacy Mode Functions

These functions support the legacy (non-orchestrated) execution mode.

### `monitor_plays_continuously()`

```python
# Lines 1483-1663
def monitor_plays_continuously():
    """Main monitoring loop for all plays"""
```

**Purpose:** Legacy main loop used when `strategy_orchestration.enabled: false`

**Deprecation Path:**
1. Keep while `fallback_to_legacy: true` is recommended
2. Remove only after orchestrated mode is stable in production
3. Requires updating `run.py` to remove legacy fallback code

### `execute_trade()`

```python
# Lines 1146-1237
def execute_trade(play_file, play_type):
```

**Purpose:** Entry point for legacy trade execution. Called by `monitor_plays_continuously()`.

**Deprecation Path:** Remove with `monitor_plays_continuously()`

### `monitor_and_manage_position()`

```python
# Lines 924-1072
def monitor_and_manage_position(play, play_file):
```

**Purpose:** Legacy position monitoring. Called by `execute_trade()`.

**Deprecation Path:** Remove with `execute_trade()`

---

## 4. Functions Still Required

These functions are **NOT candidates for deprecation**:

### Brokerage Data Retrieval (Section 1)
- `get_order_info()` - Used by pending play management
- `get_position_info()` - Used by position verification
- `get_all_orders()` - Used by status checks
- `get_all_positions()` - Used by status checks

### Market Data Retrieval (Section 2)
- `get_market_data_manager()` - Singleton accessor, widely used
- `get_stock_price()` - Passed to evaluation functions
- `get_option_data()` - Passed to evaluation functions

### Order Placement (Section 4)
- `get_option_contract()` - Used by `open_position()`
- `open_position()` - Called by `OptionSwingsStrategy.open_position()`
- `close_position()` - Called by `OptionSwingsStrategy.close_position()`

### Trade Execution Support
- `validate_play_order_types()` - Used by order validation

### Time/Market Management (Section 7)
- `get_sleep_interval()` - Used by monitoring loops
- `validate_market_hours()` - Used by both legacy and orchestrated modes
- `handle_execution_error()` - Used for retry logic
- `is_market_holiday()` - Used by market hours validation

### Ancillary (Section 8)
- `verify_position_exists()` - Used by conditional play handling
- `handle_conditional_plays()` - OCO/OTO support
- `reload_oco_peers()` - OCO reload support
- `validate_bid_price()` - Order validation
- `handle_end_of_day_pending_plays()` - EOD cleanup
- `manage_pending_plays()` - Pending order management

---

## Migration Checklist

Before removing deprecated code:

- [ ] `strategy_orchestration.enabled: true` has run in production for 2+ weeks
- [ ] `fallback_to_legacy: false` has run in production for 1+ week
- [ ] All 5 strategies tested in orchestrated mode
- [ ] Parallel execution mode validated
- [ ] No fallback to legacy mode observed in production logs
- [ ] All tests passing with orchestrated mode
- [ ] External tools updated to use `strategy.shared.*` imports

---

## Recommended Deprecation Order

1. **Phase 8a (Safe):** Remove `handle_api_error()` - marked unused
2. **Phase 8b (After validation):** Update external imports to use `strategy.shared.*`
3. **Phase 8c (Final):** Remove thin wrappers from `core.py`
4. **Phase 8d (Last):** Remove legacy mode functions (`monitor_plays_continuously`, `execute_trade`, `monitor_and_manage_position`)

---

## Code Stats

| Category | Count | Lines |
|----------|-------|-------|
| Thin wrappers | 14 | ~100 |
| Unused functions | 1 | ~15 |
| Legacy mode | 3 | ~300 |
| **Total candidate lines** | **18** | **~415** |
| **core.py total** | - | **2155** |
| **Potential reduction** | - | **~19%** |

---

## Notes

- `core.py` went from being the main module to a compatibility layer in Phase 2
- New code should import from `strategy.shared.*` directly
- Strategy runners call back to `core.py` for `open_position()` and `close_position()` (intentional for backward compat)
- The thin wrappers allow existing external tools to continue working unchanged
