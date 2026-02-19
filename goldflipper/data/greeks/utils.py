from datetime import datetime
from typing import Any

from .base import OptionData


def convert_yfinance_data_to_option_data(yf_data: dict[str, Any], risk_free_rate: float, dividend_yield: float = 0.0) -> OptionData:
    """
    Convert yfinance option data to OptionData format

    Args:
        yf_data: Dictionary containing yfinance option data
        risk_free_rate: Risk-free interest rate
        dividend_yield: Dividend yield of the underlying stock

    Returns:
        OptionData object with converted values
    """
    # Extract expiration date from yfinance data
    expiry_date = datetime.strptime(yf_data["expiration"], "%Y-%m-%d")
    current_date = datetime.now()

    # Calculate time to expiry in years
    time_to_expiry = (expiry_date - current_date).days / 365.0

    return OptionData(
        underlying_price=float(yf_data["underlyingPrice"]),
        strike_price=float(yf_data["strike"]),
        time_to_expiry=time_to_expiry,
        risk_free_rate=risk_free_rate,
        volatility=float(yf_data["impliedVolatility"]),
        dividend_yield=dividend_yield,
    )
