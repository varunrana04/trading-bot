"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                       TELEGRAM SIGNAL BOT                                     ║
║                                                                               ║
║  Real-time trading signal notifications via Telegram.                         ║
║  Sends alerts for entries, exits, P&L updates, and daily summaries.          ║
╚═══════════════════════════════════════════════════════════════════════════════╝

Setup:
1. Create bot via @BotFather on Telegram
2. Get your chat ID via @userinfobot
3. Set environment variables:
   - TELEGRAM_BOT_TOKEN
   - TELEGRAM_CHAT_ID

Author: Bot_Algo
Last Updated: January 2026
"""

import os
import json
import logging
import asyncio
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass
from enum import Enum
import urllib.request
import urllib.parse

logger = logging.getLogger("TelegramBot")


# ═══════════════════════════════════════════════════════════════════════════════
#                           CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class TelegramConfig:
    """Telegram bot configuration."""
    bot_token: str = ""
    chat_id: str = ""
    send_entries: bool = True
    send_exits: bool = True
    send_daily_summary: bool = True
    send_errors: bool = True
    quiet_hours: tuple = (22, 7)  # Don't disturb between 10 PM - 7 AM
    

class AlertType(Enum):
    """Types of trading alerts."""
    ENTRY = "ENTRY"
    EXIT = "EXIT"
    STOP_LOSS = "STOP_LOSS"
    TAKE_PROFIT = "TAKE_PROFIT"
    WARNING = "WARNING"
    ERROR = "ERROR"
    SUMMARY = "SUMMARY"
    INFO = "INFO"


# ═══════════════════════════════════════════════════════════════════════════════
#                           TELEGRAM BOT
# ═══════════════════════════════════════════════════════════════════════════════

class TelegramBot:
    """
    Telegram bot for trading signals.
    
    Usage:
        bot = TelegramBot()
        
        # Send trade entry
        await bot.send_trade_alert(
            symbol='BTCUSDT',
            alert_type=AlertType.ENTRY,
            direction='LONG',
            entry_price=45000,
            stop_loss=43000,
            take_profit=48000
        )
        
        # Send daily summary
        await bot.send_daily_summary(pnl=150.00, pnl_pct=1.5)
    """
    
    def __init__(self, config: TelegramConfig = None):
        self.config = config or TelegramConfig(
            bot_token=os.getenv('TELEGRAM_BOT_TOKEN', ''),
            chat_id=os.getenv('TELEGRAM_CHAT_ID', '')
        )
        
        self.base_url = f"https://api.telegram.org/bot{self.config.bot_token}"
        self.enabled = bool(self.config.bot_token and self.config.chat_id)
        
        if not self.enabled:
            logger.warning("Telegram bot not configured. Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID")
    
    def _is_quiet_hours(self) -> bool:
        """Check if current time is in quiet hours."""
        current_hour = datetime.now().hour
        start, end = self.config.quiet_hours
        if start > end:
            return current_hour >= start or current_hour < end
        return start <= current_hour < end
    
    def _send_message(self, text: str, parse_mode: str = "HTML") -> bool:
        """Send message via Telegram API."""
        if not self.enabled:
            logger.info(f"[TELEGRAM DISABLED] {text[:100]}...")
            return False
        
        try:
            url = f"{self.base_url}/sendMessage"
            data = {
                'chat_id': self.config.chat_id,
                'text': text,
                'parse_mode': parse_mode,
                'disable_notification': self._is_quiet_hours()
            }
            
            encoded_data = urllib.parse.urlencode(data).encode('utf-8')
            req = urllib.request.Request(url, data=encoded_data, method='POST')
            
            with urllib.request.urlopen(req, timeout=10) as response:
                result = json.loads(response.read().decode('utf-8'))
                if result.get('ok'):
                    logger.info(f"Telegram message sent successfully")
                    return True
                else:
                    logger.error(f"Telegram API error: {result}")
                    return False
                    
        except Exception as e:
            logger.error(f"Failed to send Telegram message: {e}")
            return False
    
    def send_trade_alert(
        self,
        symbol: str,
        alert_type: AlertType,
        direction: str = "",
        entry_price: float = 0,
        exit_price: float = 0,
        stop_loss: float = 0,
        take_profit: float = 0,
        quantity: float = 0,
        pnl: float = 0,
        strategy: str = ""
    ) -> bool:
        """
        Send trading alert.
        
        Args:
            symbol: Trading symbol
            alert_type: Type of alert
            direction: LONG or SHORT
            entry_price: Entry price
            exit_price: Exit price (for exits)
            stop_loss: Stop loss price
            take_profit: Take profit price
            quantity: Position quantity
            pnl: Realized P&L (for exits)
            strategy: Strategy name
        """
        emoji = {
            AlertType.ENTRY: "🟢",
            AlertType.EXIT: "🔵",
            AlertType.STOP_LOSS: "🔴",
            AlertType.TAKE_PROFIT: "💰",
            AlertType.WARNING: "⚠️",
            AlertType.ERROR: "❌",
            AlertType.SUMMARY: "📊",
            AlertType.INFO: "ℹ️"
        }
        
        icon = emoji.get(alert_type, "📣")
        
        if alert_type == AlertType.ENTRY:
            message = f"""
{icon} <b>{alert_type.value}: {symbol}</b>

Direction: <b>{direction}</b>
Entry Price: <code>${entry_price:,.2f}</code>
Quantity: <code>{quantity}</code>
Stop Loss: <code>${stop_loss:,.2f}</code>
Take Profit: <code>${take_profit:,.2f}</code>

Strategy: {strategy}
Time: {datetime.now().strftime('%H:%M:%S')}
"""
        elif alert_type in [AlertType.EXIT, AlertType.STOP_LOSS, AlertType.TAKE_PROFIT]:
            pnl_icon = "✅" if pnl > 0 else "❌"
            message = f"""
{icon} <b>{alert_type.value}: {symbol}</b>

Direction: <b>{direction}</b>
Entry: <code>${entry_price:,.2f}</code>
Exit: <code>${exit_price:,.2f}</code>
P&L: {pnl_icon} <code>${pnl:,.2f}</code>

Strategy: {strategy}
Time: {datetime.now().strftime('%H:%M:%S')}
"""
        else:
            message = f"""
{icon} <b>{alert_type.value}: {symbol}</b>

{strategy}

Time: {datetime.now().strftime('%H:%M:%S')}
"""
        
        return self._send_message(message.strip())
    
    def send_daily_summary(
        self,
        date: str = None,
        pnl: float = 0,
        pnl_pct: float = 0,
        num_trades: int = 0,
        wins: int = 0,
        losses: int = 0,
        positions: List[Dict] = None
    ) -> bool:
        """Send daily P&L summary."""
        date = date or datetime.now().strftime('%Y-%m-%d')
        win_rate = wins / num_trades * 100 if num_trades > 0 else 0
        
        pnl_icon = "📈" if pnl >= 0 else "📉"
        
        message = f"""
📊 <b>DAILY SUMMARY: {date}</b>

{pnl_icon} P&L: <code>${pnl:,.2f}</code> ({pnl_pct:+.2f}%)

Trades: {num_trades}
Wins: {wins} | Losses: {losses}
Win Rate: {win_rate:.1f}%
"""
        
        if positions:
            message += "\n<b>Open Positions:</b>"
            for pos in positions:
                message += f"\n  • {pos.get('symbol')}: {pos.get('side')} @ ${pos.get('entry_price'):,.2f}"
        
        return self._send_message(message.strip())
    
    def send_error(self, error_message: str, context: str = "") -> bool:
        """Send error notification."""
        message = f"""
❌ <b>ERROR</b>

{error_message}

Context: {context}
Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        return self._send_message(message.strip())
    
    def send_startup(self, balance: float = 0, strategies: List[str] = None) -> bool:
        """Send bot startup notification."""
        strategies = strategies or []
        
        message = f"""
🚀 <b>BOT STARTED</b>

Balance: <code>${balance:,.2f}</code>
Strategies: {', '.join(strategies) if strategies else 'None'}
Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        return self._send_message(message.strip())


# ═══════════════════════════════════════════════════════════════════════════════
#                           SIGNAL FORMATTER
# ═══════════════════════════════════════════════════════════════════════════════

class SignalFormatter:
    """
    Formats trading signals for display.
    Works with console and Telegram output.
    """
    
    @staticmethod
    def format_entry(
        symbol: str,
        direction: str,
        entry_price: float,
        stop_loss: float,
        take_profit: float,
        quantity: float = 1.0,
        strategy: str = ""
    ) -> str:
        """Format entry signal."""
        risk = abs(entry_price - stop_loss) / entry_price * 100
        reward = abs(take_profit - entry_price) / entry_price * 100
        rr_ratio = reward / risk if risk > 0 else 0
        
        return f"""
+========================================+
|  {direction:^36}  |
+========================================+
  Symbol:      {symbol}
  Entry:       ${entry_price:,.2f}
  Stop Loss:   ${stop_loss:,.2f} ({risk:.2f}%)
  Take Profit: ${take_profit:,.2f} ({reward:.2f}%)
  R:R Ratio:   1:{rr_ratio:.1f}
  Quantity:    {quantity}
  Strategy:    {strategy}
+========================================+
"""
    
    @staticmethod
    def format_exit(
        symbol: str,
        direction: str,
        entry_price: float,
        exit_price: float,
        pnl: float,
        pnl_pct: float,
        reason: str = ""
    ) -> str:
        """Format exit signal."""
        result = "WIN" if pnl > 0 else "LOSS"
        
        return f"""
+========================================+
|  EXIT - {result:^28}  |
+========================================+
  Symbol:   {symbol}
  Entry:    ${entry_price:,.2f}
  Exit:     ${exit_price:,.2f}
  P&L:      ${pnl:,.2f} ({pnl_pct:+.2f}%)
  Reason:   {reason}
+========================================+
"""


# ═══════════════════════════════════════════════════════════════════════════════
#                           MAIN (Demo)
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    print("=" * 60)
    print("TELEGRAM SIGNAL BOT - DEMO")
    print("=" * 60)
    
    # Create bot (will be disabled without tokens)
    bot = TelegramBot()
    
    print(f"\nBot Enabled: {bot.enabled}")
    
    if not bot.enabled:
        print("\nTo enable Telegram notifications, set:")
        print("  TELEGRAM_BOT_TOKEN=your_bot_token")
        print("  TELEGRAM_CHAT_ID=your_chat_id")
    
    # Demo signal formatting
    formatter = SignalFormatter()
    
    print("\n--- Entry Signal Demo ---")
    entry = formatter.format_entry(
        symbol='BTCUSDT',
        direction='LONG',
        entry_price=45000,
        stop_loss=43000,
        take_profit=48000,
        quantity=0.01,
        strategy='trend_follower_v2'
    )
    print(entry)
    
    print("--- Exit Signal Demo ---")
    exit_signal = formatter.format_exit(
        symbol='BTCUSDT',
        direction='LONG',
        entry_price=45000,
        exit_price=47500,
        pnl=25.00,
        pnl_pct=5.56,
        reason='take_profit'
    )
    print(exit_signal)
    
    # Send test message (only if enabled)
    if bot.enabled:
        bot.send_startup(balance=1000, strategies=['trend_follower_v2', 'mean_reversion'])
    
    print("\n" + "=" * 60)
