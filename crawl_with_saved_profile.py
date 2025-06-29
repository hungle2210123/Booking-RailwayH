#!/usr/bin/env python3
"""
Crawl Booking.com using saved browser profile
Uses the profile created by manual_login_setup.py to extract real booking data
"""

import os
import time
import json
import requests
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

class BookingDataCrawler:
    """Crawl real booking data using saved profile"""
    
    def __init__(self, profile_name: str = "booking_manual_profile"):
        self.profile_name = profile_name
        self.profile_path = Path.cwd() / "browser_profiles" / profile_name
        self.driver = None
        self.firecrawl_api_key = "fc-d59dc4eba8ae49cf8ea57c690e48b273"
        
    def crawl_real_bookings(self, target_url: str):
        """Crawl real booking data from admin panel"""
        if not HAS_SELENIUM:
            raise Exception("Selenium not available")
            
        print(f"🕷️ Starting real data crawl from: {target_url}")
        
        try:
            # Use saved profile
            chrome_options = Options()
            chrome_options.add_argument(f"--user-data-dir={self.profile_path}")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--start-maximized")
            
            print("🌐 Opening browser with saved profile...")
            self.driver = webdriver.Chrome(options=chrome_options)
            
            print(f"📍 Navigating to reservations page...")
            self.driver.get(target_url)
            time.sleep(10)  # Wait for page to load completely
            
            # Check if we're logged in
            if "login" in self.driver.current_url.lower():
                print("❌ Profile expired - redirected to login")
                print("Run manual_login_setup.py again to refresh your profile")
                return []
            
            print("✅ Successfully accessed admin panel!")
            
            # Wait for the reservations table to load
            print("⏳ Waiting for reservations table...")
            try:
                table = WebDriverWait(self.driver, 20).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "table.bui-table, .bui-table"))
                )
                print("✅ Found reservations table!")
            except:
                print("⚠️ Table not found with bui-table class, trying alternative selectors...")
                try:
                    table = WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located((By.TAG_NAME, "table"))
                    )
                    print("✅ Found table!")
                except:
                    print("❌ No table found - may need to adjust selectors")
                    return []
            
            # Extract booking data from table rows
            bookings = []
            try:
                # Find all table rows
                rows = self.driver.find_elements(By.CSS_SELECTOR, "tr")
                print(f"📊 Found {len(rows)} total rows")
                
                # Skip header row(s) and process data rows
                data_rows = [row for row in rows if row.find_elements(By.TAG_NAME, "td")]
                print(f"📊 Found {len(data_rows)} data rows")
                
                for i, row in enumerate(data_rows, 1):
                    try:
                        cells = row.find_elements(By.TAG_NAME, "td")
                        if len(cells) >= 7:  # Ensure we have enough columns
                            
                            # Extract data based on your table structure:
                            # Guest name | Check-in | Departure | Room | Placed | Status | Price | ... | Reservation number
                            booking = {
                                "guest_name": cells[0].text.strip() if len(cells) > 0 else "",
                                "checkin_date": cells[1].text.strip() if len(cells) > 1 else "",
                                "checkout_date": cells[2].text.strip() if len(cells) > 2 else "",
                                "room_type": cells[3].text.strip() if len(cells) > 3 else "",
                                "placed_date": cells[4].text.strip() if len(cells) > 4 else "",
                                "status": cells[5].text.strip() if len(cells) > 5 else "",
                                "price": cells[6].text.strip() if len(cells) > 6 else "",
                                "booking_id": cells[-1].text.strip() if len(cells) > 8 else "",  # Last column is usually booking ID
                                "source": "booking.com_admin",
                                "extracted_at": datetime.now().isoformat()
                            }
                            
                            # Only add if we have essential data
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
    
    def crawl_with_firecrawl_authenticated(self, target_url: str):
        """Use Firecrawl with authenticated session"""
        print("🔥 Starting Firecrawl with authenticated session...")
        
        try:
            # First get authenticated session using Selenium
            chrome_options = Options()
            chrome_options.add_argument(f"--user-data-dir={self.profile_path}")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--headless")  # Run headless for Firecrawl
            
            self.driver = webdriver.Chrome(options=chrome_options)
            self.driver.get(target_url)
            time.sleep(8)
            
            # Get authentication cookies
            cookies = self.driver.get_cookies()
            cookie_string = "; ".join([f"{c['name']}={c['value']}" for c in cookies])
            user_agent = self.driver.execute_script("return navigator.userAgent;")
            
            print(f"🍪 Got {len(cookies)} authentication cookies")
            
            # Use Firecrawl with authentication
            payload = {
                "url": target_url,
                "crawlerOptions": {
                    "includeHtml": True,
                    "onlyMainContent": False,
                    "screenshot": True,
                    "waitFor": 10000,
                    "headers": {
                        "Cookie": cookie_string,
                        "User-Agent": user_agent
                    }
                }
            }
            
            headers = {
                "Authorization": f"Bearer {self.firecrawl_api_key}",
                "Content-Type": "application/json"
            }
            
            print("📡 Sending authenticated request to Firecrawl...")
            response = requests.post(
                "https://api.firecrawl.dev/v0/scrape",
                json=payload,
                headers=headers,
                timeout=60
            )
            
            if response.status_code == 200:
                data = response.json()
                print("✅ Firecrawl request successful!")
                
                # Save screenshot for review
                if data.get("data", {}).get("screenshot"):
                    screenshot_path = self.save_screenshot(data["data"]["screenshot"])
                    print(f"📸 Screenshot saved to: {screenshot_path}")
                
                # Extract text content
                markdown_content = data["data"].get("markdown", "")
                print(f"📝 Extracted {len(markdown_content)} characters of text")
                
                return {
                    "screenshot": data["data"].get("screenshot"),
                    "text_content": markdown_content,
                    "html": data["data"].get("html", ""),
                    "success": True
                }
            else:
                print(f"❌ Firecrawl failed: {response.status_code} - {response.text}")
                return {"success": False, "error": response.text}
                
        except Exception as e:
            print(f"❌ Firecrawl with auth failed: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def save_screenshot(self, screenshot_data: str):
        """Save screenshot for review"""
        try:
            import base64
            
            # Handle data URL format
            if screenshot_data.startswith('data:image'):
                image_data = screenshot_data.split(',')[1]
            else:
                image_data = screenshot_data
            
            # Save to file
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"booking_admin_screenshot_{timestamp}.png"
            screenshot_path = Path.cwd() / filename
            
            with open(screenshot_path, 'wb') as f:
                f.write(base64.b64decode(image_data))
            
            return screenshot_path
            
        except Exception as e:
            print(f"❌ Failed to save screenshot: {str(e)}")
            return None
    
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
    
    def close(self):
        """Close browser"""
        if self.driver:
            self.driver.quit()

def main():
    """Main crawling function"""
    print("🏨 Real Booking Data Crawler")
    print("=" * 50)
    
    # Check if profile exists
    profile_path = Path.cwd() / "browser_profiles" / "booking_manual_profile"
    if not profile_path.exists():
        print("❌ No saved profile found!")
        print("Please run 'python manual_login_setup.py' first to create a profile.")
        return
    
    print(f"✅ Found saved profile at: {profile_path}")
    
    # Your actual booking admin URL
    target_url = "https://admin.booking.com/hotel/hoteladmin/extranet_ng/manage/search_reservations.html?upcoming_reservations=1&source=nav&hotel_id=14171449&lang=vi&reservation_status=ok&date_from=2025-07-01&date_to=2025-08-31&date_type=arrival"
    
    crawler = BookingDataCrawler("booking_manual_profile")
    
    try:
        print("\n🔍 Testing saved profile first...")
        # Quick profile test
        chrome_options = Options()
        chrome_options.add_argument(f"--user-data-dir={profile_path}")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--headless")  # Quick headless test
        
        test_driver = webdriver.Chrome(options=chrome_options)
        test_driver.get("https://admin.booking.com/")
        time.sleep(3)
        
        if "login" in test_driver.current_url.lower():
            print("❌ Profile expired or invalid - redirected to login")
            print("Please run 'python manual_login_setup.py' to refresh your profile.")
            test_driver.quit()
            return
        else:
            print("✅ Profile is valid - proceeding with crawling")
            test_driver.quit()
        
        print("\nCrawling options:")
        print("1. Extract table data with Selenium")
        print("2. Get screenshot + text with Firecrawl") 
        print("3. Both methods")
        print("4. Test profile with visible browser")
        print("5. Exit")
        
        choice = input("\nSelect option (1-5): ").strip()
        
        if choice == "1":
            print("\n🕷️ Using Selenium to extract table data...")
            bookings = crawler.crawl_real_bookings(target_url)
            
            if bookings:
                print(f"\n🎉 Found {len(bookings)} real bookings:")
                for i, booking in enumerate(bookings, 1):
                    print(f"{i}. {booking['guest_name']} - {booking['checkin_date']} to {booking['checkout_date']} - {booking['price']}")
                
                # Save results
                filename = crawler.save_results(bookings)
                print(f"\n📁 Full results saved to: {filename}")
            else:
                print("❌ No bookings extracted")
                
        elif choice == "2":
            print("\n🔥 Using Firecrawl to get screenshot + text...")
            result = crawler.crawl_with_firecrawl_authenticated(target_url)
            
            if result.get("success"):
                print("✅ Firecrawl extraction successful!")
                print(f"📝 Text length: {len(result['text_content'])} characters")
                print(f"📸 Screenshot: {'Available' if result['screenshot'] else 'Not available'}")
                
                # Show first 500 chars of text
                if result['text_content']:
                    print("\n📋 First 500 characters of extracted text:")
                    print("-" * 50)
                    print(result['text_content'][:500] + "..." if len(result['text_content']) > 500 else result['text_content'])
                    print("-" * 50)
            else:
                print(f"❌ Firecrawl failed: {result.get('error')}")
                
        elif choice == "3":
            print("\n🔄 Using both methods...")
            # Method 1: Selenium
            bookings = crawler.crawl_real_bookings(target_url)
            
            # Method 2: Firecrawl
            firecrawl_result = crawler.crawl_with_firecrawl_authenticated(target_url)
            
            print(f"\n📊 Selenium results: {len(bookings)} bookings")
            print(f"📊 Firecrawl results: {'Success' if firecrawl_result.get('success') else 'Failed'}")
            
            if bookings:
                crawler.save_results(bookings)
                
        elif choice == "4":
            print("\n🔍 Testing profile with visible browser...")
            # Open browser visibly to test profile
            chrome_options = Options()
            chrome_options.add_argument(f"--user-data-dir={profile_path}")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--start-maximized")
            
            test_driver = webdriver.Chrome(options=chrome_options)
            test_driver.get(target_url)
            
            print("✅ Browser opened with saved profile")
            print("🔍 Check if you can see your booking data without logging in")
            input("Press Enter to close the test browser...")
            test_driver.quit()
            
        elif choice == "5":
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