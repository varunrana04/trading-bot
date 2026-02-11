# Design Document

## Overview

This system creates four independent trading engines optimized for different asset classes. Each engine has its own optimizer, strategies, and performance tracker. The design prioritizes simplicity and speed over complexity.

## Architecture

```
trading_system/
├── engines/
│   ├── crypto_engine.py          # BTC/ETH trading
│   ├── us_markets_engine.py      # NASDAQ/S&P500/DJIA
│   ├── metals_engine.py          # Gold/Silver
│   └── indian_options_engine.py  # NIFTY/BANKNIFTY/SENSEX options
├── optimizers/
│   ├── genetic_optimizer.py      # Shared optimizer with constraint profiles
│   └── constraint_profiles.py    # Loose/moderate/hard configs
├── strategies/
│   ├── crypto_strategies.py      # Crypto-specific strategies
│   ├── us_strategies.py          # US market strategies
│   ├── metals_strategies.py      # Metals strategies
│   └── options_strategies.py     # Options strategies
├── core/
│   ├── risk_manager.py           # Position sizing, stop losses
│   ├── tax_calculator.py         # Tax calculations per jurisdiction
│   └── performance_tracker.py    # Returns tracking
└── run_all_engines.py            # Main entry point
```

## Components and Interfaces

### 1. Trading Engine Base Class

All engines inherit from a base class:

```python
class TradingEngine:
    def __init__(self, asset_class, capital, leverage_range):
        self.asset_class = asset_class
        self.capital = capital
        self.leverage_range = leverage_range
        self.positions = []
        self.trades = []
    
    def fetch_data(self, symbol, period):
        """Fetch historical data"""
        pass
    
    def backtest(self, strategy, params):
        """Run backtest with strategy"""
        pass
    
    def calculate_returns(self):
        """Calculate daily/monthly/yearly returns"""
        pass
    
    def optimize(self, constraint_profile):
        """Run genetic optimizer"""
        pass
```

### 2. Crypto Engine

**Assets**: BTC, ETH  
**Leverage**: 1x-10x  
**Strategies**:
- Momentum (EMA crossover with volume)
- Breakout (Support/resistance breaks)
- Mean Reversion (RSI + Bollinger Bands)

**Key Features**:
- 24/7 operation support
- High volatility adaptation (reduce size when vol > 50%)
- Short-term capital gains tax

### 3. US Markets Engine

**Assets**: ^NDX (NASDAQ 100), ^IXIC (NASDAQ Comp), ^GSPC (S&P 500), ^DJI (DJIA)  
**Leverage**: 1x-5x  
**Strategies**:
- Trend Following (MA crossover)
- VIX-based (Trade based on volatility index)
- Sector Rotation (Switch between indices)

**Key Features**:
- Market hours awareness (9:30 AM - 4:00 PM ET)
- Tax differentiation (short-term vs long-term)
- VIX-based leverage adjustment

### 4. Metals Engine

**Assets**: XAUUSD (Gold), XAGUSD (Silver)  
**Leverage**: 1x-20x  
**Strategies**:
- Trend Following (Similar to existing gold optimizer)
- Gold-Silver Ratio (Pair trading)
- Breakout (Range breakouts)

**Key Features**:
- Overnight financing cost calculation
- Correlation-based signals
- High leverage support

### 5. Indian Options Engine

**Assets**: NIFTY 50, BANKNIFTY, SENSEX (options only)  
**Leverage**: Inherent in options  
**Strategies**:
- Long Calls/Puts (Directional)
- Vertical Spreads (Bull/Bear spreads)
- Straddles (Volatility plays)
- Iron Condors (Range-bound)

**Key Features**:
- Options chain filtering (liquidity, Greeks)
- Expiry management (close 3 days before expiry)
- 31.2% tax rate
- No futures trading

## Data Models

### Strategy Parameters

```python
{
    "type": "momentum|breakout|mean_reversion|...",
    "params": {
        "fast_period": 10,
        "slow_period": 50,
        "stop_loss_pct": 0.02,
        "take_profit_pct": 0.05
    },
    "leverage": 2.0,
    "volatility_regime": "low|medium|high"
}
```

### Trade Record

```python
{
    "timestamp": "2024-01-01T10:00:00",
    "asset": "BTC",
    "direction": "long|short",
    "entry_price": 45000,
    "exit_price": 46000,
    "size": 0.1,
    "leverage": 3.0,
    "pnl": 100,
    "pnl_pct": 2.22,
    "tax": 31.2,
    "net_pnl": 68.8
}
```

### Performance Metrics

```python
{
    "engine": "crypto",
    "starting_capital": 100,
    "current_capital": 150,
    "daily_return": 2.5,
    "monthly_return": 15.0,
    "yearly_return": 50.0,
    "sharpe_ratio": 1.8,
    "max_drawdown": -8.5,
    "win_rate": 0.55,
    "total_trades": 120
}
```

## Error Handling

1. **Data Fetch Failures**: Retry 3 times with exponential backoff, skip if still failing
2. **Invalid Strategy Parameters**: Log warning and skip to next generation
3. **Insufficient Capital**: Skip trade and log warning
4. **API Rate Limits**: Implement request throttling (max 5 req/sec)

## Testing Strategy

1. **Unit Tests**: Test each strategy independently with synthetic data
2. **Backtest Validation**: Run on 2-year historical data
3. **Out-of-Sample Testing**: Validate on most recent 3 months
4. **Paper Trading**: Run for 30 days with live data before production

## Genetic Optimizer Design

### Constraint Profiles

**Loose** (Fast exploration):
- Population: 20
- Generations: 30
- Mutation rate: 0.3
- Parameter ranges: 150% of baseline

**Moderate** (Balanced):
- Population: 30
- Generations: 50
- Mutation rate: 0.2
- Parameter ranges: 100% of baseline

**Hard** (Conservative):
- Population: 40
- Generations: 70
- Mutation rate: 0.15
- Parameter ranges: 50% of baseline

### Fitness Function

```python
fitness = (
    total_return * 0.4 +
    sharpe_ratio * 0.3 +
    win_rate * 0.2 +
    (1 - max_drawdown) * 0.1
)
```

## Risk Management Design

### Position Sizing

```python
# Kelly Criterion with 25% fraction
kelly = (win_rate * avg_win - (1 - win_rate) * avg_loss) / avg_win
position_size = capital * kelly * 0.25

# Adjust for leverage
if leverage > 1:
    position_size = position_size / leverage
```

### Stop Loss Calculation

```python
# ATR-based stop loss
atr = calculate_atr(data, period=14)
stop_loss = entry_price - (atr * 2.0)

# Adjust for volatility regime
if volatility == "high":
    stop_loss = entry_price - (atr * 2.5)
```

### Daily Loss Limit

```python
if daily_loss > capital * 0.05:
    halt_trading_for_day()
    send_alert("Daily loss limit reached")
```

## Tax Calculation Design

### US Markets

```python
if holding_period < 365:
    tax_rate = 0.37  # Short-term (ordinary income)
else:
    tax_rate = 0.20  # Long-term capital gains
```

### Crypto

```python
tax_rate = 0.37  # Short-term capital gains (most crypto trades)
```

### Indian Options

```python
tax_rate = 0.312  # 31.2% flat rate
```

### Metals

```python
tax_rate = 0.28  # Collectibles rate for precious metals
```

## Performance Tracking Design

### Daily Returns

```python
daily_return = (end_of_day_capital - start_of_day_capital) / start_of_day_capital * 100
```

### Monthly Returns (Compounding)

```python
monthly_return = ((current_capital / capital_30_days_ago) - 1) * 100
```

### Yearly Returns (Annualized)

```python
days_elapsed = (current_date - start_date).days
yearly_return = ((current_capital / starting_capital) ** (365 / days_elapsed) - 1) * 100
```

## Implementation Priority

1. **Phase 1**: Core infrastructure (base engine, risk manager, performance tracker)
2. **Phase 2**: Crypto engine (simplest, 24/7 data available)
3. **Phase 3**: US Markets engine
4. **Phase 4**: Metals engine
5. **Phase 5**: Indian Options engine (most complex)
6. **Phase 6**: Optimizer integration and tuning

## File Organization

Delete old files:
- `optimizers/indian_daily_optimizer.py` (replace with new version)
- All old strategy files in `bots/` (keep structure, replace content)

Create new structure:
- `engines/` directory with 4 engine files
- `strategies/` directory with asset-class-specific strategies
- `core/` directory with shared components
- `run_all_engines.py` as main entry point

## Configuration

Single config file: `config/engines_config.yaml`

```yaml
crypto:
  enabled: true
  capital: 100
  leverage_range: [1, 10]
  constraint_profile: moderate
  
us_markets:
  enabled: true
  capital: 100
  leverage_range: [1, 5]
  constraint_profile: moderate

metals:
  enabled: true
  capital: 100
  leverage_range: [1, 20]
  constraint_profile: loose

indian_options:
  enabled: true
  capital: 10000  # INR
  constraint_profile: hard
```
