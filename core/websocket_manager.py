"""
WebSocket Manager - Real-time Data
Fixed: Proper message format handling
"""

import asyncio
import json
import logging
import websockets
from typing import Dict, Callable
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

class WebSocketManager:
    BINANCE_WS_URL = "wss://stream.binance.com:9443/ws"
    BINANCE_STREAM_URL = "wss://stream.binance.com:9443/stream?streams="
    
    def __init__(self):
        self.connections = {}
        self.callbacks = {}
        self.running = False
        self.price_data: Dict[str, Dict] = {}
        self.reconnect_delay = 5
        self.connected = False
        
    async def start(self, assets_config: Dict):
        """Start WebSocket for all assets"""
        self.running = True
        
        # Build stream names - lowercase symbol
        streams = []
        for asset, config in assets_config.items():
            if config.get('enable', True):
                symbol = config['symbol'].lower()
                streams.append(f"{symbol}@trade")
                streams.append(f"{symbol}@depth20@100ms")
        
        if not streams:
            logger.warning("No WebSocket streams configured")
            return
        
        # Build URL
        if len(streams) == 1:
            url = f"{self.BINANCE_WS_URL}/{streams[0]}"
        else:
            streams_param = "/".join(streams)
            url = f"{self.BINANCE_STREAM_URL}{streams_param}"
        
        logger.info(f"🔌 Connecting WebSocket: {len(streams)} streams")
        logger.info(f"URL: {url[:100]}")
        
        while self.running:
            try:
                async with websockets.connect(
                    url, 
                    ping_interval=20, 
                    ping_timeout=10,
                    close_timeout=10
                ) as ws:
                    self.connected = True
                    logger.info("✅ WebSocket connected")
                    
                    async for message in ws:
                        if not self.running:
                            break
                        try:
                            data = json.loads(message)
                            await self._handle_message(data)
                        except json.JSONDecodeError as e:
                            logger.error(f"JSON decode error: {e}")
                        except Exception as e:
                            logger.error(f"Message handling error: {e}")
                        
            except websockets.exceptions.InvalidStatusCode as e:
                logger.error(f"❌ WebSocket HTTP {e.status_code}")
                await asyncio.sleep(30)
                
            except Exception as e:
                self.connected = False
                logger.error(f"❌ WebSocket error: {type(e).__name__}: {e}")
                await asyncio.sleep(self.reconnect_delay)
                self.reconnect_delay = min(self.reconnect_delay * 2, 60)
    
    async def _handle_message(self, data: Dict):
        """Process incoming message"""
        try:
            # Combined stream format: {"stream": "btcusdt@trade", "data": {...}}
            if 'stream' in data and 'data' in data:
                stream = data['stream']
                payload = data['data']
                symbol = stream.split('@')[0].upper()
                
                if 'trade' in stream:
                    await self._handle_trade(symbol, payload)
                elif 'depth' in stream:
                    await self._handle_orderbook(symbol, payload)
                    
            # Single stream format: direct trade data
            elif data.get('e') == 'trade':
                symbol = data.get('s', '').upper()
                if symbol:
                    await self._handle_trade_single(data)
                    
            # Single stream format: depth update
            elif data.get('e') == 'depthUpdate':
                symbol = data.get('s', '').upper()
                if symbol:
                    await self._handle_orderbook_single(data)
                    
        except Exception as e:
            logger.error(f"Message processing error: {e}, data: {str(data)[:200]}")
    
    async def _handle_trade(self, symbol: str, data: Dict):
        """Process trade from combined stream"""
        try:
            if symbol not in self.price_data:
                self.price_data[symbol] = {
                    'trades': [], 
                    'last_price': 0, 
                    'volume': 0,
                    'last_trade_time': 0
                }
            
            trade = {
                'price': float(data.get('p', 0)),
                'qty': float(data.get('q', 0)),
                'time': data.get('T', 0),
                'is_buyer_maker': data.get('m', False),
                'asset': symbol.replace('USDT', ''),
                'id': data.get('t', 0)
            }
            
            # Initialize trades list if not exists
            if 'trades' not in self.price_data[symbol]:
                self.price_data[symbol]['trades'] = []
            
            self.price_data[symbol]['trades'].append(trade)
            self.price_data[symbol]['last_price'] = trade['price']
            self.price_data[symbol]['last_trade_time'] = trade['time']
            
            # Keep last 100 trades
            if len(self.price_data[symbol]['trades']) > 100:
                self.price_data[symbol]['trades'] = self.price_data[symbol]['trades'][-100:]
            
            # Trigger callbacks
            if symbol in self.callbacks:
                try:
                    await self.callbacks[symbol]('trade', trade)
                except Exception as e:
                    logger.error(f"Callback error: {e}")
                    
        except Exception as e:
            logger.error(f"Trade handling error: {e}, data: {data}")
    
    async def _handle_trade_single(self, data: Dict):
        """Process trade from single stream"""
        symbol = data.get('s', '').upper()
        if not symbol:
            return
            
        await self._handle_trade(symbol, {
            'p': data.get('p'),
            'q': data.get('q'),
            'T': data.get('T'),
            'm': data.get('m'),
            't': data.get('t')
        })
    
    async def _handle_orderbook(self, symbol: str, data: Dict):
        """Process orderbook from combined stream"""
        try:
            if symbol not in self.price_data:
                self.price_data[symbol] = {}
            
            # Parse bids and asks
            raw_bids = data.get('bids', [])
            raw_asks = data.get('asks', [])
            
            bids = [[float(b[0]), float(b[1])] for b in raw_bids[:20] if len(b) >= 2]
            asks = [[float(a[0]), float(a[1])] for a in raw_asks[:20] if len(a) >= 2]
            
            self.price_data[symbol]['orderbook'] = {
                'bids': bids,
                'asks': asks,
                'last_update_id': data.get('lastUpdateId', 0),
                'timestamp': data.get('E', int(datetime.now(timezone.utc).timestamp() * 1000))
            }
            
            # Calculate mid price
            if bids and asks:
                self.price_data[symbol]['last_price'] = (bids[0][0] + asks[0][0]) / 2
            
            # Trigger callbacks
            if symbol in self.callbacks:
                try:
                    await self.callbacks[symbol]('orderbook', self.price_data[symbol]['orderbook'])
                except Exception as e:
                    logger.error(f"Callback error: {e}")
                    
        except Exception as e:
            logger.error(f"Orderbook handling error: {e}, data: {data}")
    
    async def _handle_orderbook_single(self, data: Dict):
        """Process orderbook from single stream"""
        symbol = data.get('s', '').upper()
        if not symbol:
            return
            
        # Convert depthUpdate format to standard format
        bids = [[float(b[0]), float(b[1])] for b in data.get('b', [])]
        asks = [[float(a[0]), float(a[1])] for a in data.get('a', [])]
        
        await self._handle_orderbook(symbol, {
            'bids': bids,
            'asks': asks,
            'lastUpdateId': data.get('u', 0),
            'E': data.get('E', 0)
        })
    
    def get_price_data(self, symbol: str) -> Dict:
        """Get latest price data"""
        return self.price_data.get(symbol, {})
    
    def get_recent_trades(self, symbol: str, limit: int = 50) -> list:
        """Get recent trades for CVD calculation"""
        data = self.price_data.get(symbol, {})
        trades = data.get('trades', [])
        return trades[-limit:] if trades else []
    
    def get_last_price(self, symbol: str) -> float:
        """Get last known price"""
        data = self.price_data.get(symbol, {})
        return data.get('last_price', 0)
    
    def register_callback(self, symbol: str, callback: Callable):
        """Register callback for symbol updates"""
        self.callbacks[symbol] = callback
        logger.info(f"📡 Callback registered for {symbol}")
    
    def is_connected(self) -> bool:
        """Check WebSocket connection status"""
        return self.connected and self.running
    
    def get_stats(self) -> Dict:
        """Get WebSocket statistics"""
        return {
            'connected': self.connected,
            'symbols_tracked': len(self.price_data),
            'total_trades': sum(
                len(d.get('trades', [])) 
                for d in self.price_data.values()
            ),
            'symbols': list(self.price_data.keys())
        }
    
    def stop(self):
        """Stop WebSocket"""
        self.running = False
        self.connected = False
        logger.info("🔌 WebSocket stopped")

# Global instance
ws_manager = WebSocketManager()
