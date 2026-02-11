"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                       UNIFIED SIGNAL GENERATOR                                ║
║                                                                               ║
║  Single source of truth for signal generation.                               ║
║  Used by both optimizer and stress test for consistent results.              ║
╚═══════════════════════════════════════════════════════════════════════════════╝

Author: Bot_Algo
Last Updated: January 2026
"""

import numpy as np
import pandas as pd
from typing import Dict


def generate_signals_unified(df: pd.DataFrame, params: Dict) -> pd.Series:
    """
    Generate trading signals with given parameters.
    
    UPDATED: Simple EMA cross + volatility filter (SOL's working approach).
    Skip complex RSI confluence - just trade the cross.
    
    Args:
        df: DataFrame with OHLCV data
        params: Dict with keys:
            - ema_fast: Fast EMA period
            - ema_slow: Slow EMA period (or ema_medium)
    
    Returns:
        pd.Series of signals: -1 (short), 0 (flat), 1 (long)
    """
    close = df['close'] if 'close' in df.columns else df['Close']
    
    # EMAs - simple fast/slow
    ema_fast = close.ewm(span=params.get('ema_fast', 8)).mean()
    ema_slow = close.ewm(span=params.get('ema_slow', params.get('ema_medium', 21))).mean()
    
    # Volatility filter: skip when volatility is extreme
    returns_std = close.pct_change().rolling(20).std() * np.sqrt(252) * 100
    avg_vol = returns_std.rolling(50).mean()
    vol_ratio = returns_std / avg_vol
    high_vol = vol_ratio > params.get('vol_threshold', 1.5)
    
    signals = pd.Series(0, index=df.index)
    position = 0
    
    start_idx = max(params.get('ema_slow', 50) + 5, 55)
    
    for i in range(start_idx, len(df)):
        # Skip high volatility - go flat
        if high_vol.iloc[i] if pd.notna(high_vol.iloc[i]) else False:
            position = 0
            signals.iloc[i] = 0
            continue
        
        # Simple EMA cross
        cross_up = ema_fast.iloc[i] > ema_slow.iloc[i] and ema_fast.iloc[i-1] <= ema_slow.iloc[i-1]
        cross_down = ema_fast.iloc[i] < ema_slow.iloc[i] and ema_fast.iloc[i-1] >= ema_slow.iloc[i-1]
        
        if cross_up:
            position = 1
        elif cross_down:
            position = -1
        
        signals.iloc[i] = position
    
    return signals


# Alias for backward compatibility
generate_signals_with_params = generate_signals_unified
