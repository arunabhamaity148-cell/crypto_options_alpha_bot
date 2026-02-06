"""
Data Aggregator - Cached for Railway Hobby
Reduce API calls, faster execution
"""

import asyncio
import logging
from typing import Dict
from dataclasses import dataclass
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

@dataclass
class AssetData:
    asset: str
    spot_price: float
    perp_price: float
    funding_rate: float
    open_interest: float
    volume_24h: float
    orderbook: Dict
    timestamp: datetime

class DataAggregator:
    def __init__(self, stealth_request):
        self.stealth = stealth_request
        self._cache = {}
        self._cache_time = {}
        
    def _get_cached(self, key: str, ttl: int = 60):
        """Get cached data if valid"""
        if key in self._cache and key in self._cache_time:
            if datetime.now() - self._cache_time[key] < timedelta(seconds=ttl):
                return self._cache[key]
        return None
    
    def _set_cached(self, key: str, value):
        """Cache data with timestamp"""
        self._cache[key] = value
        self._cache_time[key] = datetime.now()
        
    async def get_all_assets_data(self, assets_config: Dict) -> Dict[str, AssetData]:
        tasks = []
        for asset, config in assets_config.items():
            if config.get('enable', True):
                tasks.append(self._fetch_asset_data(asset, config))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        data = {}
        for result in results:
            if isinstance(result, AssetData):
                data[result.asset] = result
            elif isinstance(result, Exception):
                logger.error(f"Fetch error: {result}")
        
        return data
    
    async def _fetch_asset_data(self, asset: str, config: Dict) -> AssetData:
        symbol = config['symbol']
        
        # Parallel fetch with caching
        spot, perp, funding, oi, volume, ob = await asyncio.gather(
            self.get_spot_price(symbol),
            self.get_perp_price(symbol),
            self.get_funding_rate(symbol),
            self.get_open_interest(symbol),
            self.get_24h_volume(symbol),
            self.get_orderbook(symbol),
            return_exceptions=True
        )
        
        # Handle exceptions
        spot = spot if not isinstance(spot, Exception) else 0
        perp = perp if not isinstance(perp, Exception) else 0
        funding = funding if not isinstance(funding, Exception) else 0
        oi = oi if not isinstance(oi, Exception) else 0
        volume = volume if not isinstance(volume, Exception) else 0
        ob = ob if not isinstance(ob, Exception) else {}
        
        return AssetData(
            asset=asset,
            spot_price=spot,
            perp_price=perp,
            funding_rate=funding,
            open_interest=oi,
            volume_24h=volume,
            orderbook=ob,
            timestamp=datetime.now()
        )
    
    async def get_spot_price(self, symbol: str) -> float:
        """Public method - cached"""
        cache_key = f"spot_{symbol}"
        cached = self._get_cached(cache_key, 2)  # 2s TTL
        if cached:
            return cached
            
        data = await self.stealth.get(
            'https://api.binance.com/api/v3/ticker/price',
            {'symbol': symbol}
        )
        price = float(data.get('price', 0))
        self._set_cached(cache_key, price)
        return price
    
    async def get_perp_price(self, symbol: str) -> float:
        cache_key = f"perp_{symbol}"
        cached = self._get_cached(cache_key, 2)
        if cached:
            return cached
            
        data = await self.stealth.get(
            'https://fapi.binance.com/fapi/v1/ticker/price',
            {'symbol': symbol}
        )
        price = float(data.get('price', 0))
        self._set_cached(cache_key, price)
        return price
    
    async def get_funding_rate(self, symbol: str) -> float:
        """Cached for 5 minutes"""
        cache_key = f"funding_{symbol}"
        cached = self._get_cached(cache_key, 300)
        if cached:
            return cached
            
        data = await self.stealth.get(
            'https://fapi.binance.com/fapi/v1/fundingRate',
            {'symbol': symbol, 'limit': 1}
        )
        rate = float(data[0].get('fundingRate', 0)) if data and len(data) > 0 else 0
        self._set_cached(cache_key, rate)
        return rate
    
    async def get_open_interest(self, symbol: str) -> float:
        """Cached for 1 minute"""
        cache_key = f"oi_{symbol}"
        cached = self._get_cached(cache_key, 60)
        if cached:
            return cached
            
        data = await self.stealth.get(
            'https://fapi.binance.com/fapi/v1/openInterest',
            {'symbol': symbol}
        )
        oi = float(data.get('openInterest', 0))
        self._set_cached(cache_key, oi)
        return oi
    
    async def get_24h_volume(self, symbol: str) -> float:
        cache_key = f"vol_{symbol}"
        cached = self._get_cached(cache_key, 60)
        if cached:
            return cached
            
        data = await self.stealth.get(
            'https://api.binance.com/api/v3/ticker/24hr',
            {'symbol': symbol}
        )
        vol = float(data.get('volume', 0)) * float(data.get('weightedAvgPrice', 0))
        self._set_cached(cache_key, vol)
        return vol
    
    async def get_orderbook(self, symbol: str, limit: int = 100) -> Dict:
        data = await self.stealth.get(
            'https://api.binance.com/api/v3/depth',
            {'symbol': symbol, 'limit': limit}
        )
        
        if not data or 'bids' not in data:
            return {}
        
        bids = [[float(b[0]), float(b[1])] for b in data.get('bids', [])]
        asks = [[float(a[0]), float(a[1])] for a in data.get('asks', [])]
        
        if not bids or not asks:
            return {}
        
        best_bid = bids[0][0]
        best_ask = asks[0][0]
        mid_price = (best_bid + best_ask) / 2
        
        # Calculate metrics
        bid_pressure = sum(b[1] * b[0] for b in bids[:10])
        ask_pressure = sum(a[1] * a[0] for a in asks[:10])
        total_pressure = bid_pressure + ask_pressure
        
        # Walls detection
        avg_bid = sum(b[1] for b in bids[:20]) / 20
        avg_ask = sum(a[1] for a in asks[:20]) / 20
        
        bid_walls = [(b[0], b[1]) for b in bids[:20] if b[1] > avg_bid * 5]
        ask_walls = [(a[0], a[1]) for a in asks[:20] if a[1] > avg_ask * 5]
        
        return {
            'bids': bids[:20],
            'asks': asks[:20],
            'mid_price': mid_price,
            'spread': best_ask - best_bid,
            'spread_pct': (best_ask - best_bid) / mid_price * 100,
            'bid_pressure': bid_pressure,
            'ask_pressure': ask_pressure,
            'ofi_ratio': (bid_pressure - ask_pressure) / total_pressure if total_pressure > 0 else 0,
            'bid_walls': bid_walls[:3],
            'ask_walls': ask_walls[:3],
        }
