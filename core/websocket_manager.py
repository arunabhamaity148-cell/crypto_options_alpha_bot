"""
WebSocket Manager for Real-Time Data
Binance WebSocket + Auto-Reconnect
"""

import asyncio
import json
import logging
import websockets
from typing import Dict, Callable, Set
from datetime import datetime

logger = logging.getLogger(__name__)

class WebSocketManager:
    """Manages WebSocket connections for multiple assets"""
    
    BINANCE_WS_URL = "wss://stream.binance.com:9443/ws"
    BINANCE_COMBINED_URL = "wss://stream.binance.com:9443/stream?streams="
    
    def __init__(self):
        self.connections: Dict[str, websockets.WebSocketClientProtocol] = {}
        self.callbacks: Dict[str, Callable] = {}
        self.running = False
        self.reconnect_delay = 5
        self.last_ping = {}
        self.price_data: Dict[str, Dict] = {}
        
    async def start(self, assets_config: Dict):
        """Start WebSocket connections for all assets"""
        self.running = True
        
        # Build combined stream URL
        all_streams = []
        for asset, config in assets_config.items():
            if config.get('enable', True):
                all_streams.extend(config.get('ws_streams', []))
        
        if not all_streams:
            logger.error("No WebSocket streams configured")
            return
        
        # Combined stream for efficiency
        streams_param = "/".join(all_streams)
        url = f"{self.BINANCE_COMBINED_URL}{streams_param}"
        
        logger.info(f"🔌 Connecting WebSocket: {len(all_streams)} streams")
        
        while self.running:
            try:
                async with websockets.connect(url, ping_interval=20, ping_timeout=10) as ws:
                    logger.info("✅ WebSocket connected")
                    
                    async for message in ws:
                        if not self.running:
                            break
                        
                        await self._handle_message(json.loads(message))
                        
            except websockets.exceptions.ConnectionClosed:
                logger.warning(f"🔌 WebSocket closed, reconnecting in {self.reconnect_delay}s...")
                await asyncio.sleep(self.reconnect_delay)
                self.reconnect_delay = min(self.reconnect_delay * 2, 60)  # Exponential backoff
                
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
                await asyncio.sleep(self.reconnect_delay)
    
    async def _handle_message(self, data: Dict):
        """Process incoming WebSocket message"""
        
        try:
            # Combined stream format
            if 'stream' in data and 'data' in data:
                stream = data['stream']
                payload = data['data']
                
                # Extract symbol
                symbol = stream.split('@')[0].upper()
                
                if 'trade' in stream:
                    await self._handle_trade(symbol, payload)
                elif 'depth' in stream:
                    await self._handle_orderbook(symbol, payload)
                    
        except Exception as e:
            logger.error(f"Message handling error: {e}")
    
    async def _handle_trade(self, symbol: str, data: Dict):
        """Process trade data"""
        
        if symbol not in self.price_data:
            self.price_data[symbol] = {
                'trades': [],
                'last_price': 0,
                'volume_24h': 0
            }
        
        trade = {
            'price': float(data['p']),
            'qty': float(data['q']),
            'time': data['T'],
            'is_buyer_maker': data['m']
        }
        
        self.price_data[symbol]['trades'].append(trade)
        self.price_data[symbol]['last_price'] = trade['price']
        
        # Keep last 100 trades
        if len(self.price_data[symbol]['trades']) > 100:
            self.price_data[symbol]['trades'] = self.price_data[symbol]['trades'][-100:]
        
        # Trigger callbacks
        if symbol in self.callbacks:
            await self.callbacks[symbol]('trade', trade)
    
    async def _handle_orderbook(self, symbol: str, data: Dict):
        """Process orderbook data"""
        
        if symbol not in self.price_data:
            self.price_data[symbol] = {}
        
        # Parse orderbook
        bids = [[float(b[0]), float(b[1])] for b in data.get('bids', [])]
        asks = [[float(a[0]), float(a[1])] for a in data.get('asks', [])]
        
        self.price_data[symbol]['orderbook'] = {
            'bids': bids,
            'asks': asks,
            'last_update_id': data.get('lastUpdateId', 0)
        }
        
        # Trigger callbacks
        if symbol in self.callbacks:
            await self.callbacks[symbol]('orderbook', self.price_data[symbol]['orderbook'])
    
    def get_price_data(self, symbol: str) -> Dict:
        """Get latest price data for symbol"""
        return self.price_data.get(symbol, {})
    
    def register_callback(self, symbol: str, callback: Callable):
        """Register callback for symbol updates"""
        self.callbacks[symbol] = callback
        logger.info(f"📡 Callback registered for {symbol}")
    
    def stop(self):
        """Stop all WebSocket connections"""
        self.running = False
        logger.info("🔌 WebSocket manager stopped")

# Global instance
ws_manager = WebSocketManager()
