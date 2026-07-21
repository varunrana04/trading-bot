<div align="center">
  <h1><code>trading-bot<span class="cursor">_</span></code></h1>
  <p><b>Algorithmic trading engine. Because sleeping is better than watching charts.</b></p>
  <p>
    <a href="https://varun-portfolio-eta.vercel.app/" target="_blank">
      <img src="https://img.shields.io/badge/Varun_Rana-Portfolio-10b981?style=for-the-badge&logoColor=000000" alt="Portfolio" />
    </a>
  </p>
</div>

<br>

### `[01]` system_overview
# Bot_Algo - Dual-Market Trading System

## 🎯 Main Objective

Build an automated algorithmic trading system for:
1. **Crypto Futures** (Binance) - BTC, ETH, SOL
2. **Indian Options** (Zerodha) - Nifty, BankNifty, Sensex

**Current Phase:** Backtesting, Paper Trading & Signal Generation *(No live trading)*

---

## 📂 Project Structure

```
Bot_Algo/
├── bots/
│   ├── crypto/              # Crypto paper trading & testing
│   ├── hft/                 # High-frequency trading (future use)
│   └── options/
│       └── n8n_fundamentals/  # ⭐ MAIN OPTIONS+CRYPTO ENGINE
│           ├── backtester.py         # Options backtesting
│           ├── crypto_backtester.py  # Crypto backtesting  
│           ├── crypto_bot.py         # Crypto trading logic
│           ├── philosophy.py         # Core trading philosophy
│           ├── scenario_detector.py  # Signal detection
│           ├── strategy_selector.py  # Strategy selection
│           ├── indian_costs.py       # Transaction costs
│           ├── n8n_webhook_server.py # N8N automation
│           ├── telegram_notifier.py  # Notifications
│           └── dashboard/            # Web dashboard
│
├── strategies/              # Trading strategies (ensemble, crypto, options)
├── indicators/              # Technical indicators
├── backtests/               # Backtest engines & optimizers
├── brokers/                 # Broker integrations (Zerodha, Binance)
├── hft/                     # HFT modules
├── scripts/                 # Utility scripts
├── results/                 # Optimization results
└── docs/                    # Documentation
```

---

## 🚀 Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure API Keys
```bash
cp .env.example .env
# Edit .env with your Binance/Zerodha API keys
```

### 3. Run Backtests
```bash
# Crypto backtest
python bots/options/n8n_fundamentals/crypto_backtester.py

# Options backtest  
python bots/options/n8n_fundamentals/backtester.py
```

### 4. Paper Trading
```bash
# Crypto paper trading
python run_crypto_paper.bat

# Options paper trading
python run_paper_bot.bat
```

---

## 📊 Core Components

| Component | Purpose | Location |
|-----------|---------|----------|
| **Crypto Backtester** | Test crypto strategies | `bots/options/n8n_fundamentals/crypto_backtester.py` |
| **Options Backtester** | Test options strategies | `bots/options/n8n_fundamentals/backtester.py` |
| **Philosophy Engine** | Core trading logic | `bots/options/n8n_fundamentals/philosophy.py` |
| **Scenario Detector** | Signal generation | `bots/options/n8n_fundamentals/scenario_detector.py` |
| **Dashboard** | Web UI for monitoring | `bots/options/n8n_fundamentals/dashboard/` |
| **N8N Server** | Webhook automation | `bots/options/n8n_fundamentals/n8n_webhook_server.py` |

---

## ⚙️ Configuration

| File | Purpose |
|------|---------|
| `.env` | API keys (Binance, Zerodha, Telegram) |
| `config.json` | Bot configuration |
| `broker_config.json` | Broker settings |

---

## 📈 Roadmap

- [x] Backtesting engine for both markets
- [x] Paper trading infrastructure
- [x] Signal generation & detection
- [x] Web dashboard
- [ ] Strategy optimization
- [ ] Live trading integration (future)

---

*Last updated: January 2026*

<br>

---
<div align="center">
  <sub>Built by <a href="https://github.com/varunrana04">Varun Rana</a>. <i>(Because someone has to keep the loss curve going down).</i></sub>
</div>
