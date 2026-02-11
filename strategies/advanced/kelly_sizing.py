"""
Kelly Criterion for Optimal Position Sizing
Mathematically optimal bet sizing to maximize long-term growth
"""

import numpy as np
from typing import List, Tuple, Optional, Dict
from dataclasses import dataclass


@dataclass
class PerformanceStats:
    """Trading performance statistics"""
    win_rate: float
    avg_win: float
    avg_loss: float
    sharpe_ratio: float
    total_trades: int


class KellyCriterion:
    """
    Kelly Criterion for optimal position sizing
    
    Mathematical Formula:
    f* = (p*b - q) / b
    
    where:
    - f* = fraction of capital to bet
    - p = probability of winning
    - q = probability of losing (1 - p)
    - b = ratio of win to loss (avg_win / avg_loss)
    
    Conservative Approach:
    Use fractional Kelly (f*/4 or f*/2) to reduce variance
    """
    
    def __init__(
        self,
        min_trades_required: int = 20,
        kelly_fraction: float = 0.25,  # Use 1/4 Kelly
        max_position: float = 0.20,     # Max 20% per position
        min_position: float = 0.01      # Min 1% per position
    ):
        """
        Initialize Kelly Criterion calculator
        
        Args:
            min_trades_required: Minimum trades needed for calculation
            kelly_fraction: Fraction of Kelly to use (0.25 = quarter Kelly)
            max_position: Maximum position size (as fraction of capital)
            min_position: Minimum position size (as fraction of capital)
        """
        self.min_trades_required = min_trades_required
        self.kelly_fraction = kelly_fraction
        self.max_position = max_position
        self.min_position = min_position
        
        self.trade_history = []  # List of P/L values
    
    def add_trade(self, pnl: float) -> None:
        """
        Record a completed trade
        
        Args:
            pnl: Profit/loss of the trade
        """
        self.trade_history.append(pnl)
    
    def calculate_stats(self) -> Optional[PerformanceStats]:
        """
        Calculate performance statistics from trade history
        
        Returns:
            PerformanceStats or None if insufficient data
        """
        if len(self.trade_history) < self.min_trades_required:
            return None
        
        trades = np.array(self.trade_history)
        
        # Win/loss separation
        wins = trades[trades > 0]
        losses = trades[trades < 0]
        
        if len(wins) == 0 or len(losses) == 0:
            return None  # Need both wins and losses
        
        # Calculate statistics
        win_rate = len(wins) / len(trades)
        avg_win = np.mean(wins)
        avg_loss = abs(np.mean(losses))
        
        # Sharpe ratio (risk-adjusted return)
        returns = trades
        sharpe = (np.mean(returns) / np.std(returns)) * np.sqrt(252) if np.std(returns) > 0 else 0
        
        return PerformanceStats(
            win_rate=win_rate,
            avg_win=avg_win,
            avg_loss=avg_loss,
            sharpe_ratio=sharpe,
            total_trades=len(trades)
        )
    
    def calculate_kelly_fraction(self) -> Optional[float]:
        """
        Calculate optimal Kelly fraction
        
        Formula:
        f* = (p*b - q) / b
        
        where b = avg_win/avg_loss
        
        Returns:
            Optimal position size (fraction of capital) or None
        """
        stats = self.calculate_stats()
        
        if stats is None:
            return None
        
        p = stats.win_rate
        q = 1 - p
        b = stats.avg_win / stats.avg_loss if stats.avg_loss > 0 else 0
        
        if b == 0:
            return None
        
        # Full Kelly
        kelly = (p * b - q) / b
        
        # Apply fraction (quarter Kelly for conservative)
        fractional_kelly = kelly * self.kelly_fraction
        
        # Clamp between min and max
        position_size = np.clip(fractional_kelly, self.min_position, self.max_position)
        
        return position_size
    
    def get_recommended_size(
        self,
        capital: float,
        confidence: Optional[float] = None
    ) -> Tuple[float, Dict]:
        """
        Get recommended position size in dollars
        
        Args:
            capital: Total available capital
            confidence: Optional confidence adjustment (0-1)
            
        Returns:
            (position_size_usd, metadata)
        """
        kelly = self.calculate_kelly_fraction()
        
        if kelly is None:
            # Not enough data - use conservative fixed size
            position_size = capital * 0.05  # 5% default
            metadata = {
                'kelly_fraction': None,
                'method': 'default',
                'reason': 'Insufficient trade history'
            }
        else:
            position_size = capital * kelly
            
            # Adjust by confidence if provided
            if confidence is not None:
                position_size *= confidence
            
            stats = self.calculate_stats()
            metadata = {
                'kelly_fraction': kelly,
                'method': 'kelly_criterion',
                'win_rate': stats.win_rate,
                'avg_win_loss_ratio': stats.avg_win / stats.avg_loss,
                'sharpe': stats.sharpe_ratio,
                'trades_analyzed': stats.total_trades
            }
        
        return position_size, metadata
    
    def get_risk_metrics(self) -> Dict:
        """Get current risk metrics"""
        stats = self.calculate_stats()
        
        if stats is None:
            return {
                'status': 'insufficient_data',
                'trades_needed': self.min_trades_required - len(self.trade_history)
            }
        
        kelly = self.calculate_kelly_fraction()
        
        # Risk of ruin (Kelly prevents this)
        survival_prob = stats.win_rate ** kelly if kelly else 0
        
        return {
            'status': 'ready',
            'win_rate': stats.win_rate,
            'sharpe_ratio': stats.sharpe_ratio,
            'kelly_bet': kelly,
            'edge': (stats.win_rate * stats.avg_win) - ((1-stats.win_rate) * stats.avg_loss),
            'survival_probability': survival_prob,
            'total_trades': stats.total_trades
        }


class DynamicKelly(KellyCriterion):
    """
    Dynamic Kelly with rolling window
    Adapts to recent performance
    """
    
    def __init__(self, window_size: int = 50, **kwargs):
        """
        Args:
            window_size: Use last N trades for calculation
        """
        super().__init__(**kwargs)
        self.window_size = window_size
    
    def calculate_stats(self) -> Optional[PerformanceStats]:
        """Calculate stats using rolling window"""
        if len(self.trade_history) < self.min_trades_required:
            return None
        
        # Use last N trades only
        recent_trades = self.trade_history[-self.window_size:]
        
        trades = np.array(recent_trades)
        
        wins = trades[trades > 0]
        losses = trades[trades < 0]
        
        if len(wins) == 0 or len(losses) == 0:
            return None
        
        win_rate = len(wins) / len(trades)
        avg_win = np.mean(wins)
        avg_loss = abs(np.mean(losses))
        
        sharpe = (np.mean(trades) / np.std(trades)) * np.sqrt(252) if np.std(trades) > 0 else 0
        
        return PerformanceStats(
            win_rate=win_rate,
            avg_win=avg_win,
            avg_loss=avg_loss,
            sharpe_ratio=sharpe,
            total_trades=len(recent_trades)
        )


# Example usage
if __name__ == "__main__":
    print("Kelly Criterion Position Sizing")
    print("=" * 60)
    
    # Create Kelly calculator
    kelly = DynamicKelly(
        min_trades_required=20,
        kelly_fraction=0.25,  # Quarter Kelly (conservative)
        max_position=0.20,    # Max 20% per trade
        window_size=50        # Rolling 50 trades
    )
    
    print("\nKelly Criterion initialized:")
    print(f"  Mode: Quarter Kelly (1/4 of optimal)")
    print(f"  Max position: 20%")
    print(f"  Min trades required: 20")
    print(f"  Rolling window: 50 trades")
    
    print("\nMathematical Formula:")
    print("  f* = (p*b - q) / b")
    print("  where p = win rate, b = win/loss ratio")
    
    print("\nMaximizes long-term growth rate while managing risk")
