# ULTIMATE Railway-Optimized Dockerfile
# Based on Official Railway Flask Guide + Successful GitHub Examples
FROM python:3.11-slim

WORKDIR /app

# Copy and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# CRITICAL: Railway injects PORT at runtime, not build time
# Use shell form CMD for proper environment variable substitution
CMD gunicorn app:app --host 0.0.0.0 --port $PORT