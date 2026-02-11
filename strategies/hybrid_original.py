"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                       ORIGINAL HYBRID STRATEGY                                ║
║                                                                               ║
║  The balanced version with 7/8 profitable periods.                           ║
║  Fewer trades but higher quality signals.                                    ║
╚═══════════════════════════════════════════════════════════════════════════════╝

Performance (unleveraged):
- Profitable Periods: 7/8 (88%)
- Trades per period: 2-11
- Best: Q4 2023 Bull Run (+33%)
- Worst: ETF 2024 (-11%)

Author: Bot_Algo
Last Updated: January 2026
"""

import numpy as np
import pandas as pd
from typing import Dict
import logging

logger = logging.getLogger("OriginalHybrid")


# ═══════════════════════════════════════════════════════════════════════════════
#                           ORIGINAL PARAMETERS (7/8 profitable)
# ═══════════════════════════════════════════════════════════════════════════════

ORIGINAL_PARAMS = {
    # Balanced EMAs
    'ema_fast': 8,
    'ema_medium': 21,
    'ema_slow': 50,
    
    # RSI with balanced thresholds
    'rsi_period': 7,
    'rsi_long': 50,          # Long when RSI > 50
    'rsi_short': 50,         # Short when RSI < 50
    
    # ATR
    'atr_period': 10,
    
    # Volatility filter
    'vol_extreme': 2.5,      # Skip when vol > 2.5x normal
    'vol_high': 1.8,         # Reduce size when vol > 1.8x normal
}


# ═══════════════════════════════════════════════════════════════════════════════
#                           INDICATORS
# ═══════════════════════════════════════════════════════════════════════════════

def calculate_indicators_original(df: pd.DataFrame, params: Dict = None) -> pd.DataFrame:
    """Calculate indicators for original hybrid strategy."""
    p = ORIGINAL_PARAMS.copy()
    if params:
        p.update(params)
        # Handle rsi_threshold from optimizer
        if 'rsi_threshold' in params and 'rsi_long' not in params:
            p['rsi_long'] = params['rsi_threshold']
            p['rsi_short'] = params['rsi_threshold']
    
    df = df.copy()
    
    close_col = 'close' if 'close' in df.columns else 'Close'
    high_col = 'high' if 'high' in df.columns else 'High'
    low_col = 'low' if 'low' in df.columns else 'Low'
    
    close = df[close_col]
    high = df[high_col]
    low = df[low_col]
    
    # EMAs
    df['ema_fast'] = close.ewm(span=p['ema_fast']).mean()
    df['ema_medium'] = close.ewm(span=p['ema_medium']).mean()
    df['ema_slow'] = close.ewm(span=p['ema_slow']).mean()
    
    # EMA alignment
    df['ema_bullish'] = (df['ema_fast'] > df['ema_medium']) & (df['ema_medium'] > df['ema_slow'])
    df['ema_bearish'] = (df['ema_fast'] < df['ema_medium']) & (df['ema_medium'] < df['ema_slow'])
    
    # EMA crosses
    df['ema_cross_up'] = (df['ema_fast'] > df['ema_medium']) & (df['ema_fast'].shift(1) <= df['ema_medium'].shift(1))
    df['ema_cross_down'] = (df['ema_fast'] < df['ema_medium']) & (df['ema_fast'].shift(1) >= df['ema_medium'].shift(1))
    
    # RSI
    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).ewm(span=p['rsi_period']).mean()
    loss = (-delta.where(delta < 0, 0)).ewm(span=p['rsi_period']).mean()
    rs = gain / loss.replace(0, np.nan)
    df['rsi'] = 100 - (100 / (1 + rs))
    
    df['rsi_bullish'] = df['rsi'] > p['rsi_long']
    df['rsi_bearish'] = df['rsi'] < p['rsi_short']
    
    # ATR
    tr1 = high - low
    tr2 = abs(high - close.shift())
    tr3 = abs(low - close.shift())
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    df['atr'] = tr.ewm(span=p['atr_period']).mean()
    
    # Volatility regime
    df['atr_avg'] = df['atr'].rolling(50).mean()
    df['vol_ratio'] = df['atr'] / df['atr_avg']
    df['vol_extreme'] = df['vol_ratio'] > p['vol_extreme']
    df['vol_high'] = df['vol_ratio'] > p['vol_high']
    
    # Momentum
    df['roc'] = close.pct_change(3) * 100
    
    # Breakouts
    df['high_20'] = high.rolling(20).max()
    df['low_20'] = low.rolling(20).min()
    df['breakout_up'] = close > df['high_20'].shift(1)
    df['breakout_down'] = close < df['low_20'].shift(1)
    
    return df


# ═══════════════════════════════════════════════════════════════════════════════
#                           SIGNAL GENERATION
# ═══════════════════════════════════════════════════════════════════════════════

def generate_original_signals(df: pd.DataFrame, params: Dict = None) -> pd.Series:
    """
    Generate signals using original hybrid logic (7/8 profitable).
    
    Entry:
    - EMA cross OR (EMA bullish + RSI bullish + breakout)
    
    Exit:
    - Opposite EMA cross
    - RSI flip against position
    - Strong reversal
    """
    p = ORIGINAL_PARAMS.copy()
    if params:
        p.update(params)
    
    df = calculate_indicators_original(df, p)
    
    close_col = 'close' if 'close' in df.columns else 'Close'
    
    signals = pd.Series(0, index=df.index)
    position = 0
    
    for i in range(2, len(df)):
        curr = df.iloc[i]
        prev = df.iloc[i-1]
        
        # Skip extreme volatility
        if curr['vol_extreme']:
            position = 0
            signals.iloc[i] = 0
            continue
        
        if position == 0:
            # LONG: EMA cross up OR (bullish EMA + bullish RSI + breakout)
            long_entry = (
                curr['ema_cross_up'] or 
                (curr['ema_bullish'] and curr['rsi_bullish'] and curr['breakout_up'])
            )
            
            # SHORT: EMA cross down OR (bearish EMA + bearish RSI + breakout)
            short_entry = (
                curr['ema_cross_down'] or 
                (curr['ema_bearish'] and curr['rsi_bearish'] and curr['breakout_down'])
            )
            
            if long_entry and not short_entry:
                position = 1
            elif short_entry and not long_entry:
                position = -1
        
        elif position == 1:  # Long position
            # Exit on EMA cross down
            exit_ema = curr['ema_cross_down']
            
            # Exit on RSI flip
            exit_rsi = not curr['rsi_bullish'] and prev['rsi_bullish']
            
            # Reverse on strong bearish
            if curr['ema_bearish'] and curr['rsi_bearish']:
                position = -1
            elif exit_ema or exit_rsi:
                position = 0
        
        elif position == -1:  # Short position
            # Exit on EMA cross up
            exit_ema = curr['ema_cross_up']
            
            # Exit on RSI flip
            exit_rsi = curr['rsi_bullish'] and not prev['rsi_bullish']
            
            # Reverse on strong bullish
            if curr['ema_bullish'] and curr['rsi_bullish']:
                position = 1
            elif exit_ema or exit_rsi:
                position = 0
        
        signals.iloc[i] = position
    
    return signals


# ═══════════════════════════════════════════════════════════════════════════════
#                           MAIN
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    print("=" * 65)
    print("ORIGINAL HYBRID STRATEGY - DEMO")
    print("=" * 65)
    
    try:
        from binance.client import Client
        client = Client("", "", {"timeout": 30})
        
        klines = client.futures_klines(symbol='BTCUSDT', interval='1d', limit=365)
        
        df = pd.DataFrame(klines, columns=[
            'timestamp', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_volume', 'trades', 'taker_buy_base',
            'taker_buy_quote', 'ignore'
        ])
        
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = df[col].astype(float)
        
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df = df.set_index('timestamp')
        
        print(f"\nFetched {len(df)} days of BTCUSDT data")
        
    except Exception as e:
        print(f"Using synthetic data: {e}")
        np.random.seed(42)
        days = 365
        dates = pd.date_range('2024-01-01', periods=days, freq='D')
        base = 45000
        prices = base * np.cumprod(1 + np.random.randn(days) * 0.02)
        df = pd.DataFrame({
            'open': prices,
            'high': prices * (1 + np.abs(np.random.randn(days)) * 0.01),
            'low': prices * (1 - np.abs(np.random.randn(days)) * 0.01),
            'close': prices * (1 + np.random.randn(days) * 0.005),
            'volume': np.random.randint(10000, 100000, days)
        }, index=dates)
    
    # Generate signals
    signals = generate_original_signals(df)
    
    # Count trades
    signal_changes = signals.diff().abs().fillna(0)
    num_entries = int((signal_changes > 0).sum())
    trades_per_day = num_entries / len(df)
    
    print(f"\n--- Signal Statistics ---")
    print(f"Total Entries/Exits: {num_entries} ({trades_per_day:.2f}/day)")
    print(f"Long Days: {(signals == 1).sum()}")
    print(f"Short Days: {(signals == -1).sum()}")
    print(f"Flat Days: {(signals == 0).sum()}")
    
    # Calculate returns
    returns = df['close'].pct_change()
    strategy_returns = signals.shift(1) * returns
    strategy_returns = strategy_returns.dropna()
    
    total_return = (1 + strategy_returns).prod() - 1
    buy_hold = (df['close'].iloc[-1] / df['close'].iloc[0]) - 1
    
    print(f"\n--- Performance ---")
    print(f"Total Return: {total_return:+.2%}")
    print(f"Buy & Hold: {buy_hold:+.2%}")
    print(f"Outperformance: {(total_return - buy_hold):+.2%}")
    
    print("\n" + "=" * 65)
