# Quant Trading Bot - Hugging Face Deployment

## Quick Deploy to Hugging Face Spaces

### Step 1: Create a Space
1. Go to [huggingface.co/spaces](https://huggingface.co/spaces)
2. Click "Create new Space"
3. Choose **Docker** as the SDK
4. Name it: `quant-trading-bot`

### Step 2: Upload Files
Upload these files to your Space:
- `Dockerfile`
- `requirements.txt`
- `live/` folder (all files)
- `backtests/` folder (all files)

### Step 3: Set Secrets (Optional - for Telegram)
In Space Settings > Variables and secrets:
- `TELEGRAM_BOT_TOKEN` = your bot token
- `TELEGRAM_CHAT_ID` = your chat ID

### Step 4: Deploy
Click "Commit" - it will build and start automatically.

---

## Local Testing

```bash
# Build Docker image
docker build -t quant-bot .

# Run container
docker run -it quant-bot
```

---

## What It Does

- Fetches BTC/ETH/SOL data from Binance every 60s
- Generates trading signals (1hr trend + 15m entry)
- Tracks virtual positions
- Logs trades to `results/paper_trades/`

---

## Files Structure

```
├── Dockerfile           # Container config
├── requirements.txt     # Python deps
├── live/
│   ├── run_paper.py     # Main runner
│   ├── data_feed.py     # Binance data
│   ├── signal_engine.py # Signal logic
│   ├── paper_trader.py  # Position tracking
│   ├── dashboard.py     # Display
│   └── alerts.py        # Telegram
└── backtests/
    └── balanced_strategy.py
```

---

## Viewing Logs

On Hugging Face, click the "Logs" tab to see:
- Signals generated
- Positions opened/closed
- P&L updates
