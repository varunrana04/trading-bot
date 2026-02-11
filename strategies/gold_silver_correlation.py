"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                       GOLD/SILVER CORRELATION STRATEGY                        ║
║                                                                               ║
║  Arbitrage and correlation-based trading between international and Indian    ║
║  gold/silver prices.                                                          ║
╚═══════════════════════════════════════════════════════════════════════════════╝

Strategy Logic:
- XAUUSD (International Gold) correlates with Nippon India ETF Gold BeES
- XAGUSD (International Silver) correlates with Nippon/Tata Silver ETFs
- Trade divergences when correlation breaks down temporarily

Use Cases:
1. Arbitrage: When INR-adjusted prices diverge significantly
2. Lead-Lag: International often leads Indian (time zone difference)
3. Mean Reversion: Trade spread when it deviates from norm

Author: Bot_Algo
Last Updated: January 2026
"""

import numpy as np
import pandas as pd
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional
from datetime import datetime
import logging

logger = logging.getLogger("GoldSilverStrategy")


# ═══════════════════════════════════════════════════════════════════════════════
#                           CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class GoldSilverConfig:
    """Configuration for gold/silver correlation strategy."""
    
    # Instrument mappings
    international_gold: str = 'XAUUSD'
    indian_gold_etf: str = 'GOLDBEES'
    international_silver: str = 'XAGUSD'
    indian_silver_etf: str = 'SILVERBEES'
    
    # Correlation parameters
    correlation_window: int = 20      # Days to calculate correlation
    min_correlation: float = 0.80     # Minimum correlation for pair trading
    
    # Spread parameters
    spread_window: int = 20           # Days for spread calculation
    entry_z_score: float = 2.0        # Z-score to enter spread trade
    exit_z_score: float = 0.5         # Z-score to exit
    
    # Lead-lag parameters
    lead_lag_window: int = 5          # Days to detect lead-lag
    min_lead_hours: int = 4           # Minimum lead time (hour difference)
    
    # Risk management
    max_position_pct: float = 0.10    # 10% of capital per trade
    stop_loss_z: float = 3.0          # Stop loss at 3 std dev
    
    # Currency
    default_usd_inr: float = 83.0     # Default USD/INR rate


# ═══════════════════════════════════════════════════════════════════════════════
#                           SPREAD CALCULATION
# ═══════════════════════════════════════════════════════════════════════════════

def calculate_spread(
    international_price: pd.Series,
    indian_price: pd.Series,
    usd_inr_rate: float = 83.0,
    gold_grams_per_oz: float = 31.1035
) -> pd.DataFrame:
    """
    Calculate spread between international and Indian gold/silver prices.
    
    Args:
        international_price: XAUUSD or XAGUSD prices (USD per oz)
        indian_price: Indian ETF prices (INR per unit/gram)
        usd_inr_rate: USD/INR exchange rate
        gold_grams_per_oz: Grams per troy ounce
        
    Returns:
        DataFrame with spread calculations
    """
    # Convert international to INR per gram
    international_inr = (international_price * usd_inr_rate) / gold_grams_per_oz
    
    # Calculate raw spread
    spread = international_inr - indian_price
    
    # Calculate spread percentage
    spread_pct = spread / indian_price * 100
    
    # Calculate z-score
    spread_mean = spread.rolling(20).mean()
    spread_std = spread.rolling(20).std()
    z_score = (spread - spread_mean) / spread_std
    
    return pd.DataFrame({
        'international_inr': international_inr,
        'indian_price': indian_price,
        'spread': spread,
        'spread_pct': spread_pct,
        'z_score': z_score,
        'spread_mean': spread_mean,
        'spread_std': spread_std
    })


def calculate_correlation(series1: pd.Series, series2: pd.Series, window: int = 20) -> pd.Series:
    """Calculate rolling correlation between two series."""
    return series1.rolling(window).corr(series2)


# ═══════════════════════════════════════════════════════════════════════════════
#                           SIGNAL GENERATION
# ═══════════════════════════════════════════════════════════════════════════════

def generate_signals_gold(
    international_df: pd.DataFrame,
    indian_df: pd.DataFrame,
    params: Dict = None
) -> pd.Series:
    """
    Generate trading signals for gold arbitrage.
    
    Strategy:
    - LONG Indian ETF when z-score < -2 (Indian undervalued)
    - SHORT Indian ETF when z-score > 2 (Indian overvalued)
    - EXIT when z-score returns to 0
    
    Note: This is a spread trade, so you'd simultaneously take
    opposite position in international gold.
    """
    config = GoldSilverConfig()
    if params:
        for k, v in params.items():
            if hasattr(config, k):
                setattr(config, k, v)
    
    # Get close prices
    intl_close = international_df['close']
    indian_close = indian_df['close']
    
    # Align data
    common_idx = intl_close.index.intersection(indian_close.index)
    intl_close = intl_close.loc[common_idx]
    indian_close = indian_close.loc[common_idx]
    
    # Calculate spread
    spread_df = calculate_spread(intl_close, indian_close, config.default_usd_inr)
    
    # Check correlation
    correlation = calculate_correlation(intl_close, indian_close, config.correlation_window)
    valid_corr = correlation >= config.min_correlation
    
    # Generate signals
    signals = pd.Series(0, index=common_idx)
    
    # Entry conditions
    long_entry = (spread_df['z_score'] < -config.entry_z_score) & valid_corr
    short_entry = (spread_df['z_score'] > config.entry_z_score) & valid_corr
    
    # Exit conditions
    exit_condition = abs(spread_df['z_score']) < config.exit_z_score
    
    # Stop loss
    stop_loss = abs(spread_df['z_score']) > config.stop_loss_z
    
    # Set signals
    signals[long_entry] = 1   # Long Indian (undervalued)
    signals[short_entry] = -1  # Short Indian (overvalued)
    
    # Forward fill positions
    position = 0
    for i in range(len(signals)):
        if signals.iloc[i] != 0:
            position = signals.iloc[i]
        elif position != 0 and (exit_condition.iloc[i] or stop_loss.iloc[i]):
            position = 0
        signals.iloc[i] = position
    
    return signals


def optimize_parameters_gold(
    international_df: pd.DataFrame,
    indian_df: pd.DataFrame
) -> Dict:
    """Return fixed parameters for gold strategy."""
    return {
        'entry_z_score': 2.0,
        'exit_z_score': 0.5,
        'correlation_window': 20,
        'min_correlation': 0.80
    }


# ═══════════════════════════════════════════════════════════════════════════════
#                           SILVER STRATEGY
# ═══════════════════════════════════════════════════════════════════════════════

def generate_signals_silver(
    international_df: pd.DataFrame,
    indian_df: pd.DataFrame,
    params: Dict = None
) -> pd.Series:
    """
    Generate trading signals for silver arbitrage.
    Uses same logic as gold with adjusted thresholds.
    Silver is more volatile, so wider entry bands.
    """
    config = GoldSilverConfig()
    config.entry_z_score = 2.5  # Wider for silver volatility
    config.exit_z_score = 0.75
    
    if params:
        for k, v in params.items():
            if hasattr(config, k):
                setattr(config, k, v)
    
    # Get close prices
    intl_close = international_df['close']
    indian_close = indian_df['close']
    
    # Align data
    common_idx = intl_close.index.intersection(indian_close.index)
    intl_close = intl_close.loc[common_idx]
    indian_close = indian_close.loc[common_idx]
    
    # Silver: 1 oz = 31.1035 grams (same as gold)
    spread_df = calculate_spread(intl_close, indian_close, config.default_usd_inr)
    
    # Check correlation (silver less correlated)
    correlation = calculate_correlation(intl_close, indian_close, config.correlation_window)
    valid_corr = correlation >= config.min_correlation * 0.9  # Lower threshold for silver
    
    # Generate signals
    signals = pd.Series(0, index=common_idx)
    
    long_entry = (spread_df['z_score'] < -config.entry_z_score) & valid_corr
    short_entry = (spread_df['z_score'] > config.entry_z_score) & valid_corr
    exit_condition = abs(spread_df['z_score']) < config.exit_z_score
    stop_loss = abs(spread_df['z_score']) > config.stop_loss_z
    
    signals[long_entry] = 1
    signals[short_entry] = -1
    
    position = 0
    for i in range(len(signals)):
        if signals.iloc[i] != 0:
            position = signals.iloc[i]
        elif position != 0 and (exit_condition.iloc[i] or stop_loss.iloc[i]):
            position = 0
        signals.iloc[i] = position
    
    return signals


# ═══════════════════════════════════════════════════════════════════════════════
#                           ANALYSIS TOOLS
# ═══════════════════════════════════════════════════════════════════════════════

def analyze_correlation(
    international_df: pd.DataFrame,
    indian_df: pd.DataFrame,
    metal: str = 'Gold'
) -> Dict:
    """
    Analyze correlation between international and Indian prices.
    
    Returns:
        Dict with correlation statistics
    """
    intl_close = international_df['close']
    indian_close = indian_df['close']
    
    common_idx = intl_close.index.intersection(indian_close.index)
    intl_close = intl_close.loc[common_idx]
    indian_close = indian_close.loc[common_idx]
    
    # Overall correlation
    overall_corr = intl_close.corr(indian_close)
    
    # Rolling correlation stats
    rolling_corr = calculate_correlation(intl_close, indian_close, 20)
    
    # Spread stats
    spread_df = calculate_spread(intl_close, indian_close)
    
    return {
        'metal': metal,
        'data_points': len(common_idx),
        'overall_correlation': overall_corr,
        'min_correlation': rolling_corr.min(),
        'max_correlation': rolling_corr.max(),
        'mean_correlation': rolling_corr.mean(),
        'mean_spread_pct': spread_df['spread_pct'].mean(),
        'std_spread_pct': spread_df['spread_pct'].std(),
        'max_z_score': spread_df['z_score'].max(),
        'min_z_score': spread_df['z_score'].min()
    }


# ═══════════════════════════════════════════════════════════════════════════════
#                           MAIN (Demo)
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    print("=" * 60)
    print("GOLD/SILVER CORRELATION STRATEGY - DEMO")
    print("=" * 60)
    
    # Generate synthetic data for demo
    np.random.seed(42)
    dates = pd.date_range('2024-01-01', periods=252, freq='D')
    
    # XAUUSD (Gold in USD/oz)
    gold_base = 2000
    gold_returns = np.random.randn(252) * 0.01
    gold_prices = gold_base * np.cumprod(1 + gold_returns)
    
    xauusd = pd.DataFrame({
        'open': gold_prices,
        'high': gold_prices * 1.005,
        'low': gold_prices * 0.995,
        'close': gold_prices,
        'volume': np.random.randint(10000, 50000, 252)
    }, index=dates)
    
    # Gold BeES (Indian ETF, INR/unit)
    # Should roughly track XAUUSD * USD_INR / 31.1 (grams per oz)
    usd_inr = 83
    etf_factor = usd_inr / 31.1
    noise = np.random.randn(252) * 0.005  # Add some tracking error
    etf_prices = gold_prices * etf_factor * (1 + noise)
    
    goldbees = pd.DataFrame({
        'open': etf_prices,
        'high': etf_prices * 1.003,
        'low': etf_prices * 0.997,
        'close': etf_prices,
        'volume': np.random.randint(100000, 500000, 252)
    }, index=dates)
    
    print(f"\nData: {len(dates)} trading days")
    print(f"XAUUSD range: ${gold_prices.min():.2f} - ${gold_prices.max():.2f}")
    print(f"GoldBeES range: Rs.{etf_prices.min():.2f} - Rs.{etf_prices.max():.2f}")
    
    # Analyze correlation
    analysis = analyze_correlation(xauusd, goldbees, 'Gold')
    
    print(f"\n--- Correlation Analysis ---")
    print(f"Overall Correlation: {analysis['overall_correlation']:.4f}")
    print(f"Mean Rolling Corr: {analysis['mean_correlation']:.4f}")
    print(f"Mean Spread: {analysis['mean_spread_pct']:.2f}%")
    print(f"Spread Std Dev: {analysis['std_spread_pct']:.2f}%")
    print(f"Z-Score Range: [{analysis['min_z_score']:.2f}, {analysis['max_z_score']:.2f}]")
    
    # Generate signals
    signals = generate_signals_gold(xauusd, goldbees)
    
    long_days = (signals == 1).sum()
    short_days = (signals == -1).sum()
    flat_days = (signals == 0).sum()
    
    print(f"\n--- Signal Distribution ---")
    print(f"Long (Indian undervalued): {long_days} days ({long_days/len(signals)*100:.1f}%)")
    print(f"Short (Indian overvalued): {short_days} days ({short_days/len(signals)*100:.1f}%)")
    print(f"Flat: {flat_days} days ({flat_days/len(signals)*100:.1f}%)")
    
    # Backtest
    returns = goldbees['close'].pct_change()
    strategy_returns = signals.shift(1) * returns
    strategy_returns = strategy_returns.dropna()
    
    if len(strategy_returns) > 0 and strategy_returns.std() > 0:
        total_return = (1 + strategy_returns).prod() - 1
        sharpe = (strategy_returns.mean() / strategy_returns.std()) * np.sqrt(252)
        
        print(f"\n--- Backtest Results ---")
        print(f"Total Return: {total_return:.2%}")
        print(f"Sharpe Ratio: {sharpe:.2f}")
    
    print("\n" + "=" * 60)
