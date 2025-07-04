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

# Expose port (Render handles PORT properly)
EXPOSE 10000

# Render-optimized startup command with proper PORT handling
CMD python -m gunicorn app:app --bind 0.0.0.0:${PORT:-10000} --workers 1 --timeout 120 --log-level info