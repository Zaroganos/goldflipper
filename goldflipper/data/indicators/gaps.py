"""
Gap Detector

Detects unfilled price gaps from daily OHLC data.
Gaps are significant price discontinuities that often act as support/resistance.
Used for identifying Key Entry Points (KEPs) in the trading strategy.
"""

import pandas as pd
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Gap:
    """Represents a price gap"""
    gap_type: str  # 'up' or 'down'
    date: datetime
    top: float
    bottom: float
    size_pct: float
    filled: bool = False
    fill_date: Optional[datetime] = None
    partial_fill_pct: float = 0.0
    
    @property
    def midpoint(self) -> float:
        """Get the midpoint of the gap"""
        return (self.top + self.bottom) / 2
    
    @property
    def size(self) -> float:
        """Get the absolute size of the gap"""
        return self.top - self.bottom
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'type': self.gap_type,
            'date': self.date.isoformat() if hasattr(self.date, 'isoformat') else str(self.date),
            'top': self.top,
            'bottom': self.bottom,
            'midpoint': self.midpoint,
            'size': self.size,
            'size_pct': self.size_pct,
            'filled': self.filled,
            'fill_date': self.fill_date.isoformat() if self.fill_date and hasattr(self.fill_date, 'isoformat') else None,
            'partial_fill_pct': self.partial_fill_pct
        }


class GapDetector:
    """Detect unfilled price gaps from daily OHLC data.
    
    A gap occurs when:
    - Gap Up: Current open > Previous high (bullish gap)
    - Gap Down: Current open < Previous low (bearish gap)
    
    Gaps are significant because:
    - They represent areas of price where no trading occurred
    - Price often returns to "fill" the gap
    - Unfilled gaps can act as support (gap up) or resistance (gap down)
    """
    
    DEFAULT_MIN_GAP_PCT = 0.5  # Minimum 0.5% gap to be considered significant
    
    @staticmethod
    def find_gaps(
        daily_ohlc: pd.DataFrame, 
        min_gap_pct: float = 0.5,
        include_filled: bool = False
    ) -> List[Gap]:
        """
        Find gaps in price action.
        
        Args:
            daily_ohlc: DataFrame with open, high, low, close columns
            min_gap_pct: Minimum gap size as percentage (default 0.5%)
            include_filled: If True, include filled gaps in results
            
        Returns:
            List of Gap objects (unfilled by default, or all if include_filled=True)
        """
        if daily_ohlc is None or len(daily_ohlc) < 2:
            return []
        
        # Normalize column names to lowercase
        df = daily_ohlc.copy()
        df.columns = df.columns.str.lower()
        
        # Ensure we have required columns
        required = ['open', 'high', 'low', 'close']
        if not all(col in df.columns for col in required):
            raise ValueError(f"DataFrame must have columns: {required}")
        
        gaps = []
        
        for i in range(1, len(df)):
            prev = df.iloc[i-1]
            curr = df.iloc[i]
            
            # Get the date/index for this gap
            if hasattr(df.index, 'to_pydatetime'):
                gap_date = df.index[i]
            else:
                gap_date = df.index[i]
            
            # Gap up: current open > previous high
            if curr['open'] > prev['high']:
                gap_size = curr['open'] - prev['high']
                gap_size_pct = (gap_size / prev['close']) * 100
                
                if gap_size_pct >= min_gap_pct:
                    gap = Gap(
                        gap_type='up',
                        date=gap_date,
                        top=curr['open'],
                        bottom=prev['high'],
                        size_pct=gap_size_pct,
                        filled=False
                    )
                    gaps.append(gap)
            
            # Gap down: current open < previous low
            elif curr['open'] < prev['low']:
                gap_size = prev['low'] - curr['open']
                gap_size_pct = (gap_size / prev['close']) * 100
                
                if gap_size_pct >= min_gap_pct:
                    gap = Gap(
                        gap_type='down',
                        date=gap_date,
                        top=prev['low'],
                        bottom=curr['open'],
                        size_pct=gap_size_pct,
                        filled=False
                    )
                    gaps.append(gap)
        
        # Check which gaps have been filled
        GapDetector._mark_filled_gaps(gaps, df)
        
        # Return based on include_filled preference
        if include_filled:
            return gaps
        else:
            return [g for g in gaps if not g.filled]
    
    @staticmethod
    def _mark_filled_gaps(gaps: List[Gap], df: pd.DataFrame) -> None:
        """
        Mark gaps as filled based on subsequent price action.
        
        A gap is filled when:
        - Gap Up: Price drops to touch the gap bottom (previous high)
        - Gap Down: Price rises to touch the gap top (previous low)
        """
        for gap in gaps:
            # Find the index of the gap date
            try:
                gap_idx = df.index.get_loc(gap.date)
            except KeyError:
                continue
            
            # Get subsequent price action
            subsequent = df.iloc[gap_idx:]
            
            if len(subsequent) <= 1:
                continue
            
            if gap.gap_type == 'up':
                # Gap filled if price drops to gap bottom
                min_low = subsequent['low'].min()
                if min_low <= gap.bottom:
                    gap.filled = True
                    # Find when it was filled
                    fill_mask = subsequent['low'] <= gap.bottom
                    if fill_mask.any():
                        fill_idx = fill_mask.idxmax()
                        gap.fill_date = fill_idx
                else:
                    # Calculate partial fill percentage
                    penetration = gap.top - min_low
                    gap.partial_fill_pct = min(100, max(0, (penetration / gap.size) * 100))
            else:
                # Gap down: filled if price rises to gap top
                max_high = subsequent['high'].max()
                if max_high >= gap.top:
                    gap.filled = True
                    # Find when it was filled
                    fill_mask = subsequent['high'] >= gap.top
                    if fill_mask.any():
                        fill_idx = fill_mask.idxmax()
                        gap.fill_date = fill_idx
                else:
                    # Calculate partial fill percentage
                    penetration = max_high - gap.bottom
                    gap.partial_fill_pct = min(100, max(0, (penetration / gap.size) * 100))
    
    @staticmethod
    def get_nearest_gap(
        gaps: List[Gap], 
        current_price: float,
        threshold_pct: float = 2.0
    ) -> Optional[Dict[str, Any]]:
        """
        Find the nearest unfilled gap to the current price.
        
        Args:
            gaps: List of Gap objects
            current_price: Current stock price
            threshold_pct: Maximum distance to consider (default 2%)
            
        Returns:
            Dict with nearest gap info or None if none within threshold
        """
        unfilled = [g for g in gaps if not g.filled]
        
        if not unfilled:
            return None
        
        nearest = None
        min_distance_pct = float('inf')
        
        for gap in unfilled:
            # Calculate distance to gap zone
            if current_price > gap.top:
                # Price is above gap
                distance = current_price - gap.top
            elif current_price < gap.bottom:
                # Price is below gap
                distance = gap.bottom - current_price
            else:
                # Price is within gap
                distance = 0
            
            distance_pct = (distance / current_price) * 100
            
            if distance_pct <= threshold_pct and distance_pct < min_distance_pct:
                min_distance_pct = distance_pct
                position = 'above' if current_price > gap.top else 'below' if current_price < gap.bottom else 'within'
                nearest = {
                    'gap': gap.to_dict(),
                    'distance_pct': distance_pct,
                    'position': position,
                    'support_level': gap.bottom if gap.gap_type == 'up' else None,
                    'resistance_level': gap.top if gap.gap_type == 'down' else None
                }
        
        return nearest
    
    @staticmethod
    def get_gap_levels_for_kep(
        gaps: List[Gap],
        current_price: float,
        max_gaps: int = 3
    ) -> Dict[str, float]:
        """
        Get gap levels formatted for KEP analysis.
        
        Args:
            gaps: List of Gap objects
            current_price: Current stock price
            max_gaps: Maximum number of gaps to include
            
        Returns:
            Dict with gap levels for KEP scoring
        """
        unfilled = [g for g in gaps if not g.filled]
        
        if not unfilled:
            return {}
        
        # Sort by proximity to current price
        def proximity(gap):
            mid = gap.midpoint
            return abs(current_price - mid)
        
        sorted_gaps = sorted(unfilled, key=proximity)[:max_gaps]
        
        levels = {}
        for i, gap in enumerate(sorted_gaps, 1):
            prefix = f'gap_{i}'
            levels[f'{prefix}_top'] = gap.top
            levels[f'{prefix}_bottom'] = gap.bottom
            levels[f'{prefix}_mid'] = gap.midpoint
            levels[f'{prefix}_type'] = gap.gap_type
        
        return levels
    
    @staticmethod
    def analyze_gaps_summary(
        daily_ohlc: pd.DataFrame,
        current_price: float,
        min_gap_pct: float = 0.5
    ) -> Dict[str, Any]:
        """
        Comprehensive gap analysis for a symbol.
        
        Args:
            daily_ohlc: DataFrame with OHLC data
            current_price: Current stock price
            min_gap_pct: Minimum gap size percentage
            
        Returns:
            Dict with gap analysis summary
        """
        all_gaps = GapDetector.find_gaps(daily_ohlc, min_gap_pct, include_filled=True)
        unfilled = [g for g in all_gaps if not g.filled]
        filled = [g for g in all_gaps if g.filled]
        
        # Separate by type
        unfilled_up = [g for g in unfilled if g.gap_type == 'up']
        unfilled_down = [g for g in unfilled if g.gap_type == 'down']
        
        # Find nearest gaps
        nearest_support = None
        nearest_resistance = None
        
        for gap in unfilled_up:
            if current_price > gap.bottom:
                if nearest_support is None or gap.bottom > nearest_support:
                    nearest_support = gap.bottom
        
        for gap in unfilled_down:
            if current_price < gap.top:
                if nearest_resistance is None or gap.top < nearest_resistance:
                    nearest_resistance = gap.top
        
        return {
            'total_gaps': len(all_gaps),
            'unfilled_count': len(unfilled),
            'filled_count': len(filled),
            'unfilled_up_gaps': len(unfilled_up),
            'unfilled_down_gaps': len(unfilled_down),
            'nearest_gap_support': nearest_support,
            'nearest_gap_resistance': nearest_resistance,
            'unfilled_gaps': [g.to_dict() for g in unfilled],
            'kep_levels': GapDetector.get_gap_levels_for_kep(all_gaps, current_price)
        }
