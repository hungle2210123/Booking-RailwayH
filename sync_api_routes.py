"""
Auto Sync API Routes
Flask endpoints for automatic bidirectional database synchronization
"""

from flask import Blueprint, jsonify, request
from core.auto_sync_service import auto_sync_service
import logging

logger = logging.getLogger(__name__)

# Create blueprint for sync routes
sync_api_bp = Blueprint('sync_api', __name__)

@sync_api_bp.route('/api/auto-sync/status', methods=['GET'])
def get_sync_status():
    """Get current sync status between local and Railway"""
    try:
        # Check for force refresh parameter (used after sync operations)
        force_refresh = request.args.get('force_refresh', 'false').lower() == 'true'
        
        logger.info(f"🔍 Getting sync status (force_refresh={force_refresh})")
        status = auto_sync_service.analyze_sync_status(force_refresh=force_refresh)
        
        return jsonify({
            'success': True,
            'status': {
                'local_count': status.local_count,
                'railway_count': status.railway_count,
                'sync_needed': status.sync_needed,
                'recommended_direction': status.recommended_direction,
                'differences': status.differences,
                'last_sync': status.last_sync_time.isoformat() if status.last_sync_time else None
            },
            'auto_sync_running': auto_sync_service.is_running
        })
        
    except Exception as e:
        logger.error(f"❌ Error getting sync status: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@sync_api_bp.route('/api/sync/notifications', methods=['GET'])
def get_sync_notifications():
    """Get sync notifications for UI display"""
    try:
        notifications = auto_sync_service.get_sync_notifications()
        
        return jsonify({
            'success': True,
            'notifications': notifications,
            'count': len(notifications)
        })
        
    except Exception as e:
        logger.error(f"❌ Error getting sync notifications: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'notifications': [],
            'count': 0
        }), 500

@sync_api_bp.route('/api/sync/perform', methods=['POST'])
def perform_sync():
    """Perform manual sync operation"""
    try:
        data = request.get_json() or {}
        sync_direction = data.get('direction', 'smart')  # smart, local_to_railway, railway_to_local
        tables = data.get('tables')  # Optional: specific tables to sync
        
        logger.info(f"🔄 Manual sync requested: {sync_direction}")
        
        if sync_direction == 'smart':
            result = auto_sync_service.perform_smart_sync()
            
        elif sync_direction == 'local_to_railway':
            success = auto_sync_service.sync_local_to_railway(tables)
            result = {
                'timestamp': auto_sync_service.last_check_time.isoformat() if auto_sync_service.last_check_time else None,
                'success': success,
                'actions_taken': [f"Manual sync: local → Railway"]
            }
            
        elif sync_direction == 'railway_to_local':
            success = auto_sync_service.sync_railway_to_local(tables)
            result = {
                'timestamp': auto_sync_service.last_check_time.isoformat() if auto_sync_service.last_check_time else None,
                'success': success,
                'actions_taken': [f"Manual sync: Railway → local"]
            }
            
        else:
            return jsonify({
                'success': False,
                'error': f'Invalid sync direction: {sync_direction}'
            }), 400
        
        # 🚀 ENHANCED: Force immediate cache invalidation and status refresh after manual sync
        logger.info("🔄 Manual sync completed - forcing cache invalidation")
        auto_sync_service._last_status_cache = None
        auto_sync_service._last_status_time = None
        
        # Verify sync results immediately
        logger.info("🔍 Verifying sync results...")
        verification_status = auto_sync_service.analyze_sync_status(force_refresh=True)
        logger.info(f"📊 Post-manual-sync verification: Local={verification_status.local_count}, Railway={verification_status.railway_count}, Sync needed={verification_status.sync_needed}")
        
        return jsonify({
            'success': True,
            'sync_result': result,
            'verification_status': {
                'local_count': verification_status.local_count,
                'railway_count': verification_status.railway_count,
                'sync_needed': verification_status.sync_needed
            }
        })
        
    except Exception as e:
        logger.error(f"❌ Error performing sync: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@sync_api_bp.route('/api/sync/auto/start', methods=['POST'])
def start_auto_sync():
    """Start automatic sync service"""
    try:
        if auto_sync_service.is_running:
            return jsonify({
                'success': True,
                'message': 'Auto sync is already running',
                'running': True
            })
        
        auto_sync_service.start_auto_sync()
        
        return jsonify({
            'success': True,
            'message': 'Auto sync service started',
            'running': True,
            'interval': auto_sync_service.sync_interval
        })
        
    except Exception as e:
        logger.error(f"❌ Error starting auto sync: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'running': False
        }), 500

@sync_api_bp.route('/api/sync/auto/stop', methods=['POST'])
def stop_auto_sync():
    """Stop automatic sync service"""
    try:
        if not auto_sync_service.is_running:
            return jsonify({
                'success': True,
                'message': 'Auto sync is not running',
                'running': False
            })
        
        auto_sync_service.stop_auto_sync()
        
        return jsonify({
            'success': True,
            'message': 'Auto sync service stopped',
            'running': False
        })
        
    except Exception as e:
        logger.error(f"❌ Error stopping auto sync: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@sync_api_bp.route('/api/sync/history', methods=['GET'])
def get_sync_history():
    """Get sync history"""
    try:
        history = auto_sync_service.sync_history[-10:]  # Last 10 syncs
        
        return jsonify({
            'success': True,
            'history': history,
            'total_syncs': len(auto_sync_service.sync_history)
        })
        
    except Exception as e:
        logger.error(f"❌ Error getting sync history: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'history': []
        }), 500

@sync_api_bp.route('/api/sync/config', methods=['GET', 'POST'])
def sync_config():
    """Get or update sync configuration"""
    if request.method == 'GET':
        try:
            return jsonify({
                'success': True,
                'config': {
                    'sync_interval': auto_sync_service.sync_interval,
                    'monitored_tables': auto_sync_service.monitored_tables,
                    'local_url_configured': bool(auto_sync_service.local_url),
                    'railway_url_configured': bool(auto_sync_service.railway_url),
                    'auto_sync_enabled': auto_sync_service.is_running
                }
            })
            
        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    elif request.method == 'POST':
        try:
            data = request.get_json() or {}
            
            # Update sync interval
            if 'sync_interval' in data:
                new_interval = int(data['sync_interval'])
                if 60 <= new_interval <= 3600:  # Between 1 minute and 1 hour
                    auto_sync_service.sync_interval = new_interval
                else:
                    return jsonify({
                        'success': False,
                        'error': 'Sync interval must be between 60 and 3600 seconds'
                    }), 400
            
            # Update monitored tables
            if 'monitored_tables' in data:
                auto_sync_service.monitored_tables = data['monitored_tables']
            
            return jsonify({
                'success': True,
                'message': 'Configuration updated',
                'config': {
                    'sync_interval': auto_sync_service.sync_interval,
                    'monitored_tables': auto_sync_service.monitored_tables
                }
            })
            
        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

@sync_api_bp.route('/api/sync/test_connections', methods=['GET'])
def test_sync_connections():
    """Test database connections for sync"""
    try:
        results = {
            'local': False,
            'railway': False,
            'local_error': None,
            'railway_error': None
        }
        
        # Test local connection
        if auto_sync_service.local_engine:
            try:
                with auto_sync_service.local_engine.connect() as conn:
                    conn.execute("SELECT 1")
                    results['local'] = True
            except Exception as e:
                results['local_error'] = str(e)
        else:
            results['local_error'] = "Local database URL not configured"
        
        # Test Railway connection
        if auto_sync_service.railway_engine:
            try:
                with auto_sync_service.railway_engine.connect() as conn:
                    conn.execute("SELECT 1")
                    results['railway'] = True
            except Exception as e:
                results['railway_error'] = str(e)
        else:
            results['railway_error'] = "Railway database URL not configured"
        
        return jsonify({
            'success': True,
            'connections': results,
            'both_available': results['local'] and results['railway']
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500