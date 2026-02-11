# Paper Trading Deployment Guide

## Current Status
**Time**: 10:06 PM IST (2025-11-23)
**Running Bots**: None

## Available Bots

### 1. Crypto Futures Bot (24/7)
**File**: `trade_crypto_futures_aggressive.py`
**Status**: Ready to deploy NOW
**Features**:
- ✓ GARCH volatility forecasting
- ✓ Kalman Filter price prediction
- ✓ VPIN market toxicity detection
- ✓ Kelly Criterion position sizing
- ✓ Bidirectional (LONG/SHORT)
- ✓ Multi-timeframe (15m/30m/1h)

**Capital**: $100 BTC + $100 ETH (paper)
**Leverage**: 6x (15m/30m), 8x (1h)
**Markets**: 24/7 (can start immediately)

---

### 2. Indian Options Bot
**File**: `trade_indian_options.py`
**Status**: Ready for market hours (9:15 AM - 3:30 PM IST)
**Features**:
- Iron Condor, Bull/Bear Spreads, Straddles
- Multi-leg strategies
- Greeks tracking
- Trading charges calculation

**Capital**: ₹16,666 per symbol (NIFTY/BANKNIFTY/SENSEX)
**Market Hours**: 9:15 AM - 3:30 PM IST (Mon-Fri)
**Next Trading**: Tomorrow 9:15 AM IST

---

## Deployment Commands

### Option 1: Start Crypto Bot (NOW)
```bash
cd c:/Users/Varun/Downloads/Bot_Algo
python trade_crypto_futures_aggressive.py
```

**What to expect**:
- Connects to Binance API
- Scans BTC/ETH every 2 seconds
- Generates signals with confidence scores
- Simulates trades (paper mode - no real money)

---

### Option 2: Start Indian Options Bot (Tomorrow 9:15 AM)
```bash
cd c:/Users/Varun/Downloads/Bot_Algo
python trade_indian_options.py
```

**What to expect**:
- Connects to Zerodha API
- Scans NIFTY/BANKNIFTY/SENSEX every 10 seconds
- Selects strategies based on market condition
- Simulates option trades (requires valid API token)

**IMPORTANT**: Zerodha access token expires daily. Run this before market open:
```bash
python quick_token_gen.py
```

---

### Option 3: Start Both Bots (in separate terminals)

**Terminal 1** (Crypto):
```bash
cd c:/Users/Varun/Downloads/Bot_Algo
python trade_crypto_futures_aggressive.py
```

**Terminal 2** (Options - tomorrow morning):
```bash
cd c:/Users/Varun/Downloads/Bot_Algo
python trade_indian_options.py
```

---

## Monitoring

### Live Dashboard (Optional)
```bash
python live_dashboard.py
```
Shows real-time P/L across all bots.

### Check Status
```bash
python check_all_bots.py
```

### Stop All Bots
```bash
python stop_all_bots.py
```
Or press `Ctrl+C` in each terminal.

---

## Safety Notes

1. **Paper Trading Confirmed**:
   - Crypto bot: Already in paper mode (no order placement)
   - Options bot: Simulates trades only (no real Zerodha orders)

2. **No Real Money**:
   - All P/L is simulated
   - No balance required
   - No risk

3. **Market Hours**:
   - **Crypto**: 24/7 (can run anytime)
   - **Indian Options**: 9:15 AM - 3:30 PM IST only

4. **API Requirements**:
   - Binance: Valid keys (already configured)
   - Zerodha: Daily token refresh required

---

## Quick Start (RIGHT NOW)

Since it's 10:06 PM IST, I recommend:

**START CRYPTO BOT NOW** (markets are 24/7):
```bash
cd c:/Users/Varun/Downloads/Bot_Algo
python trade_crypto_futures_aggressive.py
```

**SCHEDULE OPTIONS BOT** for tomorrow morning (9:00 AM IST):
1. Run token generator: `python quick_token_gen.py`
2. Start bot: `python trade_indian_options.py`

---

## Expected Output

### Crypto Bot
```
================================================================================
MULTI-TIMEFRAME CRYPTO BOT - BIDIRECTIONAL TRADING
================================================================================
Leverage: 15m/30m=6x, 1h=8x (reduced for safety)
Stops: 15m=0.48%, 30m=0.72%, 1h=1.08% (TIGHTER - 40% reduction)
Signals: LONG and SHORT enabled (bidirectional)
Scanning: Every 2 seconds (fast for crypto)
Capital: BTC=$100, ETH=$100
================================================================================

[21:06:37] Scanning markets...

BTCUSDT: $95,429.50
  [15m] ENTER LONG @ $95,429.50 6x (75%)
       Target: $96,905.93 | Stop: $95,171.15
```

### Options Bot (Tomorrow)
```
[9:15:00 AM] Market Open - BREATHING PERIOD
Scanning NIFTY... Spot: 22,150

  Market Condition: sideways
  Strategy: Iron Condor
  Confidence: 85%
  
  Executing Iron Condor on NIFTY (Lot Size: 75):
    SELL CE 22250 @ Rs.120 x 75 = Rs.9,000.00
    BUY CE 22350 @ Rs.60 x 75 = Rs.4,500.00
    SELL PE 22050 @ Rs.115 x 75 = Rs.8,625.00
    BUY PE 21950 @ Rs.58 x 75 = Rs.4,350.00
    Total Margin: Rs.13,500.00
```
