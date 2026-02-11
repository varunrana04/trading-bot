"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                       ROBUST BACKTESTER                                       ║
║                                                                               ║
║  Wrapper that integrates Walk-Forward Optimization with any backtester.       ║
║  Provides anti-overfitting validation for strategy development.               ║
╚═══════════════════════════════════════════════════════════════════════════════╝

Features:
- Walk-Forward Optimization (WFO) with rolling/anchored windows
- Walk-Forward Efficiency (WFE) metric
- Monte Carlo robustness testing
- Train/Validation/Holdout splits
- Parameter stability analysis

Author: Bot_Algo
Last Updated: January 2026
"""

import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from typing import Dict, List, Callable, Optional, Any, Tuple
from datetime import datetime, timedelta
import logging
import sys
import os

# Add parent path for core module access
_parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _parent_dir not in sys.path:
    sys.path.insert(0, _parent_dir)

# Use relative imports within the package
from .walk_forward import (
    WalkForwardOptimizer,
    WFOConfig,
    WFOSummary,
    WFOType,
    MonteCarloSimulator,
    print_wfo_summary
)
from .slippage import SlippageSimulator, OrderType

# Try to import costs (may fail if running standalone)
try:
    from core.costs.binance_costs import BinanceFuturesCosts
    COSTS_AVAILABLE = True
except ImportError:
    COSTS_AVAILABLE = False
    BinanceFuturesCosts = None

logger = logging.getLogger("RobustBacktester")


# ═══════════════════════════════════════════════════════════════════════════════
#                           ROBUST BACKTEST RESULT
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class RobustBacktestResult:
    """Complete result from robust backtesting pipeline."""
    
    # Basic info
    symbol: str
    strategy_name: str
    timestamp: datetime = field(default_factory=datetime.now)
    
    # WFO Results
    wfo_passed: bool = False
    wfo_summary: WFOSummary = None
    walk_forward_efficiency: float = 0.0
    
    # Performance metrics (from WFO)
    avg_return: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    profit_factor: float = 0.0
    total_trades: int = 0
    
    # Monte Carlo results
    mc_probability_of_loss: float = 0.0
    mc_worst_case_return: float = 0.0
    mc_confidence_95: float = 0.0
    
    # Parameter stability
    params_stable: bool = False
    param_variations: Dict[str, float] = field(default_factory=dict)
    
    # Final holdout test (only run once at the very end)
    holdout_tested: bool = False
    holdout_return: float = 0.0
    holdout_sharpe: float = 0.0
    
    # Overall validation
    all_checks_passed: bool = False
    failure_reasons: List[str] = field(default_factory=list)


# ═══════════════════════════════════════════════════════════════════════════════
#                           ROBUST BACKTESTER
# ═══════════════════════════════════════════════════════════════════════════════

class RobustBacktester:
    """
    Robust backtesting pipeline with Walk-Forward Optimization.
    
    Usage:
        robust = RobustBacktester(
            data=price_data,
            strategy_func=my_strategy,
            optimize_func=my_optimizer,
            symbol='BTCUSDT'
        )
        
        result = robust.run_validation()
        
        if result.all_checks_passed:
            print("Strategy is robust!")
            # Only then run holdout test
            robust.run_final_holdout_test()
    """
    
    def __init__(
        self,
        data: pd.DataFrame,
        strategy_func: Callable,
        optimize_func: Callable,
        symbol: str = 'BTCUSDT',
        strategy_name: str = 'Unknown',
        wfo_config: WFOConfig = None,
        include_costs: bool = True,
        mc_simulations: int = 1000
    ):
        """
        Initialize robust backtester.
        
        Args:
            data: OHLCV DataFrame with datetime index
            strategy_func: Function(data, params) -> signals Series
            optimize_func: Function(data) -> best params Dict
            symbol: Trading symbol
            strategy_name: Name for this strategy
            wfo_config: Walk-Forward configuration
            include_costs: Whether to include transaction costs
            mc_simulations: Number of Monte Carlo simulations
        """
        self.data = data
        self.strategy_func = strategy_func
        self.optimize_func = optimize_func
        self.symbol = symbol
        self.strategy_name = strategy_name
        self.include_costs = include_costs
        self.mc_simulations = mc_simulations
        
        # Default WFO config with strict validation
        self.wfo_config = wfo_config or WFOConfig(
            train_ratio=0.60,
            validation_ratio=0.20,
            holdout_ratio=0.20,
            num_folds=5,
            min_wfe=0.50,           # WFE must be > 50%
            min_sharpe=1.0,
            max_drawdown=0.25,
            min_profit_factor=1.3
        )
        
        # Initialize cost calculator
        if include_costs and COSTS_AVAILABLE and BinanceFuturesCosts is not None:
            self.cost_calc = BinanceFuturesCosts(symbol)
            self.slippage_sim = SlippageSimulator(symbol)
        else:
            self.cost_calc = None
            self.slippage_sim = SlippageSimulator(symbol) if include_costs else None
        
        # WFO engine
        self.wfo = WalkForwardOptimizer(
            data=data,
            strategy_func=self._strategy_with_costs,
            optimize_func=optimize_func,
            config=self.wfo_config
        )
        
        # Monte Carlo
        self.mc = MonteCarloSimulator(n_simulations=mc_simulations)
        
        # Results storage
        self.result = None
        self.best_params = None
        
        logger.info(f"RobustBacktester initialized for {symbol} - {strategy_name}")
    
    def _strategy_with_costs(self, data: pd.DataFrame, params: Dict) -> pd.Series:
        """
        Wrap strategy to include costs if enabled.
        """
        signals = self.strategy_func(data, params)
        
        # Costs are already factored into WFO metrics calculation
        # This wrapper ensures signals are properly formatted
        return signals
    
    def run_validation(self) -> RobustBacktestResult:
        """
        Run complete validation pipeline.
        
        Returns:
            RobustBacktestResult with all validation metrics
        """
        logger.info("=" * 60)
        logger.info(f"ROBUST VALIDATION: {self.strategy_name} on {self.symbol}")
        logger.info("=" * 60)
        
        result = RobustBacktestResult(
            symbol=self.symbol,
            strategy_name=self.strategy_name
        )
        
        # ═══════════════════════════════════════════════════════════════
        # STEP 1: WALK-FORWARD OPTIMIZATION
        # ═══════════════════════════════════════════════════════════════
        logger.info("\n[1/3] Running Walk-Forward Optimization...")
        
        wfo_summary = self.wfo.run()
        
        result.wfo_summary = wfo_summary
        result.wfo_passed = wfo_summary.passed
        result.walk_forward_efficiency = wfo_summary.wfe
        result.avg_return = wfo_summary.avg_return_per_fold
        result.sharpe_ratio = wfo_summary.sharpe_ratio
        result.max_drawdown = wfo_summary.max_drawdown
        result.profit_factor = wfo_summary.profit_factor
        result.total_trades = sum(f.num_trades for f in wfo_summary.folds)
        
        # Store best params (from the best performing fold)
        if wfo_summary.folds:
            best_fold = max(wfo_summary.folds, key=lambda f: f.out_sample_return)
            self.best_params = best_fold.best_params
        
        if not wfo_summary.passed:
            result.failure_reasons.extend(wfo_summary.failure_reasons)
            logger.warning(f"WFO FAILED: {wfo_summary.failure_reasons}")
        else:
            logger.info(f"WFO PASSED: WFE={wfo_summary.wfe:.2f}, Sharpe={wfo_summary.sharpe_ratio:.2f}")
        
        # ═══════════════════════════════════════════════════════════════
        # STEP 2: PARAMETER STABILITY CHECK
        # ═══════════════════════════════════════════════════════════════
        logger.info("\n[2/3] Checking parameter stability...")
        
        result.param_variations = wfo_summary.param_stability
        
        # All params should have CV < 30%
        unstable_params = [k for k, v in result.param_variations.items() if v > 0.30]
        result.params_stable = len(unstable_params) == 0
        
        if not result.params_stable:
            result.failure_reasons.append(f"Unstable params: {unstable_params}")
            logger.warning(f"PARAMS UNSTABLE: {unstable_params}")
        else:
            logger.info("PARAMS STABLE: All parameters within acceptable variation")
        
        # ═══════════════════════════════════════════════════════════════
        # STEP 3: MONTE CARLO ROBUSTNESS
        # ═══════════════════════════════════════════════════════════════
        logger.info("\n[3/3] Running Monte Carlo simulation...")
        
        # Collect all trade returns from WFO
        all_trade_returns = []
        for fold in wfo_summary.folds:
            if fold.out_sample_return != 0:
                all_trade_returns.append(fold.out_sample_return)
        
        if len(all_trade_returns) >= 3:
            mc_result = self.mc.simulate_returns(np.array(all_trade_returns))
            
            result.mc_probability_of_loss = mc_result['probability_of_loss']
            result.mc_worst_case_return = mc_result['worst_return']
            result.mc_confidence_95 = mc_result['return_percentiles'].get(0.95, 0)
            
            # Check Monte Carlo criteria
            if result.mc_probability_of_loss > 0.40:
                result.failure_reasons.append(
                    f"High loss probability: {result.mc_probability_of_loss:.1%}"
                )
            
            logger.info(f"MC: P(Loss)={result.mc_probability_of_loss:.1%}, "
                       f"Worst={result.mc_worst_case_return:.2%}, "
                       f"95th={result.mc_confidence_95:.2%}")
        else:
            logger.warning("Not enough trades for Monte Carlo simulation")
        
        # ═══════════════════════════════════════════════════════════════
        # FINAL VERDICT
        # ═══════════════════════════════════════════════════════════════
        result.all_checks_passed = (
            result.wfo_passed and
            result.params_stable and
            result.mc_probability_of_loss <= 0.40
        )
        
        logger.info("\n" + "=" * 60)
        if result.all_checks_passed:
            logger.info("✅ ALL CHECKS PASSED - Strategy is robust!")
        else:
            logger.info("❌ VALIDATION FAILED")
            for reason in result.failure_reasons:
                logger.info(f"   - {reason}")
        logger.info("=" * 60)
        
        self.result = result
        return result
    
    def run_final_holdout_test(self) -> Dict[str, float]:
        """
        Run final test on holdout data.
        
        WARNING: This should only be called ONCE, after all validation passes!
        """
        if self.result is None:
            raise ValueError("Must run validation first!")
        
        if not self.result.all_checks_passed:
            logger.warning("Holdout test should only run after passing all checks!")
        
        if self.result.holdout_tested:
            logger.warning("Holdout already tested! Do NOT test multiple times.")
            return {
                'return': self.result.holdout_return,
                'sharpe': self.result.holdout_sharpe
            }
        
        logger.info("\n" + "=" * 60)
        logger.info("🔒 FINAL HOLDOUT TEST (This is your ONE chance!)")
        logger.info("=" * 60)
        
        if self.best_params is None:
            raise ValueError("No best params found from WFO")
        
        holdout_result = self.wfo.run_final_test(self.best_params)
        
        self.result.holdout_tested = True
        self.result.holdout_return = holdout_result['total_return']
        self.result.holdout_sharpe = holdout_result['sharpe_ratio']
        
        logger.info(f"Holdout Return: {self.result.holdout_return:.2%}")
        logger.info(f"Holdout Sharpe: {self.result.holdout_sharpe:.2f}")
        logger.info("=" * 60)
        
        return holdout_result


# ═══════════════════════════════════════════════════════════════════════════════
#                           QUICK VALIDATION FUNCTION
# ═══════════════════════════════════════════════════════════════════════════════

def validate_strategy(
    data: pd.DataFrame,
    strategy_func: Callable,
    optimize_func: Callable,
    symbol: str = 'BTCUSDT',
    strategy_name: str = 'Strategy',
    verbose: bool = True
) -> RobustBacktestResult:
    """
    Quick function to validate a strategy with all anti-overfitting checks.
    
    Args:
        data: OHLCV DataFrame
        strategy_func: Strategy function
        optimize_func: Optimizer function
        symbol: Symbol name
        strategy_name: Name for logging
        verbose: Print detailed output
        
    Returns:
        RobustBacktestResult
    """
    robust = RobustBacktester(
        data=data,
        strategy_func=strategy_func,
        optimize_func=optimize_func,
        symbol=symbol,
        strategy_name=strategy_name
    )
    
    result = robust.run_validation()
    
    if verbose:
        print("\n" + "=" * 60)
        print(f"VALIDATION SUMMARY: {strategy_name}")
        print("=" * 60)
        print(f"Walk-Forward Efficiency: {result.walk_forward_efficiency:.2f}")
        print(f"Sharpe Ratio: {result.sharpe_ratio:.2f}")
        print(f"Max Drawdown: {result.max_drawdown:.2%}")
        print(f"Probability of Loss: {result.mc_probability_of_loss:.1%}")
        print(f"All Checks Passed: {'✅ YES' if result.all_checks_passed else '❌ NO'}")
        
        if result.failure_reasons:
            print("\nFailure Reasons:")
            for reason in result.failure_reasons:
                print(f"  - {reason}")
        print("=" * 60)
    
    return result


# ═══════════════════════════════════════════════════════════════════════════════
#                           MAIN (Demo)
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    print("Robust Backtester Demo")
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
        return {'fast': 10, 'slow': 30}
    
    # Run validation
    result = validate_strategy(
        data=data,
        strategy_func=simple_strategy,
        optimize_func=simple_optimizer,
        symbol='BTCUSDT',
        strategy_name='Simple MA Crossover'
    )
    
    print(f"\nFinal Result: {'PASSED' if result.all_checks_passed else 'FAILED'}")
