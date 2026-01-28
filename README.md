# 🚀 Render Deployment - Paper Trading Bot

Deploy your trading bot to Render for 24/7 operation with Binance access.

## Quick Deploy Steps

### 1. Create GitHub Repository
1. Go to [github.com](https://github.com) → New Repository
2. Name it `trading-bot`
3. Upload all files from this `render_deploy` folder

### 2. Deploy on Render
1. Go to [render.com](https://render.com) and sign up
2. Click **"New +"** → **"Web Service"**
3. Connect your GitHub account
4. Select your `trading-bot` repository
5. Render will auto-detect the Dockerfile

### 3. Configure Settings
- **Name**: trading-bot (or any name)
- **Region**: **Singapore** ← IMPORTANT!
- **Instance Type**: Free
- **Build Command**: (leave empty, uses Dockerfile)
- **Start Command**: `python -m live.app`

### 4. Deploy
Click "Create Web Service" and wait for build.

## Dashboard Access
Once deployed, Render gives you a URL like:
`https://trading-bot-xxxx.onrender.com`

## All 5 Symbols Work!
- BTCUSDT ✅
- ETHUSDT ✅
- SOLUSDT ✅
- XAUUSDT (Gold) ✅
- XAGUSDT (Silver) ✅

## Free Tier
Render free tier: Service sleeps after 15 min of inactivity.
For 24/7, consider $7/month Starter plan.
