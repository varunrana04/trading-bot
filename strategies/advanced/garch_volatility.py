"""
GARCH Model for Volatility Forecasting
Predicts future volatility for dynamic position sizing and risk management
"""

import numpy as np
import pandas as pd
from typing import Tuple, Optional
from arch import arch_model
import warnings
warnings.filterwarnings('ignore')


class GARCHVolatility:
    """
    GARCH(1,1) model for volatility forecasting
    
    Theory:
    Volatility clusters - high volatility periods follow high volatility
    
    Model:
    σ²_t = ω + α*ε²_{t-1} + β*σ²_{t-1}
    
    where:
    - σ²_t = conditional variance at time t
    - ε²_{t-1} = squared return shock (innovation)
    - ω, α, β = parameters (estimated via MLE)
    
    Constraints:
    - ω > 0
    - α, β >= 0
    - α + β < 1 (stationarity)
    """
    
    def __init__(
        self,
        p: int = 1,  # GARCH(p,q) - AR order
        q: int = 1,  # GARCH(p,q) - MA order
        lookback: int = 252  # Days of data for fitting
    ):
        """
        Initialize GARCH model
        
        Args:
            p: AR term order
            q: MA term order
            lookback: Days of returns to use for estimation
        """
        self.p = p
        self.q = q
        self.lookback = lookback
        self.model = None
        self.fitted_model = None
    
    def fit(self, returns: pd.Series) -> bool:
        """
        Fit GARCH model to return series
        
        Args:
            returns: Series of returns (not prices!)
            
        Returns:
            True if fit successful
        """
        try:
            # Use last N observations
            returns_data = returns.tail(self.lookback)
            
            # Convert to percentage returns
            returns_pct = returns_data * 100
            
            # Fit GARCH(p,q) model
            self.model = arch_model(
                returns_pct,
                vol='Garch',
                p=self.p,
                q=self.q,
                dist='normal'
            )
            
            self.fitted_model = self.model.fit(disp='off', show_warning=False)
            
            # Extract parameters
            params = self.fitted_model.params
            omega = params['omega']
            alpha = params['alpha[1]'] if self.p > 0 else 0
            beta = params['beta[1]'] if self.q > 0 else 0
            
            print(f"[GARCH] Model fitted successfully")
            print(f"  ω (omega): {omega:.6f}")
            print(f"  α (alpha): {alpha:.6f}")
            print(f"  β (beta): {beta:.6f}")
            print(f"  Persistence (α+β): {alpha+beta:.6f}")
            
            return True
            
        except Exception as e:
            print(f"[GARCH] Fit failed: {e}")
            return False
    
    def forecast(self, horizon: int = 1) -> Tuple[np.ndarray, np.ndarray]:
        """
        Forecast volatility
        
        Args:
            horizon: Number of periods ahead to forecast
            
        Returns:
            (mean_forecast, variance_forecast)
        """
        if self.fitted_model is None:
            raise ValueError("Model not fitted. Call fit() first.")
        
        forecast = self.fitted_model.forecast(horizon=horizon)
        
        # Extract variance forecast
        variance_forecast = forecast.variance.values[-1, :]
        
        # Convert back from percentage to decimal
        variance_forecast = variance_forecast / (100**2)
        
        # Mean is assumed zero in GARCH
        mean_forecast = np.zeros(horizon)
        
        return mean_forecast, variance_forecast
    
    def get_current_volatility(self) -> float:
        """Get current (last) conditional volatility"""
        if self.fitted_model is None:
            return 0.0
        
        # Conditional volatility (std dev)
        cond_vol = self.fitted_model.conditional_volatility.iloc[-1]
        
        # Convert from percentage to decimal
        return cond_vol / 100
    
    def forecast_volatility(self, horizon: int = 1) -> float:
        """
        Forecast volatility (standard deviation) for next period
        
        Args:
            horizon: Periods ahead (usually 1 for next day)
            
        Returns:
            Forecasted volatility (annualized std dev)
        """
        _, variance_forecast = self.forecast(horizon)
        
        # Volatility = sqrt(variance)
        vol_forecast = np.sqrt(variance_forecast[0])
        
        # Annualize (assuming daily data)
        annual_vol = vol_forecast * np.sqrt(252)
        
        return annual_vol
    
    def get_volatility_regime(self) -> str:
        """
        Classify current volatility regime
        
        Returns:
            'LOW' | 'NORMAL' | 'HIGH' | 'EXTREME'
        """
        if self.fitted_model is None:
            return 'UNKNOWN'
        
        current_vol = self.get_current_volatility()
        
        # Get historical volatility distribution
        historical_vol = self.fitted_model.conditional_volatility / 100
        
        # Percentile-based regime
        percentile = (historical_vol < current_vol).mean() * 100
        
        if percentile < 25:
            return 'LOW'
        elif percentile < 75:
            return 'NORMAL'
        elif percentile < 95:
            return 'HIGH'
        else:
            return 'EXTREME'
    
    def get_position_size_multiplier(self) -> float:
        """
        Get position size multiplier based on volatility forecast
        
        Lower volatility → larger positions
        Higher volatility → smaller positions
        
        Returns:
            Multiplier (0.5 to 2.0)
        """
        regime = self.get_volatility_regime()
        
        multipliers = {
            'LOW': 1.5,      # Increase size 50%
            'NORMAL': 1.0,   # Normal size
            'HIGH': 0.75,    # Reduce size 25%
            'EXTREME': 0.5,  # Reduce size 50%
            'UNKNOWN': 1.0
        }
        
        return multipliers[regime]


class RollingGARCH(GARCHVolatility):
    """
    Rolling GARCH - automatically refits model periodically
    """
    
    def __init__(self, refit_frequency: int = 30, **kwargs):
        """
        Args:
            refit_frequency: Refit model every N observations
        """
        super().__init__(**kwargs)
        self.refit_frequency = refit_frequency
        self.obs_since_fit = 0
        self.return_buffer = []
    
    def update(self, new_return: float) -> bool:
        """
        Add new observation and refit if needed
        
        Args:
            new_return: Latest return observation
            
        Returns:
            True if model was refit
        """
        self.return_buffer.append(new_return)
        self.obs_since_fit += 1
        
        # Keep buffer size manageable
        if len(self.return_buffer) > self.lookback + 100:
            self.return_buffer = self.return_buffer[-self.lookback:]
        
        # Refit if needed and we have enough data
        if (self.obs_since_fit >= self.refit_frequency and 
            len(self.return_buffer) >= 50):
            
            returns_series = pd.Series(self.return_buffer)
            success = self.fit(returns_series)
            
            if success:
                self.obs_since_fit = 0
                return True
        
        return False


# Example usage
if __name__ == "__main__":
    print("GARCH Volatility Forecasting")
    print("=" * 60)
    
    # Create model
    garch = RollingGARCH(
        p=1,
        q=1,
        lookback=252,
        refit_frequency=30
    )
    
    print("\nGARCH(1,1) model initialized")
    print("  Automatically refits every 30 observations")
    print("  Forecasts next-period volatility")
    print("  Adapts position sizing to volatility regime")
    print("\nReady to forecast BTC/ETH volatility")
