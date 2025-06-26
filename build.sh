#!/usr/bin/env bash
# Render build script for hotel booking system

set -o errexit  # exit on error

echo "🏨 Building Hotel Booking System..."

# Install dependencies
echo "📦 Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

echo "✅ Build completed successfully!"