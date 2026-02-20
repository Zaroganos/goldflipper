"""
Volume Profile Indicator

Builds a price-by-volume distribution from OHLCV bars and identifies:
  - POC  (Point of Control) — price level with the highest traded volume.
  - VAH  (Value Area High)  — upper bound of the value area.
  - VAL  (Value Area Low)   — lower bound of the value area.

The value area captures a configurable fraction of total volume (typically
70 %) by expanding outward from the POC bin by bin, always adding the
higher-volume side first.

Volume is distributed proportionally across the high-low range of each
candle so that every bar contributes volume to every price bin it touches.

Usage:
    from goldflipper.data.indicators.volume_profile import (
        VolumeProfileCalculator, VolumeProfileResult
    )
    from goldflipper.data.indicators.base import MarketData

    md = MarketData(high=df['high'], low=df['low'],
                    close=df['close'], volume=df['volume'])
    calc = VolumeProfileCalculator(md, n_bins=24, value_area_pct=0.70)
    profile = calc.get_profile()   # VolumeProfileResult
    result  = calc.calculate()     # dict[str, pd.Series] (IndicatorCalculator API)
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .base import IndicatorCalculator, MarketData

# =============================================================================
# Result dataclass
# =============================================================================


@dataclass
class VolumeProfileResult:
    """
    Structured result of a volume profile calculation.

    Attributes:
        poc: Point of Control — price level with the highest volume.
        vah: Value Area High.
        val: Value Area Low.
        bins: DataFrame with columns price_low, price_high, price_mid, volume.
        value_area_pct: Fraction of volume captured by the value area.
        total_volume: Total volume across all bars.
    """

    poc: float
    vah: float
    val: float
    bins: pd.DataFrame
    value_area_pct: float
    total_volume: float

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def price_in_value_area(self, price: float) -> bool:
        """Return True if *price* is within the value area (VAL ≤ price ≤ VAH)."""
        return self.val <= price <= self.vah

    def price_above_poc(self, price: float) -> bool:
        """Return True if *price* is strictly above the POC."""
        return price > self.poc

    def price_below_poc(self, price: float) -> bool:
        """Return True if *price* is strictly below the POC."""
        return price < self.poc

    def pct_from_poc(self, price: float) -> float:
        """Return % distance of *price* from POC (positive = above)."""
        if self.poc == 0:
            return 0.0
        return (price - self.poc) / self.poc * 100.0

    def nearest_support(self, price: float, above: bool = False) -> float | None:
        """
        Return the nearest high-volume price level below (or above) *price*.

        Searches the bins for the level with highest volume that is below
        the current price (typical support lookup). Set above=True to find
        the nearest resistance.

        Args:
            price: Current price.
            above: If True, search for levels above *price* (resistance).

        Returns:
            Price midpoint of the nearest relevant bin, or None if unavailable.
        """
        if self.bins.empty:
            return None
        if above:
            candidates = self.bins[self.bins["price_mid"] > price]
        else:
            candidates = self.bins[self.bins["price_mid"] < price]
        if candidates.empty:
            return None
        best_idx = candidates["volume"].idxmax()
        return float(candidates.loc[best_idx, "price_mid"])


# =============================================================================
# Calculator
# =============================================================================


class VolumeProfileCalculator(IndicatorCalculator):
    """
    Volume Profile calculator following the IndicatorCalculator base pattern.

    Distributes each bar's volume proportionally across its high-low range,
    then aggregates into price bins.
    """

    def __init__(
        self,
        market_data: MarketData,
        n_bins: int = 24,
        value_area_pct: float = 0.70,
    ):
        """
        Args:
            market_data: OHLCV MarketData.
            n_bins: Number of price bins to segment the price range into.
            value_area_pct: Fraction of total volume defining the value area
                (default 0.70 = 70 %).
        """
        self.n_bins = max(2, n_bins)
        self.value_area_pct = value_area_pct
        super().__init__(market_data)

    def _validate_inputs(self):
        """Override: only need OHLCV with at least 1 bar."""
        if not all(isinstance(x, pd.Series) for x in [self.data.high, self.data.low, self.data.close, self.data.volume]):
            raise ValueError("Price and volume data must be pandas Series")
        if len(self.data.close) < 1:
            raise ValueError("Volume Profile requires at least 1 bar")

    # ------------------------------------------------------------------
    # Core computation
    # ------------------------------------------------------------------

    def _build_bins(self) -> tuple[np.ndarray, list[float]]:
        """
        Distribute bar volumes into price bins.

        Returns:
            (bin_volumes array, bin_edges list)
        """
        price_min = float(self.data.low.min())
        price_max = float(self.data.high.max())

        if price_min >= price_max:
            # All bars at the same price — put everything in one bin
            price_min -= 0.01
            price_max += 0.01

        bin_size = (price_max - price_min) / self.n_bins
        bin_edges = [price_min + i * bin_size for i in range(self.n_bins + 1)]
        bin_volumes = np.zeros(self.n_bins)

        for idx in range(len(self.data.close)):
            high = float(self.data.high.iloc[idx])
            low = float(self.data.low.iloc[idx])
            close = float(self.data.close.iloc[idx])
            vol = float(self.data.volume.iloc[idx])
            bar_range = high - low

            if bar_range <= 0:
                # Doji / zero-range bar — assign volume to the close bin
                bin_idx = int((close - price_min) / bin_size)
                bin_idx = max(0, min(bin_idx, self.n_bins - 1))
                bin_volumes[bin_idx] += vol
                continue

            for i in range(self.n_bins):
                overlap = max(0.0, min(high, bin_edges[i + 1]) - max(low, bin_edges[i]))
                if overlap > 0:
                    bin_volumes[i] += vol * (overlap / bar_range)

        return bin_volumes, bin_edges

    def _find_value_area(self, bin_volumes: np.ndarray, bin_edges: list[float]) -> tuple[float, float, float, float]:
        """
        Identify POC, VAH, VAL from bin volumes.

        Returns:
            (poc_price, vah_price, val_price, total_volume)
        """
        total_vol = float(bin_volumes.sum())
        if total_vol == 0:
            mid = (bin_edges[0] + bin_edges[-1]) / 2
            return mid, bin_edges[-1], bin_edges[0], 0.0

        poc_idx = int(bin_volumes.argmax())
        poc_price = (bin_edges[poc_idx] + bin_edges[poc_idx + 1]) / 2.0

        # Expand value area outward from POC
        target_vol = total_vol * self.value_area_pct
        va_low = poc_idx
        va_high = poc_idx
        va_vol = float(bin_volumes[poc_idx])

        while va_vol < target_vol:
            can_down = va_low > 0
            can_up = va_high < self.n_bins - 1
            if not can_down and not can_up:
                break

            vol_down = float(bin_volumes[va_low - 1]) if can_down else -1.0
            vol_up = float(bin_volumes[va_high + 1]) if can_up else -1.0

            if vol_down >= vol_up and can_down:
                va_low -= 1
                va_vol += bin_volumes[va_low]
            elif can_up:
                va_high += 1
                va_vol += bin_volumes[va_high]
            elif can_down:
                va_low -= 1
                va_vol += bin_volumes[va_low]
            else:
                break

        vah = float(bin_edges[va_high + 1])
        val = float(bin_edges[va_low])
        return poc_price, vah, val, total_vol

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_profile(self) -> VolumeProfileResult:
        """
        Build and return the full Volume Profile.

        Returns:
            VolumeProfileResult with poc, vah, val, bins DataFrame, etc.

        Raises:
            ValueError: If data is invalid.
        """
        bin_volumes, bin_edges = self._build_bins()
        poc, vah, val, total_vol = self._find_value_area(bin_volumes, bin_edges)

        bins_df = pd.DataFrame(
            {
                "price_low": bin_edges[:-1],
                "price_high": bin_edges[1:],
                "price_mid": [(bin_edges[i] + bin_edges[i + 1]) / 2.0 for i in range(self.n_bins)],
                "volume": bin_volumes,
            }
        )

        return VolumeProfileResult(
            poc=poc,
            vah=vah,
            val=val,
            bins=bins_df,
            value_area_pct=self.value_area_pct,
            total_volume=total_vol,
        )

    def calculate(self) -> dict[str, pd.Series]:
        """
        Calculate Volume Profile, returning results in the IndicatorCalculator
        dict[str, pd.Series] format.

        Scalar values (poc, vah, val) are wrapped in single-element Series.
        Bin distributions are returned as full Series indexed by bin number.

        Returns:
            Dict with keys: poc, vah, val, bins_price_mid, bins_volume.
        """
        profile = self.get_profile()
        return {
            "poc": pd.Series([profile.poc]),
            "vah": pd.Series([profile.vah]),
            "val": pd.Series([profile.val]),
            "bins_price_mid": profile.bins["price_mid"].reset_index(drop=True),
            "bins_volume": profile.bins["volume"].reset_index(drop=True),
        }
