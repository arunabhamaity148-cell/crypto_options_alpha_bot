"""
WebSocket Manager
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
        self.price_data = {}
        
    async def start(self, assets_config: Dict):
        self.running = True
        streams = []
        
        for asset, config in assets_config.items():
            if config.get('enable', True):
                streams.extend(config.get('ws_streams', []))
        
        if not streams:
            logger.error("No WebSocket streams configured")
            return
        
        streams_param = "/".join(streams)
        url = f"{self.BINANCE_WS_URL}/stream?streams={streams_param}"
        
        logger.info(f"Connecting WebSocket: {len(streams)} streams")
        
        while self.running:
            try:
                async with websockets.connect(url, ping_interval=20, ping_timeout=10) as ws:
                    logger.info("WebSocket connected")
                    
                    async for message in ws:
                        if not self.running:
                            break
                        await self._handle_message(json.loads(message))
                        
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
                await asyncio.sleep(5)
    
    async def _handle_message(self, data: Dict):
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
        if symbol not in self.price_data:
            self.price_data[symbol] = {'trades': [], 'last_price': 0}
        
        trade = {
            'price': float(data['p']),
            'qty': float(data['q']),
            'time': data['T'],
            'is_buyer_maker': data['m']
        }
        
        self.price_data[symbol]['trades'].append(trade)
        self.price_data[symbol]['last_price'] = trade['price']
        
        if len(self.price_data[symbol]['trades']) > 100:
            self.price_data[symbol]['trades'] = self.price_data[symbol]['trades'][-100:]
        
        if symbol in self.callbacks:
            await self.callbacks[symbol]('trade', trade)
    
    async def _handle_orderbook(self, symbol: str, data: Dict):
        if symbol not in self.price_data:
            self.price_data[symbol] = {}
        
        bids = [[float(b[0]), float(b[1])] for b in data.get('bids', [])]
        asks = [[float(a[0]), float(a[1])] for a in data.get('asks', [])]
        
        self.price_data[symbol]['orderbook'] = {
            'bids': bids,
            'asks': asks,
            'last_update_id': data.get('lastUpdateId', 0)
        }
        
        if symbol in self.callbacks:
            await self.callbacks[symbol]('orderbook', self.price_data[symbol]['orderbook'])
    
    def get_price_data(self, symbol: str) -> Dict:
        return self.price_data.get(symbol, {})
    
    def register_callback(self, symbol: str, callback: Callable):
        self.callbacks[symbol] = callback
        logger.info(f"Callback registered for {symbol}")
    
    def stop(self):
        self.running = False
        logger.info("WebSocket manager stopped")

ws_manager = WebSocketManager()
