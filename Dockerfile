# NUCLEAR FIX: Simple Start Script Approach
FROM python:3.11-slim

WORKDIR /app

# Install minimal requirements
COPY requirements-minimal.txt .
RUN pip install --no-cache-dir -r requirements-minimal.txt

# Copy application files
COPY app.py .
COPY core/ ./core/
COPY templates/ ./templates/
COPY static/ ./static/

# Copy and make start script executable
COPY start.sh .
RUN chmod +x start.sh

# Use simple bash script that Railway can definitely execute
CMD ["./start.sh"]