"""
Gamma Exposure (GEX) Analysis

Calculates net gamma exposure from live option chain data (as opposed to
the Black-Scholes Greek calculators in this package which work from model
inputs). GEX uses real open-interest and gamma values from the market.

GEX = gamma × open_interest × 100 (per contract)
Net GEX = Σ(call GEX) − Σ(put GEX)

Interpretation
--------------
  Positive net GEX → Market makers are net long gamma.
    Dealers hedge by selling on rallies and buying on dips → stabilising.
  Negative net GEX → Market makers are net short gamma.
    Dealers hedge by buying on rallies and selling on dips → destabilising /
    potential gamma squeeze territory.

Conditions Detected
-------------------
  • Gamma Squeeze  — near-spot GEX is negative; dealers forced to buy stock
                     as price rises, creating a feedback loop.
  • Gamma Fade     — ATM gamma has declined significantly relative to the
                     chain average (price has moved OTM; momentum waning).
  • Delta Fade     — option delta has declined from its entry value by more
                     than a threshold, signalling OTM drift or reversal.
  • Parabolic      — price is >N standard deviations from VWAP with
                     consecutive momentum bars (requires OHLCV bars).

Usage:
    from goldflipper.data.greeks.gamma_exposure import GammaExposureAnalyzer
    import pandas as pd

    # chain_df must have: strike, type (call/put), gamma, open_interest
    analyzer = GammaExposureAnalyzer(chain_df, spot_price=185.50)
    gex = analyzer.net_gex()             # float
    squeeze = analyzer.is_gamma_squeeze()  # bool
    fade    = analyzer.is_gamma_fade()     # bool
    report  = analyzer.full_report()       # dict
"""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)

# Normalised type strings that indicate call / put
_CALL_TYPES = frozenset(["call", "calls", "c"])
_PUT_TYPES = frozenset(["put", "puts", "p"])


def _norm(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out.columns = [str(c).lower() for c in out.columns]
    return out


class GammaExposureAnalyzer:
    """
    Gamma Exposure (GEX) calculator from live option chain data.

    Accepts a chain DataFrame with at minimum: strike, type, gamma,
    open_interest columns. Column names are normalised to lowercase.

    Args:
        chain_df: Option chain DataFrame (calls + puts combined).
        spot_price: Current underlying price.
        near_spot_band_pct: Percentage band around spot price defining
            "near spot" strikes (default 2 %).
    """

    def __init__(
        self,
        chain_df: pd.DataFrame,
        spot_price: float,
        near_spot_band_pct: float = 2.0,
    ):
        self._raw = chain_df
        self.spot = float(spot_price)
        self.near_band = near_spot_band_pct / 100.0

        self._df = self._prepare(chain_df)

    def _prepare(self, df: pd.DataFrame) -> pd.DataFrame:
        """Normalise and validate the chain DataFrame."""
        out = _norm(df)
        required = {"strike", "type", "gamma", "open_interest"}
        missing = required - set(out.columns)
        if missing:
            raise ValueError(f"GammaExposureAnalyzer: missing columns {missing}")

        out["gamma"] = pd.to_numeric(out["gamma"], errors="coerce").fillna(0.0)
        out["open_interest"] = pd.to_numeric(out["open_interest"], errors="coerce").fillna(0.0)
        out["strike"] = pd.to_numeric(out["strike"], errors="coerce")

        out["_is_call"] = out["type"].str.lower().isin(_CALL_TYPES)
        out["_is_put"] = out["type"].str.lower().isin(_PUT_TYPES)
        out["_gex"] = out["gamma"] * out["open_interest"] * 100.0
        out["_signed_gex"] = out["_gex"] * out["_is_call"].map({True: 1, False: -1})
        return out

    # ------------------------------------------------------------------
    # GEX values
    # ------------------------------------------------------------------

    def call_gex(self) -> float:
        """Total GEX contributed by call contracts."""
        return float(self._df.loc[self._df["_is_call"], "_gex"].sum())

    def put_gex(self) -> float:
        """Total GEX contributed by put contracts."""
        return float(self._df.loc[self._df["_is_put"], "_gex"].sum())

    def net_gex(self) -> float:
        """Net GEX = call GEX − put GEX."""
        return self.call_gex() - self.put_gex()

    def near_spot_gex(self) -> float:
        """
        Net GEX for strikes within ±near_spot_band_pct % of spot.
        This is the most relevant measure for imminent price action.
        """
        near = self._df[abs(self._df["strike"] - self.spot) / self.spot <= self.near_band]
        return float(near["_signed_gex"].sum())

    def gamma_wall_strike(self) -> float | None:
        """The strike with the highest absolute GEX (the 'gamma wall')."""
        if self._df.empty:
            return None
        idx = self._df["_gex"].abs().idxmax()
        return float(self._df.loc[idx, "strike"])

    def atm_gamma(self) -> float:
        """Gamma of the option whose strike is nearest to spot."""
        df = self._df.copy()
        df["_dist"] = abs(df["strike"] - self.spot)
        atm = df.loc[df["_dist"].idxmin()]
        return float(atm.get("gamma", 0.0))

    def avg_gamma(self) -> float:
        """Mean gamma across all chain rows."""
        return float(self._df["gamma"].mean())

    # ------------------------------------------------------------------
    # Condition detectors
    # ------------------------------------------------------------------

    def is_gamma_squeeze(self, near_gex_threshold: float = 0.0) -> bool:
        """
        Detect potential gamma squeeze conditions.

        A squeeze is flagged when near-spot net GEX falls below
        *near_gex_threshold* (default 0 = negative GEX).

        Args:
            near_gex_threshold: GEX level at or below which a squeeze
                risk is flagged.

        Returns:
            True if squeeze conditions are present.
        """
        try:
            return self.near_spot_gex() < near_gex_threshold
        except Exception as exc:
            logger.warning(f"is_gamma_squeeze error: {exc}")
            return False

    def is_gamma_fade(
        self,
        atm_vs_avg_threshold: float = 0.5,
        prev_analyzer: GammaExposureAnalyzer | None = None,
        historical_drop_threshold: float = 0.7,
    ) -> bool:
        """
        Detect gamma fade — declining ATM gamma indicating waning momentum.

        Gamma fade is signalled when:
          (a) ATM gamma < atm_vs_avg_threshold × average chain gamma, OR
          (b) If a prior snapshot is supplied, ATM gamma has dropped below
              historical_drop_threshold × previous ATM gamma.

        Args:
            atm_vs_avg_threshold: ATM gamma / avg gamma ratio below which
                fade is flagged (default 0.5).
            prev_analyzer: Prior GammaExposureAnalyzer for time comparison.
            historical_drop_threshold: ATM gamma must drop to below this
                fraction of its prior value to be flagged.

        Returns:
            True if gamma fade is detected.
        """
        try:
            atm = self.atm_gamma()
            avg = self.avg_gamma()

            if avg > 0 and atm < avg * atm_vs_avg_threshold:
                return True

            if prev_analyzer is not None:
                prev_atm = prev_analyzer.atm_gamma()
                if prev_atm > 0 and atm < prev_atm * historical_drop_threshold:
                    return True

            return False
        except Exception as exc:
            logger.warning(f"is_gamma_fade error: {exc}")
            return False

    # ------------------------------------------------------------------
    # Full report
    # ------------------------------------------------------------------

    def full_report(self) -> dict[str, Any]:
        """
        Return a structured dict with all GEX metrics.

        Returns:
            Dict with keys: call_gex, put_gex, net_gex, near_spot_gex,
            gamma_wall_strike, atm_gamma, avg_gamma, is_positive_gex,
            is_negative_gex, gamma_squeeze_risk, gamma_fade.
        """
        try:
            n_gex = self.net_gex()
            ns_gex = self.near_spot_gex()
            return {
                "call_gex": round(self.call_gex(), 2),
                "put_gex": round(self.put_gex(), 2),
                "net_gex": round(n_gex, 2),
                "near_spot_gex": round(ns_gex, 2),
                "gamma_wall_strike": self.gamma_wall_strike(),
                "atm_gamma": round(self.atm_gamma(), 6),
                "avg_gamma": round(self.avg_gamma(), 6),
                "is_positive_gex": n_gex > 0,
                "is_negative_gex": n_gex < 0,
                "gamma_squeeze_risk": self.is_gamma_squeeze(),
                "gamma_fade": self.is_gamma_fade(),
            }
        except Exception as exc:
            logger.warning(f"GammaExposureAnalyzer.full_report error: {exc}")
            return {}


# =============================================================================
# Standalone helpers (for use without a full chain DataFrame)
# =============================================================================


def detect_delta_fade(
    current_delta: float,
    entry_delta: float,
    threshold: float = 0.15,
) -> bool:
    """
    Detect delta fade — an option's delta declining from its entry value.

    Delta fade signals that the position is drifting OTM, momentum is
    reversing, or time decay is overwhelming intrinsic value.

    Args:
        current_delta: Current option delta (sign is ignored; absolute value used).
        entry_delta: Option delta at position entry (absolute value).
        threshold: Minimum delta drop (in delta points) to flag as a fade.
            Default 0.15 = 15 delta points.

    Returns:
        True if delta has declined by at least *threshold*.
    """
    try:
        current = abs(float(current_delta))
        entry = abs(float(entry_delta))
        if entry <= 0:
            return False
        return (entry - current) >= threshold
    except Exception as exc:
        logger.warning(f"detect_delta_fade error: {exc}")
        return False


def detect_parabolic_move(
    closes: list[float],
    vwap: float,
    std_dev: float,
    vwap_distance_std: float = 2.0,
    min_consecutive_bars: int = 3,
) -> dict[str, Any]:
    """
    Detect parabolic price extension relative to VWAP.

    Uses pre-computed VWAP and standard deviation (from VWAPCalculator).

    A parabolic move is flagged when:
      1. Last close is > vwap_distance_std standard deviations from VWAP.
      2. At least min_consecutive_bars recent bars have closed in the same
         direction.

    Args:
        closes: List of close prices (chronological order).
        vwap: Current VWAP value.
        std_dev: Current VWAP standard deviation.
        vwap_distance_std: Standard deviation distance to flag (default 2.0).
        min_consecutive_bars: Minimum consecutive same-direction bars.

    Returns:
        Dict with: is_parabolic, direction ('up'/'down'/None),
        vwap_std_distance, consecutive_up, consecutive_down.
    """
    result: dict[str, Any] = {
        "is_parabolic": False,
        "direction": None,
        "vwap_std_distance": 0.0,
        "consecutive_up": 0,
        "consecutive_down": 0,
    }
    try:
        if len(closes) < max(2, min_consecutive_bars):
            return result

        last_close = closes[-1]
        std_dist = (last_close - vwap) / std_dev if std_dev > 0 else 0.0
        result["vwap_std_distance"] = round(std_dist, 2)

        # Count consecutive same-direction closes (walk backwards from last bar)
        con_up = 0
        con_down = 0
        for i in range(len(closes) - 1, 0, -1):
            if closes[i] > closes[i - 1]:
                if con_down == 0:
                    con_up += 1
                else:
                    break
            elif closes[i] < closes[i - 1]:
                if con_up == 0:
                    con_down += 1
                else:
                    break

        result["consecutive_up"] = con_up
        result["consecutive_down"] = con_down

        if std_dist >= vwap_distance_std and con_up >= min_consecutive_bars:
            result["is_parabolic"] = True
            result["direction"] = "up"
        elif std_dist <= -vwap_distance_std and con_down >= min_consecutive_bars:
            result["is_parabolic"] = True
            result["direction"] = "down"

        return result
    except Exception as exc:
        logger.warning(f"detect_parabolic_move error: {exc}")
        return result
