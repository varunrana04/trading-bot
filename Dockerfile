FROM python:3.11-slim

WORKDIR /app

# Install dependencies (use the Render-specific requirements)
COPY deploy/render/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy live trading module
COPY live/__init__.py ./live/
COPY live/app.py ./live/
COPY live/bot_api.py ./live/
COPY live/signal_engine.py ./live/
COPY live/data_feed.py ./live/
COPY live/paper_trader.py ./live/
COPY live/dashboard.py ./live/
COPY live/alerts.py ./live/
COPY live/run_paper.py ./live/
COPY live/diagnose_signals.py ./live/

# Copy core dependencies
COPY core/__init__.py ./core/
COPY core/state_manager.py ./core/
COPY core/telegram_bot.py ./core/
COPY core/correlation_guard.py ./core/

# Create directories for runtime
RUN mkdir -p backtests results/paper_trades

ENV PYTHONUNBUFFERED=1

# Render sets PORT env var, uvicorn reads it
EXPOSE 7860

CMD ["python", "-m", "live.app"]
