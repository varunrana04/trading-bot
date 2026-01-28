#!/usr/bin/env python3
"""
================================================================================
                    ALERTS - TELEGRAM NOTIFICATIONS
================================================================================
Sends trading alerts to Telegram for real-time monitoring.
================================================================================
"""

import logging
import os
from datetime import datetime
from typing import Dict, Optional
import json

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("Alerts")


class TelegramAlert:
    """Send alerts to Telegram"""
    
    def __init__(self, bot_token: str = None, chat_id: str = None):
        # Try to get from environment variables
        self.bot_token = bot_token or os.environ.get("TELEGRAM_BOT_TOKEN", "")
        self.chat_id = chat_id or os.environ.get("TELEGRAM_CHAT_ID", "")
        
        self.enabled = bool(self.bot_token and self.chat_id)
        
        if not self.enabled:
            logger.warning("Telegram alerts disabled - missing bot token or chat ID")
            logger.info("Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID environment variables to enable")
    
    def send(self, message: str) -> bool:
        """Send message to Telegram"""
        if not self.enabled:
            logger.info(f"[ALERT] {message}")
            return False
        
        if not REQUESTS_AVAILABLE:
            logger.error("requests library not installed")
            return False
        
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            data = {
                "chat_id": self.chat_id,
                "text": message,
                "parse_mode": "HTML"
            }
            response = requests.post(url, data=data, timeout=10)
            
            if response.status_code == 200:
                return True
            else:
                logger.error(f"Telegram error: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Telegram send error: {e}")
            return False


class AlertManager:
    """Manages trading alerts"""
    
    def __init__(self, telegram: TelegramAlert = None):
        self.telegram = telegram or TelegramAlert()
        self.daily_stats = {
            "trades": 0,
            "wins": 0,
            "losses": 0,
            "pnl": 0.0
        }
        self.last_reset = datetime.now().date()
    
    def _check_day_reset(self):
        """Reset daily stats at midnight"""
        today = datetime.now().date()
        if today != self.last_reset:
            self.daily_stats = {
                "trades": 0,
                "wins": 0,
                "losses": 0,
                "pnl": 0.0
            }
            self.last_reset = today
    
    def on_signal(self, signal: Dict):
        """Alert on new trading signal"""
        if signal.get('signal') in ['BUY', 'SELL']:
            msg = (
                f"<b>SIGNAL</b>\n"
                f"Symbol: {signal['symbol']}\n"
                f"Direction: {signal['signal']}\n"
                f"Price: ${signal.get('price', 0):.2f}\n"
                f"Conviction: {signal.get('conviction', 0):.0%}\n"
                f"Time: {datetime.now().strftime('%H:%M:%S')}"
            )
            self.telegram.send(msg)
    
    def on_trade_open(self, data: Dict):
        """Alert on position opened"""
        msg = (
            f"<b>POSITION OPENED</b>\n"
            f"Symbol: {data['symbol']}\n"
            f"Direction: {data['direction']}\n"
            f"Entry: ${data['entry_price']:.2f}\n"
            f"Margin: ${data['margin']:.2f}\n"
            f"Leverage: {data['leverage']}x\n"
            f"Time: {datetime.now().strftime('%H:%M:%S')}"
        )
        self.telegram.send(msg)
    
    def on_trade_close(self, data: Dict):
        """Alert on position closed"""
        self._check_day_reset()
        
        pnl = data['pnl']
        
        self.daily_stats['trades'] += 1
        self.daily_stats['pnl'] += pnl
        if pnl > 0:
            self.daily_stats['wins'] += 1
        else:
            self.daily_stats['losses'] += 1
        
        emoji = "+" if pnl >= 0 else ""
        result = "WIN" if pnl >= 0 else "LOSS"
        
        msg = (
            f"<b>POSITION CLOSED - {result}</b>\n"
            f"Symbol: {data['symbol']}\n"
            f"Direction: {data['direction']}\n"
            f"Exit: ${data['exit_price']:.2f}\n"
            f"Reason: {data['reason']}\n"
            f"P&L: {emoji}${pnl:.2f}\n"
            f"\n"
            f"<b>Daily Stats</b>\n"
            f"Trades: {self.daily_stats['trades']}\n"
            f"W/L: {self.daily_stats['wins']}/{self.daily_stats['losses']}\n"
            f"Daily P&L: ${self.daily_stats['pnl']:.2f}"
        )
        self.telegram.send(msg)
    
    def send_daily_summary(self, stats: Dict):
        """Send daily trading summary"""
        msg = (
            f"<b>DAILY SUMMARY</b>\n"
            f"Date: {datetime.now().strftime('%Y-%m-%d')}\n"
            f"\n"
            f"Total Trades: {stats.get('total_trades', 0)}\n"
            f"Win Rate: {stats.get('win_rate', 0)}%\n"
            f"Profit Factor: {stats.get('profit_factor', 0)}\n"
            f"Total P&L: ${stats.get('total_pnl', 0)}\n"
            f"Balance: ${stats.get('balance', 0)}\n"
            f"Return: {stats.get('return_pct', 0)}%"
        )
        self.telegram.send(msg)
    
    def send_error(self, error_msg: str):
        """Send error alert"""
        msg = f"<b>ERROR</b>\n{error_msg}"
        self.telegram.send(msg)
    
    def send_startup(self, symbols: list, balance: float):
        """Send startup notification"""
        msg = (
            f"<b>PAPER TRADING STARTED</b>\n"
            f"Symbols: {', '.join(symbols)}\n"
            f"Balance: ${balance:.2f}\n"
            f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        self.telegram.send(msg)


class ConsoleAlert:
    """Console-based alerts (fallback when Telegram not configured)"""
    
    def __init__(self):
        pass
    
    def on_signal(self, signal: Dict):
        if signal.get('signal') in ['BUY', 'SELL']:
            print(f"\n*** SIGNAL: {signal['symbol']} {signal['signal']} @ ${signal.get('price', 0):.2f} ***\n")
    
    def on_trade_open(self, data: Dict):
        print(f"\n>>> OPENED {data['direction']} {data['symbol']} @ ${data['entry_price']:.2f}")
    
    def on_trade_close(self, data: Dict):
        pnl = data['pnl']
        emoji = "+" if pnl >= 0 else ""
        print(f"\n<<< CLOSED {data['symbol']} | {data['reason']} | P&L: {emoji}${pnl:.2f}")


if __name__ == "__main__":
    # Test alerts
    alert = AlertManager()
    
    # Test signal
    alert.on_signal({
        "symbol": "BTCUSDT",
        "signal": "BUY",
        "price": 42000.0,
        "conviction": 0.7
    })
    
    # Test trade open
    alert.on_trade_open({
        "symbol": "BTCUSDT",
        "direction": "BUY",
        "entry_price": 42000.0,
        "margin": 35.0,
        "leverage": 20
    })
    
    # Test trade close
    alert.on_trade_close({
        "symbol": "BTCUSDT",
        "direction": "BUY",
        "exit_price": 42600.0,
        "pnl": 25.50,
        "reason": "TP"
    })
    
    print("\nAlert test complete!")
