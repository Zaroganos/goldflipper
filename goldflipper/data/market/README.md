# Market Data System

## Overview

`MarketDataManager` is the single entry point for all market data in Goldflipper. It is provider-agnostic, cycle-cached, and supports automatic fallback across providers.

Active providers (configured in `settings.yaml → market_data_providers`):

| Priority | Provider | Notes |
|----------|----------|-------|
| 1 (primary) | MarketDataApp | Options chains, earnings dates |
| 2 (fallback) | Alpaca | Real-time quotes, bars |
| 3 (fallback) | YFinance | Historical data |

---

## MarketDataManager API

### Price & Quotes

```python
manager.get_stock_price(symbol)          # → float | None
manager.get_option_quote(contract)       # → dict | None
manager.get_previous_close(symbol)       # → float | None
```

`get_option_quote()` returns a dict with: `bid`, `ask`, `last`, `mid`, `premium`,
`delta`, `gamma`, `theta`, `vega`, `rho`, `implied_volatility`, `volume`, `open_interest`.

### Options Chain Data

```python
manager.get_option_expirations(symbol)   # → list[str] | None
manager.get_next_earnings_date(symbol)   # → date | None  (MarketDataApp only)
```

### OHLCV Bars

```python
manager.get_bars(symbol, interval='4h', lookback_days=10)
# → pd.DataFrame (OHLCV) | None
# interval examples: '1m', '5m', '15m', '1h', '4h', '1d'
# Results are cycle-cached with key: bars:{symbol}:{interval}:{lookback_days}d
```

### VWAP

```python
manager.get_vwap(symbol, interval='4h', lookback_days=5, num_bands=2)
# → dict | None
# Keys: vwap, std_dev, upper_1, lower_1, upper_2, lower_2  (all floats)
```

Internally calls `get_bars()` then `VWAPCalculator` (`data/indicators/vwap.py`).

### Volume Profile

```python
manager.get_volume_profile(symbol, interval='4h', lookback_days=10,
                            n_bins=24, value_area_pct=0.70)
# → VolumeProfileResult | None
```

`VolumeProfileResult` attributes: `poc`, `vah`, `val`, `total_volume`, `bins` (DataFrame),
and helpers: `price_in_value_area(price)`, `price_above_poc(price)`, `pct_from_poc(price)`,
`nearest_support(price, above=False)`.

### Cycle Management

```python
manager.start_new_cycle()   # Clears per-cycle cache
```

---

## Indicators (`data/indicators/`)

| Class | File | Purpose |
|-------|------|---------|
| `VWAPCalculator` | `vwap.py` | Cumulative VWAP + std-dev bands |
| `VolumeProfileCalculator` | `volume_profile.py` | POC / VAH / VAL from OHLCV bars |
| `EMACalculator` | `ema.py` | Exponential moving averages |
| `MACDCalculator` | `macd.py` | MACD line, signal, histogram |
| `TTMSqueezeCalculator` | `ttm_squeeze.py` | TTM Squeeze momentum indicator |

All extend `IndicatorCalculator` (base.py) and accept a `MarketData` dataclass.

`VWAPCalculator` extra helpers:
```python
calc.current_vwap()                  # → float | None
calc.current_std_dev()               # → float | None
calc.std_distance_from_vwap(price)   # → float
calc.price_above_vwap(price)         # → bool
```

---

## Greeks (`data/greeks/`)

### Black-Scholes Calculators

Standard BS calculators live in `data/greeks/` (delta, gamma, theta, vega, rho).
Use for theoretical values when you only have strike/spot/IV/DTE.

### Live GEX Analysis (`gamma_exposure.py`)

Uses real open-interest + gamma values from the option chain (not BS):

```python
from goldflipper.data.greeks.gamma_exposure import (
    GammaExposureAnalyzer,
    detect_delta_fade,
    detect_parabolic_move,
)

analyzer = GammaExposureAnalyzer(chain_df, spot_price=185.50)
analyzer.net_gex()            # → float  (call GEX − put GEX)
analyzer.near_spot_gex()      # → float  (GEX within ±2% of spot)
analyzer.is_gamma_squeeze()   # → bool   (near-spot GEX < 0)
analyzer.is_gamma_fade()      # → bool   (ATM gamma declining vs chain avg)
analyzer.full_report()        # → dict

# Standalone helpers
detect_delta_fade(current_delta, entry_delta, threshold=0.15)   # → bool
detect_parabolic_move(closes, vwap, std_dev, ...)               # → dict
```

`chain_df` must have columns: `strike`, `type` (call/put), `gamma`, `open_interest`.

---

## Market Condition Screening (`strategy/shared/market_conditions.py`)

Higher-level evaluators that combine market data with strategy logic.
All three return a `dict` with at minimum `{'passed': bool, 'reason': str}`.
All are **permissive on data errors** — missing data returns `passed=True` so
a data gap doesn't silently block all trades.

```python
from goldflipper.strategy.shared import (
    evaluate_vwap_condition,
    evaluate_volume_profile_condition,
    evaluate_greek_conditions,
)

# Usage in evaluate_new_plays():
vwap_cfg = playbook.option_swings_config.vwap.to_dict()
result = evaluate_vwap_condition(self.market_data, symbol, play, vwap_cfg)
if not result['passed']:
    continue  # skip play

vp_cfg = playbook.option_swings_config.volume_profile.to_dict()
result = evaluate_volume_profile_condition(self.market_data, symbol, play, vp_cfg)

greek_cfg = playbook.option_swings_config.greek_conditions.to_dict()
result = evaluate_greek_conditions(self.market_data, symbol, play, greek_cfg)
```

### Config key reference

**`evaluate_vwap_condition`** config keys:
- `enabled`, `interval`, `lookback_days`
- `require_price_above_vwap` — CALL entries must be above VWAP
- `require_price_below_vwap` — PUT entries must be below VWAP
- `proximity_pct` — price must be within ±N% of VWAP

**`evaluate_volume_profile_condition`** config keys:
- `enabled`, `interval`, `lookback_days`, `n_bins`, `value_area_pct`
- `require_in_value_area` — price must be between VAL and VAH
- `call_requires_above_poc` / `put_requires_below_poc`
- `poc_proximity_pct` — max % distance from POC

**`evaluate_greek_conditions`** config keys:
- `enabled`, `min_delta`, `max_delta`
- `check_gamma_squeeze` / `gamma_squeeze_blocks_entry`
- `check_gamma_fade` / `gamma_fade_blocks_entry`
- `check_delta_fade` / `delta_fade_threshold` / `delta_fade_is_exit_signal`
- `check_parabolic` / `parabolic_interval` / `parabolic_vwap_std` / `parabolic_min_consecutive` / `parabolic_blocks_entry`

---

## Playbook Schema Integration

Three dataclasses in `strategy/playbooks/schema.py` mirror the config keys above:

```python
VWAPConfig            # → vwap field on OptionSwingsConfig / MomentumConfig
VolumeProfileConfig   # → volume_profile field
GreekConditionsConfig # → greek_conditions field
```

All three are nested inside strategy-specific configs with `enabled: false` by default.
Enable and tune per playbook YAML under the `option_swings_config:` or `momentum_config:` block.

Parsing is handled automatically by `Playbook.from_dict()` which pops the nested keys
before the `**kwargs` expansion and constructs the sub-config objects explicitly.

---

## Caching

All `MarketDataManager` methods use `CycleCache` (in-memory, cleared each cycle).
Cache keys follow the pattern `{type}:{symbol}[:{interval}:{lookback}d]`.
Call `manager.start_new_cycle()` between cycles to flush.
