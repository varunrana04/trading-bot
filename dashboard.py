#!/usr/bin/env python3
"""
================================================================================
                    DASHBOARD - LIVE MONITORING
================================================================================
Console-based dashboard for monitoring paper trading in real-time.
================================================================================
"""

import os
import sys
from datetime import datetime, timezone, timedelta
from typing import Dict, List

# IST timezone (UTC+5:30)
IST = timezone(timedelta(hours=5, minutes=30))

# Cross-platform terminal handling
try:
    import curses
    CURSES_AVAILABLE = True
except ImportError:
    CURSES_AVAILABLE = False


def clear_screen():
    """Clear terminal screen"""
    os.system('cls' if os.name == 'nt' else 'clear')


class SimpleDashboard:
    """Simple text-based dashboard (no curses required)"""
    
    def __init__(self, starting_balance: float = 100000.0):
        self.last_update = None
        self.signals: Dict[str, Dict] = {}
        self.positions: Dict[str, Dict] = {}
        self.trades: List[Dict] = []
        self.stats: Dict = {}
        self.balance = starting_balance
        self.starting_balance = starting_balance
    
    def update_signal(self, symbol: str, signal: Dict):
        """Update signal display"""
        self.signals[symbol] = signal
    
    def update_position(self, symbol: str, position: Dict):
        """Update position display"""
        if position:
            self.positions[symbol] = position
        elif symbol in self.positions:
            del self.positions[symbol]
    
    def add_trade(self, trade: Dict):
        """Add trade to history"""
        self.trades.append(trade)
        if len(self.trades) > 10:
            self.trades = self.trades[-10:]
    
    def update_stats(self, stats: Dict):
        """Update trading statistics"""
        self.stats = stats
        self.balance = stats.get('balance', self.balance)
    
    def render(self):
        """Render dashboard to console"""
        clear_screen()
        
        now = datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S IST")
        
        print("=" * 80)
        print(f"  PAPER TRADING DASHBOARD                         {now}")
        print("=" * 80)
        
        # Balance and stats
        ret = self.stats.get('return_pct', 0)
        ret_str = f"+{ret}%" if ret >= 0 else f"{ret}%"
        print(f"\n  Balance: ${self.balance:.2f} ({ret_str})")
        print(f"  Trades: {self.stats.get('total_trades', 0)} | "
              f"Win Rate: {self.stats.get('win_rate', 0)}% | "
              f"PF: {self.stats.get('profit_factor', 0)}")
        
        # Current signals
        print("\n" + "-" * 80)
        print("  SIGNALS")
        print("-" * 80)
        print(f"  {'Symbol':<12} {'Signal':<8} {'Direction':<10} {'Price':<12} {'Score'}")
        print("  " + "-" * 60)
        
        for sym, sig in self.signals.items():
            signal = sig.get('signal', 'HOLD')
            direction = sig.get('direction', '-')
            price = sig.get('price', 0)
            score = sig.get('score', 0)
            
            if signal == 'BUY':
                sig_str = '[BUY]'
            elif signal == 'SELL':
                sig_str = '[SELL]'
            else:
                sig_str = 'HOLD'
            
            print(f"  {sym:<12} {sig_str:<8} {direction:<10} ${price:<11.2f} {score}")
        
        # Open positions
        print("\n" + "-" * 80)
        print("  OPEN POSITIONS")
        print("-" * 80)
        
        if self.positions:
            print(f"  {'Symbol':<12} {'Dir':<6} {'Entry':<12} {'Current':<12} {'P&L%':<8} {'Hold'}")
            print("  " + "-" * 60)
            
            for sym, pos in self.positions.items():
                entry = pos.get('entry_price', 0)
                current = pos.get('current_price', entry)
                direction = pos.get('direction', '-')
                hold = pos.get('hold_candles', 0)
                
                if direction == 'BUY':
                    pnl_pct = (current - entry) / entry * 100
                else:
                    pnl_pct = (entry - current) / entry * 100
                
                pnl_str = f"+{pnl_pct:.2f}%" if pnl_pct >= 0 else f"{pnl_pct:.2f}%"
                
                print(f"  {sym:<12} {direction:<6} ${entry:<11.2f} ${current:<11.2f} {pnl_str:<8} {hold}")
        else:
            print("  No open positions")
        
        # Recent trades
        print("\n" + "-" * 80)
        print("  RECENT TRADES")
        print("-" * 80)
        
        if self.trades:
            print(f"  {'Symbol':<12} {'Dir':<6} {'P&L':<10} {'Reason':<10} {'Time'}")
            print("  " + "-" * 60)
            
            for trade in reversed(self.trades[-5:]):
                sym = trade.get('symbol', '-')
                direction = trade.get('direction', '-')
                pnl = trade.get('pnl', 0)
                reason = trade.get('reason', '-')
                time = trade.get('time', '-')
                
                pnl_str = f"+${pnl:.2f}" if pnl >= 0 else f"-${abs(pnl):.2f}"
                
                print(f"  {sym:<12} {direction:<6} {pnl_str:<10} {reason:<10} {time}")
        else:
            print("  No trades yet")
        
        print("\n" + "=" * 80)
        print("  Press Ctrl+C to stop")
        print("=" * 80)


class DashboardManager:
    """Manages dashboard updates"""
    
    def __init__(self, starting_balance: float = 100000.0):
        self.dashboard = SimpleDashboard(starting_balance)
    
    def on_signal(self, signal: Dict):
        """Handle signal update"""
        self.dashboard.update_signal(signal['symbol'], signal)
    
    def on_position_update(self, symbol: str, position: Dict):
        """Handle position update"""
        self.dashboard.update_position(symbol, position)
    
    def on_trade(self, trade: Dict):
        """Handle trade completion"""
        self.dashboard.add_trade({
            'symbol': trade.get('symbol'),
            'direction': trade.get('direction'),
            'pnl': trade.get('pnl', 0),
            'reason': trade.get('reason'),
            'time': datetime.now().strftime('%H:%M:%S')
        })
    
    def on_stats_update(self, stats: Dict):
        """Handle stats update"""
        self.dashboard.update_stats(stats)
    
    def render(self):
        """Render dashboard"""
        self.dashboard.render()


if __name__ == "__main__":
    # Test dashboard
    dashboard = DashboardManager()
    
    # Simulate updates
    dashboard.on_signal({
        'symbol': 'BTCUSDT',
        'signal': 'BUY',
        'direction': 'BULLISH',
        'price': 42000.0,
        'score': 4
    })
    
    dashboard.on_signal({
        'symbol': 'ETHUSDT',
        'signal': 'HOLD',
        'direction': 'NEUTRAL',
        'price': 2200.0,
        'score': 2
    })
    
    dashboard.on_signal({
        'symbol': 'SOLUSDT',
        'signal': 'SELL',
        'direction': 'BEARISH',
        'price': 100.0,
        'score': 3
    })
    
    dashboard.on_position_update('BTCUSDT', {
        'entry_price': 42000.0,
        'current_price': 42300.0,
        'direction': 'BUY',
        'hold_candles': 5
    })
    
    dashboard.on_stats_update({
        'total_trades': 15,
        'win_rate': 48.5,
        'profit_factor': 1.25,
        'balance': 1050.0,
        'return_pct': 5.0
    })
    
    dashboard.on_trade({
        'symbol': 'ETHUSDT',
        'direction': 'BUY',
        'pnl': 12.50,
        'reason': 'TP'
    })
    
    dashboard.render()
