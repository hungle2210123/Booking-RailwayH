#!/usr/bin/env python3
"""
Fixed Crawling Script with Chrome Process Management
Handles Chrome conflicts and properly uses saved profiles
"""

import os
import time
import json
import psutil
from pathlib import Path
from datetime import datetime
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

class FixedBookingCrawler:
    """Fixed crawler with proper Chrome process management"""
    
    def __init__(self, profile_name: str = "booking_fixed_profile"):
        self.profile_name = profile_name
        self.profile_path = Path.cwd() / "browser_profiles" / profile_name
        self.driver = None
        
    def kill_chrome_processes(self):
        """Kill Chrome processes to prevent conflicts"""
        print("🔄 Cleaning up Chrome processes...")
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
                time.sleep(3)
            else:
                print("✅ No Chrome processes to clean up")
                
        except Exception as e:
            print(f"⚠️ Could not clean Chrome processes: {str(e)}")
    
    def crawl_real_bookings(self, target_url: str):
        """Crawl real booking data with proper process management"""
        if not HAS_SELENIUM:
            raise Exception("Selenium not available")
            
        print(f"🕷️ Starting real data crawl...")
        
        # Clean up Chrome processes first
        self.kill_chrome_processes()
        
        try:
            # Setup Chrome with saved profile
            chrome_options = Options()
            chrome_options.add_argument(f"--user-data-dir={self.profile_path}")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--start-maximized")
            chrome_options.add_argument("--remote-debugging-port=9224")  # Unique port
            
            print("🌐 Opening browser with saved profile...")
            self.driver = webdriver.Chrome(options=chrome_options)
            
            print(f"📍 Navigating to reservations page...")
            self.driver.get(target_url)
            time.sleep(10)
            
            # Check if logged in
            if "login" in self.driver.current_url.lower():
                print("❌ Profile expired - redirected to login")
                print("Run 'python fixed_profile_setup.py' to refresh your profile")
                return []
            
            print("✅ Successfully accessed admin panel!")
            
            # Wait for reservations table
            print("⏳ Waiting for reservations table...")
            try:
                table = WebDriverWait(self.driver, 20).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "table.bui-table, .bui-table, table"))
                )
                print("✅ Found reservations table!")
            except:
                print("❌ No table found - page may not be loaded correctly")
                return []
            
            # Extract booking data
            bookings = []
            try:
                rows = self.driver.find_elements(By.CSS_SELECTOR, "tr")
                print(f"📊 Found {len(rows)} total rows")
                
                data_rows = [row for row in rows if row.find_elements(By.TAG_NAME, "td")]
                print(f"📊 Found {len(data_rows)} data rows")
                
                for i, row in enumerate(data_rows, 1):
                    try:
                        cells = row.find_elements(By.TAG_NAME, "td")
                        if len(cells) >= 7:
                            booking = {
                                "guest_name": cells[0].text.strip() if len(cells) > 0 else "",
                                "checkin_date": cells[1].text.strip() if len(cells) > 1 else "",
                                "checkout_date": cells[2].text.strip() if len(cells) > 2 else "",
                                "room_type": cells[3].text.strip() if len(cells) > 3 else "",
                                "placed_date": cells[4].text.strip() if len(cells) > 4 else "",
                                "status": cells[5].text.strip() if len(cells) > 5 else "",
                                "price": cells[6].text.strip() if len(cells) > 6 else "",
                                "booking_id": cells[-1].text.strip() if len(cells) > 8 else "",
                                "source": "booking.com_admin",
                                "extracted_at": datetime.now().isoformat()
                            }
                            
                            if booking["guest_name"] and booking["guest_name"] != "Guest name":
                                bookings.append(booking)
                                print(f"✅ Row {i}: {booking['guest_name']} - {booking['checkin_date']} to {booking['checkout_date']}")
                            
                    except Exception as e:
                        print(f"⚠️ Error processing row {i}: {str(e)}")
                        continue
                
            except Exception as e:
                print(f"❌ Error extracting table data: {str(e)}")
            
            print(f"🎉 Successfully extracted {len(bookings)} real bookings!")
            return bookings
            
        except Exception as e:
            print(f"❌ Crawling failed: {str(e)}")
            return []
    
    def save_results(self, bookings: list, filename: str = None):
        """Save extracted bookings to JSON file"""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"extracted_bookings_{timestamp}.json"
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(bookings, f, indent=2, ensure_ascii=False)
            
            print(f"💾 Results saved to: {filename}")
            return filename
            
        except Exception as e:
            print(f"❌ Failed to save results: {str(e)}")
            return None
    
    def test_profile_visually(self, target_url: str):
        """Test profile with visible browser"""
        print("🔍 Testing profile with visible browser...")
        
        # Clean up first
        self.kill_chrome_processes()
        
        try:
            chrome_options = Options()
            chrome_options.add_argument(f"--user-data-dir={self.profile_path}")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--start-maximized")
            chrome_options.add_argument("--remote-debugging-port=9225")
            
            self.driver = webdriver.Chrome(options=chrome_options)
            self.driver.get(target_url)
            
            print("✅ Browser opened with saved profile")
            print("🔍 Check if you can see your booking data without logging in")
            input("Press Enter to close the test browser...")
            
        except Exception as e:
            print(f"❌ Visual test failed: {str(e)}")
    
    def close(self):
        """Properly close browser and clean up"""
        if self.driver:
            try:
                self.driver.quit()
                time.sleep(2)
            except:
                pass

def main():
    """Main function with improved Chrome process management"""
    print("🏨 Fixed Real Booking Data Crawler")
    print("=" * 50)
    
    # Check if profile exists
    profile_path = Path.cwd() / "browser_profiles" / "booking_fixed_profile"
    if not profile_path.exists():
        print("❌ No saved profile found!")
        print("Please run 'python fixed_profile_setup.py' first to create a profile.")
        return
    
    print(f"✅ Found saved profile at: {profile_path}")
    
    target_url = "https://admin.booking.com/hotel/hoteladmin/extranet_ng/manage/search_reservations.html?upcoming_reservations=1&source=nav&hotel_id=14171449&lang=vi&reservation_status=ok&date_from=2025-07-01&date_to=2025-08-31&date_type=arrival"
    
    crawler = FixedBookingCrawler("booking_fixed_profile")
    
    try:
        print("\nCrawling options:")
        print("1. Extract real booking data")
        print("2. Test profile with visible browser")
        print("3. Clean up Chrome processes")
        print("4. Exit")
        
        choice = input("\nSelect option (1-4): ").strip()
        
        if choice == "1":
            print("\n🕷️ Extracting real booking data...")
            bookings = crawler.crawl_real_bookings(target_url)
            
            if bookings:
                print(f"\n🎉 Found {len(bookings)} real bookings:")
                for i, booking in enumerate(bookings, 1):
                    print(f"{i}. {booking['guest_name']} - {booking['checkin_date']} to {booking['checkout_date']} - {booking['price']}")
                
                filename = crawler.save_results(bookings)
                print(f"\n📁 Full results saved to: {filename}")
                
                # Integration option
                integrate = input("\n💾 Save to your hotel database? (y/n): ").strip().lower()
                if integrate == 'y':
                    print("🔗 Integration with hotel database would happen here")
                    print("This would use your existing hotel booking system APIs")
            else:
                print("❌ No bookings extracted")
                
        elif choice == "2":
            print("\n🔍 Testing profile visually...")
            crawler.test_profile_visually(target_url)
            
        elif choice == "3":
            print("\n🔄 Cleaning up Chrome processes...")
            crawler.kill_chrome_processes()
            print("✅ Cleanup complete")
            
        elif choice == "4":
            print("👋 Goodbye!")
            
        else:
            print("❌ Invalid option")
            
    except KeyboardInterrupt:
        print("\n⏹️ Cancelled by user")
    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}")
    finally:
        crawler.close()

if __name__ == "__main__":
    main()