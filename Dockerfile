FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY __init__.py ./live/
COPY app.py ./live/
COPY signal_engine.py ./live/
COPY data_feed.py ./live/
COPY paper_trader.py ./live/
COPY dashboard.py ./live/
COPY alerts.py ./live/
COPY run_paper.py ./live/
COPY diagnose_signals.py ./live/

RUN mkdir -p results/paper_trades

ENV PYTHONUNBUFFERED=1
EXPOSE 7860

CMD ["python", "-m", "live.app"]
