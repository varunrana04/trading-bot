#!/usr/bin/env python3
"""
ENHANCED OPTIONS STRATEGIES MODULE
Additional features:
- Multi-leg Greeks aggregation
- IV skew analysis
- Historical Vol vs Implied Vol comparison  
- Enhanced risk metrics
"""

import numpy as np
import pandas as pd
from scipy.stats import norm
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass

@dataclass
class GreeksData:
    """Container for option Greeks"""
    delta: float
    gamma: float
    vega: float
    theta: float
    rho: float = 0.0

@dataclass
class OptionLeg:
    """Single option leg in a strategy"""
    strike: float
    option_type: str  # 'CE' or 'PE'
    position: int  # +1 for long, -1 for short
    quantity: int
    premium: float
    greeks: GreeksData

# ============================================================================
# MULTI-LEG GREEKS AGGREGATION
# ============================================================================
class PortfolioGreeks:
    """Calculate and aggregate Greeks across multiple option legs"""
    
    def __init__(self):
        self.legs: List[OptionLeg] = []
    
    def add_leg(self, leg: OptionLeg):
        """Add option leg to portfolio"""
        self.legs.append(leg)
    
    def get_portfolio_greeks(self) -> GreeksData:
        """
        Aggregate Greeks across all legs
        
        Returns:
            GreeksData with portfolio-level Greeks
        """
        if not self.legs:
            return GreeksData(0, 0, 0, 0, 0)
        
        total_delta = sum(leg.greeks.delta * leg.position * leg.quantity for leg in self.legs)
        total_gamma = sum(leg.greeks.gamma * leg.position * leg.quantity for leg in self.legs)
        total_vega = sum(leg.greeks.vega * leg.position * leg.quantity for leg in self.legs)
        total_theta = sum(leg.greeks.theta * leg.position * leg.quantity for leg in self.legs)
        total_rho = sum(leg.greeks.rho * leg.position * leg.quantity for leg in self.legs)
        
        return GreeksData(total_delta, total_gamma, total_vega, total_theta, total_rho)
    
    def is_delta_neutral(self, threshold=0.1) -> bool:
        """Check if portfolio is delta neutral"""
        greeks = self.get_portfolio_greeks()
        return abs(greeks.delta) < threshold
    
    def get_risk_score(self) -> Dict[str, float]:
        """
        Calculate risk scores based on Greeks
        
        Returns:
            Dictionary with risk metrics (0-10 scale, 10=highest risk)
        """
        greeks = self.get_portfolio_greeks()
        
        # Normalize to 0-10 scale
        delta_risk = min(abs(greeks.delta) * 10, 10)
        gamma_risk = min(abs(greeks.gamma) * 100, 10)
        vega_risk = min(abs(greeks.vega) / 10, 10)
        theta_risk = min(abs(greeks.theta) * 5, 10)
        
        overall_risk = (delta_risk + gamma_risk + vega_risk) / 3
        
        return {
            'delta_risk': delta_risk,
            'gamma_risk': gamma_risk,
            'vega_risk': vega_risk,
            'theta_decay': theta_risk,
            'overall_risk': overall_risk
        }

# ============================================================================
# IV SKEW ANALYSIS
# ============================================================================
class IVSkewAnalyzer:
    """Analyze implied volatility skew across strikes"""
    
    def __init__(self):
        self.iv_data: List[Tuple[float, float, str]] = []  # (strike, IV, type)
    
    def add_option(self, strike: float, iv: float, option_type: str):
        """Add option data point"""
        self.iv_data.append((strike, iv, option_type))
    
    def calculate_skew(self, spot: float) -> Dict[str, float]:
        """
        Calculate IV skew metrics
        
        Returns:
            Dictionary with skew analysis
        """
        if len(self.iv_data) < 3:
            return {'skew': 0, 'slope': 0, 'curvature': 0}
        
        # Separate puts and calls
        puts = [(k, iv) for k, iv, t in self.iv_data if t == 'PE']
        calls = [(k, iv) for k, iv, t in self.iv_data if t == 'CE']
        
        # Calculate skew (OTM puts typically have higher IV than OTM calls)
        put_iv_avg = np.mean([iv for _, iv in puts]) if puts else 0
        call_iv_avg = np.mean([iv for _, iv in calls]) if calls else 0
        skew = put_iv_avg - call_iv_avg
        
        # Calculate slope (change in IV per strike)
        all_strikes = sorted([(k, iv) for k, iv, t in self.iv_data])
        if len(all_strikes) >= 2:
            x = np.array([k for k, _ in all_strikes])
            y = np.array([iv for _, iv in all_strikes])
            slope = np.polyfit(x, y, 1)[0]
        else:
            slope = 0
        
        # Curvature (smile)
        if len(all_strikes) >= 3:
            curvature = np.polyfit(x, y, 2)[0]
        else:
            curvature = 0
        
        return {
            'skew': skew,
            'slope': slope,
            'curvature': curvature,
            'put_iv_avg': put_iv_avg,
            'call_iv_avg': call_iv_avg
        }
    
    def get_optimal_strikes(self, spot: float, skew_info: Dict) -> Dict[str, float]:
        """
        Recommend optimal strikes based on skew
        
        Returns:
            Dictionary with recommended strikes
        """
        # If high negative skew (puts expensive), sell puts
        # If flat skew, neutral strategies
        skew = skew_info['skew']
        
        if skew > 0.02:  # Puts expensive
            return {
                'strategy': 'short_put_bias',
                'put_sell_delta': 0.30,  # Sell 30-delta puts
                'call_sell_delta': 0.25   # Conservative on calls
            }
        elif skew < -0.02:  # Calls expensive (rare)
            return {
                'strategy': 'short_call_bias',
                'put_sell_delta': 0.25,
                'call_sell_delta': 0.30
            }
        else:  # Balanced
            return {
                'strategy': 'balanced',
                'put_sell_delta': 0.25,
                'call_sell_delta': 0.25
            }

# ============================================================================
# HISTORICAL VOL vs IMPLIED VOL
# ============================================================================
class VolatilityComparator:
    """Compare historical volatility to implied volatility"""
    
    @staticmethod
    def calculate_historical_vol(prices: pd.Series, window: int = 30) -> float:
        """
        Calculate annualized historical volatility
        
        Args:
            prices: Price series
            window: Lookback window in days
        
        Returns:
            Annualized volatility
        """
        returns = prices.pct_change().dropna()
        if len(returns) < window:
            return 0
        
        recent_returns = returns.tail(window)
        daily_vol = recent_returns.std()
        annualized_vol = daily_vol * np.sqrt(252)
        
        return annualized_vol
    
    @staticmethod
    def get_vol_regime(hv: float, iv: float) -> Dict[str, any]:
        """
        Determine volatility regime based on HV vs IV
        
        Returns:
            Dictionary with regime and trading signals
        """
        iv_hv_ratio = iv / hv if hv > 0 else 1
        
        # Classify regime
        if iv_hv_ratio > 1.2:
            regime = 'IV_EXPENSIVE'
            signal = 'SELL_PREMIUM'
            confidence = min(0.9, 0.65 + (iv_hv_ratio - 1.2) * 0.5)
        elif iv_hv_ratio < 0.8:
            regime = 'IV_CHEAP'
            signal = 'BUY_PREMIUM'
            confidence = min(0.9, 0.65 + (1.0 - iv_hv_ratio) * 0.5)
        else:
            regime = 'IV_FAIR'
            signal = 'NEUTRAL'
            confidence = 0.60
        
        return {
            'regime': regime,
            'signal': signal,
            'confidence': confidence,
            'iv_hv_ratio': iv_hv_ratio,
            'hv': hv,
            'iv': iv
        }
    
    @staticmethod
    def get_strategy_recommendation(vol_info: Dict) -> str:
        """
        Recommend strategy based on vol regime
        
        Returns:
            Strategy name
        """
        regime = vol_info['regime']
        
        if regime == 'IV_EXPENSIVE':
            # Sell premium strategies
            return 'iron_condor'  # Max premium collection
        elif regime == 'IV_CHEAP':
            # Buy premium strategies
            return 'long_straddle'  # Expect big move
        else:
            # Neutral strategies
            return 'iron_butterfly'

# ============================================================================
# ENHANCED RISK METRICS
# ============================================================================
class AdvancedRiskMetrics:
    """Calculate advanced risk metrics for options portfolio"""
    
    @staticmethod
    def calculate_max_loss(strategy_legs: List[OptionLeg], spot: float) -> float:
        """Calculate maximum possible loss"""
        # Simulate price moves and find worst case
        price_range = np.linspace(spot * 0.7, spot * 1.3, 100)
        max_loss = 0
        
        for price in price_range:
            pnl = 0
            for leg in strategy_legs:
                if leg.option_type == 'CE':
                    intrinsic = max(0, price - leg.strike)
                else:
                    intrinsic = max(0, leg.strike - price)
                
                leg_pnl = (leg.premium - intrinsic) * leg.position * leg.quantity
                pnl += leg_pnl
            
            max_loss = min(max_loss, pnl)
        
        return abs(max_loss)
    
    @staticmethod
    def calculate_breakevens(strategy_legs: List[OptionLeg]) -> List[float]:
        """Calculate breakeven points"""
        # For now, simplified calculation
        # TODO: Implement proper numerical solver
        return []
    
    @staticmethod
    def calculate_probability_of_profit(
        strategy_legs: List[OptionLeg],
        spot: float,
        iv: float,
        days_to_expiry: int
    ) -> float:
        """
        Estimate probability of profit at expiry using Monte Carlo
        
        Returns:
            Probability (0-1)
        """
        num_simulations = 1000
        profitable_outcomes = 0
        
        # Simulate price at expiry
        T = days_to_expiry / 365
        for _ in range(num_simulations):
            # Simulate final price
            random_return = np.random.normal(0, iv * np.sqrt(T))
            final_price = spot * (1 + random_return)
            
            # Calculate P/L
            pnl = 0
            for leg in strategy_legs:
                if leg.option_type == 'CE':
                    intrinsic = max(0, final_price - leg.strike)
                else:
                    intrinsic = max(0, leg.strike - final_price)
                
                leg_pnl = (leg.premium - intrinsic) * leg.position * leg.quantity
                pnl += leg_pnl
            
            if pnl > 0:
                profitable_outcomes += 1
        
        return profitable_outcomes / num_simulations

# ============================================================================
# EXAMPLE USAGE
# ============================================================================
if __name__ == "__main__":
    print("Enhanced Options Strategies Module")
    print("=" * 60)
    
    # Example: Portfolio Greeks
    print("\n1. Portfolio Greeks Aggregation")
    portfolio = PortfolioGreeks()
    
    # Add Iron Condor legs
    portfolio.add_leg(OptionLeg(
        strike=22500, option_type='CE', position=-1, quantity=75,
        premium=150, greeks=GreeksData(0.30, 0.02, 50, -10)
    ))
    portfolio.add_leg(OptionLeg(
        strike=23000, option_type='CE', position=1, quantity=75,
        premium=50, greeks=GreeksData(0.10, 0.01, 20, -5)
    ))
    
    greeks = portfolio.get_portfolio_greeks()
    print(f"  Portfolio Delta: {greeks.delta:.2f}")
    print(f"  Portfolio Gamma: {greeks.gamma:.4f}")
    print(f"  Portfolio Vega: {greeks.vega:.2f}")
    print(f"  Delta Neutral: {portfolio.is_delta_neutral()}")
    
    # Example: IV Skew
    print("\n2. IV Skew Analysis")
    skew_analyzer = IVSkewAnalyzer()
    skew_analyzer.add_option(21500, 0.22, 'PE')
    skew_analyzer.add_option(22000, 0.20, 'PE')
    skew_analyzer.add_option(23000, 0.18, 'CE')
    
    skew_info = skew_analyzer.calculate_skew(22000)
    print(f"  Skew: {skew_info['skew']:.4f}")
    print(f"  Put IV Avg: {skew_info['put_iv_avg']:.2%}")
    print(f"  Call IV Avg: {skew_info['call_iv_avg']:.2%}")
    
    # Example: HV vs IV
    print("\n3. Historical Vol vs Implied Vol")
    prices = pd.Series(np.random.randn(60).cumsum() + 22000)
    hv = VolatilityComparator.calculate_historical_vol(prices)
    vol_info = VolatilityComparator.get_vol_regime(hv, 0.20)
    print(f"  Historical Vol: {hv:.2%}")
    print(f"  Implied Vol: {vol_info['iv']:.2%}")
    print(f"  Regime: {vol_info['regime']}")
    print(f"  Signal: {vol_info['signal']}")
    print(f"  Confidence: {vol_info['confidence']:.0%}")
    
    print("\n" + "=" * 60)
    print("Module loaded successfully!")
