"""
WebSocket Manager - Real-time Data
"""

import asyncio
import json
import logging
import websockets
from typing import Dict, Callable

logger = logging.getLogger(__name__)

class WebSocketManager:
    BINANCE_WS_URL = "wss://stream.binance.com:9443/ws"
    
    def __init__(self):
        self.connections = {}
        self.callbacks = {}
        self.running = False
        self.price_data: Dict[str, Dict] = {}
        self.reconnect_delay = 5
        
    async def start(self, assets_config: Dict):
        """Start WebSocket for all assets"""
        self.running = True
        
        streams = []
        for asset, config in assets_config.items():
            if config.get('enable', True):
                streams.extend(config.get('ws_streams', []))
        
        if not streams:
            logger.warning("No WebSocket streams configured")
            return
        
        streams_param = "/".join(streams)
        url = f"{self.BINANCE_WS_URL}/stream?streams={streams_param}"
        
        logger.info(f"🔌 Connecting WebSocket: {len(streams)} streams")
        
        while self.running:
            try:
                async with websockets.connect(url, ping_interval=20, ping_timeout=10) as ws:
                    logger.info("✅ WebSocket connected")
                    
                    async for message in ws:
                        if not self.running:
                            break
                        await self._handle_message(json.loads(message))
                        
            except Exception as e:
                logger.error(f"❌ WebSocket error: {e}")
                await asyncio.sleep(self.reconnect_delay)
                self.reconnect_delay = min(self.reconnect_delay * 2, 60)
    
    async def _handle_message(self, data: Dict):
        """Process incoming message"""
        try:
            if 'stream' in data and 'data' in data:
                stream = data['stream']
                payload = data['data']
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
            self.price_data[symbol] = {'trades': [], 'last_price': 0, 'volume': 0}
        
        trade = {
            'price': float(data['p']),
            'qty': float(data['q']),
            'time': data['T'],
            'is_buyer_maker': data['m'],
            'asset': symbol.replace('USDT', '')
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
        
        bids = [[float(b[0]), float(b[1])] for b in data.get('bids', [])]
        asks = [[float(a[0]), float(a[1])] for a in data.get('asks', [])]
        
        self.price_data[symbol]['orderbook'] = {
            'bids': bids[:20],
            'asks': asks[:20],
            'last_update_id': data.get('lastUpdateId', 0),
            'timestamp': data.get('E', 0)
        }
        
        if symbol in self.callbacks:
            await self.callbacks[symbol]('orderbook', self.price_data[symbol]['orderbook'])
    
    def get_price_data(self, symbol: str) -> Dict:
        """Get latest price data"""
        return self.price_data.get(symbol, {})
    
    def get_recent_trades(self, symbol: str, limit: int = 50) -> list:
        """Get recent trades for CVD calculation"""
        data = self.price_data.get(symbol, {})
        trades = data.get('trades', [])
        return trades[-limit:] if trades else []
    
    def register_callback(self, symbol: str, callback: Callable):
        """Register callback for symbol updates"""
        self.callbacks[symbol] = callback
        logger.info(f"📡 Callback registered for {symbol}")
    
    def stop(self):
        """Stop WebSocket"""
        self.running = False
        logger.info("🔌 WebSocket stopped")

# Global instance
ws_manager = WebSocketManager()
