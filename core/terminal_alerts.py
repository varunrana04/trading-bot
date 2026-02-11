"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                       TERMINAL ALERTS                                         ║
║                                                                               ║
║  Rich terminal formatting with colors for Windows CMD/PowerShell.             ║
║  Falls back to plain text if colors not supported.                            ║
╚═══════════════════════════════════════════════════════════════════════════════╝

Author: Bot_Algo
Last Updated: January 2026
"""

import os
import sys
from datetime import datetime
from typing import Optional
from enum import Enum


# ═══════════════════════════════════════════════════════════════════════════════
#                           COLOR SUPPORT
# ═══════════════════════════════════════════════════════════════════════════════

# Enable ANSI colors on Windows
if sys.platform == 'win32':
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
        COLORS_ENABLED = True
    except Exception:
        COLORS_ENABLED = False
else:
    COLORS_ENABLED = True


class Color:
    """ANSI color codes."""
    RESET = '\033[0m' if COLORS_ENABLED else ''
    BOLD = '\033[1m' if COLORS_ENABLED else ''
    DIM = '\033[2m' if COLORS_ENABLED else ''
    
    # Colors
    RED = '\033[91m' if COLORS_ENABLED else ''
    GREEN = '\033[92m' if COLORS_ENABLED else ''
    YELLOW = '\033[93m' if COLORS_ENABLED else ''
    BLUE = '\033[94m' if COLORS_ENABLED else ''
    MAGENTA = '\033[95m' if COLORS_ENABLED else ''
    CYAN = '\033[96m' if COLORS_ENABLED else ''
    WHITE = '\033[97m' if COLORS_ENABLED else ''
    
    # Backgrounds
    BG_RED = '\033[41m' if COLORS_ENABLED else ''
    BG_GREEN = '\033[42m' if COLORS_ENABLED else ''
    BG_YELLOW = '\033[43m' if COLORS_ENABLED else ''
    BG_BLUE = '\033[44m' if COLORS_ENABLED else ''


class AlertType(Enum):
    """Alert types with associated colors."""
    ENTRY_LONG = ('LONG ENTRY', Color.GREEN, Color.BG_GREEN)
    ENTRY_SHORT = ('SHORT ENTRY', Color.RED, Color.BG_RED)
    EXIT_WIN = ('EXIT - WIN', Color.GREEN, Color.BG_GREEN)
    EXIT_LOSS = ('EXIT - LOSS', Color.RED, Color.BG_RED)
    STOP_LOSS = ('STOP LOSS', Color.RED, Color.BG_RED)
    TAKE_PROFIT = ('TAKE PROFIT', Color.GREEN, Color.BG_GREEN)
    WARNING = ('WARNING', Color.YELLOW, Color.BG_YELLOW)
    INFO = ('INFO', Color.CYAN, Color.BG_BLUE)
    SIGNAL = ('SIGNAL', Color.MAGENTA, Color.BG_BLUE)


# ═══════════════════════════════════════════════════════════════════════════════
#                           TERMINAL FORMATTER
# ═══════════════════════════════════════════════════════════════════════════════

class TerminalAlert:
    """
    Rich terminal alerts for trading signals.
    
    Usage:
        alert = TerminalAlert()
        
        alert.entry(
            symbol='BTCUSDT',
            direction='LONG',
            price=45000,
            stop_loss=43000,
            take_profit=48000
        )
        
        alert.exit(
            symbol='BTCUSDT',
            direction='LONG',
            entry_price=45000,
            exit_price=47500,
            pnl=25.00
        )
    """
    
    def __init__(self, width: int = 50):
        self.width = width
    
    def _line(self, char: str = '=') -> str:
        """Create a horizontal line."""
        return char * self.width
    
    def _center(self, text: str, color: str = '') -> str:
        """Center text with optional color."""
        padded = text.center(self.width - 4)
        return f"{color}| {padded} |{Color.RESET}"
    
    def _row(self, label: str, value: str, color: str = '') -> str:
        """Create a label-value row."""
        label_width = 14
        value_str = f"{value}"
        return f"  {color}{label:<{label_width}}{Color.RESET} {value_str}"
    
    def _header(self, alert_type: AlertType) -> str:
        """Create colored header."""
        title, fg, bg = alert_type.value
        return f"""
{Color.BOLD}{self._line()}{Color.RESET}
{bg}{Color.WHITE}{Color.BOLD}  {title.center(self.width - 4)}  {Color.RESET}
{Color.BOLD}{self._line()}{Color.RESET}"""
    
    def _footer(self) -> str:
        """Create footer."""
        return f"{Color.DIM}{self._line()}{Color.RESET}"
    
    def _timestamp(self) -> str:
        """Get current timestamp."""
        return datetime.now().strftime('%H:%M:%S')
    
    # ═══════════════════════════════════════════════════════════════════════════
    #                           ALERTS
    # ═══════════════════════════════════════════════════════════════════════════
    
    def entry(
        self,
        symbol: str,
        direction: str,
        price: float,
        stop_loss: float,
        take_profit: float,
        quantity: float = 0,
        strategy: str = '',
        regime: str = ''
    ):
        """Display entry alert."""
        alert_type = AlertType.ENTRY_LONG if direction.upper() == 'LONG' else AlertType.ENTRY_SHORT
        color = Color.GREEN if direction.upper() == 'LONG' else Color.RED
        
        risk_pct = abs(price - stop_loss) / price * 100
        reward_pct = abs(take_profit - price) / price * 100
        rr = reward_pct / risk_pct if risk_pct > 0 else 0
        
        print(self._header(alert_type))
        print(self._row('Symbol', f"{Color.BOLD}{symbol}{Color.RESET}"))
        print(self._row('Direction', f"{color}{Color.BOLD}{direction.upper()}{Color.RESET}"))
        print(self._row('Entry', f"${price:,.2f}"))
        print(self._row('Stop Loss', f"${stop_loss:,.2f} ({Color.RED}-{risk_pct:.1f}%{Color.RESET})"))
        print(self._row('Take Profit', f"${take_profit:,.2f} ({Color.GREEN}+{reward_pct:.1f}%{Color.RESET})"))
        print(self._row('R:R Ratio', f"{Color.CYAN}1:{rr:.1f}{Color.RESET}"))
        if quantity > 0:
            print(self._row('Quantity', f"{quantity:.6f}"))
        if strategy:
            print(self._row('Strategy', f"{Color.MAGENTA}{strategy}{Color.RESET}"))
        if regime:
            print(self._row('Regime', f"{Color.YELLOW}{regime}{Color.RESET}"))
        print(self._row('Time', self._timestamp()))
        print(self._footer())
    
    def exit(
        self,
        symbol: str,
        direction: str,
        entry_price: float,
        exit_price: float,
        pnl: float,
        pnl_pct: float = 0,
        reason: str = ''
    ):
        """Display exit alert."""
        is_win = pnl > 0
        alert_type = AlertType.EXIT_WIN if is_win else AlertType.EXIT_LOSS
        
        if 'stop' in reason.lower():
            alert_type = AlertType.STOP_LOSS
        elif 'profit' in reason.lower() or 'take' in reason.lower():
            alert_type = AlertType.TAKE_PROFIT
        
        pnl_color = Color.GREEN if is_win else Color.RED
        
        print(self._header(alert_type))
        print(self._row('Symbol', f"{Color.BOLD}{symbol}{Color.RESET}"))
        print(self._row('Direction', direction.upper()))
        print(self._row('Entry', f"${entry_price:,.2f}"))
        print(self._row('Exit', f"${exit_price:,.2f}"))
        print(self._row('P&L', f"{pnl_color}{Color.BOLD}${pnl:+,.2f}{Color.RESET} ({pnl_pct:+.2f}%)"))
        if reason:
            print(self._row('Reason', reason))
        print(self._row('Time', self._timestamp()))
        print(self._footer())
    
    def signal(
        self,
        symbol: str,
        signal: int,
        price: float,
        regime: str = '',
        confidence: float = 0
    ):
        """Display signal update."""
        if signal == 0:
            direction = 'FLAT'
            color = Color.YELLOW
        elif signal == 1:
            direction = 'LONG'
            color = Color.GREEN
        else:
            direction = 'SHORT'
            color = Color.RED
        
        line = f"{Color.DIM}[{self._timestamp()}]{Color.RESET} "
        line += f"{Color.BOLD}{symbol}{Color.RESET} "
        line += f"${price:,.2f} "
        line += f"| Signal: {color}{Color.BOLD}{direction}{Color.RESET}"
        if regime:
            line += f" | Regime: {Color.YELLOW}{regime}{Color.RESET}"
        if confidence > 0:
            line += f" | Conf: {confidence:.0f}%"
        
        print(line)
    
    def status(
        self,
        equity: float,
        pnl: float,
        pnl_pct: float,
        positions: int = 0,
        trades_today: int = 0
    ):
        """Display status bar."""
        pnl_color = Color.GREEN if pnl >= 0 else Color.RED
        
        print(f"\n{Color.DIM}{self._line('-')}{Color.RESET}")
        line = f"  Equity: {Color.BOLD}${equity:,.2f}{Color.RESET}"
        line += f"  |  P&L: {pnl_color}${pnl:+,.2f}{Color.RESET} ({pnl_pct:+.2f}%)"
        line += f"  |  Positions: {positions}"
        line += f"  |  Trades: {trades_today}"
        print(line)
        print(f"{Color.DIM}{self._line('-')}{Color.RESET}\n")
    
    def warning(self, message: str):
        """Display warning."""
        print(f"{Color.YELLOW}{Color.BOLD}[WARNING]{Color.RESET} {message}")
    
    def error(self, message: str):
        """Display error."""
        print(f"{Color.RED}{Color.BOLD}[ERROR]{Color.RESET} {message}")
    
    def info(self, message: str):
        """Display info."""
        print(f"{Color.CYAN}[INFO]{Color.RESET} {message}")
    
    def success(self, message: str):
        """Display success."""
        print(f"{Color.GREEN}{Color.BOLD}[OK]{Color.RESET} {message}")


# ═══════════════════════════════════════════════════════════════════════════════
#                           STARTUP BANNER
# ═══════════════════════════════════════════════════════════════════════════════

def print_banner(
    symbol: str = 'BTCUSDT',
    capital: float = 1000,
    strategies: list = None
):
    """Print startup banner."""
    strategies = strategies or ['trend_follower']
    
    print(f"""
{Color.CYAN}{Color.BOLD}
 ____        _      _    _             
| __ )  ___ | |_   / \\  | | __ _  ___  
|  _ \\ / _ \\| __| / _ \\ | |/ _` |/ _ \\ 
| |_) | (_) | |_ / ___ \\| | (_| | (_) |
|____/ \\___/ \\__/_/   \\_\\_|\\__, |\\___/ 
                          |___/        
{Color.RESET}
{Color.DIM}Algorithmic Trading System v1.0{Color.RESET}
{Color.DIM}{'=' * 40}{Color.RESET}

  Symbol:     {Color.BOLD}{symbol}{Color.RESET}
  Capital:    {Color.GREEN}${capital:,.2f}{Color.RESET}
  Strategies: {Color.MAGENTA}{', '.join(strategies)}{Color.RESET}
  Started:    {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

{Color.DIM}{'=' * 40}{Color.RESET}
""")


# ═══════════════════════════════════════════════════════════════════════════════
#                           MAIN (Demo)
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print_banner('BTCUSDT', 1000, ['trend_follower_v2', 'mean_reversion'])
    
    alert = TerminalAlert()
    
    print("\n--- Entry Alert Demo ---")
    alert.entry(
        symbol='BTCUSDT',
        direction='LONG',
        price=45000,
        stop_loss=43000,
        take_profit=48000,
        quantity=0.01,
        strategy='trend_follower_v2',
        regime='strong_trend_up'
    )
    
    print("\n--- Signal Updates ---")
    alert.signal('BTCUSDT', 1, 45100, 'strong_trend_up', 85)
    alert.signal('BTCUSDT', 0, 45200, 'ranging', 50)
    alert.signal('BTCUSDT', -1, 45050, 'strong_trend_down', 90)
    
    print("\n--- Exit Alert Demo ---")
    alert.exit(
        symbol='BTCUSDT',
        direction='LONG',
        entry_price=45000,
        exit_price=47500,
        pnl=25.00,
        pnl_pct=5.56,
        reason='take_profit'
    )
    
    print("\n--- Status Bar Demo ---")
    alert.status(
        equity=1025.50,
        pnl=25.50,
        pnl_pct=2.55,
        positions=1,
        trades_today=3
    )
    
    print("--- Messages ---")
    alert.info("Market data connected")
    alert.success("Strategy initialized")
    alert.warning("High volatility detected")
    alert.error("Connection timeout")
