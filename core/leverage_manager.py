"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                       LEVERAGE & RISK MANAGEMENT                              ║
║                                                                               ║
║  Dynamic leverage system with liquidation protection.                         ║
║  Adjusts leverage based on signal confidence, volatility, and risk limits.   ║
╚═══════════════════════════════════════════════════════════════════════════════╝

Features:
- Dynamic leverage (1x - 20x) based on confidence
- Liquidation price calculation
- Safety buffer to prevent liquidation
- Position sizing with leverage
- Risk-adjusted returns calculation

Author: Bot_Algo
Last Updated: January 2026
"""

import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple
from enum import Enum
import logging

logger = logging.getLogger("LeverageManager")


# ═══════════════════════════════════════════════════════════════════════════════
#                           CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class LeverageConfig:
    """Configuration for leverage management."""
    
    # Leverage limits - UPDATED for safer trading
    min_leverage: float = 1.0
    max_leverage: float = 10.0         # Reduced from 20
    default_leverage: float = 5.0
    
    # Risk parameters
    max_risk_per_trade: float = 0.01      # 1% max risk per trade (was 2%)
    maintenance_margin: float = 0.005      # 0.5% maintenance margin (Binance)
    safety_buffer: float = 0.03            # 3% safety buffer (was 2%)
    
    # Confidence thresholds for leverage - Higher requirements
    high_confidence: float = 0.85          # 85%+ = max leverage (was 80%)
    medium_confidence: float = 0.70        # 70-85% = medium (was 60%)
    low_confidence: float = 0.50           # 50-70% = low (was 40%)
    
    # Volatility adjustments
    vol_low_mult: float = 1.3              # Low vol = slight increase (was 1.5)
    vol_normal_mult: float = 1.0           # Normal vol = base leverage
    vol_high_mult: float = 0.6             # High vol = reduce leverage (was 0.5)
    vol_extreme_mult: float = 0.0          # Extreme vol = no leverage (flat)


class LeverageMode(Enum):
    """Leverage calculation modes."""
    FIXED = "fixed"
    DYNAMIC = "dynamic"
    CONSERVATIVE = "conservative"
    AGGRESSIVE = "aggressive"


# ═══════════════════════════════════════════════════════════════════════════════
#                           LIQUIDATION CALCULATOR
# ═══════════════════════════════════════════════════════════════════════════════

class LiquidationCalculator:
    """
    Calculate liquidation prices and manage margin safety.
    
    Liquidation Price Formula (Isolated Margin):
    - Long: Entry * (1 - 1/Leverage + Maintenance Margin)
    - Short: Entry * (1 + 1/Leverage - Maintenance Margin)
    """
    
    def __init__(self, maintenance_margin: float = 0.005):
        self.maintenance_margin = maintenance_margin
    
    def long_liquidation_price(
        self,
        entry_price: float,
        leverage: float,
        maintenance_margin: float = None
    ) -> float:
        """Calculate liquidation price for long position."""
        mm = maintenance_margin or self.maintenance_margin
        return entry_price * (1 - (1 / leverage) + mm)
    
    def short_liquidation_price(
        self,
        entry_price: float,
        leverage: float,
        maintenance_margin: float = None
    ) -> float:
        """Calculate liquidation price for short position."""
        mm = maintenance_margin or self.maintenance_margin
        return entry_price * (1 + (1 / leverage) - mm)
    
    def distance_to_liquidation(
        self,
        current_price: float,
        liquidation_price: float,
        is_long: bool
    ) -> float:
        """Calculate percentage distance to liquidation."""
        if is_long:
            return (current_price - liquidation_price) / current_price * 100
        else:
            return (liquidation_price - current_price) / current_price * 100
    
    def is_safe(
        self,
        current_price: float,
        liquidation_price: float,
        is_long: bool,
        safety_buffer: float = 0.02
    ) -> Tuple[bool, float]:
        """
        Check if position is safe from liquidation.
        
        Returns:
            (is_safe, distance_pct)
        """
        distance = self.distance_to_liquidation(current_price, liquidation_price, is_long)
        min_distance = safety_buffer * 100
        return (distance > min_distance, distance)
    
    def max_safe_leverage(
        self,
        stop_loss_pct: float,
        safety_buffer: float = 0.02
    ) -> float:
        """
        Calculate maximum safe leverage given stop loss distance.
        
        To prevent liquidation before stop loss:
        Leverage <= 1 / (stop_loss_pct + maintenance_margin + safety_buffer)
        """
        total_buffer = stop_loss_pct + self.maintenance_margin + safety_buffer
        if total_buffer <= 0:
            return 1.0
        return min(1 / total_buffer, 125)  # Cap at 125x (Binance max)


# ═══════════════════════════════════════════════════════════════════════════════
#                           LEVERAGE MANAGER
# ═══════════════════════════════════════════════════════════════════════════════

class LeverageManager:
    """
    Manage dynamic leverage based on market conditions and signal confidence.
    """
    
    def __init__(self, config: LeverageConfig = None):
        self.config = config or LeverageConfig()
        self.liq_calc = LiquidationCalculator(self.config.maintenance_margin)
        
        # Track leverage history
        self.leverage_history: list = []
        self.liquidation_warnings: int = 0
        self.forced_closes: int = 0
    
    def calculate_leverage(
        self,
        confidence: float,
        volatility_ratio: float,
        stop_loss_pct: float,
        mode: LeverageMode = LeverageMode.DYNAMIC
    ) -> Dict:
        """
        Calculate optimal leverage for a trade.
        
        Args:
            confidence: Signal confidence (0-1)
            volatility_ratio: Current volatility vs average (1.0 = normal)
            stop_loss_pct: Stop loss distance as decimal (0.02 = 2%)
            mode: Leverage calculation mode
            
        Returns:
            Dict with leverage details
        """
        if mode == LeverageMode.FIXED:
            return self._fixed_leverage(stop_loss_pct)
        elif mode == LeverageMode.CONSERVATIVE:
            return self._conservative_leverage(confidence, volatility_ratio, stop_loss_pct)
        elif mode == LeverageMode.AGGRESSIVE:
            return self._aggressive_leverage(confidence, volatility_ratio, stop_loss_pct)
        else:
            return self._dynamic_leverage(confidence, volatility_ratio, stop_loss_pct)
    
    def _fixed_leverage(self, stop_loss_pct: float) -> Dict:
        """Use fixed leverage (capped for safety)."""
        max_safe = self.liq_calc.max_safe_leverage(stop_loss_pct, self.config.safety_buffer)
        leverage = min(self.config.default_leverage, max_safe)
        
        return {
            'leverage': leverage,
            'mode': 'fixed',
            'confidence_factor': 1.0,
            'volatility_factor': 1.0,
            'max_safe_leverage': max_safe,
            'capped': leverage < self.config.default_leverage
        }
    
    def _dynamic_leverage(
        self,
        confidence: float,
        volatility_ratio: float,
        stop_loss_pct: float
    ) -> Dict:
        """Calculate dynamic leverage based on all factors."""
        c = self.config
        
        # Confidence factor (0.5 - 2.0)
        if confidence >= c.high_confidence:
            conf_factor = 1.5 + (confidence - c.high_confidence) * 2.5
        elif confidence >= c.medium_confidence:
            conf_factor = 1.0 + (confidence - c.medium_confidence) * 2.5
        elif confidence >= c.low_confidence:
            conf_factor = 0.5 + (confidence - c.low_confidence) * 2.5
        else:
            conf_factor = 0.5
        
        conf_factor = min(max(conf_factor, 0.5), 2.0)
        
        # Volatility factor
        if volatility_ratio < 0.7:
            vol_factor = c.vol_low_mult
        elif volatility_ratio < 1.5:
            vol_factor = c.vol_normal_mult
        elif volatility_ratio < 2.5:
            vol_factor = c.vol_high_mult
        else:
            vol_factor = c.vol_extreme_mult
        
        # Base leverage
        base_leverage = c.default_leverage * conf_factor * vol_factor
        
        # Safety cap based on stop loss
        max_safe = self.liq_calc.max_safe_leverage(stop_loss_pct, c.safety_buffer)
        
        # Final leverage (capped)
        final_leverage = min(max(base_leverage, c.min_leverage), min(c.max_leverage, max_safe))
        
        return {
            'leverage': final_leverage,
            'mode': 'dynamic',
            'confidence_factor': conf_factor,
            'volatility_factor': vol_factor,
            'base_leverage': base_leverage,
            'max_safe_leverage': max_safe,
            'capped': final_leverage < base_leverage
        }
    
    def _conservative_leverage(
        self,
        confidence: float,
        volatility_ratio: float,
        stop_loss_pct: float
    ) -> Dict:
        """Conservative leverage (lower risk)."""
        result = self._dynamic_leverage(confidence, volatility_ratio, stop_loss_pct)
        result['leverage'] = min(result['leverage'] * 0.5, 5.0)
        result['mode'] = 'conservative'
        return result
    
    def _aggressive_leverage(
        self,
        confidence: float,
        volatility_ratio: float,
        stop_loss_pct: float
    ) -> Dict:
        """Aggressive leverage (higher risk)."""
        result = self._dynamic_leverage(confidence, volatility_ratio, stop_loss_pct)
        max_safe = result['max_safe_leverage']
        result['leverage'] = min(result['leverage'] * 1.5, max_safe)
        result['mode'] = 'aggressive'
        return result
    
    def calculate_position_with_leverage(
        self,
        equity: float,
        entry_price: float,
        leverage: float,
        stop_loss_price: float,
        is_long: bool
    ) -> Dict:
        """
        Calculate full position details with leverage.
        
        Returns position size, margin required, liquidation price, etc.
        """
        # Calculate stop loss distance
        if is_long:
            stop_loss_pct = (entry_price - stop_loss_price) / entry_price
            liq_price = self.liq_calc.long_liquidation_price(entry_price, leverage)
        else:
            stop_loss_pct = (stop_loss_price - entry_price) / entry_price
            liq_price = self.liq_calc.short_liquidation_price(entry_price, leverage)
        
        # Risk-based position sizing
        risk_amount = equity * self.config.max_risk_per_trade
        
        # Position size based on risk
        if stop_loss_pct > 0:
            base_position_value = risk_amount / stop_loss_pct
        else:
            base_position_value = equity * 0.1  # Default 10%
        
        # With leverage
        margin_required = base_position_value / leverage
        position_value = base_position_value
        quantity = position_value / entry_price
        
        # Cap at available equity
        if margin_required > equity * 0.9:  # Max 90% of equity as margin
            margin_required = equity * 0.9
            position_value = margin_required * leverage
            quantity = position_value / entry_price
        
        # Safety check
        is_safe, distance = self.liq_calc.is_safe(
            entry_price, liq_price, is_long, self.config.safety_buffer
        )
        
        return {
            'quantity': quantity,
            'position_value': position_value,
            'margin_required': margin_required,
            'leverage': leverage,
            'entry_price': entry_price,
            'stop_loss_price': stop_loss_price,
            'liquidation_price': liq_price,
            'distance_to_liq_pct': distance,
            'is_safe': is_safe,
            'max_loss': risk_amount,
            'max_loss_pct': self.config.max_risk_per_trade * 100
        }
    
    def check_liquidation_risk(
        self,
        current_price: float,
        entry_price: float,
        leverage: float,
        is_long: bool
    ) -> Dict:
        """Check current liquidation risk for open position."""
        if is_long:
            liq_price = self.liq_calc.long_liquidation_price(entry_price, leverage)
        else:
            liq_price = self.liq_calc.short_liquidation_price(entry_price, leverage)
        
        is_safe, distance = self.liq_calc.is_safe(
            current_price, liq_price, is_long, self.config.safety_buffer
        )
        
        # Warning levels
        if distance < 1.0:
            risk_level = "CRITICAL"
        elif distance < 2.0:
            risk_level = "HIGH"
        elif distance < 5.0:
            risk_level = "MEDIUM"
        else:
            risk_level = "LOW"
        
        if not is_safe:
            self.liquidation_warnings += 1
        
        return {
            'liquidation_price': liq_price,
            'current_price': current_price,
            'distance_pct': distance,
            'is_safe': is_safe,
            'risk_level': risk_level,
            'should_reduce': risk_level in ["CRITICAL", "HIGH"]
        }


# ═══════════════════════════════════════════════════════════════════════════════
#                           LEVERAGED BACKTEST
# ═══════════════════════════════════════════════════════════════════════════════

def backtest_with_leverage(
    df: pd.DataFrame,
    signals: pd.Series,
    leverage_manager: LeverageManager,
    initial_capital: float = 1000,
    confidence_series: pd.Series = None,
    volatility_series: pd.Series = None,
    mode: LeverageMode = LeverageMode.DYNAMIC
) -> Dict:
    """
    Backtest strategy with dynamic leverage.
    
    Returns detailed performance including leverage impact.
    """
    close_col = 'close' if 'close' in df.columns else 'Close'
    close = df[close_col]
    
    # Initialize
    equity = initial_capital
    position = 0
    entry_price = 0
    leverage = 1
    liq_price = 0
    margin_used = 0
    
    # Track results
    equity_curve = [initial_capital]
    trades = []
    liquidations = 0
    max_drawdown = 0
    peak_equity = initial_capital
    
    # Default confidence/volatility if not provided
    if confidence_series is None:
        confidence_series = pd.Series(0.6, index=df.index)
    if volatility_series is None:
        volatility_series = pd.Series(1.0, index=df.index)
    
    for i in range(1, len(df)):
        current_price = close.iloc[i]
        signal = signals.iloc[i]
        prev_signal = signals.iloc[i-1]
        
        confidence = confidence_series.iloc[i]
        vol_ratio = volatility_series.iloc[i]
        
        # Check for liquidation if in position
        if position != 0:
            risk_check = leverage_manager.check_liquidation_risk(
                current_price, entry_price, leverage, position == 1
            )
            
            if not risk_check['is_safe']:
                # LIQUIDATED!
                liquidations += 1
                loss_amount = margin_used * 0.9  # Lose 90% of margin
                equity = max(equity - loss_amount, 0)
                trades.append({
                    'exit_reason': 'LIQUIDATED',
                    'pnl': -loss_amount,
                    'pnl_pct': -90,
                    'leverage': leverage,
                    'margin': margin_used
                })
                position = 0
                entry_price = 0
                leverage = 1
                margin_used = 0
        
        # Signal change
        if signal != prev_signal:
            # Close existing position
            if position != 0:
                if position == 1:
                    pnl = (current_price - entry_price) / entry_price * leverage * margin_used
                else:
                    pnl = (entry_price - current_price) / entry_price * leverage * margin_used
                
                equity += pnl
                equity = max(equity, 0)  # Can't go negative
                
                trades.append({
                    'exit_reason': 'signal_change',
                    'pnl': pnl,
                    'pnl_pct': pnl / margin_used * 100 if margin_used > 0 else 0,
                    'leverage': leverage
                })
                
                position = 0
                leverage = 1
                margin_used = 0
            
            # Open new position
            if signal != 0 and equity > 10:  # Min $10 to trade
                # Calculate stop loss
                atr = df['atr'].iloc[i] if 'atr' in df.columns else current_price * 0.02
                stop_loss_pct = min(atr / current_price, 0.03)  # Max 3% stop
                
                # Calculate leverage
                lev_result = leverage_manager.calculate_leverage(
                    confidence, vol_ratio, stop_loss_pct, mode
                )
                leverage = lev_result['leverage']
                
                # Calculate position
                is_long = signal == 1
                stop_loss_price = current_price * (1 - stop_loss_pct) if is_long else current_price * (1 + stop_loss_pct)
                
                pos_result = leverage_manager.calculate_position_with_leverage(
                    equity, current_price, leverage, stop_loss_price, is_long
                )
                
                position = signal
                entry_price = current_price
                margin_used = pos_result['margin_required']
                liq_price = pos_result['liquidation_price']
        
        # Track equity
        if position != 0:
            if position == 1:
                unrealized = (current_price - entry_price) / entry_price * leverage * margin_used
            else:
                unrealized = (entry_price - current_price) / entry_price * leverage * margin_used
            current_equity = equity + unrealized
        else:
            current_equity = equity
        
        current_equity = max(current_equity, 0)
        equity_curve.append(current_equity)
        
        # Track drawdown
        peak_equity = max(peak_equity, current_equity)
        current_dd = (peak_equity - current_equity) / peak_equity if peak_equity > 0 else 0
        max_drawdown = max(max_drawdown, current_dd)
    
    # Final close
    if position != 0:
        final_price = close.iloc[-1]
        if position == 1:
            pnl = (final_price - entry_price) / entry_price * leverage * margin_used
        else:
            pnl = (entry_price - final_price) / entry_price * leverage * margin_used
        equity += pnl
    
    # Calculate metrics
    equity_series = pd.Series(equity_curve, index=df.index[:len(equity_curve)])
    returns = equity_series.pct_change().dropna()
    
    total_return = (equity - initial_capital) / initial_capital
    
    if len(returns) > 0 and returns.std() > 0:
        sharpe = (returns.mean() / returns.std()) * np.sqrt(252)
    else:
        sharpe = 0
    
    winning_trades = sum(1 for t in trades if t.get('pnl', 0) > 0)
    win_rate = winning_trades / len(trades) * 100 if trades else 0
    
    avg_leverage = np.mean([t.get('leverage', 1) for t in trades]) if trades else 1
    
    return {
        'total_return': total_return * 100,
        'final_equity': equity,
        'sharpe_ratio': sharpe,
        'max_drawdown': max_drawdown * 100,
        'total_trades': len(trades),
        'win_rate': win_rate,
        'liquidations': liquidations,
        'avg_leverage': avg_leverage,
        'equity_curve': equity_curve
    }


# ═══════════════════════════════════════════════════════════════════════════════
#                           MAIN (Demo)
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 65)
    print("LEVERAGE & RISK MANAGEMENT - DEMO")
    print("=" * 65)
    
    config = LeverageConfig()
    manager = LeverageManager(config)
    liq_calc = LiquidationCalculator()
    
    # Test liquidation prices
    print("\n--- Liquidation Price Calculator ---")
    entry = 45000
    for lev in [5, 10, 20, 50, 100]:
        long_liq = liq_calc.long_liquidation_price(entry, lev)
        short_liq = liq_calc.short_liquidation_price(entry, lev)
        print(f"  {lev}x: Long liq ${long_liq:,.0f} (-{(entry-long_liq)/entry*100:.1f}%) | "
              f"Short liq ${short_liq:,.0f} (+{(short_liq-entry)/entry*100:.1f}%)")
    
    # Test leverage calculation
    print("\n--- Dynamic Leverage Calculator ---")
    for conf, vol in [(0.9, 0.8), (0.7, 1.0), (0.5, 1.5), (0.3, 2.5)]:
        result = manager.calculate_leverage(conf, vol, 0.02)
        print(f"  Conf={conf:.1f} Vol={vol:.1f} -> {result['leverage']:.1f}x "
              f"(max safe: {result['max_safe_leverage']:.1f}x)")
    
    # Test position sizing
    print("\n--- Position with Leverage ---")
    pos = manager.calculate_position_with_leverage(
        equity=1000,
        entry_price=45000,
        leverage=10,
        stop_loss_price=44100,  # 2% stop
        is_long=True
    )
    print(f"  Equity: $1,000 | Entry: $45,000 | 10x Leverage")
    print(f"  Quantity: {pos['quantity']:.6f} BTC")
    print(f"  Position Value: ${pos['position_value']:,.2f}")
    print(f"  Margin Required: ${pos['margin_required']:,.2f}")
    print(f"  Liquidation: ${pos['liquidation_price']:,.0f} ({pos['distance_to_liq_pct']:.1f}% away)")
    print(f"  Max Loss: ${pos['max_loss']:.2f} ({pos['max_loss_pct']:.1f}%)")
    print(f"  Safe: {'Yes' if pos['is_safe'] else 'NO!'}")
    
    print("\n" + "=" * 65)
