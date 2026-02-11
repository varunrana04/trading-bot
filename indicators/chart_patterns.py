# indicators/chart_patterns.py
"""
Classical Chart Pattern Detection
Detects triangles, head & shoulders, double tops/bottoms, wedges, etc.
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Tuple
from scipy.signal import argrelextrema


class ChartPatternDetector:
    """Detects classical chart patterns using price extrema"""
    
    def __init__(self, min_pattern_length=20):
        self.min_pattern_length = min_pattern_length
    
    def find_peaks_and_troughs(self, df: pd.DataFrame, order=5) -> Tuple[np.ndarray, np.ndarray]:
        """Find local maxima (peaks) and minima (troughs)"""
        highs = df['high'].values
        lows = df['low'].values
        
        # Find local maxima and minima
        peaks = argrelextrema(highs, np.greater, order=order)[0]
        troughs = argrelextrema(lows, np.less, order=order)[0]
        
        return peaks, troughs
    
    def detect_double_top(self, df: pd.DataFrame, peaks: np.ndarray) -> List[Dict]:
        """Detect Double Top pattern"""
        patterns = []
        
        if len(peaks) < 2:
            return patterns
        
        for i in range(len(peaks) - 1):
            peak1_idx = peaks[i]
            peak2_idx = peaks[i + 1]
            
            # Check if peaks are close in price (within 2%)
            peak1_price = df.iloc[peak1_idx]['high']
            peak2_price = df.iloc[peak2_idx]['high']
            
            price_diff = abs(peak1_price - peak2_price) / peak1_price
            
            if price_diff < 0.02:  # Peaks within 2% of each other
                # Find trough between peaks
                trough_between = df.iloc[peak1_idx:peak2_idx]['low'].min()
                trough_idx = df.iloc[peak1_idx:peak2_idx]['low'].idxmin()
                
                # Pattern strength based on how deep the trough is
                trough_depth = (peak1_price - trough_between) / peak1_price
                
                if trough_depth > 0.03:  # At least 3% pullback
                    confidence = min(trough_depth * 10, 1.0)
                    
                    # Expected target: depth of pattern below neckline
                    neckline = trough_between
                    target = neckline - (peak1_price - neckline)
                    
                    patterns.append({
                        'pattern': 'double_top',
                        'type': 'chart',
                        'direction': -1,  # Bearish
                        'confidence': confidence,
                        'index': peak2_idx,
                        'timestamp': df.iloc[peak2_idx].get('timestamp', peak2_idx),
                        'price': peak2_price,
                        'neckline': neckline,
                        'target': target,
                        'invalidation': peak2_price * 1.02
                    })
        
        return patterns
    
    def detect_double_bottom(self, df: pd.DataFrame, troughs: np.ndarray) -> List[Dict]:
        """Detect Double Bottom pattern"""
        patterns = []
        
        if len(troughs) < 2:
            return patterns
        
        for i in range(len(troughs) - 1):
            trough1_idx = troughs[i]
            trough2_idx = troughs[i + 1]
            
            # Check if troughs are close in price (within 2%)
            trough1_price = df.iloc[trough1_idx]['low']
            trough2_price = df.iloc[trough2_idx]['low']
            
            price_diff = abs(trough1_price - trough2_price) / trough1_price
            
            if price_diff < 0.02:
                # Find peak between troughs
                peak_between = df.iloc[trough1_idx:trough2_idx]['high'].max()
                peak_idx = df.iloc[trough1_idx:trough2_idx]['high'].idxmax()
                
                # Pattern strength
                peak_height = (peak_between - trough1_price) / trough1_price
                
                if peak_height > 0.03:
                    confidence = min(peak_height * 10, 1.0)
                    
                    # Expected target
                    neckline = peak_between
                    target = neckline + (neckline - trough1_price)
                    
                    patterns.append({
                        'pattern': 'double_bottom',
                        'type': 'chart',
                        'direction': 1,  # Bullish
                        'confidence': confidence,
                        'index': trough2_idx,
                        'timestamp': df.iloc[trough2_idx].get('timestamp', trough2_idx),
                        'price': trough2_price,
                        'neckline': neckline,
                        'target': target,
                        'invalidation': trough2_price * 0.98
                    })
        
        return patterns
    
    def detect_head_and_shoulders(self, df: pd.DataFrame, peaks: np.ndarray, troughs: np.ndarray) -> List[Dict]:
        """Detect Head and Shoulders pattern"""
        patterns = []
        
        if len(peaks) < 3:
            return patterns
        
        for i in range(len(peaks) - 2):
            left_shoulder_idx = peaks[i]
            head_idx = peaks[i + 1]
            right_shoulder_idx = peaks[i + 2]
            
            ls_price = df.iloc[left_shoulder_idx]['high']
            head_price = df.iloc[head_idx]['high']
            rs_price = df.iloc[right_shoulder_idx]['high']
            
            # Head should be highest
            if head_price > ls_price and head_price > rs_price:
                # Shoulders should be roughly equal (within 3%)
                shoulder_diff = abs(ls_price - rs_price) / ls_price
                
                if shoulder_diff < 0.03:
                    # Find neckline (troughs between shoulders and head)
                    left_trough = df.iloc[left_shoulder_idx:head_idx]['low'].min()
                    right_trough = df.iloc[head_idx:right_shoulder_idx]['low'].min()
                    neckline = (left_trough + right_trough) / 2
                    
                    # Pattern height
                    pattern_height = (head_price - neckline) / neckline
                    
                    if pattern_height > 0.05:  # At least 5% pattern
                        confidence = min(pattern_height * 5, 1.0)
                        
                        # Target
                        target = neckline - (head_price - neckline)
                        
                        patterns.append({
                            'pattern': 'head_and_shoulders',
                            'type': 'chart',
                            'direction': -1,  # Bearish
                            'confidence': confidence,
                            'index': right_shoulder_idx,
                            'timestamp': df.iloc[right_shoulder_idx].get('timestamp', right_shoulder_idx),
                            'price': rs_price,
                            'neckline': neckline,
                            'target': target,
                            'invalidation': head_price
                        })
        
        return patterns
    
    def detect_inverse_head_and_shoulders(self, df: pd.DataFrame, peaks: np.ndarray, troughs: np.ndarray) -> List[Dict]:
        """Detect Inverse Head and Shoulders pattern"""
        patterns = []
        
        if len(troughs) < 3:
            return patterns
        
        for i in range(len(troughs) - 2):
            left_shoulder_idx = troughs[i]
            head_idx = troughs[i + 1]
            right_shoulder_idx = troughs[i + 2]
            
            ls_price = df.iloc[left_shoulder_idx]['low']
            head_price = df.iloc[head_idx]['low']
            rs_price = df.iloc[right_shoulder_idx]['low']
            
            # Head should be lowest
            if head_price < ls_price and head_price < rs_price:
                # Shoulders should be roughly equal
                shoulder_diff = abs(ls_price - rs_price) / ls_price
                
                if shoulder_diff < 0.03:
                    # Find neckline
                    left_peak = df.iloc[left_shoulder_idx:head_idx]['high'].max()
                    right_peak = df.iloc[head_idx:right_shoulder_idx]['high'].max()
                    neckline = (left_peak + right_peak) / 2
                    
                    # Pattern height
                    pattern_height = (neckline - head_price) / head_price
                    
                    if pattern_height > 0.05:
                        confidence = min(pattern_height * 5, 1.0)
                        
                        # Target
                        target = neckline + (neckline - head_price)
                        
                        patterns.append({
                            'pattern': 'inverse_head_and_shoulders',
                            'type': 'chart',
                            'direction': 1,  # Bullish
                            'confidence': confidence,
                            'index': right_shoulder_idx,
                            'timestamp': df.iloc[right_shoulder_idx].get('timestamp', right_shoulder_idx),
                            'price': rs_price,
                            'neckline': neckline,
                            'target': target,
                            'invalidation': head_price
                        })
        
        return patterns
    
    def detect_triangle(self, df: pd.DataFrame, lookback=50) -> List[Dict]:
        """Detect Triangle patterns (ascending, descending, symmetrical)"""
        if len(df) < lookback:
            return []
        
        patterns = []
        recent_df = df.iloc[-lookback:]
        
        # Find trendlines
        highs = recent_df['high'].values
        lows = recent_df['low'].values
        indices = np.arange(len(recent_df))
        
        # Fit linear regression to highs and lows
        high_slope = np.polyfit(indices, highs, 1)[0]
        low_slope = np.polyfit(indices, lows, 1)[0]
        
        # Determine triangle type
        if abs(high_slope) < 0.0001 and low_slope > 0.0001:
            # Ascending triangle (flat top, rising bottom)
            pattern_type = 'ascending_triangle'
            direction = 1  # Bullish
        elif high_slope < -0.0001 and abs(low_slope) < 0.0001:
            # Descending triangle (falling top, flat bottom)
            pattern_type = 'descending_triangle'
            direction = -1  # Bearish
        elif high_slope < -0.0001 and low_slope > 0.0001:
            # Symmetrical triangle (converging)
            pattern_type = 'symmetrical_triangle'
            direction = 0  # Neutral (breakout direction determines)
        else:
            return []
        
        # Calculate confidence based on how well price respects trendlines
        price_range = highs.max() - lows.min()
        convergence = abs(high_slope - low_slope) * len(recent_df)
        confidence = min(convergence / price_range * 2, 1.0) if price_range > 0 else 0
        
        if confidence > 0.5:
            current_price = recent_df.iloc[-1]['close']
            patterns.append({
                'pattern': pattern_type,
                'type': 'chart',
                'direction': direction,
                'confidence': confidence,
                'index': len(df) - 1,
                'timestamp': recent_df.iloc[-1].get('timestamp', len(df) - 1),
                'price': current_price,
                'upper_trendline_slope': high_slope,
                'lower_trendline_slope': low_slope
            })
        
        return patterns


def detect_chart_patterns(df: pd.DataFrame, lookback=100) -> List[Dict]:
    """
    Detect all classical chart patterns
    
    Args:
        df: DataFrame with OHLC data
        lookback: Number of candles to analyze
    
    Returns:
        List of detected chart patterns
    """
    if len(df) < 20:
        return []
    
    detector = ChartPatternDetector()
    patterns = []
    
    # Analyze recent data
    recent_df = df.iloc[-lookback:] if len(df) > lookback else df
    
    # Find peaks and troughs
    peaks, troughs = detector.find_peaks_and_troughs(recent_df, order=5)
    
    # Adjust indices to match original dataframe
    offset = len(df) - len(recent_df)
    peaks = peaks + offset
    troughs = troughs + offset
    
    # Detect patterns
    patterns.extend(detector.detect_double_top(df, peaks))
    patterns.extend(detector.detect_double_bottom(df, troughs))
    patterns.extend(detector.detect_head_and_shoulders(df, peaks, troughs))
    patterns.extend(detector.detect_inverse_head_and_shoulders(df, peaks, troughs))
    patterns.extend(detector.detect_triangle(df, lookback=min(50, lookback)))
    
    return patterns
