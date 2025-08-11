"""
Deprecated: vix_utils adapter was used for futures mapping experiments.
We no longer rely on it for pricing in WEM; provider data and Yahoo chart
fallbacks are used instead. Keep only the on-date helper for possible future use.
"""

from __future__ import annotations

from datetime import datetime, date, timedelta
from typing import Optional, Tuple, List

import logging

try:
    import pandas as pd  # type: ignore
except Exception:  # pragma: no cover - pandas is required elsewhere in project
    pd = None  # type: ignore

logger = logging.getLogger(__name__)


def _try_import_vix_utils():
    try:
        import vix_utils  # type: ignore
        return vix_utils
    except Exception as e:
        logger.debug(f"vix_utils not available: {e}")
        return None


# Month code mapping for VX symbols
_VX_MONTH_CODE = {
    1: "F", 2: "G", 3: "H", 4: "J", 5: "K", 6: "M",
    7: "N", 8: "Q", 9: "U", 10: "V", 11: "X", 12: "Z",
}


def vx_symbol_for_settlement(settlement_date: date) -> str:
    """Return VX symbol (e.g., VXH25) for a given monthly futures settlement date."""
    code = _VX_MONTH_CODE.get(settlement_date.month)
    year = settlement_date.year % 100
    return f"VX{code}{year:02d}"


def _coerce_date(val) -> Optional[date]:
    try:
        if isinstance(val, (datetime,)):
            return val.date()
        if isinstance(val, (date,)):
            return val
        if pd is not None:
            return pd.to_datetime(val).date()
        return None
    except Exception:
        return None


def _extract_expiry_column(df):
    """Find an expiry/expiration-like column in a vix_utils DataFrame."""
    lower_cols = {c.lower(): c for c in df.columns}
    # Preference order
    for key in ("expiry", "expiration", "settlement", "settlement_date", "expdate"):
        if key in lower_cols:
            return lower_cols[key]
    # Fallback: any column containing "exp"
    for lc, orig in lower_cols.items():
        if "exp" in lc:
            return orig
    return None


def _extract_trade_date_column(df):
    lower_cols = {c.lower(): c for c in df.columns}
    for key in ("trade_date", "date", "asof", "timestamp"):
        if key in lower_cols:
            return lower_cols[key]
    return None


def _get_monthly_settlement_dates_from_utils(vix_utils) -> List[date]:
    """Attempt to derive a list of monthly settlement dates using vix_utils.

    Returns future (>= today) monthly settlement dates sorted ascending when possible.
    """
    try:
        # This function name suggests trade-date to expiry mapping; we mine expiry dates
        mapping = vix_utils.vix_futures_trade_dates_and_expiry_dates()  # type: ignore[attr-defined]
        if mapping is None or not hasattr(mapping, "empty"):
            return []
        if getattr(mapping, "empty", True):
            return []
        exp_col = _extract_expiry_column(mapping)
        if not exp_col:
            return []
        expiries = mapping[exp_col].dropna().unique().tolist()
        expiries = [_coerce_date(x) for x in expiries]
        expiries = [d for d in expiries if d is not None]
        expiries = sorted(set(expiries))
        today = datetime.utcnow().date()
        future = [d for d in expiries if d >= today]
        # Deduplicate while preserving order
        seen = set()
        result: List[date] = []
        for d in future:
            if d not in seen:
                seen.add(d)
                result.append(d)
        return result
    except Exception as e:
        logger.debug(f"Could not derive monthly settlement dates from vix_utils: {e}")
        return []


def _get_monthly_futures_wide(vix_utils):
    """Return the monthly-tenor wide DataFrame if available."""
    try:
        fut = vix_utils.load_vix_term_structure()  # type: ignore[attr-defined]
        wide = vix_utils.pivot_futures_on_monthly_tenor(fut)  # type: ignore[attr-defined]
        if wide is not None and hasattr(wide, "empty") and not getattr(wide, "empty", True):
            return wide
        return None
    except Exception as e:
        logger.debug(f"Failed to build monthly futures wide frame: {e}")
        return None


def _pick_last_valid_row(df, columns: List[str]):
    """Pick the last row that has non-null values for all specified columns, searching back 30 rows."""
    try:
        for i in range(1, min(31, len(df) + 1)):
            row = df.iloc[-i]
            if all(pd.notna(row.get(c)) for c in columns):
                return row
        return None
    except Exception:
        return None


def _guess_m1_m2_columns(df) -> Optional[Tuple[str, str]]:
    """Heuristically identify the front (M1) and next (M2) tenor columns."""
    cols = list(df.columns)
    lower = {c.lower(): c for c in cols}
    # Preferred explicit names
    for c1, c2 in (("m1", "m2"), ("vx1", "vx2"), ("front", "second")):
        if c1 in lower and c2 in lower:
            return lower[c1], lower[c2]
    # Columns ending with 1/2
    cand1 = [c for c in cols if c.strip().lower().endswith("1")]
    cand2 = [c for c in cols if c.strip().lower().endswith("2")]
    if cand1 and cand2:
        return cand1[0], cand2[0]
    # Fallback: take first two numeric-like columns
    numeric_cols = [c for c in cols if pd.api.types.is_numeric_dtype(df[c])]
    if len(numeric_cols) >= 2:
        return numeric_cols[0], numeric_cols[1]
    # Fallback: any two non-date columns
    non_date = []
    for c in cols:
        if not isinstance(df[c].iloc[0], (datetime,)):
            non_date.append(c)
    if len(non_date) >= 2:
        return non_date[0], non_date[1]
    return None


def _resolve_monthly_settlement_for_weekly(weekly_exp: date, monthly_settlements: List[date]) -> Optional[Tuple[date, str]]:
    """Map a weekly option expiry to its underlying monthly futures settlement and tenor label (M1/M2).

    Rule: If weekly is before the current month's monthly settlement, use front month (M1),
    otherwise use next month (M2).
    """
    if not monthly_settlements:
        return None
    monthly_sorted = sorted(monthly_settlements)
    # Find the first monthly settlement on or after the weekly
    for i, mdt in enumerate(monthly_sorted):
        if weekly_exp <= mdt:
            # Weekly occurs before (or on) this monthly settlement
            return mdt, "M1"
    # If no monthly on/after weekly, use the next month's settlement as M1 logically
    # and then M2 would be the following one; but since we just need price, mark as M1.
    return monthly_sorted[-1], "M1"


def get_vix_futures_price_for_option_expiry(option_expiration: date) -> Optional[float]:
    """Deprecated: do not use. Retained as a no-op returning None."""
    return None


def get_vix_futures_price_for_option_expiry_on_date(option_expiration: date, reference_date: date) -> Optional[float]:
    """Return the VIX futures price for a given option expiry as of a reference date (e.g., previous Friday).

    Chooses M1/M2 tenor based on weekly vs monthly relationship, then selects the last
    available price on or before reference_date from the monthly-tenor wide frame.
    """
    vix_utils = _try_import_vix_utils()
    if vix_utils is None or pd is None:
        return None

    monthly_settlements = _get_monthly_settlement_dates_from_utils(vix_utils)
    if not monthly_settlements:
        return None

    resolved = _resolve_monthly_settlement_for_weekly(option_expiration, monthly_settlements)
    if not resolved:
        return None
    _, tenor = resolved

    wide = _get_monthly_futures_wide(vix_utils)
    if wide is None:
        return None

    # Normalize index to datetime to filter by reference_date
    try:
        if not isinstance(wide.index, pd.DatetimeIndex):
            td_col = _extract_trade_date_column(wide)
            if td_col and td_col in wide.columns:
                wide = wide.set_index(pd.to_datetime(wide[td_col]))
    except Exception:
        pass

    cols = _guess_m1_m2_columns(wide)
    if not cols:
        return None
    m1_col, m2_col = cols
    chosen_col = m1_col if tenor == "M1" else m2_col

    # Find last row on or before reference_date
    try:
        ref_ts = pd.Timestamp(reference_date)
        if isinstance(wide.index, pd.DatetimeIndex):
            subset = wide.loc[wide.index <= ref_ts]
        else:
            # Fallback: try to coerce index
            idx = pd.to_datetime(wide.index, errors='coerce')
            mask = idx <= ref_ts
            subset = wide.loc[mask] if mask.any() else wide
        if subset is None or subset.empty:
            return None
        row = subset.iloc[-1]
        val = row.get(chosen_col)
        return float(val) if val is not None else None
    except Exception:
        return None


def get_monthly_settlement_dates(limit: int = 14) -> List[date]:
    """Best-effort list of upcoming monthly settlement dates (VIX futures) using vix_utils.

    Fallback: empty list; callers should handle.
    """
    vix_utils = _try_import_vix_utils()
    if vix_utils is None:
        return []
    dates = _get_monthly_settlement_dates_from_utils(vix_utils)
    return dates[:limit] if dates else []



