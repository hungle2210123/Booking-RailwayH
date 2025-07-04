# MINIMAL Railway Test Dockerfile - Fast Build
FROM python:3.11-slim

WORKDIR /app

# Use minimal requirements for fast testing
COPY requirements-minimal.txt .
RUN pip install --no-cache-dir -r requirements-minimal.txt

# Copy only essential files
COPY app.py .
COPY core/ ./core/
COPY templates/ ./templates/
COPY static/ ./static/
COPY .env .

# Railway PORT injection
CMD gunicorn app:app --host 0.0.0.0 --port $PORT