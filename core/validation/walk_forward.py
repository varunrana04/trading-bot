"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                       WALK-FORWARD OPTIMIZATION                               ║
║                                                                               ║
║  Robust backtesting framework to prevent overfitting and look-ahead bias.    ║
║  Implements anchored and rolling walk-forward with WFE metrics.              ║
╚═══════════════════════════════════════════════════════════════════════════════╝

Key Features:
- Walk-Forward Optimization (WFO) with rolling/anchored windows
- Walk-Forward Efficiency (WFE) metric
- Strict temporal data separation
- Monte Carlo simulation for robustness
- Train/Validation/Test splits

Anti-Overfitting Measures:
1. Out-of-sample validation at every step
2. No future data leakage
3. Parameter stability checks
4. Robustness scoring

Author: Bot_Algo
Last Updated: January 2026
"""

import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from typing import Dict, List, Callable, Optional, Any, Tuple
from enum import Enum
import logging
from datetime import datetime, timedelta
import warnings

logger = logging.getLogger("WalkForward")


# ═══════════════════════════════════════════════════════════════════════════════
#                           CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

class WFOType(Enum):
    """Walk-Forward Optimization types"""
    ROLLING = "rolling"       # Fixed window that rolls forward
    ANCHORED = "anchored"     # Expanding window (anchor at start)


@dataclass
class WFOConfig:
    """Configuration for Walk-Forward Optimization"""
    
    # Window sizes (as ratio of total data)
    train_ratio: float = 0.60          # 60% for training
    validation_ratio: float = 0.20     # 20% for validation/OOS
    holdout_ratio: float = 0.20        # 20% final hold-out (never touched)
    
    # Walk-forward settings
    wfo_type: WFOType = WFOType.ROLLING
    num_folds: int = 5                  # Number of WF folds
    min_train_samples: int = 100        # Minimum training samples (lower for flexibility)
    min_test_samples: int = 30          # Minimum test samples
    
    # Validation thresholds
    min_wfe: float = 0.50               # Minimum Walk-Forward Efficiency
    min_sharpe: float = 1.0             # Minimum Sharpe ratio
    max_drawdown: float = 0.25          # Maximum drawdown (25%)
    min_profit_factor: float = 1.3      # Minimum profit factor
    
    # Anti-overfitting
    max_parameters: int = 10            # Max parameters to optimize
    parameter_stability_threshold: float = 0.30  # 30% max variation
    
    # Execution
    slippage_pct: float = 0.001         # 0.1% slippage
    include_costs: bool = True          # Include transaction costs


@dataclass
class WFOResult:
    """Result from a single walk-forward fold"""
    fold_id: int
    train_start: datetime
    train_end: datetime
    test_start: datetime
    test_end: datetime
    
    # Performance metrics
    in_sample_return: float = 0.0
    out_sample_return: float = 0.0
    in_sample_sharpe: float = 0.0
    out_sample_sharpe: float = 0.0
    in_sample_drawdown: float = 0.0
    out_sample_drawdown: float = 0.0
    
    # Parameters used
    best_params: Dict = field(default_factory=dict)
    
    # Trade statistics
    num_trades: int = 0
    win_rate: float = 0.0
    profit_factor: float = 0.0


@dataclass
class WFOSummary:
    """Summary of complete walk-forward analysis"""
    config: WFOConfig
    folds: List[WFOResult]
    
    # Aggregate metrics
    total_return: float = 0.0
    avg_return_per_fold: float = 0.0
    wfe: float = 0.0                    # Walk-Forward Efficiency
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    profit_factor: float = 0.0
    
    # Validation
    passed: bool = False
    failure_reasons: List[str] = field(default_factory=list)
    
    # Parameter stability
    param_stability: Dict[str, float] = field(default_factory=dict)


# ═══════════════════════════════════════════════════════════════════════════════
#                           WALK-FORWARD ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

class WalkForwardOptimizer:
    """
    Walk-Forward Optimization engine for robust strategy validation.
    
    Usage:
        wfo = WalkForwardOptimizer(
            data=price_data,
            strategy_func=my_strategy,
            optimize_func=my_optimizer,
            config=WFOConfig()
        )
        
        summary = wfo.run()
        if summary.passed:
            print("Strategy is robust!")
    """
    
    def __init__(
        self,
        data: pd.DataFrame,
        strategy_func: Callable,
        optimize_func: Callable,
        config: WFOConfig = None,
        cost_func: Callable = None
    ):
        """
        Initialize Walk-Forward Optimizer.
        
        Args:
            data: DataFrame with OHLCV data (must have datetime index)
            strategy_func: Function that takes (data, params) and returns signals
            optimize_func: Function that takes data and returns best params
            config: WFO configuration
            cost_func: Function to calculate costs (optional)
        """
        self.data = data
        self.strategy_func = strategy_func
        self.optimize_func = optimize_func
        self.config = config or WFOConfig()
        self.cost_func = cost_func
        
        # Validate data
        self._validate_data()
        
        # Split data
        self._create_splits()
        
        logger.info(f"WFO initialized with {len(data)} samples, {self.config.num_folds} folds")
    
    def _validate_data(self):
        """Validate input data."""
        if not isinstance(self.data.index, pd.DatetimeIndex):
            raise ValueError("Data must have DatetimeIndex")
        
        if len(self.data) < self.config.min_train_samples + self.config.min_test_samples:
            raise ValueError(f"Insufficient data: need at least {self.config.min_train_samples + self.config.min_test_samples} samples")
        
        # Check for required columns
        required_cols = ['close']
        for col in required_cols:
            if col not in self.data.columns and col.lower() not in self.data.columns:
                # Try to find case-insensitive
                found = False
                for c in self.data.columns:
                    if c.lower() == col.lower():
                        found = True
                        break
                if not found:
                    raise ValueError(f"Data must contain '{col}' column")
    
    def _create_splits(self):
        """Create train/validation/holdout splits."""
        n = len(self.data)
        
        # Hold-out set (final 20%, never touched during optimization)
        holdout_size = int(n * self.config.holdout_ratio)
        self.holdout_data = self.data.iloc[-holdout_size:]
        self.working_data = self.data.iloc[:-holdout_size]
        
        logger.info(f"Data split: {len(self.working_data)} working, {len(self.holdout_data)} holdout")
    
    def _create_folds(self) -> List[Tuple[pd.DataFrame, pd.DataFrame]]:
        """Create walk-forward folds."""
        folds = []
        n = len(self.working_data)
        
        if self.config.wfo_type == WFOType.ROLLING:
            # Rolling window: fixed size that moves forward
            fold_size = n // self.config.num_folds
            train_size = int(fold_size * (self.config.train_ratio / (self.config.train_ratio + self.config.validation_ratio)))
            test_size = fold_size - train_size
            
            for i in range(self.config.num_folds):
                start_idx = i * fold_size
                train_end = start_idx + train_size
                test_end = min(train_end + test_size, n)
                
                if train_end - start_idx >= self.config.min_train_samples and \
                   test_end - train_end >= self.config.min_test_samples:
                    train_data = self.working_data.iloc[start_idx:train_end]
                    test_data = self.working_data.iloc[train_end:test_end]
                    folds.append((train_data, test_data))
        
        else:  # ANCHORED
            # Anchored window: start fixed, end expands
            test_size = len(self.working_data) // (self.config.num_folds + 1)
            
            for i in range(self.config.num_folds):
                train_end = (i + 1) * test_size + self.config.min_train_samples
                test_start = train_end
                test_end = min(test_start + test_size, n)
                
                if train_end <= n and test_end - test_start >= self.config.min_test_samples:
                    train_data = self.working_data.iloc[:train_end]
                    test_data = self.working_data.iloc[test_start:test_end]
                    folds.append((train_data, test_data))
        
        return folds
    
    def _calculate_metrics(
        self,
        returns: pd.Series,
        include_slippage: bool = True
    ) -> Dict[str, float]:
        """Calculate performance metrics from returns."""
        if len(returns) == 0 or returns.isna().all():
            return {
                'total_return': 0.0,
                'sharpe_ratio': 0.0,
                'max_drawdown': 0.0,
                'profit_factor': 0.0,
                'win_rate': 0.0,
                'num_trades': 0
            }
        
        # Apply slippage
        if include_slippage and self.config.slippage_pct > 0:
            # Reduce returns by slippage (rough estimate)
            returns = returns - self.config.slippage_pct / 100
        
        # Total return
        total_return = (1 + returns).prod() - 1
        
        # Sharpe ratio (annualized, assuming daily returns)
        if returns.std() > 0:
            sharpe = (returns.mean() / returns.std()) * np.sqrt(252)
        else:
            sharpe = 0.0
        
        # Max drawdown
        cumulative = (1 + returns).cumprod()
        running_max = cumulative.cummax()
        drawdown = (cumulative - running_max) / running_max
        max_dd = abs(drawdown.min()) if len(drawdown) > 0 else 0.0
        
        # Profit factor
        gains = returns[returns > 0].sum()
        losses = abs(returns[returns < 0].sum())
        profit_factor = gains / losses if losses > 0 else float('inf')
        
        # Win rate
        wins = (returns > 0).sum()
        total_trades = (returns != 0).sum()
        win_rate = wins / total_trades if total_trades > 0 else 0.0
        
        return {
            'total_return': total_return,
            'sharpe_ratio': sharpe,
            'max_drawdown': max_dd,
            'profit_factor': profit_factor if profit_factor != float('inf') else 10.0,
            'win_rate': win_rate,
            'num_trades': int(total_trades)
        }
    
    def _run_fold(
        self,
        fold_id: int,
        train_data: pd.DataFrame,
        test_data: pd.DataFrame
    ) -> WFOResult:
        """Run a single walk-forward fold."""
        result = WFOResult(
            fold_id=fold_id,
            train_start=train_data.index[0],
            train_end=train_data.index[-1],
            test_start=test_data.index[0],
            test_end=test_data.index[-1]
        )
        
        try:
            # 1. Optimize on training data
            best_params = self.optimize_func(train_data)
            result.best_params = best_params
            
            # 2. Get in-sample signals and returns
            in_sample_signals = self.strategy_func(train_data, best_params)
            in_sample_returns = self._signals_to_returns(train_data, in_sample_signals)
            in_sample_metrics = self._calculate_metrics(in_sample_returns)
            
            result.in_sample_return = in_sample_metrics['total_return']
            result.in_sample_sharpe = in_sample_metrics['sharpe_ratio']
            result.in_sample_drawdown = in_sample_metrics['max_drawdown']
            
            # 3. Get out-of-sample signals and returns (CRITICAL: use same params)
            out_sample_signals = self.strategy_func(test_data, best_params)
            out_sample_returns = self._signals_to_returns(test_data, out_sample_signals)
            out_sample_metrics = self._calculate_metrics(out_sample_returns)
            
            result.out_sample_return = out_sample_metrics['total_return']
            result.out_sample_sharpe = out_sample_metrics['sharpe_ratio']
            result.out_sample_drawdown = out_sample_metrics['max_drawdown']
            result.num_trades = out_sample_metrics['num_trades']
            result.win_rate = out_sample_metrics['win_rate']
            result.profit_factor = out_sample_metrics['profit_factor']
            
            logger.debug(f"Fold {fold_id}: IS={result.in_sample_return:.2%}, OOS={result.out_sample_return:.2%}")
            
        except Exception as e:
            logger.error(f"Error in fold {fold_id}: {e}")
            warnings.warn(f"Fold {fold_id} failed: {e}")
        
        return result
    
    def _signals_to_returns(
        self,
        data: pd.DataFrame,
        signals: pd.Series
    ) -> pd.Series:
        """Convert signals to returns."""
        # Get close prices (handle case variations)
        close_col = None
        for col in data.columns:
            if col.lower() == 'close':
                close_col = col
                break
        
        if close_col is None:
            raise ValueError("Cannot find 'close' column in data")
        
        prices = data[close_col]
        
        # Calculate returns
        price_returns = prices.pct_change()
        
        # Strategy returns = signal * price returns (shifted to avoid look-ahead)
        strategy_returns = signals.shift(1) * price_returns
        
        return strategy_returns.dropna()
    
    def _calculate_wfe(self, folds: List[WFOResult]) -> float:
        """
        Calculate Walk-Forward Efficiency.
        
        WFE = Average(OOS Return) / Average(IS Return)
        
        Good WFE: > 0.5 (OOS performance is at least 50% of IS)
        """
        in_sample_returns = [f.in_sample_return for f in folds if f.in_sample_return != 0]
        out_sample_returns = [f.out_sample_return for f in folds]
        
        if not in_sample_returns or np.mean(in_sample_returns) == 0:
            return 0.0
        
        avg_is = np.mean(in_sample_returns)
        avg_oos = np.mean(out_sample_returns)
        
        # WFE can be negative if OOS loses money
        wfe = avg_oos / avg_is if avg_is > 0 else 0.0
        
        return wfe
    
    def _calculate_param_stability(self, folds: List[WFOResult]) -> Dict[str, float]:
        """Calculate parameter stability across folds."""
        if not folds or not folds[0].best_params:
            return {}
        
        stability = {}
        param_keys = folds[0].best_params.keys()
        
        for key in param_keys:
            values = [f.best_params.get(key) for f in folds if key in f.best_params]
            if values and all(isinstance(v, (int, float)) for v in values):
                mean_val = np.mean(values)
                std_val = np.std(values)
                cv = std_val / mean_val if mean_val != 0 else 0
                stability[key] = cv  # Coefficient of variation
        
        return stability
    
    def run(self) -> WFOSummary:
        """
        Run complete Walk-Forward Optimization.
        
        Returns:
            WFOSummary with all results and validation
        """
        logger.info("Starting Walk-Forward Optimization...")
        
        # Create folds
        folds_data = self._create_folds()
        logger.info(f"Created {len(folds_data)} folds")
        
        # Run each fold
        results = []
        for i, (train, test) in enumerate(folds_data):
            logger.info(f"Running fold {i+1}/{len(folds_data)}...")
            result = self._run_fold(i, train, test)
            results.append(result)
        
        # Calculate aggregate metrics
        wfe = self._calculate_wfe(results)
        param_stability = self._calculate_param_stability(results)
        
        # Aggregate returns
        oos_returns = [r.out_sample_return for r in results]
        total_return = np.prod([1 + r for r in oos_returns]) - 1
        avg_return = np.mean(oos_returns)
        
        # Aggregate Sharpe
        sharpes = [r.out_sample_sharpe for r in results if r.out_sample_sharpe != 0]
        avg_sharpe = np.mean(sharpes) if sharpes else 0
        
        # Max drawdown across folds
        max_dd = max([r.out_sample_drawdown for r in results]) if results else 0
        
        # Profit factor
        pfs = [r.profit_factor for r in results if r.profit_factor > 0 and r.profit_factor < 100]
        avg_pf = np.mean(pfs) if pfs else 0
        
        # Validation
        failure_reasons = []
        
        if wfe < self.config.min_wfe:
            failure_reasons.append(f"WFE {wfe:.2f} < {self.config.min_wfe} (overfitting likely)")
        
        if avg_sharpe < self.config.min_sharpe:
            failure_reasons.append(f"Sharpe {avg_sharpe:.2f} < {self.config.min_sharpe}")
        
        if max_dd > self.config.max_drawdown:
            failure_reasons.append(f"Drawdown {max_dd:.2%} > {self.config.max_drawdown:.0%}")
        
        if avg_pf < self.config.min_profit_factor:
            failure_reasons.append(f"Profit Factor {avg_pf:.2f} < {self.config.min_profit_factor}")
        
        # Check param stability
        for param, cv in param_stability.items():
            if cv > self.config.parameter_stability_threshold:
                failure_reasons.append(f"Param '{param}' unstable (CV={cv:.2f})")
        
        passed = len(failure_reasons) == 0
        
        summary = WFOSummary(
            config=self.config,
            folds=results,
            total_return=total_return,
            avg_return_per_fold=avg_return,
            wfe=wfe,
            sharpe_ratio=avg_sharpe,
            max_drawdown=max_dd,
            profit_factor=avg_pf,
            passed=passed,
            failure_reasons=failure_reasons,
            param_stability=param_stability
        )
        
        logger.info(f"WFO Complete: {'PASSED' if passed else 'FAILED'} (WFE={wfe:.2f})")
        
        return summary
    
    def run_final_test(self, best_params: Dict) -> Dict[str, float]:
        """
        Run final test on hold-out data.
        
        This should only be called ONCE at the very end.
        
        Args:
            best_params: Best parameters from WFO
            
        Returns:
            Hold-out test results
        """
        logger.warning("Running FINAL hold-out test. This should only happen once!")
        
        signals = self.strategy_func(self.holdout_data, best_params)
        returns = self._signals_to_returns(self.holdout_data, signals)
        metrics = self._calculate_metrics(returns)
        
        return {
            'holdout_start': self.holdout_data.index[0],
            'holdout_end': self.holdout_data.index[-1],
            'holdout_samples': len(self.holdout_data),
            **metrics
        }


# ═══════════════════════════════════════════════════════════════════════════════
#                           MONTE CARLO SIMULATION
# ═══════════════════════════════════════════════════════════════════════════════

class MonteCarloSimulator:
    """
    Monte Carlo simulation for strategy robustness testing.
    
    Generates random variations of trade sequences to estimate
    confidence intervals and worst-case scenarios.
    """
    
    def __init__(self, n_simulations: int = 1000, seed: int = 42):
        self.n_simulations = n_simulations
        self.seed = seed
        np.random.seed(seed)
    
    def simulate_returns(
        self,
        trade_returns: np.ndarray,
        confidence_levels: List[float] = [0.05, 0.25, 0.50, 0.75, 0.95]
    ) -> Dict[str, Any]:
        """
        Run Monte Carlo simulation on trade returns.
        
        Args:
            trade_returns: Array of individual trade returns
            confidence_levels: Percentiles to calculate
            
        Returns:
            Dict with simulation results
        """
        n_trades = len(trade_returns)
        if n_trades == 0:
            return {'error': 'No trades to simulate'}
        
        # Simulate by resampling trade returns
        simulated_finals = []
        simulated_drawdowns = []
        
        for _ in range(self.n_simulations):
            # Bootstrap resample
            resampled = np.random.choice(trade_returns, size=n_trades, replace=True)
            
            # Calculate cumulative return
            cumulative = np.cumprod(1 + resampled)
            final_return = cumulative[-1] - 1
            simulated_finals.append(final_return)
            
            # Calculate max drawdown
            running_max = np.maximum.accumulate(cumulative)
            drawdown = (cumulative - running_max) / running_max
            max_dd = np.abs(drawdown).max()
            simulated_drawdowns.append(max_dd)
        
        # Calculate percentiles
        return_percentiles = np.percentile(simulated_finals, [p * 100 for p in confidence_levels])
        dd_percentiles = np.percentile(simulated_drawdowns, [p * 100 for p in confidence_levels])
        
        return {
            'n_simulations': self.n_simulations,
            'n_trades': n_trades,
            'mean_return': np.mean(simulated_finals),
            'std_return': np.std(simulated_finals),
            'mean_drawdown': np.mean(simulated_drawdowns),
            'worst_return': np.min(simulated_finals),
            'best_return': np.max(simulated_finals),
            'worst_drawdown': np.max(simulated_drawdowns),
            'return_percentiles': dict(zip(confidence_levels, return_percentiles)),
            'drawdown_percentiles': dict(zip(confidence_levels, dd_percentiles)),
            'probability_of_loss': np.mean(np.array(simulated_finals) < 0)
        }


# ═══════════════════════════════════════════════════════════════════════════════
#                           UTILITY FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def print_wfo_summary(summary: WFOSummary):
    """Print formatted WFO summary."""
    print(f"\n{'='*60}")
    print(f"WALK-FORWARD OPTIMIZATION RESULTS")
    print(f"{'='*60}")
    
    status = "✅ PASSED" if summary.passed else "❌ FAILED"
    print(f"\nStatus: {status}")
    
    print(f"\nPerformance Metrics:")
    print(f"  Total Return:     {summary.total_return:.2%}")
    print(f"  Avg Return/Fold:  {summary.avg_return_per_fold:.2%}")
    print(f"  Walk-Forward Eff: {summary.wfe:.2f} (min: {summary.config.min_wfe})")
    print(f"  Sharpe Ratio:     {summary.sharpe_ratio:.2f} (min: {summary.config.min_sharpe})")
    print(f"  Max Drawdown:     {summary.max_drawdown:.2%} (max: {summary.config.max_drawdown:.0%})")
    print(f"  Profit Factor:    {summary.profit_factor:.2f} (min: {summary.config.min_profit_factor})")
    
    print(f"\nFold Results:")
    for fold in summary.folds:
        print(f"  Fold {fold.fold_id}: IS={fold.in_sample_return:.2%}, OOS={fold.out_sample_return:.2%}, "
              f"Trades={fold.num_trades}, WR={fold.win_rate:.1%}")
    
    if summary.param_stability:
        print(f"\nParameter Stability (CV):")
        for param, cv in summary.param_stability.items():
            status = "✓" if cv <= summary.config.parameter_stability_threshold else "✗"
            print(f"  {param}: {cv:.2f} {status}")
    
    if summary.failure_reasons:
        print(f"\n⚠️ Failure Reasons:")
        for reason in summary.failure_reasons:
            print(f"  - {reason}")
    
    print(f"{'='*60}\n")


# ═══════════════════════════════════════════════════════════════════════════════
#                           MAIN (Demo)
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Demo with synthetic data
    print("Walk-Forward Optimization Demo")
    print("-" * 40)
    
    # Create sample data
    np.random.seed(42)
    dates = pd.date_range('2020-01-01', periods=1000, freq='D')
    prices = 100 * np.cumprod(1 + np.random.randn(1000) * 0.02)
    data = pd.DataFrame({
        'close': prices,
        'high': prices * 1.01,
        'low': prices * 0.99,
        'open': prices,
        'volume': np.random.randint(1000, 10000, 1000)
    }, index=dates)
    
    # Simple strategy function (for demo)
    def simple_strategy(data, params):
        """Simple moving average crossover strategy."""
        fast = params.get('fast', 10)
        slow = params.get('slow', 30)
        
        close = data['close']
        fast_ma = close.rolling(fast).mean()
        slow_ma = close.rolling(slow).mean()
        
        signals = pd.Series(0, index=data.index)
        signals[fast_ma > slow_ma] = 1
        signals[fast_ma < slow_ma] = -1
        
        return signals
    
    # Simple optimizer (for demo)
    def simple_optimizer(data):
        """Find best MA parameters."""
        # In real use, this would search parameter space
        return {'fast': 10, 'slow': 30}
    
    # Run WFO
    wfo = WalkForwardOptimizer(
        data=data,
        strategy_func=simple_strategy,
        optimize_func=simple_optimizer,
        config=WFOConfig(num_folds=4)
    )
    
    summary = wfo.run()
    print_wfo_summary(summary)
    
    # Monte Carlo
    print("\nMonte Carlo Simulation:")
    mc = MonteCarloSimulator(n_simulations=1000)
    trade_returns = np.random.randn(100) * 0.02  # Sample trade returns
    mc_results = mc.simulate_returns(trade_returns)
    print(f"  Mean Return: {mc_results['mean_return']:.2%}")
    print(f"  5th Percentile: {mc_results['return_percentiles'][0.05]:.2%}")
    print(f"  95th Percentile: {mc_results['return_percentiles'][0.95]:.2%}")
    print(f"  Probability of Loss: {mc_results['probability_of_loss']:.1%}")
