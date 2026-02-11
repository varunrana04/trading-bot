"""
P-Hacking Safeguards for Backtesting
-------------------------------------
Statistical safeguards to prevent optimizing illusions and ensure robustness.
"""

import numpy as np
from scipy import stats
from typing import Dict, List, Tuple, Optional
import warnings

class BacktestSafeguards:
    """
    Implements statistical safeguards against p-hacking and overfitting.
    
    Key Protections:
    1. Minimum Sample Size Requirements
    2. Walk-Forward Validation
    3. Multiple Testing Corrections (Bonferroni)
    4. Out-of-Sample Testing
    5. Monte Carlo Permutation Tests
   6. Sharpe Ratio Statistical Significance
    """
    
    @staticmethod
    def minimum_sample_size(
        expected_trades_per_month: int = 20,
        months_required: int = 3,
        confidence_level: float = 0.95
    ) -> int:
        """
        Calculate minimum required sample size for statistical significance.
        
        Rule of Thumb: At least 30 trades minimum, preferably 100+
        
        Args:
            expected_trades_per_month: Expected number of trades per month
            months_required: Minimum months of data required
            confidence_level: Statistical confidence level
            
        Returns:
            Minimum number of trades required
        """
        # Harris (2003): Minimum 30 trades for any statistical inference
        absolute_minimum = 30
        
        # Time-based minimum
        time_based_minimum = expected_trades_per_month * months_required
        
        # Statistical minimum (based on confidence level)
        # Z-score for desired confidence
        z_score = stats.norm.ppf((1 + confidence_level) / 2)
        statistical_minimum = int((z_score / 0.1) ** 2)  # For 10% margin of error
        
        return max(absolute_minimum, time_based_minimum, statistical_minimum)
    
    @staticmethod
    def bonferroni_correction(
        p_values: List[float],
        alpha: float = 0.05
    ) -> Tuple[List[bool], float]:
        """
        Apply Bonferroni correction for multiple testing.
        
        When testing multiple strategies/parameters, we must adjust the
        significance level to avoid false discoveries.
        
        Args:
            p_values: List of p-values from multiple tests
            alpha: Family-wise error rate (FWER)
            
        Returns:
            (list of booleans indicating significance, corrected alpha)
        """
        n_tests = len(p_values)
        corrected_alpha = alpha / n_tests
        
        significant = [p < corrected_alpha for p in p_values]
        
        return significant, corrected_alpha
    
    @staticmethod
    def walk_forward_analysis(
        returns: np.ndarray,
        in_sample_pct: float = 0.6,
        n_windows: int = 5
    ) -> Dict:
        """
        Perform walk-forward analysis to validate strategy robustness.
        
        Splits data into rolling windows of in-sample (optimization) and
        out-of-sample (validation) periods.
        
        Args:
            returns: Array of strategy returns
            in_sample_pct: Percentage of each window for optimization
            n_windows: Number of walk-forward windows
            
        Returns:
            Dictionary with walk-forward statistics
        """
        n = len(returns)
        window_size = n // n_windows
        
        results = {
            'in_sample_sharpe': [],
            'out_sample_sharpe': [],
            'degradation': []
        }
        
        for i in range(n_windows):
            start = i * window_size
            end = min((i + 1) * window_size, n)
            
            if end - start < 30:  # Skip if window too small
                continue
            
            split_point = start + int((end - start) * in_sample_pct)
            
            in_sample = returns[start:split_point]
            out_sample = returns[split_point:end]
            
            if len(in_sample) > 0 and len(out_sample) > 0:
                in_sharpe = np.mean(in_sample) / (np.std(in_sample) + 1e-10) * np.sqrt(252)
                out_sharpe = np.mean(out_sample) / (np.std(out_sample) + 1e-10) * np.sqrt(252)
                
                degradation = (in_sharpe - out_sharpe) / (abs(in_sharpe) + 1e-10)
                
                results['in_sample_sharpe'].append(in_sharpe)
                results['out_sample_sharpe'].append(out_sharpe)
                results['degradation'].append(degradation)
        
        # Summary statistics
        results['avg_degradation'] = np.mean(results['degradation']) if results['degradation'] else float('inf')
        results['is_robust'] = results['avg_degradation'] < 0.3  # Less than 30% degradation
        
        return results
    
    @staticmethod
    def monte_carlo_permutation_test(
        returns: np.ndarray,
        metric_func: callable = None,
        n_permutations: int = 1000,
        alpha: float = 0.05
    ) -> Dict:
        """
        Monte Carlo permutation test to check if results are statistically significant.
        
        Randomly permutes the returns to generate null distribution and
        checks if observed metric is significantly different.
        
        Args:
            returns: Strategy returns
            metric_func: Function to calculate metric (default: Sharpe ratio)
            n_permutations: Number of random permutations
            alpha: Significance level
            
        Returns:
            Dictionary with test results
        """
        if metric_func is None:
            metric_func = lambda r: np.mean(r) / (np.std(r) + 1e-10) * np.sqrt(252)
        
        # Observed metric
        observed_metric = metric_func(returns)
        
        # Generate null distribution
        null_distribution = []
        for _ in range(n_permutations):
            permuted = np.random.permutation(returns)
            null_distribution.append(metric_func(permuted))
        
        null_distribution = np.array(null_distribution)
        
        # Calculate p-value (two-tailed)
        p_value = np.mean(np.abs(null_distribution) >= abs(observed_metric))
        
        return {
            'observed_metric': observed_metric,
            'null_mean': np.mean(null_distribution),
            'null_std': np.std(null_distribution),
            'p_value': p_value,
            'is_significant': p_value < alpha,
            'percentile': stats.percentileofscore(null_distribution, observed_metric)
        }
    
    @staticmethod
    def sharpe_ratio_significance(
        returns: np.ndarray,
        alpha: float = 0.05
    ) -> Dict:
        """
        Test statistical significance of Sharpe ratio.
        
        Uses the method from Lo (2002) to test if Sharpe ratio is
        significantly different from zero.
        
        Args:
            returns: Strategy returns
            alpha: Significance level
            
        Returns:
            Dictionary with significance test results
        """
        n = len(returns)
        
        if n < 30:
            return {
                'sharpe': 0,
                'is_significant': False,
                'error': 'Insufficient sample size (< 30)'
            }
        
        # Calculate Sharpe ratio
        mean_return = np.mean(returns)
        std_return = np.std(returns, ddof=1)
        sharpe = (mean_return / (std_return + 1e-10)) * np.sqrt(252)
        
        # Standard error of Sharpe ratio (Lo, 2002)
        # SE = sqrt((1 + 0.5 * SR^2) / n)
        se_sharpe = np.sqrt((1 + 0.5 * sharpe**2) / n)
        
        # T-statistic
        t_stat = sharpe / (se_sharpe + 1e-10)
        
        # P-value (two-tailed)
        p_value = 2 * (1 - stats.t.cdf(abs(t_stat), n - 1))
        
        # Confidence interval
        ci_lower = sharpe - stats.t.ppf(1 - alpha/2, n - 1) * se_sharpe
        ci_upper = sharpe + stats.t.ppf(1 - alpha/2, n - 1) * se_sharpe
        
        return {
            'sharpe': sharpe,
            't_statistic': t_stat,
            'p_value': p_value,
            'is_significant': p_value < alpha,
            'confidence_interval': (ci_lower, ci_upper),
            'min_sharpe_for_significance': stats.t.ppf(1 - alpha/2, n - 1) * se_sharpe
        }
    
    @staticmethod
    def validate_backtest(
        returns: np.ndarray,
        n_trades: int,
        n_parameters_tested: int = 1,
        require_walk_forward: bool = True
    ) -> Dict:
        """
        Comprehensive backtest validation.
        
        Runs all safeguards and returns a report on statistical validity.
        
        Args:
            returns: Strategy returns
            n_trades: Number of trades executed
            n_parameters_tested: Number of different parameter combinations tested
            require_walk_forward: Whether to require walk-forward validation
            
        Returns:
            Validation report with all test results
        """
        report = {
            'valid': True,
            'warnings': [],
            'errors': []
        }
        
        # 1. Sample Size Check
        min_required = BacktestSafeguards.minimum_sample_size()
        if n_trades < min_required:
            report['valid'] = False
            report['errors'].append(
                f"Insufficient sample size: {n_trades} trades < {min_required} required"
            )
        
        # 2. Sharpe Ratio Significance
        sharpe_test = BacktestSafeguards.sharpe_ratio_significance(returns)
        report['sharpe_test'] = sharpe_test
        
        if not sharpe_test.get('is_significant', False):
            report['warnings'].append(
                f"Sharpe ratio not statistically significant (p={sharpe_test.get('p_value', 1.0):.3f})"
            )
        
        # 3. Multiple Testing Correction
        if n_parameters_tested > 1:
            # Approximate p-value adjustment
            corrected_alpha = 0.05 / n_parameters_tested
            report['bonferroni_alpha'] = corrected_alpha
            
            if sharpe_test.get('p_value', 1.0) > corrected_alpha:
                report['valid'] = False
                report['errors'].append(
                    f"Failed Bonferroni correction: p={sharpe_test.get('p_value', 1.0):.4f} > "
                    f"corrected α={corrected_alpha:.4f} ({n_parameters_tested} tests)"
                )
        
        # 4. Walk-Forward Analysis
        if require_walk_forward and len(returns) >= 100:
            wf_results = BacktestSafeguards.walk_forward_analysis(returns)
            report['walk_forward'] = wf_results
            
            if not wf_results['is_robust']:
                report['warnings'].append(
                    f"Poor out-of-sample performance: {wf_results['avg_degradation']:.1%} degradation"
                )
        
        # 5. Monte Carlo Test
        if len(returns) >= 30:
            mc_test = BacktestSafeguards.monte_carlo_permutation_test(returns)
            report['monte_carlo'] = mc_test
            
            if not mc_test['is_significant']:
                report['warnings'].append(
                    f"Failed Monte Carlo test (p={mc_test['p_value']:.3f})"
                )
        
        return report


# Example usage
if __name__ == "__main__":
    print("=" * 80)
    print("P-HACKING SAFEGUARDS - Statistical Validation")
    print("=" * 80)
    
    # Simulate strategy returns
    np.random.seed(42)
    n_trades = 100
    returns = np.random.normal(0.001, 0.02, n_trades)  # 0.1% mean, 2% std daily
    
    # Run validation
    report = BacktestSafeguards.validate_backtest(
        returns=returns,
        n_trades=n_trades,
        n_parameters_tested=10  # Tested 10 different parameter sets
    )
    
    print(f"\nBacktest Validation Report:")
    print(f"Valid: {report['valid']}")
    print(f"\nSharpe Ratio Test:")
    print(f"  Sharpe: {report['sharpe_test']['sharpe']:.2f}")
    print(f"  P-value: {report['sharpe_test']['p_value']:.4f}")
    print(f"  Significant: {report['sharpe_test']['is_significant']}")
    
    if report['errors']:
        print(f"\n❌ ERRORS:")
        for error in report['errors']:
            print(f"  - {error}")
    
    if report['warnings']:
        print(f"\n⚠️  WARNINGS:")
        for warning in report['warnings']:
            print(f"  - {warning}")
    
    print("\n" + "=" * 80)
