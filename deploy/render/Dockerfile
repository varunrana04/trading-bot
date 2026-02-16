FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy all Python files into live/ folder (matching import structure)
COPY __init__.py ./live/
COPY app.py ./live/
COPY bot_api.py ./live/
COPY signal_engine.py ./live/
COPY data_feed.py ./live/
COPY paper_trader.py ./live/
COPY dashboard.py ./live/
COPY alerts.py ./live/
COPY run_paper.py ./live/
COPY diagnose_signals.py ./live/

# Copy core dependencies (imported by paper_trader.py and app.py)
COPY core/__init__.py ./core/
COPY core/state_manager.py ./core/
COPY core/telegram_bot.py ./core/
COPY core/correlation_guard.py ./core/

# Copy strategy to backtests folder
COPY balanced_strategy.py ./backtests/

# Create results directory
RUN mkdir -p results/paper_trades

ENV PYTHONUNBUFFERED=1

# Expose port for Gradio
EXPOSE 7860

# Run the app
CMD ["python", "-m", "live.app"]
