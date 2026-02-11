"""
BACKTESTING SIMULATION FRAMEWORK
Comprehensive backtesting with p-hacking safeguards

Usage:
    python backtests/backtest_engine.py --strategy crypto --period 5y
"""

import sys
import os
from pathlib import Path
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import json

# Add root to path
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

from strategies.advanced import BacktestSafeguards, UncorrelatedFeatures


class BacktestEngine:
    """
    Unified backtesting engine for all trading strategies
    
    Features:
    - Historical data replay
    - P-hacking safeguards
    - Walk-forward analysis
    - Monte Carlo validation
    - Multi-timeframe testing
    """
    
    def __init__(self, strategy_name: str, initial_capital: float = 10000):
        self.strategy_name = strategy_name
        self.initial_capital = initial_capital
        self.capital = initial_capital
        
        # Trade log
        self.trades = []
        self.equity_curve = []
        
        # Performance metrics
        self.total_trades = 0
        self.wins = 0
        self.losses = 0
        
    def generate_synthetic_data(
        self,
        n_days: int = 1825,  # 5 years
        trend: float = 0.0001,  # Daily drift
        volatility: float = 0.02,  # Daily volatility
        regime_shifts: int = 5  # Number of regime changes
    ) -> pd.DataFrame:
        """
        Generate realistic synthetic price data with regime shifts
        
        This simulates:
        - Trending periods (high Hurst)
        - Mean-reverting periods (low Hurst)
        - High volatility periods (high entropy)
        - Low volatility periods (low entropy)
        """
        print(f"Generating {n_days} days of synthetic data...")
        
        # Create date range
        dates = pd.date_range(end=datetime.now(), periods=n_days, freq='D')
        
        # Initialize price at 100
        prices = [100.0]
        
        # Regime parameters - ensure at least 1 to avoid division by zero
        regime_length = max(1, n_days // (regime_shifts + 1))
        current_regime = 0
        
        for i in range(1, n_days):
            # Change regime periodically (guard against zero regime_length)
            if regime_length > 0 and i % regime_length == 0 and current_regime < regime_shifts:
                current_regime += 1
                
            # Alternate between trending and mean-reverting
            if current_regime % 2 == 0:
                # Trending regime (high Hurst)
                current_trend = trend * 2
                current_vol = volatility
            else:
                # Mean-reverting regime (low Hurst)
                # Add mean reversion force
                deviation = prices[-1] - 100
                current_trend = -deviation * 0.01
                current_vol = volatility * 1.5
            
            # Random shock
            shock = np.random.normal(current_trend, current_vol)
            new_price = prices[-1] * (1 + shock)
            prices.append(new_price)
        
        # Create DataFrame
        df = pd.DataFrame({
            'date': dates,
            'close': prices,
            'open': prices,  # Simplified
            'high': [p * (1 + abs(np.random.normal(0, 0.005))) for p in prices],
            'low': [p * (1 - abs(np.random.normal(0, 0.005))) for p in prices],
            'volume': np.random.uniform(1000000, 5000000, n_days)
        })
        
        # Calculate returns
        df['returns'] = df['close'].pct_change()
        
        print(f"[OK] Generated {n_days} days | Price: ${df['close'].iloc[0]:.2f} -> ${df['close'].iloc[-1]:.2f}")
        
        return df
    
    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate technical indicators and uncorrelated features"""
        
        # Simple Moving Averages
        df['SMA_20'] = df['close'].rolling(20).mean()
        df['SMA_50'] = df['close'].rolling(50).mean()
        
        # RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        df['RSI'] = 100 - (100 / (1 + rs))
        
        # Uncorrelated Features (rolling calculation)
        print("Calculating uncorrelated features...")
        
        hurst_values = []
        entropy_values = []
        efficiency_values = []
        
        for i in range(len(df)):
            if i < 50:
                hurst_values.append(0.5)
                entropy_values.append(0.5)
                efficiency_values.append(0.5)
            else:
                window = df['close'].iloc[i-50:i].values
                hurst_values.append(UncorrelatedFeatures.get_hurst_exponent(window))
                entropy_values.append(UncorrelatedFeatures.get_shannon_entropy(window))
                efficiency_values.append(UncorrelatedFeatures.get_efficiency_ratio(window, period=14))
        
        df['Hurst'] = hurst_values
        df['Entropy'] = entropy_values
        df['Efficiency'] = efficiency_values
        
        return df
    
    def simple_strategy(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Simple trend-following strategy with uncorrelated feature filtering
        
        Rules:
        - LONG: SMA_20 > SMA_50, Hurst > 0.55, Entropy < 0.8
        - SHORT: SMA_20 < SMA_50, Hurst > 0.55, Entropy < 0.8
        - HOLD: Otherwise
        """
        signals = []
        
        for i in range(len(df)):
            if i < 50:  # Need enough data
                signals.append('HOLD')
                continue
            
            sma_20 = df['SMA_20'].iloc[i]
            sma_50 = df['SMA_50'].iloc[i]
            hurst = df['Hurst'].iloc[i]
            entropy = df['Entropy'].iloc[i]
            rsi = df['RSI'].iloc[i]
            
            # Trend-following with uncorrelated filters
            if sma_20 > sma_50 and hurst > 0.55 and entropy < 0.8 and rsi < 70:
                signals.append('LONG')
            elif sma_20 < sma_50 and hurst > 0.55 and entropy < 0.8 and rsi > 30:
                signals.append('SHORT')
            else:
                signals.append('HOLD')
        
        df['signal'] = signals
        return df
    
    def run_backtest(self, df: pd.DataFrame) -> Dict:
        """Execute backtest on historical data"""
        
        print(f"\nRunning backtest: {self.strategy_name}")
        print("=" * 80)
        
        position = None
        entry_price = 0
        entry_idx = 0
        
        for i in range(51, len(df)):  # Start after warm-up
            signal = df['signal'].iloc[i]
            price = df['close'].iloc[i]
            date = df['date'].iloc[i]
            
            # Enter position
            if position is None and signal in ['LONG', 'SHORT']:
                position = signal
                entry_price = price
                entry_idx = i
                
            # Exit position
            elif position is not None:
                should_exit = False
                exit_reason = ''
                
                # Exit if signal reverses
                if (position == 'LONG' and signal == 'SHORT') or \
                   (position == 'SHORT' and signal == 'LONG'):
                    should_exit = True
                    exit_reason = 'SIGNAL_REVERSAL'
                
                # Take profit / stop loss
                pnl_pct = 0
                if position == 'LONG':
                    pnl_pct = ((price - entry_price) / entry_price) * 100
                else:
                    pnl_pct = ((entry_price - price) / entry_price) * 100
                
                if pnl_pct >= 2.0:  # 2% profit target
                    should_exit = True
                    exit_reason = 'PROFIT_TARGET'
                elif pnl_pct <= -1.0:  # 1% stop loss
                    should_exit = True
                    exit_reason = 'STOP_LOSS'
                
                if should_exit:
                    # Log trade
                    pnl_usd = self.capital * (pnl_pct / 100)
                    self.capital += pnl_usd
                    
                    trade = {
                        'entry_date': df['date'].iloc[entry_idx],
                        'exit_date': date,
                        'side': position,
                        'entry_price': entry_price,
                        'exit_price': price,
                        'pnl_pct': pnl_pct,
                        'pnl_usd': pnl_usd,
                        'exit_reason': exit_reason,
                        'hurst': df['Hurst'].iloc[i],
                        'entropy': df['Entropy'].iloc[i]
                    }
                    
                    self.trades.append(trade)
                    self.total_trades += 1
                    
                    if pnl_usd > 0:
                        self.wins += 1
                    else:
                        self.losses += 1
                    
                    # Reset position
                    position = None
            
            # Track equity
            self.equity_curve.append({
                'date': date,
                'equity': self.capital
            })
        
        # Calculate metrics
        returns = [t['pnl_pct'] / 100 for t in self.trades]
        
        if len(returns) == 0:
            print("\n[ERROR] No trades executed!")
            return {}
        
        results = {
            'total_trades': self.total_trades,
            'wins': self.wins,
            'losses': self.losses,
            'win_rate': (self.wins / self.total_trades) * 100 if self.total_trades > 0 else 0,
            'final_capital': self.capital,
            'total_return': ((self.capital - self.initial_capital) / self.initial_capital) * 100,
            'sharpe_ratio': self._calculate_sharpe(returns),
            'max_drawdown': self._calculate_max_drawdown(),
            'avg_win': np.mean([t['pnl_pct'] for t in self.trades if t['pnl_usd'] > 0]) if self.wins > 0 else 0,
            'avg_loss': np.mean([t['pnl_pct'] for t in self.trades if t['pnl_usd'] < 0]) if self.losses > 0 else 0,
        }
        
        return results
    
    def _calculate_sharpe(self, returns: List[float]) -> float:
        """Calculate Sharpe ratio"""
        if len(returns) == 0:
            return 0
        mean_return = np.mean(returns)
        std_return = np.std(returns)
        if std_return == 0:
            return 0
        return (mean_return / std_return) * np.sqrt(252)
    
    def _calculate_max_drawdown(self) -> float:
        """Calculate maximum drawdown"""
        if len(self.equity_curve) == 0:
            return 0
        
        equity = [e['equity'] for e in self.equity_curve]
        peak = equity[0]
        max_dd = 0
        
        for value in equity:
            if value > peak:
                peak = value
            dd = ((peak - value) / peak) * 100
            if dd > max_dd:
                max_dd = dd
        
        return max_dd
    
    def validate_with_safeguards(self, returns: List[float], n_params_tested: int = 1) -> Dict:
        """Apply p-hacking safeguards to backtest results"""
        
        print("\n" + "=" * 80)
        print("STATISTICAL VALIDATION (P-Hacking Safeguards)")
        print("=" * 80)
        
        returns_array = np.array(returns)
        
        report = BacktestSafeguards.validate_backtest(
            returns=returns_array,
            n_trades=self.total_trades,
            n_parameters_tested=n_params_tested,
            require_walk_forward=True
        )
        
        print(f"\n{'='*80}")
        print(f"VALIDATION RESULT: {'[VALID]' if report['valid'] else '[INVALID]'}")
        print(f"{'='*80}")
        
        if report['errors']:
            print("\n[ERRORS]:")
            for error in report['errors']:
                print(f"  - {error}")
        
        if report['warnings']:
            print("\n[WARNINGS]:")
            for warning in report['warnings']:
                print(f"  - {warning}")
        
        # Print detailed results
        if 'sharpe_test' in report:
            st = report['sharpe_test']
            print(f"\nSharpe Ratio Test:")
            print(f"  Sharpe: {st['sharpe']:.2f}")
            print(f"  P-value: {st['p_value']:.4f}")
            print(f"  Significant: {'[YES]' if st['is_significant'] else '[NO]'}")
        
        if 'walk_forward' in report:
            wf = report['walk_forward']
            print(f"\nWalk-Forward Analysis:")
            print(f"  Avg Degradation: {wf['avg_degradation']:.1%}")
            print(f"  Robust: {'[YES]' if wf['is_robust'] else '[NO]'}")
        
        if 'monte_carlo' in report:
            mc = report['monte_carlo']
            print(f"\nMonte Carlo Permutation Test:")
            print(f"  P-value: {mc['p_value']:.4f}")
            print(f"  Significant: {'[YES]' if mc['is_significant'] else '[NO]'}")
        
        return report
    
    def print_results(self, results: Dict):
        """Print backtest results"""
        
        print("\n" + "=" * 80)
        print(f"BACKTEST RESULTS: {self.strategy_name}")
        print("=" * 80)
        
        print(f"\nPerformance:")
        print(f"  Total Trades: {results['total_trades']}")
        print(f"  Win Rate: {results['win_rate']:.1f}% ({results['wins']}W / {results['losses']}L)")
        print(f"  Avg Win: {results['avg_win']:.2f}%")
        print(f"  Avg Loss: {results['avg_loss']:.2f}%")
        
        print(f"\nReturns:")
        print(f"  Initial Capital: ${self.initial_capital:,.2f}")
        print(f"  Final Capital: ${results['final_capital']:,.2f}")
        print(f"  Total Return: {results['total_return']:+.2f}%")
        
        print(f"\nRisk Metrics:")
        print(f"  Sharpe Ratio: {results['sharpe_ratio']:.2f}")
        print(f"  Max Drawdown: {results['max_drawdown']:.2f}%")
        
        print("=" * 80)


def main():
    """Run backtest simulation"""
    
    print("\n" + "=" * 80)
    print(" " * 20 + "BACKTEST SIMULATION")
    print("=" * 80)
    
    # Create backtest engine
    engine = BacktestEngine(strategy_name="Trend Following + Uncorrelated Features", initial_capital=10000)
    
    # Generate synthetic data (5 years)
    df = engine.generate_synthetic_data(n_days=1825, regime_shifts=10)
    
    # Calculate indicators
    df = engine.calculate_indicators(df)
    
    # Apply strategy
    df = engine.simple_strategy(df)
    
    # Run backtest
    results = engine.run_backtest(df)
    
    if results:
        # Print results
        engine.print_results(results)
        
        # Validate with p-hacking safeguards
        returns = [t['pnl_pct'] / 100 for t in engine.trades]
        validation = engine.validate_with_safeguards(returns, n_params_tested=1)
        
        # Save results
        results_dir = Path(__file__).parent / "results"
        results_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        results_file = results_dir / f"backtest_{timestamp}.json"
        
        with open(results_file, 'w') as f:
            json.dump({
                'results': results,
                'validation': {k: v for k, v in validation.items() if k != 'sharpe_test' and k != 'walk_forward' and k != 'monte_carlo'},
                'trades': engine.trades[:10]  # Save first 10 trades as sample
            }, f, indent=2, default=str)
        
        print(f"\n[OK] Results saved to: {results_file}")


if __name__ == "__main__":
    main()
