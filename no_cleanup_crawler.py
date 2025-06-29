#!/usr/bin/env python3
"""
No-Cleanup Crawler - Uses unique ports to avoid conflicts
Doesn't kill any Chrome processes, preserves all your windows
"""

import os
import time
import json
import random
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
    HAS_SELENIUM = False

class NoCleanupCrawler:
    """Crawler that doesn't kill any Chrome processes"""
    
    def __init__(self, profile_name: str = "booking_fixed_profile"):
        self.profile_name = profile_name
        self.profile_path = Path.cwd() / "browser_profiles" / profile_name
        self.driver = None
        self.google_api_key = os.getenv('GOOGLE_API_KEY')
        # Use random debugging port to avoid conflicts
        self.debug_port = random.randint(9300, 9400)
        
    def crawl_without_cleanup(self, target_url: str) -> list:
        """Crawl without killing any Chrome processes"""
        print("🔐 No-cleanup crawling - preserving ALL your Chrome windows")
        print(f"🔌 Using debugging port: {self.debug_port}")
        
        try:
            # Setup Chrome with unique debugging port
            chrome_options = Options()
            chrome_options.add_argument(f"--user-data-dir={self.profile_path}")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--force-device-scale-factor=1")
            chrome_options.add_argument(f"--remote-debugging-port={self.debug_port}")
            
            print("🌐 Opening browser with saved profile (no cleanup)...")
            self.driver = webdriver.Chrome(options=chrome_options)
            
            print(f"📍 Navigating to admin panel...")
            self.driver.get(target_url)
            time.sleep(10)
            
            # Check if logged in
            if "login" in self.driver.current_url.lower():
                print("❌ Profile expired - redirected to login")
                return []
            
            print("✅ Successfully accessed admin panel!")
            
            # Wait for table
            try:
                WebDriverWait(self.driver, 20).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "table, .bui-table"))
                )
                print("✅ Table loaded!")
            except:
                print("⚠️ Table not found, proceeding anyway...")
            
            time.sleep(5)
            
            # Take screenshot
            total_height = self.driver.execute_script("return document.body.scrollHeight")
            self.driver.set_window_size(1920, total_height)
            time.sleep(2)
            
            print("📸 Taking screenshot...")
            screenshot_base64 = self.driver.get_screenshot_as_base64()
            
            if screenshot_base64:
                # Process with AI
                print("🤖 Processing with AI...")
                import base64
                screenshot_bytes = base64.b64decode(screenshot_base64)
                
                # Use existing AI function
                from core.logic_postgresql import extract_booking_info_from_image_content
                result = extract_booking_info_from_image_content(screenshot_bytes, self.google_api_key)
                
                if 'error' not in result:
                    bookings = []
                    if result.get('type') == 'multiple' and 'bookings' in result:
                        bookings = result['bookings']
                    elif result.get('guest_name'):
                        bookings = [result]
                    
                    print(f"✅ AI extracted {len(bookings)} bookings!")
                    return bookings
                else:
                    print(f"❌ AI error: {result['error']}")
                    return []
            else:
                print("❌ Screenshot failed")
                return []
                
        except Exception as e:
            print(f"❌ Crawling error: {str(e)}")
            return []
        finally:
            if self.driver:
                try:
                    self.driver.quit()
                except:
                    pass

def main():
    """No-cleanup crawling test"""
    print("🔐 No-Cleanup Booking Crawler")
    print("=" * 40)
    print("This crawler preserves ALL your Chrome windows and dev tools!")
    
    target_url = "https://admin.booking.com/hotel/hoteladmin/extranet_ng/manage/search_reservations.html?upcoming_reservations=1&source=nav&hotel_id=14171449&lang=vi&reservation_status=ok&date_from=2025-07-01&date_to=2025-08-31&date_type=arrival"
    
    crawler = NoCleanupCrawler("booking_fixed_profile")
    
    print("\n🚀 Starting no-cleanup crawl...")
    bookings = crawler.crawl_without_cleanup(target_url)
    
    if bookings:
        print(f"\n🎉 Successfully extracted {len(bookings)} bookings:")
        for i, booking in enumerate(bookings, 1):
            print(f"{i}. {booking.get('guest_name', 'Unknown')} - {booking.get('checkin_date', 'N/A')} to {booking.get('checkout_date', 'N/A')}")
            
        # Save results
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"no_cleanup_bookings_{timestamp}.json"
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(bookings, f, indent=2, ensure_ascii=False)
        print(f"\n📁 Results saved to: {filename}")
    else:
        print("❌ No bookings extracted")

if __name__ == "__main__":
    main()