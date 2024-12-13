from goldflipper.chart.candlestick import CandlestickChart
from goldflipper.data.indicators.ema import EMACalculator
from goldflipper.data.indicators.macd import MACDCalculator
import yfinance as yf

def create_chart_example(symbol: str):
    # Get data
    stock = yf.Ticker(symbol)
    data = stock.history(period='1y')
    
    # Create chart
    chart = CandlestickChart(data)
    
    # Add EMA overlays
    ema_calc = EMACalculator(data)
    emas = ema_calc.calculate()
    
    for period in [9, 21]:
        chart.add_overlay({
            'data': emas[f'ema_{period}'],
            'type': 'line',
            'name': f'EMA-{period}',
            'color': 'blue' if period == 9 else 'red'
        })
    
    # Add MACD indicator
    macd_calc = MACDCalculator(data)
    macd_data = macd_calc.calculate()
    
    chart.add_indicator({
        'data': macd_data['macd_line'],
        'type': 'line',
        'name': 'MACD',
        'panel': 2
    })
    
    # Show chart
    chart.show() 