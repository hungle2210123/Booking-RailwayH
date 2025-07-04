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

# Copy Railway startup script
COPY railway_start.py /app/railway_start.py
RUN chmod +x /app/railway_start.py

# Set environment variables
ENV PYTHONPATH=/app
ENV FLASK_APP=app.py

# Expose port (Railway will assign the actual port)
EXPOSE 5000

# Use smart Railway startup script that handles PORT issues
CMD ["python", "/app/railway_start.py"]