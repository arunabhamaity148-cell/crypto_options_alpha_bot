"""
Anti-Ban Request Handler
Random delays, rotation, human-like behavior
"""

import random
import time
import asyncio
import aiohttp
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)

class StealthRequest:
    """Prevents IP ban with intelligent request management"""
    
    USER_AGENTS = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101',
    ]
    
    def __init__(self, config: Dict):
        self.config = config
        self.last_request_time = 0
        self.request_count = 0
        self.min_delay = config.get('min_request_delay', 1.0)
        self.max_delay = config.get('max_request_delay', 5.0)
        self.max_per_minute = config.get('max_requests_per_minute', 15)
        
    async def _apply_jitter(self):
        """Random delay to avoid pattern detection"""
        if not self.config.get('enable_jitter', True):
            return
            
        # Calculate time since last request
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        
        # Base delay + random jitter
        base_delay = random.uniform(self.min_delay, self.max_delay)
        
        # Add exponential backoff if too many requests
        if self.request_count > self.max_per_minute:
            base_delay *= 2
            
        # Ensure minimum gap
        if time_since_last < base_delay:
            await asyncio.sleep(base_delay - time_since_last)
            
        self.last_request_time = time.time()
        self.request_count += 1
        
        # Reset counter every minute
        if self.request_count >= self.max_per_minute:
            await asyncio.sleep(60)
            self.request_count = 0
    
    def _get_headers(self) -> Dict:
        """Rotate headers to appear as different clients"""
        return {
            'User-Agent': random.choice(self.USER_AGENTS),
            'Accept': 'application/json',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Cache-Control': 'no-cache',
            'X-Requested-With': 'XMLHttpRequest',
        }
    
    async def get(self, url: str, params: Optional[Dict] = None) -> Dict:
        """Stealth GET request"""
        await self._apply_jitter()
        
        headers = self._get_headers()
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, params=params, timeout=30) as response:
                    if response.status == 429:  # Rate limited
                        logger.warning("Rate limited, backing off...")
                        await asyncio.sleep(60)
                        return await self.get(url, params)
                    response.raise_for_status()
                    return await response.json()
        except Exception as e:
            logger.error(f"Request failed: {e}")
            await asyncio.sleep(5)
            return {}
    
    async def post(self, url: str, data: Dict) -> Dict:
        """Stealth POST request"""
        await self._apply_jitter()
        
        headers = self._get_headers()
        headers['Content-Type'] = 'application/json'
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=data, timeout=30) as response:
                    response.raise_for_status()
                    return await response.json()
        except Exception as e:
            logger.error(f"POST request failed: {e}")
            return {}
