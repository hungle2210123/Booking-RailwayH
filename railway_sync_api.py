#!/usr/bin/env python3
"""
Railway Sync API Integration
Provides sync functionality as Flask routes for dashboard integration
"""

import subprocess
import os
import sys
import json
from flask import Blueprint, request, jsonify, render_template
from pathlib import Path

# Create blueprint for sync routes
sync_bp = Blueprint('sync', __name__)

def run_psql_command(host, port, user, database, password, command):
    """Run a psql command and return result"""
    env = os.environ.copy()
    env['PGPASSWORD'] = password
    
    cmd = [
        'psql',
        '-h', host,
        '-p', str(port),
        '-U', user,
        '-d', database,
        '-c', command
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, env=env)
        return {
            'success': result.returncode == 0,
            'stdout': result.stdout.strip(),
            'stderr': result.stderr.strip()
        }
    except Exception as e:
        return {
            'success': False,
            'stdout': '',
            'stderr': str(e)
        }

def export_table_to_csv(host, port, user, database, password, table, filename):
    """Export table to CSV"""
    env = os.environ.copy()
    env['PGPASSWORD'] = password
    env['PGCLIENTENCODING'] = 'UTF8'
    
    copy_command = f"\\copy {table} TO '{filename}' WITH CSV HEADER ENCODING 'UTF8'"
    
    cmd = [
        'psql',
        '-h', host,
        '-p', str(port),
        '-U', user,
        '-d', database,
        '-c', copy_command
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, env=env)
        if result.returncode == 0:
            # Count records
            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    line_count = sum(1 for line in f) - 1  # Subtract header
                return {'success': True, 'count': line_count, 'error': None}
            except:
                return {'success': True, 'count': 0, 'error': None}
        else:
            return {'success': False, 'count': 0, 'error': result.stderr.strip()}
    except Exception as e:
        return {'success': False, 'count': 0, 'error': str(e)}

def import_csv_to_table(host, port, user, database, password, table, filename):
    """Import CSV to table"""
    if not os.path.exists(filename):
        return {'success': False, 'error': f'File {filename} not found'}
        
    env = os.environ.copy()
    env['PGPASSWORD'] = password
    env['PGCLIENTENCODING'] = 'UTF8'
    
    # Clear table first
    clear_result = run_psql_command(host, port, user, database, password, 
                                  f"TRUNCATE TABLE {table} RESTART IDENTITY CASCADE;")
    
    # Import data
    copy_command = f"\\copy {table} FROM '{filename}' WITH CSV HEADER ENCODING 'UTF8'"
    
    cmd = [
        'psql',
        '-h', host,
        '-p', str(port),
        '-U', user,
        '-d', database,
        '-c', copy_command
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, env=env)
        return {
            'success': result.returncode == 0,
            'error': result.stderr.strip() if result.returncode != 0 else None
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}

@sync_bp.route('/sync_dashboard')
def sync_dashboard():
    """Render sync dashboard page"""
    import os
    current_source = os.getenv('DATABASE_SOURCE', 'auto')
    return render_template('sync_dashboard.html', current_database_source=current_source)

@sync_bp.route('/api/test_connections', methods=['POST'])
def test_connections():
    """Test database connections"""
    try:
        # Configuration
        LOCAL_CONFIG = {
            'host': 'localhost',
            'port': 5432,
            'user': 'postgres',
            'database': 'hotel_booking',
            'password': 'locloc123'
        }
        
        RAILWAY_CONFIG = {
            'host': 'mainline.proxy.rlwy.net',
            'port': 36647,
            'user': 'postgres',
            'database': 'railway',
            'password': 'VmyAveAhkGVOFlSiVBWgyIEAUbKAXEPi'
        }
        
        # Test local connection
        local_result = run_psql_command(
            LOCAL_CONFIG['host'], LOCAL_CONFIG['port'], LOCAL_CONFIG['user'],
            LOCAL_CONFIG['database'], LOCAL_CONFIG['password'],
            "SELECT COUNT(*) as booking_count FROM bookings;"
        )
        
        # Test Railway connection
        railway_result = run_psql_command(
            RAILWAY_CONFIG['host'], RAILWAY_CONFIG['port'], RAILWAY_CONFIG['user'],
            RAILWAY_CONFIG['database'], RAILWAY_CONFIG['password'],
            "SELECT COUNT(*) as booking_count FROM bookings;"
        )
        
        return jsonify({
            'success': True,
            'local': {
                'connected': local_result['success'],
                'data': local_result['stdout'] if local_result['success'] else None,
                'error': local_result['stderr'] if not local_result['success'] else None
            },
            'railway': {
                'connected': railway_result['success'],
                'data': railway_result['stdout'] if railway_result['success'] else None,
                'error': railway_result['stderr'] if not railway_result['success'] else None
            }
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@sync_bp.route('/api/sync_local_to_railway', methods=['POST'])
def sync_local_to_railway():
    """Sync data from local PostgreSQL to Railway"""
    try:
        # Configuration
        LOCAL_CONFIG = {
            'host': 'localhost',
            'port': 5432,
            'user': 'postgres',
            'database': 'hotel_booking',
            'password': 'locloc123'
        }
        
        RAILWAY_CONFIG = {
            'host': 'mainline.proxy.rlwy.net',
            'port': 36647,
            'user': 'postgres',
            'database': 'railway',
            'password': 'VmyAveAhkGVOFlSiVBWgyIEAUbKAXEPi'
        }
        
        # Create export directory
        export_dir = 'sync_export'
        os.makedirs(export_dir, exist_ok=True)
        
        # Tables to sync
        tables = ['guests', 'bookings', 'expenses', 'quick_notes', 'message_templates']
        
        results = {
            'export': {},
            'import': {},
            'summary': {
                'total_tables': len(tables),
                'successful_exports': 0,
                'successful_imports': 0,
                'errors': []
            }
        }
        
        # Export phase
        for table in tables:
            filename = os.path.join(export_dir, f"{table}.csv")
            export_result = export_table_to_csv(
                LOCAL_CONFIG['host'], LOCAL_CONFIG['port'], LOCAL_CONFIG['user'],
                LOCAL_CONFIG['database'], LOCAL_CONFIG['password'],
                table, filename
            )
            
            results['export'][table] = export_result
            if export_result['success']:
                results['summary']['successful_exports'] += 1
            else:
                results['summary']['errors'].append(f"Export {table}: {export_result['error']}")
        
        # Import phase
        for table in tables:
            if results['export'][table]['success']:
                filename = os.path.join(export_dir, f"{table}.csv")
                import_result = import_csv_to_table(
                    RAILWAY_CONFIG['host'], RAILWAY_CONFIG['port'], RAILWAY_CONFIG['user'],
                    RAILWAY_CONFIG['database'], RAILWAY_CONFIG['password'],
                    table, filename
                )
                
                results['import'][table] = import_result
                if import_result['success']:
                    results['summary']['successful_imports'] += 1
                else:
                    results['summary']['errors'].append(f"Import {table}: {import_result['error']}")
            else:
                results['import'][table] = {'success': False, 'error': 'Export failed'}
        
        # Verify final counts
        verification = {}
        for table in ['bookings', 'guests', 'expenses']:
            verify_result = run_psql_command(
                RAILWAY_CONFIG['host'], RAILWAY_CONFIG['port'], RAILWAY_CONFIG['user'],
                RAILWAY_CONFIG['database'], RAILWAY_CONFIG['password'],
                f"SELECT COUNT(*) FROM {table};"
            )
            if verify_result['success']:
                try:
                    count = int(verify_result['stdout'].split('\n')[2].strip())
                    verification[table] = count
                except:
                    verification[table] = 0
            else:
                verification[table] = 0
        
        results['verification'] = verification
        results['success'] = results['summary']['successful_imports'] >= 2  # At least guests and bookings
        
        return jsonify(results)
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@sync_bp.route('/api/sync_railway_to_local', methods=['POST'])
def sync_railway_to_local():
    """Sync data from Railway to local PostgreSQL"""
    try:
        # Same logic as above but reversed
        # Configuration
        LOCAL_CONFIG = {
            'host': 'localhost',
            'port': 5432,
            'user': 'postgres',
            'database': 'hotel_booking',
            'password': 'locloc123'
        }
        
        RAILWAY_CONFIG = {
            'host': 'mainline.proxy.rlwy.net',
            'port': 36647,
            'user': 'postgres',
            'database': 'railway',
            'password': 'VmyAveAhkGVOFlSiVBWgyIEAUbKAXEPi'
        }
        
        # Create export directory
        export_dir = 'railway_export'
        os.makedirs(export_dir, exist_ok=True)
        
        # Tables to sync
        tables = ['guests', 'bookings', 'expenses', 'quick_notes', 'message_templates']
        
        results = {
            'export': {},
            'import': {},
            'summary': {
                'total_tables': len(tables),
                'successful_exports': 0,
                'successful_imports': 0,
                'errors': []
            }
        }
        
        # Export from Railway
        for table in tables:
            filename = os.path.join(export_dir, f"{table}.csv")
            export_result = export_table_to_csv(
                RAILWAY_CONFIG['host'], RAILWAY_CONFIG['port'], RAILWAY_CONFIG['user'],
                RAILWAY_CONFIG['database'], RAILWAY_CONFIG['password'],
                table, filename
            )
            
            results['export'][table] = export_result
            if export_result['success']:
                results['summary']['successful_exports'] += 1
            else:
                results['summary']['errors'].append(f"Export {table}: {export_result['error']}")
        
        # Import to Local
        for table in tables:
            if results['export'][table]['success']:
                filename = os.path.join(export_dir, f"{table}.csv")
                import_result = import_csv_to_table(
                    LOCAL_CONFIG['host'], LOCAL_CONFIG['port'], LOCAL_CONFIG['user'],
                    LOCAL_CONFIG['database'], LOCAL_CONFIG['password'],
                    table, filename
                )
                
                results['import'][table] = import_result
                if import_result['success']:
                    results['summary']['successful_imports'] += 1
                else:
                    results['summary']['errors'].append(f"Import {table}: {import_result['error']}")
            else:
                results['import'][table] = {'success': False, 'error': 'Export failed'}
        
        results['success'] = results['summary']['successful_imports'] >= 2
        
        return jsonify(results)
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@sync_bp.route('/api/switch_database', methods=['POST'])
def switch_database():
    """Switch database source"""
    try:
        data = request.get_json()
        source = data.get('source', '').lower()
        
        if source not in ['local', 'railway', 'auto']:
            return jsonify({'success': False, 'error': 'Invalid source. Use: local, railway, or auto'}), 400
        
        # Update .env file
        env_file = Path('.env')
        if not env_file.exists():
            return jsonify({'success': False, 'error': '.env file not found'}), 500
        
        # Read current .env content
        with open(env_file, 'r') as f:
            lines = f.readlines()
        
        # Update DATABASE_SOURCE line
        updated = False
        for i, line in enumerate(lines):
            if line.startswith('DATABASE_SOURCE='):
                lines[i] = f'DATABASE_SOURCE={source}\n'
                updated = True
                break
        
        if not updated:
            # Add DATABASE_SOURCE if not found
            lines.append(f'DATABASE_SOURCE={source}\n')
        
        # Write updated content
        with open(env_file, 'w') as f:
            f.writelines(lines)
        
        return jsonify({
            'success': True, 
            'message': f'Switched to {source.upper()} database',
            'restart_required': True
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@sync_bp.route('/api/get_database_status', methods=['GET'])
def get_database_status():
    """Get current database configuration status"""
    try:
        import os
        from dotenv import load_dotenv
        load_dotenv()
        
        source = os.getenv('DATABASE_SOURCE', 'auto')
        local_url = os.getenv('LOCAL_DATABASE_URL')
        railway_url = os.getenv('RAILWAY_DATABASE_URL')
        current_url = os.getenv('DATABASE_URL')
        
        # Determine which database is actually being used
        active_database = 'unknown'
        if current_url:
            if 'localhost' in current_url:
                active_database = 'local'
            elif 'railway' in current_url or 'mainline.proxy.rlwy.net' in current_url:
                active_database = 'railway'
            else:
                active_database = 'external'
        
        return jsonify({
            'success': True,
            'current_source': source,
            'active_database': active_database,
            'available': {
                'local': bool(local_url),
                'railway': bool(railway_url)
            },
            'urls': {
                'local': local_url[:50] + '...' if local_url else None,
                'railway': railway_url[:50] + '...' if railway_url else None,
                'current': current_url[:50] + '...' if current_url else None
            }
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500