"""
Advanced Trading Strategies Module
Mathematical and statistical strategies for institutional-grade trading
"""

from .statistical_arbitrage import StatisticalArbitrage
from .kalman_filter import KalmanFilter, AdaptiveKalmanFilter, KalmanState
from .garch_volatility import GARCHVolatility, RollingGARCH
from .kelly_sizing import KellyCriterion, DynamicKelly, PerformanceStats
from .vpin_microstructure import VPIN, OrderBookImbalance
from .var_risk import ValueAtRisk, RiskManager, VaRMethod
from .uncorrelated_features import UncorrelatedFeatures
from .backtest_safeguards import BacktestSafeguards

__all__ = [
    # Statistical Arbitrage
    'StatisticalArbitrage',
    
    # Kalman Filtering
    'KalmanFilter',
    'AdaptiveKalmanFilter',
    'KalmanState',
    
    # Volatility Forecasting
    'GARCHVolatility',
    'RollingGARCH',
    
    # Position Sizing
    'KellyCriterion',
    'DynamicKelly',
    'PerformanceStats',
    
   # Market Microstructure
    'VPIN',
    'OrderBookImbalance',
    
    # Risk Management
    'ValueAtRisk',
    'RiskManager',
    'VaRMethod',
    
    # Uncorrelated Features
    'UncorrelatedFeatures',
    
    # P-Hacking Safeguards
    'BacktestSafeguards',
]

__version__ = '1.0.0'

print(f"Advanced Strategies Module v{__version__} loaded")
print("Available strategies:")
print("  [OK] Statistical Arbitrage (Cointegration)")
print("  [OK] Kalman Filter (Adaptive Prediction)")
print("  [OK] GARCH (Volatility Forecasting)")
print("  [OK] Kelly Criterion (Optimal Sizing)")
print("  [OK] VPIN (Market Microstructure)")
print("  [OK] Value at Risk (Risk Management)")
print("  [OK] Uncorrelated Features (Hurst, Entropy)")
