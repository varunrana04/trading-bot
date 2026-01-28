FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy live trading module
COPY live/ ./live/

# Create results directory
RUN mkdir -p results/paper_trades

ENV PYTHONUNBUFFERED=1

# Expose port for Gradio (Railway will auto-detect)
EXPOSE 7860

# Run the app
CMD ["python", "-m", "live.app"]
