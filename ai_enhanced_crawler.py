#!/usr/bin/env python3
"""
AI-Enhanced Booking Crawler with Full Page Screenshot + Gemini AI
Uses your existing Gemini AI setup from the add guest section
"""

import os
import time
import json
import psutil
import base64
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

class AIEnhancedBookingCrawler:
    """Enhanced crawler with full page screenshot + Gemini AI"""
    
    def __init__(self, profile_name: str = "booking_fixed_profile"):
        self.profile_name = profile_name
        self.profile_path = Path.cwd() / "browser_profiles" / profile_name
        self.driver = None
        self.google_api_key = os.getenv('GOOGLE_API_KEY')
        
        if not self.google_api_key:
            print("❌ GOOGLE_API_KEY not found in environment!")
            print("Please set your API key in .env file")
    
    def kill_chrome_processes(self):
        """Smart Chrome cleanup using dedicated function"""
        from smart_chrome_cleanup import smart_chrome_cleanup
        smart_chrome_cleanup(self.profile_name)
    
    def take_full_page_screenshot(self, target_url: str) -> bytes:
        """Take full page screenshot and return image bytes"""
        if not HAS_SELENIUM:
            raise Exception("Selenium not available")
            
        print(f"📸 Taking full page screenshot of booking admin...")
        
        # Clean up Chrome processes first
        self.kill_chrome_processes()
        
        try:
            # Setup Chrome for full page screenshot
            chrome_options = Options()
            chrome_options.add_argument(f"--user-data-dir={self.profile_path}")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--start-maximized")
            chrome_options.add_argument("--remote-debugging-port=9226")
            
            # Enable full page screenshot
            chrome_options.add_argument("--force-device-scale-factor=1")
            chrome_options.add_argument("--disable-web-security")
            
            print("🌐 Opening browser with saved profile...")
            self.driver = webdriver.Chrome(options=chrome_options)
            
            print(f"📍 Navigating to reservations page...")
            self.driver.get(target_url)
            time.sleep(10)  # Wait for page to load completely
            
            # Check if logged in
            if "login" in self.driver.current_url.lower():
                print("❌ Profile expired - redirected to login")
                print("Please refresh your profile first")
                return None
            
            print("✅ Successfully accessed admin panel!")
            
            # Wait for table to load
            print("⏳ Waiting for reservations table to load...")
            try:
                WebDriverWait(self.driver, 20).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "table, .bui-table"))
                )
                print("✅ Table loaded!")
            except:
                print("⚠️ Table not found, proceeding with screenshot anyway...")
            
            # Additional wait for all content to load
            time.sleep(5)
            
            # Get page dimensions for full page screenshot
            total_height = self.driver.execute_script("return document.body.scrollHeight")
            viewport_height = self.driver.execute_script("return window.innerHeight")
            
            print(f"📏 Page height: {total_height}px, Viewport: {viewport_height}px")
            
            # Set window size to capture full page
            self.driver.set_window_size(1920, total_height)
            time.sleep(2)
            
            # Take screenshot
            print("📸 Capturing full page screenshot...")
            screenshot_base64 = self.driver.get_screenshot_as_base64()
            screenshot_bytes = base64.b64decode(screenshot_base64)
            
            # Save screenshot locally for review
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            screenshot_path = Path.cwd() / f"booking_admin_full_{timestamp}.png"
            with open(screenshot_path, 'wb') as f:
                f.write(screenshot_bytes)
            
            print(f"📸 Screenshot saved: {screenshot_path}")
            print(f"📊 Screenshot size: {len(screenshot_bytes)} bytes")
            
            return screenshot_bytes
            
        except Exception as e:
            print(f"❌ Screenshot failed: {str(e)}")
            return None
        finally:
            if self.driver:
                self.driver.quit()
    
    def extract_bookings_with_ai(self, screenshot_bytes: bytes) -> dict:
        """Use enhanced Gemini AI specifically for Booking.com admin table"""
        if not screenshot_bytes:
            return {'error': 'No screenshot data available'}
            
        if not self.google_api_key:
            return {'error': 'Google API key not available'}
        
        print("🤖 Processing screenshot with Enhanced Gemini AI...")
        
        try:
            # Try enhanced extractor first (better for admin tables)
            try:
                from enhanced_ai_extractor import extract_booking_table_with_enhanced_ai
                print("🚀 Using enhanced AI extractor for Booking.com admin table...")
                result = extract_booking_table_with_enhanced_ai(screenshot_bytes, self.google_api_key)
                
                if 'error' not in result:
                    print("✅ Enhanced AI extraction successful!")
                    return result
                else:
                    print(f"⚠️ Enhanced extractor failed: {result['error']}")
            except ImportError:
                print("⚠️ Enhanced extractor not available, using standard extractor...")
            
            # Fallback to existing AI function
            from core.logic_postgresql import extract_booking_info_from_image_content
            print("🔄 Using standard AI extractor as fallback...")
            
            result = extract_booking_info_from_image_content(screenshot_bytes, self.google_api_key)
            
            if 'error' in result:
                print(f"❌ AI extraction error: {result['error']}")
                return result
            else:
                print("✅ Standard AI extraction successful!")
                return result
                
        except Exception as e:
            print(f"❌ AI processing failed: {str(e)}")
            return {'error': str(e)}
    
    def process_ai_results(self, ai_result: dict) -> list:
        """Process AI results into standardized booking format"""
        bookings = []
        
        try:
            if 'error' in ai_result:
                print(f"❌ AI result contains error: {ai_result['error']}")
                return bookings
            
            # Handle both single and multiple booking formats
            if ai_result.get('type') == 'single':
                booking = ai_result.get('booking', {})
                if booking.get('guest_name'):
                    booking['source'] = 'ai_extraction'
                    booking['extracted_at'] = datetime.now().isoformat()
                    bookings.append(booking)
                    print(f"✅ Processed single booking: {booking.get('guest_name')}")
                    
            elif ai_result.get('type') == 'multiple':
                ai_bookings = ai_result.get('bookings', [])
                for booking in ai_bookings:
                    if booking.get('guest_name'):
                        booking['source'] = 'ai_extraction'
                        booking['extracted_at'] = datetime.now().isoformat()
                        bookings.append(booking)
                        print(f"✅ Processed booking: {booking.get('guest_name')}")
                        
            # Handle direct array format (fallback)
            elif isinstance(ai_result, list):
                for booking in ai_result:
                    if booking.get('guest_name'):
                        booking['source'] = 'ai_extraction'
                        booking['extracted_at'] = datetime.now().isoformat()
                        bookings.append(booking)
                        print(f"✅ Processed booking: {booking.get('guest_name')}")
                        
            # Handle single booking object (fallback)
            elif ai_result.get('guest_name'):
                ai_result['source'] = 'ai_extraction'
                ai_result['extracted_at'] = datetime.now().isoformat()
                bookings.append(ai_result)
                print(f"✅ Processed single booking: {ai_result.get('guest_name')}")
            
            print(f"🎉 Total bookings processed: {len(bookings)}")
            return bookings
            
        except Exception as e:
            print(f"❌ Error processing AI results: {str(e)}")
            return bookings
    
    def save_results(self, bookings: list, ai_result: dict = None) -> str:
        """Save extracted bookings and AI result to files"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        try:
            # Save processed bookings
            bookings_filename = f"ai_extracted_bookings_{timestamp}.json"
            with open(bookings_filename, 'w', encoding='utf-8') as f:
                json.dump(bookings, f, indent=2, ensure_ascii=False)
            
            print(f"💾 Bookings saved to: {bookings_filename}")
            
            # Save raw AI result for debugging
            if ai_result:
                ai_filename = f"ai_raw_result_{timestamp}.json"
                with open(ai_filename, 'w', encoding='utf-8') as f:
                    json.dump(ai_result, f, indent=2, ensure_ascii=False)
                
                print(f"💾 Raw AI result saved to: {ai_filename}")
            
            return bookings_filename
            
        except Exception as e:
            print(f"❌ Failed to save results: {str(e)}")
            return None

def main():
    """Main AI-enhanced crawling function"""
    print("🤖 AI-Enhanced Booking Data Crawler")
    print("=" * 50)
    
    # Check if profile exists
    profile_path = Path.cwd() / "browser_profiles" / "booking_fixed_profile"
    if not profile_path.exists():
        print("❌ No saved profile found!")
        print("Please run 'python fixed_profile_setup.py' first to create a profile.")
        return
    
    print(f"✅ Found saved profile at: {profile_path}")
    
    # Check API key
    api_key = os.getenv('GOOGLE_API_KEY')
    if not api_key:
        print("❌ GOOGLE_API_KEY not found!")
        print("Please add GOOGLE_API_KEY to your .env file")
        return
    
    print(f"✅ Found Google API key: {api_key[:10]}...")
    
    target_url = "https://admin.booking.com/hotel/hoteladmin/extranet_ng/manage/search_reservations.html?upcoming_reservations=1&source=nav&hotel_id=14171449&lang=vi&reservation_status=ok&date_from=2025-07-01&date_to=2025-08-31&date_type=arrival"
    
    crawler = AIEnhancedBookingCrawler("booking_fixed_profile")
    
    try:
        print("\n🤖 AI-Enhanced Extraction Options:")
        print("1. Full AI extraction (Screenshot + Gemini)")
        print("2. Take screenshot only (for manual review)")
        print("3. Clean up Chrome processes")
        print("4. Exit")
        
        choice = input("\nSelect option (1-4): ").strip()
        
        if choice == "1":
            print("\n🤖 Starting AI-enhanced extraction...")
            
            # Step 1: Take full page screenshot
            screenshot_bytes = crawler.take_full_page_screenshot(target_url)
            
            if screenshot_bytes:
                # Step 2: Process with AI
                ai_result = crawler.extract_bookings_with_ai(screenshot_bytes)
                
                # Step 3: Process results
                bookings = crawler.process_ai_results(ai_result)
                
                if bookings:
                    print(f"\n🎉 AI extracted {len(bookings)} bookings:")
                    for i, booking in enumerate(bookings, 1):
                        print(f"{i}. {booking.get('guest_name', 'Unknown')} - {booking.get('checkin_date', 'N/A')} to {booking.get('checkout_date', 'N/A')}")
                        if booking.get('room_amount'):
                            print(f"   Amount: {booking.get('room_amount')} - ID: {booking.get('booking_id', 'N/A')}")
                    
                    # Save results
                    filename = crawler.save_results(bookings, ai_result)
                    print(f"\n📁 Results saved to: {filename}")
                    
                    # Integration option
                    integrate = input("\n💾 Save to your hotel database? (y/n): ").strip().lower()
                    if integrate == 'y':
                        print("🔗 Integration with hotel database:")
                        print("You can use the saved JSON file with your existing import functions")
                        print("Or modify this script to call your database functions directly")
                else:
                    print("❌ No bookings extracted from AI analysis")
                    if ai_result:
                        print(f"Raw AI result: {ai_result}")
            else:
                print("❌ Failed to take screenshot")
                
        elif choice == "2":
            print("\n📸 Taking screenshot for manual review...")
            screenshot_bytes = crawler.take_full_page_screenshot(target_url)
            
            if screenshot_bytes:
                print("✅ Screenshot saved - you can review it manually")
            else:
                print("❌ Failed to take screenshot")
                
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

if __name__ == "__main__":
    main()