"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                       HIGH FREQUENCY HYBRID STRATEGY                          ║
║                                                                               ║
║  Combines V2 trend-following logic with higher trade frequency.               ║
║  Target: 1-5 complete trades per day for 24/7 crypto markets.                ║
╚═══════════════════════════════════════════════════════════════════════════════╝

Key Changes from V2:
- Faster EMAs (8/21 instead of 20/50)
- Add RSI momentum confirmation
- Quicker exit on trend weakness
- Volatility filter to skip extreme vol
- Keep the core EMA + breakout logic that worked in crashes

Author: Bot_Algo
Last Updated: January 2026
"""

import numpy as np
import pandas as pd
from typing import Dict, Tuple
import logging

logger = logging.getLogger("HybridStrategy")


# ═══════════════════════════════════════════════════════════════════════════════
#                           PARAMETERS
# ═══════════════════════════════════════════════════════════════════════════════

HYBRID_PARAMS = {
    # Ultra-fast EMAs for more signals
    'ema_fast': 5,           # Very fast
    'ema_medium': 13,        # Medium
    'ema_slow': 34,          # Fibonacci sequence
    
    # RSI for momentum - looser thresholds
    'rsi_period': 5,         # Very fast RSI
    'rsi_long': 45,          # Long when RSI > 45 (more signals)
    'rsi_short': 55,         # Short when RSI < 55 (more signals)
    'rsi_extreme_high': 75,  # Strong overbought
    'rsi_extreme_low': 25,   # Strong oversold
    
    # ATR for stops and volatility
    'atr_period': 7,         # Faster ATR
    'atr_stop_mult': 1.2,    # Tighter stops for more trades
    
    # Volatility filter
    'vol_extreme': 3.0,      # Only skip very extreme vol
    'vol_high': 2.0,         # Reduce size threshold
    
    # Quick exit settings
    'exit_ema_cross': True,
    'exit_rsi_flip': True,
    'exit_on_rsi_extreme': True,  # Exit at RSI extremes
    
    # Breakout settings
    'breakout_period': 10,   # Shorter breakout period
}


# ═══════════════════════════════════════════════════════════════════════════════
#                           INDICATORS
# ═══════════════════════════════════════════════════════════════════════════════

def calculate_indicators(df: pd.DataFrame, params: Dict = None) -> pd.DataFrame:
    """Calculate all indicators for hybrid strategy."""
    p = HYBRID_PARAMS.copy()
    if params:
        p.update(params)
    
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
    
    # Quick EMA cross (fast crosses medium)
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
    df['atr_pct'] = df['atr'] / close * 100
    
    # Volatility regime
    df['atr_avg'] = df['atr'].rolling(50).mean()
    df['vol_ratio'] = df['atr'] / df['atr_avg']
    df['vol_extreme'] = df['vol_ratio'] > p['vol_extreme']
    df['vol_high'] = df['vol_ratio'] > p['vol_high']
    
    # Momentum (ROC)
    df['roc'] = close.pct_change(3) * 100
    
    # Breakout detection
    df['high_20'] = high.rolling(20).max()
    df['low_20'] = low.rolling(20).min()
    df['breakout_up'] = close > df['high_20'].shift(1)
    df['breakout_down'] = close < df['low_20'].shift(1)
    
    return df


# ═══════════════════════════════════════════════════════════════════════════════
#                           SIGNAL GENERATION
# ═══════════════════════════════════════════════════════════════════════════════

def generate_hybrid_signals(df: pd.DataFrame, params: Dict = None) -> pd.Series:
    """
    Generate ultra-high frequency signals.
    
    Entry (any of these):
    - EMA cross (fast crosses medium)
    - RSI extreme + momentum (oversold bounce / overbought fade)
    - Breakout with EMA confirmation
    - Strong momentum burst (ROC + RSI aligned)
    
    Exit:
    - EMA cross opposite
    - RSI reaches extreme opposite
    - Momentum reversal
    """
    p = HYBRID_PARAMS.copy()
    if params:
        p.update(params)
    
    df = calculate_indicators(df, p)
    
    close_col = 'close' if 'close' in df.columns else 'Close'
    close = df[close_col]
    
    # Add more indicators for extra signals
    rsi = df['rsi']
    roc = df['roc']
    
    signals = pd.Series(0, index=df.index)
    position = 0
    
    for i in range(2, len(df)):
        curr = df.iloc[i]
        prev = df.iloc[i-1]
        
        # Skip extreme volatility (only VERY extreme)
        if curr['vol_extreme']:
            position = 0
            signals.iloc[i] = 0
            continue
        
        curr_rsi = rsi.iloc[i]
        prev_rsi = rsi.iloc[i-1]
        curr_roc = roc.iloc[i]
        
        if position == 0:
            # === LONG ENTRY CONDITIONS (any one triggers) ===
            
            # 1. EMA cross up
            ema_long = curr['ema_cross_up']
            
            # 2. RSI oversold bounce (RSI was < 25, now rising)
            rsi_bounce = (prev_rsi < p['rsi_extreme_low'] and curr_rsi > prev_rsi)
            
            # 3. Breakout with bullish EMA
            breakout_long = curr['breakout_up'] and (curr['ema_fast'] > curr['ema_medium'])
            
            # 4. Strong bullish momentum (ROC > 2% and RSI > 50)
            momentum_long = (curr_roc > 2) and (curr_rsi > 50)
            
            # 5. EMA alignment with any bullish RSI
            trend_long = curr['ema_bullish'] and curr['rsi_bullish']
            
            long_entry = ema_long or rsi_bounce or breakout_long or momentum_long or trend_long
            
            # === SHORT ENTRY CONDITIONS ===
            
            # 1. EMA cross down
            ema_short = curr['ema_cross_down']
            
            # 2. RSI overbought fade (RSI was > 75, now falling)
            rsi_fade = (prev_rsi > p['rsi_extreme_high'] and curr_rsi < prev_rsi)
            
            # 3. Breakdown with bearish EMA
            breakout_short = curr['breakout_down'] and (curr['ema_fast'] < curr['ema_medium'])
            
            # 4. Strong bearish momentum (ROC < -2% and RSI < 50)
            momentum_short = (curr_roc < -2) and (curr_rsi < 50)
            
            # 5. EMA alignment with any bearish RSI
            trend_short = curr['ema_bearish'] and curr['rsi_bearish']
            
            short_entry = ema_short or rsi_fade or breakout_short or momentum_short or trend_short
            
            # Execute entry
            if long_entry and not short_entry:
                position = 1
            elif short_entry and not long_entry:
                position = -1
            elif long_entry and short_entry:
                # Conflicting signals - use momentum
                if curr_roc > 0:
                    position = 1
                else:
                    position = -1
        
        elif position == 1:  # Long position
            # === EXIT/REVERSE CONDITIONS ===
            
            # Exit on EMA cross down
            exit_ema = curr['ema_cross_down']
            
            # Exit on RSI extreme high (take profit)
            exit_rsi_high = curr_rsi > p['rsi_extreme_high']
            
            # Exit on momentum reversal
            exit_momentum = (curr_roc < -1.5) and (prev_rsi > curr_rsi)
            
            # Strong reversal (enter short)
            strong_reverse = curr['ema_bearish'] and (curr_rsi < 40)
            
            if strong_reverse:
                position = -1
            elif exit_ema or exit_rsi_high or exit_momentum:
                position = 0
        
        elif position == -1:  # Short position
            # === EXIT/REVERSE CONDITIONS ===
            
            # Exit on EMA cross up
            exit_ema = curr['ema_cross_up']
            
            # Exit on RSI extreme low (take profit)
            exit_rsi_low = curr_rsi < p['rsi_extreme_low']
            
            # Exit on momentum reversal
            exit_momentum = (curr_roc > 1.5) and (prev_rsi < curr_rsi)
            
            # Strong reversal (enter long)
            strong_reverse = curr['ema_bullish'] and (curr_rsi > 60)
            
            if strong_reverse:
                position = 1
            elif exit_ema or exit_rsi_low or exit_momentum:
                position = 0
        
        signals.iloc[i] = position
    
    return signals


def optimize_params(df: pd.DataFrame) -> Dict:
    """Return fixed parameters."""
    return HYBRID_PARAMS.copy()


# ═══════════════════════════════════════════════════════════════════════════════
#                           POSITION SIZING
# ═══════════════════════════════════════════════════════════════════════════════

def calculate_position_size(
    equity: float,
    price: float,
    atr: float,
    vol_ratio: float,
    risk_pct: float = 0.02
) -> Dict:
    """
    Calculate position size with volatility adjustment.
    
    Args:
        equity: Current equity
        price: Entry price  
        atr: Current ATR
        vol_ratio: Volatility ratio (1.0 = normal)
        risk_pct: Risk per trade (default 2%)
    """
    # Base position value
    base_risk = equity * risk_pct
    
    # Stop loss distance (1.5x ATR)
    stop_distance = atr * 1.5
    
    # Raw position size
    if stop_distance > 0:
        quantity = base_risk / stop_distance
    else:
        quantity = (equity * 0.1) / price
    
    # Adjust for volatility
    if vol_ratio > 1.8:
        quantity *= 0.5  # Half size in high vol
    elif vol_ratio > 1.3:
        quantity *= 0.75  # Reduced size
    elif vol_ratio < 0.7:
        quantity *= 1.2  # Increase in low vol
    
    position_value = quantity * price
    
    return {
        'quantity': quantity,
        'value': position_value,
        'stop_distance': stop_distance,
        'risk_amount': base_risk,
        'vol_adjustment': vol_ratio
    }


# ═══════════════════════════════════════════════════════════════════════════════
#                           MAIN (Demo)
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    logging.basicConfig(level=logging.INFO)
    
    print("=" * 65)
    print("HIGH FREQUENCY HYBRID STRATEGY - DEMO")
    print("=" * 65)
    
    # Try to fetch real BTC data
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
    
    print(f"Price Range: ${df['close'].min():,.0f} - ${df['close'].max():,.0f}")
    
    # Generate signals
    signals = generate_hybrid_signals(df)
    
    # Count trades
    signal_changes = signals.diff().abs().fillna(0)
    num_entries = int((signal_changes > 0).sum())
    trades_per_day = num_entries / len(df)
    
    # Position distribution
    long_days = (signals == 1).sum()
    short_days = (signals == -1).sum()
    flat_days = (signals == 0).sum()
    
    print(f"\n--- Signal Statistics ---")
    print(f"Total Entries/Exits: {num_entries} ({trades_per_day:.2f}/day)")
    print(f"Long Days: {long_days} ({long_days/len(df)*100:.1f}%)")
    print(f"Short Days: {short_days} ({short_days/len(df)*100:.1f}%)")
    print(f"Flat Days: {flat_days} ({flat_days/len(df)*100:.1f}%)")
    
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
    
    # Max drawdown
    cumulative = (1 + strategy_returns).cumprod()
    rolling_max = cumulative.expanding().max()
    drawdown = (cumulative - rolling_max) / rolling_max
    max_dd = drawdown.min()
    
    # Win rate
    daily_wins = (strategy_returns > 0).sum()
    daily_losses = (strategy_returns < 0).sum()
    win_rate = daily_wins / (daily_wins + daily_losses) * 100 if (daily_wins + daily_losses) > 0 else 0
    
    print(f"\n--- Performance ---")
    print(f"Total Return: {total_return:+.2%}")
    print(f"Buy & Hold: {buy_hold:+.2%}")
    print(f"Outperformance: {(total_return - buy_hold):+.2%}")
    print(f"Sharpe Ratio: {sharpe:.2f}")
    print(f"Max Drawdown: {max_dd:.2%}")
    print(f"Win Rate (daily): {win_rate:.1f}%")
    
    print("\n" + "=" * 65)
