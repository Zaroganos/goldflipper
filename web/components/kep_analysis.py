"""
KEP (Key Entry Points) Analysis Component

Identifies and scores potential trade entry levels based on congruence of multiple factors.
Integrates with WEM module for expected move levels and calculates additional support/resistance.

KEP Congruence Parameters (from Playbook §4.1):
- WEM S1/S2 (Weekly Expected Move bounds)
- Delta 16± (Probability bounds)
- 52-week High/Low
- Fibonacci Levels
- Gap Levels
- Prior Day/Week H/L
- 200 EMA
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


@dataclass
class KEPLevel:
    """Represents a single KEP level"""
    name: str
    price: float
    category: str  # 'wem', 'delta', 'technical', 'historical', 'fibonacci', 'gap'
    importance: str = 'normal'  # 'high', 'normal', 'low'
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'price': self.price,
            'category': self.category,
            'importance': self.importance
        }


@dataclass
class KEPScore:
    """KEP analysis result for a symbol"""
    symbol: str
    current_price: float
    score: int
    max_score: int
    rating: str  # 'HIGH', 'MEDIUM', 'LOW'
    matched_factors: List[Dict[str, Any]]
    all_levels: Dict[str, float]
    direction_bias: Optional[str] = None  # 'CALLS', 'PUTS', 'NEUTRAL'
    nearest_level: Optional[Dict[str, Any]] = None
    confluence_zones: List[Dict[str, Any]] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'symbol': self.symbol,
            'current_price': self.current_price,
            'score': self.score,
            'max_score': self.max_score,
            'score_pct': round(self.score / self.max_score * 100, 1) if self.max_score > 0 else 0,
            'rating': self.rating,
            'matched_factors': self.matched_factors,
            'all_levels': self.all_levels,
            'direction_bias': self.direction_bias,
            'nearest_level': self.nearest_level,
            'confluence_zones': self.confluence_zones
        }


class KEPAnalyzer:
    """
    Analyzes Key Entry Points by scoring proximity to multiple congruence factors.
    
    A KEP is identified when price approaches a level where multiple factors converge,
    increasing the probability of a significant price reaction.
    """
    
    DEFAULT_PROXIMITY_THRESHOLD = 0.02  # 2% from level
    
    # Level definitions with weights
    LEVEL_CHECKS = [
        ('wem_s1', 'WEM S1 (Lower Bound)', 'wem', 1.5),
        ('wem_s2', 'WEM S2 (Upper Bound)', 'wem', 1.5),
        ('delta_16_plus', 'Delta 16 Call Strike', 'delta', 1.0),
        ('delta_16_minus', 'Delta 16 Put Strike', 'delta', 1.0),
        ('high_52', '52-Week High', 'historical', 1.5),
        ('low_52', '52-Week Low', 'historical', 1.5),
        ('fib_618', 'Fibonacci 61.8%', 'fibonacci', 1.0),
        ('fib_382', 'Fibonacci 38.2%', 'fibonacci', 1.0),
        ('fib_500', 'Fibonacci 50%', 'fibonacci', 0.5),
        ('ema_200', '200 EMA', 'technical', 1.5),
        ('ema_21', '21 EMA', 'technical', 0.5),
        ('prior_day_high', 'Prior Day High', 'historical', 0.75),
        ('prior_day_low', 'Prior Day Low', 'historical', 0.75),
        ('prior_week_high', 'Prior Week High', 'historical', 1.0),
        ('prior_week_low', 'Prior Week Low', 'historical', 1.0),
        ('gap_1_top', 'Gap Level (Top)', 'gap', 1.0),
        ('gap_1_bottom', 'Gap Level (Bottom)', 'gap', 1.0),
    ]
    
    def __init__(self, proximity_threshold: float = None):
        """
        Initialize KEP Analyzer.
        
        Args:
            proximity_threshold: Custom proximity threshold (default 2%)
        """
        self.proximity_threshold = proximity_threshold or self.DEFAULT_PROXIMITY_THRESHOLD
    
    def calculate_kep_score(
        self,
        symbol: str,
        current_price: float,
        levels: Dict[str, float],
        proximity_threshold: float = None
    ) -> KEPScore:
        """
        Score a potential KEP based on proximity to congruence factors.
        
        Args:
            symbol: Stock ticker
            current_price: Current stock price
            levels: Dict containing all calculated levels
            proximity_threshold: Override default proximity threshold
            
        Returns:
            KEPScore with score and matched factors
        """
        threshold = proximity_threshold or self.proximity_threshold
        
        score = 0
        matched_factors = []
        weighted_score = 0.0
        max_weighted_score = sum(weight for _, _, _, weight in self.LEVEL_CHECKS)
        
        for level_key, label, category, weight in self.LEVEL_CHECKS:
            level_price = levels.get(level_key)
            
            if level_price is None or not isinstance(level_price, (int, float)):
                continue
            
            if level_price <= 0:
                continue
            
            distance_pct = (current_price - level_price) / current_price
            
            if abs(distance_pct) <= threshold:
                score += 1
                weighted_score += weight
                matched_factors.append({
                    'factor': label,
                    'level_key': level_key,
                    'level': level_price,
                    'distance_pct': round(distance_pct * 100, 2),
                    'category': category,
                    'weight': weight,
                    'direction': 'above' if distance_pct > 0 else 'below'
                })
        
        # Determine rating based on weighted score
        if weighted_score >= 4.0:
            rating = 'HIGH'
        elif weighted_score >= 2.0:
            rating = 'MEDIUM'
        else:
            rating = 'LOW'
        
        # Determine direction bias based on matched factors
        direction_bias = self._determine_direction_bias(current_price, levels, matched_factors)
        
        # Find nearest level
        nearest = self._find_nearest_level(current_price, levels)
        
        # Find confluence zones
        confluence_zones = self._find_confluence_zones(levels, threshold * 2)
        
        return KEPScore(
            symbol=symbol,
            current_price=current_price,
            score=score,
            max_score=len(self.LEVEL_CHECKS),
            rating=rating,
            matched_factors=matched_factors,
            all_levels=levels,
            direction_bias=direction_bias,
            nearest_level=nearest,
            confluence_zones=confluence_zones
        )
    
    def _determine_direction_bias(
        self,
        current_price: float,
        levels: Dict[str, float],
        matched_factors: List[Dict]
    ) -> str:
        """
        Determine directional bias based on where price is relative to levels.
        
        Returns 'CALLS' if near support levels, 'PUTS' if near resistance levels.
        """
        support_indicators = 0
        resistance_indicators = 0
        
        # Check position relative to key levels
        support_levels = ['wem_s1', 'delta_16_minus', 'low_52', 'prior_day_low', 'prior_week_low']
        resistance_levels = ['wem_s2', 'delta_16_plus', 'high_52', 'prior_day_high', 'prior_week_high']
        
        for factor in matched_factors:
            level_key = factor.get('level_key', '')
            direction = factor.get('direction', '')
            
            # Near support and above it = potential bounce (CALLS)
            if level_key in support_levels:
                if direction == 'above':  # Price slightly above support
                    support_indicators += factor.get('weight', 1)
                else:  # Price at or below support (breakdown risk)
                    resistance_indicators += factor.get('weight', 1) * 0.5
            
            # Near resistance and below it = potential rejection (PUTS)
            if level_key in resistance_levels:
                if direction == 'below':  # Price slightly below resistance
                    resistance_indicators += factor.get('weight', 1)
                else:  # Price at or above resistance (breakout potential)
                    support_indicators += factor.get('weight', 1) * 0.5
        
        # Also check 200 EMA position
        ema_200 = levels.get('ema_200')
        if ema_200 and isinstance(ema_200, (int, float)):
            if current_price > ema_200:
                support_indicators += 0.5  # Above EMA = bullish bias
            else:
                resistance_indicators += 0.5  # Below EMA = bearish bias
        
        if support_indicators > resistance_indicators + 1:
            return 'CALLS'
        elif resistance_indicators > support_indicators + 1:
            return 'PUTS'
        else:
            return 'NEUTRAL'
    
    def _find_nearest_level(
        self,
        current_price: float,
        levels: Dict[str, float]
    ) -> Optional[Dict[str, Any]]:
        """Find the single nearest level to current price."""
        nearest = None
        min_distance = float('inf')
        
        for level_key, label, category, weight in self.LEVEL_CHECKS:
            level_price = levels.get(level_key)
            
            if level_price is None or not isinstance(level_price, (int, float)):
                continue
            
            if level_price <= 0:
                continue
            
            distance = abs(current_price - level_price)
            
            if distance < min_distance:
                min_distance = distance
                nearest = {
                    'level_key': level_key,
                    'label': label,
                    'price': level_price,
                    'distance': distance,
                    'distance_pct': round((distance / current_price) * 100, 2),
                    'category': category,
                    'direction': 'above' if current_price > level_price else 'below'
                }
        
        return nearest
    
    def _find_confluence_zones(
        self,
        levels: Dict[str, float],
        zone_threshold: float
    ) -> List[Dict[str, Any]]:
        """
        Find zones where multiple levels converge.
        
        A confluence zone is an area where 2+ levels are within zone_threshold of each other.
        """
        # Get all valid level prices
        level_prices = []
        for level_key, label, category, weight in self.LEVEL_CHECKS:
            price = levels.get(level_key)
            if price and isinstance(price, (int, float)) and price > 0:
                level_prices.append({
                    'key': level_key,
                    'label': label,
                    'price': price,
                    'category': category,
                    'weight': weight
                })
        
        if len(level_prices) < 2:
            return []
        
        # Sort by price
        level_prices.sort(key=lambda x: x['price'])
        
        # Find clusters
        zones = []
        used_indices = set()
        
        for i, level in enumerate(level_prices):
            if i in used_indices:
                continue
            
            cluster = [level]
            used_indices.add(i)
            
            # Find nearby levels
            for j, other in enumerate(level_prices):
                if j in used_indices:
                    continue
                
                # Check if within threshold of cluster center
                cluster_avg = sum(l['price'] for l in cluster) / len(cluster)
                if abs(other['price'] - cluster_avg) / cluster_avg <= zone_threshold:
                    cluster.append(other)
                    used_indices.add(j)
            
            # Only keep clusters with 2+ levels
            if len(cluster) >= 2:
                prices = [l['price'] for l in cluster]
                zones.append({
                    'center': round(sum(prices) / len(prices), 2),
                    'low': round(min(prices), 2),
                    'high': round(max(prices), 2),
                    'level_count': len(cluster),
                    'levels': [l['label'] for l in cluster],
                    'total_weight': sum(l['weight'] for l in cluster)
                })
        
        # Sort by importance (weight)
        zones.sort(key=lambda x: x['total_weight'], reverse=True)
        
        return zones
    
    def gather_all_levels(
        self,
        wem_data: Dict[str, Any],
        ohlc_data: pd.DataFrame,
        quote_data: Optional[Dict[str, Any]] = None,
        ema_data: Optional[Dict[str, Any]] = None,
        fib_data: Optional[Dict[str, float]] = None,
        gap_data: Optional[Dict[str, float]] = None
    ) -> Dict[str, float]:
        """
        Gather all levels from various sources into a single dict.
        
        Args:
            wem_data: WEM calculation results (from st.session_state.wem_stocks_data)
            ohlc_data: DataFrame with OHLC data for prior day/week calculations
            quote_data: Stock quote with 52-week H/L (optional)
            ema_data: EMA calculation results (optional)
            fib_data: Fibonacci levels (optional)
            gap_data: Gap levels (optional)
            
        Returns:
            Dict with all level keys and their prices
        """
        levels = {}
        
        # WEM levels
        if wem_data:
            levels['wem_s1'] = wem_data.get('straddle_1')
            levels['wem_s2'] = wem_data.get('straddle_2')
            levels['delta_16_plus'] = wem_data.get('delta_16_plus')
            levels['delta_16_minus'] = wem_data.get('delta_16_minus')
            levels['atm_price'] = wem_data.get('atm_price')
        
        # 52-week H/L from quote
        if quote_data:
            levels['high_52'] = quote_data.get('High52') or quote_data.get('high_52')
            levels['low_52'] = quote_data.get('Low52') or quote_data.get('low_52')
        
        # Prior day/week from OHLC
        if ohlc_data is not None and len(ohlc_data) > 0:
            prior_levels = self._calculate_prior_levels(ohlc_data)
            levels.update(prior_levels)
        
        # EMA levels
        if ema_data:
            levels['ema_200'] = ema_data.get('ema_200')
            levels['ema_21'] = ema_data.get('ema_21')
            levels['ema_9'] = ema_data.get('ema_9')
            
            # If EMAs are Series, get the last value
            for key in ['ema_200', 'ema_21', 'ema_9']:
                if isinstance(levels.get(key), pd.Series):
                    levels[key] = float(levels[key].iloc[-1])
        
        # Fibonacci levels
        if fib_data:
            for key, value in fib_data.items():
                if key.startswith('fib_'):
                    levels[key] = value
        
        # Gap levels
        if gap_data:
            for key, value in gap_data.items():
                if key.startswith('gap_'):
                    levels[key] = value
        
        # Clean up None values and non-numeric values
        levels = {k: v for k, v in levels.items() 
                  if v is not None and isinstance(v, (int, float)) and v > 0}
        
        return levels
    
    def _calculate_prior_levels(self, ohlc_data: pd.DataFrame) -> Dict[str, float]:
        """Calculate prior day/week high/low from OHLC data."""
        levels = {}
        
        df = ohlc_data.copy()
        df.columns = df.columns.str.lower()
        
        if len(df) < 2:
            return levels
        
        # Prior day (most recent complete day)
        levels['prior_day_high'] = float(df['high'].iloc[-2])
        levels['prior_day_low'] = float(df['low'].iloc[-2])
        
        # Prior week (last 5 trading days, excluding today)
        if len(df) >= 6:
            prior_week = df.iloc[-6:-1]  # 5 days before today
            levels['prior_week_high'] = float(prior_week['high'].max())
            levels['prior_week_low'] = float(prior_week['low'].min())
        
        return levels


def analyze_symbol_kep(
    symbol: str,
    wem_data: Dict[str, Any],
    ohlc_data: pd.DataFrame,
    current_price: Optional[float] = None,
    quote_data: Optional[Dict[str, Any]] = None,
    proximity_threshold: float = 0.02
) -> KEPScore:
    """
    Convenience function to analyze KEP for a single symbol.
    
    Args:
        symbol: Stock ticker
        wem_data: WEM calculation results
        ohlc_data: OHLC DataFrame
        current_price: Current price (uses wem_data.atm_price if not provided)
        quote_data: Optional quote data with 52-week H/L
        proximity_threshold: Proximity threshold for scoring
        
    Returns:
        KEPScore object
    """
    from goldflipper.data.indicators import FibonacciCalculator, GapDetector, EMACalculator, MarketData
    
    analyzer = KEPAnalyzer(proximity_threshold)
    
    # Get current price
    price = current_price or (wem_data.get('atm_price') if wem_data else None)
    if not price:
        raise ValueError(f"No current price available for {symbol}")
    
    # Normalize OHLC columns
    df = ohlc_data.copy()
    df.columns = df.columns.str.lower()
    
    # Calculate Fibonacci levels
    fib_data = None
    try:
        fib_data = FibonacciCalculator.calculate_from_ohlc(df, lookback=20)
    except Exception as e:
        logger.warning(f"Could not calculate Fibonacci for {symbol}: {e}")
    
    # Detect gaps
    gap_data = None
    try:
        gaps = GapDetector.find_gaps(df)
        if gaps:
            gap_data = GapDetector.get_gap_levels_for_kep(gaps, price)
    except Exception as e:
        logger.warning(f"Could not detect gaps for {symbol}: {e}")
    
    # Calculate EMAs
    ema_data = None
    try:
        if len(df) >= 200:
            market_data = MarketData(
                high=df['high'],
                low=df['low'],
                close=df['close'],
                volume=df.get('volume', pd.Series([0] * len(df))),
                period=200
            )
            ema_calc = EMACalculator(market_data, periods=[9, 21, 200])
            ema_result = ema_calc.calculate()
            ema_data = {
                'ema_9': float(ema_result['ema_9'].iloc[-1]),
                'ema_21': float(ema_result['ema_21'].iloc[-1]),
                'ema_200': float(ema_result['ema_200'].iloc[-1])
            }
    except Exception as e:
        logger.warning(f"Could not calculate EMAs for {symbol}: {e}")
    
    # Gather all levels
    levels = analyzer.gather_all_levels(
        wem_data=wem_data,
        ohlc_data=df,
        quote_data=quote_data,
        ema_data=ema_data,
        fib_data=fib_data,
        gap_data=gap_data
    )
    
    # Calculate score
    return analyzer.calculate_kep_score(symbol, price, levels, proximity_threshold)


def batch_analyze_kep(
    symbols_data: List[Dict[str, Any]],
    ohlc_provider: callable,
    quote_provider: Optional[callable] = None,
    proximity_threshold: float = 0.02
) -> List[KEPScore]:
    """
    Analyze KEP for multiple symbols.
    
    Args:
        symbols_data: List of WEM data dicts (from st.session_state.wem_stocks_data)
        ohlc_provider: Function that takes symbol and returns OHLC DataFrame
        quote_provider: Optional function that takes symbol and returns quote dict
        proximity_threshold: Proximity threshold for scoring
        
    Returns:
        List of KEPScore objects sorted by score (descending)
    """
    results = []
    
    for wem_data in symbols_data:
        symbol = wem_data.get('symbol')
        if not symbol:
            continue
        
        try:
            ohlc_data = ohlc_provider(symbol)
            if ohlc_data is None or len(ohlc_data) == 0:
                logger.warning(f"No OHLC data for {symbol}")
                continue
            
            quote_data = None
            if quote_provider:
                try:
                    quote_data = quote_provider(symbol)
                except Exception as e:
                    logger.warning(f"Could not get quote for {symbol}: {e}")
            
            kep_score = analyze_symbol_kep(
                symbol=symbol,
                wem_data=wem_data,
                ohlc_data=ohlc_data,
                quote_data=quote_data,
                proximity_threshold=proximity_threshold
            )
            results.append(kep_score)
            
        except Exception as e:
            logger.error(f"Error analyzing KEP for {symbol}: {e}")
            continue
    
    # Sort by score descending
    results.sort(key=lambda x: x.score, reverse=True)
    
    return results
