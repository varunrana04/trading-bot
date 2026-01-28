#!/usr/bin/env python3
"""
================================================================================
                    PAPER TRADING RUNNER - WEBSOCKET MODE
================================================================================
Real-time paper trading with Binance WebSocket streaming.
Instant signal generation on candle close.

Usage:
    python run_paper.py                  # Run with WebSocket (real-time)
    python run_paper.py --balance 50000  # Start with $50k
    python run_paper.py --min-lev 5 --max-lev 50  # Custom leverage range
================================================================================
"""

import argparse
import asyncio
import logging
import sys
import signal as sig
from datetime import datetime
from typing import Dict

# Add parent directory to path
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Try importing from live/ folder (local), fallback to root (HF)
try:
    from live.data_feed import BinanceDataFeed, SimulatedDataFeed
    from live.signal_engine import SignalEngine
    from live.paper_trader import PaperTrader
    from live.dashboard import DashboardManager
    from live.alerts import AlertManager, TelegramAlert
except ImportError:
    from data_feed import BinanceDataFeed, SimulatedDataFeed
    from signal_engine import SignalEngine
    from paper_trader import PaperTrader
    from dashboard import DashboardManager
    from alerts import AlertManager, TelegramAlert

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("PaperRunner")


class RealTimeTradingSystem:
    """Real-time paper trading system with WebSocket"""
    
    def __init__(self, symbols: list, balance: float = 100000.0, min_lev: int = 10, max_lev: int = 50):
        self.symbols = symbols
        self.running = False
        self.min_lev = min_lev
        self.max_lev = max_lev
        
        # Initialize components
        logger.info("Initializing REAL-TIME paper trading system...")
        
        self.data_feed = BinanceDataFeed(symbols, ["15m", "1h"])
        self.signal_engine = SignalEngine()
        self.paper_trader = PaperTrader(starting_balance=balance, min_leverage=min_lev, max_leverage=max_lev)
        self.dashboard = DashboardManager(starting_balance=balance)
        self.alerts = AlertManager()
        
        # Wire up callbacks
        self._setup_callbacks()
        
        logger.info(f"System initialized with {len(symbols)} symbols, ${balance:,.0f} balance")
        logger.info(f"Leverage range: {min_lev}x - {max_lev}x (dynamic)")
        logger.info("MODE: WebSocket Real-Time Streaming")
    
    def _setup_callbacks(self):
        """Connect component callbacks"""
        
        # Data feed callback - process on each candle update
        def on_candle(symbol, timeframe, candle, is_closed):
            if is_closed:
                logger.info(f"[CANDLE] {symbol} {timeframe} closed @ {candle['close']:.2f}")
                self.process_candle(symbol)
                self.dashboard.render()
        
        self.data_feed.add_callback(on_candle)
        
        # Signal engine -> alerts
        self.signal_engine.add_callback(self.alerts.on_signal)
        
        # Paper trader -> alerts
        def on_trade_event(event_type, data):
            if event_type == "OPEN":
                self.alerts.on_trade_open(data)
            elif event_type == "CLOSE":
                self.alerts.on_trade_close(data)
                self.dashboard.on_trade(data)
        
        self.paper_trader.add_callback(on_trade_event)
    
    def process_candle(self, symbol: str):
        """Process new candle for a symbol"""
        
        # Get data
        df_1h = self.data_feed.get_dataframe(symbol, "1h")
        df_15m = self.data_feed.get_dataframe(symbol, "15m")
        
        if df_1h is None or df_15m is None:
            return
        
        # Get latest price
        latest = self.data_feed.get_latest(symbol, "15m")
        if latest:
            current_price = latest['close']
        else:
            return
        
        # Check existing position
        if self.paper_trader.has_position(symbol):
            exit_reason = self.paper_trader.update_position(symbol, current_price)
            
            if not exit_reason:
                # Update dashboard with position
                pos = self.paper_trader.get_position(symbol)
                if pos:
                    self.dashboard.on_position_update(symbol, {
                        'entry_price': pos.entry_price,
                        'current_price': current_price,
                        'direction': pos.direction,
                        'hold_candles': pos.hold_candles
                    })
        else:
            # Generate signal
            signal = self.signal_engine.process(symbol, df_1h, df_15m)
            
            # Update dashboard
            self.dashboard.on_signal(signal)
            
            # Open position if signal
            if signal['signal'] in ['BUY', 'SELL']:
                signal['price'] = current_price
                signal['atr_pct'] = 1.0  # Default
                self.paper_trader.open_position(signal)
        
        # Update stats
        stats = self.paper_trader.get_stats()
        self.dashboard.on_stats_update(stats)
    
    async def run_async(self):
        """Run the paper trading system with WebSocket"""
        self.running = True
        
        # Send startup alert
        self.alerts.send_startup(self.symbols, self.paper_trader.balance)
        
        logger.info("Starting REAL-TIME trading with WebSocket...")
        logger.info("Fetching initial historical data...")
        
        # Fetch initial data
        self.data_feed.fetch_initial_data(days=7)
        
        # Process each symbol initially
        for symbol in self.symbols:
            self.process_candle(symbol.upper())
        
        # Render initial dashboard
        self.dashboard.render()
        
        # Start WebSocket streaming
        logger.info("Connecting to Binance WebSocket...")
        await self.data_feed._connect()
    
    def run(self):
        """Run the system (blocking)"""
        try:
            asyncio.run(self.run_async())
        except KeyboardInterrupt:
            logger.info("Shutting down...")
            self.stop()
    
    def stop(self):
        """Stop the system"""
        self.running = False
        self.data_feed.stop()
        
        # Print final summary
        self.paper_trader.print_summary()
        
        # Send final alert
        stats = self.paper_trader.get_stats()
        self.alerts.send_daily_summary(stats)


class PollingTradingSystem:
    """Fallback polling-based trading system"""
    
    def __init__(self, symbols: list, balance: float = 100000.0, min_lev: int = 10, max_lev: int = 50, poll_interval: int = 10):
        self.symbols = symbols
        self.running = False
        self.poll_interval = poll_interval
        
        logger.info("Initializing polling-based paper trading system...")
        
        self.data_feed = SimulatedDataFeed(symbols, ["15m", "1h"])
        self.signal_engine = SignalEngine()
        self.paper_trader = PaperTrader(starting_balance=balance, min_leverage=min_lev, max_leverage=max_lev)
        self.dashboard = DashboardManager()
        self.alerts = AlertManager()
        
        self._setup_callbacks()
        
        logger.info(f"System initialized with {len(symbols)} symbols, ${balance:,.0f} balance")
        logger.info(f"MODE: Polling every {poll_interval}s")
    
    def _setup_callbacks(self):
        self.signal_engine.add_callback(self.alerts.on_signal)
        
        def on_trade_event(event_type, data):
            if event_type == "OPEN":
                self.alerts.on_trade_open(data)
            elif event_type == "CLOSE":
                self.alerts.on_trade_close(data)
                self.dashboard.on_trade(data)
        
        self.paper_trader.add_callback(on_trade_event)
    
    def process_candle(self, symbol: str):
        df_1h = self.data_feed.get_dataframe(symbol, "1h")
        df_15m = self.data_feed.get_dataframe(symbol, "15m")
        
        if df_1h is None or df_15m is None:
            return
        
        latest = self.data_feed.get_latest(symbol, "15m")
        if latest:
            current_price = latest['close']
        else:
            return
        
        if self.paper_trader.has_position(symbol):
            exit_reason = self.paper_trader.update_position(symbol, current_price)
            if not exit_reason:
                pos = self.paper_trader.get_position(symbol)
                if pos:
                    self.dashboard.on_position_update(symbol, {
                        'entry_price': pos.entry_price,
                        'current_price': current_price,
                        'direction': pos.direction,
                        'hold_candles': pos.hold_candles
                    })
        else:
            signal = self.signal_engine.process(symbol, df_1h, df_15m)
            self.dashboard.on_signal(signal)
            
            if signal['signal'] in ['BUY', 'SELL']:
                signal['price'] = current_price
                signal['atr_pct'] = 1.0
                self.paper_trader.open_position(signal)
        
        stats = self.paper_trader.get_stats()
        self.dashboard.on_stats_update(stats)
    
    def run(self):
        import time
        self.running = True
        
        self.alerts.send_startup(self.symbols, self.paper_trader.balance)
        
        logger.info(f"Starting paper trading with {self.poll_interval}s polling interval...")
        logger.info("Fetching initial data...")
        self.data_feed.fetch_latest()
        
        for symbol in self.symbols:
            self.process_candle(symbol)
        
        self.dashboard.render()
        
        last_poll = datetime.now()
        
        try:
            while self.running:
                now = datetime.now()
                
                if (now - last_poll).total_seconds() >= self.poll_interval:
                    self.data_feed.fetch_latest()
                    
                    for symbol in self.symbols:
                        self.process_candle(symbol)
                    
                    self.dashboard.render()
                    last_poll = now
                
                time.sleep(1)
                
        except KeyboardInterrupt:
            logger.info("Shutting down...")
            self.stop()
    
    def stop(self):
        self.running = False
        self.paper_trader.print_summary()
        stats = self.paper_trader.get_stats()
        self.alerts.send_daily_summary(stats)


def main():
    parser = argparse.ArgumentParser(description="Paper Trading System")
    parser.add_argument("--symbols", nargs="+", default=["BTCUSDT", "ETHUSDT", "SOLUSDT"],
                        help="Symbols to trade")
    parser.add_argument("--balance", type=float, default=100000.0,
                        help="Starting balance (default: $100,000)")
    parser.add_argument("--poll", type=int, default=0,
                        help="Polling interval in seconds (0=WebSocket mode)")
    parser.add_argument("--min-lev", type=int, default=10,
                        help="Minimum leverage (default: 10)")
    parser.add_argument("--max-lev", type=int, default=50,
                        help="Maximum leverage (default: 50)")
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("  PAPER TRADING SYSTEM")
    print("=" * 60)
    print(f"  Symbols: {', '.join(args.symbols)}")
    print(f"  Balance: ${args.balance:,.0f}")
    print(f"  Leverage: {args.min_lev}x - {args.max_lev}x (dynamic)")
    if args.poll > 0:
        print(f"  Mode: Polling ({args.poll}s)")
    else:
        print(f"  Mode: WebSocket (Real-Time)")
    print("=" * 60)
    print()
    
    # Choose system based on mode
    if args.poll > 0:
        system = PollingTradingSystem(args.symbols, args.balance, args.min_lev, args.max_lev, args.poll)
    else:
        system = RealTimeTradingSystem(args.symbols, args.balance, args.min_lev, args.max_lev)
    
    def signal_handler(signum, frame):
        print("\n\nReceived shutdown signal...")
        system.stop()
        sys.exit(0)
    
    sig.signal(sig.SIGINT, signal_handler)
    sig.signal(sig.SIGTERM, signal_handler)
    
    # Run
    system.run()


if __name__ == "__main__":
    main()
