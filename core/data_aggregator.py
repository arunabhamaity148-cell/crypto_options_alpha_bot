"""
Multi-Exchange Data Aggregation
Combines Binance + CoinDCX for unique alpha
"""

import asyncio
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
import numpy as np

logger = logging.getLogger(__name__)

@dataclass
class MarketData:
    symbol: str
    spot_price: float
    perp_price: float
    timestamp: datetime
    orderbook: Dict
    recent_trades: List[Dict]
    funding_rate: float
    open_interest: float
    volume_24h: float

class DataAggregator:
    """Aggregates data from multiple sources for unique insights"""
    
    def __init__(self, binance_client, coindcx_client, stealth_request):
        self.binance = binance_client
        self.coindcx = coindcx_client
        self.stealth = stealth_request
        self.cache = {}
        self.cache_ttl = 5  # seconds
        
    async def get_spot_perp_basis(self, symbol: str = 'BTCUSDT') -> Dict:
        """
        Calculate basis between spot and perpetual
        Unique indicator - arbitrage opportunity detection
        """
        try:
            # Spot price
            spot = await self.stealth.get(
                'https://api.binance.com/api/v3/ticker/price',
                {'symbol': symbol}
            )
            spot_price = float(spot.get('price', 0))
            
            # Perp price
            perp = await self.stealth.get(
                'https://fapi.binance.com/fapi/v1/ticker/price',
                {'symbol': symbol}
            )
            perp_price = float(perp.get('price', 0))
            
            # Funding rate
            funding = await self.stealth.get(
                'https://fapi.binance.com/fapi/v1/fundingRate',
                {'symbol': symbol, 'limit': 1}
            )
            funding_rate = float(funding[0].get('fundingRate', 0)) if funding else 0
            
            # Calculate basis
            basis = (perp_price - spot_price) / spot_price
            annualized_basis = basis * 365 * 3  # 8-hour funding periods
            
            return {
                'spot_price': spot_price,
                'perp_price': perp_price,
                'basis': basis,
                'basis_bps': basis * 10000,
                'annualized_basis': annualized_basis,
                'funding_rate': funding_rate,
                'funding_annualized': funding_rate * 365 * 3,
                'timestamp': datetime.now(),
                'signal': 'long_spot_short_perp' if basis < -0.001 else \
                         'short_spot_long_perp' if basis > 0.003 else 'neutral'
            }
            
        except Exception as e:
            logger.error(f"Basis calculation error: {e}")
            return {}
    
    async def get_order_flow_imbalance(self, symbol: str = 'BTCUSDT', depth: int = 100) -> Dict:
        """
        Calculate Order Flow Imbalance (OFI)
        Unique microstructure indicator
        """
        try:
            # Get orderbook
            ob = await self.stealth.get(
                'https://api.binance.com/api/v3/depth',
                {'symbol': symbol, 'limit': depth}
            )
            
            bids = ob.get('bids', [])
            asks = ob.get('asks', [])
            
            if not bids or not asks:
                return {}
            
            # Calculate weighted bid/ask pressure
            bid_volume = sum([float(b[1]) * float(b[0]) for b in bids[:20]])
            ask_volume = sum([float(a[1]) * float(a[0]) for a in asks[:20]])
            
            bid_count = len([b for b in bids[:20] if float(b[1]) > 0.1])
            ask_count = len([a for a in asks[:20] if float(a[1]) > 0.1])
            
            # OFI calculation
            total_volume = bid_volume + ask_volume
            if total_volume == 0:
                return {}
                
            ofi_ratio = (bid_volume - ask_volume) / total_volume
            ofi_score = ofi_ratio * 10  # Scale to readable number
            
            # Large order detection (whale walls)
            bid_walls = [(float(b[0]), float(b[1])) for b in bids if float(b[1]) > 5]
            ask_walls = [(float(a[0]), float(a[1])) for a in asks if float(a[1]) > 5]
            
            return {
                'ofi_ratio': ofi_ratio,
                'ofi_score': round(ofi_score, 2),
                'bid_pressure': bid_volume,
                'ask_pressure': ask_volume,
                'bid_ask_ratio': bid_volume / ask_volume if ask_volume > 0 else 0,
                'bid_walls': bid_walls[:3],
                'ask_walls': ask_walls[:3],
                'spread': float(asks[0][0]) - float(bids[0][0]),
                'spread_pct': (float(asks[0][0]) - float(bids[0][0])) / float(bids[0][0]) * 100,
                'interpretation': 'strong_buy_pressure' if ofi_score > 2 else \
                                'strong_sell_pressure' if ofi_score < -2 else 'neutral'
            }
            
        except Exception as e:
            logger.error(f"OFI calculation error: {e}")
            return {}
    
    async def get_cumulative_volume_delta(self, symbol: str = 'BTCUSDT', limit: int = 100) -> Dict:
        """
        Calculate CVD - Cumulative Volume Delta
        Shows aggressive buying vs selling
        """
        try:
            # Get recent trades
            trades = await self.stealth.get(
                'https://api.binance.com/api/v3/trades',
                {'symbol': symbol, 'limit': limit}
            )
            
            if not trades:
                return {}
            
            # Get orderbook for mid price
            ob = await self.stealth.get(
                'https://api.binance.com/api/v3/ticker/bookTicker',
                {'symbol': symbol}
            )
            
            mid_price = (float(ob.get('bidPrice', 0)) + float(ob.get('askPrice', 0))) / 2
            
            buy_volume = 0
            sell_volume = 0
            
            for trade in trades:
                price = float(trade['price'])
                qty = float(trade['qty'])
                
                # Aggressive buyer: trade at or above ask
                # Aggressive seller: trade at or below bid
                if trade.get('isBuyerMaker', False):
                    sell_volume += qty * price
                else:
                    buy_volume += qty * price
            
            cvd = buy_volume - sell_volume
            total_volume = buy_volume + sell_volume
            
            return {
                'cvd': round(cvd, 2),
                'buy_volume': round(buy_volume, 2),
                'sell_volume': round(sell_volume, 2),
                'delta_ratio': (buy_volume - sell_volume) / total_volume if total_volume > 0 else 0,
                'buy_pressure_pct': (buy_volume / total_volume * 100) if total_volume > 0 else 50,
                'recent_trades_count': len(trades),
                'interpretation': 'aggressive_buying' if cvd > total_volume * 0.1 else \
                                'aggressive_selling' if cvd < -total_volume * 0.1 else 'balanced'
            }
            
        except Exception as e:
            logger.error(f"CVD calculation error: {e}")
            return {}
    
    async def get_liquidity_heatmap(self, symbol: str = 'BTCUSDT') -> Dict:
        """
        Identify liquidity clusters and voids
        Predicts where price will move
        """
        try:
            # Get deeper orderbook
            ob = await self.stealth.get(
                'https://api.binance.com/api/v3/depth',
                {'symbol': symbol, 'limit': 500}
            )
            
            bids = ob.get('bids', [])
            asks = ob.get('asks', [])
            
            if not bids or not asks:
                return {}
            
            current_price = (float(bids[0][0]) + float(asks[0][0])) / 2
            
            # Cluster liquidity by price levels
            bid_clusters = {}
            ask_clusters = {}
            
            cluster_size = current_price * 0.005  # 0.5% clusters
            
            for bid in bids:
                price = float(bid[0])
                qty = float(bid[1])
                cluster = round(price / cluster_size) * cluster_size
                bid_clusters[cluster] = bid_clusters.get(cluster, 0) + qty
            
            for ask in asks:
                price = float(ask[0])
                qty = float(ask[1])
                cluster = round(price / cluster_size) * cluster_size
                ask_clusters[cluster] = ask_clusters.get(cluster, 0) + qty
            
            # Find largest clusters (walls)
            top_bid_walls = sorted(bid_clusters.items(), key=lambda x: x[1], reverse=True)[:3]
            top_ask_walls = sorted(ask_clusters.items(), key=lambda x: x[1], reverse=True)[:3]
            
            # Find liquidity voids (gaps)
            bid_prices = [float(b[0]) for b in bids]
            ask_prices = [float(a[0]) for a in asks]
            
            bid_gaps = [bid_prices[i] - bid_prices[i+1] for i in range(min(50, len(bid_prices)-1))]
            ask_gaps = [ask_prices[i+1] - ask_prices[i] for i in range(min(50, len(ask_prices)-1))]
            
            max_bid_gap = max(bid_gaps) if bid_gaps else 0
            max_ask_gap = max(ask_gaps) if ask_gaps else 0
            
            # Predict liquidity hunt zones
            hunt_zone_below = current_price - max_bid_gap * 2 if max_bid_gap > current_price * 0.002 else None
            hunt_zone_above = current_price + max_ask_gap * 2 if max_ask_gap > current_price * 0.002 else None
            
            return {
                'current_price': current_price,
                'bid_walls': [(w[0], round(w[1], 4)) for w in top_bid_walls],
                'ask_walls': [(w[0], round(w[1], 4)) for w in top_ask_walls],
                'largest_bid_wall': top_bid_walls[0] if top_bid_walls else None,
                'largest_ask_wall': top_ask_walls[0] if top_ask_walls else None,
                'liquidity_void_below': hunt_zone_below,
                'liquidity_void_above': hunt_zone_above,
                'max_gap_below': max_bid_gap,
                'max_gap_above': max_ask_gap,
                'hunt_probability': 'high' if max_bid_gap > current_price * 0.003 or max_ask_gap > current_price * 0.003 else 'low'
            }
            
        except Exception as e:
            logger.error(f"Liquidity heatmap error: {e}")
            return {}
    
    async def get_comprehensive_snapshot(self, symbol: str = 'BTCUSDT') -> Dict:
        """Get all unique indicators in one call"""
        
        tasks = [
            self.get_spot_perp_basis(symbol),
            self.get_order_flow_imbalance(symbol),
            self.get_cumulative_volume_delta(symbol),
            self.get_liquidity_heatmap(symbol),
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        return {
            'basis_data': results[0] if not isinstance(results[0], Exception) else {},
            'ofi_data': results[1] if not isinstance(results[1], Exception) else {},
            'cvd_data': results[2] if not isinstance(results[2], Exception) else {},
            'liquidity_data': results[3] if not isinstance(results[3], Exception) else {},
            'timestamp': datetime.now(),
            'symbol': symbol
        }
