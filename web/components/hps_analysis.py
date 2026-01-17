"""
HPS (High Probability Setups) Analysis Component

Validates KEPs with technical evidence to identify high-probability trade setups.
Part of the WEM → KEP → HPS workflow for the Options Swing strategy.

HPS Evidence Indicators (from Playbook §5):
- Retest (2nd or 3rd touch of level)
- RSI Zone (Oversold <30 for calls, Overbought >70 for puts)
- 200 EMA Position
- 9/21 EMA Crossover
- Volume Confirmation
- Candlestick Patterns
- MACD Divergence
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class TradeDirection(Enum):
    """Trade direction recommendation"""
    CALLS = "CALLS"
    PUTS = "PUTS"
    NEUTRAL = "NEUTRAL"


class HPSRecommendation(Enum):
    """HPS trade recommendation"""
    TRADE = "TRADE"      # Score >= 3: Take the trade
    WATCH = "WATCH"      # Score 2: Monitor for confirmation
    SKIP = "SKIP"        # Score < 2: Not enough evidence


@dataclass
class HPSEvidence:
    """Single piece of HPS evidence"""
    evidence_type: str
    met: bool
    value: Any
    weight: float = 1.0
    direction_hint: Optional[str] = None  # 'CALLS', 'PUTS', or None
    details: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'type': self.evidence_type,
            'met': self.met,
            'value': self.value,
            'weight': self.weight,
            'direction_hint': self.direction_hint,
            'details': self.details
        }


@dataclass
class TradeSetup:
    """Recommended trade setup parameters"""
    direction: str  # 'CALLS' or 'PUTS'
    reason: str
    entry_strike_delta: Tuple[float, float]  # e.g., (0.3, 0.5)
    dte_range: Tuple[int, int]  # e.g., (14, 21)
    stop_loss_pct: float  # e.g., 0.29 for 29%
    take_profit_pct: float  # e.g., 0.45 for 45%
    r_ratio: float
    confidence: str  # 'HIGH', 'MEDIUM', 'LOW'
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'direction': self.direction,
            'reason': self.reason,
            'entry_strike_delta': list(self.entry_strike_delta),
            'dte_range': list(self.dte_range),
            'stop_loss_pct': self.stop_loss_pct,
            'take_profit_pct': self.take_profit_pct,
            'r_ratio': self.r_ratio,
            'confidence': self.confidence
        }


@dataclass
class HPSResult:
    """Complete HPS analysis result"""
    symbol: str
    current_price: float
    kep_score: int
    kep_rating: str
    hps_score: float
    max_hps_score: float
    recommendation: str  # 'TRADE', 'WATCH', 'SKIP'
    direction: str  # 'CALLS', 'PUTS', 'NEUTRAL'
    evidence: List[HPSEvidence]
    trade_setup: Optional[TradeSetup] = None
    kep_data: Optional[Dict] = None
    analysis_timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'symbol': self.symbol,
            'current_price': self.current_price,
            'kep_score': self.kep_score,
            'kep_rating': self.kep_rating,
            'hps_score': self.hps_score,
            'max_hps_score': self.max_hps_score,
            'score_pct': round(self.hps_score / self.max_hps_score * 100, 1) if self.max_hps_score > 0 else 0,
            'recommendation': self.recommendation,
            'direction': self.direction,
            'evidence': [e.to_dict() for e in self.evidence],
            'evidence_met_count': sum(1 for e in self.evidence if e.met),
            'trade_setup': self.trade_setup.to_dict() if self.trade_setup else None,
            'analysis_timestamp': self.analysis_timestamp.isoformat()
        }


class HPSAnalyzer:
    """
    Analyzes High Probability Setups by validating KEP candidates with technical evidence.
    
    HPS Evidence Criteria (from Playbook):
    - Retest: 2nd or 3rd touch of level (+2 weight)
    - RSI Zone: Oversold (<30) or Overbought (>70) (+1 weight)
    - 200 EMA Position: Price at or near 200 EMA (+1 weight)
    - 9/21 EMA Cross: Recent crossover (+1 weight)
    - Volume Confirmation: Above average volume (+1 weight)
    - Candlestick Pattern: Reversal pattern at level (+1 weight)
    - MACD Divergence: Bullish/bearish divergence (+1 weight)
    """
    
    # Evidence weights
    EVIDENCE_WEIGHTS = {
        'retest': 2.0,
        'rsi_zone': 1.0,
        'ema_200_position': 1.0,
        'ema_crossover': 1.0,
        'volume_confirmation': 1.0,
        'candlestick_pattern': 1.0,
        'macd_divergence': 1.0,
    }
    
    # Trade parameters from Playbook
    DEFAULT_STOP_LOSS_PCT = 0.29  # 29%
    DEFAULT_TAKE_PROFIT_PCT = 0.45  # 45% for 1:1.5 R-ratio
    SHORT_SWING_DTE = (14, 21)
    LONG_SWING_DTE = (28, 35)
    STRIKE_DELTA_RANGE = (0.3, 0.5)
    
    def __init__(self):
        self.max_score = sum(self.EVIDENCE_WEIGHTS.values())
    
    def calculate_hps_score(
        self,
        kep_data: Dict[str, Any],
        indicators: Dict[str, Any],
        ohlc_data: pd.DataFrame
    ) -> HPSResult:
        """
        Score HPS evidence for a KEP candidate.
        
        Args:
            kep_data: KEP analysis data (from KEPScore.to_dict())
            indicators: Technical indicator values
            ohlc_data: DataFrame with OHLC data
            
        Returns:
            HPSResult with evidence score and trade recommendation
        """
        symbol = kep_data.get('symbol', 'UNKNOWN')
        current_price = kep_data.get('current_price', 0)
        kep_score = kep_data.get('score', 0)
        kep_rating = kep_data.get('rating', 'LOW')
        
        evidence_list = []
        total_score = 0.0
        
        # 1. RSI Zone Check
        rsi_evidence = self._check_rsi_zone(indicators)
        evidence_list.append(rsi_evidence)
        if rsi_evidence.met:
            total_score += rsi_evidence.weight
        
        # 2. 200 EMA Position Check
        ema_evidence = self._check_ema_200_position(current_price, indicators)
        evidence_list.append(ema_evidence)
        if ema_evidence.met:
            total_score += ema_evidence.weight
        
        # 3. 9/21 EMA Crossover Check
        crossover_evidence = self._check_ema_crossover(indicators)
        evidence_list.append(crossover_evidence)
        if crossover_evidence.met:
            total_score += crossover_evidence.weight
        
        # 4. Volume Confirmation Check
        volume_evidence = self._check_volume_confirmation(ohlc_data)
        evidence_list.append(volume_evidence)
        if volume_evidence.met:
            total_score += volume_evidence.weight
        
        # 5. MACD Divergence Check
        macd_evidence = self._check_macd_divergence(indicators)
        evidence_list.append(macd_evidence)
        if macd_evidence.met:
            total_score += macd_evidence.weight
        
        # 6. Retest Check (uses OHLC data to detect level touches)
        retest_evidence = self._check_retest(kep_data, ohlc_data)
        evidence_list.append(retest_evidence)
        if retest_evidence.met:
            total_score += retest_evidence.weight
        
        # 7. Candlestick Pattern Check
        candle_evidence = self._check_candlestick_pattern(ohlc_data)
        evidence_list.append(candle_evidence)
        if candle_evidence.met:
            total_score += candle_evidence.weight
        
        # Determine recommendation
        if total_score >= 3.0:
            recommendation = HPSRecommendation.TRADE.value
        elif total_score >= 2.0:
            recommendation = HPSRecommendation.WATCH.value
        else:
            recommendation = HPSRecommendation.SKIP.value
        
        # Determine direction
        direction = self._infer_direction(evidence_list, kep_data)
        
        # Generate trade setup if recommendation is TRADE
        trade_setup = None
        if recommendation == HPSRecommendation.TRADE.value:
            trade_setup = self._generate_trade_setup(
                direction=direction,
                evidence_list=evidence_list,
                kep_data=kep_data,
                current_price=current_price
            )
        
        return HPSResult(
            symbol=symbol,
            current_price=current_price,
            kep_score=kep_score,
            kep_rating=kep_rating,
            hps_score=total_score,
            max_hps_score=self.max_score,
            recommendation=recommendation,
            direction=direction,
            evidence=evidence_list,
            trade_setup=trade_setup,
            kep_data=kep_data
        )
    
    def _check_rsi_zone(self, indicators: Dict[str, Any]) -> HPSEvidence:
        """Check if RSI is in oversold or overbought zone."""
        rsi = indicators.get('rsi_current')
        
        if rsi is None:
            return HPSEvidence(
                evidence_type='RSI Zone',
                met=False,
                value=None,
                weight=self.EVIDENCE_WEIGHTS['rsi_zone'],
                details="RSI data not available"
            )
        
        # Handle Series
        if hasattr(rsi, 'iloc'):
            rsi = float(rsi.iloc[-1] if len(rsi) > 0 else rsi)
        
        if rsi < 30:
            return HPSEvidence(
                evidence_type='RSI Zone',
                met=True,
                value=round(rsi, 1),
                weight=self.EVIDENCE_WEIGHTS['rsi_zone'],
                direction_hint='CALLS',
                details=f"RSI Oversold ({rsi:.1f} < 30)"
            )
        elif rsi > 70:
            return HPSEvidence(
                evidence_type='RSI Zone',
                met=True,
                value=round(rsi, 1),
                weight=self.EVIDENCE_WEIGHTS['rsi_zone'],
                direction_hint='PUTS',
                details=f"RSI Overbought ({rsi:.1f} > 70)"
            )
        else:
            return HPSEvidence(
                evidence_type='RSI Zone',
                met=False,
                value=round(rsi, 1),
                weight=self.EVIDENCE_WEIGHTS['rsi_zone'],
                details=f"RSI Neutral ({rsi:.1f})"
            )
    
    def _check_ema_200_position(self, current_price: float, indicators: Dict[str, Any]) -> HPSEvidence:
        """Check if price is at or near 200 EMA."""
        ema_200 = indicators.get('ema_200')
        
        if ema_200 is None:
            return HPSEvidence(
                evidence_type='200 EMA Position',
                met=False,
                value=None,
                weight=self.EVIDENCE_WEIGHTS['ema_200_position'],
                details="200 EMA data not available"
            )
        
        # Handle Series
        if hasattr(ema_200, 'iloc'):
            ema_200 = float(ema_200.iloc[-1] if len(ema_200) > 0 else ema_200)
        
        distance_pct = abs(current_price - ema_200) / current_price
        
        if distance_pct < 0.01:  # Within 1%
            direction = 'CALLS' if current_price > ema_200 else 'PUTS'
            return HPSEvidence(
                evidence_type='200 EMA Position',
                met=True,
                value=round(ema_200, 2),
                weight=self.EVIDENCE_WEIGHTS['ema_200_position'],
                direction_hint=direction,
                details=f"Price at 200 EMA (${ema_200:.2f}, {distance_pct*100:.1f}% away)"
            )
        else:
            return HPSEvidence(
                evidence_type='200 EMA Position',
                met=False,
                value=round(ema_200, 2),
                weight=self.EVIDENCE_WEIGHTS['ema_200_position'],
                details=f"Price {distance_pct*100:.1f}% from 200 EMA (${ema_200:.2f})"
            )
    
    def _check_ema_crossover(self, indicators: Dict[str, Any]) -> HPSEvidence:
        """Check for recent 9/21 EMA crossover."""
        crossover_bullish = indicators.get('9_21_crossover_bullish')
        crossover_up = indicators.get('9_21_crossover_up')
        crossover_down = indicators.get('9_21_crossover_down')
        
        # Handle Series
        if hasattr(crossover_up, 'iloc'):
            crossover_up = bool(crossover_up.iloc[-1]) if len(crossover_up) > 0 else False
        if hasattr(crossover_down, 'iloc'):
            crossover_down = bool(crossover_down.iloc[-1]) if len(crossover_down) > 0 else False
        
        if crossover_up:
            return HPSEvidence(
                evidence_type='9/21 EMA Crossover',
                met=True,
                value='Bullish Cross',
                weight=self.EVIDENCE_WEIGHTS['ema_crossover'],
                direction_hint='CALLS',
                details="9 EMA crossed above 21 EMA (Bullish)"
            )
        elif crossover_down:
            return HPSEvidence(
                evidence_type='9/21 EMA Crossover',
                met=True,
                value='Bearish Cross',
                weight=self.EVIDENCE_WEIGHTS['ema_crossover'],
                direction_hint='PUTS',
                details="9 EMA crossed below 21 EMA (Bearish)"
            )
        else:
            return HPSEvidence(
                evidence_type='9/21 EMA Crossover',
                met=False,
                value='No Cross',
                weight=self.EVIDENCE_WEIGHTS['ema_crossover'],
                details="No recent EMA crossover detected"
            )
    
    def _check_volume_confirmation(self, ohlc_data: pd.DataFrame) -> HPSEvidence:
        """Check if recent volume is above average."""
        if ohlc_data is None or len(ohlc_data) < 20:
            return HPSEvidence(
                evidence_type='Volume Confirmation',
                met=False,
                value=None,
                weight=self.EVIDENCE_WEIGHTS['volume_confirmation'],
                details="Insufficient data for volume analysis"
            )
        
        df = ohlc_data.copy()
        df.columns = df.columns.str.lower()
        
        if 'volume' not in df.columns:
            return HPSEvidence(
                evidence_type='Volume Confirmation',
                met=False,
                value=None,
                weight=self.EVIDENCE_WEIGHTS['volume_confirmation'],
                details="Volume data not available"
            )
        
        avg_volume = df['volume'].rolling(20).mean().iloc[-1]
        current_volume = df['volume'].iloc[-1]
        volume_ratio = current_volume / avg_volume if avg_volume > 0 else 0
        
        if volume_ratio >= 1.2:  # 20% above average
            return HPSEvidence(
                evidence_type='Volume Confirmation',
                met=True,
                value=round(volume_ratio, 2),
                weight=self.EVIDENCE_WEIGHTS['volume_confirmation'],
                details=f"Volume {volume_ratio:.1f}x average (Above average)"
            )
        else:
            return HPSEvidence(
                evidence_type='Volume Confirmation',
                met=False,
                value=round(volume_ratio, 2),
                weight=self.EVIDENCE_WEIGHTS['volume_confirmation'],
                details=f"Volume {volume_ratio:.1f}x average (Below threshold)"
            )
    
    def _check_macd_divergence(self, indicators: Dict[str, Any]) -> HPSEvidence:
        """Check for MACD divergence or crossover."""
        macd_crossover = indicators.get('macd_crossover')
        macd_trend = indicators.get('macd_trend')
        histogram = indicators.get('macd_histogram')
        
        # Check for crossover
        if macd_crossover:
            if hasattr(macd_crossover, 'iloc'):
                macd_crossover = macd_crossover.iloc[-1] if len(macd_crossover) > 0 else None
            
            if macd_crossover == 'bullish':
                return HPSEvidence(
                    evidence_type='MACD Signal',
                    met=True,
                    value='Bullish Crossover',
                    weight=self.EVIDENCE_WEIGHTS['macd_divergence'],
                    direction_hint='CALLS',
                    details="MACD bullish crossover"
                )
            elif macd_crossover == 'bearish':
                return HPSEvidence(
                    evidence_type='MACD Signal',
                    met=True,
                    value='Bearish Crossover',
                    weight=self.EVIDENCE_WEIGHTS['macd_divergence'],
                    direction_hint='PUTS',
                    details="MACD bearish crossover"
                )
        
        # Check histogram momentum
        if histogram is not None:
            if hasattr(histogram, 'iloc') and len(histogram) >= 2:
                curr_hist = histogram.iloc[-1]
                prev_hist = histogram.iloc[-2]
                
                if curr_hist > 0 and curr_hist > prev_hist:
                    return HPSEvidence(
                        evidence_type='MACD Signal',
                        met=True,
                        value='Bullish Momentum',
                        weight=self.EVIDENCE_WEIGHTS['macd_divergence'],
                        direction_hint='CALLS',
                        details="MACD histogram increasing (bullish)"
                    )
                elif curr_hist < 0 and curr_hist < prev_hist:
                    return HPSEvidence(
                        evidence_type='MACD Signal',
                        met=True,
                        value='Bearish Momentum',
                        weight=self.EVIDENCE_WEIGHTS['macd_divergence'],
                        direction_hint='PUTS',
                        details="MACD histogram decreasing (bearish)"
                    )
        
        return HPSEvidence(
            evidence_type='MACD Signal',
            met=False,
            value='Neutral',
            weight=self.EVIDENCE_WEIGHTS['macd_divergence'],
            details="No significant MACD signal"
        )
    
    def _check_retest(self, kep_data: Dict[str, Any], ohlc_data: pd.DataFrame) -> HPSEvidence:
        """Check if price has tested a key level multiple times."""
        if ohlc_data is None or len(ohlc_data) < 5:
            return HPSEvidence(
                evidence_type='Level Retest',
                met=False,
                value=0,
                weight=self.EVIDENCE_WEIGHTS['retest'],
                details="Insufficient data for retest analysis"
            )
        
        df = ohlc_data.copy()
        df.columns = df.columns.str.lower()
        
        # Get matched factors from KEP
        matched_factors = kep_data.get('matched_factors', [])
        if not matched_factors:
            return HPSEvidence(
                evidence_type='Level Retest',
                met=False,
                value=0,
                weight=self.EVIDENCE_WEIGHTS['retest'],
                details="No KEP levels to check for retest"
            )
        
        # Check how many times price touched the nearest level in recent bars
        nearest_level = kep_data.get('nearest_level', {})
        level_price = nearest_level.get('price') if nearest_level else None
        
        if not level_price:
            level_price = matched_factors[0].get('level') if matched_factors else None
        
        if not level_price:
            return HPSEvidence(
                evidence_type='Level Retest',
                met=False,
                value=0,
                weight=self.EVIDENCE_WEIGHTS['retest'],
                details="No level price to analyze"
            )
        
        # Count touches (within 0.5% of level)
        threshold = level_price * 0.005
        recent_bars = df.tail(10)
        touches = 0
        
        for _, bar in recent_bars.iterrows():
            if abs(bar['low'] - level_price) <= threshold or abs(bar['high'] - level_price) <= threshold:
                touches += 1
        
        if touches >= 2:
            return HPSEvidence(
                evidence_type='Level Retest',
                met=True,
                value=touches,
                weight=self.EVIDENCE_WEIGHTS['retest'],
                details=f"Level tested {touches} times (2nd/3rd entry opportunity)"
            )
        else:
            return HPSEvidence(
                evidence_type='Level Retest',
                met=False,
                value=touches,
                weight=self.EVIDENCE_WEIGHTS['retest'],
                details=f"Level tested {touches} time(s) (waiting for retest)"
            )
    
    def _check_candlestick_pattern(self, ohlc_data: pd.DataFrame) -> HPSEvidence:
        """Check for reversal candlestick patterns."""
        if ohlc_data is None or len(ohlc_data) < 3:
            return HPSEvidence(
                evidence_type='Candlestick Pattern',
                met=False,
                value=None,
                weight=self.EVIDENCE_WEIGHTS['candlestick_pattern'],
                details="Insufficient data for pattern analysis"
            )
        
        df = ohlc_data.copy()
        df.columns = df.columns.str.lower()
        
        last = df.iloc[-1]
        prev = df.iloc[-2]
        
        body = abs(last['close'] - last['open'])
        range_size = last['high'] - last['low']
        
        if range_size == 0:
            return HPSEvidence(
                evidence_type='Candlestick Pattern',
                met=False,
                value=None,
                weight=self.EVIDENCE_WEIGHTS['candlestick_pattern'],
                details="Invalid candle data"
            )
        
        body_pct = body / range_size
        upper_wick = last['high'] - max(last['open'], last['close'])
        lower_wick = min(last['open'], last['close']) - last['low']
        
        # Hammer (bullish reversal)
        if lower_wick >= 2 * body and upper_wick <= body * 0.5 and last['close'] > last['open']:
            return HPSEvidence(
                evidence_type='Candlestick Pattern',
                met=True,
                value='Hammer',
                weight=self.EVIDENCE_WEIGHTS['candlestick_pattern'],
                direction_hint='CALLS',
                details="Hammer pattern detected (bullish reversal)"
            )
        
        # Shooting Star (bearish reversal)
        if upper_wick >= 2 * body and lower_wick <= body * 0.5 and last['close'] < last['open']:
            return HPSEvidence(
                evidence_type='Candlestick Pattern',
                met=True,
                value='Shooting Star',
                weight=self.EVIDENCE_WEIGHTS['candlestick_pattern'],
                direction_hint='PUTS',
                details="Shooting Star pattern detected (bearish reversal)"
            )
        
        # Bullish Engulfing
        if (last['close'] > last['open'] and 
            prev['close'] < prev['open'] and
            last['open'] < prev['close'] and 
            last['close'] > prev['open']):
            return HPSEvidence(
                evidence_type='Candlestick Pattern',
                met=True,
                value='Bullish Engulfing',
                weight=self.EVIDENCE_WEIGHTS['candlestick_pattern'],
                direction_hint='CALLS',
                details="Bullish Engulfing pattern detected"
            )
        
        # Bearish Engulfing
        if (last['close'] < last['open'] and 
            prev['close'] > prev['open'] and
            last['open'] > prev['close'] and 
            last['close'] < prev['open']):
            return HPSEvidence(
                evidence_type='Candlestick Pattern',
                met=True,
                value='Bearish Engulfing',
                weight=self.EVIDENCE_WEIGHTS['candlestick_pattern'],
                direction_hint='PUTS',
                details="Bearish Engulfing pattern detected"
            )
        
        # Doji (indecision, but can signal reversal)
        if body_pct < 0.1:
            return HPSEvidence(
                evidence_type='Candlestick Pattern',
                met=True,
                value='Doji',
                weight=self.EVIDENCE_WEIGHTS['candlestick_pattern'] * 0.5,  # Half weight for doji
                details="Doji pattern detected (potential reversal)"
            )
        
        return HPSEvidence(
            evidence_type='Candlestick Pattern',
            met=False,
            value=None,
            weight=self.EVIDENCE_WEIGHTS['candlestick_pattern'],
            details="No significant pattern detected"
        )
    
    def _infer_direction(self, evidence_list: List[HPSEvidence], kep_data: Dict[str, Any]) -> str:
        """Infer trade direction from evidence and KEP data."""
        calls_score = 0
        puts_score = 0
        
        # Count direction hints from evidence
        for ev in evidence_list:
            if ev.met and ev.direction_hint:
                if ev.direction_hint == 'CALLS':
                    calls_score += ev.weight
                elif ev.direction_hint == 'PUTS':
                    puts_score += ev.weight
        
        # Also consider KEP direction bias
        kep_direction = kep_data.get('direction_bias')
        if kep_direction == 'CALLS':
            calls_score += 1
        elif kep_direction == 'PUTS':
            puts_score += 1
        
        if calls_score > puts_score + 0.5:
            return TradeDirection.CALLS.value
        elif puts_score > calls_score + 0.5:
            return TradeDirection.PUTS.value
        else:
            return TradeDirection.NEUTRAL.value
    
    def _generate_trade_setup(
        self,
        direction: str,
        evidence_list: List[HPSEvidence],
        kep_data: Dict[str, Any],
        current_price: float
    ) -> TradeSetup:
        """Generate trade setup parameters based on evidence."""
        # Build reason string
        reasons = []
        for ev in evidence_list:
            if ev.met:
                reasons.append(ev.evidence_type)
        reason_str = ', '.join(reasons[:3])
        if len(reasons) > 3:
            reason_str += f" +{len(reasons)-3} more"
        
        # Calculate confidence
        met_count = sum(1 for ev in evidence_list if ev.met)
        if met_count >= 5:
            confidence = 'HIGH'
        elif met_count >= 3:
            confidence = 'MEDIUM'
        else:
            confidence = 'LOW'
        
        # Use playbook parameters
        return TradeSetup(
            direction=direction,
            reason=reason_str,
            entry_strike_delta=self.STRIKE_DELTA_RANGE,
            dte_range=self.SHORT_SWING_DTE,
            stop_loss_pct=self.DEFAULT_STOP_LOSS_PCT,
            take_profit_pct=self.DEFAULT_TAKE_PROFIT_PCT,
            r_ratio=1.5,
            confidence=confidence
        )


def analyze_hps_for_kep(
    kep_data: Dict[str, Any],
    ohlc_data: pd.DataFrame
) -> HPSResult:
    """
    Convenience function to analyze HPS for a single KEP.
    
    Args:
        kep_data: KEP analysis data (from KEPScore.to_dict())
        ohlc_data: DataFrame with OHLC data
        
    Returns:
        HPSResult with analysis
    """
    from goldflipper.data.indicators import RSICalculator, EMACalculator, MACDCalculator, MarketData
    
    analyzer = HPSAnalyzer()
    
    # Normalize OHLC
    df = ohlc_data.copy()
    df.columns = df.columns.str.lower()
    
    # Calculate indicators
    indicators = {}
    
    try:
        # RSI
        if len(df) >= 14:
            rsi_value = RSICalculator.calculate_from_prices(df['close'], period=14)
            indicators['rsi_current'] = rsi_value
    except Exception as e:
        logger.warning(f"Error calculating RSI: {e}")
    
    try:
        # EMA
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
            indicators.update(ema_result)
    except Exception as e:
        logger.warning(f"Error calculating EMA: {e}")
    
    try:
        # MACD
        if len(df) >= 26:
            market_data = MarketData(
                high=df['high'],
                low=df['low'],
                close=df['close'],
                volume=df.get('volume', pd.Series([0] * len(df))),
                period=26
            )
            macd_calc = MACDCalculator(market_data)
            macd_result = macd_calc.calculate()
            indicators['macd_histogram'] = macd_result.get('histogram')
            indicators['macd_crossover'] = macd_result.get('crossover')
            indicators['macd_trend'] = macd_result.get('trend')
    except Exception as e:
        logger.warning(f"Error calculating MACD: {e}")
    
    return analyzer.calculate_hps_score(kep_data, indicators, df)


def batch_analyze_hps(
    kep_results: List[Dict[str, Any]],
    ohlc_provider: callable
) -> List[HPSResult]:
    """
    Analyze HPS for multiple KEP candidates.
    
    Args:
        kep_results: List of KEP data dicts
        ohlc_provider: Function that takes symbol and returns OHLC DataFrame
        
    Returns:
        List of HPSResult objects sorted by recommendation and score
    """
    results = []
    
    for kep_data in kep_results:
        symbol = kep_data.get('symbol')
        if not symbol:
            continue
        
        try:
            ohlc_data = ohlc_provider(symbol)
            if ohlc_data is None or len(ohlc_data) == 0:
                continue
            
            hps_result = analyze_hps_for_kep(kep_data, ohlc_data)
            results.append(hps_result)
            
        except Exception as e:
            logger.error(f"Error analyzing HPS for {symbol}: {e}")
            continue
    
    # Sort by recommendation priority (TRADE > WATCH > SKIP) then by score
    priority = {'TRADE': 0, 'WATCH': 1, 'SKIP': 2}
    results.sort(key=lambda x: (priority.get(x.recommendation, 3), -x.hps_score))
    
    return results
