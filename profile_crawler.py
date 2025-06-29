#!/usr/bin/env python3
"""
Booking.com Profile-Based Crawler
Handles browser profile setup, login automation, and data extraction
"""

import os
import time
import json
import base64
from datetime import datetime
from pathlib import Path
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Try to import Selenium (optional)
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException, WebDriverException
    HAS_SELENIUM = True
except ImportError:
    HAS_SELENIUM = False
    logger.warning("Selenium not available. Install with: pip install selenium webdriver-manager")

# Try to import requests for Firecrawl
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False
    logger.warning("Requests not available. Install with: pip install requests")

class BookingProfileCrawler:
    """Profile-based crawler for Booking.com admin panel"""
    
    def __init__(self, profile_name: str = "booking_profile"):
        self.profile_name = profile_name
        self.profile_path = Path.cwd() / "browser_profiles" / profile_name
        self.driver = None
        self.firecrawl_api_key = os.getenv('FIRECRAWL_API_KEY')
        
        # Create profile directory
        self.profile_path.mkdir(parents=True, exist_ok=True)
        
    def setup_browser_profile(self, username: str, password: str, headless: bool = False):
        """Setup browser profile with Booking.com login"""
        if not HAS_SELENIUM:
            raise Exception("Selenium not available. Please install selenium and webdriver-manager")
            
        logger.info(f"🚀 Setting up browser profile: {self.profile_name}")
        
        try:
            # Chrome options for profile
            chrome_options = Options()
            chrome_options.add_argument(f"--user-data-dir={self.profile_path}")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            
            if headless:
                chrome_options.add_argument("--headless")
                
            # Launch browser
            logger.info("🌐 Launching Chrome browser...")
            self.driver = webdriver.Chrome(options=chrome_options)
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            # Navigate to login page
            login_url = "https://admin.booking.com/"
            logger.info(f"📍 Navigating to: {login_url}")
            self.driver.get(login_url)
            time.sleep(3)
            
            # Wait for and fill username
            logger.info("📝 Filling login credentials...")
            username_field = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.NAME, "username"))
            )
            username_field.clear()
            username_field.send_keys(username)
            
            # Click Next button
            next_button = self.driver.find_element(By.XPATH, "//button[contains(text(), 'Next') or contains(text(), 'Tiếp theo')]")
            next_button.click()
            time.sleep(2)
            
            # Wait for password field and fill it
            password_field = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.NAME, "password"))
            )
            password_field.clear()
            password_field.send_keys(password)
            
            # Click Login button
            login_button = self.driver.find_element(By.XPATH, "//button[@type='submit']")
            login_button.click()
            
            logger.info("⏳ Waiting for login to complete...")
            time.sleep(10)  # Wait for login and any 2FA
            
            # Check if we're logged in by looking for admin elements
            current_url = self.driver.current_url
            if "admin.booking.com" in current_url and "login" not in current_url:
                logger.info("✅ Login successful! Profile saved.")
                return True
            else:
                logger.warning("⚠️ Login may require manual completion (2FA, captcha, etc.)")
                logger.info("💡 Please complete login manually in the browser, then run test_saved_profile()")
                return False
                
        except Exception as e:
            logger.error(f"❌ Profile setup failed: {str(e)}")
            return False
            
    def test_saved_profile(self):
        """Test if saved profile can access admin panel"""
        if not HAS_SELENIUM:
            raise Exception("Selenium not available")
            
        logger.info("🧪 Testing saved browser profile...")
        
        try:
            chrome_options = Options()
            chrome_options.add_argument(f"--user-data-dir={self.profile_path}")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            
            self.driver = webdriver.Chrome(options=chrome_options)
            
            # Test access to admin panel
            admin_url = "https://admin.booking.com/hotel/hoteladmin/extranet_ng/manage/search_reservations.html"
            logger.info(f"📍 Testing access to: {admin_url}")
            self.driver.get(admin_url)
            time.sleep(5)
            
            # Check if we can access the reservations
            if "login" in self.driver.current_url.lower():
                logger.error("❌ Profile not working - redirected to login")
                return False
            else:
                logger.info("✅ Profile working - admin panel accessible")
                return True
                
        except Exception as e:
            logger.error(f"❌ Profile test failed: {str(e)}")
            return False
            
    def crawl_with_selenium(self, target_url: str):
        """Crawl booking data using Selenium"""
        if not HAS_SELENIUM:
            raise Exception("Selenium not available")
            
        logger.info("🕷️ Starting Selenium crawling...")
        
        try:
            chrome_options = Options()
            chrome_options.add_argument(f"--user-data-dir={self.profile_path}")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            
            self.driver = webdriver.Chrome(options=chrome_options)
            
            logger.info(f"📍 Navigating to: {target_url}")
            self.driver.get(target_url)
            time.sleep(8)  # Wait for page to load
            
            # Wait for reservation table
            table = WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "table, .bui-table"))
            )
            
            # Extract table data
            bookings = []
            rows = self.driver.find_elements(By.CSS_SELECTOR, "tr.bui-table__row")
            
            logger.info(f"📊 Found {len(rows)} table rows")
            
            for row in rows[1:]:  # Skip header row
                cells = row.find_elements(By.TAG_NAME, "td")
                if len(cells) >= 7:  # Ensure we have enough columns
                    booking = {
                        "guest_name": cells[0].text.strip() if len(cells) > 0 else "",
                        "checkin_date": cells[1].text.strip() if len(cells) > 1 else "",
                        "checkout_date": cells[2].text.strip() if len(cells) > 2 else "",
                        "room_type": cells[3].text.strip() if len(cells) > 3 else "",
                        "placed_date": cells[4].text.strip() if len(cells) > 4 else "",
                        "status": cells[5].text.strip() if len(cells) > 5 else "",
                        "price": cells[6].text.strip() if len(cells) > 6 else "",
                        "booking_id": cells[8].text.strip() if len(cells) > 8 else "",
                    }
                    
                    if booking["guest_name"]:  # Only add if guest name exists
                        bookings.append(booking)
            
            logger.info(f"✅ Extracted {len(bookings)} bookings")
            return bookings
            
        except Exception as e:
            logger.error(f"❌ Selenium crawling failed: {str(e)}")
            return []
            
    def crawl_with_firecrawl(self, target_url: str):
        """Crawl booking data using Firecrawl API"""
        if not HAS_REQUESTS:
            raise Exception("Requests library not available")
            
        if not self.firecrawl_api_key:
            raise Exception("FIRECRAWL_API_KEY not set in environment")
            
        logger.info("🔥 Starting Firecrawl crawling...")
        
        try:
            # First use Selenium to get authenticated page
            chrome_options = Options()
            chrome_options.add_argument(f"--user-data-dir={self.profile_path}")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            
            self.driver = webdriver.Chrome(options=chrome_options)
            self.driver.get(target_url)
            time.sleep(8)
            
            # Get cookies for authenticated request
            cookies = self.driver.get_cookies()
            cookie_string = "; ".join([f"{c['name']}={c['value']}" for c in cookies])
            
            # Use Firecrawl with authentication
            payload = {
                "url": target_url,
                "crawlerOptions": {
                    "includeHtml": True,
                    "onlyMainContent": False,
                    "screenshot": True,
                    "waitFor": 8000,
                    "headers": {
                        "Cookie": cookie_string,
                        "User-Agent": self.driver.execute_script("return navigator.userAgent;")
                    }
                }
            }
            
            headers = {
                "Authorization": f"Bearer {self.firecrawl_api_key}",
                "Content-Type": "application/json"
            }
            
            logger.info("📡 Sending request to Firecrawl...")
            response = requests.post(
                "https://api.firecrawl.dev/v0/scrape",
                json=payload,
                headers=headers,
                timeout=60
            )
            
            if response.status_code == 200:
                data = response.json()
                logger.info("✅ Firecrawl request successful")
                
                # Process with AI if available
                if data.get("data", {}).get("screenshot"):
                    screenshot_data = data["data"]["screenshot"]
                    markdown_content = data["data"].get("markdown", "")
                    
                    # Save screenshot for review
                    self.save_screenshot(screenshot_data)
                    
                    # Here you would integrate with your existing AI processing
                    logger.info("🤖 AI processing would happen here")
                    
                return data
            else:
                logger.error(f"❌ Firecrawl failed: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Firecrawl crawling failed: {str(e)}")
            return None
            
    def save_screenshot(self, screenshot_data: str, filename: str = None):
        """Save screenshot for review"""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"booking_screenshot_{timestamp}.png"
            
        try:
            # Handle data URL format
            if screenshot_data.startswith('data:image'):
                image_data = screenshot_data.split(',')[1]
            else:
                image_data = screenshot_data
                
            # Save to file
            screenshot_path = self.profile_path / filename
            with open(screenshot_path, 'wb') as f:
                f.write(base64.b64decode(image_data))
                
            logger.info(f"📸 Screenshot saved: {screenshot_path}")
            return screenshot_path
            
        except Exception as e:
            logger.error(f"❌ Failed to save screenshot: {str(e)}")
            return None
            
    def close(self):
        """Close browser"""
        if self.driver:
            self.driver.quit()
            
def main():
    """Test the crawler"""
    print("🏨 Booking.com Profile Crawler Test")
    print("=" * 50)
    
    # Initialize crawler
    crawler = BookingProfileCrawler("booking_test_profile")
    
    try:
        # Setup profile (you'll need to enter credentials)
        username = input("Enter Booking.com username/email: ")
        password = input("Enter password: ")
        
        print("\n1. Setting up browser profile...")
        success = crawler.setup_browser_profile(username, password)
        
        if success:
            print("✅ Profile setup complete!")
        else:
            print("⚠️ Manual completion may be required")
            
        input("Press Enter after completing any manual login steps...")
        
        # Test saved profile
        print("\n2. Testing saved profile...")
        if crawler.test_saved_profile():
            print("✅ Profile working!")
            
            # Crawl data
            target_url = "https://admin.booking.com/hotel/hoteladmin/extranet_ng/manage/search_reservations.html?upcoming_reservations=1&source=nav&hotel_id=14171449&lang=vi&reservation_status=ok&date_from=2025-07-01&date_to=2025-08-31&date_type=arrival"
            
            print("\n3. Crawling booking data...")
            bookings = crawler.crawl_with_selenium(target_url)
            
            print(f"\n📊 Results: {len(bookings)} bookings found")
            for i, booking in enumerate(bookings[:3], 1):  # Show first 3
                print(f"{i}. {booking['guest_name']} - {booking['checkin_date']} to {booking['checkout_date']}")
                
        else:
            print("❌ Profile not working")
            
    except KeyboardInterrupt:
        print("\n⏹️ Cancelled by user")
    except Exception as e:
        print(f"❌ Error: {str(e)}")
    finally:
        crawler.close()

if __name__ == "__main__":
    main()