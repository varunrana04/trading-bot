#!/usr/bin/env python3
"""
STATISTICAL ARBITRAGE - Pairs Trading for Indian Options
Uses cointegration between NIFTY and BANKNIFTY
"""

import pandas as pd
import numpy as np
from typing import Dict, Tuple, Optional
from statsmodels.tsa.stattools import coint
from statsmodels.regression.linear_model import OLS

try:
    from strategies.advanced import StatisticalArbitrage
    STAT_ARB_AVAILABLE = True
except:
    STAT_ARB_AVAILABLE = False

class OptionsPairsTading:
    """
    Pairs trading between correlated option underlyings
    Example: NIFTY vs BANKNIFTY
    """
    
    def __init__(self, lookback_window: int = 60):
        """
        Args:
            lookback_window: Days to use for cointegration testing
        """
        self.lookback = lookback_window
        self.hedge_ratio = None
        self.spread_mean = None
        self.spread_std = None
        self.cointegrated = False
        
    def test_cointegration(self, price_A: pd.Series, price_B: pd.Series) -> Dict:
        """
        Test if two price series are cointegrated
        
        Returns:
            {
                'cointegrated': bool,
                'p_value': float,
                'hedge_ratio': float,
                'spread_mean': float,
                'spread_std': float,
                'half_life': float
            }
        """
        if len(price_A) < 30 or len(price_B) < 30:
            return {'cointegrated': False}
        
        # Ensure same length
        min_len = min(len(price_A), len(price_B))
        A = price_A.iloc[-min_len:].values
        B = price_B.iloc[-min_len:].values
        
        # Engle-Granger cointegration test
        try:
            # Get hedge ratio via OLS
            model = OLS(A, B).fit()
            hedge_ratio = model.params[0]
            
            # Calculate spread
            spread = A - hedge_ratio * B
            
            # Test spread for stationarity (cointegration)
            _, p_value, _ = coint(price_A.iloc[-min_len:], price_B.iloc[-min_len:])
            
            # Calculate spread stats
            spread_mean = np.mean(spread)
            spread_std = np.std(spread)
            
            # Calculate half-life (mean reversion speed)
            spread_lag = np.roll(spread, 1)[1:]
            spread_ret = spread[1:] - spread_lag
            
            half_life_model = OLS(spread_ret, spread_lag - spread_mean).fit()
            lambda_param = half_life_model.params[0]
            half_life = -np.log(2) / lambda_param if lambda_param < 0 else 999
            
            cointegrated = p_value < 0.05 and 1 < half_life < 30
            
            # Store if cointegrated
            if cointegrated:
                self.hedge_ratio = hedge_ratio
                self.spread_mean = spread_mean
                self.spread_std = spread_std
                self.cointegrated = True
            
            return {
                'cointegrated': cointegrated,
                'p_value': p_value,
                'hedge_ratio': hedge_ratio,
                'spread_mean': spread_mean,
                'spread_std': spread_std,
                'half_life': half_life
            }
        except:
            return {'cointegrated': False}
    
    def calculate_z_score(self, price_A: float, price_B: float) -> Optional[float]:
        """
        Calculate current z-score of spread
        
        Returns:
            Z-score or None if not cointegrated
        """
        if not self.cointegrated:
            return None
        
        spread = price_A - self.hedge_ratio * price_B
        z_score = (spread - self.spread_mean) / self.spread_std if self.spread_std > 0 else 0
        
        return z_score
    
    def get_signal(
        self,
        price_A: float,
        price_B: float,
        entry_threshold: float = 2.0,
        exit_threshold: float = 0.5
    ) -> Dict:
        """
        Generate pairs trading signal
        
        Args:
            price_A: Current price of asset A
            price_B: Current price of asset B
            entry_threshold: Z-score threshold for entry (default: 2.0)
            exit_threshold: Z-score threshold for exit (default: 0.5)
        
        Returns:
            {
                'signal': 'LONG_A_SHORT_B' | 'SHORT_A_LONG_B' | 'EXIT' | 'HOLD',
                'z_score': float,
                'confidence': float
            }
        """
        z_score = self.calculate_z_score(price_A, price_B)
        
        if z_score is None:
            return {'signal': 'HOLD', 'z_score': 0, 'confidence': 0}
        
        # Entry signals
        if z_score > entry_threshold:
            # Spread too high → Short A, Long B
            signal = 'SHORT_A_LONG_B'
            confidence = min(0.95, 0.65 + (abs(z_score) - entry_threshold) * 0.1)
        elif z_score < -entry_threshold:
            # Spread too low → Long A, Short B
            signal = 'LONG_A_SHORT_B'
            confidence = min(0.95, 0.65 + (abs(z_score) - entry_threshold) * 0.1)
        
        # Exit signals
        elif abs(z_score) < exit_threshold:
            signal = 'EXIT'
            confidence = 0.70
        
        # Hold
        else:
            signal = 'HOLD'
            confidence = 0.50
        
        return {
            'signal': signal,
            'z_score': z_score,
            'confidence': confidence
        }

# ============================================================================
# NIFTY-BANKNIFTY PAIRS STRATEGY
# ============================================================================
class NiftyBankNiftyPairs:
    """Specialized pairs trading for NIFTY and BANKNIFTY options"""
    
    def __init__(self):
        self.pairs_trader = OptionsPairsTading(lookback_window=60)
        self.position = None
    
    def update_cointegration(self, nifty_prices: pd.Series, banknifty_prices: pd.Series):
        """Update cointegration relationship"""
        result = self.pairs_trader.test_cointegration(nifty_prices, banknifty_prices)
        
        if result.get('cointegrated'):
            print(f"[PAIRS] NIFTY-BANKNIFTY Cointegrated!")
            print(f"  P-value: {result['p_value']:.4f}")
            print(f"  Hedge Ratio: {result['hedge_ratio']:.4f}")
            print(f"  Half-life: {result['half_life']:.1f} days")
        
        return result
    
    def execute_pairs_trade(
        self,
        nifty_spot: float,
        banknifty_spot: float,
        nifty_capital: float,
        banknifty_capital: float
    ) -> Dict:
        """
        Execute pairs trading logic
        
        Returns:
            {
                'action': 'ENTER' | 'EXIT' | 'HOLD',
                'nifty_trade': 'BUY' | 'SELL' | None,
                'banknifty_trade': 'BUY' | 'SELL' | None,
                'nifty_size': float,
                'banknifty_size': float,
                'confidence': float
            }
        """
        signal_info = self.pairs_trader.get_signal(nifty_spot, banknifty_spot)
        
        signal = signal_info['signal']
        z_score = signal_info['z_score']
        confidence = signal_info['confidence']
        
        if signal == 'LONG_A_SHORT_B' and self.position is None:
            # Long NIFTY, Short BANKNIFTY
            return {
                'action': 'ENTER',
                'nifty_trade': 'BUY',
                'banknifty_trade': 'SELL',
                'nifty_size': nifty_capital * 0.5,  # Use 50% capital
                'banknifty_size': banknifty_capital * 0.5 * self.pairs_trader.hedge_ratio,
                'confidence': confidence,
                'z_score': z_score
            }
        
        elif signal == 'SHORT_A_LONG_B' and self.position is None:
            # Short NIFTY, Long BANKNIFTY
            return {
                'action': 'ENTER',
                'nifty_trade': 'SELL',
                'banknifty_trade': 'BUY',
                'nifty_size': nifty_capital * 0.5,
                'banknifty_size': banknifty_capital * 0.5 * self.pairs_trader.hedge_ratio,
                'confidence': confidence,
                'z_score': z_score
            }
        
        elif signal == 'EXIT' and self.position is not None:
            # Exit current position
            return {
                'action': 'EXIT',
                'nifty_trade': None,
                'banknifty_trade': None,
                'nifty_size': 0,
                'banknifty_size': 0,
                'confidence': confidence,
                'z_score': z_score
            }
        
        else:
            return {
                'action': 'HOLD',
                'nifty_trade': None,
                'banknifty_trade': None,
                'nifty_size': 0,
                'banknifty_size': 0,
                'confidence': 0.5,
                'z_score': z_score
            }

# ============================================================================
# EXAMPLE USAGE
# ============================================================================
if __name__ == "__main__":
    print("=" * 60)
    print("Statistical Arbitrage - Pairs Trading Module")
    print("=" * 60)
    
    # Example with synthetic data
    np.random.seed(42)
    days = 100
    
    # Create cointegrated series
    nifty = pd.Series(22000 + np.cumsum(np.random.randn(days) * 100))
    banknifty = pd.Series(48000 + 2.18 * (nifty - 22000) + np.random.randn(days) * 50)
    
    # Test cointegration
    pairs = NiftyBankNiftyPairs()
    result = pairs.update_cointegration(nifty, banknifty)
    
    if result.get('cointegrated'):
        print("\n[SIGNAL TEST]")
        current_nifty = nifty.iloc[-1]
        current_banknifty = banknifty.iloc[-1]
        
        signal = pairs.execute_pairs_trade(
            current_nifty,
            current_banknifty,
            nifty_capital=16666.67,
            banknifty_capital=16666.67
        )
        
        print(f"  Action: {signal['action']}")
        print(f"  NIFTY Trade: {signal['nifty_trade']}")
        print(f"  BANKNIFTY Trade: {signal['banknifty_trade']}")
        print(f"  Z-Score: {signal['z_score']:.2f}")
        print(f"  Confidence: {signal['confidence']:.0%}")
    
    print("\n" + "=" * 60)
    print("Module loaded successfully!")
