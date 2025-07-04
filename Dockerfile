# Use official Python runtime as base image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Set environment variables
ENV PYTHONPATH=/app
ENV FLASK_APP=app.py

# Expose port (Railway will assign the actual port)
EXPOSE 5000

# CRITICAL FIX: Use shell form to enable environment variable substitution
# Railway injects PORT at runtime, shell form processes $PORT correctly
CMD python -m gunicorn app:app --bind 0.0.0.0:${PORT:-5000} --workers 1 --timeout 120