"""
Optimized Railway Crawling Service - 100% Performance Implementation
Addresses all critical performance bottlenecks for production-ready crawling
"""

import os
import time
import json
import asyncio
import aiohttp
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import logging
from dataclasses import dataclass
from functools import wraps
import random

logger = logging.getLogger(__name__)

@dataclass
class CrawlMetrics:
    """Performance metrics for crawl operations"""
    url: str
    method: str
    start_time: float
    end_time: float
    success: bool
    data_size: int
    cost: float
    error: str = None
    
    @property
    def duration(self):
        return self.end_time - self.start_time
    
    @property
    def throughput(self):
        return self.data_size / self.duration if self.duration > 0 else 0

class RateLimitManager:
    """Intelligent rate limiting and quota management"""
    
    def __init__(self):
        self.rate_limits = {
            'firecrawl': {'requests_per_minute': 10, 'daily_quota': 500, 'cost_per_request': 0.003},
            'scrapfly': {'requests_per_minute': 20, 'daily_quota': 1000, 'cost_per_request': 0.001},
            'scraperapi': {'requests_per_minute': 100, 'daily_quota': 5000, 'cost_per_request': 0.0001},
            'direct_http': {'requests_per_minute': 1000, 'daily_quota': float('inf'), 'cost_per_request': 0}
        }
        self.usage_tracker = {}
        self.request_times = {}
        self.daily_cost = 0
        self.cost_budget = float(os.getenv('CRAWL_BUDGET_USD', '50'))  # $50 default
    
    def can_make_request(self, service: str) -> tuple[bool, str]:
        """Check if request is within rate limits and budget"""
        current_time = time.time()
        service_limits = self.rate_limits[service]
        
        # Check daily quota
        today = datetime.now().strftime('%Y-%m-%d')
        daily_usage = self.usage_tracker.get(f'{service}_{today}', 0)
        if daily_usage >= service_limits['daily_quota']:
            return False, f"Daily quota exceeded for {service}"
        
        # Check rate limits
        minute_ago = current_time - 60
        recent_requests = [t for t in self.request_times.get(service, []) if t > minute_ago]
        if len(recent_requests) >= service_limits['requests_per_minute']:
            return False, f"Rate limit exceeded for {service}"
        
        # Check budget
        estimated_cost = self.daily_cost + service_limits['cost_per_request']
        if estimated_cost > self.cost_budget:
            return False, f"Budget limit would be exceeded (${estimated_cost:.4f} > ${self.cost_budget})"
        
        return True, "OK"
    
    def record_request(self, service: str, success: bool):
        """Record a request for rate limiting"""
        current_time = time.time()
        today = datetime.now().strftime('%Y-%m-%d')
        
        # Track usage
        usage_key = f'{service}_{today}'
        self.usage_tracker[usage_key] = self.usage_tracker.get(usage_key, 0) + 1
        
        # Track request timing
        if service not in self.request_times:
            self.request_times[service] = []
        self.request_times[service].append(current_time)
        
        # Track cost
        cost = self.rate_limits[service]['cost_per_request']
        self.daily_cost += cost
        
        # Cleanup old request times (keep last hour)
        hour_ago = current_time - 3600
        self.request_times[service] = [t for t in self.request_times[service] if t > hour_ago]

class CacheManager:
    """Multi-level caching with TTL management"""
    
    def __init__(self):
        self.memory_cache = {}
        self.cache_ttl = {
            'booking_data': 3600,    # 1 hour for booking data
            'screenshots': 7200,     # 2 hours for screenshots
            'html_content': 1800     # 30 minutes for HTML
        }
        # Try to initialize Redis, fallback to memory-only
        self.redis_client = None
        try:
            import redis
            self.redis_client = redis.Redis(
                host=os.getenv('REDIS_HOST', 'localhost'),
                port=int(os.getenv('REDIS_PORT', '6379')),
                db=0,
                decode_responses=True
            )
            self.redis_client.ping()  # Test connection
            logger.info("Redis cache connected")
        except Exception as e:
            logger.warning(f"Redis not available, using memory cache only: {e}")
    
    def get_cache_key(self, url: str, options: dict) -> str:
        """Generate cache key from URL and options"""
        cache_data = f"{url}:{json.dumps(options, sort_keys=True)}"
        return hashlib.md5(cache_data.encode()).hexdigest()
    
    async def get_cached(self, url: str, options: dict, cache_type: str = 'booking_data') -> Optional[dict]:
        """Get cached data if available"""
        cache_key = self.get_cache_key(url, options)
        
        # Check memory cache first (fastest)
        if cache_key in self.memory_cache:
            cache_entry = self.memory_cache[cache_key]
            if datetime.now() < cache_entry['expires']:
                logger.info(f"Cache HIT (memory): {url[:50]}...")
                return cache_entry['data']
            else:
                # Expired, remove from memory cache
                del self.memory_cache[cache_key]
        
        # Check Redis cache (if available)
        if self.redis_client:
            try:
                cached_data = self.redis_client.get(f"crawl:{cache_key}")
                if cached_data:
                    logger.info(f"Cache HIT (Redis): {url[:50]}...")
                    data = json.loads(cached_data)
                    
                    # Update memory cache
                    self.memory_cache[cache_key] = {
                        'data': data,
                        'expires': datetime.now() + timedelta(seconds=300)  # 5 min in memory
                    }
                    return data
            except Exception as e:
                logger.warning(f"Redis error: {e}")
        
        logger.info(f"Cache MISS: {url[:50]}...")
        return None
    
    async def set_cached(self, url: str, options: dict, data: dict, cache_type: str = 'booking_data'):
        """Store data in cache"""
        cache_key = self.get_cache_key(url, options)
        ttl = self.cache_ttl.get(cache_type, 3600)
        
        # Store in memory cache
        self.memory_cache[cache_key] = {
            'data': data,
            'expires': datetime.now() + timedelta(seconds=300)  # 5 min in memory
        }
        
        # Store in Redis cache (if available)
        if self.redis_client:
            try:
                self.redis_client.setex(f"crawl:{cache_key}", ttl, json.dumps(data))
            except Exception as e:
                logger.warning(f"Redis error: {e}")

class CircuitBreaker:
    """Circuit breaker pattern for service reliability"""
    
    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 300):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_counts = {}
        self.circuit_states = {}  # 'closed', 'open', 'half-open'
        self.circuit_open_times = {}
    
    def can_call_service(self, service: str) -> tuple[bool, str]:
        """Check if service can be called based on circuit state"""
        current_time = time.time()
        
        if self.circuit_states.get(service) == 'open':
            # Check if recovery timeout has passed
            open_time = self.circuit_open_times.get(service, 0)
            if current_time - open_time > self.recovery_timeout:
                self.circuit_states[service] = 'half-open'
                logger.info(f"Circuit breaker for {service} moved to half-open")
                return True, "half-open"
            else:
                remaining = self.recovery_timeout - (current_time - open_time)
                return False, f"Circuit breaker open, retry in {remaining:.0f}s"
        
        return True, "closed"
    
    def record_success(self, service: str):
        """Record successful operation"""
        self.failure_counts[service] = 0
        if self.circuit_states.get(service) == 'half-open':
            self.circuit_states[service] = 'closed'
            logger.info(f"Circuit breaker for {service} closed (recovered)")
    
    def record_failure(self, service: str):
        """Record failed operation"""
        self.failure_counts[service] = self.failure_counts.get(service, 0) + 1
        
        if self.failure_counts[service] >= self.failure_threshold:
            self.circuit_states[service] = 'open'
            self.circuit_open_times[service] = time.time()
            logger.warning(f"Circuit breaker for {service} opened after {self.failure_counts[service]} failures")

class OptimizedRailwayCrawler:
    """100% Performance Railway Crawling Service"""
    
    def __init__(self):
        self.rate_limiter = RateLimitManager()
        self.cache_manager = CacheManager()
        self.circuit_breaker = CircuitBreaker()
        self.metrics: List[CrawlMetrics] = []
        
        # Service configurations
        self.services = {
            'firecrawl': {
                'api_key_env': 'FIRECRAWL_API_KEY',
                'url': 'https://api.firecrawl.dev/v1/scrape',
                'performance_score': 95,
                'features': ['javascript', 'screenshots', 'llm_extraction']
            },
            'scrapfly': {
                'api_key_env': 'SCRAPFLY_API_KEY',
                'url': 'https://api.scrapfly.io/scrape',
                'performance_score': 85,
                'features': ['javascript', 'screenshots', 'asp']
            },
            'scraperapi': {
                'api_key_env': 'SCRAPERAPI_KEY',
                'url': 'http://api.scraperapi.com',
                'performance_score': 75,
                'features': ['proxies', 'headers_rotation']
            },
            'direct_http': {
                'api_key_env': None,
                'url': None,
                'performance_score': 60,
                'features': ['basic_http']
            }
        }
        
        # Initialize session
        self.session = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session with connection pooling"""
        if not self.session or self.session.closed:
            connector = aiohttp.TCPConnector(
                limit=10,  # Total connection pool size
                limit_per_host=5,  # Max connections per host
                keepalive_timeout=30,
                enable_cleanup_closed=True
            )
            
            timeout = aiohttp.ClientTimeout(total=60, connect=10, sock_read=30)
            
            self.session = aiohttp.ClientSession(
                connector=connector,
                timeout=timeout
            )
        
        return self.session
    
    def select_optimal_service(self, requirements: dict = None) -> str:
        """Select best service based on requirements and cost"""
        if not requirements:
            requirements = {'min_performance': 70, 'features': []}
        
        candidates = []
        
        for service_name, config in self.services.items():
            # Check if service is available
            api_key_env = config.get('api_key_env')
            if api_key_env and not os.getenv(api_key_env):
                continue
            
            # Check circuit breaker
            can_call, reason = self.circuit_breaker.can_call_service(service_name)
            if not can_call:
                continue
            
            # Check rate limits
            can_request, limit_reason = self.rate_limiter.can_make_request(service_name)
            if not can_request:
                continue
            
            # Check if meets requirements
            performance = config['performance_score']
            if performance < requirements['min_performance']:
                continue
            
            # Check feature requirements
            required_features = requirements.get('features', [])
            service_features = config.get('features', [])
            if not all(feature in service_features for feature in required_features):
                continue
            
            # Calculate cost efficiency
            cost = self.rate_limiter.rate_limits[service_name]['cost_per_request']
            cost_efficiency = performance / (cost * 1000 + 1)  # +1 to avoid division by zero
            
            candidates.append({
                'service': service_name,
                'performance': performance,
                'cost': cost,
                'cost_efficiency': cost_efficiency
            })
        
        if not candidates:
            raise Exception("No available crawling services meet requirements")
        
        # Select highest cost efficiency
        best = max(candidates, key=lambda x: x['cost_efficiency'])
        logger.info(f"Selected {best['service']} (performance: {best['performance']}, cost: ${best['cost']:.4f})")
        return best['service']
    
    async def crawl_with_retry(self, url: str, options: dict = None, max_retries: int = 3) -> dict:
        """Crawl with exponential backoff retry"""
        last_error = None
        
        for attempt in range(max_retries):
            try:
                return await self._crawl_single(url, options)
            except Exception as e:
                last_error = e
                
                if attempt < max_retries - 1:
                    wait_time = (2 ** attempt) + random.uniform(0, 1)
                    logger.warning(f"Attempt {attempt + 1} failed: {e}. Retrying in {wait_time:.1f}s...")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"All {max_retries} attempts failed for {url}")
        
        raise last_error
    
    async def _crawl_single(self, url: str, options: dict = None) -> dict:
        """Crawl single URL with full optimization"""
        if not options:
            options = {}
        
        # Check cache first
        cached_result = await self.cache_manager.get_cached(url, options)
        if cached_result:
            return cached_result
        
        # Select optimal service
        requirements = {
            'min_performance': 70,
            'features': options.get('required_features', [])
        }
        service = self.select_optimal_service(requirements)
        
        # Performance tracking
        start_time = time.time()
        success = False
        data_size = 0
        cost = self.rate_limiter.rate_limits[service]['cost_per_request']
        
        try:
            # Make the request
            if service == 'firecrawl':
                result = await self._crawl_with_firecrawl(url, options)
            elif service == 'scrapfly':
                result = await self._crawl_with_scrapfly(url, options)
            elif service == 'scraperapi':
                result = await self._crawl_with_scraperapi(url, options)
            else:  # direct_http
                result = await self._crawl_with_direct_http(url, options)
            
            success = True
            data_size = len(json.dumps(result))
            
            # Record success
            self.rate_limiter.record_request(service, True)
            self.circuit_breaker.record_success(service)
            
            # Cache the result
            await self.cache_manager.set_cached(url, options, result)
            
            return result
            
        except Exception as e:
            # Record failure
            self.rate_limiter.record_request(service, False)
            self.circuit_breaker.record_failure(service)
            raise
            
        finally:
            # Record metrics
            end_time = time.time()
            metric = CrawlMetrics(
                url=url,
                method=service,
                start_time=start_time,
                end_time=end_time,
                success=success,
                data_size=data_size,
                cost=cost,
                error=None if success else str(last_error) if 'last_error' in locals() else None
            )
            self.metrics.append(metric)
            
            # Log performance
            duration = metric.duration
            logger.info(f"PERF: {service} - {duration:.2f}s, {data_size} bytes, ${cost:.4f}")
            
            # Alert on slow operations
            if duration > 30:
                logger.warning(f"SLOW: {url} took {duration:.2f}s with {service}")
    
    async def _crawl_with_firecrawl(self, url: str, options: dict) -> dict:
        """Optimized Firecrawl implementation"""
        api_key = os.getenv('FIRECRAWL_API_KEY')
        if not api_key:
            raise Exception("Firecrawl API key not configured")
        
        session = await self._get_session()
        
        payload = {
            'url': url,
            'pageOptions': {
                'screenshot': True,
                'fullPageScreenshot': True,
                'waitFor': 3000
            }
        }
        
        # Add Booking.com optimizations if detected
        if 'booking.com' in url.lower():
            payload['pageOptions']['waitFor'] = 5000
            payload['extractorOptions'] = {
                'mode': 'llm-extraction',
                'extractionPrompt': self._get_booking_com_prompt()
            }
        
        headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        }
        
        async with session.post(
            'https://api.firecrawl.dev/v1/scrape',
            headers=headers,
            json=payload
        ) as response:
            if response.status == 200:
                return await response.json()
            else:
                text = await response.text()
                raise Exception(f"Firecrawl API error: {response.status} - {text}")
    
    async def _crawl_with_scrapfly(self, url: str, options: dict) -> dict:
        """Optimized ScrapFly implementation"""
        api_key = os.getenv('SCRAPFLY_API_KEY')
        if not api_key:
            raise Exception("ScrapFly API key not configured")
        
        session = await self._get_session()
        
        params = {
            'key': api_key,
            'url': url,
            'render_js': True,
            'screenshots': True,
            'asp': True,
            'format': 'json'
        }
        
        async with session.get(
            'https://api.scrapfly.io/scrape',
            params=params
        ) as response:
            if response.status == 200:
                return await response.json()
            else:
                text = await response.text()
                raise Exception(f"ScrapFly API error: {response.status} - {text}")
    
    async def _crawl_with_scraperapi(self, url: str, options: dict) -> dict:
        """Optimized ScraperAPI implementation"""
        api_key = os.getenv('SCRAPERAPI_KEY')
        if not api_key:
            raise Exception("ScraperAPI key not configured")
        
        session = await self._get_session()
        
        params = {
            'api_key': api_key,
            'url': url,
            'render': True
        }
        
        async with session.get(
            'http://api.scraperapi.com',
            params=params
        ) as response:
            if response.status == 200:
                html = await response.text()
                return {'html': html, 'status': 'success'}
            else:
                text = await response.text()
                raise Exception(f"ScraperAPI error: {response.status} - {text}")
    
    async def _crawl_with_direct_http(self, url: str, options: dict) -> dict:
        """Optimized direct HTTP implementation"""
        session = await self._get_session()
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        
        async with session.get(url, headers=headers) as response:
            if response.status == 200:
                html = await response.text()
                return {'html': html, 'status': 'success'}
            else:
                raise Exception(f"HTTP error: {response.status}")
    
    def _get_booking_com_prompt(self) -> str:
        """Optimized Booking.com extraction prompt"""
        return """
        Extract booking data from this Booking.com admin/partner page.
        Focus on these key elements:
        
        1. Booking Reference (usually BK + 8-10 digits)
        2. Guest Name (full name)
        3. Check-in Date (YYYY-MM-DD format)
        4. Check-out Date (YYYY-MM-DD format)
        5. Total Amount (booking value)
        6. Commission Amount (partner commission)
        7. Booking Status (confirmed/cancelled/no-show)
        
        Return as JSON with fields: booking_id, guest_name, checkin_date, 
        checkout_date, total_amount, commission, status
        """
    
    def get_performance_report(self) -> dict:
        """Generate comprehensive performance report"""
        if not self.metrics:
            return {"error": "No metrics available"}
        
        successful_ops = [m for m in self.metrics if m.success]
        failed_ops = [m for m in self.metrics if not m.success]
        
        # Calculate costs
        total_cost = sum(m.cost for m in self.metrics)
        cost_per_success = sum(m.cost for m in successful_ops) / len(successful_ops) if successful_ops else 0
        
        # Performance by method
        method_stats = {}
        for metric in self.metrics:
            if metric.method not in method_stats:
                method_stats[metric.method] = {'count': 0, 'success': 0, 'avg_duration': 0, 'total_cost': 0}
            
            stats = method_stats[metric.method]
            stats['count'] += 1
            if metric.success:
                stats['success'] += 1
            stats['avg_duration'] = (stats['avg_duration'] * (stats['count'] - 1) + metric.duration) / stats['count']
            stats['total_cost'] += metric.cost
        
        return {
            'summary': {
                'total_operations': len(self.metrics),
                'success_rate': len(successful_ops) / len(self.metrics) * 100,
                'average_duration': sum(m.duration for m in successful_ops) / len(successful_ops) if successful_ops else 0,
                'total_cost_usd': total_cost,
                'cost_per_success_usd': cost_per_success,
                'total_data_processed_bytes': sum(m.data_size for m in successful_ops),
                'average_throughput_bps': sum(m.throughput for m in successful_ops) / len(successful_ops) if successful_ops else 0
            },
            'method_performance': method_stats,
            'slowest_operations': sorted(self.metrics, key=lambda x: x.duration, reverse=True)[:5],
            'cost_breakdown': {method: stats['total_cost'] for method, stats in method_stats.items()},
            'cache_stats': {
                'memory_cache_size': len(self.cache_manager.memory_cache),
                'cache_hit_rate': 'Not tracked yet'  # Would need cache hit counters
            }
        }
    
    async def crawl_urls_parallel(self, urls: List[str], options: dict = None, max_concurrent: int = 5) -> dict:
        """Crawl multiple URLs in parallel with semaphore control"""
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def crawl_with_semaphore(url):
            async with semaphore:
                return await self.crawl_with_retry(url, options)
        
        # Create tasks
        tasks = [crawl_with_semaphore(url) for url in urls]
        
        # Execute in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Separate successes from failures
        successful_results = []
        errors = []
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                errors.append({'url': urls[i], 'error': str(result)})
            else:
                successful_results.append({'url': urls[i], 'data': result})
        
        return {
            'successful': successful_results,
            'errors': errors,
            'success_rate': len(successful_results) / len(urls) * 100,
            'total_urls': len(urls),
            'performance_report': self.get_performance_report()
        }
    
    async def close(self):
        """Clean up resources"""
        if self.session and not self.session.closed:
            await self.session.close()

# Global optimized instance
optimized_crawler = OptimizedRailwayCrawler()