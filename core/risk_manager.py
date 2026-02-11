"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                       RISK MANAGER                                            ║
║                                                                               ║
║  Comprehensive risk management with:                                          ║
║  - Dynamic leverage (1x-20x based on confidence)                             ║
║  - Stop Loss / Take Profit                                                    ║
║  - Trailing Stops                                                             ║
║  - Position Sizing (risk % per trade)                                        ║
╚═══════════════════════════════════════════════════════════════════════════════╝

Author: Bot_Algo
Last Updated: January 2026
"""

from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple
from enum import Enum
import time


class OrderSide(Enum):
    LONG = 1
    SHORT = -1
    FLAT = 0


@dataclass
class Position:
    """Active position with risk parameters."""
    symbol: str
    side: OrderSide
    entry_price: float
    quantity: float
    leverage: int
    
    # Risk levels
    stop_loss: float = 0.0
    take_profit: float = 0.0
    trailing_stop: float = 0.0
    trailing_activation: float = 0.0
    
    # State
    highest_price: float = 0.0
    lowest_price: float = 0.0
    entry_time: float = field(default_factory=time.time)
    
    def update_trailing(self, current_price: float) -> bool:
        """Update trailing stop. Returns True if stop triggered."""
        if self.trailing_stop <= 0:
            return False
        
        if self.side == OrderSide.LONG:
            if current_price > self.highest_price:
                self.highest_price = current_price
            
            if self.trailing_activation > 0 and current_price < self.trailing_activation:
                return False
            
            trail_price = self.highest_price * (1 - self.trailing_stop / 100)
            if current_price <= trail_price:
                return True
                
        elif self.side == OrderSide.SHORT:
            if self.lowest_price == 0 or current_price < self.lowest_price:
                self.lowest_price = current_price
            
            if self.trailing_activation > 0 and current_price > self.trailing_activation:
                return False
            
            trail_price = self.lowest_price * (1 + self.trailing_stop / 100)
            if current_price >= trail_price:
                return True
        
        return False
    
    def check_sl_tp(self, current_price: float) -> Tuple[bool, str]:
        """Check if SL or TP hit. Returns (triggered, reason)."""
        if self.side == OrderSide.LONG:
            if self.stop_loss > 0 and current_price <= self.stop_loss:
                return True, "STOP_LOSS"
            if self.take_profit > 0 and current_price >= self.take_profit:
                return True, "TAKE_PROFIT"
                
        elif self.side == OrderSide.SHORT:
            if self.stop_loss > 0 and current_price >= self.stop_loss:
                return True, "STOP_LOSS"
            if self.take_profit > 0 and current_price <= self.take_profit:
                return True, "TAKE_PROFIT"
        
        return False, ""
    
    def get_pnl_percent(self, current_price: float) -> float:
        """Calculate unrealized PnL %."""
        if self.entry_price == 0:
            return 0.0
        
        if self.side == OrderSide.LONG:
            return ((current_price - self.entry_price) / self.entry_price) * 100 * self.leverage
        elif self.side == OrderSide.SHORT:
            return ((self.entry_price - current_price) / self.entry_price) * 100 * self.leverage
        return 0.0


@dataclass 
class RiskConfig:
    """Risk management configuration."""
    risk_per_trade: float = 1.0
    max_position_size: float = 20.0
    base_leverage: int = 5
    max_leverage: int = 10           # Reduced from 20
    min_leverage: int = 1
    default_sl_percent: float = 3.0  # Increased from 2%
    default_tp_percent: float = 6.0  # Increased from 4% (2:1 R:R)
    trailing_percent: float = 2.0    # Increased from 1.5%
    trailing_activation: float = 3.0 # Increased from 2%
    max_daily_loss: float = 100.0
    max_drawdown: float = 100.0
    min_confidence: float = 70.0     # NEW: Minimum confidence to enter


class RiskManager:
    """Comprehensive risk management with SL/TP/trailing."""
    
    def __init__(self, capital: float, config: RiskConfig = None):
        self.capital = capital
        self.initial_capital = capital
        self.config = config or RiskConfig()
        self.positions: Dict[str, Position] = {}
        self.daily_pnl = 0.0
        self.daily_trades = 0
        self.peak_capital = capital
        
    def calculate_leverage(self, confidence: float, volatility: float = 1.0) -> int:
        """Calculate dynamic leverage based on confidence."""
        if confidence >= 80:
            lev = self.config.max_leverage
        elif confidence >= 60:
            lev = int(self.config.base_leverage * 1.5)
        elif confidence >= 40:
            lev = self.config.base_leverage
        else:
            lev = self.config.min_leverage
        
        if volatility > 1.5:
            lev = max(self.config.min_leverage, lev // 2)
        elif volatility > 1.2:
            lev = max(self.config.min_leverage, int(lev * 0.7))
        
        return min(self.config.max_leverage, max(self.config.min_leverage, lev))
    
    def calculate_position_size(self, price: float, leverage: int, sl_percent: float = None) -> float:
        """Calculate position size based on risk per trade."""
        sl = sl_percent or self.config.default_sl_percent
        risk_amount = self.capital * (self.config.risk_per_trade / 100)
        position_value = risk_amount / (sl / 100)
        max_position = self.capital * (self.config.max_position_size / 100) * leverage
        position_value = min(position_value, max_position)
        return position_value / price
    
    def calculate_sl_tp(self, entry_price: float, side: OrderSide, atr: float = None) -> Tuple[float, float]:
        """Calculate stop loss and take profit prices."""
        sl_pct = self.config.default_sl_percent / 100
        tp_pct = self.config.default_tp_percent / 100
        
        if atr and atr > 0:
            sl_pct = (atr * 2) / entry_price
            tp_pct = (atr * 4) / entry_price
        
        if side == OrderSide.LONG:
            sl = entry_price * (1 - sl_pct)
            tp = entry_price * (1 + tp_pct)
        else:
            sl = entry_price * (1 + sl_pct)
            tp = entry_price * (1 - tp_pct)
        
        return sl, tp
    
    def open_position(self, symbol: str, side: int, price: float, confidence: float, 
                      volatility: float = 1.0, atr: float = None) -> Optional[Position]:
        """Open a new position with full risk management."""
        if self.daily_pnl <= -self.config.max_daily_loss:
            return None
        
        current_dd = (self.peak_capital - self.capital) / self.peak_capital * 100
        if current_dd >= self.config.max_drawdown:
            return None
        
        if symbol in self.positions:
            self.close_position(symbol, price, "NEW_SIGNAL")
        
        order_side = OrderSide.LONG if side == 1 else OrderSide.SHORT
        leverage = self.calculate_leverage(confidence, volatility)
        quantity = self.calculate_position_size(price, leverage)
        sl, tp = self.calculate_sl_tp(price, order_side, atr)
        
        if order_side == OrderSide.LONG:
            trail_activation = price * (1 + self.config.trailing_activation / 100)
        else:
            trail_activation = price * (1 - self.config.trailing_activation / 100)
        
        position = Position(
            symbol=symbol, side=order_side, entry_price=price,
            quantity=quantity, leverage=leverage, stop_loss=sl,
            take_profit=tp, trailing_stop=self.config.trailing_percent,
            trailing_activation=trail_activation, highest_price=price, lowest_price=price,
        )
        
        self.positions[symbol] = position
        self.daily_trades += 1
        return position
    
    def close_position(self, symbol: str, price: float, reason: str = "MANUAL") -> float:
        """Close position and return PnL."""
        if symbol not in self.positions:
            return 0.0
        
        pos = self.positions[symbol]
        pnl_pct = pos.get_pnl_percent(price)
        pnl_usd = (pnl_pct / 100) * (pos.quantity * pos.entry_price / pos.leverage)
        
        self.capital += pnl_usd
        self.daily_pnl += pnl_pct
        
        if self.capital > self.peak_capital:
            self.peak_capital = self.capital
        
        del self.positions[symbol]
        return pnl_usd
    
    def update_position(self, symbol: str, price: float) -> Tuple[bool, str]:
        """Update position - check SL/TP/trailing."""
        if symbol not in self.positions:
            return False, ""
        
        pos = self.positions[symbol]
        
        if pos.update_trailing(price):
            return True, "TRAILING_STOP"
        
        triggered, reason = pos.check_sl_tp(price)
        if triggered:
            return True, reason
        
        return False, ""
    
    def get_position_status(self, symbol: str, price: float) -> Dict:
        """Get current position status."""
        if symbol not in self.positions:
            return {'active': False, 'side': 'FLAT', 'pnl_pct': 0, 'leverage': 0}
        
        pos = self.positions[symbol]
        return {
            'active': True,
            'side': 'LONG' if pos.side == OrderSide.LONG else 'SHORT',
            'entry': pos.entry_price,
            'quantity': pos.quantity,
            'leverage': pos.leverage,
            'sl': pos.stop_loss,
            'tp': pos.take_profit,
            'pnl_pct': pos.get_pnl_percent(price),
        }
    
    def reset_daily(self):
        """Reset daily counters."""
        self.daily_pnl = 0.0
        self.daily_trades = 0


if __name__ == "__main__":
    rm = RiskManager(capital=1000)
    
    print("=" * 60)
    print("RISK MANAGER DEMO")
    print("=" * 60)
    
    pos = rm.open_position("BTCUSDT", 1, 90000, 75, 1.0)
    
    if pos:
        print(f"\nOpened: {pos.side.name} @ ${pos.entry_price:,.0f}")
        print(f"  Lev: {pos.leverage}x | SL: ${pos.stop_loss:,.0f} | TP: ${pos.take_profit:,.0f}")
    
    for price in [90500, 91000, 91500, 92000, 91800]:
        status = rm.get_position_status("BTCUSDT", price)
        should_close, reason = rm.update_position("BTCUSDT", price)
        print(f"  ${price:,.0f} -> PnL: {status['pnl_pct']:+.1f}%", end="")
        
        if should_close:
            pnl = rm.close_position("BTCUSDT", price, reason)
            print(f" -> CLOSED ({reason}): ${pnl:+.2f}")
            break
        print()
    
    print(f"\nCapital: ${rm.capital:,.2f}")
