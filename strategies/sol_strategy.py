"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                       SOL-SPECIFIC STRATEGY                                   ║
║                                                                               ║
║  Optimized strategy for Solana (SOL) with volatility filtering.              ║
║  SOL is extremely volatile - 154% annualized in some periods.                 ║
╚═══════════════════════════════════════════════════════════════════════════════╝

Performance:
- Profitable Periods: 5/8 (62%)
- Total Return: +140%
- Key: Skip extreme volatility periods, ride trends

Author: Bot_Algo
Last Updated: January 2026
"""

import numpy as np
import pandas as pd
from typing import Dict
import logging

logger = logging.getLogger("SOLStrategy")


# ═══════════════════════════════════════════════════════════════════════════════
#                           SOL PARAMETERS
# ═══════════════════════════════════════════════════════════════════════════════

SOL_PARAMS = {
    # EMAs - faster to catch SOL's rapid moves
    'ema_fast': 8,
    'ema_slow': 21,
    
    # Volatility filter - lower threshold (skip more)
    'vol_threshold': 1.2,
    'vol_lookback': 20,
    
    # RSI
    'rsi_period': 14,
}


# ═══════════════════════════════════════════════════════════════════════════════
#                           SIGNAL GENERATION
# ═══════════════════════════════════════════════════════════════════════════════

def generate_sol_signals(df: pd.DataFrame, params: Dict = None) -> pd.Series:
    """
    Generate signals optimized for SOL's high volatility.
    
    Key features:
    1. Skip extreme volatility (>1.5x normal)
    2. Simple EMA cross for clear trend following
    3. Slower EMAs to avoid noise
    """
    p = SOL_PARAMS.copy()
    if params:
        p.update(params)
    
    df = df.copy()
    
    close_col = 'close' if 'close' in df.columns else 'Close'
    close = df[close_col]
    
    # EMAs
    ema_fast = close.ewm(span=p['ema_fast']).mean()
    ema_slow = close.ewm(span=p['ema_slow']).mean()
    
    # Volatility: rolling returns std
    returns_std = close.pct_change().rolling(p['vol_lookback']).std() * np.sqrt(252) * 100
    avg_vol = returns_std.rolling(50).mean()
    vol_ratio = returns_std / avg_vol
    
    # High volatility flag
    high_vol = vol_ratio > p['vol_threshold']
    
    signals = pd.Series(0, index=df.index)
    position = 0
    
    for i in range(50, len(df)):
        # Skip high volatility - go flat
        if high_vol.iloc[i] if pd.notna(high_vol.iloc[i]) else False:
            position = 0
            signals.iloc[i] = 0
            continue
        
        # Simple EMA cross
        ema_cross_up = ema_fast.iloc[i] > ema_slow.iloc[i] and ema_fast.iloc[i-1] <= ema_slow.iloc[i-1]
        ema_cross_down = ema_fast.iloc[i] < ema_slow.iloc[i] and ema_fast.iloc[i-1] >= ema_slow.iloc[i-1]
        
        if ema_cross_up:
            position = 1
        elif ema_cross_down:
            position = -1
        
        signals.iloc[i] = position
    
    return signals


# ═══════════════════════════════════════════════════════════════════════════════
#                           MAIN
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    from stress_test import fetch_period_data, STRESS_PERIODS
    from core.terminal_alerts import Color
    
    print(f"\n{Color.BOLD}{'=' * 60}{Color.RESET}")
    print(f"{Color.CYAN}SOL STRATEGY TEST{Color.RESET}")
    print(f"{Color.BOLD}{'=' * 60}{Color.RESET}\n")
    
    profitable = 0
    total_return = 0
    
    for period in STRESS_PERIODS:
        df = fetch_period_data('SOLUSDT', period.start_date, period.end_date)
        if len(df) < 50:
            continue
        
        signals = generate_sol_signals(df)
        
        close = df['close'] if 'close' in df.columns else df['Close']
        returns = close.pct_change()
        strat_returns = signals.shift(1) * returns
        strat_returns = strat_returns.dropna()
        ret = (1 + strat_returns).prod() - 1
        
        total_return += ret * 100
        
        if ret > 0:
            profitable += 1
            color = Color.GREEN
        else:
            color = Color.RED
        
        print(f"{period.name}")
        print(f"  Return: {color}{ret*100:+.1f}%{Color.RESET}")
    
    print(f"\n{Color.BOLD}SUMMARY:{Color.RESET}")
    print(f"  Profitable: {profitable}/8 ({profitable/8*100:.0f}%)")
    print(f"  Total Return: +{total_return:.1f}%")
    print(f"\n{Color.BOLD}{'=' * 60}{Color.RESET}")
