"""
Statistical Arbitrage Strategy - Cointegration Pairs Trading
Uses Johansen test to find cointegrated pairs and trades mean reversion
"""

import numpy as np
import pandas as pd
from statsmodels.tsa.stattools import coint
from statsmodels.tsa.vector_ar.vecm import coint_johansen
from typing import Tuple, Dict, Optional
import warnings
warnings.filterwarnings('ignore')


class StatisticalArbitrage:
    """
    Cointegration-based pairs trading strategy
    
    Theory:
    If two assets are cointegrated, their price spread is mean-reverting.
    Trade when spread deviates significantly from mean.
    
    Mathematical Model:
    Price_A = β * Price_B + spread
    Z-score = (spread - μ) / σ
    
    Entry: |Z| > entry_threshold (default 2.0)
    Exit: |Z| < exit_threshold (default 0.5)
    """
    
    def __init__(
        self,
        lookback_period: int = 90,
        entry_zscore: float = 2.0,
        exit_zscore: float = 0.5,
        min_half_life: int = 1,
        max_half_life: int = 30
    ):
        """
        Initialize statistical arbitrage strategy
        
        Args:
            lookback_period: Days of data for cointegration test
            entry_zscore: Z-score threshold to enter trade
            exit_zscore: Z-score threshold to exit trade
            min_half_life: Minimum mean reversion half-life (days)
            max_half_life: Maximum mean reversion half-life (days)
        """
        self.lookback_period = lookback_period
        self.entry_zscore = entry_zscore
        self.exit_zscore = exit_zscore
        self.min_half_life = min_half_life
        self.max_half_life = max_half_life
        
        self.pairs = {}  # Store cointegration parameters
        self.positions = {}  # Current positions
    
    def test_cointegration(
        self,
        series_a: pd.Series,
        series_b: pd.Series
    ) -> Tuple[bool, float, float]:
        """
        Test if two price series are cointegrated using Engle-Granger test
        
        Args:
            series_a: First price series
            series_b: Second price series
            
        Returns:
            (is_cointegrated, p_value, hedge_ratio)
        """
        try:
            # Engle-Granger cointegration test
            score, pvalue, _ = coint(series_a, series_b)
            
            # Calculate hedge ratio (beta)
            hedge_ratio = np.polyfit(series_b, series_a, 1)[0]
            
            # Cointegrated if p-value < 0.05
            is_cointegrated = pvalue < 0.05
            
            return is_cointegrated, pvalue, hedge_ratio
            
        except Exception as e:
            print(f"[STAT ARB] Cointegration test failed: {e}")
            return False, 1.0, 0.0
    
    def calculate_spread(
        self,
        price_a: float,
        price_b: float,
        hedge_ratio: float
    ) -> float:
        """
        Calculate spread between two assets
        
        Spread = Price_A - β * Price_B
        """
        return price_a - hedge_ratio * price_b
    
    def calculate_zscore(
        self,
        spread: float,
        spread_series: pd.Series
    ) -> float:
        """
        Calculate Z-score of current spread
        
        Z = (spread - mean) / std
        """
        mean = spread_series.mean()
        std = spread_series.std()
        
        if std == 0:
            return 0.0
        
        return (spread - mean) / std
    
    def calculate_half_life(self, spread_series: pd.Series) -> float:
        """
        Calculate mean reversion half-life using Ornstein-Uhlenbeck process
        
        Formula: spread_t = θ * (μ - spread_{t-1}) + ε
        Half-life = -log(2) / θ
        
        Returns:
            Half-life in periods
        """
        try:
            spread_lag = spread_series.shift(1).dropna()
            spread_diff = spread_series.diff().dropna()
            
            # Align indices
            spread_lag = spread_lag[spread_diff.index]
            
            # OLS regression: Δspread_t = θ * spread_{t-1} + c
            X = spread_lag.values.reshape(-1, 1)
            y = spread_diff.values
            
            theta = np.linalg.lstsq(X, y, rcond=None)[0][0]
            
            if theta >= 0:
                return np.inf  # Not mean reverting
            
            half_life = -np.log(2) / theta
            return half_life
            
        except Exception:
            return np.inf
    
    def update_pair(
        self,
        symbol_a: str,
        symbol_b: str,
        prices_a: pd.Series,
        prices_b: pd.Series
    ) -> bool:
        """
        Update cointegration parameters for a pair
        
        Returns:
            True if pair is cointegrated and valid
        """
        # Test cointegration
        is_coint, pvalue, hedge_ratio = self.test_cointegration(
            prices_a, prices_b
        )
        
        if not is_coint:
            print(f"[STAT ARB] {symbol_a}/{symbol_b} not cointegrated (p={pvalue:.4f})")
            return False
        
        # Calculate spread series
        spread_series = prices_a - hedge_ratio * prices_b
        
        # Check half-life
        half_life = self.calculate_half_life(spread_series)
        
        if half_life < self.min_half_life or half_life > self.max_half_life:
            print(f"[STAT ARB] {symbol_a}/{symbol_b} half-life {half_life:.1f} out of range")
            return False
        
        # Store parameters
        pair_key = f"{symbol_a}/{symbol_b}"
        self.pairs[pair_key] = {
            'symbol_a': symbol_a,
            'symbol_b': symbol_b,
            'hedge_ratio': hedge_ratio,
            'spread_mean': spread_series.mean(),
            'spread_std': spread_series.std(),
            'half_life': half_life,
            'pvalue': pvalue
        }
        
        print(f"[STAT ARB] {pair_key} cointegrated!")
        print(f"  Hedge ratio: {hedge_ratio:.4f}")
        print(f"  Half-life: {half_life:.1f} periods")
        print(f"  P-value: {pvalue:.4f}")
        
        return True
    
    def generate_signal(
        self,
        pair_key: str,
        current_price_a: float,
        current_price_b: float,
        spread_history: pd.Series
    ) -> Dict:
        """
        Generate trading signal for a cointegrated pair
        
        Returns:
            {
                'action': 'LONG_A_SHORT_B' | 'SHORT_A_LONG_B' | 'CLOSE' | 'HOLD',
                'zscore': float,
                'spread': float,
                'confidence': float
            }
        """
        if pair_key not in self.pairs:
            return {'action': 'HOLD', 'zscore': 0, 'spread': 0, 'confidence': 0}
        
        params = self.pairs[pair_key]
        
        # Calculate current spread
        spread = self.calculate_spread(
            current_price_a,
            current_price_b,
            params['hedge_ratio']
        )
        
        # Calculate Z-score
        zscore = self.calculate_zscore(spread, spread_history)
        
        # Check if we have a position
        has_position = pair_key in self.positions
        
        # Entry signals
        if not has_position:
            if zscore > self.entry_zscore:
                # Spread too high - short spread
                # Short A, Long B
                confidence = min(abs(zscore) / 3.0, 1.0)
                return {
                    'action': 'SHORT_A_LONG_B',
                    'zscore': zscore,
                    'spread': spread,
                    'confidence': confidence,
                    'size_a': 1.0,
                    'size_b': params['hedge_ratio']
                }
            
            elif zscore < -self.entry_zscore:
                # Spread too low - long spread
                # Long A, Short B
                confidence = min(abs(zscore) / 3.0, 1.0)
                return {
                    'action': 'LONG_A_SHORT_B',
                    'zscore': zscore,
                    'spread': spread,
                    'confidence': confidence,
                    'size_a': 1.0,
                    'size_b': params['hedge_ratio']
                }
        
        # Exit signals
        else:
            if abs(zscore) < self.exit_zscore:
                return {
                    'action': 'CLOSE',
                    'zscore': zscore,
                    'spread': spread,
                    'confidence': 1.0
                }
        
        return {
            'action': 'HOLD',
            'zscore': zscore,
            'spread': spread,
            'confidence': 0.0
        }
    
    def get_pair_status(self, pair_key: str) -> Optional[Dict]:
        """Get current status of a pair"""
        if pair_key not in self.pairs:
            return None
        
        return {
            **self.pairs[pair_key],
            'has_position': pair_key in self.positions,
            'position': self.positions.get(pair_key)
        }


# Example usage
if __name__ == "__main__":
    print("Statistical Arbitrage - Cointegration Pairs Trading")
    print("=" * 60)
    
    # Initialize strategy
    stat_arb = StatisticalArbitrage(
        lookback_period=90,
        entry_zscore=2.0,
        exit_zscore=0.5
    )
    
    print("\nStrategy initialized with parameters:")
    print(f"  Lookback: {stat_arb.lookback_period} periods")
    print(f"  Entry Z-score: ±{stat_arb.entry_zscore}")
    print(f"  Exit Z-score: ±{stat_arb.exit_zscore}")
    print(f"  Half-life range: {stat_arb.min_half_life}-{stat_arb.max_half_life} periods")
    print("\nReady to test BTC/ETH cointegration")
