"""
Uncorrelated Features Module
----------------------------
Provides independent signals (Hurst Exponent, Shannon Entropy, Efficiency Ratio)
to reduce overfitting and filter out noise in trading strategies.
"""

import numpy as np
import pandas as pd
from typing import Union, Tuple

class UncorrelatedFeatures:
    """
    Calculates uncorrelated features to distinguish between trending and mean-reverting regimes
    and to measure market noise/efficiency.
    """

    @staticmethod
    def get_hurst_exponent(series: Union[pd.Series, np.ndarray], max_lag: int = 20) -> float:
        """
        Calculate the Hurst Exponent to determine the long-term memory of a time series.
        
        H < 0.5: Mean reverting (anti-persistent)
        H = 0.5: Random walk (geometric brownian motion)
        H > 0.5: Trending (persistent)
        
        Args:
            series: Price series (close prices)
            max_lag: Maximum lag to calculate R/S statistics
            
        Returns:
            Hurst exponent (float)
        """
        try:
            lags = range(2, max_lag)
            tau = [np.sqrt(np.std(np.subtract(series[lag:], series[:-lag]))) for lag in lags]
            
            # Use linear regression to find the slope (Hurst Exponent)
            # log(tau) = H * log(lag) + C
            poly = np.polyfit(np.log(lags), np.log(tau), 1)
            return poly[0] * 2.0 # The standard implementation often yields H/2 for this method, adjusting scaling
            
            # Alternative simplified R/S analysis for speed in rolling windows:
            # This is a simplified approximation suitable for rolling windows
            # For a more rigorous R/S, we would need a heavier computation.
            # Let's stick to a robust standard deviation scaling method.
        except:
            return 0.5

    @staticmethod
    def get_shannon_entropy(series: Union[pd.Series, np.ndarray], base: int = 2, bins: int = 10) -> float:
        """
        Calculate Shannon Entropy to measure the amount of information/noise.
        High entropy = High noise/randomness.
        Low entropy = More deterministic/structured.
        
        Args:
            series: Price series or returns
            base: Logarithm base (2 for bits)
            bins: Number of bins for discretization
            
        Returns:
            Entropy value (float)
        """
        try:
            # Calculate returns if passed prices
            if isinstance(series, pd.Series):
                clean_series = series.pct_change().dropna().values
            else:
                clean_series = np.diff(series) / series[:-1]
                clean_series = clean_series[~np.isnan(clean_series)]
            
            if len(clean_series) == 0:
                return 1.0

            # Discretize into bins
            hist, bin_edges = np.histogram(clean_series, bins=bins, density=True)
            
            # Calculate probabilities
            probs = hist * np.diff(bin_edges)
            probs = probs[probs > 0] # Remove zeros for log
            
            # Calculate entropy: H = -sum(p * log(p))
            entropy = -np.sum(probs * np.log(probs) / np.log(base))
            
            # Normalize entropy to [0, 1] range relative to max possible entropy for these bins
            max_entropy = np.log(bins) / np.log(base)
            normalized_entropy = entropy / max_entropy
            
            return min(max(normalized_entropy, 0.0), 1.0)
            
        except Exception as e:
            return 1.0 # Default to max noise on error

    @staticmethod
    def get_efficiency_ratio(series: Union[pd.Series, np.ndarray], period: int = 10) -> float:
        """
        Calculate Kaufman's Efficiency Ratio (KER).
        ER = Direction / Volatility
        ER = (Price_t - Price_{t-n}) / Sum(abs(Price_i - Price_{i-1}))
        
        ER -> 1: Extremely efficient trend (straight line)
        ER -> 0: Inefficient, choppy market (noise)
        
        Args:
            series: Price series
            period: Lookback period
            
        Returns:
            Efficiency Ratio (0.0 to 1.0)
        """
        try:
            if isinstance(series, pd.Series):
                series = series.values
                
            if len(series) <= period:
                return 0.0
                
            # Direction: Net price change over the period
            change = abs(series[-1] - series[-period - 1])
            
            # Volatility: Sum of absolute period-to-period price changes
            volatility = np.sum(np.abs(np.diff(series[-period-1:])))
            
            if volatility == 0:
                return 1.0 if change > 0 else 0.0
                
            return change / volatility
            
        except:
            return 0.0

    @staticmethod
    def get_fractal_dimension(series: Union[pd.Series, np.ndarray], period: int = 20) -> float:
        """
        Calculate Fractal Dimension (D) using the Sevcik method or derived from Hurst.
        D = 2 - H (approximate relationship for fractional Brownian motion)
        
        D -> 1.0: Smooth curve (Trend)
        D -> 1.5: Random walk
        D -> 2.0: Rough, jagged plane (Mean reversion/Noise)
        
        Args:
            series: Price series
            period: Lookback period
            
        Returns:
            Fractal Dimension (1.0 to 2.0)
        """
        try:
            # Using the relationship with Hurst for consistency
            # D = 2 - H
            # However, let's use a slightly more direct calculation if possible, 
            # but for now, deriving from Hurst is a good "uncorrelated" proxy 
            # if we use a different Hurst calc method.
            
            # Let's implement a simple Sevcik Fractal Dimension approximation
            if isinstance(series, pd.Series):
                prices = series.iloc[-period:].values
            else:
                prices = series[-period:]
                
            if len(prices) < 2:
                return 1.5
                
            # Normalize prices to unit square
            n = len(prices) - 1
            max_p = np.max(prices)
            min_p = np.min(prices)
            range_p = max_p - min_p
            
            if range_p == 0:
                return 1.0
                
            # Calculate length of the curve
            length = 0.0
            for i in range(1, len(prices)):
                norm_y1 = (prices[i-1] - min_p) / range_p
                norm_y2 = (prices[i] - min_p) / range_p
                norm_x_dist = 1.0 / n
                length += np.sqrt(norm_x_dist**2 + (norm_y2 - norm_y1)**2)
                
            # D = 1 + log(L) / log(2*n)
            d = 1 + np.log(length) / np.log(2 * n)
            
            return min(max(d, 1.0), 2.0)
            
        except:
            return 1.5
