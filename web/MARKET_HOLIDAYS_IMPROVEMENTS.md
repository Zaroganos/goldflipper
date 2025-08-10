# Market Holiday Detection Improvements

## Overview
This document tracks improvements made to the Weekly Expected Moves (WEM) system to handle market holidays correctly.

## Problem Statement
The original WEM system calculated option expiration dates by simply finding the next Friday. However, when Friday is a market holiday (like July 4th, 2025), weekly options actually expire on the preceding Thursday instead.

## Solution Implemented

### 1. Market Holiday Detection System
- **Location**: `goldflipper/utils/market_holidays.py`
- **Features**:
  - Detects major US market holidays (New Year's, MLK Day, Presidents' Day, Good Friday, Memorial Day, Juneteenth, Independence Day, Labor Day, Thanksgiving, Christmas)
  - Handles weekend adjustments (when holidays fall on weekends)
  - Supports next Friday expiration date calculation with holiday awareness
  - Provides fallback expiration date candidates when primary date is unavailable

### 2. Smart Expiration Date Handling
- **Functions**:
  - `find_next_friday_expiration()` - Returns holiday-adjusted expiration date
  - `get_expiration_date_candidates()` - Provides ordered list of fallback dates
  - `is_market_holiday()` - Core holiday detection logic

### 3. WEM Integration
- **Location**: `goldflipper/web/pages/6_📊_WEM.py`
- **Changes**:
  - Uses holiday-aware expiration date calculation
  - Tries multiple expiration dates if primary date fails
  - Logs all holiday adjustments for transparency
  - Shows actual vs calculated expiration dates in results

### 4. Debug Tools and Testing
- **Location**: `goldflipper/utils/market_holidays.py` - `test_holiday_detection_ui()`
- **Features**:
  - Interactive Streamlit UI for testing holiday detection
  - **Debug Mode Only**: Test button only appears when `settings.yaml` has `logging.debug.enabled: true`
  - Validates specific cases like July 4th, 2025 (Friday → Thursday)
  - Shows next Friday calculation with holiday adjustments
  - **Code Organization**: Moved from WEM page to utility module for better separation of concerns

## Code Organization Improvements

### Holiday Detection Cleanup (Latest Update)
- **Moved** all holiday detection test UI code from WEM page to `utils/market_holidays.py`
- **Added** debug mode requirement for test button visibility
- **Improved** code separation - WEM page now focuses on core functionality
- **Enhanced** test functionality with additional expiration date validation

### File Structure
```
goldflipper/
├── utils/
│   └── market_holidays.py         # Core holiday detection + test UI
└── web/
    └── pages/
        └── 6_📊_WEM.py            # Clean WEM interface (test button only in debug mode)
```

## Testing the Implementation

### Manual Testing
1. **Enable Debug Mode**: Set `logging.debug.enabled: true` in `settings.yaml`
2. **Access Test Button**: Navigate to WEM page sidebar → Debug Tools section
3. **Run Holiday Test**: Click "🧪 Test Holiday Detection" button
4. **Verify Results**: Check July 4th, 2025 detection and expiration adjustments

### Automated Testing
```python
from goldflipper.utils.market_holidays import is_market_holiday, find_next_friday_expiration
from datetime import datetime

# Test July 4th, 2025 detection
july_4_2025 = datetime(2025, 7, 4).date()
assert is_market_holiday(july_4_2025), "July 4th, 2025 should be detected as holiday"

# Test expiration adjustment
next_friday = find_next_friday_expiration()
print(f"Next Friday expiration: {next_friday}")
```

## Future Enhancements

### Pandas Market Calendars Migration
- **Library**: `pandas-market-calendars`
- **Benefits**: More comprehensive holiday coverage, international markets, partial trading days
- **Installation**: `pip install pandas-market-calendars`
- **Implementation Example**:
```python
import pandas_market_calendars as mcal
nyse = mcal.get_calendar('NYSE')
is_holiday = not nyse.valid_days(start_date, end_date).empty
```

### Additional Features
- Support for international market holidays
- Early market close detection (e.g., day before holidays)
- Options expiration calendar API integration
- More sophisticated fallback logic for rare edge cases

---

## Expiration Source Selection Improvements (Latest Update)

### 5. Provider‑Guided Expiration Selection
- **Goal**: Choose the correct options expiration date per underlying using a data provider’s actual listings, rather than assuming “next Friday” (which breaks on holidays and product exceptions).
- **What changed**:
  - Added provider capability `get_available_expirations(symbol)` to list expirations.
    - **Location**: `goldflipper/data/market/providers/base.py` (abstract method)
    - Implemented first for `yfinance`:
      - **Location**: `goldflipper/data/market/providers/yfinance_provider.py`
      - Returns `Ticker(symbol).options` (YYYY‑MM‑DD strings)
  - Added manager entrypoint to aggregate/select expirations:
    - **Location**: `goldflipper/data/market/manager.py` → `get_available_expirations(symbol)`
    - Uses configured provider first; can fallback per existing provider fallback order
  - Introduced configuration key to select provider for expirations:
    - **Location**: `goldflipper/config/settings_template.yaml`
    - `market_data_providers.expiration_provider: "yfinance"` (default)

### 6. WEM Runtime Behavior Update
- **Location**: `web/pages/6_📊_WEM.py`
- **Now WEM does**:
  1. Queries configured provider for available expirations for the symbol.
  2. Computes a calendar‑guided reference next Friday (holiday‑aware via market calendar).
  3. Picks the earliest provider expiration on/after that reference date.
  4. Fetches the option chain for that chosen expiration.
  5. If provider expirations aren’t available, falls back to holiday‑aware next Friday and the existing multi‑date retry logic.

This removes the previous guessing/blind fallback and significantly reduces occasional Delta‑16 mismatches caused by fetching the wrong expiration.

### 7. Market Calendar Upgrade with pandas_market_calendars
- **Location**: `goldflipper/utils/market_holidays.py`
- **Behavior**:
  - If `pandas_market_calendars` is available, the system uses NYSE (`XNYS`) schedule to identify the next Friday trading day precisely (early closes/holidays included).
  - Otherwise, it falls back to the lightweight in‑house holiday logic.
- **Reference**: [pandas_market_calendars](https://github.com/rsheftel/pandas_market_calendars)

### 8. Configuration
- `market_data_providers.primary_provider`: unchanged (still controls primary data source)
- `market_data_providers.expiration_provider`: NEW; controls which provider supplies expiration lists. Default: `yfinance`.

### 9. Current State
- **Holiday handling**: Robust; holiday‑aware next Friday with `pandas_market_calendars` upgrade when available; existing fallback candidate dates retained.
- **Expiration selection**: Provider‑guided via `yfinance` by default, with fallback to calendar logic.
- **Delta‑16 accuracy**: Improved by aligning the chain’s expiration to actual available listings before selection.
- **Backwards compatibility**: If expiration lists aren’t available, previous behavior remains with better logging.

### 10. Next Steps / To‑Do
- Implement `get_available_expirations(symbol)` for other providers (MarketData.app, Alpaca) to broaden choices and resilience.
- Ensure provider chain payloads include an explicit `expiration` column everywhere and verify it matches the selected date at runtime.
- Consider hardening Delta selection using absolute delta closeness per side (already side‑separated) to guard against provider delta sign anomalies.
- Optionally expose WEM UI control to choose the expiration provider.

## Validation Results

### July 4th, 2025 Test Case
- **Date**: Friday, July 4th, 2025
- **Expected**: Market holiday detected
- **Actual**: ✅ Correctly detected as holiday
- **Adjustment**: Options expire Thursday, July 3rd, 2025
- **WEM Impact**: System automatically uses Thursday expiration date

### Other Holiday Tests
- **Christmas**: Properly handled when falls on weekday
- **New Year's**: Weekend adjustment logic working
- **Memorial Day**: Last Monday calculation correct
- **Good Friday**: Easter-based calculation accurate

## Performance Impact
- **Minimal**: Holiday detection adds <1ms to expiration calculations
- **Caching**: Not needed for simple date calculations
- **Memory**: No significant impact from holiday list storage
- **API Calls**: No additional external API calls required

## Error Handling
- **Graceful Degradation**: Falls back to regular Friday if holiday detection fails
- **Logging**: All adjustments and errors logged for debugging
- **User Feedback**: Clear UI messages about any expiration date changes
- **Validation**: Multiple fallback dates tried before giving up

## Debug Mode Configuration
To enable debug tools and holiday testing interface:

```yaml
# settings.yaml
logging:
  debug:
    enabled: true  # Set to true to show debug tools in WEM interface
```

When debug mode is enabled, the WEM sidebar will show a "🔧 Debug Tools" section with the holiday detection test button. 