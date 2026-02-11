# indicators/pattern_recognition.py
"""
Comprehensive Chart Pattern Recognition
Detects both candlestick patterns and classical chart patterns
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Tuple


class CandlestickPatternDetector:
    """Detects candlestick patterns using price action rules"""
    
    def __init__(self, body_min_ratio=0.6, wick_max_ratio=0.3):
        self.body_min_ratio = body_min_ratio
        self.wick_max_ratio = wick_max_ratio
    
    def detect_doji(self, row) -> Tuple[bool, float]:
        """Detect Doji pattern - small body, long wicks"""
        body = abs(row['close'] - row['open'])
        total_range = row['high'] - row['low']
        
        if total_range == 0:
            return False, 0.0
        
        body_ratio = body / total_range
        
        # Doji: body is less than 10% of total range
        is_doji = body_ratio < 0.1
        confidence = 1.0 - (body_ratio / 0.1) if is_doji else 0.0
        
        return is_doji, min(confidence, 1.0)
    
    def detect_hammer(self, df, idx) -> Tuple[bool, float]:
        """Detect Hammer - small body at top, long lower wick"""
        if idx < 1:
            return False, 0.0
        
        row = df.iloc[idx]
        body = abs(row['close'] - row['open'])
        total_range = row['high'] - row['low']
        lower_wick = min(row['open'], row['close']) - row['low']
        upper_wick = row['high'] - max(row['open'], row['close'])
        
        if total_range == 0:
            return False, 0.0
        
        # Hammer criteria:
        # 1. Lower wick is at least 2x the body
        # 2. Upper wick is very small
        # 3. Appears in downtrend
        lower_wick_ratio = lower_wick / total_range
        body_ratio = body / total_range
        upper_wick_ratio = upper_wick / total_range
        
        is_hammer = (
            lower_wick >= body * 2 and
            upper_wick_ratio < 0.1 and
            body_ratio < 0.3 and
            lower_wick_ratio > 0.6
        )
        
        # Check if in downtrend (price declining over last 5 candles)
        if is_hammer and idx >= 5:
            trend = df.iloc[idx-5:idx]['close'].mean() > row['close']
            if not trend:
                is_hammer = False
        
        confidence = lower_wick_ratio * 1.2 if is_hammer else 0.0
        return is_hammer, min(confidence, 1.0)
    
    def detect_shooting_star(self, df, idx) -> Tuple[bool, float]:
        """Detect Shooting Star - small body at bottom, long upper wick"""
        if idx < 1:
            return False, 0.0
        
        row = df.iloc[idx]
        body = abs(row['close'] - row['open'])
        total_range = row['high'] - row['low']
        lower_wick = min(row['open'], row['close']) - row['low']
        upper_wick = row['high'] - max(row['open'], row['close'])
        
        if total_range == 0:
            return False, 0.0
        
        upper_wick_ratio = upper_wick / total_range
        body_ratio = body / total_range
        lower_wick_ratio = lower_wick / total_range
        
        is_shooting_star = (
            upper_wick >= body * 2 and
            lower_wick_ratio < 0.1 and
            body_ratio < 0.3 and
            upper_wick_ratio > 0.6
        )
        
        # Check if in uptrend
        if is_shooting_star and idx >= 5:
            trend = df.iloc[idx-5:idx]['close'].mean() < row['close']
            if not trend:
                is_shooting_star = False
        
        confidence = upper_wick_ratio * 1.2 if is_shooting_star else 0.0
        return is_shooting_star, min(confidence, 1.0)
    
    def detect_engulfing(self, df, idx) -> Tuple[str, float]:
        """Detect Bullish/Bearish Engulfing pattern"""
        if idx < 1:
            return None, 0.0
        
        prev = df.iloc[idx-1]
        curr = df.iloc[idx]
        
        prev_body = abs(prev['close'] - prev['open'])
        curr_body = abs(curr['close'] - curr['open'])
        
        # Bullish Engulfing
        if (prev['close'] < prev['open'] and  # Previous was bearish
            curr['close'] > curr['open'] and  # Current is bullish
            curr['open'] < prev['close'] and  # Opens below previous close
            curr['close'] > prev['open']):    # Closes above previous open
            
            engulfing_ratio = curr_body / prev_body if prev_body > 0 else 0
            confidence = min(engulfing_ratio / 2, 1.0)
            return 'bullish_engulfing', confidence
        
        # Bearish Engulfing
        if (prev['close'] > prev['open'] and  # Previous was bullish
            curr['close'] < curr['open'] and  # Current is bearish
            curr['open'] > prev['close'] and  # Opens above previous close
            curr['close'] < prev['open']):    # Closes below previous open
            
            engulfing_ratio = curr_body / prev_body if prev_body > 0 else 0
            confidence = min(engulfing_ratio / 2, 1.0)
            return 'bearish_engulfing', confidence
        
        return None, 0.0
    
    def detect_three_soldiers(self, df, idx) -> Tuple[bool, float]:
        """Detect Three White Soldiers - three consecutive bullish candles"""
        if idx < 2:
            return False, 0.0
        
        candles = df.iloc[idx-2:idx+1]
        
        # All three must be bullish
        all_bullish = all(candles['close'] > candles['open'])
        
        # Each closes higher than previous
        ascending = (candles.iloc[1]['close'] > candles.iloc[0]['close'] and
                    candles.iloc[2]['close'] > candles.iloc[1]['close'])
        
        # Each opens within previous candle's body
        opens_within_body = (
            candles.iloc[1]['open'] >= candles.iloc[0]['open'] and
            candles.iloc[1]['open'] <= candles.iloc[0]['close'] and
            candles.iloc[2]['open'] >= candles.iloc[1]['open'] and
            candles.iloc[2]['open'] <= candles.iloc[1]['close']
        )
        
        is_three_soldiers = all_bullish and ascending and opens_within_body
        
        # Confidence based on candle sizes
        if is_three_soldiers:
            avg_body = candles.apply(lambda r: abs(r['close'] - r['open']), axis=1).mean()
            avg_range = (candles['high'] - candles['low']).mean()
            confidence = avg_body / avg_range if avg_range > 0 else 0
        else:
            confidence = 0.0
        
        return is_three_soldiers, min(confidence, 1.0)
    
    def detect_three_crows(self, df, idx) -> Tuple[bool, float]:
        """Detect Three Black Crows - three consecutive bearish candles"""
        if idx < 2:
            return False, 0.0
        
        candles = df.iloc[idx-2:idx+1]
        
        # All three must be bearish
        all_bearish = all(candles['close'] < candles['open'])
        
        # Each closes lower than previous
        descending = (candles.iloc[1]['close'] < candles.iloc[0]['close'] and
                     candles.iloc[2]['close'] < candles.iloc[1]['close'])
        
        # Each opens within previous candle's body
        opens_within_body = (
            candles.iloc[1]['open'] <= candles.iloc[0]['open'] and
            candles.iloc[1]['open'] >= candles.iloc[0]['close'] and
            candles.iloc[2]['open'] <= candles.iloc[1]['open'] and
            candles.iloc[2]['open'] >= candles.iloc[1]['close']
        )
        
        is_three_crows = all_bearish and descending and opens_within_body
        
        if is_three_crows:
            avg_body = candles.apply(lambda r: abs(r['close'] - r['open']), axis=1).mean()
            avg_range = (candles['high'] - candles['low']).mean()
            confidence = avg_body / avg_range if avg_range > 0 else 0
        else:
            confidence = 0.0
        
        return is_three_crows, min(confidence, 1.0)
    
    def detect_morning_star(self, df, idx) -> Tuple[bool, float]:
        """Detect Morning Star - bullish reversal pattern"""
        if idx < 2:
            return False, 0.0
        
        first = df.iloc[idx-2]
        second = df.iloc[idx-1]
        third = df.iloc[idx]
        
        # First candle: Large bearish
        first_bearish = first['close'] < first['open']
        first_body = abs(first['close'] - first['open'])
        
        # Second candle: Small body (star)
        second_body = abs(second['close'] - second['open'])
        second_is_small = second_body < first_body * 0.3
        
        # Third candle: Large bullish
        third_bullish = third['close'] > third['open']
        third_body = abs(third['close'] - third['open'])
        third_closes_high = third['close'] > (first['open'] + first['close']) / 2
        
        is_morning_star = (
            first_bearish and
            second_is_small and
            third_bullish and
            third_closes_high
        )
        
        if is_morning_star:
            confidence = min((third_body / first_body) * 0.7, 1.0)
        else:
            confidence = 0.0
        
        return is_morning_star, confidence
    
    def detect_evening_star(self, df, idx) -> Tuple[bool, float]:
        """Detect Evening Star - bearish reversal pattern"""
        if idx < 2:
            return False, 0.0
        
        first = df.iloc[idx-2]
        second = df.iloc[idx-1]
        third = df.iloc[idx]
        
        # First candle: Large bullish
        first_bullish = first['close'] > first['open']
        first_body = abs(first['close'] - first['open'])
        
        # Second candle: Small body (star)
        second_body = abs(second['close'] - second['open'])
        second_is_small = second_body < first_body * 0.3
        
        # Third candle: Large bearish
        third_bearish = third['close'] < third['open']
        third_body = abs(third['close'] - third['open'])
        third_closes_low = third['close'] < (first['open'] + first['close']) / 2
        
        is_evening_star = (
            first_bullish and
            second_is_small and
            third_bearish and
            third_closes_low
        )
        
        if is_evening_star:
            confidence = min((third_body / first_body) * 0.7, 1.0)
        else:
            confidence = 0.0
        
        return is_evening_star, confidence


def detect_candlestick_patterns(df: pd.DataFrame, lookback=100) -> List[Dict]:
    """
    Detect all candlestick patterns in the dataframe
    
    Returns:
        List of detected patterns with metadata
    """
    detector = CandlestickPatternDetector()
    patterns = []
    
    # Only check recent candles to save time
    start_idx = max(0, len(df) - lookback)
    
    for idx in range(start_idx, len(df)):
        row = df.iloc[idx]
        
        # Doji
        is_doji, conf = detector.detect_doji(row)
        if is_doji and conf > 0.6:
            patterns.append({
                'pattern': 'doji',
                'type': 'candlestick',
                'direction': 0,  # Neutral
                'confidence': conf,
                'index': idx,
                'timestamp': row.get('timestamp', idx),
                'price': row['close']
            })
        
        # Hammer
        is_hammer, conf = detector.detect_hammer(df, idx)
        if is_hammer and conf > 0.6:
            patterns.append({
                'pattern': 'hammer',
                'type': 'candlestick',
                'direction': 1,  # Bullish
                'confidence': conf,
                'index': idx,
                'timestamp': row.get('timestamp', idx),
                'price': row['close']
            })
        
        # Shooting Star
        is_shooting, conf = detector.detect_shooting_star(df, idx)
        if is_shooting and conf > 0.6:
            patterns.append({
                'pattern': 'shooting_star',
                'type': 'candlestick',
                'direction': -1,  # Bearish
                'confidence': conf,
                'index': idx,
                'timestamp': row.get('timestamp', idx),
                'price': row['close']
            })
        
        # Engulfing
        eng_type, conf = detector.detect_engulfing(df, idx)
        if eng_type and conf > 0.6:
            patterns.append({
                'pattern': eng_type,
                'type': 'candlestick',
                'direction': 1 if 'bullish' in eng_type else -1,
                'confidence': conf,
                'index': idx,
                'timestamp': row.get('timestamp', idx),
                'price': row['close']
            })
        
        # Three Soldiers
        is_soldiers, conf = detector.detect_three_soldiers(df, idx)
        if is_soldiers and conf > 0.6:
            patterns.append({
                'pattern': 'three_white_soldiers',
                'type': 'candlestick',
                'direction': 1,
                'confidence': conf,
                'index': idx,
                'timestamp': row.get('timestamp', idx),
                'price': row['close']
            })
        
        # Three Crows
        is_crows, conf = detector.detect_three_crows(df, idx)
        if is_crows and conf > 0.6:
            patterns.append({
                'pattern': 'three_black_crows',
                'type': 'candlestick',
                'direction': -1,
                'confidence': conf,
                'index': idx,
                'timestamp': row.get('timestamp', idx),
                'price': row['close']
            })
        
        # Morning Star
        is_morning, conf = detector.detect_morning_star(df, idx)
        if is_morning and conf > 0.6:
            patterns.append({
                'pattern': 'morning_star',
                'type': 'candlestick',
                'direction': 1,
                'confidence': conf,
                'index': idx,
                'timestamp': row.get('timestamp', idx),
                'price': row['close']
            })
        
        # Evening Star
        is_evening, conf = detector.detect_evening_star(df, idx)
        if is_evening and conf > 0.6:
            patterns.append({
                'pattern': 'evening_star',
                'type': 'candlestick',
                'direction': -1,
                'confidence': conf,
                'index': idx,
                'timestamp': row.get('timestamp', idx),
                'price': row['close']
            })
    
    return patterns


def detect_chart_patterns(df: pd.DataFrame, lookback=100) -> List[Dict]:
    """
    Detect classical chart patterns (triangles, H&S, double tops, etc.)
    """
    from .chart_patterns import detect_chart_patterns as detect_classical_patterns
    return detect_classical_patterns(df, lookback)


def detect_all_patterns(df: pd.DataFrame, lookback=100) -> List[Dict]:
    """
    Detect all patterns (candlestick + chart patterns)
    
    Args:
        df: DataFrame with OHLC data
        lookback: Number of candles to analyze
    
    Returns:
        List of all detected patterns
    """
    candlestick_patterns = detect_candlestick_patterns(df, lookback)
    chart_patterns = detect_chart_patterns(df, lookback)
    
    all_patterns = candlestick_patterns + chart_patterns
    
    # Sort by index (most recent first)
    all_patterns.sort(key=lambda x: x['index'], reverse=True)
    
    return all_patterns


def aggregate_pattern_signals(patterns: List[Dict], min_confidence=0.7) -> Dict:
    """
    Aggregate multiple pattern signals into a single trading signal
    
    Returns:
        {
            'signal': 1 (buy), -1 (sell), or 0 (neutral),
            'confidence': overall confidence,
            'pattern_count': number of patterns detected,
            'details': pattern breakdown
        }
    """
    if not patterns:
        return {
            'signal': 0,
            'confidence': 0.0,
            'pattern_count': 0,
            'details': []
        }
    
    # Filter by minimum confidence
    strong_patterns = [p for p in patterns if p['confidence'] >= min_confidence]
    
    if not strong_patterns:
        return {
            'signal': 0,
            'confidence': 0.0,
            'pattern_count': 0,
            'details': []
        }
    
    # Calculate weighted signal
    total_weight = 0
    weighted_signal = 0
    
    for pattern in strong_patterns:
        weight = pattern['confidence']
        weighted_signal += pattern['direction'] * weight
        total_weight += weight
    
    # Normalize
    if total_weight > 0:
        avg_signal = weighted_signal / total_weight
        overall_confidence = total_weight / len(strong_patterns)
    else:
        avg_signal = 0
        overall_confidence = 0
    
    # Convert to discrete signal
    if avg_signal > 0.3:
        signal = 1  # Bullish
    elif avg_signal < -0.3:
        signal = -1  # Bearish
    else:
        signal = 0  # Neutral
    
    return {
        'signal': signal,
        'confidence': min(overall_confidence, 1.0),
        'pattern_count': len(strong_patterns),
        'details': strong_patterns
    }
