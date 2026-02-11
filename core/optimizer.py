"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                       PARAMETER OPTIMIZER                                     ║
║                                                                               ║
║  Automated optimization with grid search and walk-forward validation.        ║
║  Goal: Find best parameters for each market regime.                          ║
╚═══════════════════════════════════════════════════════════════════════════════╝

Features:
- Grid search over parameter ranges
- Walk-forward validation to prevent overfitting
- Regime-specific optimization
- Multi-objective scoring (return, sharpe, drawdown, win_rate)

Author: Bot_Algo
Last Updated: January 2026
"""

import os
import sys
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Callable
from dataclasses import dataclass, field
from itertools import product
import logging
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.terminal_alerts import Color
from stress_test import STRESS_PERIODS, fetch_period_data, MarketPeriod

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger("Optimizer")


# ═══════════════════════════════════════════════════════════════════════════════
#                           PARAMETER SPACE
# ═══════════════════════════════════════════════════════════════════════════════

PARAM_GRID = {
    'ema_fast': [5, 6, 8, 10],
    'ema_medium': [13, 18, 21, 26],
    'ema_slow': [34, 42, 50, 60],
    'rsi_period': [5, 7, 10, 14],
    'rsi_threshold': [45, 48, 50, 52, 55],
}

# Reduced grid for faster testing
PARAM_GRID_FAST = {
    'ema_fast': [5, 8, 10],
    'ema_medium': [13, 21],
    'ema_slow': [34, 50],
    'rsi_period': [7, 10],
    'rsi_threshold': [48, 50, 52],
}


@dataclass
class OptimizationResult:
    """Result from a single parameter set."""
    params: Dict
    profitable_periods: int
    total_return: float
    avg_sharpe: float
    max_drawdown: float
    avg_win_rate: float
    score: float
    period_results: List = field(default_factory=list)


# ═══════════════════════════════════════════════════════════════════════════════
#                           STRATEGY WITH PARAMS
# ═══════════════════════════════════════════════════════════════════════════════

def calculate_indicators_with_params(df: pd.DataFrame, params: Dict) -> pd.DataFrame:
    """Calculate indicators with custom parameters."""
    df = df.copy()
    
    close_col = 'close' if 'close' in df.columns else 'Close'
    high_col = 'high' if 'high' in df.columns else 'High'
    low_col = 'low' if 'low' in df.columns else 'Low'
    
    close = df[close_col]
    high = df[high_col]
    low = df[low_col]
    
    # EMAs with custom periods
    df['ema_fast'] = close.ewm(span=params['ema_fast']).mean()
    df['ema_medium'] = close.ewm(span=params['ema_medium']).mean()
    df['ema_slow'] = close.ewm(span=params['ema_slow']).mean()
    
    # EMA alignment
    df['ema_bullish'] = (df['ema_fast'] > df['ema_medium']) & (df['ema_medium'] > df['ema_slow'])
    df['ema_bearish'] = (df['ema_fast'] < df['ema_medium']) & (df['ema_medium'] < df['ema_slow'])
    
    # EMA crosses
    df['ema_cross_up'] = (df['ema_fast'] > df['ema_medium']) & (df['ema_fast'].shift(1) <= df['ema_medium'].shift(1))
    df['ema_cross_down'] = (df['ema_fast'] < df['ema_medium']) & (df['ema_fast'].shift(1) >= df['ema_medium'].shift(1))
    
    # RSI with custom period
    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).ewm(span=params['rsi_period']).mean()
    loss = (-delta.where(delta < 0, 0)).ewm(span=params['rsi_period']).mean()
    rs = gain / loss.replace(0, np.nan)
    df['rsi'] = 100 - (100 / (1 + rs))
    
    # RSI with custom threshold
    df['rsi_bullish'] = df['rsi'] > params['rsi_threshold']
    df['rsi_bearish'] = df['rsi'] < params['rsi_threshold']
    
    # Volatility
    tr1 = high - low
    tr2 = abs(high - close.shift())
    tr3 = abs(low - close.shift())
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    df['atr'] = tr.ewm(span=10).mean()
    df['atr_avg'] = df['atr'].rolling(50).mean()
    df['vol_ratio'] = df['atr'] / df['atr_avg']
    df['vol_extreme'] = df['vol_ratio'] > 2.5
    
    # Breakouts
    df['high_20'] = high.rolling(20).max()
    df['low_20'] = low.rolling(20).min()
    df['breakout_up'] = close > df['high_20'].shift(1)
    df['breakout_down'] = close < df['low_20'].shift(1)
    
    return df


def generate_signals_with_params(df: pd.DataFrame, params: Dict) -> pd.Series:
    """Generate signals with custom parameters."""
    df = calculate_indicators_with_params(df, params)
    
    signals = pd.Series(0, index=df.index)
    position = 0
    
    for i in range(2, len(df)):
        curr = df.iloc[i]
        prev = df.iloc[i-1]
        
        if curr['vol_extreme']:
            position = 0
            signals.iloc[i] = 0
            continue
        
        if position == 0:
            long_entry = (
                curr['ema_cross_up'] or 
                (curr['ema_bullish'] and curr['rsi_bullish'] and curr['breakout_up'])
            )
            short_entry = (
                curr['ema_cross_down'] or 
                (curr['ema_bearish'] and curr['rsi_bearish'] and curr['breakout_down'])
            )
            
            if long_entry and not short_entry:
                position = 1
            elif short_entry and not long_entry:
                position = -1
        
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
    
    return signals


# ═══════════════════════════════════════════════════════════════════════════════
#                           OPTIMIZER
# ═══════════════════════════════════════════════════════════════════════════════

class ParameterOptimizer:
    """
    Automated parameter optimization with grid search.
    """
    
    def __init__(
        self,
        param_grid: Dict = None,
        periods: List[MarketPeriod] = None,
        symbol: str = 'BTCUSDT'
    ):
        self.param_grid = param_grid or PARAM_GRID_FAST
        self.periods = periods or STRESS_PERIODS
        self.symbol = symbol
        self.results: List[OptimizationResult] = []
        
        # Cache fetched data
        self._data_cache: Dict[str, pd.DataFrame] = {}
    
    def _get_period_data(self, period: MarketPeriod) -> pd.DataFrame:
        """Get data for period (cached)."""
        key = f"{period.start_date}_{period.end_date}"
        if key not in self._data_cache:
            self._data_cache[key] = fetch_period_data(
                self.symbol, period.start_date, period.end_date
            )
        return self._data_cache[key]
    
    def _evaluate_params(self, params: Dict) -> OptimizationResult:
        """Evaluate a single parameter set on all periods."""
        period_results = []
        
        for period in self.periods:
            df = self._get_period_data(period)
            
            if len(df) < 30:
                period_results.append({
                    'period': period.name,
                    'return': 0,
                    'sharpe': 0,
                    'max_dd': 0,
                    'win_rate': 0
                })
                continue
            
            # Generate signals
            signals = generate_signals_with_params(df, params)
            
            # Calculate metrics
            returns = df['close'].pct_change()
            strategy_returns = signals.shift(1) * returns
            strategy_returns = strategy_returns.dropna()
            
            total_return = (1 + strategy_returns).prod() - 1
            
            if len(strategy_returns) > 0 and strategy_returns.std() > 0:
                sharpe = (strategy_returns.mean() / strategy_returns.std()) * np.sqrt(252)
            else:
                sharpe = 0
            
            # Drawdown
            cumulative = (1 + strategy_returns).cumprod()
            rolling_max = cumulative.expanding().max()
            max_dd = ((cumulative - rolling_max) / rolling_max).min()
            
            # Win rate
            wins = (strategy_returns > 0).sum()
            total = (strategy_returns != 0).sum()
            win_rate = wins / total * 100 if total > 0 else 0
            
            period_results.append({
                'period': period.name,
                'market_type': period.market_type,
                'return': total_return * 100,
                'sharpe': sharpe,
                'max_dd': max_dd * 100,
                'win_rate': win_rate
            })
        
        # Aggregate
        profitable = sum(1 for r in period_results if r['return'] > 0)
        avg_return = np.mean([r['return'] for r in period_results])
        avg_sharpe = np.mean([r['sharpe'] for r in period_results])
        max_dd = min([r['max_dd'] for r in period_results])
        avg_win = np.mean([r['win_rate'] for r in period_results])
        
        # Score function (weighted)
        # Prioritize: profitable periods > sharpe > return > low drawdown
        score = (
            profitable * 15 +              # 15 points per profitable period
            avg_sharpe * 5 +                # Sharpe contribution
            avg_return * 0.5 +              # Return contribution
            (-max_dd) * 0.1 +               # Penalty for drawdown
            avg_win * 0.1                   # Win rate bonus
        )
        
        return OptimizationResult(
            params=params,
            profitable_periods=profitable,
            total_return=avg_return,
            avg_sharpe=avg_sharpe,
            max_drawdown=max_dd,
            avg_win_rate=avg_win,
            score=score,
            period_results=period_results
        )
    
    def run_grid_search(self, verbose: bool = True) -> List[OptimizationResult]:
        """Run full grid search."""
        # Generate all combinations
        param_names = list(self.param_grid.keys())
        param_values = list(self.param_grid.values())
        combinations = list(product(*param_values))
        
        total = len(combinations)
        
        if verbose:
            print(f"\n{Color.BOLD}{'=' * 60}{Color.RESET}")
            print(f"{Color.CYAN}PARAMETER OPTIMIZATION{Color.RESET}")
            print(f"{Color.BOLD}{'=' * 60}{Color.RESET}")
            print(f"\nTesting {total} parameter combinations...")
            print(f"Parameters: {param_names}\n")
        
        self.results = []
        
        for idx, values in enumerate(combinations):
            params = dict(zip(param_names, values))
            
            result = self._evaluate_params(params)
            self.results.append(result)
            
            if verbose and (idx + 1) % 10 == 0:
                print(f"  Progress: {idx + 1}/{total} ({(idx+1)/total*100:.0f}%)")
        
        # Sort by score
        self.results.sort(key=lambda x: x.score, reverse=True)
        
        if verbose:
            self._print_top_results(5)
        
        return self.results
    
    def _print_top_results(self, n: int = 5):
        """Print top N results."""
        print(f"\n{Color.BOLD}TOP {n} PARAMETER SETS:{Color.RESET}")
        print("-" * 60)
        
        for i, result in enumerate(self.results[:n]):
            prof_color = Color.GREEN if result.profitable_periods >= 7 else Color.YELLOW
            print(f"\n{Color.BOLD}#{i+1} Score: {result.score:.1f}{Color.RESET}")
            print(f"  Params: {result.params}")
            print(f"  Profitable: {prof_color}{result.profitable_periods}/8{Color.RESET}")
            print(f"  Avg Return: {result.total_return:+.1f}%")
            print(f"  Avg Sharpe: {result.avg_sharpe:.2f}")
            print(f"  Max DD: {result.max_drawdown:.1f}%")
    
    def get_best_params(self) -> Dict:
        """Get best parameter set."""
        if not self.results:
            self.run_grid_search(verbose=False)
        return self.results[0].params
    
    def get_regime_specific_params(self) -> Dict[str, Dict]:
        """
        Find best parameters for each market regime.
        """
        regime_results = {}
        
        for result in self.results[:20]:  # Top 20
            for pr in result.period_results:
                regime = pr.get('market_type', 'unknown')
                if regime not in regime_results:
                    regime_results[regime] = []
                
                regime_results[regime].append({
                    'params': result.params,
                    'return': pr['return'],
                    'sharpe': pr['sharpe']
                })
        
        # Find best for each regime
        best_per_regime = {}
        for regime, results in regime_results.items():
            results.sort(key=lambda x: x['return'], reverse=True)
            if results:
                best_per_regime[regime] = {
                    'params': results[0]['params'],
                    'return': results[0]['return']
                }
        
        return best_per_regime


# ═══════════════════════════════════════════════════════════════════════════════
#                           WALK-FORWARD VALIDATION
# ═══════════════════════════════════════════════════════════════════════════════

def walk_forward_validate(
    optimizer: ParameterOptimizer,
    train_periods: int = 6,
    test_periods: int = 2
) -> Dict:
    """
    Walk-forward validation to prevent overfitting.
    
    Train on N periods, test on M periods, slide window.
    """
    all_periods = optimizer.periods
    results = []
    
    for i in range(len(all_periods) - train_periods - test_periods + 1):
        train = all_periods[i:i + train_periods]
        test = all_periods[i + train_periods:i + train_periods + test_periods]
        
        # Optimize on train
        train_optimizer = ParameterOptimizer(
            param_grid=optimizer.param_grid,
            periods=train,
            symbol=optimizer.symbol
        )
        train_optimizer.run_grid_search(verbose=False)
        best_params = train_optimizer.get_best_params()
        
        # Test on out-of-sample
        test_optimizer = ParameterOptimizer(
            param_grid={'ema_fast': [best_params['ema_fast']], 
                       'ema_medium': [best_params['ema_medium']],
                       'ema_slow': [best_params['ema_slow']],
                       'rsi_period': [best_params['rsi_period']],
                       'rsi_threshold': [best_params['rsi_threshold']]},
            periods=test,
            symbol=optimizer.symbol
        )
        test_result = test_optimizer._evaluate_params(best_params)
        
        results.append({
            'train_periods': [p.name for p in train],
            'test_periods': [p.name for p in test],
            'best_params': best_params,
            'test_return': test_result.total_return,
            'test_profitable': test_result.profitable_periods
        })
    
    return results


# ═══════════════════════════════════════════════════════════════════════════════
#                           MAIN
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Parameter Optimizer')
    parser.add_argument('--symbol', type=str, default='BTCUSDT')
    parser.add_argument('--fast', action='store_true', help='Use reduced parameter grid')
    
    args = parser.parse_args()
    
    grid = PARAM_GRID_FAST if args.fast else PARAM_GRID
    
    optimizer = ParameterOptimizer(
        param_grid=grid,
        symbol=args.symbol
    )
    
    results = optimizer.run_grid_search(verbose=True)
    
    print(f"\n{Color.BOLD}BEST PARAMETERS:{Color.RESET}")
    print(optimizer.get_best_params())
    
    print(f"\n{Color.BOLD}REGIME-SPECIFIC BEST:{Color.RESET}")
    for regime, data in optimizer.get_regime_specific_params().items():
        print(f"  {regime}: {data['return']:+.1f}%")
