"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                       DATA CACHE & OPTIMIZATIONS                              ║
║                                                                               ║
║  Caching layer to reduce API calls and improve performance.                   ║
╚═══════════════════════════════════════════════════════════════════════════════╝

Author: Bot_Algo
Last Updated: January 2026
"""

import os
import json
import time
import hashlib
from datetime import datetime, timedelta
from typing import Dict, Optional, Any
import pandas as pd
import logging

logger = logging.getLogger("DataCache")


class DataCache:
    """
    In-memory cache with TTL for market data.
    Reduces API calls and improves responsiveness.
    """
    
    def __init__(self, default_ttl: int = 60):
        """
        Initialize cache.
        
        Args:
            default_ttl: Default time-to-live in seconds
        """
        self.cache: Dict[str, Any] = {}
        self.timestamps: Dict[str, float] = {}
        self.default_ttl = default_ttl
        self.hits = 0
        self.misses = 0
    
    def _get_key(self, *args, **kwargs) -> str:
        """Generate cache key from arguments."""
        key_str = str(args) + str(sorted(kwargs.items()))
        return hashlib.md5(key_str.encode()).hexdigest()
    
    def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache if not expired.
        
        Returns:
            Cached value or None if expired/missing
        """
        if key not in self.cache:
            self.misses += 1
            return None
        
        if time.time() - self.timestamps[key] > self.default_ttl:
            # Expired
            del self.cache[key]
            del self.timestamps[key]
            self.misses += 1
            return None
        
        self.hits += 1
        return self.cache[key]
    
    def set(self, key: str, value: Any, ttl: int = None):
        """Store value in cache."""
        self.cache[key] = value
        self.timestamps[key] = time.time()
    
    def clear(self):
        """Clear all cache."""
        self.cache = {}
        self.timestamps = {}
    
    def stats(self) -> Dict:
        """Get cache statistics."""
        total = self.hits + self.misses
        return {
            'hits': self.hits,
            'misses': self.misses,
            'hit_rate': self.hits / total * 100 if total > 0 else 0,
            'size': len(self.cache)
        }


# Global cache instance
_data_cache = DataCache(default_ttl=60)


def cached(ttl: int = 60):
    """Decorator to cache function results."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            key = _data_cache._get_key(func.__name__, *args, **kwargs)
            result = _data_cache.get(key)
            if result is not None:
                return result
            result = func(*args, **kwargs)
            _data_cache.set(key, result, ttl)
            return result
        return wrapper
    return decorator


# ═══════════════════════════════════════════════════════════════════════════════
#                           POSITION SIZING
# ═══════════════════════════════════════════════════════════════════════════════

class PositionSizer:
    """
    Advanced position sizing with Kelly Criterion and risk management.
    """
    
    def __init__(
        self,
        capital: float = 1000,
        max_risk_per_trade: float = 0.02,  # 2% risk per trade
        max_position_pct: float = 0.20,    # 20% max in single position
        kelly_fraction: float = 0.25       # Use 25% of Kelly
    ):
        self.capital = capital
        self.max_risk_per_trade = max_risk_per_trade
        self.max_position_pct = max_position_pct
        self.kelly_fraction = kelly_fraction
        
        # Track win rate for Kelly
        self.wins = 0
        self.losses = 0
        self.avg_win = 0
        self.avg_loss = 0
    
    def update_stats(self, pnl: float):
        """Update win/loss stats for Kelly calculation."""
        if pnl > 0:
            self.wins += 1
            self.avg_win = ((self.avg_win * (self.wins - 1)) + pnl) / self.wins
        else:
            self.losses += 1
            self.avg_loss = ((self.avg_loss * (self.losses - 1)) + abs(pnl)) / self.losses
    
    def kelly_criterion(self) -> float:
        """
        Calculate Kelly Criterion bet size.
        
        f* = (p * b - q) / b
        where:
            p = win probability
            b = win/loss ratio
            q = 1 - p
        """
        total = self.wins + self.losses
        if total < 10:  # Need minimum trades
            return self.max_position_pct
        
        p = self.wins / total
        q = 1 - p
        
        if self.avg_loss == 0:
            return self.max_position_pct
        
        b = self.avg_win / self.avg_loss
        
        kelly = (p * b - q) / b
        
        # Use fractional Kelly (safer)
        return min(kelly * self.kelly_fraction, self.max_position_pct)
    
    def calculate_position_size(
        self,
        price: float,
        stop_loss: float,
        confidence: float = 1.0,
        regime_multiplier: float = 1.0
    ) -> Dict:
        """
        Calculate optimal position size.
        
        Args:
            price: Entry price
            stop_loss: Stop loss price
            confidence: Signal confidence (0-1)
            regime_multiplier: Regime-based adjustment
            
        Returns:
            Dict with position details
        """
        # Risk per unit
        risk_per_unit = abs(price - stop_loss)
        if risk_per_unit == 0:
            risk_per_unit = price * 0.01  # Default 1%
        
        # Max risk amount
        max_risk = self.capital * self.max_risk_per_trade
        
        # Position size based on risk
        risk_based_size = max_risk / risk_per_unit
        
        # Apply confidence and regime adjustments
        adjusted_size = risk_based_size * confidence * regime_multiplier
        
        # Kelly-based cap
        kelly_pct = self.kelly_criterion()
        kelly_max_position = (self.capital * kelly_pct) / price
        
        # Final size (take minimum)
        max_by_capital = (self.capital * self.max_position_pct) / price
        final_size = min(adjusted_size, kelly_max_position, max_by_capital)
        
        # Position value
        position_value = final_size * price
        
        return {
            'quantity': final_size,
            'value': position_value,
            'risk_amount': final_size * risk_per_unit,
            'risk_pct': (final_size * risk_per_unit) / self.capital * 100,
            'kelly_pct': kelly_pct * 100,
            'size_method': 'risk_based'
        }


# ═══════════════════════════════════════════════════════════════════════════════
#                           CONFIDENCE SCORING
# ═══════════════════════════════════════════════════════════════════════════════

class ConfidenceScorer:
    """
    Calculate signal confidence based on multiple factors.
    """
    
    def __init__(self):
        self.weights = {
            'trend_alignment': 0.30,
            'regime_strength': 0.25,
            'volume_confirmation': 0.20,
            'momentum_strength': 0.15,
            'volatility_regime': 0.10
        }
    
    def score(self, df: pd.DataFrame, signal: int) -> Dict:
        """
        Calculate confidence score for a signal.
        
        Args:
            df: OHLCV DataFrame with indicators
            signal: Trading signal (1, -1, 0)
            
        Returns:
            Dict with confidence breakdown
        """
        if signal == 0:
            return {'total': 0, 'components': {}}
        
        close = df['close'].iloc[-1]
        
        scores = {}
        
        # 1. Trend Alignment (EMA alignment)
        if 'EMA_50' in df.columns and 'EMA_200' in df.columns:
            ema_50 = df['EMA_50'].iloc[-1]
            ema_200 = df['EMA_200'].iloc[-1]
            
            if signal == 1:  # Long
                trend_score = 1.0 if close > ema_50 > ema_200 else 0.5 if close > ema_50 else 0.2
            else:  # Short
                trend_score = 1.0 if close < ema_50 < ema_200 else 0.5 if close < ema_50 else 0.2
        else:
            trend_score = 0.5
        
        scores['trend_alignment'] = trend_score
        
        # 2. Regime Strength (ADX)
        if 'ADX' in df.columns:
            adx = df['ADX'].iloc[-1]
            if adx > 40:
                regime_score = 1.0
            elif adx > 25:
                regime_score = 0.7
            elif adx > 15:
                regime_score = 0.4
            else:
                regime_score = 0.2
        else:
            regime_score = 0.5
        
        scores['regime_strength'] = regime_score
        
        # 3. Volume Confirmation
        if 'volume' in df.columns:
            vol_ma = df['volume'].rolling(20).mean().iloc[-1]
            current_vol = df['volume'].iloc[-1]
            vol_ratio = current_vol / vol_ma if vol_ma > 0 else 1
            
            if vol_ratio > 1.5:
                vol_score = 1.0
            elif vol_ratio > 1.0:
                vol_score = 0.7
            else:
                vol_score = 0.4
        else:
            vol_score = 0.5
        
        scores['volume_confirmation'] = vol_score
        
        # 4. Momentum Strength
        returns = df['close'].pct_change(5).iloc[-1]
        momentum_aligned = (signal == 1 and returns > 0) or (signal == -1 and returns < 0)
        
        if momentum_aligned:
            if abs(returns) > 0.05:
                mom_score = 1.0
            elif abs(returns) > 0.02:
                mom_score = 0.7
            else:
                mom_score = 0.5
        else:
            mom_score = 0.2
        
        scores['momentum_strength'] = mom_score
        
        # 5. Volatility Regime
        if 'ATR' in df.columns:
            atr = df['ATR'].iloc[-1]
            atr_ma = df['ATR'].rolling(20).mean().iloc[-1]
            atr_ratio = atr / atr_ma if atr_ma > 0 else 1
            
            # Moderate volatility is best
            if 0.8 <= atr_ratio <= 1.5:
                vol_regime_score = 1.0
            elif 0.5 <= atr_ratio <= 2.0:
                vol_regime_score = 0.6
            else:
                vol_regime_score = 0.3
        else:
            vol_regime_score = 0.5
        
        scores['volatility_regime'] = vol_regime_score
        
        # Calculate weighted total
        total = sum(scores[k] * self.weights[k] for k in scores)
        
        return {
            'total': round(total * 100, 1),  # As percentage
            'components': scores
        }


# ═══════════════════════════════════════════════════════════════════════════════
#                           MULTI-SYMBOL MANAGER
# ═══════════════════════════════════════════════════════════════════════════════

class MultiSymbolManager:
    """
    Manage signals across multiple symbols.
    """
    
    def __init__(self, symbols: list, capital: float = 1000):
        self.symbols = symbols
        self.capital = capital
        self.capital_per_symbol = capital / len(symbols) if symbols else capital
        
        self.signals: Dict[str, int] = {s: 0 for s in symbols}
        self.positions: Dict[str, float] = {s: 0 for s in symbols}
        self.last_update: Dict[str, datetime] = {}
    
    def update_signal(self, symbol: str, signal: int):
        """Update signal for a symbol."""
        if symbol in self.symbols:
            self.signals[symbol] = signal
            self.last_update[symbol] = datetime.now()
    
    def get_portfolio_exposure(self) -> Dict:
        """Get overall portfolio exposure."""
        long_count = sum(1 for s in self.signals.values() if s > 0)
        short_count = sum(1 for s in self.signals.values() if s < 0)
        flat_count = sum(1 for s in self.signals.values() if s == 0)
        
        return {
            'long': long_count,
            'short': short_count,
            'flat': flat_count,
            'net_exposure': long_count - short_count,
            'exposure_ratio': (long_count - short_count) / len(self.symbols) if self.symbols else 0
        }
    
    def should_trade(self, symbol: str, new_signal: int) -> bool:
        """Check if trade should be taken (portfolio constraints)."""
        exposure = self.get_portfolio_exposure()
        
        # Don't add to heavily skewed portfolio
        if new_signal == 1 and exposure['net_exposure'] >= len(self.symbols) // 2:
            return False
        if new_signal == -1 and exposure['net_exposure'] <= -len(self.symbols) // 2:
            return False
        
        return True


# ═══════════════════════════════════════════════════════════════════════════════
#                           MAIN (Demo)
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import numpy as np
    
    print("=" * 60)
    print("OPTIMIZATION MODULES - DEMO")
    print("=" * 60)
    
    # Test Position Sizer
    print("\n--- Position Sizer ---")
    sizer = PositionSizer(capital=1000, max_risk_per_trade=0.02)
    
    # Simulate some trades
    for pnl in [50, -20, 30, -15, 40, 20]:
        sizer.update_stats(pnl)
    
    result = sizer.calculate_position_size(
        price=45000,
        stop_loss=44000,
        confidence=0.85,
        regime_multiplier=1.0
    )
    
    print(f"Entry: $45,000, Stop: $44,000")
    print(f"Quantity: {result['quantity']:.6f}")
    print(f"Value: ${result['value']:.2f}")
    print(f"Risk: ${result['risk_amount']:.2f} ({result['risk_pct']:.2f}%)")
    print(f"Kelly: {result['kelly_pct']:.2f}%")
    
    # Test Confidence Scorer
    print("\n--- Confidence Scorer ---")
    scorer = ConfidenceScorer()
    
    # Create sample data
    np.random.seed(42)
    dates = pd.date_range('2024-01-01', periods=100, freq='D')
    df = pd.DataFrame({
        'close': 45000 * np.cumprod(1 + np.random.randn(100) * 0.01),
        'volume': np.random.randint(10000, 50000, 100)
    }, index=dates)
    
    df['EMA_50'] = df['close'].ewm(span=50).mean()
    df['EMA_200'] = df['close'].ewm(span=200).mean()
    df['ADX'] = 30  # Simulated
    df['ATR'] = df['close'] * 0.015
    
    confidence = scorer.score(df, signal=1)
    print(f"Signal Confidence: {confidence['total']}%")
    print(f"Components: {confidence['components']}")
    
    # Test Cache
    print("\n--- Data Cache ---")
    cache = DataCache(default_ttl=5)
    cache.set('test_key', 'test_value')
    print(f"Get: {cache.get('test_key')}")
    print(f"Stats: {cache.stats()}")
    
    # Test Multi-Symbol
    print("\n--- Multi-Symbol Manager ---")
    manager = MultiSymbolManager(['BTCUSDT', 'ETHUSDT', 'SOLUSDT'], capital=1000)
    manager.update_signal('BTCUSDT', 1)
    manager.update_signal('ETHUSDT', -1)
    print(f"Exposure: {manager.get_portfolio_exposure()}")
    
    print("\n" + "=" * 60)
