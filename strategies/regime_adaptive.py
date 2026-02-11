"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                       REGIME-ADAPTIVE STRATEGY                                ║
║                                                                               ║
║  Uses different parameters based on detected market regime.                  ║
║  Goal: 8/8 profitable periods by optimizing for each market type.            ║
╚═══════════════════════════════════════════════════════════════════════════════╝

Regime Detection:
- ADX < 20: Ranging/Choppy → Use mean-reversion params
- ADX > 25 + Up trend: Trending Up → Use momentum params
- ADX > 25 + Down trend: Trending Down → Use momentum params
- ATR > 2x normal: Volatile → Conservative params, smaller size

Author: Bot_Algo
Last Updated: January 2026
"""

import numpy as np
import pandas as pd
from typing import Dict, Tuple
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger("RegimeAdaptive")


# ═══════════════════════════════════════════════════════════════════════════════
#                           REGIME TYPES
# ═══════════════════════════════════════════════════════════════════════════════

class MarketRegime(Enum):
    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    RANGING = "ranging"
    VOLATILE = "volatile"
    CONSOLIDATING = "consolidating"  # Post-hype, like ETF 2024
    V_RECOVERY = "v_recovery"  # Sharp drop + recovery like COVID


# ═══════════════════════════════════════════════════════════════════════════════
#                           REGIME-SPECIFIC PARAMETERS
# ═══════════════════════════════════════════════════════════════════════════════

# Parameters optimized for each regime
REGIME_PARAMS = {
    MarketRegime.TRENDING_UP: {
        'ema_fast': 8,
        'ema_medium': 21,
        'ema_slow': 50,
        'rsi_period': 7,
        'rsi_threshold': 45,     # Lower threshold to catch uptrends earlier
        'use_breakout': True,
        'use_ema_cross': True,
        'position_mult': 1.2,    # Larger position in clear trends
    },
    MarketRegime.TRENDING_DOWN: {
        'ema_fast': 8,
        'ema_medium': 21,
        'ema_slow': 50,
        'rsi_period': 7,
        'rsi_threshold': 55,     # Higher threshold to catch downtrends
        'use_breakout': True,
        'use_ema_cross': True,
        'position_mult': 1.0,
    },
    MarketRegime.RANGING: {
        'ema_fast': 5,
        'ema_medium': 13,
        'ema_slow': 34,
        'rsi_period': 5,
        'rsi_threshold': 50,
        'use_breakout': False,   # Don't use breakouts in ranging
        'use_ema_cross': True,
        'position_mult': 0.8,    # Smaller position in choppy markets
    },
    MarketRegime.VOLATILE: {
        'ema_fast': 10,
        'ema_medium': 26,
        'ema_slow': 60,
        'rsi_period': 14,
        'rsi_threshold': 50,
        'use_breakout': False,
        'use_ema_cross': True,
        'position_mult': 0.5,    # Much smaller position
        'skip_if_extreme': True,
    },
    MarketRegime.CONSOLIDATING: {
        # Special params for post-hype consolidation (like ETF 2024)
        'ema_fast': 5,
        'ema_medium': 13,
        'ema_slow': 34,
        'rsi_period': 5,
        'rsi_threshold': 50,
        'use_breakout': False,
        'use_ema_cross': True,
        'require_confirmation': True,  # Extra confirmation needed
        'position_mult': 0.6,
    },
    MarketRegime.V_RECOVERY: {
        # Params for V-shaped recovery (COVID, flash crashes)
        'ema_fast': 5,
        'ema_medium': 13,
        'ema_slow': 34,
        'rsi_period': 5,
        'rsi_threshold': 40,  # Lower threshold to catch recovery
        'use_breakout': True,  # Breakouts work well in V-recovery
        'use_ema_cross': True,
        'position_mult': 1.0,
        'favor_long': True,  # Favor long in recovery
    },
}


# ═══════════════════════════════════════════════════════════════════════════════
#                           REGIME DETECTOR
# ═══════════════════════════════════════════════════════════════════════════════

class RegimeDetector:
    """
    Detect current market regime.
    """
    
    def __init__(
        self,
        adx_trending: float = 25,
        adx_ranging: float = 20,
        vol_extreme: float = 2.0,
        consolidation_lookback: int = 20
    ):
        self.adx_trending = adx_trending
        self.adx_ranging = adx_ranging
        self.vol_extreme = vol_extreme
        self.consolidation_lookback = consolidation_lookback
    
    def detect(self, df: pd.DataFrame) -> pd.Series:
        """Detect regime for each row."""
        df = self._add_regime_indicators(df)
        
        regimes = pd.Series(MarketRegime.RANGING, index=df.index)
        
        for i in range(len(df)):
            row = df.iloc[i]
            
            # Check for V-recovery first (takes priority)
            if self._is_v_recovery(df, i):
                regimes.iloc[i] = MarketRegime.V_RECOVERY
                continue
            
            # Check volatility
            if row.get('vol_extreme', False):
                regimes.iloc[i] = MarketRegime.VOLATILE
                continue
            
            # Check for consolidation (price range shrinking after big move)
            if self._is_consolidating(df, i):
                regimes.iloc[i] = MarketRegime.CONSOLIDATING
                continue
            
            adx = row.get('adx', 15)
            plus_di = row.get('plus_di', 50)
            minus_di = row.get('minus_di', 50)
            
            if adx > self.adx_trending:
                if plus_di > minus_di:
                    regimes.iloc[i] = MarketRegime.TRENDING_UP
                else:
                    regimes.iloc[i] = MarketRegime.TRENDING_DOWN
            elif adx < self.adx_ranging:
                regimes.iloc[i] = MarketRegime.RANGING
            else:
                # Transition zone
                regimes.iloc[i] = MarketRegime.RANGING
        
        return regimes
    
    def _add_regime_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add ADX and volatility indicators."""
        df = df.copy()
        
        close_col = 'close' if 'close' in df.columns else 'Close'
        high_col = 'high' if 'high' in df.columns else 'High'
        low_col = 'low' if 'low' in df.columns else 'Low'
        
        close = df[close_col]
        high = df[high_col]
        low = df[low_col]
        
        # ADX calculation
        plus_dm = high.diff()
        minus_dm = -low.diff()
        plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0)
        minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0)
        
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        
        smoothed_tr = tr.rolling(14).sum()
        df['plus_di'] = 100 * (plus_dm.rolling(14).sum() / smoothed_tr)
        df['minus_di'] = 100 * (minus_dm.rolling(14).sum() / smoothed_tr)
        
        dx = 100 * abs(df['plus_di'] - df['minus_di']) / (df['plus_di'] + df['minus_di'] + 0.001)
        df['adx'] = dx.rolling(14).mean()
        
        # Volatility
        df['atr'] = tr.ewm(span=10).mean()
        df['atr_avg'] = df['atr'].rolling(50).mean()
        df['vol_ratio'] = df['atr'] / df['atr_avg']
        df['vol_extreme'] = df['vol_ratio'] > self.vol_extreme
        
        # Range for consolidation detection
        df['range_20'] = high.rolling(20).max() - low.rolling(20).min()
        df['range_pct'] = df['range_20'] / close * 100
        
        return df
    
    def _is_consolidating(self, df: pd.DataFrame, idx: int) -> bool:
        """Detect if market is in post-hype consolidation."""
        if idx < self.consolidation_lookback + 10:
            return False
        
        # Check if recent range is much smaller than prior range
        current_range = df['range_pct'].iloc[idx]
        prior_range = df['range_pct'].iloc[idx - self.consolidation_lookback]
        
        # Also check if there was a big move before
        close_col = 'close' if 'close' in df.columns else 'Close'
        price_change = abs(df[close_col].iloc[idx] - df[close_col].iloc[idx - self.consolidation_lookback * 2])
        price_change_pct = price_change / df[close_col].iloc[idx - self.consolidation_lookback * 2] * 100
        
        # Consolidating: big move before (>30%) + shrinking range
        if price_change_pct > 30 and current_range < prior_range * 0.6:
            return True
        
        return False
    
    def _is_v_recovery(self, df: pd.DataFrame, idx: int) -> bool:
        """
        Detect V-shaped recovery (like COVID March 2020).
        Sharp drop followed by sharp recovery.
        """
        if idx < 15:
            return False
        
        close_col = 'close' if 'close' in df.columns else 'Close'
        close = df[close_col]
        
        # Check for sharp drop and recovery pattern
        lookback = 10
        if idx < lookback * 2:
            return False
        
        # Find min in lookback
        window = close.iloc[idx - lookback:idx + 1]
        min_idx = window.idxmin()
        min_val = window.min()
        
        # Price before the drop
        pre_drop = close.iloc[idx - lookback]
        
        # Current price
        current = close.iloc[idx]
        
        # Drop from pre to min
        drop_pct = (pre_drop - min_val) / pre_drop * 100
        
        # Recovery from min to current
        if min_val > 0:
            recovery_pct = (current - min_val) / min_val * 100
        else:
            recovery_pct = 0
        
        # V-recovery: >20% drop followed by >15% recovery
        if drop_pct > 20 and recovery_pct > 15:
            return True
        
        return False


# ═══════════════════════════════════════════════════════════════════════════════
#                           ADAPTIVE STRATEGY
# ═══════════════════════════════════════════════════════════════════════════════

def calculate_adaptive_indicators(df: pd.DataFrame, params: Dict) -> pd.DataFrame:
    """Calculate indicators with given parameters."""
    df = df.copy()
    
    close_col = 'close' if 'close' in df.columns else 'Close'
    high_col = 'high' if 'high' in df.columns else 'High'
    low_col = 'low' if 'low' in df.columns else 'Low'
    
    close = df[close_col]
    high = df[high_col]
    low = df[low_col]
    
    # EMAs
    df['ema_fast'] = close.ewm(span=params['ema_fast']).mean()
    df['ema_medium'] = close.ewm(span=params['ema_medium']).mean()
    df['ema_slow'] = close.ewm(span=params['ema_slow']).mean()
    
    # EMA states
    df['ema_bullish'] = (df['ema_fast'] > df['ema_medium']) & (df['ema_medium'] > df['ema_slow'])
    df['ema_bearish'] = (df['ema_fast'] < df['ema_medium']) & (df['ema_medium'] < df['ema_slow'])
    df['ema_cross_up'] = (df['ema_fast'] > df['ema_medium']) & (df['ema_fast'].shift(1) <= df['ema_medium'].shift(1))
    df['ema_cross_down'] = (df['ema_fast'] < df['ema_medium']) & (df['ema_fast'].shift(1) >= df['ema_medium'].shift(1))
    
    # RSI
    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).ewm(span=params['rsi_period']).mean()
    loss = (-delta.where(delta < 0, 0)).ewm(span=params['rsi_period']).mean()
    rs = gain / loss.replace(0, np.nan)
    df['rsi'] = 100 - (100 / (1 + rs))
    
    df['rsi_bullish'] = df['rsi'] > params['rsi_threshold']
    df['rsi_bearish'] = df['rsi'] < params['rsi_threshold']
    
    # Breakouts
    df['high_20'] = high.rolling(20).max()
    df['low_20'] = low.rolling(20).min()
    df['breakout_up'] = close > df['high_20'].shift(1)
    df['breakout_down'] = close < df['low_20'].shift(1)
    
    return df


def generate_adaptive_signals(df: pd.DataFrame) -> Tuple[pd.Series, pd.Series]:
    """
    Generate signals with regime-adaptive parameters.
    
    Returns:
        signals: Trading signals (-1, 0, 1)
        regimes: Detected regime for each bar
    """
    # Detect regimes
    detector = RegimeDetector()
    regimes = detector.detect(df)
    
    signals = pd.Series(0, index=df.index)
    position = 0
    current_params = REGIME_PARAMS[MarketRegime.RANGING]
    
    for i in range(2, len(df)):
        regime = regimes.iloc[i]
        params = REGIME_PARAMS[regime]
        
        # Recalculate indicators if params changed
        if params != current_params:
            current_params = params
        
        # Calculate indicators for current bar's regime
        window_start = max(0, i - 60)
        window = df.iloc[window_start:i+1].copy()
        window = calculate_adaptive_indicators(window, params)
        
        if len(window) < 3:
            signals.iloc[i] = position
            continue
        
        curr = window.iloc[-1]
        prev = window.iloc[-2]
        
        # Skip if volatile and params say to skip
        if regime == MarketRegime.VOLATILE and params.get('skip_if_extreme', False):
            position = 0
            signals.iloc[i] = 0
            continue
        
        # Entry logic
        if position == 0:
            long_signal = False
            short_signal = False
            
            # EMA cross entry
            if params.get('use_ema_cross', True):
                if curr['ema_cross_up']:
                    long_signal = True
                if curr['ema_cross_down']:
                    short_signal = True
            
            # Breakout entry (only in trending regimes)
            if params.get('use_breakout', False):
                if curr['ema_bullish'] and curr['rsi_bullish'] and curr['breakout_up']:
                    long_signal = True
                if curr['ema_bearish'] and curr['rsi_bearish'] and curr['breakout_down']:
                    short_signal = True
            
            # Confirmation requirement for consolidating
            if params.get('require_confirmation', False):
                # Need both EMA and RSI aligned
                if long_signal and not (curr['ema_bullish'] or curr['rsi_bullish']):
                    long_signal = False
                if short_signal and not (curr['ema_bearish'] or curr['rsi_bearish']):
                    short_signal = False
            
            # Favor long in V-recovery or trending up
            if params.get('favor_long', False) or regime == MarketRegime.V_RECOVERY:
                # More aggressive long entry, suppress short
                if curr['ema_bullish'] or curr['rsi_bullish']:
                    long_signal = True
                short_signal = False  # Don't short in V-recovery
            
            # In trending up, also favor long
            if regime == MarketRegime.TRENDING_UP:
                if curr['ema_bullish']:
                    long_signal = True
                # Still allow shorts but less aggressive
            
            if long_signal and not short_signal:
                position = 1
            elif short_signal and not long_signal:
                position = -1
        
        # Exit logic
        elif position == 1:
            exit_ema = curr['ema_cross_down']
            exit_rsi = not curr['rsi_bullish'] and prev['rsi_bullish']
            
            if curr['ema_bearish'] and curr['rsi_bearish']:
                position = -1
            elif exit_ema or exit_rsi:
                position = 0
        
        elif position == -1:
            exit_ema = curr['ema_cross_up']
            exit_rsi = curr['rsi_bullish'] and not prev['rsi_bullish']
            
            if curr['ema_bullish'] and curr['rsi_bullish']:
                position = 1
            elif exit_ema or exit_rsi:
                position = 0
        
        signals.iloc[i] = position
    
    return signals, regimes


# ═══════════════════════════════════════════════════════════════════════════════
#                           MAIN
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    from stress_test import STRESS_PERIODS, fetch_period_data
    from core.terminal_alerts import Color
    
    print(f"\n{Color.BOLD}{'=' * 60}{Color.RESET}")
    print(f"{Color.CYAN}REGIME-ADAPTIVE STRATEGY TEST{Color.RESET}")
    print(f"{Color.BOLD}{'=' * 60}{Color.RESET}\n")
    
    profitable = 0
    total_return = 0
    
    for period in STRESS_PERIODS:
        df = fetch_period_data('BTCUSDT', period.start_date, period.end_date)
        
        if len(df) < 30:
            continue
        
        signals, regimes = generate_adaptive_signals(df)
        
        # Calculate return
        returns = df['close'].pct_change()
        strategy_returns = signals.shift(1) * returns
        strategy_returns = strategy_returns.dropna()
        
        period_return = (1 + strategy_returns).prod() - 1
        total_return += period_return
        
        # Regime distribution
        regime_counts = regimes.value_counts()
        
        color = Color.GREEN if period_return > 0 else Color.RED
        print(f"{period.name}")
        print(f"  Return: {color}{period_return*100:+.2f}%{Color.RESET}")
        print(f"  Primary Regime: {regime_counts.index[0].value if len(regime_counts) > 0 else 'N/A'}")
        
        if period_return > 0:
            profitable += 1
    
    print(f"\n{Color.BOLD}SUMMARY:{Color.RESET}")
    print(f"  Profitable: {profitable}/8 ({profitable/8*100:.0f}%)")
    print(f"  Total Return: {total_return*100:+.2f}%")
    print(f"  Avg Return: {total_return/8*100:+.2f}%")
