"""
Kalman Filter for Adaptive Price Prediction
Superior to moving averages - filters noise and predicts next price
"""

import numpy as np
from typing import Tuple, Dict
from dataclasses import dataclass


@dataclass
class KalmanState:
    """State vector for Kalman filter"""
    price: float  # Estimated true price
    velocity: float  # Price velocity (first derivative)
    acceleration: float  # Price acceleration (second derivative)


class KalmanFilter:
    """
    Kalman Filter for price tracking and prediction
    
    Theory:
    - Price observations are noisy
    - True price follows a physical model (constant acceleration)
    - Kalman filter optimally estimates true state
    
    State Model:
    X_t = [price, velocity, acceleration]
    
    State transition:
    price_{t+1} = price_t + velocity_t*dt + 0.5*acceleration_t*dt²
    velocity_{t+1} = velocity_t + acceleration_t*dt
    acceleration_{t+1} = acceleration_t (random walk)
    
    Measurement:
    observed_price_t = true_price_t + noise
    """
    
    def __init__(
        self,
        process_variance: float = 1e-5,
        measurement_variance: float = 1e-3,
        dt: float = 1.0
    ):
        """
        Initialize Kalman filter
        
        Args:
            process_variance: How much we expect the model to deviate (Q)
            measurement_variance: How noisy are price observations (R)
            dt: Time step
        """
        self.dt = dt
        
        # State vector: [price, velocity, acceleration]
        self.x = np.zeros(3)  # State estimate
        
        # Covariance matrix (uncertainty in state)
        self.P = np.eye(3) * 1000  # Start very uncertain
        
        # State transition matrix (F)
        # price_{t+1} = price_t + vel*dt + 0.5*acc*dt²
        # vel_{t+1} = vel_t + acc*dt
        # acc_{t+1} = acc_t
        self.F = np.array([
            [1, dt, 0.5*dt**2],
            [0, 1, dt],
            [0, 0, 1]
        ])
        
        # Measurement matrix (H)
        # We only observe price, not velocity or acceleration
        self.H = np.array([[1, 0, 0]])
        
        # Process noise covariance (Q)
        self.Q = np.eye(3) * process_variance
        
        # Measurement noise covariance (R)
        self.R = np.array([[measurement_variance]])
        
        # Is initialized
        self.initialized = False
    
    def update(self, observed_price: float) -> KalmanState:
        """
        Update filter with new price observation
        
        Args:
            observed_price: Latest observed price
            
        Returns:
            Updated state estimate
        """
        # Initialize on first observation
        if not self.initialized:
            self.x = np.array([observed_price, 0, 0])
            self.initialized = True
            return KalmanState(observed_price, 0, 0)
        
        # PREDICTION STEP
        # Predict state: x_pred = F * x
        x_pred = self.F @ self.x
        
        # Predict covariance: P_pred = F*P*F' + Q
        P_pred = self.F @ self.P @ self.F.T + self.Q
        
        # UPDATE STEP
        # Measurement residual: y = z - H*x_pred
        z = np.array([[observed_price]])
        y = z - self.H @ x_pred.reshape(-1, 1)
        
        # Residual covariance: S = H*P_pred*H' + R
        S = self.H @ P_pred @ self.H.T + self.R
        
        # Kalman gain: K = P_pred*H' * inv(S)
        K = P_pred @ self.H.T @ np.linalg.inv(S)
        
        # Updated state estimate: x = x_pred + K*y
        self.x = (x_pred.reshape(-1, 1) + K @ y).flatten()
        
        # Updated covariance: P = (I - K*H) * P_pred
        I = np.eye(3)
        self.P = (I - K @ self.H) @ P_pred
        
        return KalmanState(
            price=self.x[0],
            velocity=self.x[1],
            acceleration=self.x[2]
        )
    
    def predict(self, steps: int = 1) -> Tuple[float, float]:
        """
        Predict future price
        
        Args:
            steps: Number of time steps ahead
            
        Returns:
            (predicted_price, uncertainty)
        """
        # Predict state: x_future = F^steps * x
        F_power = np.linalg.matrix_power(self.F, steps)
        x_future = F_power @ self.x
        
        # Predict covariance
        P_future = F_power @ self.P @ F_power.T
        
        predicted_price = x_future[0]
        uncertainty = np.sqrt(P_future[0, 0])
        
        return predicted_price, uncertainty
    
    def get_current_state(self) -> KalmanState:
        """Get current state estimate"""
        return KalmanState(
            price=self.x[0],
            velocity=self.x[1],
            acceleration=self.x[2]
        )
    
    def get_confidence_interval(
        self,
        steps: int = 1,
        confidence: float = 0.95
    ) -> Tuple[float, float, float]:
        """
        Get prediction with confidence interval
        
        Args:
            steps: Steps ahead
            confidence: Confidence level (e.g., 0.95 for 95%)
            
        Returns:
            (predicted_price, lower_bound, upper_bound)
        """
        predicted_price, uncertainty = self.predict(steps)
        
        # Z-score for confidence level
        # 0.95 → 1.96, 0.99 → 2.576
        from scipy.stats import norm
        z_score = norm.ppf((1 + confidence) / 2)
        
        margin = z_score * uncertainty
        
        return predicted_price, predicted_price - margin, predicted_price + margin


class AdaptiveKalmanFilter(KalmanFilter):
    """
    Adaptive Kalman Filter - adjusts noise parameters based on residuals
    """
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.residual_window = []
        self.window_size = 20
    
    def update(self, observed_price: float) -> KalmanState:
        """Update with adaptive noise estimation"""
        state = super().update(observed_price)
        
        # Calculate innovation (residual)
        if self.initialized:
            predicted_price, _ = self.predict(0)
            residual = observed_price - predicted_price
            
            self.residual_window.append(residual)
            if len(self.residual_window) > self.window_size:
                self.residual_window.pop(0)
            
            # Adapt measurement noise based on recent residuals
            if len(self.residual_window) >= 10:
                residual_var = np.var(self.residual_window)
                # Slowly adjust R
                self.R = 0.9 * self.R + 0.1 * np.array([[residual_var]])
        
        return state


# Example usage
if __name__ == "__main__":
    print("Kalman Filter for Price Prediction")
    print("=" * 60)
    
    # Create filter
    kf = AdaptiveKalmanFilter(
        process_variance=1e-5,
        measurement_variance=1e-3
    )
    
    print("\nFilter initialized with adaptive noise estimation")
    print("  State: [price, velocity, acceleration]")
    print("  Predicts 1-N steps ahead with confidence intervals")
    print("\nReady to track BTC/ETH prices")
