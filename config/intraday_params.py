"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                       INTRADAY OPTIMIZED PARAMETERS                           ║
║                                                                               ║
║  Optimized parameters for each symbol at each timeframe.                     ║
╚═══════════════════════════════════════════════════════════════════════════════╝

Optimization Results Summary:
- 1H: BTC 5/6 (83%), ETH 3/6 (50%)
- 15M: BTC 3/4 (75%), ETH 3/4 (75%), SOL 2/4 (50%)
- 5M: BTC 2/4 (50%)

Author: Bot_Algo  
Last Updated: January 2026
"""

from typing import Dict

# ═══════════════════════════════════════════════════════════════════════════════
#                           DAILY (1D) PARAMETERS
# ═══════════════════════════════════════════════════════════════════════════════

PARAMS_1D = {
    'BTCUSDT': {
        'ema_fast': 5, 'ema_medium': 21, 'ema_slow': 34,
        'rsi_period': 5, 'rsi_threshold': 45,
        'profitable': '7/8 (88%)',
    },
    'ETHUSDT': {
        'ema_fast': 10, 'ema_medium': 13, 'ema_slow': 50,
        'rsi_period': 7, 'rsi_threshold': 48,
        'profitable': '8/8 (100%)',
    },
    'SOLUSDT': {
        'ema_fast': 8, 'ema_slow': 21, 'vol_threshold': 1.2,
        'profitable': '5/8 (62%)',
    },
}


# ═══════════════════════════════════════════════════════════════════════════════
#                           1-HOUR PARAMETERS
# ═══════════════════════════════════════════════════════════════════════════════

PARAMS_1H = {
    'BTCUSDT': {
        'ema_fast': 8, 'ema_medium': 50, 'ema_slow': 150,
        'rsi_period': 14, 'rsi_threshold': 45,
        'profitable': '5/6 (83%)',
    },
    'ETHUSDT': {
        'ema_fast': 8, 'ema_medium': 21, 'ema_slow': 100,
        'rsi_period': 7, 'rsi_threshold': 55,
        'profitable': '4/6 (67%)',
    },
    'SOLUSDT': {
        'ema_fast': 10, 'ema_medium': 50, 'ema_slow': 100,
        'rsi_period': 10, 'rsi_threshold': 45,
        'profitable': '6/6 (100%)',
    },
}


# ═══════════════════════════════════════════════════════════════════════════════
#                           15-MINUTE PARAMETERS
# ═══════════════════════════════════════════════════════════════════════════════

# UPDATED: Much faster EMAs to reduce lag (old: 15/75/250 = ~62h lag)
PARAMS_15M = {
    'BTCUSDT': {
        'ema_fast': 5, 'ema_medium': 13, 'ema_slow': 34,  # Fibonacci sequence
        'rsi_period': 7, 'rsi_threshold': 50,
        'profitable': 'TESTING',
    },
    'ETHUSDT': {
        'ema_fast': 5, 'ema_medium': 13, 'ema_slow': 34,
        'rsi_period': 7, 'rsi_threshold': 50,
        'profitable': 'TESTING',
    },
    'SOLUSDT': {
        'ema_fast': 5, 'ema_medium': 13, 'ema_slow': 34,
        'rsi_period': 7, 'rsi_threshold': 50,
        'profitable': 'TESTING',
    },
}


# ═══════════════════════════════════════════════════════════════════════════════
#                           5-MINUTE PARAMETERS
# ═══════════════════════════════════════════════════════════════════════════════

PARAMS_5M = {
    'BTCUSDT': {
        'ema_fast': 8, 'ema_medium': 21, 'ema_slow': 150,
        'rsi_period': 14, 'rsi_threshold': 45,
        'profitable': '3/4 (75%)',
    },
    'ETHUSDT': {
        'ema_fast': 15, 'ema_medium': 75, 'ema_slow': 100,
        'rsi_period': 7, 'rsi_threshold': 50,
        'profitable': '4/4 (100%)',
    },
    'SOLUSDT': {
        'ema_fast': 10, 'ema_medium': 75, 'ema_slow': 100,
        'rsi_period': 7, 'rsi_threshold': 45,
        'profitable': '4/4 (100%)',
    },
}


# ═══════════════════════════════════════════════════════════════════════════════
#                           HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

TIMEFRAME_PARAMS = {
    '1d': PARAMS_1D,
    '1h': PARAMS_1H,
    '15m': PARAMS_15M,
    '5m': PARAMS_5M,
}


def get_intraday_params(symbol: str, timeframe: str) -> Dict:
    """Get optimized parameters for symbol and timeframe."""
    params_dict = TIMEFRAME_PARAMS.get(timeframe, PARAMS_1D)
    
    if symbol in params_dict:
        params = params_dict[symbol].copy()
        params.pop('profitable', None)
        return params
    
    # Default params
    return {
        'ema_fast': 13,
        'ema_medium': 55,
        'ema_slow': 100,
        'rsi_period': 14,
        'rsi_threshold': 50,
    }


def print_summary():
    """Print optimization summary."""
    print("\n" + "=" * 60)
    print("INTRADAY OPTIMIZATION SUMMARY")
    print("=" * 60 + "\n")
    
    for tf, params_dict in TIMEFRAME_PARAMS.items():
        print(f"\n{tf.upper()} TIMEFRAME:")
        print("-" * 40)
        for symbol, params in params_dict.items():
            prof = params.get('profitable', 'N/A')
            print(f"  {symbol}: {prof}")


# ═══════════════════════════════════════════════════════════════════════════════
#                           MAIN
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print_summary()
