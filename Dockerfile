# ULTIMATE NUCLEAR FIX: Give Railway Exactly What It Wants
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

# Copy entrypoint script
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

# Use our entrypoint script
CMD ["/docker-entrypoint.sh"]