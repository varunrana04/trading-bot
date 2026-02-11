# Requirements Document

## Introduction

Build three specialized trading engines (Crypto, US Markets, Metals) plus refactor Indian markets for options-only trading. Each engine optimizes for its asset class with leverage, taxes, and volatility. Goal: maximize returns from $100 starting capital with daily/monthly/yearly tracking.

## Glossary

- **Trading_Engine**: Complete trading module for one asset class
- **Crypto_Engine**: BTC/ETH trading with high volatility strategies
- **US_Market_Engine**: NASDAQ/S&P500/DJIA trading with US tax treatment
- **Metals_Engine**: Gold/Silver (XAUUSD/XAGUSD) trading with leverage
- **Indian_Options_Engine**: NIFTY/BANKNIFTY/SENSEX options only (no futures)
- **Optimizer**: Genetic algorithm that finds optimal strategy parameters
- **Risk_Manager**: Enforces position sizing and stop losses

## Requirements

### Requirement 1: Crypto Engine (BTC/ETH)

**User Story:** As a trader, I want a crypto engine for high-volatility trading, so that I can profit from 24/7 crypto markets.

#### Acceptance Criteria

1. THE Crypto_Engine SHALL trade Bitcoin and Ethereum
2. THE Crypto_Engine SHALL implement 3-5 strategies (momentum, breakout, mean reversion)
3. THE Crypto_Engine SHALL apply leverage 1x-10x based on volatility
4. WHEN volatility exceeds 50%, THE Crypto_Engine SHALL reduce position size by 30%
5. THE Crypto_Engine SHALL track daily/monthly/yearly returns from $100 capital

### Requirement 2: US Markets Engine

**User Story:** As a trader, I want a US markets engine with tax-aware returns, so that I can trade major indices efficiently.

#### Acceptance Criteria

1. THE US_Market_Engine SHALL trade NASDAQ 100, NASDAQ Composite, S&P 500, and DJIA
2. THE US_Market_Engine SHALL implement 3-4 index-specific strategies
3. THE US_Market_Engine SHALL apply leverage 1x-5x
4. THE US_Market_Engine SHALL calculate taxes (short-term vs long-term capital gains)
5. THE US_Market_Engine SHALL track daily/monthly/yearly returns from $100 capital

### Requirement 3: Metals Engine (Gold/Silver)

**User Story:** As a trader, I want a metals engine for XAUUSD/XAGUSD, so that I can trade precious metals with leverage.

#### Acceptance Criteria

1. THE Metals_Engine SHALL trade XAUUSD (Gold) and XAGUSD (Silver)
2. THE Metals_Engine SHALL apply leverage 1x-20x
3. THE Metals_Engine SHALL implement correlation strategies between gold and silver
4. THE Metals_Engine SHALL account for overnight financing costs
5. THE Metals_Engine SHALL track daily/monthly/yearly returns from $100 capital

### Requirement 4: Indian Options Engine

**User Story:** As a trader, I want options-only trading for Indian indices, so that I can use options strategies instead of futures.

#### Acceptance Criteria

1. THE Indian_Options_Engine SHALL trade options for NIFTY 50, BANKNIFTY, and SENSEX only
2. THE Indian_Options_Engine SHALL NOT trade futures
3. THE Indian_Options_Engine SHALL implement 4-6 options strategies (calls, puts, spreads, straddles)
4. THE Indian_Options_Engine SHALL apply 31.2% tax rate
5. THE Indian_Options_Engine SHALL track daily/monthly/yearly returns from ₹10,000 capital

### Requirement 5: Optimizer with Constraint Profiles

**User Story:** As a developer, I want an optimizer with loose/moderate/hard constraints, so that I can find optimal parameters quickly.

#### Acceptance Criteria

1. THE Optimizer SHALL support loose, moderate, and hard constraint profiles
2. THE Optimizer SHALL run 30-50 generations
3. THE Optimizer SHALL preserve top 20% elite strategies each generation
4. THE Optimizer SHALL validate on out-of-sample data

### Requirement 6: Risk Management

**User Story:** As a trader, I want risk management with leverage awareness, so that I can protect capital.

#### Acceptance Criteria

1. THE Risk_Manager SHALL enforce position size limits per asset class
2. WHEN drawdown exceeds 15%, THE Risk_Manager SHALL reduce positions by 50%
3. THE Risk_Manager SHALL use ATR-based stop losses
4. THE Risk_Manager SHALL enforce 5% daily loss limit

### Requirement 7: Performance Tracking

**User Story:** As a trader, I want to see returns from $100 across timeframes, so that I can evaluate strategies.

#### Acceptance Criteria

1. THE system SHALL calculate daily P&L from $100 starting capital
2. THE system SHALL calculate monthly returns with compounding
3. THE system SHALL calculate annualized returns
4. THE system SHALL report Sharpe ratio, win rate, and max drawdown
5. THE system SHALL export results to JSON
