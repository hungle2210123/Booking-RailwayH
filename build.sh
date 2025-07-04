#!/usr/bin/env bash
# Build script for hotel booking system

set -o errexit  # exit on error

echo "🏨 Building Hotel Booking System..."

# Install dependencies (skip pip upgrade in managed environments)
echo "📦 Installing Python dependencies..."
if [[ -n "$RAILWAY_ENVIRONMENT_ID" ]] || [[ -n "$NIX_PATH" ]]; then
    echo "🔧 Detected managed environment - skipping pip upgrade"
    pip install -r requirements.txt
else
    echo "🔧 Local environment - upgrading pip first"
    pip install --upgrade pip
    pip install -r requirements.txt
fi

echo "✅ Build completed successfully!"