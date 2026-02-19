from typing import cast

import pandas as pd
import yfinance as yf

from goldflipper.chart.candlestick import CandlestickChart
from goldflipper.data.indicators.base import MarketData
from goldflipper.data.indicators.ema import EMACalculator
from goldflipper.data.indicators.macd import MACDCalculator


def _as_series(data: pd.DataFrame, column: str) -> pd.Series:
    values = data[column]
    if isinstance(values, pd.DataFrame):
        return cast(pd.Series, values.iloc[:, 0])
    return cast(pd.Series, values)


def create_chart_example(symbol: str):
    # Get data
    stock = yf.Ticker(symbol)
    data = stock.history(period="1y")

    # Create chart
    chart = CandlestickChart(data)

    market_data = MarketData(
        high=_as_series(data, "High"),
        low=_as_series(data, "Low"),
        close=_as_series(data, "Close"),
        volume=_as_series(data, "Volume"),
    )

    # Add EMA overlays
    ema_calc = EMACalculator(market_data)
    emas = ema_calc.calculate()

    for period in [9, 21]:
        chart.add_overlay({"data": emas[f"ema_{period}"], "type": "line", "name": f"EMA-{period}", "color": "blue" if period == 9 else "red"})

    # Add MACD indicator
    macd_calc = MACDCalculator(market_data)
    macd_data = macd_calc.calculate()

    chart.add_indicator({"data": macd_data["macd_line"], "type": "line", "name": "MACD", "panel": 2})

    # Show chart
    chart.show()
