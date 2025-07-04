#!/usr/bin/env python3
"""
Smart Railway Startup Script
Handles Railway's environment variable issues and ensures proper application startup
"""

import os
import sys
import subprocess
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

def validate_and_fix_port():
    """
    Validate and fix PORT environment variable issues
    Railway sometimes passes malformed PORT values
    """
    port = os.environ.get('PORT', '5000')
    
    logger.info(f"🔍 Raw PORT value from Railway: '{port}'")
    logger.info(f"🔍 PORT type: {type(port)}")
    
    # Handle common Railway PORT issues
    if port == '$PORT':
        logger.warning("⚠️ Railway passed literal '$PORT' string - fixing to 5000")
        port = '5000'
    elif port == '' or port is None:
        logger.warning("⚠️ PORT is empty/None - setting to 5000")
        port = '5000'
    elif not isinstance(port, str):
        logger.warning(f"⚠️ PORT is not string ({type(port)}) - converting")
        port = str(port)
    
    # Validate PORT is numeric
    try:
        port_int = int(port)
        if port_int < 1 or port_int > 65535:
            logger.warning(f"⚠️ PORT {port_int} out of valid range - setting to 5000")
            port = '5000'
        else:
            logger.info(f"✅ PORT validation successful: {port}")
    except (ValueError, TypeError):
        logger.warning(f"❌ PORT '{port}' is not numeric - setting to 5000")
        port = '5000'
    
    # Set the corrected PORT back to environment
    os.environ['PORT'] = port
    return port

def setup_environment():
    """
    Setup Railway environment variables and handle common issues
    """
    logger.info("🚀 Railway Smart Environment Setup Starting...")
    
    # Validate and fix PORT
    port = validate_and_fix_port()
    
    # Check for Railway environment indicators
    railway_indicators = [
        'RAILWAY_ENVIRONMENT_ID',
        'RAILWAY_PROJECT_ID', 
        'RAILWAY_SERVICE_ID',
        'RAILWAY_DEPLOYMENT_ID'
    ]
    
    is_railway = any(os.environ.get(indicator) for indicator in railway_indicators)
    logger.info(f"🔍 Railway environment detected: {'✅ YES' if is_railway else '❌ NO'}")
    
    # Set production settings for Railway
    if is_railway:
        os.environ['FLASK_ENV'] = 'production'
        os.environ['ENV'] = 'production'
        os.environ['DEBUG'] = 'false'
        logger.info("🏭 Production environment settings applied")
    
    # Database URL handling
    db_urls = ['DATABASE_URL', 'POSTGRES_URL', 'POSTGRESQL_URL']
    db_url = None
    for url_key in db_urls:
        if os.environ.get(url_key):
            db_url = os.environ[url_key]
            logger.info(f"📊 Database URL found: {url_key}")
            break
    
    if not db_url:
        logger.warning("⚠️ No database URL found in environment")
    
    return port

def start_gunicorn(port):
    """
    Start Gunicorn with proper configuration
    """
    logger.info(f"🦄 Starting Gunicorn on 0.0.0.0:{port}")
    
    # Gunicorn command with robust configuration
    cmd = [
        'python', '-m', 'gunicorn',
        'app:app',
        '--bind', f'0.0.0.0:{port}',
        '--workers', '1',
        '--timeout', '120',
        '--worker-class', 'sync',
        '--max-requests', '1000',
        '--max-requests-jitter', '100',
        '--log-level', 'info',
        '--access-logfile', '-',
        '--error-logfile', '-'
    ]
    
    logger.info(f"🔧 Gunicorn command: {' '.join(cmd)}")
    
    try:
        # Start Gunicorn
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        logger.error(f"❌ Gunicorn failed to start: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("🛑 Received interrupt signal, shutting down...")
        sys.exit(0)

def main():
    """
    Main startup function
    """
    try:
        # Setup environment and get validated PORT
        port = setup_environment()
        
        # Start the application
        start_gunicorn(port)
        
    except Exception as e:
        logger.error(f"💥 Startup failed: {e}")
        logger.error(f"Environment variables: {dict(os.environ)}")
        sys.exit(1)

if __name__ == '__main__':
    main()