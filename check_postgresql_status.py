#!/usr/bin/env python3
"""
PostgreSQL Status Checker
Check if PostgreSQL is running and accessible
"""

import socket
import subprocess
import sys
import platform

def check_port_open(host, port):
    """Check if a port is open on a host"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(3)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except Exception:
        return False

def check_postgresql_service():
    """Check if PostgreSQL service is running"""
    system = platform.system().lower()
    
    try:
        if system == "windows":
            # Check Windows services
            result = subprocess.run(['sc', 'query', 'postgresql-x64-14'], 
                                  capture_output=True, text=True)
            if result.returncode == 0 and 'RUNNING' in result.stdout:
                return True, "PostgreSQL service is running"
            
            # Try other common service names
            services = ['postgresql-x64-13', 'postgresql-x64-12', 'postgresql-x64-15']
            for service in services:
                result = subprocess.run(['sc', 'query', service], 
                                      capture_output=True, text=True)
                if result.returncode == 0 and 'RUNNING' in result.stdout:
                    return True, f"PostgreSQL service ({service}) is running"
            
            return False, "PostgreSQL service not found or not running"
            
        elif system == "darwin":  # macOS
            result = subprocess.run(['brew', 'services', 'list'], 
                                  capture_output=True, text=True)
            if 'postgresql' in result.stdout and 'started' in result.stdout:
                return True, "PostgreSQL service is running (brew)"
            return False, "PostgreSQL service not running"
            
        elif system == "linux":
            result = subprocess.run(['systemctl', 'is-active', 'postgresql'], 
                                  capture_output=True, text=True)
            if result.stdout.strip() == 'active':
                return True, "PostgreSQL service is running (systemctl)"
            return False, "PostgreSQL service not running"
        
        else:
            return False, f"Unsupported system: {system}"
            
    except Exception as e:
        return False, f"Error checking service: {e}"

def test_connection_methods():
    """Test different connection methods"""
    hosts = [
        ('localhost', 'Local hostname'),
        ('127.0.0.1', 'IPv4 loopback'),
        ('::1', 'IPv6 loopback')
    ]
    
    port = 5432
    results = []
    
    for host, description in hosts:
        if check_port_open(host, port):
            results.append((host, description, True))
        else:
            results.append((host, description, False))
    
    return results

def check_psql_command():
    """Check if psql command is available"""
    try:
        result = subprocess.run(['psql', '--version'], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            return True, result.stdout.strip()
        return False, "psql command not found"
    except Exception as e:
        return False, f"Error running psql: {e}"

def get_system_info():
    """Get system information"""
    return {
        'system': platform.system(),
        'release': platform.release(),
        'machine': platform.machine(),
        'python_version': sys.version.split()[0]
    }

def main():
    """Main diagnostic function"""
    print("🔍 PostgreSQL Connection Diagnostic Tool")
    print("=" * 50)
    
    # System info
    info = get_system_info()
    print(f"💻 System: {info['system']} {info['release']} ({info['machine']})")
    print(f"🐍 Python: {info['python_version']}")
    print()
    
    # Check PostgreSQL service
    print("🔧 Checking PostgreSQL Service...")
    service_running, service_msg = check_postgresql_service()
    if service_running:
        print(f"✅ {service_msg}")
    else:
        print(f"❌ {service_msg}")
    print()
    
    # Check port accessibility
    print("🌐 Checking Port Accessibility...")
    connection_results = test_connection_methods()
    
    working_hosts = []
    for host, description, accessible in connection_results:
        if accessible:
            print(f"✅ {host} ({description}) - Port 5432 is open")
            working_hosts.append(host)
        else:
            print(f"❌ {host} ({description}) - Port 5432 is not accessible")
    print()
    
    # Check psql command
    print("🛠️ Checking PostgreSQL Client...")
    psql_available, psql_msg = check_psql_command()
    if psql_available:
        print(f"✅ {psql_msg}")
    else:
        print(f"❌ {psql_msg}")
    print()
    
    # Recommendations
    print("💡 Recommendations for pgAdmin 4:")
    print("-" * 30)
    
    if working_hosts:
        print("✅ PostgreSQL appears to be accessible!")
        print("🔗 Use these connection settings in pgAdmin 4:")
        print()
        for host in working_hosts:
            print(f"   Host name/address: {host}")
            print(f"   Port: 5432")
            print(f"   Username: postgres")
            print(f"   Password: [your PostgreSQL password]")
            print(f"   Maintenance database: postgres")
            print()
        
        print("🎯 Try connecting with the FIRST working host above.")
        
    else:
        print("❌ PostgreSQL is not accessible!")
        print("🔧 To fix this:")
        
        if not service_running:
            system = platform.system().lower()
            if system == "windows":
                print("   1. Start PostgreSQL service:")
                print("      - Open Command Prompt as Administrator")
                print("      - Run: net start postgresql-x64-14")
                print("      - Or use Services: Win+R → services.msc → Find PostgreSQL → Start")
            elif system == "darwin":
                print("   1. Start PostgreSQL service:")
                print("      - Run: brew services start postgresql")
            elif system == "linux":
                print("   1. Start PostgreSQL service:")
                print("      - Run: sudo systemctl start postgresql")
        
        print("   2. Verify PostgreSQL installation")
        print("   3. Check firewall settings")
        print("   4. Ensure PostgreSQL is configured to listen on localhost")
    
    print()
    print("📚 For detailed setup instructions, see: PGADMIN_SETUP_GUIDE.md")
    print("🔧 For connection issues, see: PGADMIN_CONNECTION_FIX.md")

if __name__ == '__main__':
    main()