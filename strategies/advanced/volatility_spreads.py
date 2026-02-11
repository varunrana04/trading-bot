"""
VOLATILITY SPREADS - Complete Suite
Based on Options Volatility & Pricing Ch 11-13 (Natenberg)

Implements: Straddles, Strangles, Butterflies, Calendars, Ratios, Christmas Trees
"""

import numpy as np
from typing import Dict, List, Literal, Optional
from greeks_calculator import GreeksCalculator

class VolatilitySpread:
    """Base class for all option spreads"""
    
    def __init__(self, spot: float, volatility: float, risk_free_rate: float = 0.05):
        self.spot = spot
        self.volatility = volatility
        self.r = risk_free_rate
        self.legs = []
    
    def add_leg(self, strike: float, expiry_days: int, quantity: int,
                option_type: Literal['call', 'put']):
        """Add option leg to spread"""
        calc = GreeksCalculator(self.spot, strike, expiry_days/365, self.volatility, self.r)
        greeks = calc.all_greeks(option_type)
        
        self.legs.append({
            'strike': strike,
            'expiry_days': expiry_days,
            'quantity': quantity,
            'type': option_type,
            'price': greeks['price'],
            'delta': greeks['delta'],
            'gamma': greeks['gamma'],
            'theta': greeks['theta'],
            'vega': greeks['vega']
        })
    
    def portfolio_greeks(self) -> Dict:
        """Calculate portfolio-level Greeks"""
        total = {
            'cost': 0,
            'delta': 0,
            'gamma': 0,
            'theta': 0,
            'vega': 0
        }
        
        for leg in self.legs:
            total['cost'] += leg['quantity'] * leg['price']
            total['delta'] += leg['quantity'] * leg['delta']
            total['gamma'] += leg['quantity'] * leg['gamma']
            total['theta'] += leg['quantity'] * leg['theta']
            total['vega'] += leg['quantity'] * leg['vega']
        
        return total


class Straddle(VolatilitySpread):
    """
    Long/Short Straddle - Basic volatility play
    Ch 11: Buy/Sell ATM call + ATM put
    """
    
    def __init__(self, spot: float, strike: float, expiry_days: int,
                 volatility: float, position: Literal['long', 'short'] = 'long'):
        super().__init__(spot, volatility)
        self.strike = strike
        self.expiry = expiry_days
        self.position = +1 if position == 'long' else -1
        
        # Add legs
        self.add_leg(strike, expiry_days, self.position, 'call')
        self.add_leg(strike, expiry_days, self.position, 'put')
    
    def breakeven_points(self) -> Dict:
        """Calculate breakeven prices at expiration"""
        greeks = self.portfolio_greeks()
        cost = abs(greeks['cost'])
        
        upper_breakeven = self.strike + cost
        lower_breakeven = self.strike - cost
        
        return {
            'upper': upper_breakeven,
            'lower': lower_breakeven,
            'range': 2 * cost,
            'interpretation': f"Profit if spot moves beyond [{lower_breakeven:.0f}, {upper_breakeven:.0f}]"
        }


class Strangle(VolatilitySpread):
    """
    Long/Short Strangle - Wider breakevens than straddle
    Ch 11: Buy/Sell OTM call + OTM put
    """
    
    def __init__(self, spot: float, call_strike: float, put_strike: float,
                 expiry_days: int, volatility: float, 
                 position: Literal['long', 'short'] = 'long'):
        super().__init__(spot, volatility)
        self.call_strike = call_strike
        self.put_strike = put_strike
        self.expiry = expiry_days
        self.position = +1 if position == 'long' else -1
        
        # Add legs
        self.add_leg(call_strike, expiry_days, self.position, 'call')
        self.add_leg(put_strike, expiry_days, self.position, 'put')


class Butterfly(VolatilitySpread):
    """
    Butterfly Spread - Limited risk, limited profit
    Ch 11: 1-2-1 ratio spread
    """
    
    def __init__(self, spot: float, low_strike: float, mid_strike: float,
                 high_strike: float, expiry_days: int, volatility: float,
                 option_type: Literal['call', 'put'] = 'call'):
        super().__init__(spot, volatility)
        
        # Classic 1-2-1 structure
        self.add_leg(low_strike, expiry_days, +1, option_type)   # Buy 1
        self.add_leg(mid_strike, expiry_days, -2, option_type)   # Sell 2
        self.add_leg(high_strike, expiry_days, +1, option_type)  # Buy 1
        
        self.max_profit = high_strike - mid_strike  # Wing width
    
    def profit_zone(self) -> Dict:
        """Determine profitable price range"""
        greeks = self.portfolio_greeks()
        cost = abs(greeks['cost'])
        
        # Simplified - actual would need full P/L calculation
        return {
            'max_profit_at': self.legs[1]['strike'],  # Middle strike
            'max_profit': self.max_profit - cost,
            'max_loss': cost
        }


class CalendarSpread(VolatilitySpread):
    """
    Calendar (Time) Spread - Profit from theta decay differential
    Ch 11: Sell near-term, buy far-term at same strike
    """
    
    def __init__(self, spot: float, strike: float, 
                 near_expiry_days: int, far_expiry_days: int,
                 volatility: float, option_type: Literal['call', 'put'] = 'call'):
        super().__init__(spot, volatility)
        
        self.add_leg(strike, near_expiry_days, -1, option_type)  # Sell near
        self.add_leg(strike, far_expiry_days, +1, option_type)   # Buy far
        
    def theta_advantage(self) -> Dict:
        """Calculate theta decay differential"""
        near_theta = self.legs[0]['theta']
        far_theta = self.legs[1]['theta']
        
        daily_profit = abs(near_theta) - abs(far_theta)
        
        return {
            'near_theta': near_theta,
            'far_theta': far_theta,
            'daily_advantage': daily_profit,
            'strategy': 'Profit from near option decaying faster'
        }


class RatioSpread(VolatilitySpread):
    """
    Ratio Spread - Sell more than buy
    Ch 13: Example 1x2 or 1x3 ratio
    """
    
    def __init__(self, spot: float, buy_strike: float, sell_strike: float,
                 expiry_days: int, ratio: int, volatility: float,
                 option_type: Literal['call', 'put'] = 'call'):
        super().__init__(spot, volatility)
        
        self.add_leg(buy_strike, expiry_days, +1, option_type)      # Buy 1
        self.add_leg(sell_strike, expiry_days, -ratio, option_type)  # Sell ratio


class ChristmasTree(VolatilitySpread):
    """
    Christmas Tree Spread - Extended butterfly variant
    Page 200: 1-1-1-1 structure with varying deltas
    """
    
    def __init__(self, spot: float, strikes: List[float], expiry_days: int,
                 volatility: float, tree_type: Literal['long', 'short'] = 'long',
                 option_type: Literal['call', 'put'] = 'put'):
        super().__init__(spot, volatility)
        
        if len(strikes) != 4:
            raise ValueError("Christmas tree needs exactly 4 strikes")
        
        if tree_type == 'long':
            # Long Put Christmas Tree (from book pg 200)
            quantities = [+1, -1, -1, +1]
        else:
            # Short Put Christmas Tree
            quantities = [-1, +1, +1, -1]
        
        for strike, qty in zip(sorted(strikes, reverse=True), quantities):
            self.add_leg(strike, expiry_days, qty, option_type)


class SpreadAnalyzer:
    """Analyze and compare different spread strategies"""
    
    @staticmethod
    def compare_spreads(spreads: List[VolatilitySpread]):
        """Compare multiple spreads side by side"""
        import pandas as pd
        
        data = []
        for i, spread in enumerate(spreads):
            greeks = spread.portfolio_greeks()
            data.append({
                'Spread': f"Spread {i+1}",
                'Cost': greeks['cost'],
                'Delta': greeks['delta'],
                'Gamma': greeks['gamma'],
                'Theta': greeks['theta'],
                'Vega': greeks['vega']
            })
        
        return pd.DataFrame(data)
    
    @staticmethod
    def breakeven_volatility(spread: VolatilitySpread, target_pnl: float = 0) -> float:
        """
        Find implied volatility where spread P/L = target
        From Ch 13 - breakeven volatility analysis
        """
        # Simplified - would need full revaluation at different IVs
        greeks = spread.portfolio_greeks()
        current_cost = greeks['cost']
        vega = greeks['vega']
        
        if abs(vega) < 0.01:
            return spread.volatility
        
        # Approximate: Change in IV needed
        iv_change = (target_pnl - current_cost) / vega
        breakeven_iv = spread.volatility + (iv_change / 100)
        
        return max(0.01, breakeven_iv)


# Example usage
if __name__ == "__main__":
    print("="*80)
    print("VOLATILITY SPREADS - Standalone System")
    print("="*80)
    
    spot = 23500
    vol = 0.18
    expiry = 7
    
    # 1. Long Straddle
    print("\n1. LONG STRADDLE (ATM)")
    print("-" * 40)
    straddle = Straddle(spot, 23500, expiry, vol, 'long')
    greeks = straddle.portfolio_greeks()
    breakevens = straddle.breakeven_points()
    
    print(f"Cost: Rs.{greeks['cost']:.2f}")
    print(f"Delta: {greeks['delta']:+.4f} (should be ~0 for ATM)")
    print(f"Gamma: {greeks['gamma']:+.6f}")
    print(f"Theta: {greeks['theta']:+.4f}")
    print(f"Vega:  {greeks['vega']:+.4f}")
    print(f"\nBreakevens: {breakevens['lower']:.0f} - {breakevens['upper']:.0f}")
    
    # 2. Calendar Spread
    print("\n2. CALENDAR SPREAD (ATM)")
    print("-" * 40)
    calendar = CalendarSpread(spot, 23500, 7, 30, vol, 'call')
    greeks = calendar.portfolio_greeks()
    theta_adv = calendar.theta_advantage()
    
    print(f"Cost: Rs.{greeks['cost']:.2f}")
    print(f"Theta Advantage: Rs.{theta_adv['daily_advantage']:.2f}/day")
    print(f"Vega: {greeks['vega']:+.4f}")
    
    # 3. Butterfly
    print("\n3. BUTTERFLY SPREAD")
    print("-" * 40)
    butterfly = Butterfly(spot, 23400, 23500, 23600, expiry, vol, 'call')
    greeks = butterfly.portfolio_greeks()
    
    print(f"Cost: Rs.{greeks['cost']:.2f}")
    print(f"Delta: {greeks['delta']:+.4f}")
    print(f"Max Profit: Rs.{butterfly.max_profit:.2f}")
    
    print("\n" + "="*80)
