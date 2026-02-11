"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                       TIMEFRAME CONFIGURATION                                 ║
║                                                                               ║
║  Configuration for multi-timeframe trading (5m, 15m, 1h, 1d).                ║
║  Each timeframe has different test periods and parameter adjustments.         ║
╚═══════════════════════════════════════════════════════════════════════════════╝

Author: Bot_Algo
Last Updated: January 2026
"""

from dataclasses import dataclass
from typing import Dict, List
from datetime import datetime, timedelta


# ═══════════════════════════════════════════════════════════════════════════════
#                           TIMEFRAME CONFIGS
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class TimeframeConfig:
    """Configuration for a specific timeframe."""
    interval: str           # Binance interval: '1m', '5m', '15m', '1h', '1d'
    name: str              # Display name
    candles_per_day: int   # Number of candles per day
    lookback_days: int     # Max days of data available (Binance limits)
    test_periods_days: int # Duration of each test period
    ema_multiplier: float  # Multiply daily EMA params by this
    trades_per_day_target: int  # Expected trades per day


TIMEFRAME_CONFIGS = {
    '5m': TimeframeConfig(
        interval='5m',
        name='5-Minute',
        candles_per_day=288,      # 24*60/5
        lookback_days=30,          # ~8000 candles max
        test_periods_days=7,       # 1 week test periods
        ema_multiplier=12.0,       # Fast EMAs for 5m
        trades_per_day_target=5,
    ),
    '15m': TimeframeConfig(
        interval='15m',
        name='15-Minute',
        candles_per_day=96,        # 24*60/15
        lookback_days=60,          # ~5760 candles max
        test_periods_days=14,      # 2 week test periods
        ema_multiplier=6.0,        # Medium EMAs for 15m
        trades_per_day_target=3,
    ),
    '1h': TimeframeConfig(
        interval='1h',
        name='1-Hour',
        candles_per_day=24,
        lookback_days=180,         # ~4320 candles max
        test_periods_days=30,      # 1 month test periods
        ema_multiplier=1.5,        # Slightly faster for 1h
        trades_per_day_target=1,
    ),
    '4h': TimeframeConfig(
        interval='4h',
        name='4-Hour',
        candles_per_day=6,
        lookback_days=365,
        test_periods_days=60,
        ema_multiplier=1.0,        # Same as daily
        trades_per_day_target=0.5,
    ),
    '1d': TimeframeConfig(
        interval='1d',
        name='Daily',
        candles_per_day=1,
        lookback_days=1000,
        test_periods_days=90,      # 3 month test periods
        ema_multiplier=1.0,
        trades_per_day_target=0.2,
    ),
}


# ═══════════════════════════════════════════════════════════════════════════════
#                           INTRADAY TEST PERIODS
# ═══════════════════════════════════════════════════════════════════════════════

# Test periods for intraday timeframes (recent data only)
# Format: (name, start_date, end_date, market_type)

INTRADAY_TEST_PERIODS = [
    # Recent periods (within Binance kline history limits)
    ("Q4 2024 Range", "2024-10-01", "2024-10-31", "choppy"),
    ("Nov 2024 Bull", "2024-11-01", "2024-11-30", "trending"),
    ("Dec 2024 Consolidation", "2024-12-01", "2024-12-31", "choppy"),
    ("Jan 2025 Start", "2025-01-01", "2025-01-31", "volatile"),
    # Extend as needed for more recent periods
]

# For 1h and 4h, we can use older periods too
HOURLY_TEST_PERIODS = [
    ("Sep 2024 Pre-Rally", "2024-09-01", "2024-09-30", "choppy"),
    ("Q4 2024 Range", "2024-10-01", "2024-10-31", "choppy"),
    ("Nov 2024 Bull", "2024-11-01", "2024-11-30", "trending"),
    ("Dec 2024 Consolidation", "2024-12-01", "2024-12-31", "choppy"),
    ("BTC ETF Anniversary", "2025-01-01", "2025-01-31", "volatile"),
    ("Early 2025", "2025-02-01", "2025-02-28", "choppy"),
]


# ═══════════════════════════════════════════════════════════════════════════════
#                           PARAM SCALING
# ═══════════════════════════════════════════════════════════════════════════════

def scale_params_for_timeframe(daily_params: Dict, timeframe: str) -> Dict:
    """
    Scale daily parameters for a different timeframe.
    
    For faster timeframes:
    - Multiply EMA periods by multiplier
    - RSI stays the same (momentum is relative)
    - Thresholds stay the same
    """
    if timeframe not in TIMEFRAME_CONFIGS:
        return daily_params
    
    config = TIMEFRAME_CONFIGS[timeframe]
    mult = config.ema_multiplier
    
    scaled = daily_params.copy()
    
    # Scale EMA periods (round to int)
    for key in ['ema_fast', 'ema_medium', 'ema_slow']:
        if key in scaled:
            scaled[key] = max(3, int(scaled[key] * mult))
    
    # RSI period scales slightly
    if 'rsi_period' in scaled:
        scaled['rsi_period'] = max(3, int(scaled['rsi_period'] * (mult ** 0.5)))
    
    return scaled


def get_default_params(timeframe: str) -> Dict:
    """Get default parameters for a timeframe."""
    base = {
        'ema_fast': 8,
        'ema_medium': 21,
        'ema_slow': 50,
        'rsi_period': 7,
        'rsi_threshold': 50,
    }
    return scale_params_for_timeframe(base, timeframe)


# ═══════════════════════════════════════════════════════════════════════════════
#                           MAIN
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 60)
    print("TIMEFRAME CONFIGURATIONS")
    print("=" * 60 + "\n")
    
    for tf, config in TIMEFRAME_CONFIGS.items():
        print(f"{config.name} ({tf})")
        print(f"  Candles/Day: {config.candles_per_day}")
        print(f"  Lookback: {config.lookback_days} days")
        print(f"  EMA Multiplier: {config.ema_multiplier}x")
        
        params = get_default_params(tf)
        print(f"  Default EMAs: {params['ema_fast']}/{params['ema_medium']}/{params['ema_slow']}")
        print()
