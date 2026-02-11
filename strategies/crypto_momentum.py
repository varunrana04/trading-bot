"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                       CRYPTO MOMENTUM STRATEGY                                ║
║                                                                               ║
║  A robust momentum + trend following strategy for BTC/ETH/SOL futures.        ║
║  Designed to pass Walk-Forward Optimization validation.                       ║
╚═══════════════════════════════════════════════════════════════════════════════╝

Strategy Logic:
- Enter on momentum breakout + trend confirmation
- Dynamic position sizing based on volatility
- Strict risk management (ATR-based stops)

Author: Bot_Algo
Last Updated: January 2026
"""

import numpy as np
import pandas as pd
from typing import Dict, Tuple, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger("MomentumStrategy")


# ═══════════════════════════════════════════════════════════════════════════════
#                           STRATEGY PARAMETERS
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class MomentumParams:
    """Strategy parameters with sensible defaults."""
    
    # Trend filters
    trend_ema_fast: int = 20       # Fast EMA for trend
    trend_ema_slow: int = 50       # Slow EMA for trend
    trend_ema_major: int = 200     # Major trend filter
    
    # Momentum
    momentum_period: int = 14      # Momentum lookback
    momentum_threshold: float = 0.03  # 3% momentum threshold
    
    # RSI
    rsi_period: int = 14
    rsi_oversold: int = 30
    rsi_overbought: int = 70
    
    # Volatility (ATR)
    atr_period: int = 14
    atr_multiplier: float = 2.0   # Stop loss = ATR * multiplier
    
    # Entry/Exit
    take_profit_atr: float = 3.0  # TP = ATR * this
    max_hold_bars: int = 20       # Max holding period


# ═══════════════════════════════════════════════════════════════════════════════
#                           INDICATOR CALCULATION
# ═══════════════════════════════════════════════════════════════════════════════

def calculate_indicators(df: pd.DataFrame, params: MomentumParams = None) -> pd.DataFrame:
    """
    Calculate all technical indicators needed for the strategy.
    
    Args:
        df: OHLCV DataFrame
        params: Strategy parameters
        
    Returns:
        DataFrame with indicators added
    """
    if params is None:
        params = MomentumParams()
    
    df = df.copy()
    
    # Get close price (handle case variations)
    close_col = 'close'
    for col in df.columns:
        if col.lower() == 'close':
            close_col = col
            break
    
    close = df[close_col]
    
    # EMAs
    df['ema_fast'] = close.ewm(span=params.trend_ema_fast, adjust=False).mean()
    df['ema_slow'] = close.ewm(span=params.trend_ema_slow, adjust=False).mean()
    df['ema_major'] = close.ewm(span=params.trend_ema_major, adjust=False).mean()
    
    # Trend signals
    df['trend_bullish'] = (df['ema_fast'] > df['ema_slow']) & (close > df['ema_major'])
    df['trend_bearish'] = (df['ema_fast'] < df['ema_slow']) & (close < df['ema_major'])
    
    # Momentum (Rate of Change)
    df['momentum'] = close.pct_change(params.momentum_period)
    df['momentum_breakout'] = df['momentum'] > params.momentum_threshold
    df['momentum_breakdown'] = df['momentum'] < -params.momentum_threshold
    
    # RSI
    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(params.rsi_period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(params.rsi_period).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    
    # ATR
    high_col = 'high' if 'high' in df.columns else 'High'
    low_col = 'low' if 'low' in df.columns else 'Low'
    
    if high_col in df.columns and low_col in df.columns:
        high_low = df[high_col] - df[low_col]
        high_close = abs(df[high_col] - close.shift())
        low_close = abs(df[low_col] - close.shift())
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        df['atr'] = tr.rolling(params.atr_period).mean()
    else:
        # Fallback: use close volatility
        df['atr'] = close.rolling(params.atr_period).std() * 2
    
    # ATR percentage
    df['atr_pct'] = df['atr'] / close * 100
    
    return df


# ═══════════════════════════════════════════════════════════════════════════════
#                           SIGNAL GENERATION
# ═══════════════════════════════════════════════════════════════════════════════

def generate_signals(df: pd.DataFrame, params: Dict = None) -> pd.Series:
    """
    Generate trading signals from data.
    
    This is the main strategy function that will be passed to WFO.
    
    Args:
        df: OHLCV DataFrame
        params: Parameter dictionary (will be converted to MomentumParams)
        
    Returns:
        Series of signals: 1 = long, -1 = short, 0 = flat
    """
    # Convert params dict to dataclass
    if params is None:
        mp = MomentumParams()
    else:
        mp = MomentumParams(
            trend_ema_fast=params.get('trend_ema_fast', 20),
            trend_ema_slow=params.get('trend_ema_slow', 50),
            trend_ema_major=params.get('trend_ema_major', 200),
            momentum_period=params.get('momentum_period', 14),
            momentum_threshold=params.get('momentum_threshold', 0.03),
            rsi_period=params.get('rsi_period', 14),
            rsi_oversold=params.get('rsi_oversold', 30),
            rsi_overbought=params.get('rsi_overbought', 70),
            atr_period=params.get('atr_period', 14),
            atr_multiplier=params.get('atr_multiplier', 2.0),
            take_profit_atr=params.get('take_profit_atr', 3.0),
            max_hold_bars=params.get('max_hold_bars', 20)
        )
    
    # Calculate indicators
    df = calculate_indicators(df, mp)
    
    # Initialize signals
    signals = pd.Series(0, index=df.index)
    
    # Long signal conditions
    long_condition = (
        df['trend_bullish'] &                    # Uptrend
        df['momentum_breakout'] &                # Momentum breakout
        (df['rsi'] > mp.rsi_oversold) &          # Not oversold (avoid catching knives)
        (df['rsi'] < mp.rsi_overbought) &        # Not overbought
        (df['atr_pct'] < 5.0)                    # Volatility not too high
    )
    
    # Short signal conditions
    short_condition = (
        df['trend_bearish'] &                    # Downtrend
        df['momentum_breakdown'] &               # Momentum breakdown
        (df['rsi'] > mp.rsi_oversold) &          # Not oversold
        (df['rsi'] < mp.rsi_overbought) &        # Not overbought
        (df['atr_pct'] < 5.0)                    # Volatility check
    )
    
    # Set signals
    signals[long_condition] = 1
    signals[short_condition] = -1
    
    return signals


# ═══════════════════════════════════════════════════════════════════════════════
#                           PARAMETER OPTIMIZATION
# ═══════════════════════════════════════════════════════════════════════════════

def optimize_parameters(df: pd.DataFrame) -> Dict:
    """
    Optimize strategy parameters on training data.
    
    This is a simplified grid search. In production, use more sophisticated methods.
    
    Args:
        df: Training data
        
    Returns:
        Best parameters dictionary
    """
    best_params = None
    best_sharpe = -999
    
    # Parameter grid (keep small to avoid overfitting!)
    fast_emas = [10, 20]
    slow_emas = [30, 50]
    momentum_thresholds = [0.02, 0.03]
    
    for fast in fast_emas:
        for slow in slow_emas:
            if fast >= slow:
                continue
                
            for mom_thresh in momentum_thresholds:
                params = {
                    'trend_ema_fast': fast,
                    'trend_ema_slow': slow,
                    'momentum_threshold': mom_thresh
                }
                
                # Generate signals
                signals = generate_signals(df, params)
                
                # Calculate returns
                close_col = 'close' if 'close' in df.columns else 'Close'
                returns = df[close_col].pct_change()
                strategy_returns = signals.shift(1) * returns
                strategy_returns = strategy_returns.dropna()
                
                # Calculate Sharpe
                if len(strategy_returns) > 20 and strategy_returns.std() > 0:
                    sharpe = (strategy_returns.mean() / strategy_returns.std()) * np.sqrt(252)
                else:
                    sharpe = 0
                
                if sharpe > best_sharpe:
                    best_sharpe = sharpe
                    best_params = params
    
    if best_params is None:
        # Default params if optimization fails
        best_params = {
            'trend_ema_fast': 20,
            'trend_ema_slow': 50,
            'momentum_threshold': 0.03
        }
    
    logger.info(f"Best params: {best_params} (Sharpe: {best_sharpe:.2f})")
    return best_params


# ═══════════════════════════════════════════════════════════════════════════════
#                           POSITION SIZING
# ═══════════════════════════════════════════════════════════════════════════════

def calculate_position_size(
    capital: float,
    entry_price: float,
    atr: float,
    risk_per_trade: float = 0.02,  # 2% risk per trade
    max_leverage: int = 10
) -> Dict:
    """
    Calculate position size based on ATR risk.
    
    Args:
        capital: Total capital
        entry_price: Entry price
        atr: Current ATR
        risk_per_trade: Max risk as % of capital
        max_leverage: Maximum leverage allowed
        
    Returns:
        Dict with position sizing info
    """
    # Risk amount
    risk_amount = capital * risk_per_trade
    
    # Stop loss distance = 2 * ATR
    stop_distance = atr * 2
    stop_pct = stop_distance / entry_price
    
    # Position size where stop loss = risk_amount
    notional = risk_amount / stop_pct
    
    # Quantity
    quantity = notional / entry_price
    
    # Required leverage
    leverage = notional / capital
    leverage = min(leverage, max_leverage)
    
    # Adjust if leverage capped
    if leverage == max_leverage:
        notional = capital * max_leverage
        quantity = notional / entry_price
    
    return {
        'capital': capital,
        'entry_price': entry_price,
        'atr': atr,
        'stop_distance': stop_distance,
        'stop_pct': stop_pct * 100,
        'quantity': quantity,
        'notional': notional,
        'leverage': leverage,
        'risk_amount': risk_amount,
        'stop_price': entry_price - stop_distance,
        'take_profit': entry_price + (atr * 3)
    }


# ═══════════════════════════════════════════════════════════════════════════════
#                           MAIN (Demo)
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys
    import os
    
    # Add paths
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
    
    logging.basicConfig(level=logging.INFO)
    
    print("=" * 60)
    print("CRYPTO MOMENTUM STRATEGY - DEMO")
    print("=" * 60)
    
    # Create sample data
    np.random.seed(42)
    dates = pd.date_range('2021-01-01', periods=1000, freq='D')
    prices = 40000 * np.cumprod(1 + np.random.randn(1000) * 0.02)
    
    data = pd.DataFrame({
        'open': prices,
        'high': prices * (1 + np.abs(np.random.randn(1000)) * 0.01),
        'low': prices * (1 - np.abs(np.random.randn(1000)) * 0.01),
        'close': prices * (1 + np.random.randn(1000) * 0.005),
        'volume': np.random.randint(1000, 10000, 1000)
    }, index=dates)
    
    print(f"\nData: {len(data)} days")
    print(f"Price range: ${data['close'].min():,.0f} - ${data['close'].max():,.0f}")
    
    # Calculate indicators
    params = MomentumParams()
    df_with_indicators = calculate_indicators(data, params)
    
    print(f"\nIndicators calculated:")
    print(f"  EMA Fast: {params.trend_ema_fast}")
    print(f"  EMA Slow: {params.trend_ema_slow}")
    print(f"  EMA Major: {params.trend_ema_major}")
    
    # Generate signals
    signals = generate_signals(data)
    
    long_signals = (signals == 1).sum()
    short_signals = (signals == -1).sum()
    
    print(f"\nSignals generated:")
    print(f"  Long signals: {long_signals}")
    print(f"  Short signals: {short_signals}")
    
    # Optimize parameters
    print(f"\nOptimizing parameters...")
    best_params = optimize_parameters(data)
    print(f"  Best fast EMA: {best_params.get('trend_ema_fast')}")
    print(f"  Best slow EMA: {best_params.get('trend_ema_slow')}")
    print(f"  Best momentum threshold: {best_params.get('momentum_threshold')}")
    
    # Position sizing example
    sizing = calculate_position_size(
        capital=1000,
        entry_price=45000,
        atr=1000,
        risk_per_trade=0.02
    )
    
    print(f"\nPosition Sizing (Capital=$1000, BTC=$45000, ATR=$1000):")
    print(f"  Quantity: {sizing['quantity']:.6f} BTC")
    print(f"  Notional: ${sizing['notional']:,.0f}")
    print(f"  Leverage: {sizing['leverage']:.1f}x")
    print(f"  Stop Loss: ${sizing['stop_price']:,.0f} ({sizing['stop_pct']:.1f}%)")
    print(f"  Take Profit: ${sizing['take_profit']:,.0f}")
    
    print("\n" + "=" * 60)
    print("To validate this strategy, use:")
    print("  from core.validation import validate_strategy")
    print("  from strategies.crypto_momentum import generate_signals, optimize_parameters")
    print("  result = validate_strategy(data, generate_signals, optimize_parameters)")
    print("=" * 60)
