# Multi-Asset Trading Platform - Design Document

## Overview

This document outlines the technical design for the multi-asset trading platform. The platform extends the proven NIFTY bot architecture to support 9 different assets across Indian markets, commodities, cryptocurrencies, and US markets.

## Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Unified Dashboard                         │
│              (Web UI + Real-time Updates)                    │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                  Dashboard API Server                        │
│           (Aggregates data from all bots)                    │
└─────────────────────────────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        ▼                   ▼                   ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│  NIFTY Bot   │    │ BankNIFTY Bot│    │   Gold Bot   │
│  (Process 1) │    │  (Process 2) │    │  (Process 3) │
└──────────────┘    └──────────────┘    └──────────────┘
        │                   │                   │
        ▼                   ▼                   ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│  NSE Data    │    │  NSE Data    │    │ Commodity    │
│   Source     │    │   Source     │    │ Data Source  │
└──────────────┘    └──────────────┘    └──────────────┘

        ... (6 more bots for BTC, ETH, DJ, SP500, NASDAQ, Silver)

┌─────────────────────────────────────────────────────────────┐
│              Shared Components (src/)                        │
│  - Portfolio Manager                                         │
│  - Risk Management                                           │
│  - Data Models                                               │
│  - Utilities                                                 │
└─────────────────────────────────────────────────────────────┘
```

### Component Architecture

Each asset bot follows this structure:

```
bots/{asset}/
├── {asset}_bot.py          # Main trading bot
├── {asset}_data.py         # Data fetcher
├── {asset}_strategy.py     # Trading strategies
├── {asset}_config.py       # Configuration
├── test_{asset}_bot.py     # Tests
└── README.md               # Documentation
```

## Components and Interfaces

### 1. Asset Bot (Base Template)

**Purpose**: Core trading logic for each asset

**Key Components**:
- Market hours checker
- Signal generator
- Trade executor
- Position manager
- Data saver

**Interface**:
```python
class AssetBot:
    def __init__(self, config: AssetConfig)
    def is_market_open() -> bool
    def can_open_new_trades() -> bool
    def get_live_data() -> MarketData
    def get_option_chain() -> List[OptionData]
    def generate_signal() -> Optional[Signal]
    def execute_trade(signal: Signal) -> Position
    def manage_positions() -> None
    def save_state() -> None
```

### 2. Data Fetcher (Asset-Specific)

**Purpose**: Fetch real-time market data for each asset

**Implementations**:
- **NSE Data Fetcher** (NIFTY, Bank NIFTY) - Uses nsepython
- **Commodity Data Fetcher** (Gold, Silver) - Uses commodity APIs
- **Crypto Data Fetcher** (BTC, ETH) - Uses exchange APIs (Binance, Coinbase)
- **US Market Data Fetcher** (DJ, SP500, NASDAQ) - Uses Yahoo Finance / Alpha Vantage

**Interface**:
```python
class DataFetcher:
    def get_spot_price() -> float
    def get_option_chain() -> List[OptionData]
    def get_volume() -> int
    def get_volatility() -> float
```

### 3. Trading Strategy (Asset-Specific)

**Purpose**: Generate high-probability trading signals (75%+ win rate)

**Strategy Types**:
- **Trend Following** - EMA crossovers, ADX confirmation
- **Mean Reversion** - RSI + Bollinger Bands
- **Breakout** - Support/resistance levels
- **Volatility** - IV rank strategies
- **Time-based** - Intraday patterns

**Interface**:
```python
class TradingStrategy:
    def analyze_market(data: MarketData) -> AnalysisResult
    def generate_signal(analysis: AnalysisResult) -> Optional[Signal]
    def calculate_probability(signal: Signal) -> float
    def validate_signal(signal: Signal) -> bool
```

### 4. Configuration Manager

**Purpose**: Manage asset-specific configurations

**Configuration Structure**:
```python
@dataclass
class AssetConfig:
    # Asset identification
    symbol: str
    asset_type: str  # 'equity', 'commodity', 'crypto'
    
    # Trading parameters
    lot_size: int
    strike_interval: float
    min_premium: float
    max_premium: float
    
    # Market hours
    market_open_time: time
    market_close_time: time
    timezone: str
    
    # Trading windows
    cautious_start_1: time  # Morning cautious window start
    cautious_end_1: time    # Morning cautious window end
    cautious_start_2: time  # Evening cautious window start
    cautious_end_2: time    # Evening cautious window end
    
    # Risk parameters
    initial_capital: float
    max_position_size_pct: float
    max_daily_loss_pct: float
    stop_loss_pct: float
    take_profit_pct: float
    
    # Strategy parameters
    min_probability_normal: float  # 0.75 (75%)
    min_probability_cautious: float  # 0.90 (90%)
    
    # Data source
    data_source: str
    data_api_key: Optional[str]
```

### 5. Unified Dashboard

**Purpose**: Display all assets in one interface

**Features**:
- Real-time price updates for all assets
- Combined portfolio view
- Asset-wise P&L breakdown
- Active positions across all assets
- Performance metrics per asset
- Alerts and notifications

**Technology Stack**:
- Backend: FastAPI (Python)
- Frontend: HTML/CSS/JavaScript
- Real-time: WebSocket
- Data: JSON files + SQLite (optional)

### 6. Portfolio Manager (Shared)

**Purpose**: Manage positions and capital across all assets

**Key Features**:
- Track positions per asset
- Calculate combined P&L
- Enforce portfolio-wide risk limits
- Handle multi-currency (INR, USD, Crypto)
- Position sizing per asset

**Enhancements for Multi-Asset**:
```python
class MultiAssetPortfolioManager:
    def __init__(self, total_capital: float)
    def allocate_capital_per_asset() -> Dict[str, float]
    def get_asset_portfolio(asset: str) -> Portfolio
    def get_combined_portfolio() -> CombinedPortfolio
    def calculate_total_pnl() -> float
    def get_asset_allocation() -> Dict[str, float]
    def rebalance_if_needed() -> None
```

### 7. Risk Manager (Shared)

**Purpose**: Enforce risk limits across all assets

**Multi-Asset Risk Features**:
- Per-asset position limits
- Portfolio-wide exposure limits
- Correlation-based risk adjustment
- Asset-specific volatility scaling
- Dynamic position sizing

**Interface**:
```python
class MultiAssetRiskManager:
    def validate_trade(signal: Signal, asset: str) -> ValidationResult
    def check_portfolio_risk() -> RiskStatus
    def calculate_position_size(signal: Signal, asset: str) -> int
    def check_correlation_risk(new_position: Position) -> bool
    def adjust_for_volatility(asset: str, base_size: int) -> int
```

## Data Models

### Asset-Specific Models

```python
@dataclass
class AssetMarketData:
    symbol: str
    asset_type: str
    timestamp: datetime
    spot_price: float
    volume: int
    volatility: float
    bid: float
    ask: float
    
    # Asset-specific fields
    extra_data: Dict[str, Any]  # Flexible for asset-specific data

@dataclass
class AssetPosition:
    position_id: str
    asset: str
    symbol: str
    direction: Direction
    quantity: int
    entry_price: float
    current_price: float
    pnl: float
    entry_time: datetime
    
    # Options-specific (optional)
    strike_price: Optional[float]
    option_type: Optional[str]
    expiry_date: Optional[date]

@dataclass
class CombinedPortfolio:
    total_value: float
    total_cash: float
    total_pnl: float
    asset_portfolios: Dict[str, Portfolio]
    asset_allocations: Dict[str, float]
    timestamp: datetime
```

## Error Handling

### Error Categories

1. **Data Errors**
   - API failures
   - Network timeouts
   - Invalid data format
   - Missing data

2. **Trading Errors**
   - Order rejection
   - Insufficient capital
   - Position limit exceeded
   - Market closed

3. **System Errors**
   - Bot crash
   - Database errors
   - Configuration errors
   - Memory issues

### Error Handling Strategy

```python
class ErrorHandler:
    def handle_data_error(error: Exception, asset: str) -> None:
        # Log error
        # Use fallback data source
        # Notify user if critical
        # Continue with other assets
    
    def handle_trading_error(error: Exception, asset: str) -> None:
        # Log error
        # Rollback if needed
        # Notify user
        # Continue with other assets
    
    def handle_system_error(error: Exception, asset: str) -> None:
        # Log error
        # Save state
        # Attempt recovery
        # Shutdown gracefully if critical
```

## Testing Strategy

### Test Levels

1. **Unit Tests** (per asset)
   - Data fetcher tests
   - Strategy logic tests
   - Configuration validation
   - P&L calculation tests

2. **Integration Tests** (per asset)
   - End-to-end signal generation
   - Trade execution flow
   - Position management
   - Data persistence

3. **System Tests** (multi-asset)
   - Multiple bots running simultaneously
   - Dashboard aggregation
   - Portfolio-wide risk management
   - Cross-asset correlation

4. **Backtesting** (per asset)
   - Historical data validation
   - Strategy performance
   - Win rate verification (≥75%)
   - Risk metrics

### Test Coverage Goals

- Unit tests: ≥90% code coverage
- Integration tests: All critical paths
- System tests: All multi-asset scenarios
- Backtesting: Minimum 1 year of data

## Deployment Strategy

### Phase 1: Foundation (Current)
- ✅ NIFTY bot operational
- ✅ Shared components tested
- ✅ Dashboard working

### Phase 2: Indian Markets
- 🚧 Bank NIFTY bot
- 🚧 Integrate with existing dashboard

### Phase 3: Commodities
- 🚧 Gold bot
- 🚧 Silver bot

### Phase 4: Cryptocurrencies
- 🚧 BTC bot
- 🚧 ETH bot

### Phase 5: US Markets
- 🚧 Dow Jones bot
- 🚧 S&P 500 bot
- 🚧 NASDAQ bot

### Phase 6: Integration & Optimization
- 🚧 Unified dashboard enhancements
- 🚧 Cross-asset risk management
- 🚧 Performance optimization
- 🚧 Advanced analytics

## Performance Considerations

### Scalability

- Each bot runs as independent process
- Shared components use efficient data structures
- Database indexing for fast queries
- Caching for frequently accessed data

### Resource Management

- Memory: ~100MB per bot
- CPU: Minimal (event-driven)
- Network: Moderate (real-time data)
- Storage: ~1GB per year per asset

### Optimization Strategies

- Lazy loading of historical data
- Connection pooling for APIs
- Batch processing where possible
- Asynchronous I/O for data fetching

## Security Considerations

### API Keys Management

- Store in environment variables
- Never commit to version control
- Rotate keys periodically
- Use separate keys per asset

### Data Protection

- Encrypt sensitive data at rest
- Secure WebSocket connections (WSS)
- Validate all inputs
- Sanitize logs (no sensitive data)

### Access Control

- Dashboard authentication
- Role-based access (view/trade/admin)
- Audit logging
- Session management

## Monitoring and Alerting

### Metrics to Monitor

- Bot health status
- Trade execution success rate
- Data fetch latency
- P&L per asset
- Win rate per asset
- System resource usage

### Alerts

- Bot crash/restart
- Data source failure
- Large losses (>5% daily)
- Risk limit breaches
- Unusual trading activity

## Documentation

### Per-Asset Documentation

- README with overview
- Configuration guide
- Strategy explanation
- Troubleshooting guide

### Platform Documentation

- Architecture overview
- Setup instructions
- API documentation
- User guide

## Future Enhancements

### Potential Features

- Machine learning for signal generation
- Sentiment analysis integration
- Advanced portfolio optimization
- Multi-timeframe analysis
- Social trading features
- Mobile app
- Voice alerts
- Telegram bot integration

### Scalability Improvements

- Kubernetes deployment
- Load balancing
- Distributed caching
- Microservices architecture
- Cloud deployment (AWS/Azure)
