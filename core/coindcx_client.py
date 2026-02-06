"""
CoinDCX API Client for Real Options Data
"""

import asyncio
import logging
import hmac
import hashlib
import json
import time
from typing import Dict, List, Optional
from datetime import datetime

import aiohttp

logger = logging.getLogger(__name__)

class CoinDCXClient:
    BASE_URL = "https://api.coindcx.com"
    BASE_URL_V2 = "https://api.coindcx.com/exchange/v1"
    
    def __init__(self, api_key: str, api_secret: str):
        self.api_key = api_key
        self.api_secret = api_secret
        self.session = None
        
    async def _init_session(self):
        if self.session is None:
            self.session = aiohttp.ClientSession()
    
    def _generate_signature(self, body: str = "") -> tuple:
        """Generate HMAC signature"""
        if not self.api_secret:
            return "", 0
        
        timestamp = int(time.time() * 1000)
        signature_data = f"{timestamp}{json.dumps(body) if body else ''}"
        
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            signature_data.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return signature, timestamp
    
    async def get_options_instruments(self, underlying: str = "BTC") -> List[Dict]:
        """Get all options instruments"""
        await self._init_session()
        
        try:
            url = f"{self.BASE_URL_V2}/derivatives/options/instruments"
            
            async with self.session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    options = [
                        opt for opt in data 
                        if opt.get('underlying') == underlying
                    ]
                    
                    logger.info(f"CoinDCX: {len(options)} options for {underlying}")
                    return options
                else:
                    logger.error(f"CoinDCX API error: {response.status}")
                    return []
                    
        except Exception as e:
            logger.error(f"CoinDCX fetch error: {e}")
            return []
    
    async def get_options_ticker(self, symbol: str) -> Optional[Dict]:
        """Get real-time options ticker with Greeks"""
        await self._init_session()
        
        try:
            url = f"{self.BASE_URL_V2}/derivatives/options/ticker"
            params = {'symbol': symbol}
            
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    return {
                        'symbol': data.get('symbol'),
                        'mark_price': float(data.get('mark_price', 0)),
                        'spot_price': float(data.get('spot_price', 0)),
                        'iv': float(data.get('iv', 0)),
                        'delta': float(data.get('delta', 0)),
                        'gamma': float(data.get('gamma', 0)),
                        'theta': float(data.get('theta', 0)),
                        'vega': float(data.get('vega', 0)),
                        'oi': float(data.get('oi', 0)),
                        'volume_24h': float(data.get('volume', 0)),
                        'bid': float(data.get('bid', 0)),
                        'ask': float(data.get('ask', 0)),
                        'strike': float(data.get('strike_price', 0)),
                        'expiry': data.get('expiry_date'),
                    }
                else:
                    logger.error(f"Ticker error: {response.status}")
                    return None
                    
        except Exception as e:
            logger.error(f"Ticker fetch error: {e}")
            return None
    
    async def find_best_option(self, underlying: str, strike: float, 
                              option_type: str, expiry_days: int = 2) -> Optional[Dict]:
        """Find best option matching criteria"""
        
        instruments = await self.get_options_instruments(underlying)
        
        if not instruments:
            return None
        
        opt_type = "call" if option_type == "CE" else "put"
        
        # Find closest strike
        matching = []
        for opt in instruments:
            if opt.get('option_type') != opt_type:
                continue
            
            opt_strike = float(opt.get('strike_price', 0))
            if abs(opt_strike - strike) < (100 if underlying == 'BTC' else 10):
                matching.append(opt)
        
        if not matching:
            return None
        
        # Get ticker for first match
        best = matching[0]
        symbol = best.get('symbol')
        
        ticker = await self.get_options_ticker(symbol)
        
        if ticker:
            ticker['symbol'] = symbol
            ticker['instrument'] = best
        
        return ticker
    
    async def close(self):
        if self.session:
            await self.session.close()

# Global instance
coindcx_client = None

def init_coindcx_client(api_key: str, api_secret: str):
    global coindcx_client
    coindcx_client = CoinDCXClient(api_key, api_secret)
    return coindcx_client
