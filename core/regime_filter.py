"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                       MARKET REGIME FILTER                                    ║
║                                                                               ║
║  Detects market regime (trending/ranging) to improve strategy selection.      ║
║  Uses ADX + volatility metrics for regime classification.                     ║
╚═══════════════════════════════════════════════════════════════════════════════╝

Regimes:
1. STRONG_TREND_UP - High ADX, price above long MA
2. STRONG_TREND_DOWN - High ADX, price below long MA  
3. WEAK_TREND_UP - Medium ADX, price above MA
4. WEAK_TREND_DOWN - Medium ADX, price below MA
5. RANGING - Low ADX, choppy market

Strategy Selection:
- STRONG_TREND: Use trend following (break-out, momentum)
- WEAK_TREND: Reduce position size
- RANGING: Use mean reversion or stay flat

Author: Bot_Algo
Last Updated: January 2026
"""

import numpy as np
import pandas as pd
from enum import Enum
from dataclasses import dataclass
from typing import Dict, Tuple, Optional
import logging

logger = logging.getLogger("RegimeFilter")


# ═══════════════════════════════════════════════════════════════════════════════
#                           REGIME DEFINITIONS
# ═══════════════════════════════════════════════════════════════════════════════

class MarketRegime(Enum):
    """Market regime classifications"""
    STRONG_TREND_UP = "strong_trend_up"
    STRONG_TREND_DOWN = "strong_trend_down"
    WEAK_TREND_UP = "weak_trend_up"
    WEAK_TREND_DOWN = "weak_trend_down"
    RANGING = "ranging"
    VOLATILE = "volatile"


@dataclass
class RegimeConfig:
    """Configuration for regime detection"""
    adx_period: int = 14
    adx_strong_threshold: float = 25.0   # ADX > 25 = strong trend
    adx_weak_threshold: float = 20.0     # ADX 20-25 = weak trend
    ma_period: int = 200                  # Long-term MA for direction
    volatility_period: int = 20
    volatility_threshold: float = 0.03    # 3% daily vol = high volatility


# ═══════════════════════════════════════════════════════════════════════════════
#                           INDICATOR CALCULATIONS
# ═══════════════════════════════════════════════════════════════════════════════

def calculate_adx(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """
    Calculate Average Directional Index (ADX).
    
    ADX measures trend strength (not direction):
    - ADX > 25: Strong trend
    - ADX 20-25: Weak trend
    - ADX < 20: Ranging/choppy
    """
    df = df.copy()
    
    # Get column names (case insensitive)
    high_col = 'high' if 'high' in df.columns else 'High'
    low_col = 'low' if 'low' in df.columns else 'Low'
    close_col = 'close' if 'close' in df.columns else 'Close'
    
    high = df[high_col]
    low = df[low_col]
    close = df[close_col]
    
    # +DM and -DM
    plus_dm = high.diff()
    minus_dm = -low.diff()
    
    plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0)
    minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0)
    
    # True Range
    tr1 = high - low
    tr2 = abs(high - close.shift())
    tr3 = abs(low - close.shift())
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    
    # Smoothed values
    atr = tr.rolling(period).mean()
    plus_di = 100 * (plus_dm.rolling(period).mean() / atr)
    minus_di = 100 * (minus_dm.rolling(period).mean() / atr)
    
    # DX and ADX
    dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
    adx = dx.rolling(period).mean()
    
    df['ADX'] = adx
    df['plus_DI'] = plus_di
    df['minus_DI'] = minus_di
    
    return df


def calculate_volatility(df: pd.DataFrame, period: int = 20) -> pd.Series:
    """Calculate annualized volatility."""
    close_col = 'close' if 'close' in df.columns else 'Close'
    returns = df[close_col].pct_change()
    volatility = returns.rolling(period).std() * np.sqrt(252)
    return volatility


# ═══════════════════════════════════════════════════════════════════════════════
#                           REGIME DETECTION
# ═══════════════════════════════════════════════════════════════════════════════

class RegimeFilter:
    """
    Market regime detector and filter.
    
    Usage:
        filter = RegimeFilter()
        df = filter.detect_regime(data)
        
        regime = filter.get_current_regime(df)
        if regime in [MarketRegime.STRONG_TREND_UP, MarketRegime.STRONG_TREND_DOWN]:
            # Use trend following
        elif regime == MarketRegime.RANGING:
            # Use mean reversion or stay flat
    """
    
    def __init__(self, config: RegimeConfig = None):
        self.config = config or RegimeConfig()
    
    def detect_regime(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add regime column to dataframe.
        
        Args:
            df: OHLCV DataFrame
            
        Returns:
            DataFrame with 'regime' column added
        """
        df = df.copy()
        
        # Calculate ADX
        df = calculate_adx(df, self.config.adx_period)
        
        # Calculate long MA
        close_col = 'close' if 'close' in df.columns else 'Close'
        df['MA_long'] = df[close_col].rolling(self.config.ma_period).mean()
        
        # Calculate volatility
        df['volatility'] = calculate_volatility(df, self.config.volatility_period)
        
        # Determine trend direction
        df['above_ma'] = df[close_col] > df['MA_long']
        
        # Classify regime
        conditions = []
        regimes = []
        
        # Strong trend up
        conditions.append(
            (df['ADX'] >= self.config.adx_strong_threshold) & 
            df['above_ma']
        )
        regimes.append(MarketRegime.STRONG_TREND_UP.value)
        
        # Strong trend down
        conditions.append(
            (df['ADX'] >= self.config.adx_strong_threshold) & 
            ~df['above_ma']
        )
        regimes.append(MarketRegime.STRONG_TREND_DOWN.value)
        
        # Weak trend up
        conditions.append(
            (df['ADX'] >= self.config.adx_weak_threshold) & 
            (df['ADX'] < self.config.adx_strong_threshold) & 
            df['above_ma']
        )
        regimes.append(MarketRegime.WEAK_TREND_UP.value)
        
        # Weak trend down
        conditions.append(
            (df['ADX'] >= self.config.adx_weak_threshold) & 
            (df['ADX'] < self.config.adx_strong_threshold) & 
            ~df['above_ma']
        )
        regimes.append(MarketRegime.WEAK_TREND_DOWN.value)
        
        # High volatility (override)
        conditions.append(
            df['volatility'] > self.config.volatility_threshold
        )
        regimes.append(MarketRegime.VOLATILE.value)
        
        # Default: ranging
        df['regime'] = MarketRegime.RANGING.value
        
        # Apply conditions (last match wins for volatile override)
        for cond, regime in zip(conditions[:-1], regimes[:-1]):
            df.loc[cond, 'regime'] = regime
        
        return df
    
    def get_current_regime(self, df: pd.DataFrame) -> MarketRegime:
        """Get current regime from last row."""
        if 'regime' not in df.columns:
            df = self.detect_regime(df)
        
        regime_str = df['regime'].iloc[-1]
        return MarketRegime(regime_str)
    
    def get_regime_stats(self, df: pd.DataFrame) -> Dict:
        """Get distribution of regimes in data."""
        if 'regime' not in df.columns:
            df = self.detect_regime(df)
        
        counts = df['regime'].value_counts()
        total = len(df)
        
        return {
            regime: {
                'count': counts.get(regime, 0),
                'pct': counts.get(regime, 0) / total * 100
            }
            for regime in [r.value for r in MarketRegime]
        }
    
    def should_trade(self, df: pd.DataFrame, strategy_type: str = 'trend') -> bool:
        """
        Determine if we should trade based on regime and strategy type.
        
        Args:
            df: DataFrame with regime column
            strategy_type: 'trend' or 'mean_reversion'
            
        Returns:
            True if regime is favorable for strategy type
        """
        regime = self.get_current_regime(df)
        
        if strategy_type == 'trend':
            # Trend strategies work in strong trends
            return regime in [
                MarketRegime.STRONG_TREND_UP,
                MarketRegime.STRONG_TREND_DOWN
            ]
        
        elif strategy_type == 'mean_reversion':
            # Mean reversion works in ranging markets
            return regime in [
                MarketRegime.RANGING,
                MarketRegime.WEAK_TREND_UP,
                MarketRegime.WEAK_TREND_DOWN
            ]
        
        return False
    
    def get_position_multiplier(self, df: pd.DataFrame) -> float:
        """
        Get position size multiplier based on regime.
        
        Returns:
            Multiplier (0.0 to 1.0)
        """
        regime = self.get_current_regime(df)
        
        multipliers = {
            MarketRegime.STRONG_TREND_UP: 1.0,
            MarketRegime.STRONG_TREND_DOWN: 1.0,
            MarketRegime.WEAK_TREND_UP: 0.5,
            MarketRegime.WEAK_TREND_DOWN: 0.5,
            MarketRegime.RANGING: 0.25,
            MarketRegime.VOLATILE: 0.0   # No trading in high vol
        }
        
        return multipliers.get(regime, 0.5)


# ═══════════════════════════════════════════════════════════════════════════════
#                           MAIN (Demo)
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys
    import os
    
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    logging.basicConfig(level=logging.INFO)
    
    print("=" * 60)
    print("MARKET REGIME FILTER - DEMO")
    print("=" * 60)
    
    # Try to get real data
    try:
        from binance.client import Client
        client = Client("", "", {"timeout": 30})
        
        klines = client.futures_klines(
            symbol='BTCUSDT',
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
        
        print(f"\nFetched {len(df)} days of BTCUSDT data")
        
    except Exception as e:
        print(f"Using synthetic data: {e}")
        
        np.random.seed(42)
        dates = pd.date_range('2024-01-01', periods=365, freq='D')
        prices = 40000 * np.cumprod(1 + np.random.randn(365) * 0.02)
        
        df = pd.DataFrame({
            'open': prices,
            'high': prices * 1.015,
            'low': prices * 0.985,
            'close': prices * (1 + np.random.randn(365) * 0.005),
            'volume': np.random.randint(1000, 10000, 365)
        }, index=dates)
    
    # Detect regimes
    filter = RegimeFilter()
    df = filter.detect_regime(df)
    
    # Get stats
    stats = filter.get_regime_stats(df)
    
    print(f"\nRegime Distribution (last {len(df)} days):")
    for regime, data in stats.items():
        if data['count'] > 0:
            print(f"  {regime}: {data['count']} days ({data['pct']:.1f}%)")
    
    print(f"\nCurrent Regime: {filter.get_current_regime(df).value}")
    print(f"Should Trade (Trend): {filter.should_trade(df, 'trend')}")
    print(f"Should Trade (Mean Rev): {filter.should_trade(df, 'mean_reversion')}")
    print(f"Position Multiplier: {filter.get_position_multiplier(df):.2f}")
    
    print(f"\nLast 10 days regime:")
    for idx, row in df.tail(10).iterrows():
        print(f"  {idx.date()}: ADX={row['ADX']:.1f}, Regime={row['regime']}")
    
    print("\n" + "=" * 60)
