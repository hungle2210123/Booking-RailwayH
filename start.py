#!/usr/bin/env python3
import os
import subprocess
import sys

# Get PORT from environment, default to 5000
port = os.environ.get('PORT', '5000')

# Validate port is numeric
try:
    port_num = int(port)
    if port_num < 1 or port_num > 65535:
        port = '5000'
except (ValueError, TypeError):
    port = '5000'

print(f"🚀 Starting gunicorn on port {port}")

# Start gunicorn
cmd = [
    'python', '-m', 'gunicorn', 
    'app:app', 
    '--bind', f'0.0.0.0:{port}',
    '--workers', '1',
    '--timeout', '120'
]

subprocess.execvp('python', cmd)