"""
Scheduled Re-Optimization — Compare current params vs fresh optimization.

Checks if current trading parameters are still optimal by comparing
recent performance against fresh Bayesian optimization results.
Alerts if Sharpe ratio has dropped significantly.

Usage:
    python scripts/scheduled_reopt.py
    # Or via cron: 0 0 * * 0 python scripts/scheduled_reopt.py
"""

import sys
import os
import json
import logging
from pathlib import Path
from datetime import datetime

# Add root to path
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

logger = logging.getLogger("ScheduledReopt")


def load_current_performance() -> dict:
    """Load recent trading performance from trade logs."""
    import glob
    
    json_files = glob.glob("results/paper_trades/*.json")
    all_trades = []
    
    for f in json_files:
        try:
            with open(f, 'r') as fh:
                trades = json.load(fh)
                all_trades.extend(trades)
        except Exception:
            continue
    
    if not all_trades:
        return {"trades": 0, "sharpe": 0, "win_rate": 0, "pnl": 0}
    
    import numpy as np
    
    pnl_col = 'pnl' if 'pnl' in all_trades[0] else 'pnl_usd'
    returns = [t.get(pnl_col, 0) for t in all_trades]
    
    wins = sum(1 for r in returns if r > 0)
    total = len(returns)
    win_rate = (wins / total * 100) if total > 0 else 0
    
    arr = np.array(returns)
    sharpe = (np.mean(arr) / np.std(arr) * np.sqrt(252)) if np.std(arr) > 0 else 0
    
    return {
        "trades": total,
        "sharpe": round(sharpe, 2),
        "win_rate": round(win_rate, 1),
        "pnl": round(sum(returns), 2),
        "avg_return": round(np.mean(arr), 2) if len(arr) > 0 else 0
    }


def load_baseline_performance() -> dict:
    """Load baseline metrics from last optimization run."""
    baseline_file = "results/optimization_baseline.json"
    
    if os.path.exists(baseline_file):
        with open(baseline_file, 'r') as f:
            return json.load(f)
    
    return {"sharpe": 1.0, "win_rate": 50.0, "timestamp": "never"}


def save_baseline(metrics: dict):
    """Save current metrics as new baseline."""
    baseline_file = "results/optimization_baseline.json"
    metrics["timestamp"] = datetime.now().isoformat()
    
    os.makedirs("results", exist_ok=True)
    with open(baseline_file, 'w') as f:
        json.dump(metrics, f, indent=2)
    
    logger.info(f"Saved new baseline: Sharpe={metrics['sharpe']}, WR={metrics['win_rate']}%")


def check_reoptimization_needed(current: dict, baseline: dict, 
                                  sharpe_threshold: float = 0.20) -> dict:
    """
    Compare current performance to baseline.
    
    Args:
        current: Current performance metrics
        baseline: Baseline from last optimization
        sharpe_threshold: Alert if Sharpe dropped by this fraction (20%)
    
    Returns:
        Dict with recommendation
    """
    result = {
        "timestamp": datetime.now().isoformat(),
        "current": current,
        "baseline": baseline,
        "needs_reopt": False,
        "reasons": []
    }
    
    if current["trades"] < 10:
        result["reasons"].append(f"Insufficient data ({current['trades']} trades, need 10+)")
        return result
    
    # Check Sharpe degradation
    baseline_sharpe = baseline.get("sharpe", 1.0)
    if baseline_sharpe > 0:
        sharpe_change = (current["sharpe"] - baseline_sharpe) / baseline_sharpe
        if sharpe_change < -sharpe_threshold:
            result["needs_reopt"] = True
            result["reasons"].append(
                f"Sharpe degraded {sharpe_change*100:.0f}% "
                f"({baseline_sharpe} -> {current['sharpe']})"
            )
    
    # Check win rate drop
    baseline_wr = baseline.get("win_rate", 50.0)
    if baseline_wr > 0:
        wr_drop = baseline_wr - current["win_rate"]
        if wr_drop > 10:  # More than 10pp drop
            result["needs_reopt"] = True
            result["reasons"].append(
                f"Win rate dropped {wr_drop:.0f}pp "
                f"({baseline_wr:.0f}% -> {current['win_rate']:.0f}%)"
            )
    
    # Check negative PnL
    if current["pnl"] < 0 and current["trades"] >= 20:
        result["needs_reopt"] = True
        result["reasons"].append(f"Net negative P&L: ${current['pnl']:.2f}")
    
    if not result["reasons"]:
        result["reasons"].append("Performance within acceptable range")
    
    return result


def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    print("=" * 60)
    print("  SCHEDULED RE-OPTIMIZATION CHECK")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    current = load_current_performance()
    baseline = load_baseline_performance()
    
    print(f"\n  Current Performance:")
    print(f"    Trades:   {current['trades']}")
    print(f"    Sharpe:   {current['sharpe']}")
    print(f"    Win Rate: {current['win_rate']}%")
    print(f"    P&L:      ${current['pnl']:.2f}")
    
    print(f"\n  Baseline:")
    print(f"    Sharpe:   {baseline.get('sharpe', 'N/A')}")
    print(f"    Win Rate: {baseline.get('win_rate', 'N/A')}%")
    print(f"    Last Run: {baseline.get('timestamp', 'never')}")
    
    result = check_reoptimization_needed(current, baseline)
    
    print(f"\n  {'='*40}")
    if result["needs_reopt"]:
        print("  !! RE-OPTIMIZATION RECOMMENDED !!")
        for reason in result["reasons"]:
            print(f"    - {reason}")
        print(f"\n  Run: python scripts/bayesian_optimizer.py")
    else:
        print("  [OK] No re-optimization needed")
        for reason in result["reasons"]:
            print(f"    - {reason}")
    
    # Save report
    report_file = "results/reopt_check.json"
    os.makedirs("results", exist_ok=True)
    with open(report_file, 'w') as f:
        json.dump(result, f, indent=2)
    print(f"\n  Report saved: {report_file}")
    
    # Option to save current as new baseline
    if "--save-baseline" in sys.argv:
        save_baseline(current)
        print("  Baseline updated!")


if __name__ == "__main__":
    main()
