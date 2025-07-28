# Ultra Simple Dockerfile for Railway Free Plan
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

# Set default PORT if not provided
ENV PORT=5000

# Direct command without script
CMD python -m gunicorn app:app --bind 0.0.0.0:$PORT --workers 1 --timeout 120