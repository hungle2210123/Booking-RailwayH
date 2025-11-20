# Ultra Simple Dockerfile for Railway Free Plan
FROM python:3.11-slim

WORKDIR /app

# Install COMPLETE requirements (minimal was missing Flask-Caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY app.py .
COPY run.py .
COPY backup_routes.py .
COPY migrate_add_apartments.py .
COPY migrate_add_rooms.py .
COPY force_migration.py .
COPY core/ ./core/
COPY templates/ ./templates/
COPY static/ ./static/

# Set default PORT if not provided (Railway will override this)
ENV PORT=5000

# Use run.py for production startup with diagnostics
CMD ["python3", "-u", "run.py"]