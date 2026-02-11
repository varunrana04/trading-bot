"""
Value at Risk (VaR) and Risk Management
Quantifies maximum expected loss at a given confidence level
"""

import numpy as np
import pandas as pd
from scipy import stats
from typing import Tuple, List, Dict, Optional
from enum import Enum


class VaRMethod(Enum):
    """Methods for calculating VaR"""
    HISTORICAL = "historical"
    PARAMETRIC = "parametric"
    MONTE_CARLO = "monte_carlo"


class ValueAtRisk:
    """
    Value at Risk (VaR) calculator
    
    Theory:
    VaR = Maximum expected loss at confidence level over time horizon
    
    Example:
    95% Daily VaR = $1000
    → 95% confident we won't lose more than $1000 tomorrow
    → 5% chance of losing more than $1000
    
    Three Methods:
    1. Historical: Use empirical distribution of past returns
    2. Parametric: Assume normal distribution
    3. Monte Carlo: Simulate many scenarios
    """
    
    def __init__(
        self,
        confidence_level: float = 0.95,
        time_horizon: int = 1  # Days
    ):
        """
        Args:
            confidence_level: e.g., 0.95 for 95%
            time_horizon: Days ahead to calculate VaR
        """
        self.confidence_level = confidence_level
        self.time_horizon = time_horizon
        self.return_history = []
    
    def add_return(self, ret: float) -> None:
        """Add a return observation"""
        self.return_history.append(ret)
    
    def calculate_historical_var(
        self,
        returns: Optional[np.ndarray] = None
    ) -> float:
        """
        Historical VaR - use empirical distribution
        
        Args:
            returns: Return series, or None to use stored history
            
        Returns:
            VaR (positive number = loss)
        """
        if returns is None:
            if len(self.return_history) == 0:
                return 0.0
            returns = np.array(self.return_history)
        
        # Find percentile
        alpha = 1 - self.confidence_level
        var = -np.percentile(returns, alpha * 100)
        
        # Scale by time horizon (sqrt rule)
        var_scaled = var * np.sqrt(self.time_horizon)
        
        return var_scaled
    
    def calculate_parametric_var(
        self,
        returns: Optional[np.ndarray] = None
    ) -> float:
        """
        Parametric VaR - assume normal distribution
        
        Formula:
        VaR = μ - z_α * σ * sqrt(T)
        
        where z_α is the z-score for confidence level
        """
        if returns is None:
            if len(self.return_history) == 0:
                return 0.0
            returns = np.array(self.return_history)
        
        mu = np.mean(returns)
        sigma = np.std(returns)
        
        # Z-score for confidence level
        # 0.95 → 1.645, 0.99 → 2.326
        z_score = stats.norm.ppf(1 - self.confidence_level)
        
        # VaR calculation
        var = -(mu + z_score * sigma) * np.sqrt(self.time_horizon)
        
        return max(0, var)
    
    def calculate_cvar(
        self,
        returns: Optional[np.ndarray] = None,
        method: VaRMethod = VaRMethod.HISTORICAL
    ) -> float:
        """
        Conditional VaR (CVaR) / Expected Shortfall
        
        Definition:
        Expected loss given that VaR is exceeded
        
        CVaR is always >= VaR and is a coherent risk measure
        """
        if returns is None:
            if len(self.return_history) == 0:
                return 0.0
            returns = np.array(self.return_history)
        
        # Calculate VaR first
        if method == VaRMethod.HISTORICAL:
            var = self.calculate_historical_var(returns)
        else:
            var = self.calculate_parametric_var(returns)
        
        # CVaR = average of losses worse than VaR
        losses = -returns
        losses_beyond_var = losses[losses > var]
        
        if len(losses_beyond_var) == 0:
            return var  # If no losses beyond VaR, CVaR = VaR
        
        cvar = np.mean(losses_beyond_var)
        
        return cvar
    
    def calculate_portfolio_var(
        self,
        portfolio_returns: np.ndarray,
        method: VaRMethod = VaRMethod.HISTORICAL
    ) -> Dict:
        """
        Calculate comprehensive VaR metrics for portfolio
        
        Returns:
            Dict with VaR, CVaR, and other risk metrics
        """
        if method == VaRMethod.HISTORICAL:
            var = self.calculate_historical_var(portfolio_returns)
        else:
            var = self.calculate_parametric_var(portfolio_returns)
        
        cvar = self.calculate_cvar(portfolio_returns, method)
        
        # Additional metrics
        volatility = np.std(portfolio_returns) * np.sqrt(252)  # Annualized
        max_drawdown = self._calculate_max_drawdown(portfolio_returns)
        
        return {
            'var': var,
            'cvar': cvar,
            'volatility_annual': volatility,
            'max_drawdown': max_drawdown,
            'confidence_level': self.confidence_level,
            'time_horizon': self.time_horizon,
            'method': method.value
        }
    
    def _calculate_max_drawdown(self, returns: np.ndarray) -> float:
        """Calculate maximum drawdown from return series"""
        cumulative = np.cumprod(1 + returns)
        running_max = np.maximum.accumulate(cumulative)
        drawdown = (cumulative - running_max) / running_max
        return abs(np.min(drawdown))
    
    def check_risk_limit(
        self,
        current_var: float,
        max_var_pct: float = 0.02
    ) -> Tuple[bool, str]:
        """
        Check if current VaR exceeds risk limit
        
        Args:
            current_var: Current VaR as fraction of portfolio
            max_var_pct: Maximum allowed VaR (e.g., 0.02 = 2%)
            
        Returns:
            (is_safe, message)
        """
        if current_var <= max_var_pct:
            return True, f"VaR {current_var:.2%} within limit ({max_var_pct:.2%})"
        else:
            excess = current_var - max_var_pct
            return False, f"VaR {current_var:.2%} exceeds limit by {excess:.2%}"


class RiskManager:
    """
    Comprehensive risk management system
    Integrates VaR, position limits, and circuit breakers
    """
    
    def __init__(
        self,
        max_var_pct: float = 0.02,          # Max 2% VaR
        max_position_pct: float = 0.20,      # Max 20% per position
        max_daily_loss_pct: float = -0.05,   # Max 5% daily loss
        max_drawdown_pct: float = -0.15      # Max 15% drawdown
    ):
        """Initialize risk manager"""
        self.max_var_pct = max_var_pct
        self.max_position_pct = max_position_pct
        self.max_daily_loss_pct = max_daily_loss_pct
        self.max_drawdown_pct = max_drawdown_pct
        
        self.var_calculator = ValueAtRisk(confidence_level=0.95)
        
        # Track daily performance
        self.daily_pnl = 0.0
        self.peak_capital = 0.0
    
    def check_all_limits(
        self,
        current_capital: float,
        position_size: float,
        returns: np.ndarray
    ) -> Dict:
        """
        Check all risk limits
        
        Returns:
            {
                'can_trade': bool,
                'warnings': list,
                'metrics': dict
            }
        """
        warnings = []
        
        # 1. Check VaR
        var_metrics = self.var_calculator.calculate_portfolio_var(returns)
        var_pct = var_metrics['var'] / current_capital if current_capital > 0 else 0
        
        if var_pct > self.max_var_pct:
            warnings.append(f"VaR ({var_pct:.2%}) exceeds limit ({self.max_var_pct:.2%})")
        
        # 2. Check position size
        position_pct = position_size / current_capital if current_capital > 0 else 0
        
        if position_pct > self.max_position_pct:
            warnings.append(f"Position ({position_pct:.2%}) exceeds limit ({self.max_position_pct:.2%})")
        
        # 3. Check daily loss
        daily_loss_pct = self.daily_pnl / self.peak_capital if self.peak_capital > 0 else 0
        
        if daily_loss_pct < self.max_daily_loss_pct:
            warnings.append(f"Daily loss ({daily_loss_pct:.2%}) hit limit ({self.max_daily_loss_pct:.2%})")
        
        # 4. Check drawdown
        if self.peak_capital > 0:
            drawdown_pct = (current_capital - self.peak_capital) / self.peak_capital
            
            if drawdown_pct < self.max_drawdown_pct:
                warnings.append(f"Drawdown ({drawdown_pct:.2%}) hit limit ({self.max_drawdown_pct:.2%})")
        
        # Update peak
        if current_capital > self.peak_capital:
            self.peak_capital = current_capital
        
        can_trade = len(warnings) == 0
        
        return {
            'can_trade': can_trade,
            'warnings': warnings,
            'metrics': {
                **var_metrics,
                'position_pct': position_pct,
                'daily_loss_pct': daily_loss_pct
            }
        }


# Example usage
if __name__ == "__main__":
    print("Value at Risk (VaR) - Risk Management")
    print("=" * 60)
    
    # Create VaR calculator
    var = ValueAtRisk(confidence_level=0.95, time_horizon=1)
    
    print("\nVaR calculator initialized:")
    print("  Confidence: 95%")
    print("  Horizon: 1 day")
    
    print("\nInterpretation:")
    print("  95% Daily VaR = $1000")
    print("  → 95% confident won't lose more than $1000 tomorrow")
    
    # Create risk manager
    risk_mgr = RiskManager(
        max_var_pct=0.02,
        max_position_pct=0.20,
        max_daily_loss_pct=-0.05,
        max_drawdown_pct=-0.15
    )
    
    print("\n" + "=" * 60)
    print("Risk Manager initialized with limits:")
    print("  Max VaR: 2% of portfolio")
    print("  Max position: 20% per trade")
    print("  Max daily loss: -5%")
    print("  Max drawdown: -15%")
    
    print("\nCircuit breakers will stop trading if limits exceeded")
