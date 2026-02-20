"""
VWAP (Volume Weighted Average Price) Indicator

Calculates anchored session VWAP and standard deviation bands from
OHLCV bar data. Follows the IndicatorCalculator base-class pattern.

Typical price (TP) = (High + Low + Close) / 3
VWAP = Σ(TP × Volume) / Σ(Volume)   [cumulative over session]

Standard deviation bands expand by ±1σ, ±2σ, … from VWAP using a
volume-weighted variance:
    var = Σ((TP − VWAP)² × Volume) / Σ(Volume)

Usage:
    from goldflipper.data.indicators.vwap import VWAPCalculator
    from goldflipper.data.indicators.base import MarketData

    md = MarketData(high=df['high'], low=df['low'],
                    close=df['close'], volume=df['volume'])
    calc = VWAPCalculator(md, num_bands=2)
    result = calc.calculate()
    # result['vwap']     → pd.Series of VWAP values
    # result['upper_1']  → +1σ band
    # result['lower_2']  → −2σ band
    current_vwap = calc.current_vwap()
    std_distance = calc.std_distance_from_vwap(price)
"""

import pandas as pd

from .base import IndicatorCalculator, MarketData


class VWAPCalculator(IndicatorCalculator):
    """
    Anchored VWAP calculator with standard deviation bands.

    Computes a cumulative VWAP anchored to the first bar of the provided
    data. For intraday VWAP, pass only the current session's bars.
    For multi-session VWAP (e.g. 4-hour bars over several days), the
    anchor will be the start of the provided window.
    """

    def __init__(self, market_data: MarketData, num_bands: int = 2):
        """
        Args:
            market_data: MarketData with high, low, close, volume Series.
            num_bands: Number of standard deviation bands to compute on
                each side (default 2 → ±1σ and ±2σ).
        """
        self.num_bands = num_bands
        super().__init__(market_data)

    def _validate_inputs(self):
        """Override: require at least 2 bars (1 is not enough for bands)."""
        if len(self.data.close) < 2:
            raise ValueError("VWAP requires at least 2 bars")

    def calculate(self) -> dict[str, pd.Series]:
        """
        Calculate VWAP and standard deviation bands.

        Returns:
            Dict with keys:
              'vwap'       → pd.Series, same index as input
              'std_dev'    → pd.Series of rolling volume-weighted std-dev
              'upper_N'    → pd.Series, +N standard deviations above VWAP
              'lower_N'    → pd.Series, −N standard deviations below VWAP
        """
        typical = (self.data.high + self.data.low + self.data.close) / 3.0

        # Cumulative sums anchored to bar 0
        cum_vol = self.data.volume.cumsum()
        cum_pv = (typical * self.data.volume).cumsum()

        # Avoid division by zero on the first bar if volume is 0
        cum_vol_safe = cum_vol.replace(0, float("nan"))
        vwap = cum_pv / cum_vol_safe

        # Volume-weighted variance → std dev
        cum_sq_dev = ((typical - vwap) ** 2 * self.data.volume).cumsum()
        std_dev = (cum_sq_dev / cum_vol_safe) ** 0.5

        result: dict[str, pd.Series] = {"vwap": vwap, "std_dev": std_dev}
        for i in range(1, self.num_bands + 1):
            result[f"upper_{i}"] = vwap + i * std_dev
            result[f"lower_{i}"] = vwap - i * std_dev

        return result

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------

    def current_vwap(self) -> float | None:
        """Return the most recent VWAP value as a scalar."""
        try:
            series = self.calculate()["vwap"]
            val = series.iloc[-1]
            return None if pd.isna(val) else float(val)
        except Exception:
            return None

    def current_std_dev(self) -> float | None:
        """Return the most recent volume-weighted standard deviation."""
        try:
            series = self.calculate()["std_dev"]
            val = series.iloc[-1]
            return None if pd.isna(val) else float(val)
        except Exception:
            return None

    def std_distance_from_vwap(self, price: float) -> float | None:
        """
        Return how many standard deviations *price* is from the current VWAP.

        Positive = price above VWAP.  Negative = price below VWAP.
        Returns None if std_dev is zero or unavailable.
        """
        vwap = self.current_vwap()
        std = self.current_std_dev()
        if vwap is None or std is None or std == 0:
            return None
        return (price - vwap) / std

    def price_above_vwap(self, price: float) -> bool:
        """Return True if *price* is above the current VWAP."""
        vwap = self.current_vwap()
        return vwap is not None and price > vwap

    def price_below_vwap(self, price: float) -> bool:
        """Return True if *price* is below the current VWAP."""
        vwap = self.current_vwap()
        return vwap is not None and price < vwap
