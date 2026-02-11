"""
GREEKS CALCULATOR - Complete Suite
Based on Options Volatility & Pricing (Natenberg)
Implements all Greeks: Delta, Gamma, Theta, Vega, Rho
"""

import numpy as np
from scipy.stats import norm
from scipy.optimize import brentq
from typing import Dict, Optional, Literal

class GreeksCalculator:
    """
    Complete Greeks calculator implementing Black-Scholes formulas
    from Natenberg's Options Volatility & Pricing
    """
    
    def __init__(self, spot: float, strike: float, time_to_expiry: float, 
                 volatility: float, risk_free_rate: float = 0.05):
        """
        Args:
            spot: Current underlying price
            strike: Option strike price
            time_to_expiry: Time to expiration in years
            volatility: Annualized volatility (decimal, e.g., 0.20 for 20%)
            risk_free_rate: Risk-free interest rate (decimal)
        """
        self.S = spot
        self.K = strike
        self.T = time_to_expiry
        self.sigma = volatility
        self.r = risk_free_rate
        
        # Calculate d1 and d2 (used by multiple Greeks)
        self._calculate_d_values()
    
    def _calculate_d_values(self):
        """Calculate d1 and d2 from Black-Scholes formula"""
        if self.T <= 0:
            self.d1 = 0
            self.d2 = 0
            return
        
        self.d1 = (np.log(self.S / self.K) + (self.r + 0.5 * self.sigma**2) * self.T) / \
                  (self.sigma * np.sqrt(self.T))
        self.d2 = self.d1 - self.sigma * np.sqrt(self.T)
    
    def price(self, option_type: Literal['call', 'put'] = 'call') -> float:
        """
        Calculate Black-Scholes option price
        
        Args:
            option_type: 'call' or 'put'
            
        Returns:
            Theoretical option price
        """
        if self.T <= 0:
            # At expiration
            if option_type == 'call':
                return max(self.S - self.K, 0)
            else:
                return max(self.K - self.S, 0)
        
        if option_type == 'call':
            price = self.S * norm.cdf(self.d1) - \
                    self.K * np.exp(-self.r * self.T) * norm.cdf(self.d2)
        else:  # put
            price = self.K * np.exp(-self.r * self.T) * norm.cdf(-self.d2) - \
                    self.S * norm.cdf(-self.d1)
        
        return price
    
    def delta(self, option_type: Literal['call', 'put'] = 'call') -> float:
        """
        Calculate Delta (∂V/∂S)
        
        Delta measures the rate of change of option value with respect to 
        changes in the underlying price.
        
        - Call delta: 0 to 1
        - Put delta: -1 to 0
        
        Returns:
            Delta value
        """
        if self.T <= 0:
            if option_type == 'call':
                return 1.0 if self.S > self.K else 0.0
            else:
                return -1.0 if self.S < self.K else 0.0
        
        if option_type == 'call':
            return norm.cdf(self.d1)
        else:  # put
            return -norm.cdf(-self.d1)  # or norm.cdf(self.d1) - 1
    
    def gamma(self) -> float:
        """
        Calculate Gamma (∂²V/∂S² = ∂Δ/∂S)
        
        Gamma measures the rate of change of delta with respect to changes
        in the underlying price. Same for calls and puts.
        
        Key properties (from Natenberg):
        - Highest for ATM options
        - Decreases as option moves ITM or OTM
        - Increases as expiration approaches
        
        Returns:
            Gamma value
        """
        if self.T <= 0 or self.sigma == 0:
            return 0.0
        
        gamma = norm.pdf(self.d1) / (self.S * self.sigma * np.sqrt(self.T))
        return gamma
    
    def theta(self, option_type: Literal['call', 'put'] = 'call') -> float:
        """
        Calculate Theta (∂V/∂t)
        
        Theta measures the rate of change of option value with respect to time.
        Usually negative for long options (time decay).
        
        Book insight (Natenberg Ch 9):
        - ATM theta proportional to volatility / sqrt(time)
        - Accelerates as expiration approaches
        
        Returns:
            Theta per day (divide by 365)
        """
        if self.T <= 0:
            return 0.0
        
        # Common term for both calls and puts
        term1 = -(self.S * norm.pdf(self.d1) * self.sigma) / (2 * np.sqrt(self.T))
        
        if option_type == 'call':
            term2 = -self.r * self.K * np.exp(-self.r * self.T) * norm.cdf(self.d2)
            theta_annual = term1 + term2
        else:  # put
            term2 = self.r * self.K * np.exp(-self.r * self.T) * norm.cdf(-self.d2)
            theta_annual = term1 + term2
        
        return theta_annual / 365  # Convert to per-day theta
    
    def vega(self) -> float:
        """
        Calculate Vega (∂V/∂σ)
        
        Vega measures the sensitivity of option value to changes in volatility.
        Same for calls and puts.
        
        Book insight (Natenberg Ch 9):
        - Long-term options have higher vega than short-term
        - ATM options have highest vega
        
        Returns:
            Vega per 1% change in volatility
        """
        if self.T <= 0:
            return 0.0
        
        vega = self.S * norm.pdf(self.d1) * np.sqrt(self.T)
        return vega / 100  # Per 1% change in IV
    
    def rho(self, option_type: Literal['call', 'put'] = 'call') -> float:
        """
        Calculate Rho (∂V/∂r)
        
        Rho measures the sensitivity of option value to changes in interest rates.
        
        Returns:
            Rho per 1% change in interest rate
        """
        if self.T <= 0:
            return 0.0
        
        if option_type == 'call':
            rho = self.K * self.T * np.exp(-self.r * self.T) * norm.cdf(self.d2)
        else:  # put
            rho = -self.K * self.T * np.exp(-self.r * self.T) * norm.cdf(-self.d2)
        
        return rho / 100  # Per 1% change in rate
    
    def all_greeks(self, option_type: Literal['call', 'put'] = 'call') -> Dict[str, float]:
        """
        Calculate all Greeks at once
        
        Returns:
            Dictionary with all Greeks and option price
        """
        return {
            'price': self.price(option_type),
            'delta': self.delta(option_type),
            'gamma': self.gamma(),
            'theta': self.theta(option_type),
            'vega': self.vega(),
            'rho': self.rho(option_type),
            'underlying': self.S,
            'strike': self.K,
            'time_to_expiry': self.T,
            'volatility': self.sigma,
            'option_type': option_type
        }
    
    def __repr__(self):
        return f"GreeksCalculator(S={self.S}, K={self.K}, T={self.T:.3f}, σ={self.sigma:.2%})"


# Example usage
if __name__ == "__main__":
    # Example: NIFTY option
    calc = GreeksCalculator(
        spot=23500,
        strike=23500,  # ATM
        time_to_expiry=7/365,  # 7 days to expiry
        volatility=0.18,  # 18% IV
        risk_free_rate=0.07  # 7% Indian rates
    )
    
    print("="*80)
    print("GREEKS CALCULATOR - NIFTY 23500 CE (7 Days to Expiry)")
    print("="*80)
    
    greeks = calc.all_greeks('call')
    
    print(f"\nOption Price:  Rs.{greeks['price']:.2f}")
    print(f"\nThe Greeks:")
    print(f"  Delta:   {greeks['delta']:+.4f}  (Price change per Rs.1 move)")
    print(f"  Gamma:   {greeks['gamma']:+.6f}  (Delta change per Rs.1 move)")
    print(f"  Theta:   {greeks['theta']:+.4f}  (Time decay per day)")
    print(f"  Vega:    {greeks['vega']:+.4f}  (Price change per 1% IV move)")
    print(f"  Rho:     {greeks['rho']:+.4f}  (Price change per 1% rate move)")
    print("\n" + "="*80)
