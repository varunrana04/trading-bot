"""
VOLATILITY ANALYZER - Historical & Implied Volatility
Based on Options Volatility & Pricing (Natenberg Ch 6)
"""

import numpy as np
import pandas as pd
from scipy.optimize import brentq
from scipy.stats import norm
from typing import Optional, List
from greeks_calculator import GreeksCalculator
from uncorrelated_features import UncorrelatedFeatures

class VolatilityAnalyzer:
    """
    Complete volatility analysis system
    - Historical Volatility calculation
    - Implied Volatility extraction
    - HV/IV comparison
    """
    
    @staticmethod
    def calculate_historical_volatility(prices: np.ndarray, window: int = 20, 
                                       annualization_factor: int = 252) -> float:
        """
        Calculate Historical Volatility using log returns method
        
        From Natenberg Ch 6:
        σ = sqrt(Σ(r_i - r_mean)² / (n-1)) × sqrt(252)
        
        Args:
            prices: Array of historical prices
            window: Number of periods for calculation
            annualization_factor: 252 for daily, 52 for weekly
            
        Returns:
            Annualized historical volatility (decimal)
        """
        if len(prices) < 2:
            return 0.0
        
        # Calculate log returns
        returns = np.log(prices[1:] / prices[:-1])
        
        # Use last 'window' returns
        if len(returns) > window:
            returns = returns[-window:]
        
        # Calculate standard deviation (sample)
        volatility = np.std(returns, ddof=1)
        
        # Annualize
        annual_volatility = volatility * np.sqrt(annualization_factor)
        
        return annual_volatility
    
    @staticmethod
    def rolling_historical_volatility(prices: np.ndarray, window: int = 20) -> np.ndarray:
        """
        Calculate rolling historical volatility
        
        Args:
            prices: Array of historical prices
            window: Rolling window size
            
        Returns:
            Array of rolling HV values
        """
        hv_series = []
        
        for i in range(window, len(prices)):
            window_prices = prices[i-window:i+1]
            hv = VolatilityAnalyzer.calculate_historical_volatility(window_prices, window)
            hv_series.append(hv)
        
        return np.array(hv_series)
    
    @staticmethod
    def implied_volatility(market_price: float, spot: float, strike: float,
                          time_to_expiry: float, risk_free_rate: float = 0.05,
                          option_type: str = 'call') -> Optional[float]:
        """
        Extract Implied Volatility from market price
        
        Uses Newton-Raphson method to find σ where BS(σ) = market_price
        
        Args:
            market_price: Observed market price of option
            spot: Current underlying price
            strike: Strike price
            time_to_expiry: Time to expiration (years)
            risk_free_rate: Risk-free rate
            option_type: 'call' or 'put'
            
        Returns:
            Implied volatility (decimal) or None if not found
        """
        def objective_function(sigma):
            """Function to minimize: BS_price(sigma) - market_price"""
            if sigma <= 0:
                return float('inf')
            
            calc = GreeksCalculator(spot, strike, time_to_expiry, sigma, risk_free_rate)
            theoretical_price = calc.price(option_type)
            return theoretical_price - market_price
        
        try:
            # Search for IV between 1% and 500%
            iv = brentq(objective_function, 0.01, 5.0, xtol=0.0001)
            return iv
        except ValueError:
            # No solution found in range
            return None
    
    @staticmethod
    def iv_percentile(current_iv: float, iv_history: List[float]) -> float:
        """
        Calculate where current IV stands in historical distribution
        
        Args:
            current_iv: Current implied volatility
            iv_history: Historical IV values
            
        Returns:
            Percentile (0-100)
        """
        if not iv_history:
            return 50.0
        
        percentile = (np.sum(np.array(iv_history) < current_iv) / len(iv_history)) * 100
        return percentile
    
    @staticmethod
    def volatility_regime(hv: float, iv: float, price_series: Optional[np.ndarray] = None) -> dict:
        """
        Determine volatility regime (from Natenberg's analysis)
        Enhanced with Uncorrelated Features (Hurst, Entropy)
        
        Args:
            hv: Historical volatility
            iv: Implied volatility
            price_series: Optional price series for advanced feature calculation
            
        Returns:
            Dictionary with regime analysis
        """
        iv_hv_ratio = iv / hv if hv > 0 else 1.0
        
        # Default uncorrelated features
        hurst = 0.5
        entropy = 0.5
        efficiency = 0.5
        
        # Calculate advanced features if series provided
        if price_series is not None and len(price_series) > 20:
            hurst = UncorrelatedFeatures.get_hurst_exponent(price_series)
            entropy = UncorrelatedFeatures.get_shannon_entropy(price_series)
            efficiency = UncorrelatedFeatures.get_efficiency_ratio(price_series)
        
        # Classify regime
        if iv_hv_ratio > 1.2:
            regime = 'IV_EXPENSIVE'
            signal = 'SELL_PREMIUM'
            confidence = min(0.90, 0.65 + (iv_hv_ratio - 1.2) * 0.5)
        elif iv_hv_ratio < 0.8:
            regime = 'IV_CHEAP'
            signal = 'BUY_PREMIUM'
            confidence = min(0.90, 0.65 + (1.0 - iv_hv_ratio) * 0.5)
        else:
            regime = 'IV_FAIR'
            signal = 'NEUTRAL'
            confidence = 0.60
            
        # Adjust confidence based on Hurst (Trend persistence)
        # If Hurst > 0.6 (Strong Trend), selling premium (straddles) is riskier
        if hurst > 0.6 and signal == 'SELL_PREMIUM':
            confidence *= 0.8 # Reduce confidence for short volatility in strong trends
            regime += ' (TRENDING)'
            
        # If Hurst < 0.4 (Mean Reversion), selling premium is safer
        elif hurst < 0.4 and signal == 'SELL_PREMIUM':
            confidence = min(confidence * 1.2, 0.95)
            regime += ' (MEAN_REV)'
            
        # Adjust for Entropy (Noise)
        # High entropy = High noise = Unpredictable = Lower confidence
        if entropy > 0.8:
            confidence *= 0.8
            regime += ' (NOISY)'
        
        return {
            'regime': regime,
            'signal': signal,
            'confidence': confidence,
            'iv_hv_ratio': iv_hv_ratio,
            'hv': hv,
            'iv': iv,
            'hurst': hurst,
            'entropy': entropy,
            'efficiency': efficiency,
            'recommendation': f"IV is {((iv_hv_ratio-1)*100):+.1f}% vs HV"
        }


class VolatilityComparison:
    """Compare multiple options' volatilities"""
    
    def __init__(self, spot_price: float):
        self.spot = spot_price
        self.option_chain = []
    
    def add_option(self, strike: float, market_price: float, expiry: float, option_type: str):
        """Add option to chain for analysis"""
        # Extract IV
        iv = VolatilityAnalyzer.implied_volatility(
            market_price, self.spot, strike, expiry, 0.05, option_type
        )
        
        if iv is not None:
            self.option_chain.append({
                'strike': strike,
                'price': market_price,
                'expiry': expiry,
                'type': option_type,
                'iv': iv,
                'moneyness': strike / self.spot
            })
    
    def analyze_skew(self) -> dict:
        """
        Analyze IV skew across strikes
        
        Returns volatility smile/skew analysis
        """
        if len(self.option_chain) < 3:
            return {'error': 'Need at least 3 options'}
        
        # Separate calls and puts
        calls = [opt for opt in self.option_chain if opt['type'] == 'call']
        puts = [opt for opt in self.option_chain if opt['type'] == 'put']
        
        # Find ATM
        atm_options = sorted(self.option_chain, key=lambda x: abs(x['strike'] - self.spot))
        atm_iv = atm_options[0]['iv'] if atm_options else 0.20
        
        # OTM put IV (downside protection premium)
        otm_puts = [opt for opt in puts if opt['strike'] < self.spot * 0.95]
        otm_put_iv = np.mean([opt['iv'] for opt in otm_puts]) if otm_puts else atm_iv
        
        # Calculate skew
        skew = otm_put_iv - atm_iv
        
        return {
            'atm_iv': atm_iv,
            'otm_put_iv': otm_put_iv,
            'skew': skew,
            'skew_pct': (skew / atm_iv * 100) if atm_iv > 0 else 0,
            'interpretation': 'Steep' if skew > 0.05 else 'Flat' if skew < 0.02 else 'Normal'
        }


# Example usage
if __name__ == "__main__":
    print("="*80)
    print("VOLATILITY ANALYZER - Example")
    print("="*80)
    
    # Generate sample price data
    np.random.seed(42)
    initial_price = 23500
    returns = np.random.normal(0, 0.01, 30)  # 30 days
    prices = initial_price * np.cumprod(1 + returns)
    
    # Calculate HV
    hv = VolatilityAnalyzer.calculate_historical_volatility(prices, window=20)
    print(f"\nHistorical Volatility (20-day): {hv:.2%}")
    
    # Sample market data
    market_price = 185.50
    iv = VolatilityAnalyzer.implied_volatility(
        market_price=market_price,
        spot=23500,
        strike=23500,
        time_to_expiry=7/365,
        option_type='call'
    )
    
    if iv:
        print(f"Implied Volatility:             {iv:.2%}")
        
        # Regime analysis
        regime = VolatilityAnalyzer.volatility_regime(hv, iv)
        print(f"\nVolatility Regime: {regime['regime']}")
        print(f"Signal: {regime['signal']}")
        print(f"Confidence: {regime['confidence']:.0%}")
        print(f"Recommendation: {regime['recommendation']}")
    
    print("\n" + "="*80)
