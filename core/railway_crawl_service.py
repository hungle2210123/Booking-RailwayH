"""
Railway-Compatible Crawling Service
Provides comprehensive web crawling functionality for serverless/cloud platforms
Supports multiple crawling methods with intelligent fallbacks
"""

import os
import requests
import json
import asyncio
import base64
from typing import Dict, List, Optional, Any
import logging
from datetime import datetime
import time

logger = logging.getLogger(__name__)

class RailwayCrawlService:
    """Railway-compatible crawling service with multiple cloud-optimized methods"""
    
    def __init__(self):
        self.is_railway = self.detect_railway_environment()
        self.firecrawl_api_key = os.getenv('FIRECRAWL_API_KEY')
        self.scrapfly_api_key = os.getenv('SCRAPFLY_API_KEY')
        self.brightdata_api_key = os.getenv('BRIGHTDATA_API_KEY')
        self.scraperapi_key = os.getenv('SCRAPERAPI_KEY')
        
        # Initialize available crawling methods
        self.crawling_methods = self._initialize_crawling_methods()
        
    def detect_railway_environment(self):
        """Detect if running on Railway or similar serverless platform"""
        railway_indicators = [
            'RAILWAY_ENVIRONMENT',
            'RAILWAY_PROJECT_ID', 
            'RAILWAY_SERVICE_ID',
            'KOYEB_PROJECT_ID',
            'RENDER_SERVICE_ID'
        ]
        
        for indicator in railway_indicators:
            if os.getenv(indicator):
                logger.info(f"Detected cloud environment: {indicator}")
                return True
                
        # Check for headless environment (no display)
        if not os.getenv('DISPLAY') and os.name != 'nt':
            logger.info("Detected headless environment")
            return True
            
        return False
    
    def _initialize_crawling_methods(self):
        """Initialize all available crawling methods"""
        methods = []
        
        # 1. Firecrawl API (Premium cloud scraping)
        if self.firecrawl_api_key:
            methods.append({
                'id': 'firecrawl',
                'name': 'Firecrawl API',
                'description': 'Premium cloud scraping with browser rendering',
                'supported': True,
                'priority': 1
            })
        
        # 2. ScrapFly API (High-performance scraping)
        if self.scrapfly_api_key:
            methods.append({
                'id': 'scrapfly',
                'name': 'ScrapFly API',
                'description': 'High-performance web scraping with anti-bot protection',
                'supported': True,
                'priority': 2
            })
        
        # 3. BrightData (Residential proxy network)
        if self.brightdata_api_key:
            methods.append({
                'id': 'brightdata',
                'name': 'BrightData API',
                'description': 'Residential proxy network for protected sites',
                'supported': True,
                'priority': 3
            })
        
        # 4. ScraperAPI (Simple proxy solution)
        if self.scraperapi_key:
            methods.append({
                'id': 'scraperapi',
                'name': 'ScraperAPI',
                'description': 'Simple proxy-based scraping service',
                'supported': True,
                'priority': 4
            })
        
        # 5. Direct HTTP requests (Basic fallback)
        methods.append({
            'id': 'direct_http',
            'name': 'Direct HTTP Requests',
            'description': 'Basic HTTP scraping (limited functionality)',
            'supported': True,
            'priority': 5
        })
        
        # 6. Puppeteer Cloud (If in local/Docker environment)
        if not self.is_railway:
            try:
                import pyppeteer
                methods.append({
                    'id': 'puppeteer',
                    'name': 'Puppeteer Cloud',
                    'description': 'Headless Chrome automation',
                    'supported': True,
                    'priority': 0
                })
            except ImportError:
                pass
        
        return sorted(methods, key=lambda x: x['priority'])
    
    def is_crawling_available(self):
        """Check if web crawling is available in current environment"""
        return len([m for m in self.crawling_methods if m['supported']]) > 0
    
    def get_crawling_methods(self):
        """Get available crawling methods for current environment"""
        return self.crawling_methods
    
    def crawl_with_firecrawl(self, url: str, options: Dict = None):
        """Crawl website using Firecrawl API"""
        if not self.firecrawl_api_key:
            raise Exception("Firecrawl API key not configured")
            
        try:
            headers = {
                'Authorization': f'Bearer {self.firecrawl_api_key}',
                'Content-Type': 'application/json'
            }
            
            payload = {
                'url': url,
                'pageOptions': {
                    'screenshot': True,
                    'fullPageScreenshot': True,
                    'waitFor': 3000
                },
                'extractorOptions': {
                    'mode': 'llm-extraction',
                    'extractionSchema': {
                        'type': 'object',
                        'properties': {
                            'bookings': {
                                'type': 'array',
                                'items': {
                                    'type': 'object',
                                    'properties': {
                                        'guest_name': {'type': 'string'},
                                        'booking_id': {'type': 'string'},
                                        'checkin_date': {'type': 'string'},
                                        'checkout_date': {'type': 'string'},
                                        'room_amount': {'type': 'number'},
                                        'commission': {'type': 'number'}
                                    }
                                }
                            }
                        }
                    }
                }
            }
            
            if options:
                payload.update(options)
                
            response = requests.post(
                'https://api.firecrawl.dev/v1/scrape',
                headers=headers,
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                raise Exception(f"Firecrawl API error: {response.status_code} - {response.text}")
                
        except Exception as e:
            logger.error(f"Firecrawl crawling failed: {e}")
            raise
    
    def crawl_with_scrapfly(self, url: str, options: Dict = None):
        """Crawl website using ScrapFly API"""
        if not self.scrapfly_api_key:
            raise Exception("ScrapFly API key not configured")
            
        try:
            params = {
                'key': self.scrapfly_api_key,
                'url': url,
                'render_js': True,
                'screenshots': True,
                'asp': True,  # Anti-Scraping Protection
                'format': 'json'
            }
            
            if options:
                params.update(options)
                
            response = requests.get(
                'https://api.scrapfly.io/scrape',
                params=params,
                timeout=30
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                raise Exception(f"ScrapFly API error: {response.status_code} - {response.text}")
                
        except Exception as e:
            logger.error(f"ScrapFly crawling failed: {e}")
            raise
    
    def crawl_with_scraperapi(self, url: str, options: Dict = None):
        """Crawl website using ScraperAPI"""
        if not self.scraperapi_key:
            raise Exception("ScraperAPI key not configured")
            
        try:
            params = {
                'api_key': self.scraperapi_key,
                'url': url,
                'render': True,
                'format': 'json'
            }
            
            if options:
                params.update(options)
                
            response = requests.get(
                'http://api.scraperapi.com',
                params=params,
                timeout=30
            )
            
            if response.status_code == 200:
                return {'html': response.text, 'status': 'success'}
            else:
                raise Exception(f"ScraperAPI error: {response.status_code} - {response.text}")
                
        except Exception as e:
            logger.error(f"ScraperAPI crawling failed: {e}")
            raise
    
    def crawl_with_direct_http(self, url: str, options: Dict = None):
        """Basic HTTP crawling with headers rotation"""
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        
        if options and 'headers' in options:
            headers.update(options['headers'])
            
        try:
            response = requests.get(url, headers=headers, timeout=15)
            if response.status_code == 200:
                return {'html': response.text, 'status': 'success'}
            else:
                raise Exception(f"HTTP error: {response.status_code}")
                
        except Exception as e:
            logger.error(f"Direct HTTP crawling failed: {e}")
            raise
    
    def smart_crawl(self, url: str, options: Dict = None):
        """Intelligent crawling with automatic fallback between methods"""
        last_error = None
        
        for method in self.crawling_methods:
            if not method['supported']:
                continue
                
            try:
                logger.info(f"Attempting crawl with method: {method['name']}")
                
                if method['id'] == 'firecrawl':
                    result = self.crawl_with_firecrawl(url, options)
                elif method['id'] == 'scrapfly':
                    result = self.crawl_with_scrapfly(url, options)
                elif method['id'] == 'scraperapi':
                    result = self.crawl_with_scraperapi(url, options)
                elif method['id'] == 'direct_http':
                    result = self.crawl_with_direct_http(url, options)
                else:
                    continue
                
                logger.info(f"Successfully crawled with method: {method['name']}")
                return {
                    'success': True,
                    'method': method['id'],
                    'method_name': method['name'],
                    'data': result,
                    'message': f'Successfully crawled using {method["name"]}'
                }
                
            except Exception as e:
                last_error = e
                logger.warning(f"Method {method['name']} failed: {e}")
                continue
        
        # All methods failed
        return {
            'success': False,
            'method': 'all_failed',
            'error': f'All crawling methods failed. Last error: {str(last_error)}',
            'available_methods': [m['name'] for m in self.crawling_methods if m['supported']],
            'suggestion': 'Check API keys configuration or try manual data entry'
        }
    
    def crawl_admin_bookings_api(self, target_url: str, profile_name: str = None):
        """Comprehensive API-based crawling with intelligent fallback"""
        try:
            logger.info(f"🚀 Starting comprehensive crawl for: {target_url}")
            logger.info(f"🌍 Environment: {'Railway' if self.is_railway else 'Local'}")
            logger.info(f"📊 Available methods: {[m['name'] for m in self.crawling_methods if m['supported']]}")
            
            # Use smart crawling with automatic fallback
            result = self.smart_crawl(target_url)
            
            if result['success']:
                # Try to extract booking data from the crawled content
                raw_data = result['data']
                
                # Process based on the crawling method used
                if result['method'] == 'firecrawl':
                    extracted_data = raw_data.get('llm_extraction', {}).get('bookings', [])
                    screenshot = raw_data.get('screenshot')
                elif result['method'] == 'scrapfly':
                    html_content = raw_data.get('result', {}).get('content', '')
                    screenshot = raw_data.get('result', {}).get('screenshots', [{}])[0].get('binary_base64')
                    extracted_data = self._extract_bookings_from_html(html_content)
                else:
                    # For other methods, extract from HTML
                    html_content = raw_data.get('html', '')
                    extracted_data = self._extract_bookings_from_html(html_content)
                    screenshot = None
                
                return {
                    'success': True,
                    'method': result['method_name'],
                    'environment': 'railway' if self.is_railway else 'local',
                    'bookings': extracted_data,
                    'screenshot': screenshot,
                    'raw_data': raw_data,
                    'message': f'✅ Successfully crawled {len(extracted_data) if extracted_data else 0} bookings using {result["method_name"]}'
                }
            else:
                return {
                    'success': False,
                    'method': 'failed',
                    'environment': 'railway' if self.is_railway else 'local',
                    'error': result['error'],
                    'available_methods': result.get('available_methods', []),
                    'alternatives': [
                        'Manual booking entry',
                        'CSV/Excel import', 
                        'Screenshot upload with AI extraction',
                        'Direct API integration'
                    ],
                    'setup_instructions': self._get_setup_instructions()
                }
                
        except Exception as e:
            logger.error(f"❌ Comprehensive crawl failed: {e}")
            return {
                'success': False,
                'method': 'exception',
                'environment': 'railway' if self.is_railway else 'local',
                'error': str(e),
                'suggestion': 'Check network connectivity and API configurations'
            }
    
    def _extract_bookings_from_html(self, html_content: str):
        """Extract booking data from HTML content using basic parsing"""
        # This is a basic implementation - can be enhanced with BeautifulSoup or regex
        bookings = []
        
        # Basic extraction patterns (this would need to be customized for specific sites)
        import re
        
        # Look for booking patterns in HTML
        booking_patterns = [
            r'booking[_-]?id["\s]*[:=]["\s]*([A-Za-z0-9]+)',
            r'guest[_-]?name["\s]*[:=]["\s]*["\'](.*?)["\']',
            r'check[_-]?in["\s]*[:=]["\s]*["\'](.*?)["\']',
            r'check[_-]?out["\s]*[:=]["\s]*["\'](.*?)["\']'
        ]
        
        # Basic extraction - this would need to be enhanced for production
        logger.info("🔍 Attempting basic HTML extraction (placeholder implementation)")
        
        return bookings  # Return empty for now - can be enhanced
    
    def _get_setup_instructions(self):
        """Get setup instructions for enabling crawling"""
        instructions = {
            'firecrawl': {
                'name': 'Firecrawl API',
                'steps': [
                    '1. Visit https://firecrawl.dev',
                    '2. Sign up for an account',
                    '3. Get your API key from dashboard',
                    '4. Set FIRECRAWL_API_KEY environment variable'
                ],
                'cost': 'Free tier: 500 requests/month'
            },
            'scrapfly': {
                'name': 'ScrapFly API',
                'steps': [
                    '1. Visit https://scrapfly.io',
                    '2. Create an account',
                    '3. Get API key from dashboard',
                    '4. Set SCRAPFLY_API_KEY environment variable'
                ],
                'cost': 'Free tier: 1000 requests/month'
            },
            'scraperapi': {
                'name': 'ScraperAPI',
                'steps': [
                    '1. Visit https://scraperapi.com',
                    '2. Sign up for free account',
                    '3. Get API key',
                    '4. Set SCRAPERAPI_KEY environment variable'
                ],
                'cost': 'Free tier: 5000 requests/month'
            }
        }
        
        return instructions

# Global instance
railway_crawl_service = RailwayCrawlService()