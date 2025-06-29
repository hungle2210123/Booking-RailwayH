#!/usr/bin/env python3
"""
Smart Chrome Process Management
Only targets specific browser profiles, preserves your dev tools and other Chrome windows
"""

import psutil
import time
import os
from pathlib import Path

def smart_chrome_cleanup(profile_name: str = None):
    """
    Smart cleanup that only targets specific profile-related Chrome processes
    Preserves your main Chrome browser, dev tools, and other tabs
    """
    print("🔍 Smart Chrome cleanup - targeting only automation processes...")
    
    if profile_name:
        profile_path = str(Path.cwd() / "browser_profiles" / profile_name)
        print(f"🎯 Targeting profile: {profile_name}")
        print(f"📁 Profile path: {profile_path}")
    
    killed_count = 0
    preserved_count = 0
    
    try:
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                proc_info = proc.info
                if not proc_info['name'] or 'chrome' not in proc_info['name'].lower():
                    continue
                
                cmdline = proc_info.get('cmdline', [])
                if not cmdline:
                    continue
                
                cmdline_str = ' '.join(cmdline)
                
                # Only kill Chrome processes that match our automation criteria
                should_kill = False
                
                if profile_name and profile_path in cmdline_str:
                    # Kill processes using our specific profile
                    should_kill = True
                    reason = f"using profile {profile_name}"
                elif '--remote-debugging-port=' in cmdline_str:
                    # Kill processes with our debugging ports (9222-9227)
                    debug_ports = ['9222', '9223', '9224', '9225', '9226', '9227']
                    if any(f'--remote-debugging-port={port}' in cmdline_str for port in debug_ports):
                        should_kill = True
                        reason = "using automation debugging port"
                elif '--user-data-dir=' in cmdline_str and 'browser_profiles' in cmdline_str:
                    # Kill any process using our browser_profiles directory
                    should_kill = True
                    reason = "using automation profile directory"
                elif '--disable-blink-features=AutomationControlled' in cmdline_str:
                    # Kill automation-specific Chrome processes
                    should_kill = True
                    reason = "automation-controlled process"
                
                if should_kill:
                    try:
                        print(f"🔴 Killing Chrome process (PID: {proc_info['pid']}) - {reason}")
                        proc.terminate()
                        killed_count += 1
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
                else:
                    preserved_count += 1
                    
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
                
    except Exception as e:
        print(f"⚠️ Error during smart cleanup: {str(e)}")
    
    if killed_count > 0:
        print(f"✅ Smart cleanup complete: Killed {killed_count} automation processes, preserved {preserved_count} regular Chrome processes")
        time.sleep(2)  # Short wait for cleanup
    else:
        print(f"✅ No automation processes found to clean up. {preserved_count} regular Chrome processes preserved.")
    
    return killed_count

def force_cleanup_automation_ports():
    """Emergency cleanup for automation debugging ports only"""
    print("🚨 Emergency cleanup of automation debugging ports...")
    
    debug_ports = ['9222', '9223', '9224', '9225', '9226', '9227']
    killed_count = 0
    
    try:
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                proc_info = proc.info
                if not proc_info['name'] or 'chrome' not in proc_info['name'].lower():
                    continue
                
                cmdline = proc_info.get('cmdline', [])
                if not cmdline:
                    continue
                
                cmdline_str = ' '.join(cmdline)
                
                # Only kill processes using our specific debugging ports
                for port in debug_ports:
                    if f'--remote-debugging-port={port}' in cmdline_str:
                        try:
                            print(f"🔴 Killing automation Chrome process on port {port} (PID: {proc_info['pid']})")
                            proc.terminate()
                            killed_count += 1
                            break
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            pass
                            
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
                
    except Exception as e:
        print(f"⚠️ Error during emergency cleanup: {str(e)}")
    
    print(f"✅ Emergency cleanup complete: Killed {killed_count} automation processes")
    return killed_count

def check_chrome_processes():
    """Check what Chrome processes are running (for debugging)"""
    print("🔍 Checking Chrome processes...")
    
    automation_count = 0
    regular_count = 0
    
    try:
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                proc_info = proc.info
                if not proc_info['name'] or 'chrome' not in proc_info['name'].lower():
                    continue
                
                cmdline = proc_info.get('cmdline', [])
                if not cmdline:
                    continue
                
                cmdline_str = ' '.join(cmdline)
                
                # Check if it's an automation process
                is_automation = (
                    '--remote-debugging-port=' in cmdline_str or
                    'browser_profiles' in cmdline_str or
                    '--disable-blink-features=AutomationControlled' in cmdline_str
                )
                
                if is_automation:
                    automation_count += 1
                    print(f"🤖 Automation process (PID: {proc_info['pid']})")
                else:
                    regular_count += 1
                    print(f"🌐 Regular Chrome process (PID: {proc_info['pid']})")
                    
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
                
    except Exception as e:
        print(f"⚠️ Error checking processes: {str(e)}")
    
    print(f"📊 Summary: {automation_count} automation processes, {regular_count} regular Chrome processes")
    return automation_count, regular_count

if __name__ == "__main__":
    print("🛠️ Smart Chrome Process Manager")
    print("=" * 50)
    
    while True:
        print("\nOptions:")
        print("1. Check Chrome processes")
        print("2. Smart cleanup (profile-specific)")
        print("3. Emergency cleanup (automation ports only)")
        print("4. Exit")
        
        choice = input("\nSelect option (1-4): ").strip()
        
        if choice == "1":
            check_chrome_processes()
            
        elif choice == "2":
            profile_name = input("Enter profile name (or press Enter for all automation): ").strip()
            if not profile_name:
                profile_name = None
            smart_chrome_cleanup(profile_name)
            
        elif choice == "3":
            force_cleanup_automation_ports()
            
        elif choice == "4":
            print("👋 Goodbye!")
            break
            
        else:
            print("❌ Invalid option")