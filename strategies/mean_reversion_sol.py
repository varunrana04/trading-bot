"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                       MEAN REVERSION STRATEGY (SOL)                           ║
║                                                                               ║
║  Mean reversion strategy designed for ranging/choppy markets.                 ║
║  Best used when ADX < 20 (no strong trend).                                   ║
╚═══════════════════════════════════════════════════════════════════════════════╝

Strategy Logic:
- Enter when price deviates significantly from mean
- Use Bollinger Bands for overbought/oversold
- Works opposite of trend following

Best Markets:
- Low ADX (< 20) = ranging market
- High volatility bursts within range
- SOL tends to have more ranging periods than BTC

Author: Bot_Algo
Last Updated: January 2026
"""

import numpy as np
import pandas as pd
from typing import Dict
from dataclasses import dataclass
import logging
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = logging.getLogger("MeanReversionStrategy")


# ═══════════════════════════════════════════════════════════════════════════════
#                           FIXED PARAMETERS
# ═══════════════════════════════════════════════════════════════════════════════

FIXED_PARAMS = {
    'bb_period': 20,         # Bollinger Band period
    'bb_std': 2.0,           # Standard deviation multiplier
    'rsi_period': 14,        # RSI period
    'rsi_oversold': 30,      # Oversold threshold
    'rsi_overbought': 70,    # Overbought threshold
    'adx_threshold': 20,     # Only trade when ADX < this (ranging)
    'profit_target': 0.015,  # 1.5% profit target (quick scalp)
    'stop_loss': 0.02,       # 2% stop loss
}


# ═══════════════════════════════════════════════════════════════════════════════
#                           INDICATOR CALCULATION
# ═══════════════════════════════════════════════════════════════════════════════

def calculate_indicators_mr(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate indicators for mean reversion strategy."""
    df = df.copy()
    
    close_col = 'close' if 'close' in df.columns else 'Close'
    high_col = 'high' if 'high' in df.columns else 'High'
    low_col = 'low' if 'low' in df.columns else 'Low'
    
    close = df[close_col]
    
    # Bollinger Bands
    ma = close.rolling(FIXED_PARAMS['bb_period']).mean()
    std = close.rolling(FIXED_PARAMS['bb_period']).std()
    
    df['bb_middle'] = ma
    df['bb_upper'] = ma + (FIXED_PARAMS['bb_std'] * std)
    df['bb_lower'] = ma - (FIXED_PARAMS['bb_std'] * std)
    
    # Position within bands (0 = lower, 1 = upper)
    df['bb_percent'] = (close - df['bb_lower']) / (df['bb_upper'] - df['bb_lower'])
    
    # RSI
    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(FIXED_PARAMS['rsi_period']).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(FIXED_PARAMS['rsi_period']).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    
    # ADX for regime filter (simplified)
    if high_col in df.columns and low_col in df.columns:
        high = df[high_col]
        low = df[low_col]
        
        plus_dm = high.diff()
        minus_dm = -low.diff()
        plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0)
        minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0)
        
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        
        atr = tr.rolling(14).mean()
        plus_di = 100 * (plus_dm.rolling(14).mean() / atr)
        minus_di = 100 * (minus_dm.rolling(14).mean() / atr)
        
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
        df['adx'] = dx.rolling(14).mean()
    else:
        # Default low ADX if no high/low data
        df['adx'] = 15
    
    # Oversold/Overbought conditions
    df['oversold'] = (close < df['bb_lower']) & (df['rsi'] < FIXED_PARAMS['rsi_oversold'])
    df['overbought'] = (close > df['bb_upper']) & (df['rsi'] > FIXED_PARAMS['rsi_overbought'])
    
    # Regime check (only trade when ranging)
    df['is_ranging'] = df['adx'] < FIXED_PARAMS['adx_threshold']
    
    return df


# ═══════════════════════════════════════════════════════════════════════════════
#                           SIGNAL GENERATION
# ═══════════════════════════════════════════════════════════════════════════════

def generate_signals_mr(df: pd.DataFrame, params: Dict = None) -> pd.Series:
    """
    Generate mean reversion signals.
    
    Strategy:
    - LONG: Price at lower BB + RSI oversold + ADX < 20 (ranging)
    - SHORT: Price at upper BB + RSI overbought + ADX < 20 (ranging)
    - EXIT: Price returns to middle band
    """
    _ = params  # Fixed params
    
    df = calculate_indicators_mr(df)
    
    close_col = 'close' if 'close' in df.columns else 'Close'
    close = df[close_col]
    
    signals = pd.Series(0, index=df.index)
    
    # Long entry: oversold + ranging
    long_entry = df['oversold'] & df['is_ranging']
    
    # Short entry: overbought + ranging
    short_entry = df['overbought'] & df['is_ranging']
    
    # Exit: price returns to middle
    at_middle = (close >= df['bb_middle'] * 0.99) & (close <= df['bb_middle'] * 1.01)
    
    # Set entry signals
    signals[long_entry] = 1
    signals[short_entry] = -1
    
    # Forward fill positions
    position = signals.copy()
    for i in range(1, len(position)):
        if position.iloc[i] == 0:
            prev = position.iloc[i-1]
            # Exit at middle band
            if prev != 0 and at_middle.iloc[i]:
                position.iloc[i] = 0
            else:
                position.iloc[i] = prev
    
    return position


def optimize_parameters_mr(df: pd.DataFrame) -> Dict:
    """Return fixed parameters."""
    return FIXED_PARAMS.copy()


# ═══════════════════════════════════════════════════════════════════════════════
#                           MAIN (Demo)
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    print("=" * 60)
    print("MEAN REVERSION STRATEGY - SOL")
    print("=" * 60)
    
    # Try to get real SOL data
    try:
        from binance.client import Client
        client = Client("", "", {"timeout": 30})
        
        klines = client.futures_klines(
            symbol='SOLUSDT',
            interval='1d',
            limit=365
        )
        
        df = pd.DataFrame(klines, columns=[
            'timestamp', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_volume', 'trades', 'taker_buy_base',
            'taker_buy_quote', 'ignore'
        ])
        
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = df[col].astype(float)
        
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df = df.set_index('timestamp')
        
        print(f"\nFetched {len(df)} days of SOLUSDT data")
        print(f"Price range: ${df['close'].min():.2f} - ${df['close'].max():.2f}")
        
    except Exception as e:
        print(f"Using synthetic data: {e}")
        
        np.random.seed(42)
        dates = pd.date_range('2024-01-01', periods=365, freq='D')
        # Ranging price with mean reversion
        base = 100
        prices = [base]
        for _ in range(364):
            # Mean reverting: tend back toward 100
            deviation = (prices[-1] - base) / base
            drift = -deviation * 0.1  # Pull back toward mean
            prices.append(prices[-1] * (1 + drift + np.random.randn() * 0.03))
        
        prices = np.array(prices)
        df = pd.DataFrame({
            'open': prices,
            'high': prices * (1 + np.abs(np.random.randn(365)) * 0.02),
            'low': prices * (1 - np.abs(np.random.randn(365)) * 0.02),
            'close': prices * (1 + np.random.randn(365) * 0.01),
            'volume': np.random.randint(10000, 100000, 365)
        }, index=dates)
    
    # Calculate indicators
    df = calculate_indicators_mr(df)
    
    print(f"\nADX Stats:")
    print(f"  Mean: {df['adx'].mean():.1f}")
    print(f"  Ranging days (ADX < 20): {(df['adx'] < 20).sum()}")
    print(f"  Trending days (ADX > 25): {(df['adx'] > 25).sum()}")
    
    # Generate signals
    signals = generate_signals_mr(df)
    
    long_days = (signals == 1).sum()
    short_days = (signals == -1).sum()
    flat_days = (signals == 0).sum()
    
    print(f"\nPosition Distribution:")
    print(f"  Long: {long_days} days ({long_days/len(signals)*100:.1f}%)")
    print(f"  Short: {short_days} days ({short_days/len(signals)*100:.1f}%)")
    print(f"  Flat: {flat_days} days ({flat_days/len(signals)*100:.1f}%)")
    
    # Calculate returns
    returns = df['close'].pct_change()
    strategy_returns = signals.shift(1) * returns
    strategy_returns = strategy_returns.dropna()
    
    if len(strategy_returns) > 0 and strategy_returns.std() > 0:
        total_return = (1 + strategy_returns).prod() - 1
        sharpe = (strategy_returns.mean() / strategy_returns.std()) * np.sqrt(252)
        
        print(f"\nBacktest Results (no costs):")
        print(f"  Total Return: {total_return:.2%}")
        print(f"  Sharpe Ratio: {sharpe:.2f}")
    
    print("\n" + "=" * 60)
