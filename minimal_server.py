#!/usr/bin/env python3
"""
MINIMAL FLASK SERVER - NO DATABASE, NO IMPORTS, JUST HTTP
This will work even if everything else fails
"""
import os
import sys

# Force unbuffered output
sys.stdout.reconfigure(line_buffering=True)

print("=" * 70, flush=True)
print("🚀 MINIMAL SERVER STARTING", flush=True)
print("=" * 70, flush=True)

port = os.environ.get('PORT', '5000')
print(f"PORT from environment: {port}", flush=True)

try:
    port_int = int(port)
    print(f"✅ PORT is valid integer: {port_int}", flush=True)
except:
    print(f"❌ PORT is invalid: {port}", flush=True)
    port_int = 5000

# Import Flask
from flask import Flask, jsonify

app = Flask(__name__)

@app.route('/')
def health():
    return jsonify({'status': 'healthy', 'port': port_int}), 200

@app.route('/test')
def test():
    return jsonify({'message': 'Server is working!'}), 200

if __name__ == '__main__':
    print(f"🚀 Starting Flask on 0.0.0.0:{port_int}", flush=True)
    print("=" * 70, flush=True)
    app.run(host='0.0.0.0', port=port_int, debug=False)
