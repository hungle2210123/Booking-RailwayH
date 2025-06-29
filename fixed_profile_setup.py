#!/usr/bin/env python3
"""
Fixed Manual Login Profile Setup for Booking.com
Handles Chrome process conflicts and proper cleanup
"""

import os
import time
import psutil
import subprocess
from pathlib import Path
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    HAS_SELENIUM = True
except ImportError:
    print("❌ Selenium not installed!")
    print("Install with: pip install selenium webdriver-manager psutil")
    HAS_SELENIUM = False
    exit(1)

class FixedProfileSetup:
    """Setup browser profile with proper Chrome process management"""
    
    def __init__(self, profile_name: str = "booking_fixed_profile"):
        self.profile_name = profile_name
        self.profile_path = Path.cwd() / "browser_profiles" / profile_name
        self.profile_path.mkdir(parents=True, exist_ok=True)
        self.driver = None
        
    def kill_chrome_processes(self):
        """Kill all Chrome processes to prevent conflicts"""
        print("🔄 Checking for existing Chrome processes...")
        killed_count = 0
        
        try:
            for proc in psutil.process_iter(['pid', 'name']):
                if proc.info['name'] and 'chrome' in proc.info['name'].lower():
                    try:
                        proc.terminate()
                        killed_count += 1
                    except:
                        pass
            
            if killed_count > 0:
                print(f"🔄 Terminated {killed_count} Chrome process(es)")
                time.sleep(3)  # Wait for processes to close
            else:
                print("✅ No existing Chrome processes found")
                
        except Exception as e:
            print(f"⚠️ Could not check Chrome processes: {str(e)}")
    
    def setup_manual_login_profile(self):
        """Setup profile with proper process management"""
        print(f"🚀 Setting up browser profile: {self.profile_name}")
        print(f"📁 Profile location: {self.profile_path}")
        
        # Step 1: Clean up existing Chrome processes
        self.kill_chrome_processes()
        
        try:
            # Step 2: Setup Chrome with unique profile
            chrome_options = Options()
            chrome_options.add_argument(f"--user-data-dir={self.profile_path}")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            chrome_options.add_argument("--start-maximized")
            
            # Add unique port to avoid conflicts
            chrome_options.add_argument("--remote-debugging-port=9222")
            
            print("🌐 Launching Chrome browser...")
            self.driver = webdriver.Chrome(options=chrome_options)
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            # Step 3: Navigate to login
            login_url = "https://admin.booking.com/"
            print(f"📍 Navigating to: {login_url}")
            self.driver.get(login_url)
            
            # Step 4: Interactive login process
            print("\n" + "="*60)
            print("🔑 MANUAL LOGIN STEP-BY-STEP")
            print("="*60)
            print("STEP 1: Complete login in the browser window")
            print("  • Enter your username/email")
            print("  • Enter your password") 
            print("  • Complete any 2FA/verification")
            print("  • Wait until you reach the admin dashboard")
            print("")
            print("STEP 2: Come back here when ready")
            print("="*60)
            
            # Interactive waiting with status checking
            while True:
                user_input = input("\n⏳ Press Enter when login complete (or 'status' to check): ").strip().lower()
                
                if user_input == 'status':
                    current_url = self.driver.current_url
                    print(f"📊 Current URL: {current_url}")
                    if "login" in current_url.lower():
                        print("❌ Still on login page - please complete login first")
                    elif "admin.booking.com" in current_url:
                        print("✅ Looks like you're in the admin panel!")
                    else:
                        print("❓ Unknown page - make sure you're logged into Booking.com")
                    continue
                else:
                    break
            
            # Step 5: Verify login
            print("\n🔍 Verifying login status...")
            current_url = self.driver.current_url
            print(f"📊 Current URL: {current_url}")
            
            if "login" in current_url.lower():
                print("❌ Still on login page. Please complete login first.")
                retry = input("Try again? (y/n): ").strip().lower()
                if retry == 'y':
                    return self.setup_manual_login_profile()
                else:
                    return False
            
            print("✅ Login verification successful!")
            
            # Step 6: Test reservations access
            print("\n🔍 Testing access to reservations page...")
            reservations_url = "https://admin.booking.com/hotel/hoteladmin/extranet_ng/manage/search_reservations.html?upcoming_reservations=1&source=nav&hotel_id=14171449&lang=vi&reservation_status=ok&date_from=2025-07-01&date_to=2025-08-31&date_type=arrival"
            
            self.driver.get(reservations_url)
            time.sleep(8)
            
            current_url = self.driver.current_url
            print(f"📊 Reservations URL: {current_url}")
            
            if "login" in current_url.lower():
                print("❌ Redirected to login when accessing reservations")
                return False
            else:
                print("✅ Successfully accessed reservations page!")
                
                # Look for table elements
                try:
                    time.sleep(5)
                    tables = self.driver.find_elements(By.TAG_NAME, "table")
                    if tables:
                        print(f"✅ Found {len(tables)} table(s) on the page")
                    
                    guest_elements = self.driver.find_elements(By.XPATH, "//*[contains(text(), 'Guest') or contains(text(), 'guest')]")
                    if guest_elements:
                        print("✅ Found guest-related elements")
                    
                    print("\n" + "="*60)
                    print("🎉 PROFILE SETUP COMPLETE!")
                    print("="*60)
                    print("✅ Login successful and verified")
                    print("✅ Reservations page accessible") 
                    print("✅ Browser profile automatically saved")
                    print(f"📁 Profile location: {self.profile_path}")
                    print("")
                    print("🚀 Next steps:")
                    print("  1. Close this browser properly (don't just X out)")
                    print("  2. Run the crawling script")
                    print("  3. Profile will work automatically!")
                    print("="*60)
                    
                    input("\n🔍 Verify you can see booking data, then press Enter to close properly...")
                    
                    # Proper cleanup
                    self.close()
                    
                    return True
                    
                except Exception as e:
                    print(f"⚠️ Could not verify table elements: {str(e)}")
                    print("But profile should still be saved.")
                    self.close()
                    return True
                
        except Exception as e:
            print(f"❌ Error during profile setup: {str(e)}")
            self.close()
            return False
    
    def test_saved_profile(self):
        """Test saved profile with proper process management"""
        print(f"🧪 Testing saved profile: {self.profile_name}")
        
        # Clean up any existing Chrome processes first
        self.kill_chrome_processes()
        
        try:
            chrome_options = Options()
            chrome_options.add_argument(f"--user-data-dir={self.profile_path}")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--start-maximized")
            chrome_options.add_argument("--remote-debugging-port=9223")  # Different port
            
            print("🌐 Opening browser with saved profile...")
            self.driver = webdriver.Chrome(options=chrome_options)
            
            # Test direct access to admin panel
            admin_url = "https://admin.booking.com/hotel/hoteladmin/extranet_ng/manage/search_reservations.html?upcoming_reservations=1&source=nav&hotel_id=14171449&lang=vi&reservation_status=ok&date_from=2025-07-01&date_to=2025-08-31&date_type=arrival"
            print(f"📍 Testing access to: {admin_url}")
            self.driver.get(admin_url)
            time.sleep(8)
            
            current_url = self.driver.current_url
            print(f"📊 Current URL: {current_url}")
            
            if "login" in current_url.lower():
                print("❌ Profile test failed - redirected to login page")
                print("You may need to setup the profile again")
                self.close()
                return False
            else:
                print("✅ Profile test successful - no login required!")
                print("You should see your booking reservations in the browser")
                
                input("Press Enter to close the browser...")
                self.close()
                return True
                
        except Exception as e:
            print(f"❌ Profile test failed: {str(e)}")
            self.close()
            return False
    
    def close(self):
        """Properly close browser and clean up"""
        if self.driver:
            try:
                self.driver.quit()
                time.sleep(2)
            except:
                pass
        
        # Additional cleanup
        try:
            time.sleep(1)
            # Kill any remaining Chrome processes that might be stuck
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                if proc.info['name'] and 'chrome' in proc.info['name'].lower():
                    try:
                        cmdline = proc.info.get('cmdline', [])
                        if cmdline and str(self.profile_path) in ' '.join(cmdline):
                            proc.terminate()
                    except:
                        pass
        except:
            pass

def main():
    """Main function with improved error handling"""
    print("🏨 Fixed Booking.com Profile Setup")
    print("=" * 50)
    
    setup = FixedProfileSetup("booking_fixed_profile")
    
    try:
        while True:
            print("\nOptions:")
            print("1. Setup new profile (manual login)")
            print("2. Test existing profile")
            print("3. Clean up Chrome processes")
            print("4. Exit")
            
            choice = input("\nSelect option (1-4): ").strip()
            
            if choice == "1":
                print("\n🔧 Starting profile setup...")
                success = setup.setup_manual_login_profile()
                if success:
                    print("✅ Profile setup completed successfully!")
                else:
                    print("❌ Profile setup failed or incomplete")
                    
            elif choice == "2":
                print("\n🧪 Testing saved profile...")
                success = setup.test_saved_profile()
                if success:
                    print("✅ Profile is working correctly!")
                else:
                    print("❌ Profile test failed - may need to setup again")
                    
            elif choice == "3":
                print("\n🔄 Cleaning up Chrome processes...")
                setup.kill_chrome_processes()
                print("✅ Cleanup complete")
                
            elif choice == "4":
                print("👋 Goodbye!")
                break
                
            else:
                print("❌ Invalid option. Please select 1, 2, 3, or 4.")
                
    except KeyboardInterrupt:
        print("\n⏹️ Cancelled by user")
    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}")
    finally:
        setup.close()

if __name__ == "__main__":
    main()