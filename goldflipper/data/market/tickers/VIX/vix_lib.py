from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import List, Optional
from urllib.parse import quote, urlencode

import pandas as pd
import requests
from io import StringIO
from pathlib import Path

from goldflipper.utils.market_holidays import is_market_holiday
from typing import Dict


# ---------------------------- Expiration Rules ----------------------------- #

def third_friday(year: int, month: int) -> datetime:
    """Return date of the third Friday for given year/month."""
    first = datetime(year, month, 1)
    days_until_friday = (4 - first.weekday()) % 7  # Friday=4 (Mon=0)
    first_friday = first + timedelta(days=days_until_friday)
    return first_friday + timedelta(weeks=2)


def generate_rule_based_expirations_for_year(year: int) -> List[datetime]:
    """Generate VIX monthly settlement dates for a given year using the rule:
    Wednesday that is 30 days before the third Friday of the following month,
    adjusted to the prior business day when a holiday intervenes.
    """
    expirations: List[datetime] = []
    for month in range(1, 13):
        # Third Friday of following month
        next_month = month + 1
        next_year = year
        if next_month == 13:
            next_month = 1
            next_year += 1
        tfr = third_friday(next_year, next_month)
        exp_date = (tfr - timedelta(days=30)).date()
        while exp_date.weekday() >= 5 or is_market_holiday(exp_date):
            exp_date = exp_date - timedelta(days=1)
        expirations.append(datetime.combine(exp_date, datetime.min.time()))
    return sorted(expirations)


def get_rule_based_vix_expirations_window() -> List[datetime]:
    """Return rule-based VIX monthly expirations for current and next year."""
    today = datetime.now(timezone.utc).date()
    dates = generate_rule_based_expirations_for_year(today.year)
    dates += generate_rule_based_expirations_for_year(today.year + 1)
    return sorted({d for d in dates})


# -------------------------- EOD Spot Price Fetch --------------------------- #

def _to_unix_day_bounds(day: datetime) -> tuple[int, int]:
    start = datetime(day.year, day.month, day.day, 0, 0, 0, tzinfo=timezone.utc)
    end = start + timedelta(days=1)
    return int(start.timestamp()), int(end.timestamp())


def _yahoo_chart_url(symbol: str, day: datetime, interval: str = '1d') -> str:
    p1, p2 = _to_unix_day_bounds(day)
    encoded = quote(symbol, safe='')
    qs = urlencode({'symbol': symbol, 'period1': p1, 'period2': p2, 'interval': interval})
    return f"https://query1.finance.yahoo.com/v8/finance/chart/{encoded}?{qs}"


def get_yahoo_chart_daily_close(symbol: str, day: datetime) -> Optional[float]:
    """Directly query Yahoo chart API for a single day's daily close."""
    try:
        url = _yahoo_chart_url(symbol, day, '1d')
        resp = requests.get(url, timeout=8, headers={'User-Agent': 'Mozilla/5.0'})
        if resp.status_code != 200:
            return None
        data = resp.json()
        result = (data or {}).get('chart', {}).get('result')
        if not result:
            return None
        quote = result[0].get('indicators', {}).get('quote', [{}])[0]
        closes = quote.get('close') or []
        if closes and closes[0] is not None:
            return float(closes[0])
        return None
    except Exception:
        return None


def get_cboe_vix_close_for_date(day: datetime) -> Optional[float]:
    """Fetch VIX index close for a given date from Cboe CSV (1990-present).

    Source: https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv
    """
    try:
        url = "https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv"
        resp = requests.get(url, timeout=12, headers={'User-Agent': 'Mozilla/5.0'})
        if resp.status_code != 200 or not resp.text:
            return None
        # CSV header format: DATE,OPEN,HIGH,LOW,CLOSE  (dates formatted as MM/DD/YYYY)
        df = pd.read_csv(StringIO(resp.text))
        df['DATE'] = pd.to_datetime(df['DATE'], format='%m/%d/%Y', errors='coerce').dt.date
        row = df.loc[df['DATE'] == day.date()]
        if row.empty:
            return None
        return float(row.iloc[0]['CLOSE'])
    except Exception:
        return None


# ----------------------- Chain selection / mids (VIX) ---------------------- #

def robust_mid(option_row: pd.Series) -> Optional[float]:
    """Compute a robust mid for an option row: (bid+ask)/2; else last; else ask; else bid."""
    try:
        bid = float(option_row.get('bid', 0) or 0)
        ask = float(option_row.get('ask', 0) or 0)
        last = float(option_row.get('last', 0) or 0)
    except Exception:
        bid = ask = last = 0.0
    if bid > 0 and ask > 0:
        return (bid + ask) / 2.0
    if last > 0:
        return last
    if ask > 0:
        return ask
    if bid > 0:
        return bid
    return None


def select_vix_required_options_from_chain(
    calls: pd.DataFrame,
    puts: pd.DataFrame,
) -> Optional[Dict[str, pd.Series]]:
    """Return {'atm_call','atm_put','itm_call','itm_put'} for VIX using |C-P| ATM and adjacent strikes.

    Requires both calls/puts present at ATM strike and adjacent strikes; uses robust mid validity checks.
    """
    try:
        # Compute robust mids per strike
        def _group_mid(df: pd.DataFrame) -> Optional[float]:
            if df.empty:
                return None
            return robust_mid(df.iloc[0])

        call_mids_map = calls.groupby('strike').apply(_group_mid).dropna().to_dict()
        put_mids_map = puts.groupby('strike').apply(_group_mid).dropna().to_dict()
        common_strikes = sorted(set(call_mids_map.keys()) & set(put_mids_map.keys()))
        if not common_strikes:
            return None

        # ATM by min |C-P|
        atm_strike = min(common_strikes, key=lambda k: abs(float(call_mids_map[k]) - float(put_mids_map[k])))

        # Adjacent strikes
        all_strikes = sorted(set(calls['strike'].tolist() + puts['strike'].tolist()))
        if len(all_strikes) < 3:
            return None
        atm_index = all_strikes.index(atm_strike)
        if atm_index == 0 or atm_index == len(all_strikes) - 1:
            return None
        itm_call_strike = all_strikes[atm_index - 1]
        itm_put_strike = all_strikes[atm_index + 1]

        # Extract rows
        atm_calls = calls[calls['strike'] == atm_strike]
        atm_puts = puts[puts['strike'] == atm_strike]
        itm_calls = calls[calls['strike'] == itm_call_strike]
        itm_puts = puts[puts['strike'] == itm_put_strike]
        if atm_calls.empty or atm_puts.empty or itm_calls.empty or itm_puts.empty:
            return None
        atm_call = atm_calls.iloc[0]
        atm_put = atm_puts.iloc[0]
        itm_call = itm_calls.iloc[0]
        itm_put = itm_puts.iloc[0]

        # Validate robust mids exist
        if robust_mid(atm_call) is None or robust_mid(atm_put) is None:
            return None
        if robust_mid(itm_call) is None or robust_mid(itm_put) is None:
            return None

        return {
            'atm_call': atm_call,
            'atm_put': atm_put,
            'itm_call': itm_call,
            'itm_put': itm_put,
        }
    except Exception:
        return None


# --------------------------- Provider chain helper ------------------------- #

def get_vix_option_chain(manager, symbol: str, expiration_date: datetime) -> Optional[Dict[str, pd.DataFrame]]:
    """Fetch VIX option chain for the given expiration using the market data manager."""
    try:
        expiration_str = expiration_date.strftime('%Y-%m-%d')
        chain = manager.get_option_chain(symbol, expiration_str)
        if not chain or 'calls' not in chain or 'puts' not in chain:
            return None
        calls_df = chain['calls']
        puts_df = chain['puts']
        if calls_df.empty and puts_df.empty:
            return None
        return chain
    except Exception:
        return None


