#!/usr/bin/env python3
"""
Reliable startup script for Railway deployment
Handles PORT environment variable without shell expansion
"""
import os
import subprocess
import sys

def main():
    # Get PORT from environment with fallback to 5000
    port = os.environ.get('PORT', '5000')
    
    # Validate port
    try:
        port_int = int(port)
        if not (1 <= port_int <= 65535):
            print(f"⚠️ Invalid port {port}, using 5000")
            port = '5000'
    except (ValueError, TypeError):
        print(f"⚠️ Non-numeric port '{port}', using 5000")
        port = '5000'
    
    print(f"🚀 Starting gunicorn on 0.0.0.0:{port}")
    
    # Start gunicorn with validated port
    # ⚡ EMERGENCY: Increased timeout + added worker class for better performance
    cmd = [
        'gunicorn',
        'app:app',
        '--bind', f'0.0.0.0:{port}',
        '--workers', '2',  # Increased from 1 to 2 workers
        '--worker-class', 'sync',  # Explicit sync worker
        '--timeout', '300',  # Increased from 120 to 300 seconds
        '--graceful-timeout', '300',
        '--keep-alive', '5',
        '--access-logfile', '-',
        '--error-logfile', '-',
        '--log-level', 'info'
    ]
    
    print(f"📝 Command: {' '.join(cmd)}")
    os.execvp('gunicorn', cmd)

if __name__ == '__main__':
    main()