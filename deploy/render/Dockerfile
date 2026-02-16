FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy all Python files into live/ folder (matching import structure)
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

# Copy core dependencies (imported by paper_trader.py and app.py)
COPY core/__init__.py ./core/
COPY core/state_manager.py ./core/
COPY core/telegram_bot.py ./core/
COPY core/correlation_guard.py ./core/

# Copy strategy to backtests folder
COPY balanced_strategy.py ./backtests/

# Create results directory
RUN mkdir -p backtests results/paper_trades

ENV PYTHONUNBUFFERED=1

# Expose port (Render sets PORT env var, uvicorn reads it)
EXPOSE 7860

# Run the app (FastAPI + Gradio + Keep-alive)
CMD ["python", "-m", "live.app"]
