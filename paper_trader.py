#!/usr/bin/env python3
"""
================================================================================
                    PAPER TRADER - VIRTUAL TRADING
================================================================================
Simulates trading with virtual money to validate strategy before going live.
Tracks positions, calculates P&L, and logs all trades.
================================================================================
"""

import json
import logging
import os
from datetime import datetime
from typing import Callable, Dict, List, Optional
from dataclasses import dataclass, asdict
import numpy as np

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("PaperTrader")


@dataclass
class Position:
    symbol: str
    direction: str  # BUY or SELL
    entry_price: float
    entry_time: str
    leverage: int
    margin: float
    tp_price: float
    sl_price: float
    trail_pct: float
    max_pnl_pct: float = 0.0
    hold_candles: int = 0


@dataclass
class Trade:
    symbol: str
    direction: str
    entry_price: float
    exit_price: float
    entry_time: str
    exit_time: str
    leverage: int
    margin: float
    pnl: float
    pnl_pct: float
    exit_reason: str
    conviction: float


class PaperTrader:
    """Paper trading engine for strategy validation"""
    
    def __init__(self, starting_balance: float = 100000.0, min_leverage: int = 10, max_leverage: int = 50):
        self.starting_balance = starting_balance
        self.balance = starting_balance
        
        self.positions: Dict[str, Position] = {}  # symbol -> position
        self.trades: List[Trade] = []
        self.callbacks: List[Callable] = []
        
        # Trading parameters
        self.risk_per_trade = 0.02  # 2% per trade for larger balance
        self.max_leverage = max_leverage
        self.min_leverage = min_leverage
        self.max_hold_candles = 32  # 8 hours at 15m
        
        # Exit parameters
        self.tp_pct = 0.015  # 1.5%
        self.sl_pct = 0.008  # 0.8%
        self.trail_pct = 0.007  # 0.7%
        
        # Simulated slippage
        self.slippage_pct = 0.0005  # 0.05%
        
        # Trade log file
        self.log_dir = "results/paper_trades"
        os.makedirs(self.log_dir, exist_ok=True)
    
    def add_callback(self, callback: Callable):
        """Add callback for trade events"""
        self.callbacks.append(callback)
    
    def _notify_callbacks(self, event_type: str, data: Dict):
        """Notify callbacks of trade events"""
        for cb in self.callbacks:
            try:
                cb(event_type, data)
            except Exception as e:
                logger.error(f"Callback error: {e}")
    
    def get_position(self, symbol: str) -> Optional[Position]:
        """Get current position for symbol"""
        return self.positions.get(symbol)
    
    def has_position(self, symbol: str) -> bool:
        """Check if we have a position for symbol"""
        return symbol in self.positions
    
    def open_position(self, signal: Dict) -> bool:
        """Open a new position based on signal"""
        symbol = signal['symbol']
        
        if self.has_position(symbol):
            logger.warning(f"Already have position for {symbol}")
            return False
        
        direction = signal['signal']
        if direction not in ['BUY', 'SELL']:
            return False
        
        price = signal['price']
        conviction = signal.get('conviction', 0.5)
        atr_pct = signal.get('atr_pct', 1.0)
        
        # Apply slippage
        if direction == 'BUY':
            entry_price = price * (1 + self.slippage_pct)
        else:
            entry_price = price * (1 - self.slippage_pct)
        
        # Calculate position size (scale with balance)
        base_margin = self.balance * self.risk_per_trade * (0.5 + conviction * 0.5)
        max_margin = self.balance * 0.05  # Max 5% per trade
        margin = np.clip(base_margin, 100, max_margin)
        
        # Calculate leverage
        leverage = int(self.min_leverage + conviction * (self.max_leverage - self.min_leverage))
        leverage = np.clip(leverage, self.min_leverage, self.max_leverage)
        
        # Calculate exit prices
        if direction == 'BUY':
            tp_price = entry_price * (1 + self.tp_pct)
            sl_price = entry_price * (1 - self.sl_pct)
        else:
            tp_price = entry_price * (1 - self.tp_pct)
            sl_price = entry_price * (1 + self.sl_pct)
        
        # Create position
        position = Position(
            symbol=symbol,
            direction=direction,
            entry_price=entry_price,
            entry_time=datetime.now().isoformat(),
            leverage=leverage,
            margin=margin,
            tp_price=tp_price,
            sl_price=sl_price,
            trail_pct=self.trail_pct
        )
        
        self.positions[symbol] = position
        
        logger.info(f"OPENED {direction} {symbol} @ {entry_price:.2f} | Margin: ${margin:.2f} | Lev: {leverage}x")
        
        self._notify_callbacks("OPEN", {
            "symbol": symbol,
            "direction": direction,
            "entry_price": entry_price,
            "margin": margin,
            "leverage": leverage
        })
        
        return True
    
    def update_position(self, symbol: str, current_price: float) -> Optional[str]:
        """Update position and check for exit conditions"""
        if not self.has_position(symbol):
            return None
        
        position = self.positions[symbol]
        position.hold_candles += 1
        
        # Calculate current P&L
        if position.direction == 'BUY':
            pnl_pct = (current_price - position.entry_price) / position.entry_price
        else:
            pnl_pct = (position.entry_price - current_price) / position.entry_price
        
        # Update max P&L for trailing stop
        position.max_pnl_pct = max(position.max_pnl_pct, pnl_pct)
        
        # Check exit conditions
        exit_reason = None
        
        # Take Profit
        if position.direction == 'BUY' and current_price >= position.tp_price:
            exit_reason = "TP"
        elif position.direction == 'SELL' and current_price <= position.tp_price:
            exit_reason = "TP"
        
        # Stop Loss
        elif position.direction == 'BUY' and current_price <= position.sl_price:
            exit_reason = "SL"
        elif position.direction == 'SELL' and current_price >= position.sl_price:
            exit_reason = "SL"
        
        # Trailing Stop
        elif position.max_pnl_pct > position.trail_pct:
            if pnl_pct < position.max_pnl_pct - position.trail_pct:
                exit_reason = "TRAIL"
        
        # Timeout
        elif position.hold_candles >= self.max_hold_candles:
            exit_reason = "TIMEOUT"
        
        if exit_reason:
            self.close_position(symbol, current_price, exit_reason)
            return exit_reason
        
        return None
    
    def close_position(self, symbol: str, exit_price: float, reason: str):
        """Close position and record trade"""
        if not self.has_position(symbol):
            return
        
        position = self.positions[symbol]
        
        # Apply slippage
        if position.direction == 'BUY':
            actual_exit = exit_price * (1 - self.slippage_pct)
            pnl_pct = (actual_exit - position.entry_price) / position.entry_price
        else:
            actual_exit = exit_price * (1 + self.slippage_pct)
            pnl_pct = (position.entry_price - actual_exit) / position.entry_price
        
        # Calculate P&L
        leveraged_pnl = pnl_pct * position.leverage
        gross_pnl = position.margin * leveraged_pnl
        
        # Trading costs (0.08% round trip)
        costs = position.margin * position.leverage * 0.0008
        net_pnl = gross_pnl - costs
        
        # Update balance
        self.balance += net_pnl
        
        # Record trade
        trade = Trade(
            symbol=symbol,
            direction=position.direction,
            entry_price=position.entry_price,
            exit_price=actual_exit,
            entry_time=position.entry_time,
            exit_time=datetime.now().isoformat(),
            leverage=position.leverage,
            margin=position.margin,
            pnl=round(net_pnl, 2),
            pnl_pct=round(pnl_pct * 100, 2),
            exit_reason=reason,
            conviction=0
        )
        
        self.trades.append(trade)
        del self.positions[symbol]
        
        pnl_color = "+" if net_pnl >= 0 else ""
        logger.info(f"CLOSED {position.direction} {symbol} @ {actual_exit:.2f} | {reason} | P&L: {pnl_color}${net_pnl:.2f} ({pnl_pct*100:.2f}%)")
        
        self._notify_callbacks("CLOSE", {
            "symbol": symbol,
            "direction": position.direction,
            "exit_price": actual_exit,
            "pnl": net_pnl,
            "reason": reason
        })
        
        # Save trade log
        self._save_trade(trade)
    
    def _save_trade(self, trade: Trade):
        """Save trade to log file"""
        log_file = os.path.join(self.log_dir, f"trades_{datetime.now().strftime('%Y%m%d')}.json")
        
        trades_data = []
        if os.path.exists(log_file):
            try:
                with open(log_file, 'r') as f:
                    trades_data = json.load(f)
            except:
                pass
        
        trades_data.append(asdict(trade))
        
        with open(log_file, 'w') as f:
            json.dump(trades_data, f, indent=2)
    
    def get_stats(self) -> Dict:
        """Get trading statistics"""
        n = len(self.trades)
        if n == 0:
            return {
                "total_trades": 0,
                "balance": self.balance,
                "return_pct": 0
            }
        
        winners = [t for t in self.trades if t.pnl > 0]
        losers = [t for t in self.trades if t.pnl <= 0]
        
        win_rate = len(winners) / n * 100
        total_win = sum(t.pnl for t in winners)
        total_loss = abs(sum(t.pnl for t in losers))
        pf = total_win / total_loss if total_loss > 0 else float('inf')
        
        ret = (self.balance - self.starting_balance) / self.starting_balance * 100
        
        return {
            "total_trades": n,
            "winners": len(winners),
            "losers": len(losers),
            "win_rate": round(win_rate, 2),
            "profit_factor": round(pf, 2) if pf != float('inf') else "inf",
            "total_pnl": round(sum(t.pnl for t in self.trades), 2),
            "avg_win": round(total_win / len(winners), 2) if winners else 0,
            "avg_loss": round(-total_loss / len(losers), 2) if losers else 0,
            "balance": round(self.balance, 2),
            "return_pct": round(ret, 2)
        }
    
    def print_summary(self):
        """Print trading summary"""
        stats = self.get_stats()
        
        print("\n" + "=" * 60)
        print("  PAPER TRADING SUMMARY")
        print("=" * 60)
        print(f"  Total Trades:   {stats['total_trades']}")
        print(f"  Winners:        {stats.get('winners', 0)}")
        print(f"  Losers:         {stats.get('losers', 0)}")
        print(f"  Win Rate:       {stats['win_rate']}%")
        print(f"  Profit Factor:  {stats['profit_factor']}")
        print(f"  Total P&L:      ${stats.get('total_pnl', 0)}")
        print(f"  Balance:        ${stats['balance']}")
        print(f"  Return:         {stats['return_pct']}%")
        print("=" * 60)
        
        # Open positions
        if self.positions:
            print("\n  OPEN POSITIONS:")
            for sym, pos in self.positions.items():
                print(f"    {sym}: {pos.direction} @ {pos.entry_price:.2f}")


if __name__ == "__main__":
    # Test paper trader
    trader = PaperTrader(starting_balance=1000.0)
    
    # Simulate opening a position
    signal = {
        "symbol": "BTCUSDT",
        "signal": "BUY",
        "price": 42000.0,
        "conviction": 0.6,
        "atr_pct": 1.2
    }
    
    trader.open_position(signal)
    
    # Simulate price updates
    trader.update_position("BTCUSDT", 42100.0)
    trader.update_position("BTCUSDT", 42300.0)
    trader.update_position("BTCUSDT", 42500.0)  # Should hit TP
    
    trader.print_summary()
