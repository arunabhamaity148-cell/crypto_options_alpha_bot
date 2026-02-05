"""
Multi-Exchange Data Aggregation for BTC, ETH, SOL
"""

import asyncio
import logging
from typing import Dict, List
from dataclasses import dataclass
from datetime import datetime

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
    """Aggregates data from Binance for all assets"""
    
    def __init__(self, stealth_request):
        self.stealth = stealth_request
        
    async def get_all_assets_data(self, assets_config: Dict) -> Dict[str, AssetData]:
        """Fetch data for all assets concurrently"""
        
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
                logger.error(f"Asset data fetch error: {result}")
        
        return data
    
    async def _fetch_asset_data(self, asset: str, config: Dict) -> AssetData:
        """Fetch comprehensive data for single asset"""
        
        symbol = config['symbol']
        
        # Fetch all components concurrently
        tasks = [
            self._get_spot_price(symbol),
            self._get_perp_price(symbol),
            self._get_funding_rate(symbol),
            self._get_open_interest(symbol),
            self._get_24h_volume(symbol),
            self._get_orderbook(symbol),
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Extract results (handle exceptions)
        spot = results[0] if not isinstance(results[0], Exception) else 0
        perp = results[1] if not isinstance(results[1], Exception) else 0
        funding = results[2] if not isinstance(results[2], Exception) else 0
        oi = results[3] if not isinstance(results[3], Exception) else 0
        volume = results[4] if not isinstance(results[4], Exception) else 0
        ob = results[5] if not isinstance(results[5], Exception) else {}
        
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
    
    async def _get_spot_price(self, symbol: str) -> float:
        """Get spot price"""
        data = await self.stealth.get(
            'https://api.binance.com/api/v3/ticker/price',
            {'symbol': symbol}
        )
        return float(data.get('price', 0))
    
    async def _get_perp_price(self, symbol: str) -> float:
        """Get perpetual price"""
        data = await self.stealth.get(
            'https://fapi.binance.com/fapi/v1/ticker/price',
            {'symbol': symbol}
        )
        return float(data.get('price', 0))
    
    async def _get_funding_rate(self, symbol: str) -> float:
        """Get funding rate"""
        data = await self.stealth.get(
            'https://fapi.binance.com/fapi/v1/fundingRate',
            {'symbol': symbol, 'limit': 1}
        )
        if data and len(data) > 0:
            return float(data[0].get('fundingRate', 0))
        return 0
    
    async def _get_open_interest(self, symbol: str) -> float:
        """Get open interest"""
        data = await self.stealth.get(
            'https://fapi.binance.com/fapi/v1/openInterest',
            {'symbol': symbol}
        )
        return float(data.get('openInterest', 0))
    
    async def _get_24h_volume(self, symbol: str) -> float:
        """Get 24h volume"""
        data = await self.stealth.get(
            'https://api.binance.com/api/v3/ticker/24hr',
            {'symbol': symbol}
        )
        return float(data.get('volume', 0)) * float(data.get('weightedAvgPrice', 0))
    
    async def _get_orderbook(self, symbol: str, limit: int = 100) -> Dict:
        """Get orderbook with analysis"""
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
        
        # Calculate metrics
        best_bid = bids[0][0]
        best_ask = asks[0][0]
        mid_price = (best_bid + best_ask) / 2
        
        # Bid/ask pressure (top 10 levels)
        bid_pressure = sum(b[1] * b[0] for b in bids[:10])
        ask_pressure = sum(a[1] * a[0] for a in asks[:10])
        
        # Find walls (>5x average size)
        avg_bid = sum(b[1] for b in bids[:20]) / 20
        avg_ask = sum(a[1] for a in asks[:20]) / 20
        
        bid_walls = [(b[0], b[1]) for b in bids[:20] if b[1] > avg_bid * 5]
        ask_walls = [(a[0], a[1]) for a in asks[:20] if a[1] > avg_ask * 5]
        
        # Liquidity voids (gaps)
        bid_gaps = []
        for i in range(min(20, len(bids)-1)):
            gap = (bids[i][0] - bids[i+1][0]) / bids[i][0]
            if gap > 0.002:  # 0.2% gap
                bid_gaps.append((bids[i+1][0], gap))
        
        ask_gaps = []
        for i in range(min(20, len(asks)-1)):
            gap = (asks[i+1][0] - asks[i][0]) / asks[i][0]
            if gap > 0.002:
                ask_gaps.append((asks[i][0], gap))
        
        return {
            'bids': bids[:20],
            'asks': asks[:20],
            'mid_price': mid_price,
            'spread': best_ask - best_bid,
            'spread_pct': (best_ask - best_bid) / mid_price * 100,
            'bid_pressure': bid_pressure,
            'ask_pressure': ask_pressure,
            'ofi_ratio': (bid_pressure - ask_pressure) / (bid_pressure + ask_pressure) if (bid_pressure + ask_pressure) > 0 else 0,
            'bid_walls': bid_walls[:3],
            'ask_walls': ask_walls[:3],
            'liquidity_voids_below': bid_gaps[:2],
            'liquidity_voids_above': ask_gaps[:2],
        }
    
    async def get_recent_trades(self, symbol: str, limit: int = 100) -> List[Dict]:
        """Get recent trades for CVD calculation"""
        data = await self.stealth.get(
            'https://api.binance.com/api/v3/trades',
            {'symbol': symbol, 'limit': limit}
        )
        return data if isinstance(data, list) else []
