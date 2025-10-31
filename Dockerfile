# Ultra Simple Dockerfile for Railway Free Plan
FROM python:3.11-slim

WORKDIR /app

# Install COMPLETE requirements (minimal was missing Flask-Caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy ONLY minimal server for testing
COPY minimal_server.py .

# Set default PORT if not provided (Railway will override this)
ENV PORT=5000

# TEMPORARY: Use absolute minimal server to test Railway platform
CMD ["python3", "-u", "minimal_server.py"]