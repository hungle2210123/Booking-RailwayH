#!/usr/bin/env python3
"""
Hotel Booking Management System - Simple Deployment Version
PostgreSQL Edition (Google Sheets Removed)
"""
import os
from flask import Flask, render_template, jsonify
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Create Flask app
app = Flask(__name__)

# Configuration
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'default-secret-key')
app.config['DEBUG'] = False

@app.route('/')
def home():
    """Simple home page"""
    return jsonify({
        'status': 'success',
        'message': 'Hotel Booking System - PostgreSQL Edition',
        'version': '1.0.0',
        'features': [
            'PostgreSQL Database',
            'Commission Analytics',
            'Payment Tracking',
            'AI Integration Ready'
        ]
    })

@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': '2025-06-26',
        'environment': os.getenv('FLASK_ENV', 'production')
    })

@app.route('/test')
def test():
    """Test endpoint"""
    try:
        # Test basic functionality
        db_url = os.getenv('DATABASE_URL', 'Not configured')
        return jsonify({
            'status': 'ok',
            'database_configured': 'postgresql://' in str(db_url),
            'environment_loaded': True,
            'flask_working': True
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e)
        })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)