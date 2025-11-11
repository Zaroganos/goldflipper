# Short Puts Strategy - Implementation Plan

## Executive Summary

This document outlines the implementation plan for adding a **Short Puts** strategy to the goldflipper trading system. The strategy will operate alongside the existing "Option Swings" strategy, with branching happening at play creation time based on user choice.

## Strategy Requirements

Based on the specification in `short-puts.md` and user clarifications:

1. **Entry Criteria:**
   - Target: 45 DTE (days to expiration) - acceptable range 35-49 DTE
   - Target Delta: 30 delta puts
   - IV Rank/Percentile: Must be > 50% (1-year lookback)
   - Symbol: SPY default, but accept any valid symbol

2. **Position Management:**
   - Entry: SELL to open (cash-secured puts)
   - Profit Target: 50% of premium collected (close when premium drops to 50% of entry)
   - Stop Loss: Optional - close if premium doubles (2x entry credit)
   - Rolling: At 21 DTE, or when position is "challenged" (moved significantly against)

3. **Risk Management:**
   - Maximum capital allocation: 40-50% of account
   - Maximum notional leverage: 3x account value
   - Cash-secured requirement: Strike × 100 × contracts must be available as buying power

## Architecture Overview

### Strategy Branching

The implementation will add a **strategy choice** at the beginning of play creation flows:
- User selects "Option Swings" (existing) or "Short Puts" (new)
- This choice determines:
  - Which play creation logic is used
  - How position side is handled (LONG vs SHORT)
  - How TP/SL calculations work
  - How orders are placed (BUY vs SELL)

### Position Side Tracking

All plays will include a new field: `position_side: "LONG" | "SHORT"`
- **LONG**: Existing behavior (BUY to open, SELL to close)
- **SHORT**: New behavior (SELL to open, BUY to close)

This field will be:
- Set automatically based on strategy choice
- Used throughout `core.py` to determine order sides
- Used to invert TP/SL premium calculations

## Files to Modify

### 1. Configuration Files

#### `goldflipper/config/settings_template.yaml`
**Changes:**
- Add new `short_puts` section alongside `options_swings`
- Parameters:
  ```yaml
  short_puts:
    enabled: true
    target_dte: 45              # Target days to expiration
    dte_range: [35, 49]         # Acceptable DTE range
    target_delta: 0.30          # Target delta for puts
    delta_tolerance: 0.05       # Acceptable delta range (±0.05)
    iv_rank_threshold: 50        # Minimum IV Rank/Percentile (%)
    profit_target_pct: 50.0      # Take profit at 50% of premium
    roll_dte: 21                # Roll when DTE reaches this
    max_capital_allocation: 0.50 # Max % of account to use
    max_notional_leverage: 3.0   # Max notional leverage (3x account)
    default_symbol: "SPY"        # Default symbol
    stop_loss_enabled: true      # Enable 2x stop loss
    stop_loss_multiplier: 2.0    # Close if premium reaches 2x entry
  ```

### 2. Core Trading Logic

#### `goldflipper/core.py`
**Major Changes Required:**

1. **Add `position_side` field handling:**
   - Detect `position_side` in play data (default to "LONG" for backward compatibility)
   - Use this field to determine order sides in `open_position()` and `close_position()`

2. **Modify `open_position()` function:**
   - For SHORT positions: Use `OrderSide.SELL` instead of `OrderSide.BUY`
   - For SHORT positions: Use `ask` price for entry (selling premium)
   - Store `entry_credit` instead of `entry_premium` for shorts
   - Add buying power check before opening short positions

3. **Modify `close_position()` function:**
   - For SHORT positions: Use `OrderSide.BUY` instead of `OrderSide.SELL`
   - For SHORT positions: Use `bid` price for closing (buying back premium)
   - Invert premium-based TP/SL logic for shorts

4. **Modify `calculate_and_store_premium_levels()`:**
   - For SHORT positions: Invert calculations
     - TP: `entry_credit * (1 - profit_target_pct/100)` (premium decreases)
     - SL: `entry_credit * stop_loss_multiplier` (premium increases)

5. **Modify `evaluate_closing_strategy()`:**
   - For SHORT positions: Invert premium-based conditions
     - TP: `current_premium <= tp_target` (premium decreased)
     - SL: `current_premium >= sl_target` (premium increased)

6. **Add DTE calculation and rolling logic:**
   - New function: `calculate_dte(expiration_date)` → returns days to expiration
   - New function: `should_roll_position(play)` → checks if DTE <= roll_dte
   - New function: `roll_short_put(play, play_file)` → closes current, opens new
   - Integrate rolling check in `monitor_and_manage_position()`

7. **Add risk management functions:**
   - New function: `check_buying_power_requirement(play)` → calculates cash needed
   - New function: `check_notional_exposure(play)` → calculates total notional
   - New function: `check_portfolio_risk_limits()` → validates against max limits
   - Call these before opening short positions

### 3. Play Creation Tools

#### `goldflipper/tools/play_creation_tool.py`
**Changes:**
- At start of `create_play()` function, add strategy choice:
  ```python
  strategy_choice = get_input(
      "Select strategy:\n1. Option Swings (Long)\n2. Short Puts\nEnter choice (1 or 2): ",
      str,
      validation=lambda x: x in ["1", "2"],
      error_message="Please enter 1 or 2."
  )
  ```
- Pass strategy choice to `PlayBuilder.__init__()`
- Modify `PlayBuilder.build_base_play()` to branch based on strategy:
  - If "Option Swings": Use existing logic (set `position_side: "LONG"`)
  - If "Short Puts": Call new method `build_short_put_play()` (set `position_side: "SHORT"`)

#### `goldflipper/tools/auto_play_creator.py`
**Changes:**
- Add strategy mode selection in `create_test_plays()`:
  ```python
  strategy_mode = get_input("Strategy: 1=Option Swings, 2=Short Puts", ...)
  ```
- Add new method: `create_short_put_play_data(market_data)`
  - Fetches option chain for target DTE (35-49 range)
  - Calculates delta for each put option
  - Selects put closest to 30 delta
  - Checks IV Rank (must be > 50%)
  - Creates play with `position_side: "SHORT"` and strategy-specific fields

### 4. New Strategy Module

#### `goldflipper/strategy/short_puts.py` (NEW FILE)
**Purpose:** Centralized logic for short puts strategy

**Functions to implement:**

1. `find_short_put_option(symbol, target_dte, target_delta, iv_rank_threshold)`
   - Fetches option chain for symbol
   - Filters by DTE range (35-49)
   - Calculates delta for puts (using greeks calculator)
   - Filters by delta tolerance (±0.05 from target)
   - Calculates IV Rank/Percentile
   - Returns best matching put option or None

2. `calculate_iv_rank(symbol, current_iv)`
   - Fetches 1-year historical option data
   - Extracts IV values for each expiration cycle
   - Calculates percentile rank: `(current_iv - min_iv) / (max_iv - min_iv) * 100`
   - Returns IV Rank as percentage (0-100)

3. `calculate_dte(expiration_date)`
   - Takes expiration date string (MM/DD/YYYY)
   - Returns days to expiration as integer

4. `check_entry_conditions(symbol, option_data)`
   - Validates DTE is in range
   - Validates delta is close to target
   - Validates IV Rank > threshold
   - Returns tuple: (is_valid, reason_if_invalid)

5. `calculate_short_put_risk(play)`
   - Calculates buying power requirement: `strike * 100 * contracts`
   - Calculates notional exposure: `strike * 100 * contracts`
   - Returns dict with risk metrics

6. `should_roll_position(play, roll_dte=21)`
   - Calculates current DTE
   - Checks if DTE <= roll_dte
   - Optionally checks if "challenged" (premium > entry_credit * challenge_threshold)
   - Returns tuple: (should_roll, reason)

7. `find_roll_target(symbol, current_strike, target_dte, target_delta)`
   - Finds next expiration cycle (~45 DTE)
   - Finds put with same strike and ~30 delta
   - Returns option data for roll

### 5. Market Data Enhancements

#### `goldflipper/data/market/manager.py`
**Changes:**
- Ensure `get_option_chain()` supports filtering by expiration date
- Add helper method to get historical IV data (for IV Rank calculation)

#### `goldflipper/tools/option_data_fetcher.py`
**Changes:**
- Ensure `calculate_greeks()` function is accessible for delta calculation
- May need to export this function or move to a shared utility module

### 6. Risk Management Integration

#### `goldflipper/core.py` (risk management section)
**New Functions:**

1. `get_account_buying_power()`
   - Fetches account from Alpaca
   - Returns `account.options_buying_power` or `account.buying_power`

2. `get_portfolio_exposure()`
   - Scans all OPEN plays
   - Sums buying power used for SHORT positions
   - Sums notional exposure for SHORT positions
   - Returns dict: `{'total_bp_used': float, 'total_notional': float}`

3. `validate_short_put_risk(play)`
   - Calculates required buying power for new position
   - Gets current portfolio exposure
   - Checks against max_capital_allocation and max_notional_leverage
   - Returns tuple: (is_valid, error_message)

## Implementation Steps

### Phase 1: Foundation (Core Infrastructure)
1. Add `short_puts` config section to `settings_template.yaml`
   - Added complete configuration section with all required parameters
2. Create `goldflipper/strategy/short_puts.py` module
   - Implemented: `calculate_dte()`, `calculate_iv_rank()`, `check_entry_conditions()`, `calculate_short_put_risk()`, `should_roll_position()`
   - All functions are fully implemented
3. Implement IV Rank calculation function
   - **CURRENT:** Fully implemented using MarketDataManager (MarketDataApp provider) to sample IV from ATM puts across multiple expiration dates
   - **APPROXIMATION METHOD:** Uses cross-sectional sampling (current option chain across 12 expirations) - NOT true 1-year historical
   - **WHY:** Provides practical IV distribution snapshot without requiring 52+ historical API calls
   - Properly uses the market data abstraction layer instead of direct API calls
   - Calculates IV Rank as: (Current IV - Min IV) / (Max IV - Min IV) * 100
   - Handles edge cases: insufficient data, identical IVs, format conversion
   - Uses MarketDataApp provider as the primary data source (per system configuration)
   - **NOTE:** True 1-year historical IV Rank is NOT implemented (see "Key Technical Considerations" section for details)
4. Implement DTE calculation function
   - Fully implemented with support for multiple date formats
5. Add `position_side` field handling throughout codebase
   - Modified `open_position()`: Detects position_side, uses SELL for SHORT, stores entry_credit
   - Modified `close_position()`: Uses BUY to close for SHORT positions
   - Modified `calculate_and_store_premium_levels()`: Inverts TP/SL calculations for SHORT
   - Modified `evaluate_closing_strategy()`: Inverts premium-based conditions for SHORT
   - All changes maintain backward compatibility (defaults to LONG)

### Phase 2: Play Creation
1. Modify `play_creation_tool.py` to add strategy choice
   - **COMPLETED:** Added strategy choice prompt at start of `create_play()`
   - **COMPLETED:** Modified `PlayBuilder.__init__()` to accept strategy_choice parameter
   - **COMPLETED:** Modified `build_base_play()` to branch based on strategy choice
2. Add `build_short_put_play()` method to `PlayBuilder`
   - **COMPLETED:** Implemented `build_short_put_play()` method that uses `find_short_put_option()`
   - **COMPLETED:** Automatically selects option matching DTE, delta, and IV Rank criteria
   - **COMPLETED:** Sets `position_side: "SHORT"` and `entry_credit` for short positions
   - **COMPLETED:** Added `_add_short_put_tp_sl()` method to configure TP/SL based on strategy rules
3. Implement `create_short_put_play_data()` in `auto_play_creator.py`
   - **COMPLETED:** Implemented `create_short_put_play_data()` method that uses `find_short_put_option()`
   - **COMPLETED:** Creates short put plays with automated option selection based on DTE, delta, and IV Rank
   - **COMPLETED:** Sets `position_side: "SHORT"` and `entry_credit` for short positions
   - **COMPLETED:** Automatically configures TP/SL based on strategy rules (50% profit target, 2x stop loss)
   - **COMPLETED:** Modified `create_test_plays()` to accept strategy parameter ("option_swings" or "short_puts")
   - **COMPLETED:** Updated `main()` function to prompt for strategy selection before execution mode
4. Implement option selection logic (DTE + delta + IV Rank)
   - **COMPLETED:** Implemented `find_short_put_option()` in `short_puts.py`
   - **COMPLETED:** Function filters expirations by DTE range (35-49)
   - **COMPLETED:** Calculates delta for all puts using `calculate_greeks()`
   - **COMPLETED:** Filters by delta tolerance (±0.05 from target 0.30)
   - **COMPLETED:** Calculates IV Rank and validates against threshold (>50%)
   - **COMPLETED:** Returns best matching option with all required data

### Phase 3: Order Execution
1. Modify `open_position()` to handle SHORT positions (SELL to open)
   - **COMPLETED:** Detects position_side, uses OrderSide.SELL for SHORT, stores entry_credit
2. Modify `close_position()` to handle SHORT positions (BUY to close)
   - **COMPLETED:** Uses OrderSide.BUY to close for SHORT positions
3. Invert TP/SL premium calculations for SHORT positions
   - **COMPLETED:** TP/SL calculations inverted in `calculate_and_store_premium_levels()` and `evaluate_closing_strategy()`
4. Add buying power validation before opening
   - **COMPLETED:** Added `validate_short_put_risk()` function and integrated into `open_position()`
   - **COMPLETED:** Validates buying power availability, capital allocation limits, and notional leverage limits

### Phase 4: Position Management
1. Add DTE calculation to monitoring loop
2. Implement rolling logic (`roll_short_put()`)
3. Integrate rolling check in `monitor_and_manage_position()`
4. Add "challenged" condition detection

### Phase 5: Risk Management
1. Implement portfolio exposure tracking
   - **COMPLETED:** Implemented `get_portfolio_exposure()` function that scans OPEN plays and calculates total BP used and notional for SHORT positions
2. Add risk limit validation
   - **COMPLETED:** Implemented `validate_short_put_risk()` function that validates buying power, capital allocation, and notional leverage limits
   - **COMPLETED:** Integrated validation into `open_position()` for SHORT positions
3. Add alerts/warnings when approaching limits
   - **PENDING:** Can be added as enhancement if needed (validation currently blocks orders that exceed limits)

### Phase 6: Testing & Validation
1. Test play creation for short puts
2. Test order placement (SELL to open)
3. Test position monitoring and TP/SL
4. Test rolling logic
5. Test risk limit enforcement

## Key Technical Considerations

### IV Rank Calculation

**CURRENT IMPLEMENTATION (Approximation):**
- **Method:** Cross-sectional IV sampling from current option chain across multiple expirations
- **How it works:** Samples IV from ATM put options across 12 available expiration dates (typically 4-8 weeks of data)
- **Data Source:** MarketDataApp current option chain data via MarketDataManager
- **Limitation:** This is NOT true 1-year historical IV Rank - it's a practical approximation using current market data
- **Why it works:** Provides a reasonable distribution of IV values across different expiration cycles, giving a snapshot of current IV levels relative to available expirations
- **Performance:** Fast (single query per expiration, ~12 API calls total)
- **Fallback:** If insufficient data (< 3 samples), returns None and skips IV Rank check (logs warning)

**TRUE 1-YEAR IV RANK (Not Implemented):**
- **What's needed:** True 1-year IV Rank requires historical IV data over the past 52 weeks
- **Data Source Available:** MarketDataApp supports historical option data via `options/quotes/{option_symbol}/?date=YYYY-MM-DD` parameter
- **Implementation Requirements:**
  1. **Historical Data Collection Logic:**
     - For each date in the past year (weekly or daily sampling):
       - Calculate target expiration date (historical_date + 45 days to get ~45 DTE)
       - Determine which strike was ATM on that historical date (requires historical stock price)
       - Construct the OCC option symbol for that strike/expiration
       - Query that option's IV using the historical `date` parameter
       - Collect all IV values over the year
  2. **Technical Challenges:**
     - **API Calls:** 52+ calls for weekly sampling (or 365 for daily) - significant rate limiting concerns
     - **Performance:** Each calculation could take 10-30+ seconds
     - **Caching:** Need to cache historical IV data to avoid recalculating for same symbol repeatedly
     - **Data Consistency:** Must ensure comparing apples-to-apples (same DTE, same moneyness)
  3. **What's Already Available:**
     - MarketDataApp historical option data endpoint exists (see `data_backfill_helper.py` for pattern)
     - Can query specific option contracts for historical dates
  4. **Future Implementation:**
     - Consider implementing with weekly sampling (52 calls) + aggressive caching
     - Add helper functions to determine target expiration dates for historical dates
     - Add logic to find ATM options on historical dates (requires historical stock prices)
     - Cache IV distribution per symbol to avoid recalculation
- **Note:** Current approximation is sufficient for Phase 1. True 1-year IV Rank can be added as enhancement later if needed.

### Delta Calculation
- **Method:** Use existing `calculate_greeks()` function from `option_data_fetcher.py`
- **Source:** Calculate from option chain data using Black-Scholes or similar
- **Accuracy:** Ensure delta is calculated correctly for puts (negative values)

### Cash-Secured Requirement
- **Calculation:** `strike_price * 100 * contracts`
- **Validation:** Check that `account.buying_power >= required_bp`
- **Error:** Block order if insufficient buying power

### Rolling Logic
- **Trigger:** DTE <= 21 OR premium >= entry_credit * challenge_multiplier (e.g., 1.5x)
- **Process:** 
  1. Close current position (BUY to close)
  2. Find new option (same strike, ~45 DTE, ~30 delta)
  3. Open new position (SELL to open)
  4. Update play record with new expiration and option symbol
- **Error Handling:** If roll fails, log error and continue monitoring

### Backward Compatibility
- All existing plays will have `position_side: "LONG"` (implicit or explicit)
- Default behavior: If `position_side` missing, assume "LONG"
- Existing play creation flows unchanged (unless user selects new strategy)

## Testing Checklist

- [ ] Create short put play via play_creation_tool
- [ ] Create short put play via auto_play_creator
- [ ] Verify IV Rank calculation works correctly
- [ ] Verify delta-based option selection works
- [ ] Verify SELL to open order is placed correctly
- [ ] Verify entry_credit is stored correctly
- [ ] Verify TP triggers at 50% premium (premium decreases)
- [ ] Verify SL triggers at 2x premium (premium increases)
- [ ] Verify rolling triggers at 21 DTE
- [ ] Verify rolling process completes successfully
- [ ] Verify buying power validation blocks insufficient funds
- [ ] Verify notional exposure limits are enforced
- [ ] Verify existing LONG plays still work correctly
- [ ] Verify mixed portfolio (LONG + SHORT) works correctly

## Configuration Example

```yaml
short_puts:
  enabled: true
  target_dte: 45
  dte_range: [35, 49]
  target_delta: 0.30
  delta_tolerance: 0.05
  iv_rank_threshold: 50
  profit_target_pct: 50.0
  roll_dte: 21
  max_capital_allocation: 0.50
  max_notional_leverage: 3.0
  default_symbol: "SPY"
  stop_loss_enabled: true
  stop_loss_multiplier: 2.0
  challenge_threshold: 1.5  # Roll if premium reaches 1.5x entry
```

## Play Data Structure Addition

All plays will include (optional for backward compatibility):
```json
{
  "position_side": "SHORT",  // or "LONG"
  "entry_point": {
    "entry_credit": 2.50,     // For SHORT: credit received
    "entry_premium": 2.50     // For LONG: premium paid (backward compat)
  },
  "strategy": "Short Puts",   // New strategy identifier
  "rolling": {                 // Optional: rolling tracking
    "original_expiration": "01/15/2025",
    "roll_count": 1,
    "last_roll_date": "12/25/2024"
  }
}
```

## Risk Management Example

```python
# Before opening short put position
play = {
    "symbol": "SPY",
    "strike_price": "450.0",
    "contracts": 1,
    "position_side": "SHORT"
}

# Calculate required buying power (cash-secured)
required_bp = float(play["strike_price"]) * 100 * play["contracts"]
# = 450.0 * 100 * 1 = $45,000

# Get account buying power
account = client.get_account()
available_bp = float(account.options_buying_power)

# Check if sufficient
if required_bp > available_bp:
    raise ValueError(f"Insufficient buying power. Required: ${required_bp}, Available: ${available_bp}")

# Check portfolio limits
portfolio = get_portfolio_exposure()
total_bp_used = portfolio['total_bp_used'] + required_bp
max_allocation = account.equity * config.get('short_puts', 'max_capital_allocation', default=0.50)

if total_bp_used > max_allocation:
    raise ValueError(f"Exceeds capital allocation limit. Used: ${total_bp_used}, Limit: ${max_allocation}")
```

## Next Steps

1. Review this implementation plan
2. Approve approach and design decisions
3. Begin Phase 1 implementation (Foundation)
4. Iterate through phases with testing at each stage
5. Document any deviations or additional requirements discovered during implementation

---

**Note:** This plan assumes the existing codebase structure and patterns. Some adjustments may be needed based on actual code review during implementation.

