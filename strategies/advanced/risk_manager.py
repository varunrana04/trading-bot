"""
RISK MANAGEMENT SYSTEM - Phase 4
Complete risk framework for options trading
Based on Natenberg Ch 10 & 14
"""

import numpy as np
from typing import Dict, List
from greeks_calculator import GreeksCalculator

class RiskManager:
    """
    Complete Risk Management System
    Implements position limits, VaR, Greeks monitoring
    """
    
    def __init__(self, capital: float, max_position_pct: float = 0.10,
                 max_delta_pct: float = 0.15, max_vega_per_100k: float = 1000):
        self.capital = capital
        self.max_position_size = capital * max_position_pct
        self.max_portfolio_delta = max_delta_pct  # 15% max directional
        self.max_vega = (capital /100000) * max_vega_per_100k  # $1k vega per $100k
        
        self.positions = []
        self.alerts = []
    
    def check_position_limits(self, new_position_cost: float, new_greeks: Dict) -> Dict:
        """
        Pre-trade risk check
        Returns approval/rejection with reasons
        """
        violations = []
        
        # Position size check
        if abs(new_position_cost) > self.max_position_size:
            violations.append(
                f"Position size Rs.{abs(new_position_cost):.2f} exceeds limit Rs.{self.max_position_size:.2f}"
            )
        
        # Delta check
        current_delta = sum(pos['greeks']['delta'] for pos in self.positions)
        new_total_delta = current_delta + new_greeks['delta']
        
        if abs(new_total_delta) > self.max_portfolio_delta:
            violations.append(
                f"Portfolio delta {new_total_delta:.2f} exceeds limit {self.max_portfolio_delta:.2f}"
            )
        
        # Vega check
        current_vega = sum(pos['greeks']['vega'] for pos in self.positions)
        new_total_vega = current_vega + new_greeks['vega']
        
        if abs(new_total_vega) > self.max_vega:
            violations.append(
                f"Portfolio vega {new_total_vega:.2f} exceeds limit {self.max_vega:.2f}"
            )
        
        return {
            'approved': len(violations) == 0,
            'violations': violations,
            'projected_delta': new_total_delta,
            'projected_vega': new_total_vega
        }
    
    def calculate_var(self, confidence: float = 0.95, holding_days: int = 1) -> float:
        """
        Calculate Value at Risk using delta-gamma-vega approximation
        """
        # Aggregate portfolio Greeks
        total_delta = sum(pos['greeks']['delta'] for pos in self.positions)
        total_gamma = sum(pos['greeks']['gamma'] for pos in self.positions)
        total_vega = sum(pos['greeks']['vega'] for pos in self.positions)
        
        # Estimate spot price move (assume 20% annual vol)
        daily_vol = 0.20 / np.sqrt(252)
        spot_move = 23500 * daily_vol * np.sqrt(holding_days)  # Simplified
        
        # Delta risk
        delta_risk = total_delta * spot_move
        
        # Gamma risk (convexity)
        gamma_risk = 0.5 * total_gamma * spot_move**2
        
        # Vega risk (assume IV can move 5% in a day)
        vega_risk = total_vega * 5  # 5% IV move
        
        # Z-score for confidence level
        from scipy.stats import norm
        z_score = norm.ppf(confidence)
        
        total_risk = abs(delta_risk) + abs(gamma_risk) + abs(vega_risk)
        var = z_score * total_risk
        
        return var
    
    def portfolio_metrics(self) -> Dict:
        """Get current portfolio risk metrics"""
        total_greeks = {
            'delta': sum(p['greeks']['delta'] for p in self.positions),
            'gamma': sum(p['greeks']['gamma'] for p in self.positions),
            'theta': sum(p['greeks']['theta'] for p in self.positions),
            'vega': sum(p['greeks']['vega'] for p in self.positions)
        }
        
        return {
            'num_positions': len(self.positions),
            'total_cost': sum(p['cost'] for p in self.positions),
            'greeks': total_greeks,
            'delta_utilization': abs(total_greeks['delta']) / self.max_portfolio_delta,
            'vega_utilization': abs(total_greeks['vega']) / self.max_vega,
            'var_95': self.calculate_var(0.95, 1)
        }


if __name__ == "__main__":
    print("="*80)
    print("RISK MANAGEMENT SYSTEM - Phase 4")
    print("="*80)
    
    rm = RiskManager(capital=1000000)  # 10L capital
    
    # Example: New straddle position
    new_greeks = {
        'delta': 0.05,
        'gamma': 0.0015,
        'theta': -35,
        'vega': 28
    }
    new_cost = 50000
    
    check = rm.check_position_limits(new_cost, new_greeks)
    
    print("\nPosition Pre-Trade Check:")
    print(f"  Approved: {check['approved']}")
    print(f"  Projected Delta: {check['projected_delta']:.4f}")
    print(f"  Projected Vega: {check['projected_vega']:.2f}")
    
    if check['violations']:
        print("\n  Violations:")
        for v in check['violations']:
            print(f"    - {v}")
    
    print("\n" + "="*80)
