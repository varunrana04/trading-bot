"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                       PAPER TRADING ENGINE                                    ║
║                                                                               ║
║  Simulated trading for forward testing strategies.                            ║
║  Tracks orders, fills, P&L, and compares expected vs actual.                  ║
╚═══════════════════════════════════════════════════════════════════════════════╝

Features:
- Simulated order book with realistic fills
- Slippage simulation
- Cost tracking (matches backtest assumptions)
- Daily P&L logging to JSON
- Position management
- Risk metrics calculation

Author: Bot_Algo
Last Updated: January 2026
"""

import json
import os
import sys
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable
from enum import Enum
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.validation.slippage import SlippageSimulator, OrderType
from core.costs.binance_costs import BinanceFuturesCosts

logger = logging.getLogger("PaperTrading")


# ═══════════════════════════════════════════════════════════════════════════════
#                           ENUMS & DATA CLASSES
# ═══════════════════════════════════════════════════════════════════════════════

class OrderSide(Enum):
    BUY = "buy"
    SELL = "sell"


class OrderStatus(Enum):
    PENDING = "pending"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


class PositionSide(Enum):
    LONG = "long"
    SHORT = "short"
    FLAT = "flat"


@dataclass
class Order:
    """Represents a trading order."""
    order_id: str
    symbol: str
    side: OrderSide
    quantity: float
    order_type: str  # 'market' or 'limit'
    limit_price: Optional[float] = None
    
    # Execution
    status: OrderStatus = OrderStatus.PENDING
    fill_price: Optional[float] = None
    fill_time: Optional[datetime] = None
    slippage: float = 0.0
    
    # Costs
    commission: float = 0.0
    funding_cost: float = 0.0
    total_cost: float = 0.0
    
    # Metadata
    created_at: datetime = field(default_factory=datetime.now)
    strategy: str = "unknown"
    signal_price: float = 0.0  # Expected price
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        d = asdict(self)
        d['side'] = self.side.value
        d['status'] = self.status.value
        d['created_at'] = self.created_at.isoformat()
        if self.fill_time:
            d['fill_time'] = self.fill_time.isoformat()
        return d


@dataclass
class Position:
    """Represents an open position."""
    symbol: str
    side: PositionSide
    quantity: float
    entry_price: float
    entry_time: datetime
    
    # P&L tracking
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    total_costs: float = 0.0
    
    # Risk
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    
    def update_pnl(self, current_price: float):
        """Update unrealized P&L."""
        if self.side == PositionSide.LONG:
            self.unrealized_pnl = (current_price - self.entry_price) * self.quantity
        elif self.side == PositionSide.SHORT:
            self.unrealized_pnl = (self.entry_price - current_price) * self.quantity
    
    def to_dict(self) -> Dict:
        d = asdict(self)
        d['side'] = self.side.value
        d['entry_time'] = self.entry_time.isoformat()
        return d


@dataclass
class DailyStats:
    """Daily trading statistics."""
    date: str
    starting_balance: float
    ending_balance: float
    pnl: float
    pnl_pct: float
    num_trades: int
    wins: int
    losses: int
    
    # Expected vs Actual
    expected_pnl: float = 0.0
    actual_pnl: float = 0.0
    slippage_total: float = 0.0
    costs_total: float = 0.0
    
    def to_dict(self) -> Dict:
        return asdict(self)


# ═══════════════════════════════════════════════════════════════════════════════
#                           PAPER TRADING ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

class PaperTradingEngine:
    """
    Paper trading engine for forward testing strategies.
    
    Usage:
        engine = PaperTradingEngine(
            initial_balance=1000,
            symbol='BTCUSDT'
        )
        
        # Execute trade
        order = engine.place_order('buy', quantity=0.01, price=45000)
        
        # Update with market data
        engine.update_price(45500)
        
        # Get stats
        stats = engine.get_daily_stats()
    """
    
    def __init__(
        self,
        initial_balance: float = 1000.0,
        symbol: str = 'BTCUSDT',
        log_dir: str = None
    ):
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.symbol = symbol
        
        # Logging
        self.log_dir = log_dir or os.path.join(
            os.path.dirname(__file__), 'paper_trading_logs'
        )
        os.makedirs(self.log_dir, exist_ok=True)
        
        # Order and position tracking
        self.orders: List[Order] = []
        self.positions: Dict[str, Position] = {}  # symbol -> position
        self.order_counter = 0
        
        # Cost calculators
        self.cost_calc = BinanceFuturesCosts(symbol)
        self.slippage_sim = SlippageSimulator(symbol)
        
        # Daily stats
        self.daily_stats: List[DailyStats] = []
        self.today_trades = 0
        self.today_wins = 0
        self.today_losses = 0
        self.today_start_balance = initial_balance
        
        # Current market data
        self.current_price = 0.0
        self.last_update = datetime.now()
        
        logger.info(f"Paper Trading Engine initialized: {symbol}, Balance: ${initial_balance:,.2f}")
    
    def _generate_order_id(self) -> str:
        """Generate unique order ID."""
        self.order_counter += 1
        return f"PT-{datetime.now().strftime('%Y%m%d%H%M%S')}-{self.order_counter:04d}"
    
    def place_order(
        self,
        side: str,
        quantity: float,
        price: float,
        order_type: str = 'market',
        strategy: str = 'manual',
        stop_loss: float = None,
        take_profit: float = None
    ) -> Order:
        """
        Place a paper trade order.
        
        Args:
            side: 'buy' or 'sell'
            quantity: Amount to trade
            price: Current market price (signal price)
            order_type: 'market' or 'limit'
            strategy: Strategy name for tracking
            stop_loss: Optional stop loss price
            take_profit: Optional take profit price
            
        Returns:
            Order object
        """
        order_side = OrderSide.BUY if side.lower() == 'buy' else OrderSide.SELL
        
        order = Order(
            order_id=self._generate_order_id(),
            symbol=self.symbol,
            side=order_side,
            quantity=quantity,
            order_type=order_type,
            signal_price=price,
            strategy=strategy
        )
        
        if order_type == 'limit':
            order.limit_price = price
        
        # Simulate execution
        self._execute_order(order, price)
        
        # Create/update position if filled
        if order.status == OrderStatus.FILLED:
            self._update_position(order, stop_loss, take_profit)
        
        self.orders.append(order)
        self.today_trades += 1
        
        return order
    
    def _execute_order(self, order: Order, market_price: float):
        """Simulate order execution with slippage."""
        # Calculate slippage
        order_type = OrderType.MARKET if order.order_type == 'market' else OrderType.LIMIT
        
        slippage_result = self.slippage_sim.calculate(
            price=market_price,
            size=order.quantity * market_price,
            order_type=order_type,
            is_buy=(order.side == OrderSide.BUY)
        )
        
        slippage_pct = slippage_result['slippage_pct'] / 100  # Convert from percent
        
        # Apply slippage
        if order.side == OrderSide.BUY:
            fill_price = market_price * (1 + slippage_pct)
        else:
            fill_price = market_price * (1 - slippage_pct)
        
        order.fill_price = fill_price
        order.slippage = abs(fill_price - market_price)
        order.fill_time = datetime.now()
        
        # Calculate costs
        trade_costs = self.cost_calc.calculate_trade_cost(
            entry_price=fill_price,
            quantity=order.quantity,
            leverage=1  # Paper trading uses 1x
        )
        order.commission = trade_costs['trading_fee_entry']
        order.total_cost = order.commission + order.slippage * order.quantity
        
        # Deduct costs from balance
        self.balance -= order.total_cost
        
        order.status = OrderStatus.FILLED
        
        logger.info(f"Order {order.order_id} FILLED: {order.side.value} {order.quantity} @ {fill_price:.2f} "
                   f"(slippage: ${order.slippage:.2f}, cost: ${order.total_cost:.2f})")
    
    def _update_position(self, order: Order, stop_loss: float = None, take_profit: float = None):
        """Update position after order fill."""
        symbol = order.symbol
        
        if symbol not in self.positions:
            # New position
            side = PositionSide.LONG if order.side == OrderSide.BUY else PositionSide.SHORT
            self.positions[symbol] = Position(
                symbol=symbol,
                side=side,
                quantity=order.quantity,
                entry_price=order.fill_price,
                entry_time=order.fill_time,
                stop_loss=stop_loss,
                take_profit=take_profit
            )
        else:
            pos = self.positions[symbol]
            
            # Same direction: add to position
            if (pos.side == PositionSide.LONG and order.side == OrderSide.BUY) or \
               (pos.side == PositionSide.SHORT and order.side == OrderSide.SELL):
                # Average entry price
                total_qty = pos.quantity + order.quantity
                pos.entry_price = (pos.entry_price * pos.quantity + 
                                  order.fill_price * order.quantity) / total_qty
                pos.quantity = total_qty
            else:
                # Opposite direction: reduce or close position
                if order.quantity >= pos.quantity:
                    # Close position
                    pos.update_pnl(order.fill_price)
                    realized = pos.unrealized_pnl - pos.total_costs
                    self.balance += realized
                    
                    if realized > 0:
                        self.today_wins += 1
                    else:
                        self.today_losses += 1
                    
                    pos.realized_pnl = realized
                    logger.info(f"Position closed: {symbol}, P&L: ${realized:.2f}")
                    
                    # Remove or flip position
                    if order.quantity > pos.quantity:
                        # Flip position
                        new_side = PositionSide.LONG if order.side == OrderSide.BUY else PositionSide.SHORT
                        self.positions[symbol] = Position(
                            symbol=symbol,
                            side=new_side,
                            quantity=order.quantity - pos.quantity,
                            entry_price=order.fill_price,
                            entry_time=order.fill_time
                        )
                    else:
                        del self.positions[symbol]
                else:
                    # Partial close
                    pos.quantity -= order.quantity
    
    def update_price(self, price: float):
        """Update current market price and check stops."""
        self.current_price = price
        self.last_update = datetime.now()
        
        # Update unrealized P&L
        for symbol, pos in list(self.positions.items()):
            pos.update_pnl(price)
            
            # Check stop loss
            if pos.stop_loss:
                if (pos.side == PositionSide.LONG and price <= pos.stop_loss) or \
                   (pos.side == PositionSide.SHORT and price >= pos.stop_loss):
                    logger.info(f"Stop loss triggered for {symbol} @ {price}")
                    self.close_position(symbol, price, "stop_loss")
            
            # Check take profit
            if pos.take_profit:
                if (pos.side == PositionSide.LONG and price >= pos.take_profit) or \
                   (pos.side == PositionSide.SHORT and price <= pos.take_profit):
                    logger.info(f"Take profit triggered for {symbol} @ {price}")
                    self.close_position(symbol, price, "take_profit")
    
    def close_position(self, symbol: str, price: float, reason: str = "manual"):
        """Close an open position."""
        if symbol not in self.positions:
            logger.warning(f"No position to close for {symbol}")
            return
        
        pos = self.positions[symbol]
        side = 'sell' if pos.side == PositionSide.LONG else 'buy'
        self.place_order(side, pos.quantity, price, strategy=reason)
    
    def get_equity(self) -> float:
        """Get current equity (balance + unrealized P&L)."""
        unrealized = sum(pos.unrealized_pnl for pos in self.positions.values())
        return self.balance + unrealized
    
    def end_day(self) -> DailyStats:
        """End trading day and record stats."""
        equity = self.get_equity()
        pnl = equity - self.today_start_balance
        pnl_pct = pnl / self.today_start_balance * 100
        
        stats = DailyStats(
            date=datetime.now().strftime('%Y-%m-%d'),
            starting_balance=self.today_start_balance,
            ending_balance=equity,
            pnl=pnl,
            pnl_pct=pnl_pct,
            num_trades=self.today_trades,
            wins=self.today_wins,
            losses=self.today_losses,
            slippage_total=sum(o.slippage * o.quantity for o in self.orders 
                              if o.created_at.date() == datetime.now().date()),
            costs_total=sum(o.total_cost for o in self.orders 
                           if o.created_at.date() == datetime.now().date())
        )
        
        self.daily_stats.append(stats)
        
        # Save to file
        self._save_daily_log(stats)
        
        # Reset daily counters
        self.today_start_balance = equity
        self.today_trades = 0
        self.today_wins = 0
        self.today_losses = 0
        
        return stats
    
    def _save_daily_log(self, stats: DailyStats):
        """Save daily stats to JSON file."""
        filename = f"paper_trading_{datetime.now().strftime('%Y%m%d')}.json"
        filepath = os.path.join(self.log_dir, filename)
        
        data = {
            'stats': stats.to_dict(),
            'orders': [o.to_dict() for o in self.orders 
                      if o.created_at.date() == datetime.now().date()],
            'positions': {k: v.to_dict() for k, v in self.positions.items()}
        }
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2, default=str)
        
        logger.info(f"Daily log saved: {filepath}")
    
    def get_summary(self) -> Dict:
        """Get overall paper trading summary."""
        equity = self.get_equity()
        total_pnl = equity - self.initial_balance
        total_pnl_pct = total_pnl / self.initial_balance * 100
        
        filled_orders = [o for o in self.orders if o.status == OrderStatus.FILLED]
        total_slippage = sum(o.slippage * o.quantity for o in filled_orders)
        total_costs = sum(o.total_cost for o in filled_orders)
        
        return {
            'initial_balance': self.initial_balance,
            'current_equity': equity,
            'total_pnl': total_pnl,
            'total_pnl_pct': total_pnl_pct,
            'total_trades': len(filled_orders),
            'open_positions': len(self.positions),
            'total_slippage': total_slippage,
            'total_costs': total_costs,
            'days_traded': len(self.daily_stats),
        }


# ═══════════════════════════════════════════════════════════════════════════════
#                           MAIN (Demo)
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    print("=" * 60)
    print("PAPER TRADING ENGINE - DEMO")
    print("=" * 60)
    
    # Create engine
    engine = PaperTradingEngine(
        initial_balance=1000,
        symbol='BTCUSDT'
    )
    
    print(f"\nInitial Balance: ${engine.balance:,.2f}")
    
    # Simulate trading
    print("\n--- Day 1 Trading ---")
    
    # Buy BTC
    order1 = engine.place_order(
        side='buy',
        quantity=0.01,
        price=45000,
        strategy='trend_follower_v2',
        stop_loss=43000,
        take_profit=48000
    )
    print(f"Order 1: {order1.status.value} @ ${order1.fill_price:,.2f}")
    
    # Price moves up
    engine.update_price(46000)
    print(f"Price: $46,000 - Equity: ${engine.get_equity():,.2f}")
    
    # Close position
    order2 = engine.place_order(
        side='sell',
        quantity=0.01,
        price=46000,
        strategy='take_profit'
    )
    print(f"Order 2: {order2.status.value} @ ${order2.fill_price:,.2f}")
    
    # End day
    stats = engine.end_day()
    
    print(f"\n--- Day 1 Summary ---")
    print(f"P&L: ${stats.pnl:,.2f} ({stats.pnl_pct:.2f}%)")
    print(f"Trades: {stats.num_trades}, Wins: {stats.wins}, Losses: {stats.losses}")
    print(f"Slippage: ${stats.slippage_total:.2f}")
    print(f"Costs: ${stats.costs_total:.2f}")
    
    # Overall summary
    summary = engine.get_summary()
    print(f"\n--- Overall Summary ---")
    print(f"Total P&L: ${summary['total_pnl']:,.2f} ({summary['total_pnl_pct']:.2f}%)")
    print(f"Total Trades: {summary['total_trades']}")
    print(f"Total Slippage: ${summary['total_slippage']:.2f}")
    print(f"Total Costs: ${summary['total_costs']:.2f}")
    
    print("\n" + "=" * 60)
