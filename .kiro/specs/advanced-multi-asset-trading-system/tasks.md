# Implementation Plan

- [x] 1. Set up core infrastructure



  - Create base TradingEngine class with common methods
  - Implement RiskManager with position sizing and stop losses
  - Implement TaxCalculator with jurisdiction-specific rates
  - Implement PerformanceTracker for daily/monthly/yearly returns
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 7.1, 7.2, 7.3, 7.4, 7.5_

- [x] 2. Build genetic optimizer with constraint profiles


  - Create GeneticOptimizer class with population evolution
  - Implement three constraint profiles (loose, moderate, hard)
  - Implement fitness function combining return, Sharpe, win rate, drawdown
  - Add elitism to preserve top 20% each generation
  - _Requirements: 5.1, 5.2, 5.3, 5.4_

- [x] 3. Implement Crypto Engine


  - [x] 3.1 Create CryptoEngine class inheriting from TradingEngine


    - Set up BTC and ETH data fetching
    - Configure leverage range 1x-10x
    - _Requirements: 1.1, 1.3_

  - [x] 3.2 Implement crypto strategies

    - Momentum strategy (EMA crossover with volume)
    - Breakout strategy (support/resistance)
    - Mean reversion strategy (RSI + Bollinger Bands)
    - _Requirements: 1.2_

  - [x] 3.3 Add volatility adaptation

    - Calculate rolling volatility
    - Reduce position size by 30% when volatility > 50%
    - _Requirements: 1.4_

  - [x] 3.4 Integrate tax calculation and performance tracking

    - Apply short-term capital gains tax
    - Track daily/monthly/yearly returns from $100
    - _Requirements: 1.5_

  - [x] 3.5 Run optimization and generate report

    - Optimize with moderate constraint profile
    - Export results to JSON
    - _Requirements: 1.5_

- [x] 4. Implement US Markets Engine


  - [x] 4.1 Create USMarketsEngine class

    - Set up data fetching for NASDAQ 100, NASDAQ Comp, S&P 500, DJIA
    - Configure leverage range 1x-5x
    - _Requirements: 2.1, 2.3_

  - [x] 4.2 Implement US market strategies

    - Trend following (MA crossover)
    - VIX-based strategy
    - Sector rotation strategy
    - _Requirements: 2.2_

  - [x] 4.3 Add tax-aware calculations

    - Distinguish short-term vs long-term capital gains
    - Apply appropriate tax rates
    - _Requirements: 2.4_

  - [x] 4.4 Integrate performance tracking

    - Track daily/monthly/yearly returns from $100
    - Export results to JSON
    - _Requirements: 2.5_

  - [x] 4.5 Run optimization and generate report

    - Optimize with moderate constraint profile
    - _Requirements: 2.5_

- [x] 5. Implement Metals Engine


  - [x] 5.1 Create MetalsEngine class

    - Set up data fetching for XAUUSD and XAGUSD
    - Configure leverage range 1x-20x
    - _Requirements: 3.1, 3.2_

  - [x] 5.2 Implement metals strategies

    - Trend following (similar to existing gold optimizer)
    - Gold-Silver ratio pair trading
    - Breakout strategy
    - _Requirements: 3.3_

  - [x] 5.3 Add overnight financing cost calculation

    - Calculate daily financing costs for leveraged positions
    - Deduct from returns
    - _Requirements: 3.4_

  - [x] 5.4 Integrate performance tracking

    - Track daily/monthly/yearly returns from $100
    - Export results to JSON
    - _Requirements: 3.5_

  - [x] 5.5 Run optimization and generate report

    - Optimize with loose constraint profile
    - _Requirements: 3.5_

- [x] 6. Implement Indian Options Engine


  - [x] 6.1 Create IndianOptionsEngine class

    - Set up options data fetching for NIFTY 50, BANKNIFTY, SENSEX
    - Ensure NO futures trading
    - _Requirements: 4.1, 4.2_

  - [x] 6.2 Implement options strategies

    - Long calls and puts
    - Vertical spreads (bull/bear)
    - Straddles
    - Iron condors
    - _Requirements: 4.3_

  - [x] 6.3 Add options-specific features

    - Filter by liquidity (OI > 500, volume > 100)
    - Evaluate Greeks (Delta, Gamma, Theta, Vega)
    - Implement expiry management (close 3 days before)
    - _Requirements: 4.3_

  - [x] 6.4 Apply Indian tax rate and track performance

    - Apply 31.2% tax rate to all profits
    - Track daily/monthly/yearly returns from ₹10,000
    - Export results to JSON
    - _Requirements: 4.4, 4.5_

  - [x] 6.5 Run optimization and generate report

    - Optimize with hard constraint profile
    - _Requirements: 4.5_

- [x] 7. Create main runner and configuration


  - Create run_all_engines.py to execute all engines
  - Create config/engines_config.yaml with settings for all engines
  - Add command-line arguments to run specific engines
  - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_

- [x] 8. Clean up old files



  - Remove old optimizer files that are being replaced
  - Archive old strategy implementations
  - Update documentation to reflect new structure
  - _Requirements: All_

- [ ] 9. Documentation and validation
  - Create README for new engine system
  - Document how to run each engine
  - Document constraint profiles and when to use each
  - Add examples of output reports
  - _Requirements: All_
