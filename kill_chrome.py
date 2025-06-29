#!/usr/bin/env python3
"""Quick Chrome process killer"""

import psutil
import time

def kill_all_chrome():
    """Kill all Chrome processes"""
    print("🔄 Killing all Chrome processes...")
    killed_count = 0
    
    try:
        for proc in psutil.process_iter(['pid', 'name']):
            if proc.info['name'] and 'chrome' in proc.info['name'].lower():
                try:
                    print(f"  Killing: {proc.info['name']} (PID: {proc.info['pid']})")
                    proc.terminate()
                    killed_count += 1
                except:
                    try:
                        proc.kill()
                        killed_count += 1
                    except:
                        pass
        
        if killed_count > 0:
            print(f"✅ Killed {killed_count} Chrome process(es)")
            time.sleep(3)
        else:
            print("✅ No Chrome processes found")
            
    except Exception as e:
        print(f"❌ Error: {str(e)}")

if __name__ == "__main__":
    kill_all_chrome()
    print("✅ Done! Now you can run the profile setup.")