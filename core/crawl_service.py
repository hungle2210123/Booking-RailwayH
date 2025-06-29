"""
Advanced Web Crawling Service with Profile Management and Firecrawl Integration
Integrates with existing hotel booking AI processing pipeline
"""

import os
import json
import asyncio
import base64
from datetime import datetime
from typing import Dict, List, Optional, Any
import time
import logging
import requests

# Optional imports - will use fallbacks if not available
try:
    import aiohttp
    HAS_AIOHTTP = True
except ImportError:
    HAS_AIOHTTP = False
    
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

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ProfileCrawler:
    """Browser profile management for authenticated crawling"""
    
    def __init__(self, profile_name: str = "default"):
        self.profile_name = profile_name
        self.profile_path = os.path.join(os.getcwd(), "browser_profiles", profile_name)
        self.driver = None
        
    def setup_browser(self, headless: bool = False):
        """Setup Chrome browser with saved profile"""
        chrome_options = Options()
        
        # Use saved profile for persistent login
        chrome_options.add_argument(f"--user-data-dir={self.profile_path}")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        if headless:
            chrome_options.add_argument("--headless")
            
        # Create profile directory if it doesn't exist
        os.makedirs(self.profile_path, exist_ok=True)
        
        self.driver = webdriver.Chrome(options=chrome_options)
        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        return self.driver
    
    def save_login_session(self, login_url: str, username: str, password: str, 
                          username_selector: str, password_selector: str, 
                          submit_selector: str):
        """Save login session to browser profile"""
        try:
            logger.info(f"Saving login session for {login_url}")
            
            if not self.driver:
                self.setup_browser()
                
            self.driver.get(login_url)
            time.sleep(3)
            
            # Fill login form
            username_field = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, username_selector))
            )
            username_field.clear()
            username_field.send_keys(username)
            
            password_field = self.driver.find_element(By.CSS_SELECTOR, password_selector)
            password_field.clear()
            password_field.send_keys(password)
            
            # Submit form
            submit_button = self.driver.find_element(By.CSS_SELECTOR, submit_selector)
            submit_button.click()
            
            # Wait for login to complete
            time.sleep(5)
            
            logger.info(f"✅ Login session saved to profile: {self.profile_name}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error saving login session: {str(e)}")
            return False
    
    def close(self):
        """Close browser and save session"""
        if self.driver:
            self.driver.quit()

class FirecrawlService:
    """Firecrawl API integration for content extraction"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.firecrawl.dev/v0"
        
    def crawl_page(self, url: str, options: Dict = None) -> Dict:
        """Crawl a single page with Firecrawl (sync version)"""
        if options is None:
            options = {
                "includeHtml": True,
                "onlyMainContent": True,
                "screenshot": True,
                "waitFor": 5000  # Wait 5 seconds for JavaScript to load
            }
            
        payload = {
            "url": url,
            "crawlerOptions": options
        }
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/scrape", 
                json=payload, 
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"✅ Successfully crawled: {url}")
                return result
            else:
                logger.error(f"❌ Firecrawl error {response.status_code}: {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Firecrawl request failed: {str(e)}")
            return None

class BookingCrawler:
    """Main booking data crawler with AI integration"""
    
    def __init__(self, firecrawl_api_key: str, profile_name: str = "booking_profile"):
        self.firecrawl = FirecrawlService(firecrawl_api_key)
        self.profile_crawler = ProfileCrawler(profile_name)
        
    def setup_booking_profile(self, platform: str, credentials: Dict):
        """Setup browser profile for specific booking platform"""
        platform_configs = {
            "booking.com": {
                "login_url": "https://account.booking.com/sign-in",
                "username_selector": "#username",
                "password_selector": "#password", 
                "submit_selector": "button[type='submit']"
            },
            "agoda.com": {
                "login_url": "https://www.agoda.com/account/signin",
                "username_selector": "#email",
                "password_selector": "#password",
                "submit_selector": "button[data-selenium='loginBtn']"
            },
            "airbnb.com": {
                "login_url": "https://www.airbnb.com/login",
                "username_selector": "#email",
                "password_selector": "#password",
                "submit_selector": "button[type='submit']"
            }
        }
        
        if platform not in platform_configs:
            raise ValueError(f"Platform {platform} not supported")
            
        config = platform_configs[platform]
        
        # Setup browser and save login
        self.profile_crawler.setup_browser()
        return self.profile_crawler.save_login_session(
            config["login_url"],
            credentials["username"],
            credentials["password"],
            config["username_selector"],
            config["password_selector"],
            config["submit_selector"]
        )
    
    def crawl_booking_data(self, booking_urls: List[str]) -> List[Dict]:
        """Crawl booking data from multiple URLs (sync version)"""
        results = []
        
        for url in booking_urls:
            try:
                logger.info(f"🕷️ Crawling: {url}")
                
                # Special handling for Booking.com admin panel
                crawl_options = {
                    "includeHtml": True,
                    "onlyMainContent": False,  # Include full page for admin panels
                    "screenshot": True,
                    "waitFor": 8000  # Wait longer for admin panels to load
                }
                
                # Use Firecrawl to get page content and screenshot
                crawl_result = self.firecrawl.crawl_page(url, crawl_options)
                
                if crawl_result and "data" in crawl_result:
                    data = crawl_result["data"]
                    
                    # Extract screenshot if available
                    screenshot_data = data.get("screenshot")
                    markdown_content = data.get("markdown", "")
                    
                    logger.info(f"📊 Extracted {len(markdown_content)} chars of text")
                    
                    # Process with existing AI pipeline
                    if screenshot_data:
                        booking_data = self.process_with_ai(screenshot_data, markdown_content)
                        if booking_data:
                            booking_data["source_url"] = url
                            booking_data["crawl_timestamp"] = datetime.now().isoformat()
                            results.append(booking_data)
                            logger.info(f"✅ Extracted booking: {booking_data.get('guest_name', 'Unknown')}")
                    else:
                        logger.warning(f"⚠️ No screenshot data available for {url}")
                
                # Rate limiting
                time.sleep(2)
                
            except Exception as e:
                logger.error(f"❌ Error crawling {url}: {str(e)}")
                continue
                
        return results
    
    def process_with_ai(self, screenshot_data: str, markdown_content: str) -> Optional[Dict]:
        """Process crawled data using existing AI pipeline"""
        try:
            # Import existing AI processing function
            from core.logic_postgresql import extract_booking_info_from_image_content
            import os
            
            # Convert base64 screenshot to image data
            if screenshot_data.startswith('data:image'):
                # Remove data URL prefix
                image_data = screenshot_data.split(',')[1]
            else:
                image_data = screenshot_data
                
            # Prepare enhanced prompt for Booking.com admin data
            enhanced_prompt = f"""
            This is a screenshot from Booking.com admin panel reservation list. Extract ALL visible booking information.
            
            Text content from page: {markdown_content[:1500]}
            
            For EACH booking visible, extract:
            - guest_name (full name)
            - booking_id (reservation number)  
            - checkin_date (arrival date in YYYY-MM-DD format)
            - checkout_date (departure date in YYYY-MM-DD format)
            - room_amount (total booking amount, numeric only)
            - commission (if visible or calculable)
            - email (guest email if visible)
            - phone (guest phone if visible)
            - nights (number of nights)
            - guests (number of guests)
            
            If multiple bookings are visible, return an array of booking objects.
            If only one booking, return a single object.
            Return clean JSON without trailing commas.
            """
            
            # Process with existing Gemini AI
            image_bytes = base64.b64decode(image_data)
            api_key = os.getenv('GOOGLE_API_KEY')
            
            result = extract_booking_info_from_image_content(image_bytes, api_key, enhanced_prompt)
            
            if result and not result.get('error'):
                logger.info(f"🤖 AI extracted: {result}")
                return result
            else:
                logger.error(f"❌ AI extraction failed: {result}")
                
        except Exception as e:
            logger.error(f"❌ AI processing error: {str(e)}")
            
        return None
    
    def close(self):
        """Cleanup resources"""
        self.profile_crawler.close()

# Integration with Flask app
class CrawlIntegration:
    """Integration point for Flask application"""
    
    @staticmethod
    def setup_crawl_routes(app):
        """Add crawling routes to Flask app"""
        from flask import request, jsonify
        
        @app.route('/crawl', methods=['GET'])
        def crawl_page():
            """Crawling interface page"""
            from flask import render_template
            return render_template('crawl_bookings.html')
        
        @app.route('/api/setup_crawl_profile', methods=['POST'])
        def setup_crawl_profile():
            """API endpoint to setup crawling profile"""
            try:
                data = request.get_json()
                platform = data.get('platform')
                credentials = data.get('credentials')
                
                crawler = BookingCrawler(
                    firecrawl_api_key=os.environ.get('FIRECRAWL_API_KEY'),
                    profile_name=f"{platform}_profile"
                )
                
                success = crawler.setup_booking_profile(platform, credentials)
                crawler.close()
                
                if success:
                    return jsonify({
                        'success': True,
                        'message': f'Profile setup complete for {platform}'
                    })
                else:
                    return jsonify({
                        'success': False,
                        'message': 'Profile setup failed'
                    }), 400
                    
            except Exception as e:
                return jsonify({
                    'success': False,
                    'message': str(e)
                }), 500
        
        @app.route('/api/crawl_bookings', methods=['POST'])
        def crawl_bookings():
            """API endpoint to crawl booking data"""
            try:
                data = request.get_json()
                urls = data.get('urls', [])
                
                if not urls:
                    return jsonify({
                        'success': False,
                        'message': 'No URLs provided'
                    }), 400
                
                # Run async crawling
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                crawler = BookingCrawler(
                    firecrawl_api_key=os.environ.get('FIRECRAWL_API_KEY')
                )
                
                results = loop.run_until_complete(crawler.crawl_booking_data(urls))
                crawler.close()
                loop.close()
                
                return jsonify({
                    'success': True,
                    'bookings_extracted': len(results),
                    'data': results
                })
                
            except Exception as e:
                return jsonify({
                    'success': False,
                    'message': str(e)
                }), 500

# Example usage
if __name__ == "__main__":
    # Example: Setup profile and crawl
    async def example_usage():
        # Initialize crawler
        crawler = BookingCrawler(
            firecrawl_api_key="your_firecrawl_api_key",
            profile_name="my_booking_profile"
        )
        
        # Setup profile for Booking.com
        success = crawler.setup_booking_profile("booking.com", {
            "username": "your_email@example.com",
            "password": "your_password"
        })
        
        if success:
            # Crawl booking pages
            urls = [
                "https://booking.com/booking-details/12345",
                "https://booking.com/booking-details/67890"
            ]
            
            results = await crawler.crawl_booking_data(urls)
            print(f"Extracted {len(results)} bookings")
            
            for booking in results:
                print(f"Guest: {booking.get('guest_name')}")
                print(f"Amount: {booking.get('room_amount')}")
        
        crawler.close()
    
    # Run example
    # asyncio.run(example_usage())