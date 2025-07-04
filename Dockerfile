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

# Ensure Railway environment file is available
COPY .env.railway .

# Set environment variables
ENV PYTHONPATH=/app
ENV FLASK_APP=app.py

# Expose port 8080 (Railway's preferred internal port)
EXPOSE 8080

# Run gunicorn on fixed port 8080
CMD ["python", "-m", "gunicorn", "app:app", "--bind", "0.0.0.0:8080", "--workers", "1", "--timeout", "120"]