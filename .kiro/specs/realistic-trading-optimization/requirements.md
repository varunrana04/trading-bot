# Realistic Trading Optimization - Requirements Document

## Introduction

This document defines requirements for overhauling the US Markets/Crypto/Metals optimization system to produce realistic, tradeable strategies. The current system generates over-optimized results with unrealistic parameters that fail in live trading due to excessive indicators, curve-fitted parameters, tight stop losses that trigger instantly from volatility/spread, and small take profits that get consumed by slippage.

## Glossary

- **Optimization System**: The framework that tests and optimizes trading strategies
- **Curve Fitting**: Over-optimization where parameters work perfectly on historical data but fail on new data
- **Slippage**: The difference between expected trade price and actual execution price
- **Spread**: The difference between bid and ask price
- **Stop Loss**: Price level where a losing trade is automatically closed
- **Take Profit**: Price level where a winning trade is automatically closed
- **ATR (Average True Range)**: Volatility indicator measuring average price movement
- **Minimum Tick**: Smallest price movement for an asset
- **Core Indicators**: Essential technical indicators that provide genuine edge
- **Redundant Indicators**: Multiple indicators measuring the same market condition
- **Parameter Range**: Valid minimum and maximum values for strategy parameters
- **Realistic Constraints**: Trading limitations based on actual market conditions

## Requirements

### Requirement 1: Indicator Reduction and Simplification

**User Story:** As a trader, I want strategies using only essential indicators, so that signals are clear, robust, and not over-fitted to historical noise.

#### Acceptance Criteria

1. THE Optimization System SHALL limit strategies to maximum 5 core indicators per strategy
2. THE System SHALL prohibit using multiple indicators that measure the same market condition (e.g., RSI + Stochastic + CCI together)
3. THE System SHALL use only proven indicators: Moving Averages (SMA/EMA), RSI, MACD, Bollinger Bands, ATR
4. THE System SHALL remove all exotic or complex indicators that add minimal value
5. THE System SHALL validate that each indicator serves a distinct purpose (trend, momentum, volatility, volume, or confirmation)

### Requirement 2: Realistic Parameter Ranges

**User Story:** As a trader, I want parameter ranges that prevent curve-fitting, so that strategies remain robust across different market conditions.

#### Acceptance Criteria

1. THE Optimization System SHALL enforce minimum parameter values to prevent over-optimization
2. WHEN optimizing moving average periods, THE System SHALL use minimum period of 10 and maximum of 200
3. WHEN optimizing RSI periods, THE System SHALL use minimum period of 10 and maximum of 30
4. WHEN optimizing lookback periods, THE System SHALL use minimum of 20 bars and maximum of 100 bars
5. THE System SHALL reject parameter combinations that are too specific (e.g., exact values like 17.3 instead of rounded values like 15 or 20)

### Requirement 3: Volatility-Based Stop Loss Constraints

**User Story:** As a trader, I want stop losses based on actual market volatility, so that positions don't get stopped out by normal price fluctuations.

#### Acceptance Criteria

1. THE Optimization System SHALL calculate minimum stop loss distance using ATR (Average True Range)
2. THE System SHALL enforce minimum stop loss of 2.0 × ATR for all assets
3. WHEN asset spread exceeds 0.1%, THE System SHALL add spread to minimum stop loss distance
4. THE System SHALL increase minimum stop loss to 3.0 × ATR for highly volatile assets (crypto, small-cap stocks)
5. THE System SHALL reject any strategy with stop loss tighter than the calculated minimum

### Requirement 4: Slippage-Resistant Take Profit Levels

**User Story:** As a trader, I want take profit levels large enough to overcome slippage and transaction costs, so that winning trades actually generate net profit.

#### Acceptance Criteria

1. THE Optimization System SHALL calculate minimum take profit using ATR and transaction costs
2. THE System SHALL enforce minimum take profit of 3.0 × ATR for all assets
3. WHEN total transaction costs (commission + slippage + spread) exceed 0.2%, THE System SHALL increase minimum take profit to 4.0 × ATR
4. THE System SHALL ensure take profit is at least 1.5× larger than stop loss (minimum risk-reward ratio)
5. THE System SHALL reject strategies where average winning trade is less than 2× transaction costs

### Requirement 5: Realistic Slippage Modeling

**User Story:** As a trader, I want backtests to include realistic slippage based on asset liquidity, so that results reflect actual trading conditions.

#### Acceptance Criteria

1. THE Optimization System SHALL apply asset-specific slippage rates during backtesting
2. WHEN backtesting liquid assets (S&P 500, NASDAQ, Gold), THE System SHALL apply 0.05% slippage
3. WHEN backtesting medium liquidity assets (Silver, Dow Jones), THE System SHALL apply 0.10% slippage
4. WHEN backtesting crypto assets (Bitcoin, Ethereum), THE System SHALL apply 0.15% slippage
5. WHEN backtesting during high volatility periods, THE System SHALL double the slippage rate

### Requirement 6: Spread-Aware Entry and Exit

**User Story:** As a trader, I want strategies that account for bid-ask spread, so that entry and exit prices are realistic.

#### Acceptance Criteria

1. THE Optimization System SHALL incorporate bid-ask spread into all trade simulations
2. WHEN entering long positions, THE System SHALL use ask price (higher price)
3. WHEN exiting long positions, THE System SHALL use bid price (lower price)
4. THE System SHALL apply asset-specific spreads: 0.01% for major indices, 0.05% for commodities, 0.10% for crypto
5. THE System SHALL reject strategies where spread costs exceed 30% of average profit per trade

### Requirement 7: Minimum Trade Duration Requirements

**User Story:** As a trader, I want strategies that hold positions long enough to avoid excessive transaction costs, so that trading frequency doesn't erode profits.

#### Acceptance Criteria

1. THE Optimization System SHALL enforce minimum trade duration based on timeframe
2. WHEN trading 5-minute timeframe, THE System SHALL require minimum 15-minute hold time (3 bars)
3. WHEN trading 15-minute timeframe, THE System SHALL require minimum 45-minute hold time (3 bars)
4. WHEN trading hourly timeframe, THE System SHALL require minimum 3-hour hold time (3 bars)
5. THE System SHALL penalize strategies with average trade duration less than minimum requirement

### Requirement 8: Maximum Trade Frequency Limits

**User Story:** As a trader, I want limits on trade frequency to prevent over-trading, so that transaction costs don't consume all profits.

#### Acceptance Criteria

1. THE Optimization System SHALL limit maximum trades per day based on timeframe
2. WHEN trading 5-minute timeframe, THE System SHALL allow maximum 10 trades per day
3. WHEN trading 15-minute timeframe, THE System SHALL allow maximum 6 trades per day
4. WHEN trading hourly timeframe, THE System SHALL allow maximum 3 trades per day
5. THE System SHALL reject strategies exceeding maximum trade frequency

### Requirement 9: Simplified Fitness Function

**User Story:** As a trader, I want a fitness function that prioritizes real-world profitability over curve-fitted metrics, so that strategies work in live trading.

#### Acceptance Criteria

1. THE Optimization System SHALL use simplified fitness function with 3 components only
2. THE System SHALL weight net profit after all costs at 50%
3. THE System SHALL weight risk-reward ratio (avg win / avg loss) at 30%
4. THE System SHALL weight maximum drawdown at 20%
5. THE System SHALL remove complex metrics that encourage over-optimization (Sharpe ratio, Sortino ratio, etc.)

### Requirement 10: Robust Parameter Validation

**User Story:** As a trader, I want automatic validation that rejects unrealistic parameter combinations, so that only tradeable strategies are produced.

#### Acceptance Criteria

1. THE Optimization System SHALL validate all parameters before backtesting
2. WHEN stop loss is less than 2.0 × ATR, THE System SHALL reject the parameter set
3. WHEN take profit is less than 3.0 × ATR, THE System SHALL reject the parameter set
4. WHEN risk-reward ratio is less than 1.5, THE System SHALL reject the parameter set
5. THE System SHALL log all rejected parameter sets with rejection reasons

### Requirement 11: Walk-Forward Validation with Strict Criteria

**User Story:** As a trader, I want strict out-of-sample validation to ensure strategies aren't curve-fitted, so that performance is consistent on new data.

#### Acceptance Criteria

1. THE Optimization System SHALL use 60% training, 40% validation split (stricter than before)
2. WHEN validation profit drops more than 20% from training profit, THE System SHALL reject the strategy
3. WHEN validation win rate drops more than 5% from training win rate, THE System SHALL reject the strategy
4. THE System SHALL require validation period to be profitable (positive net profit)
5. THE System SHALL report both training and validation metrics side-by-side for comparison

### Requirement 12: Asset-Specific Realistic Constraints

**User Story:** As a trader, I want constraints tailored to each asset's characteristics, so that strategies respect real market conditions.

#### Acceptance Criteria

1. THE Optimization System SHALL maintain asset-specific constraint profiles
2. WHEN optimizing Gold, THE System SHALL use: 0.05% slippage, 0.01% spread, 2.0 × ATR stop loss, 3.0 × ATR take profit
3. WHEN optimizing Bitcoin, THE System SHALL use: 0.15% slippage, 0.10% spread, 3.0 × ATR stop loss, 4.0 × ATR take profit
4. WHEN optimizing S&P 500, THE System SHALL use: 0.05% slippage, 0.01% spread, 2.0 × ATR stop loss, 3.0 × ATR take profit
5. THE System SHALL document all asset-specific constraints in configuration files

### Requirement 13: Reduced Genetic Algorithm Population

**User Story:** As a trader, I want smaller optimization populations to reduce overfitting risk, so that strategies are more generalizable.

#### Acceptance Criteria

1. THE Optimization System SHALL reduce population size from 50 to 20 individuals per generation
2. THE System SHALL reduce generations from 20 to 10 generations
3. THE System SHALL increase mutation rate from 10% to 20% to maintain diversity
4. THE System SHALL use tournament selection instead of fitness-proportionate selection
5. THE System SHALL stop early if best fitness doesn't improve for 3 consecutive generations

### Requirement 14: Transaction Cost Transparency

**User Story:** As a trader, I want clear breakdown of all transaction costs, so that I understand true profitability.

#### Acceptance Criteria

1. THE Optimization System SHALL report detailed cost breakdown for each strategy
2. THE System SHALL separately report: commission costs, slippage costs, spread costs, tax costs
3. THE System SHALL calculate cost-per-trade and cost-as-percentage-of-profit
4. WHEN total costs exceed 40% of gross profit, THE System SHALL flag the strategy as high-cost
5. THE System SHALL include cost analysis in all optimization reports

### Requirement 15: Realistic Backtesting Constraints

**User Story:** As a trader, I want backtests that simulate real trading limitations, so that results are achievable in live trading.

#### Acceptance Criteria

1. THE Optimization System SHALL enforce realistic position sizing (maximum 20% of capital per trade)
2. THE System SHALL respect market hours (no trading outside regular hours)
3. THE System SHALL simulate order execution delays (1-2 bars delay for entries/exits)
4. THE System SHALL reject trades during low liquidity periods (first/last 5 minutes of session)
5. THE System SHALL include gap risk (overnight gaps can bypass stop losses)

---

## Summary

This requirements document defines a comprehensive overhaul of the optimization system to produce realistic, tradeable strategies by:

- **Indicator Simplification**: Maximum 3 core indicators, removing redundant and exotic indicators
- **Realistic Parameters**: Minimum values to prevent curve-fitting, rounded values instead of exact decimals
- **Volatility-Based Stops**: Minimum 2.0-3.0 × ATR stop losses to avoid premature exits
- **Slippage-Resistant Profits**: Minimum 3.0-4.0 × ATR take profits to overcome transaction costs
- **Realistic Costs**: Asset-specific slippage (0.05%-0.15%), spreads (0.01%-0.10%), and commissions
- **Trade Frequency Limits**: Maximum trades per day to prevent over-trading
- **Simplified Fitness**: Focus on net profit, risk-reward, and drawdown only
- **Strict Validation**: 60/40 train/test split with maximum 20% performance degradation
- **Asset-Specific Constraints**: Tailored parameters for each asset's characteristics
- **Reduced Optimization**: Smaller populations (20 vs 50) and fewer generations (10 vs 20)

The system will produce strategies that are actually tradeable in live markets, with realistic expectations for slippage, spread, and transaction costs.
