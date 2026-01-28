"""
Live Trading Module
===================
Components for real-time paper and live trading.

Modules:
    - data_feed: Binance WebSocket/polling data ingestion
    - signal_engine: Real-time signal generation
    - paper_trader: Virtual position tracking
    - dashboard: Console monitoring
    - alerts: Telegram notifications
    - run_paper: Main paper trading runner
"""

from .data_feed import SimulatedDataFeed, BinanceDataFeed, CandleBuffer
from .signal_engine import SignalEngine, IndicatorCalculator
from .paper_trader import PaperTrader, Position, Trade
from .dashboard import DashboardManager, SimpleDashboard
from .alerts import AlertManager, TelegramAlert

__all__ = [
    'SimulatedDataFeed',
    'BinanceDataFeed',
    'CandleBuffer',
    'SignalEngine',
    'IndicatorCalculator',
    'PaperTrader',
    'Position',
    'Trade',
    'DashboardManager',
    'SimpleDashboard',
    'AlertManager',
    'TelegramAlert'
]
