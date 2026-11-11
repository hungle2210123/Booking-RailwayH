# p01_health_cancellations — health, cancellations centre, OK status, auto-sync, debug routes
# Part of app.py (lines 612-1426 before the Oct 25 split). Runs inside app.py's namespace
# (see the loader at the end of app.py): every name defined in app.py and earlier parts is available here.
@app.route('/health')
def healthcheck():
    """Railway healthcheck endpoint - returns 200 OK without database access"""
    return jsonify({
        'status': 'healthy',
        'service': 'hotel-booking-system',
        'version': '2.0',
        'timestamp': datetime.now().isoformat()
    }), 200


