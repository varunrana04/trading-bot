#!/usr/bin/env python3
"""
================================================================================
                    PAPER TRADING WEB DASHBOARD
================================================================================
Gradio-based web interface for Hugging Face Spaces deployment.
Runs the paper trading bot in background and displays live stats.
================================================================================
"""

import gradio as gr
import threading
import time
import os
import sys
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Try importing from live/ folder
try:
    from live.data_feed import SimulatedDataFeed
    from live.signal_engine import SignalEngine
    from live.paper_trader import PaperTrader
except ImportError:
    from data_feed import SimulatedDataFeed
    from signal_engine import SignalEngine
    from paper_trader import PaperTrader


class TradingBotDashboard:
    """Web dashboard for the trading bot"""
    
    def __init__(self, balance=100000.0, min_lev=10, max_lev=50):
        self.symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XAUUSDT", "XAGUSDT"]
        self.balance = balance
        self.min_lev = min_lev
        self.max_lev = max_lev
        
        # Trading components
        self.data_feed = None
        self.signal_engine = None
        self.paper_trader = None
        
        # State
        self.running = False
        self.thread = None
        self.last_update = None
        self.logs = []
        self.signals_log = []
        self.trades_log = []
        
    def log(self, msg):
        """Add to logs"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        entry = f"[{timestamp}] {msg}"
        self.logs.append(entry)
        if len(self.logs) > 100:
            self.logs = self.logs[-100:]
        print(entry)
    
    def start_bot(self):
        """Initialize and start the trading bot"""
        if self.running:
            return "Bot is already running!"
        
        try:
            self.log("Initializing trading components...")
            
            # Initialize components
            self.data_feed = SimulatedDataFeed(self.symbols, ["15m", "1h"])
            
            # Log Binance client status
            if self.data_feed.client:
                self.log("✅ Binance API client connected")
            elif self.data_feed.use_rest_fallback:
                self.log("ℹ️ Using REST API fallback (direct HTTP to Binance)")
            else:
                self.log("❌ Binance API client NOT connected!")
                self.log("   Check if python-binance is installed correctly")
            
            self.signal_engine = SignalEngine()
            self.paper_trader = PaperTrader(
                starting_balance=self.balance,
                min_leverage=self.min_lev,
                max_leverage=self.max_lev
            )
            
            self.log("Fetching initial market data...")
            self.data_feed.fetch_latest()
            
            # Log data fetch results
            data_status = []
            for sym in self.symbols:
                df = self.data_feed.get_dataframe(sym, "15m")
                if df is not None and len(df) > 0:
                    data_status.append(f"{sym}: ✅ {len(df)} candles")
                else:
                    data_status.append(f"{sym}: ❌ No data")
            self.log(f"Data status: {', '.join(data_status)}")
            
            self.running = True
            self.thread = threading.Thread(target=self._run_loop, daemon=True)
            self.thread.start()
            
            self.log(f"✅ Bot started! Trading {', '.join(self.symbols)}")
            self.log(f"   Balance: ${self.balance:,.0f} | Leverage: {self.min_lev}x-{self.max_lev}x")
            
            return "✅ Bot started successfully!"
            
        except Exception as e:
            self.log(f"❌ Error starting bot: {e}")
            import traceback
            self.log(f"   Traceback: {traceback.format_exc()}")
            return f"❌ Error: {e}"
    
    def _run_loop(self):
        """Background trading loop"""
        poll_interval = 60  # seconds
        
        while self.running:
            try:
                # Fetch latest data
                self.data_feed.fetch_latest()
                self.last_update = datetime.now()
                
                # Process each symbol
                for symbol in self.symbols:
                    self._process_symbol(symbol)
                
                # Wait for next poll
                time.sleep(poll_interval)
                
            except Exception as e:
                self.log(f"⚠️ Error in loop: {e}")
                time.sleep(10)
    
    def _process_symbol(self, symbol: str):
        """Process trading logic for a symbol"""
        df_1h = self.data_feed.get_dataframe(symbol, "1h")
        df_15m = self.data_feed.get_dataframe(symbol, "15m")
        
        if df_1h is None or df_15m is None:
            self.log(f"⚠️ {symbol}: No data available")
            return
        
        latest = self.data_feed.get_latest(symbol, "15m")
        if not latest:
            return
            
        current_price = latest['close']
        
        # Check existing position
        if self.paper_trader.has_position(symbol):
            exit_reason = self.paper_trader.update_position(symbol, current_price)
            if exit_reason:
                pos = self.paper_trader.get_position(symbol)
                self.log(f"🔴 CLOSED {symbol} - Reason: {exit_reason}")
                self.trades_log.append({
                    'time': datetime.now().strftime("%Y-%m-%d %H:%M"),
                    'symbol': symbol,
                    'action': 'CLOSE',
                    'reason': exit_reason
                })
        else:
            # Generate signal
            signal = self.signal_engine.process(symbol, df_1h, df_15m)
            
            # Log signal status for visibility
            direction = signal.get('direction', 'NEUTRAL')
            sig_type = signal['signal']
            
            if sig_type in ['BUY', 'SELL']:
                signal['price'] = current_price
                signal['atr_pct'] = 1.0
                self.paper_trader.open_position(signal)
                
                emoji = "🟢 LONG" if sig_type == 'BUY' else "🔴 SHORT"
                self.log(f"{emoji} {symbol} @ ${current_price:,.2f} (score: {signal.get('score', 0)}/5)")
                
                self.signals_log.append({
                    'time': datetime.now().strftime("%Y-%m-%d %H:%M"),
                    'symbol': symbol,
                    'signal': sig_type,
                    'price': current_price,
                    'confidence': signal.get('confidence', 0)
                })
            else:
                # Log why we're not trading (periodically, not every tick)
                reason = signal.get('reason', 'Conditions not met')
                if direction != 'NEUTRAL':
                    self.log(f"📊 {symbol}: {direction} trend, waiting for entry ({reason})")
                else:
                    self.log(f"⏸️ {symbol}: No clear trend @ ${current_price:,.2f}")
    
    def stop_bot(self):
        """Stop the trading bot"""
        self.running = False
        self.log("🛑 Bot stopped")
        return "🛑 Bot stopped"
    
    def get_status(self):
        """Get current bot status"""
        if not self.running:
            return "🔴 Bot is not running", "", "", ""
        
        stats = self.paper_trader.get_stats() if self.paper_trader else {}
        
        # Build status display
        status = "🟢 Bot is running"
        if self.last_update:
            status += f"\n📡 Last update: {self.last_update.strftime('%H:%M:%S')}"
        
        # Build P&L display
        pnl_display = f"""
## 💰 Portfolio Status

| Metric | Value |
|--------|-------|
| **Starting Balance** | ${self.balance:,.2f} |
| **Current Balance** | ${stats.get('balance', self.balance):,.2f} |
| **Total P&L** | ${stats.get('total_pnl', 0):,.2f} |
| **Return** | {stats.get('total_return', 0):.2f}% |
| **Win Rate** | {stats.get('win_rate', 0):.1f}% |
| **Total Trades** | {stats.get('total_trades', 0)} |
"""
        
        # Build positions display
        positions = []
        if self.paper_trader:
            for symbol in self.symbols:
                pos = self.paper_trader.get_position(symbol)
                if pos:
                    latest = self.data_feed.get_latest(symbol, "15m") if self.data_feed else None
                    current_price = latest['close'] if latest else pos.entry_price
                    pnl_pct = ((current_price - pos.entry_price) / pos.entry_price * 100)
                    if pos.direction == "SHORT":
                        pnl_pct = -pnl_pct
                    positions.append(f"• **{symbol}** {pos.direction} @ ${pos.entry_price:,.2f} → ${current_price:,.2f} ({pnl_pct:+.2f}%)")
        
        positions_display = "\n".join(positions) if positions else "No open positions"
        
        # Build logs display
        logs_display = "\n".join(self.logs[-20:]) if self.logs else "No logs yet"
        
        return status, pnl_display, positions_display, logs_display
    
    def get_logs(self):
        """Get recent logs"""
        return "\n".join(self.logs[-50:]) if self.logs else "No logs yet"


# Initialize dashboard
print("=" * 60)
print("  PAPER TRADING BOT - HUGGING FACE DEPLOYMENT")
print("=" * 60)

# Get config from environment or use defaults
BALANCE = float(os.environ.get("STARTING_BALANCE", "100000"))
MIN_LEV = int(os.environ.get("MIN_LEVERAGE", "10"))
MAX_LEV = int(os.environ.get("MAX_LEVERAGE", "50"))

dashboard = TradingBotDashboard(balance=BALANCE, min_lev=MIN_LEV, max_lev=MAX_LEV)

# Auto-start the bot
dashboard.start_bot()


# Create Gradio interface
with gr.Blocks(title="Crypto Paper Trading Bot", theme=gr.themes.Soft()) as app:
    gr.Markdown("""
    # 🤖 Crypto & Precious Metals Trading Bot
    
    Real-time paper trading on **BTC, ETH, SOL, Gold, Silver** using multi-timeframe analysis.
    """)
    
    with gr.Row():
        with gr.Column(scale=2):
            status_display = gr.Markdown("Loading...")
            pnl_display = gr.Markdown("Loading P&L...")
        
        with gr.Column(scale=1):
            positions_display = gr.Markdown("Loading positions...")
    
    with gr.Accordion("📋 Activity Logs", open=False):
        logs_display = gr.Textbox(
            label="Recent Activity",
            lines=15,
            interactive=False
        )
    
    with gr.Row():
        refresh_btn = gr.Button("🔄 Refresh", variant="primary")
        stop_btn = gr.Button("🛑 Stop Bot", variant="stop")
        start_btn = gr.Button("▶️ Start Bot", variant="secondary")
    
    # Auto-refresh every 30 seconds
    def refresh():
        return dashboard.get_status()
    
    refresh_btn.click(
        fn=refresh,
        outputs=[status_display, pnl_display, positions_display, logs_display]
    )
    
    stop_btn.click(
        fn=dashboard.stop_bot,
        outputs=[status_display]
    )
    
    start_btn.click(
        fn=dashboard.start_bot,
        outputs=[status_display]
    )
    
    # Load initial status
    app.load(
        fn=refresh,
        outputs=[status_display, pnl_display, positions_display, logs_display]
    )


if __name__ == "__main__":
    # Launch on port 7860 (Hugging Face default)
    app.launch(server_name="0.0.0.0", server_port=7860)
