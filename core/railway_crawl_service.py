"""
Railway-Compatible Crawling Service
Provides fallback functionality for web crawling on serverless/cloud platforms
"""

import os
import requests
import json
from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger(__name__)

class RailwayCrawlService:
    """Railway-compatible crawling service with API-based alternatives"""
    
    def __init__(self):
        self.is_railway = self.detect_railway_environment()
        self.firecrawl_api_key = os.getenv('FIRECRAWL_API_KEY')
        
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
    
    def is_crawling_available(self):
        """Check if web crawling is available in current environment"""
        if self.is_railway:
            # On Railway, only API-based crawling is available
            return bool(self.firecrawl_api_key)
        else:
            # Local environment - check for Selenium
            try:
                import selenium
                return True
            except ImportError:
                return bool(self.firecrawl_api_key)
    
    def get_crawling_methods(self):
        """Get available crawling methods for current environment"""
        methods = []
        
        if self.is_railway:
            if self.firecrawl_api_key:
                methods.append({
                    'id': 'firecrawl',
                    'name': 'Firecrawl API',
                    'description': 'Cloud-based web scraping service',
                    'supported': True
                })
            methods.append({
                'id': 'selenium',
                'name': 'Selenium Browser Automation',
                'description': 'Not available on cloud platforms',
                'supported': False,
                'reason': 'Requires Chrome browser and display server'
            })
        else:
            # Local environment
            try:
                import selenium
                methods.append({
                    'id': 'selenium',
                    'name': 'Selenium Browser Automation', 
                    'description': 'Full browser automation with saved profiles',
                    'supported': True
                })
            except ImportError:
                methods.append({
                    'id': 'selenium',
                    'name': 'Selenium Browser Automation',
                    'description': 'Install selenium and Chrome browser',
                    'supported': False,
                    'reason': 'Selenium not installed'
                })
                
            if self.firecrawl_api_key:
                methods.append({
                    'id': 'firecrawl',
                    'name': 'Firecrawl API',
                    'description': 'Cloud-based web scraping service',
                    'supported': True
                })
        
        return methods
    
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
    
    def crawl_admin_bookings_api(self, target_url: str, profile_name: str = None):
        """API-based alternative to Selenium crawling"""
        try:
            logger.info(f"Starting API-based crawl for: {target_url}")
            
            # Use Firecrawl for cloud environments
            if self.is_railway and self.firecrawl_api_key:
                result = self.crawl_with_firecrawl(target_url)
                
                return {
                    'success': True,
                    'method': 'firecrawl',
                    'data': result.get('llm_extraction', {}),
                    'screenshot': result.get('screenshot'),
                    'message': 'Booking data extracted via Firecrawl API'
                }
            else:
                # Fallback: Return helpful message
                return {
                    'success': False,
                    'method': 'unavailable',
                    'error': 'Web crawling not available in current environment',
                    'suggestion': 'Use local development environment for browser-based crawling',
                    'alternatives': [
                        'Manual booking entry',
                        'CSV/Excel import',
                        'API integration',
                        'Screenshot upload with AI extraction'
                    ]
                }
                
        except Exception as e:
            logger.error(f"API crawling failed: {e}")
            return {
                'success': False,
                'method': 'api',
                'error': str(e),
                'suggestion': 'Try alternative booking input methods'
            }

# Global instance
railway_crawl_service = RailwayCrawlService()