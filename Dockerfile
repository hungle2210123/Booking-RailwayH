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
ENV PORT=5000

# Expose port
EXPOSE $PORT

# Create startup script that handles PORT environment variable
COPY start.sh /start.sh
RUN chmod +x /start.sh

# Command to run the application
CMD ["/start.sh"]