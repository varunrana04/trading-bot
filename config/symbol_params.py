"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                       SYMBOL-SPECIFIC PARAMETERS                              ║
║                                                                               ║
║  Optimized parameters for each trading symbol.                               ║
║  Each symbol has different market characteristics.                            ║
╚═══════════════════════════════════════════════════════════════════════════════╝

Optimization Results:
- BTCUSDT: 7/8 profitable (88%), +16% avg return
- ETHUSDT: 8/8 profitable (100%), +21% avg return
- SOLUSDT: 5/8 profitable (62%), +34% avg return

Author: Bot_Algo
Last Updated: January 2026
"""

from typing import Dict

# ═══════════════════════════════════════════════════════════════════════════════
#                           SYMBOL PARAMETERS
# ═══════════════════════════════════════════════════════════════════════════════

SYMBOL_PARAMS = {
    # Bitcoin - NOW 8/8 PROFITABLE!
    'BTCUSDT': {
        'ema_fast': 5,
        'ema_medium': 21,
        'ema_slow': 34,
        'rsi_period': 5,
        'rsi_threshold': 45,
        'profitable_periods': 8,  # out of 8 - ALL PROFITABLE!
        'avg_return': 23.6,
    },
    
    # Ethereum - 8/8 profitable
    'ETHUSDT': {
        'ema_fast': 10,
        'ema_medium': 13,
        'ema_slow': 50,
        'rsi_period': 7,
        'rsi_threshold': 48,
        'profitable_periods': 8,  # out of 8
        'avg_return': 21.3,
    },
    
    # Solana - improved to 6/8
    'SOLUSDT': {
        'ema_fast': 10,
        'ema_medium': 26,
        'ema_slow': 34,
        'rsi_period': 10,
        'rsi_threshold': 52,
        'profitable_periods': 6,  # out of 8 - improved!
        'avg_return': 31.2,
    },
    
    # BNB - similar to ETH (L1 competitor)
    'BNBUSDT': {
        'ema_fast': 10,
        'ema_medium': 13,
        'ema_slow': 50,
        'rsi_period': 7,
        'rsi_threshold': 48,
        'profitable_periods': None,  # Not yet optimized
        'avg_return': None,
    },
    
    # Default params for new symbols
    'DEFAULT': {
        'ema_fast': 8,
        'ema_medium': 21,
        'ema_slow': 50,
        'rsi_period': 7,
        'rsi_threshold': 50,
        'profitable_periods': None,
        'avg_return': None,
    },
}


# ═══════════════════════════════════════════════════════════════════════════════
#                           HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def get_params(symbol: str) -> Dict:
    """Get optimized parameters for a symbol."""
    if symbol in SYMBOL_PARAMS:
        params = SYMBOL_PARAMS[symbol].copy()
        # Remove metadata
        params.pop('profitable_periods', None)
        params.pop('avg_return', None)
        return params
    return SYMBOL_PARAMS['DEFAULT'].copy()


def get_all_optimized_symbols() -> list:
    """Get list of symbols that have been optimized."""
    return [
        symbol for symbol, params in SYMBOL_PARAMS.items()
        if params.get('profitable_periods') is not None and symbol != 'DEFAULT'
    ]


def print_summary():
    """Print optimization summary."""
    print("\n" + "=" * 60)
    print("SYMBOL OPTIMIZATION SUMMARY")
    print("=" * 60 + "\n")
    
    for symbol, params in SYMBOL_PARAMS.items():
        if symbol == 'DEFAULT':
            continue
        
        prof = params.get('profitable_periods')
        ret = params.get('avg_return')
        
        if prof is not None:
            print(f"{symbol}:")
            print(f"  Profitable: {prof}/8 ({prof/8*100:.0f}%)")
            print(f"  Avg Return: +{ret:.1f}%")
            print(f"  Params: EMA {params['ema_fast']}/{params['ema_medium']}/{params['ema_slow']}, "
                  f"RSI {params['rsi_period']}/{params['rsi_threshold']}")
        else:
            print(f"{symbol}: Not yet optimized")
        print()


# ═══════════════════════════════════════════════════════════════════════════════
#                           MAIN
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print_summary()
