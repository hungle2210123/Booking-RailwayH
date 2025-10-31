#!/usr/bin/env python3
"""
EMERGENCY STARTUP SCRIPT - Prints EVERYTHING before importing anything heavy
"""
import sys
import os

# Force unbuffered output
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

print("\n" + "=" * 70, flush=True)
print("🚨 EMERGENCY STARTUP DIAGNOSTICS", flush=True)
print("=" * 70, flush=True)

# Print Python info
print(f"\n📍 Python: {sys.version}", flush=True)
print(f"📍 Executable: {sys.executable}", flush=True)
print(f"📍 Working directory: {os.getcwd()}", flush=True)

# Print ALL environment variables
print("\n🔍 ENVIRONMENT VARIABLES:", flush=True)
print("=" * 70, flush=True)
for key in sorted(os.environ.keys()):
    value = os.environ[key]
    # Mask sensitive values
    if any(x in key.upper() for x in ['PASSWORD', 'SECRET', 'KEY', 'TOKEN']):
        masked = value[:10] + '...' if len(value) > 10 else '***'
        print(f"{key} = {masked}", flush=True)
    elif 'URL' in key.upper():
        masked = value[:30] + '...' if len(value) > 30 else value
        print(f"{key} = {masked}", flush=True)
    else:
        print(f"{key} = {value}", flush=True)

print("=" * 70, flush=True)

# Check for DATABASE_URL specifically
print("\n🔍 DATABASE CONFIGURATION:", flush=True)
db_url = os.environ.get('DATABASE_URL')
postgres_url = os.environ.get('POSTGRES_URL')
railway_db = os.environ.get('RAILWAY_DATABASE_URL')

print(f"DATABASE_URL: {'✅ SET' if db_url else '❌ NOT SET'}", flush=True)
print(f"POSTGRES_URL: {'✅ SET' if postgres_url else '❌ NOT SET'}", flush=True)
print(f"RAILWAY_DATABASE_URL: {'✅ SET' if railway_db else '❌ NOT SET'}", flush=True)

# Check PORT
port = os.environ.get('PORT', '5000')
print(f"\n🔍 PORT: {port}", flush=True)

# Now try minimal Flask import
print("\n🔬 TESTING FLASK IMPORT...", flush=True)
try:
    from flask import Flask, jsonify
    print("✅ Flask imported successfully", flush=True)

    # Create minimal app
    app = Flask(__name__)

    @app.route('/')
    def health():
        return jsonify({
            'status': 'healthy',
            'message': 'Emergency startup successful',
            'python_version': sys.version,
            'port': port,
            'database_configured': bool(db_url or postgres_url or railway_db)
        }), 200

    @app.route('/env')
    def show_env():
        """Debug endpoint to see environment"""
        env_vars = {}
        for key in sorted(os.environ.keys()):
            if any(x in key.upper() for x in ['PASSWORD', 'SECRET', 'KEY', 'TOKEN']):
                env_vars[key] = '***MASKED***'
            else:
                env_vars[key] = os.environ[key]
        return jsonify(env_vars), 200

    print("✅ Flask app created", flush=True)
    print(f"✅ Routes registered: / and /env", flush=True)

    # Start server
    print(f"\n🚀 STARTING FLASK SERVER ON 0.0.0.0:{port}", flush=True)
    print("=" * 70, flush=True)

    app.run(
        host='0.0.0.0',
        port=int(port),
        debug=False,
        use_reloader=False
    )

except Exception as e:
    print(f"\n❌ FLASK STARTUP FAILED:", flush=True)
    print(f"Error: {e}", flush=True)
    import traceback
    traceback.print_exc()
    sys.exit(1)
