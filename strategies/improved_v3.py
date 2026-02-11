"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                       IMPROVED STRATEGIES V3                                  ║
║                                                                               ║
║  Enhanced strategies with higher trade frequency for 24/7 crypto trading.    ║
║  Target: 1-5 complete trades per day (2-10 entries/exits)                    ║
╚═══════════════════════════════════════════════════════════════════════════════╝

Improvements:
- Mean Reversion: Looser RSI/BB conditions, faster entry
- Trend Following: Add volatility filter to reduce losses in V-recoveries
- Both: More trades, adaptive position sizing

Author: Bot_Algo
Last Updated: January 2026
"""

import numpy as np
import pandas as pd
from typing import Dict, Tuple
from dataclasses import dataclass
import logging

logger = logging.getLogger("ImprovedStrategies")


# ═══════════════════════════════════════════════════════════════════════════════
#                           VOLATILITY FILTER
# ═══════════════════════════════════════════════════════════════════════════════

def calculate_volatility_regime(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add volatility regime classification.
    
    Regimes:
    - low: ATR < 0.7x normal (quiet market)
    - normal: 0.7x - 1.5x (good for trading)
    - high: 1.5x - 2.5x (reduce size)
    - extreme: > 2.5x (don't trade or hedge only)
    """
    df = df.copy()
    
    close_col = 'close' if 'close' in df.columns else 'Close'
    high_col = 'high' if 'high' in df.columns else 'High'
    low_col = 'low' if 'low' in df.columns else 'Low'
    
    # ATR calculation
    high = df[high_col]
    low = df[low_col]
    close = df[close_col]
    
    tr1 = high - low
    tr2 = abs(high - close.shift())
    tr3 = abs(low - close.shift())
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    
    df['ATR'] = tr.rolling(14).mean()
    df['ATR_pct'] = df['ATR'] / close * 100  # As percentage
    
    # Rolling ATR average for comparison
    df['ATR_avg'] = df['ATR'].rolling(50).mean()
    df['volatility_ratio'] = df['ATR'] / df['ATR_avg']
    
    # Classify volatility
    conditions = [
        df['volatility_ratio'] < 0.7,
        (df['volatility_ratio'] >= 0.7) & (df['volatility_ratio'] < 1.5),
        (df['volatility_ratio'] >= 1.5) & (df['volatility_ratio'] < 2.5),
        df['volatility_ratio'] >= 2.5
    ]
    choices = ['low', 'normal', 'high', 'extreme']
    df['vol_regime'] = np.select(conditions, choices, default='normal')
    
    # Position multiplier based on volatility
    mult_conditions = [
        df['volatility_ratio'] < 0.7,
        (df['volatility_ratio'] >= 0.7) & (df['volatility_ratio'] < 1.5),
        (df['volatility_ratio'] >= 1.5) & (df['volatility_ratio'] < 2.5),
        df['volatility_ratio'] >= 2.5
    ]
    mult_choices = [1.2, 1.0, 0.5, 0.0]  # 0 = no trade in extreme vol
    df['vol_multiplier'] = np.select(mult_conditions, mult_choices, default=1.0)
    
    return df


# ═══════════════════════════════════════════════════════════════════════════════
#                           IMPROVED MEAN REVERSION
# ═══════════════════════════════════════════════════════════════════════════════

MEAN_REVERSION_PARAMS = {
    'bb_period': 14,         # Shorter period = faster signals
    'bb_std': 1.5,           # Tighter bands = more triggers
    'rsi_period': 7,         # Faster RSI
    'rsi_oversold': 35,      # Looser = more trades
    'rsi_overbought': 65,    # Looser = more trades
    'adx_threshold': 30,     # Higher = trade in more conditions
    'bb_pct_low': 0.15,      # Enter long when BB% < 15%
    'bb_pct_high': 0.85,     # Enter short when BB% > 85%
}


def generate_mean_reversion_v3(df: pd.DataFrame, params: Dict = None) -> pd.Series:
    """
    Improved mean reversion with more trades.
    
    Changes from V1:
    - Use BB% instead of requiring price below band
    - Looser RSI thresholds
    - Faster entry/exit
    - Don't require strict ADX (just adjust size)
    """
    p = MEAN_REVERSION_PARAMS.copy()
    if params:
        p.update(params)
    
    df = df.copy()
    df = calculate_volatility_regime(df)
    
    close_col = 'close' if 'close' in df.columns else 'Close'
    close = df[close_col]
    
    # Bollinger Bands
    ma = close.rolling(p['bb_period']).mean()
    std = close.rolling(p['bb_period']).std()
    bb_upper = ma + (p['bb_std'] * std)
    bb_lower = ma - (p['bb_std'] * std)
    bb_pct = (close - bb_lower) / (bb_upper - bb_lower)
    
    # RSI
    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(p['rsi_period']).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(p['rsi_period']).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    
    # Entry conditions (OR based, not AND)
    # Long: low BB% OR oversold RSI
    long_entry = (bb_pct < p['bb_pct_low']) | (rsi < p['rsi_oversold'])
    
    # Short: high BB% OR overbought RSI  
    short_entry = (bb_pct > p['bb_pct_high']) | (rsi > p['rsi_overbought'])
    
    # Exit: price near middle band (40-60%)
    exit_zone = (bb_pct > 0.4) & (bb_pct < 0.6)
    
    # Block trades in extreme volatility
    can_trade = df['vol_multiplier'] > 0
    
    # Generate signals
    signals = pd.Series(0, index=df.index)
    position = 0
    
    for i in range(1, len(df)):
        if can_trade.iloc[i]:
            if position == 0:
                if long_entry.iloc[i]:
                    position = 1
                elif short_entry.iloc[i]:
                    position = -1
            elif position == 1:
                if exit_zone.iloc[i] or short_entry.iloc[i]:
                    position = -1 if short_entry.iloc[i] else 0
            elif position == -1:
                if exit_zone.iloc[i] or long_entry.iloc[i]:
                    position = 1 if long_entry.iloc[i] else 0
        else:
            position = 0  # Exit in extreme volatility
        
        signals.iloc[i] = position
    
    return signals


# ═══════════════════════════════════════════════════════════════════════════════
#                           IMPROVED TREND FOLLOWER
# ═══════════════════════════════════════════════════════════════════════════════

TREND_PARAMS = {
    'ema_fast': 8,           # Fast EMA
    'ema_slow': 21,          # Slow EMA
    'atr_period': 14,        # ATR period
    'atr_mult': 1.5,         # ATR multiplier for breakout
    'adx_period': 14,        # ADX period
    'adx_threshold': 20,     # Min ADX for trend
    'rsi_period': 14,        # RSI for confirmation
}


def generate_trend_v3(df: pd.DataFrame, params: Dict = None) -> pd.Series:
    """
    Improved trend following with volatility filter.
    
    Changes from V2:
    - Add volatility filter to reduce position/exit in extreme vol
    - Use EMA crossover + momentum confirmation
    - Faster signals with shorter EMAs
    """
    p = TREND_PARAMS.copy()
    if params:
        p.update(params)
    
    df = df.copy()
    df = calculate_volatility_regime(df)
    
    close_col = 'close' if 'close' in df.columns else 'Close'
    high_col = 'high' if 'high' in df.columns else 'High'
    low_col = 'low' if 'low' in df.columns else 'Low'
    
    close = df[close_col]
    
    # EMAs
    ema_fast = close.ewm(span=p['ema_fast']).mean()
    ema_slow = close.ewm(span=p['ema_slow']).mean()
    
    # EMA crossover
    ema_bull = ema_fast > ema_slow
    ema_bear = ema_fast < ema_slow
    
    # Momentum (ROC)
    roc = close.pct_change(5) * 100
    
    # ATR breakout
    high = df[high_col]
    low = df[low_col]
    tr = pd.concat([high - low, 
                    abs(high - close.shift()), 
                    abs(low - close.shift())], axis=1).max(axis=1)
    atr = tr.rolling(p['atr_period']).mean()
    
    upper_break = close > close.shift(1).rolling(20).max()
    lower_break = close < close.shift(1).rolling(20).min()
    
    # ADX
    plus_dm = high.diff()
    minus_dm = -low.diff()
    plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0)
    minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0)
    
    smoothed_tr = tr.rolling(14).sum()
    plus_di = 100 * (plus_dm.rolling(14).sum() / smoothed_tr)
    minus_di = 100 * (minus_dm.rolling(14).sum() / smoothed_tr)
    
    dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di + 0.001)
    adx = dx.rolling(14).mean()
    
    trending = adx > p['adx_threshold']
    
    # Entry conditions
    long_entry = ema_bull & (roc > 0) & (trending | upper_break)
    short_entry = ema_bear & (roc < 0) & (trending | lower_break)
    
    # Volatility filter
    vol_mult = df['vol_multiplier']
    can_trade = vol_mult > 0
    reduce_size = vol_mult < 1  # Flag for position sizing
    
    # Generate signals
    signals = pd.Series(0, index=df.index)
    position = 0
    
    for i in range(1, len(df)):
        if not can_trade.iloc[i]:
            # Exit in extreme volatility
            position = 0
        elif position == 0:
            if long_entry.iloc[i]:
                position = 1
            elif short_entry.iloc[i]:
                position = -1
        elif position == 1:
            if short_entry.iloc[i]:
                position = -1
            elif not (ema_bull.iloc[i] and roc.iloc[i] > -2):
                position = 0  # Exit if trend weakens
        elif position == -1:
            if long_entry.iloc[i]:
                position = 1
            elif not (ema_bear.iloc[i] and roc.iloc[i] < 2):
                position = 0  # Exit if trend weakens
        
        signals.iloc[i] = position
    
    return signals


# ═══════════════════════════════════════════════════════════════════════════════
#                           COMBINED STRATEGY
# ═══════════════════════════════════════════════════════════════════════════════

def generate_adaptive_signals(df: pd.DataFrame) -> Tuple[pd.Series, pd.DataFrame]:
    """
    Adaptive strategy that switches between trend and mean reversion
    based on market conditions.
    
    Returns:
        signals: Trading signals
        debug_df: DataFrame with all indicators
    """
    df = df.copy()
    df = calculate_volatility_regime(df)
    
    # Calculate ADX for regime
    close_col = 'close' if 'close' in df.columns else 'Close'
    high_col = 'high' if 'high' in df.columns else 'High'
    low_col = 'low' if 'low' in df.columns else 'Low'
    
    close = df[close_col]
    high = df[high_col]
    low = df[low_col]
    
    # ADX
    plus_dm = high.diff()
    minus_dm = -low.diff()
    plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0)
    minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0)
    
    tr = pd.concat([high - low, 
                    abs(high - close.shift()), 
                    abs(low - close.shift())], axis=1).max(axis=1)
    
    smoothed_tr = tr.rolling(14).sum()
    plus_di = 100 * (plus_dm.rolling(14).sum() / smoothed_tr)
    minus_di = 100 * (minus_dm.rolling(14).sum() / smoothed_tr)
    
    dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di + 0.001)
    adx = dx.rolling(14).mean()
    
    # Get both strategy signals
    trend_signals = generate_trend_v3(df)
    mr_signals = generate_mean_reversion_v3(df)
    
    # Adaptive: use trend when ADX > 25, else mean reversion
    is_trending = adx > 25
    
    signals = pd.Series(0, index=df.index)
    for i in range(len(df)):
        if is_trending.iloc[i]:
            signals.iloc[i] = trend_signals.iloc[i]
        else:
            signals.iloc[i] = mr_signals.iloc[i]
    
    df['adx'] = adx
    df['is_trending'] = is_trending
    df['strategy_used'] = np.where(is_trending, 'trend', 'mean_reversion')
    
    return signals, df


# ═══════════════════════════════════════════════════════════════════════════════
#                           MAIN (Demo)
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    print("=" * 65)
    print("IMPROVED STRATEGIES V3 - DEMO")
    print("=" * 65)
    
    # Generate synthetic test data
    np.random.seed(42)
    days = 365
    dates = pd.date_range('2024-01-01', periods=days, freq='D')
    
    # Mix of trending and ranging
    base = 45000
    prices = [base]
    for i in range(1, days):
        if i < 120:  # Trend up
            prices.append(prices[-1] * (1 + 0.002 + np.random.randn() * 0.015))
        elif i < 240:  # Range
            mean = np.mean(prices[-20:])
            prices.append(prices[-1] + (mean - prices[-1]) * 0.05 + np.random.randn() * 500)
        else:  # Trend down then up
            prices.append(prices[-1] * (1 - 0.001 + np.random.randn() * 0.02))
    
    prices = np.array(prices)
    df = pd.DataFrame({
        'open': prices,
        'high': prices * (1 + np.abs(np.random.randn(days)) * 0.01),
        'low': prices * (1 - np.abs(np.random.randn(days)) * 0.01),
        'close': prices * (1 + np.random.randn(days) * 0.005),
        'volume': np.random.randint(10000, 100000, days)
    }, index=dates)
    
    print(f"\nTest Data: {days} days")
    print(f"Price Range: ${df['close'].min():,.0f} - ${df['close'].max():,.0f}")
    
    # Test each strategy
    for name, func in [
        ("Mean Reversion V3", generate_mean_reversion_v3),
        ("Trend Following V3", generate_trend_v3),
        ("Adaptive (Combined)", lambda x: generate_adaptive_signals(x)[0])
    ]:
        signals = func(df)
        
        # Count trades
        signal_changes = signals.diff().abs().fillna(0)
        num_entries = (signal_changes > 0).sum()
        trades_per_day = num_entries / days
        
        # Calculate returns
        returns = df['close'].pct_change()
        strategy_returns = signals.shift(1) * returns
        strategy_returns = strategy_returns.dropna()
        
        total_return = (1 + strategy_returns).prod() - 1
        buy_hold = (df['close'].iloc[-1] / df['close'].iloc[0]) - 1
        
        if strategy_returns.std() > 0:
            sharpe = (strategy_returns.mean() / strategy_returns.std()) * np.sqrt(252)
        else:
            sharpe = 0
        
        print(f"\n{name}:")
        print(f"  Total Entries: {num_entries} ({trades_per_day:.2f}/day)")
        print(f"  Return: {total_return:+.2%} (B&H: {buy_hold:+.2%})")
        print(f"  Sharpe: {sharpe:.2f}")
        
        # Position distribution
        long = (signals == 1).sum()
        short = (signals == -1).sum()
        flat = (signals == 0).sum()
        print(f"  Positions: {long} long / {short} short / {flat} flat days")
    
    print("\n" + "=" * 65)
