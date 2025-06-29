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
    return render_template('sync_dashboard.html')

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