FROM python:3.11-slim

RUN useradd -m -u 1000 user
USER user
ENV PATH="/home/user/.local/bin:$PATH"

WORKDIR /app

COPY --chown=user requirements-deploy.txt ./requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy all Python files to live/ folder structure
COPY --chown=user __init__.py ./live/
COPY --chown=user app.py ./live/
COPY --chown=user alerts.py ./live/
COPY --chown=user dashboard.py ./live/
COPY --chown=user data_feed.py ./live/
COPY --chown=user paper_trader.py ./live/
COPY --chown=user run_paper.py ./live/
COPY --chown=user signal_engine.py ./live/

# Copy strategy to backtests folder
COPY --chown=user balanced_strategy.py ./backtests/

RUN mkdir -p results/paper_trades

ENV PYTHONUNBUFFERED=1

# Expose port for Gradio
EXPOSE 7860

# Run Gradio dashboard (auto-starts trading bot)
CMD ["python", "-m", "live.app"]
