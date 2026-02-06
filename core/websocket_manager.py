"""
WebSocket Manager - Optimized for Railway Hobby Plan
Reduced memory, faster reconnect, efficient processing
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
        self.reconnect_delay = 3  # Start lower
        self.connected = False
        self.message_count = 0
        self.last_cleanup = datetime.now(timezone.utc)
        
    async def start(self, assets_config: Dict):
        """Start WebSocket - optimized for fewer assets"""
        self.running = True
        
        # Build stream names - only enabled assets
        streams = []
        enabled_assets = {
            k: v for k, v in assets_config.items() 
            if v.get('enable', True)
        }
        
        for asset, config in enabled_assets.items():
            symbol = config['symbol'].lower()
            # Reduced streams: only trade + depth (no 100ms for less CPU)
            streams.append(f"{symbol}@trade")
            streams.append(f"{symbol}@depth20@250ms")  # 250ms instead of 100ms
        
        if not streams:
            logger.warning("No WebSocket streams configured")
            return
        
        # Build URL
        if len(streams) == 1:
            url = f"{self.BINANCE_WS_URL}/{streams[0]}"
        else:
            streams_param = "/".join(streams)
            url = f"{self.BINANCE_STREAM_URL}{streams_param}"
        
        logger.info(f"🔌 Connecting: {len(enabled_assets)} assets, {len(streams)} streams")
        
        while self.running:
            try:
                async with websockets.connect(
                    url, 
                    ping_interval=30,  # Increased from 20
                    ping_timeout=15,   # Increased from 10
                    close_timeout=10
                ) as ws:
                    self.connected = True
                    self.reconnect_delay = 3  # RESET on successful connect
                    logger.info("✅ WebSocket connected")
                    
                    async for message in ws:
                        if not self.running:
                            break
                        
                        self.message_count += 1
                        
                        # Periodic cleanup every 1000 messages
                        if self.message_count % 1000 == 0:
                            self._cleanup_old_data()
                        
                        try:
                            data = json.loads(message)
                            await self._handle_message(data)
                        except json.JSONDecodeError:
                            continue
                        except Exception as e:
                            logger.error(f"Handler error: {e}")
                        
            except websockets.exceptions.InvalidStatusCode as e:
                logger.error(f"HTTP {e.status_code}, waiting 20s...")
                await asyncio.sleep(20)
                
            except Exception as e:
                self.connected = False
                logger.error(f"WS error: {type(e).__name__}")
                await asyncio.sleep(self.reconnect_delay)
                # Exponential backoff with max 30s
                self.reconnect_delay = min(self.reconnect_delay * 1.5, 30)
    
    def _cleanup_old_data(self):
        """Memory cleanup for Railway Hobby"""
        now = datetime.now(timezone.utc)
        if (now - self.last_cleanup).seconds < 60:
            return
        
        for symbol in self.price_data:
            # Keep only last 50 trades (was 100)
            if 'trades' in self.price_data[symbol]:
                trades = self.price_data[symbol]['trades']
                if len(trades) > 50:
                    self.price_data[symbol]['trades'] = trades[-50:]
        
        self.last_cleanup = now
        logger.debug("Memory cleanup completed")
    
    async def _handle_message(self, data: Dict):
        """Process message - optimized"""
        try:
            if 'stream' in data and 'data' in data:
                stream = data['stream']
                payload = data['data']
                symbol = stream.split('@')[0].upper()
                
                if 'trade' in stream:
                    await self._handle_trade(symbol, payload)
                elif 'depth' in stream:
                    await self._handle_orderbook(symbol, payload)
                    
            elif data.get('e') == 'trade':
                symbol = data.get('s', '').upper()
                if symbol:
                    await self._handle_trade_single(data)
                    
            elif data.get('e') == 'depthUpdate':
                symbol = data.get('s', '').upper()
                if symbol:
                    await self._handle_orderbook_single(data)
                    
        except Exception as e:
            logger.error(f"Process error: {e}")
    
    async def _handle_trade(self, symbol: str, data: Dict):
        """Process trade - memory optimized"""
        if symbol not in self.price_data:
            self.price_data[symbol] = {
                'trades': [], 
                'last_price': 0, 
                'last_trade_time': 0
            }
        
        trade = {
            'price': float(data.get('p', 0)),
            'qty': float(data.get('q', 0)),
            'time': data.get('T', 0),
            'm': data.get('m', False),  # is_buyer_maker
        }
        
        self.price_data[symbol]['trades'].append(trade)
        self.price_data[symbol]['last_price'] = trade['price']
        self.price_data[symbol]['last_trade_time'] = trade['time']
        
        # Keep only 50 trades
        if len(self.price_data[symbol]['trades']) > 50:
            self.price_data[symbol]['trades'] = self.price_data[symbol]['trades'][-50:]
        
        # Callback
        if symbol in self.callbacks:
            try:
                await self.callbacks[symbol]('trade', trade)
            except:
                pass
    
    async def _handle_orderbook(self, symbol: str, data: Dict):
        """Process orderbook - calculate OFI here"""
        try:
            if symbol not in self.price_data:
                self.price_data[symbol] = {}
            
            raw_bids = data.get('bids', [])
            raw_asks = data.get('asks', [])
            
            bids = [[float(b[0]), float(b[1])] for b in raw_bids[:10]]
            asks = [[float(a[0]), float(a[1])] for a in raw_asks[:10]]
            
            if not bids or not asks:
                return
            
            best_bid = bids[0][0]
            best_ask = asks[0][0]
            mid_price = (best_bid + best_ask) / 2
            
            # Calculate OFI
            bid_vol = sum(b[1] for b in bids)
            ask_vol = sum(a[1] for a in asks)
            total_vol = bid_vol + ask_vol
            ofi = (bid_vol - ask_vol) / total_vol if total_vol > 0 else 0
            
            # Calculate walls
            avg_bid = bid_vol / len(bids) if bids else 0
            avg_ask = ask_vol / len(asks) if asks else 0
            
            bid_walls = [(b[0], b[1]) for b in bids if b[1] > avg_bid * 3]
            ask_walls = [(a[0], a[1]) for a in asks if a[1] > avg_ask * 3]
            
            self.price_data[symbol]['orderbook'] = {
                'bids': bids,
                'asks': asks,
                'mid_price': mid_price,
                'spread_pct': (best_ask - best_bid) / mid_price * 100,
                'ofi_ratio': ofi,
                'bid_pressure': sum(b[0] * b[1] for b in bids),
                'ask_pressure': sum(a[0] * a[1] for a in asks),
                'bid_walls': bid_walls[:2],  # Top 2 only
                'ask_walls': ask_walls[:2],
            }
            
            self.price_data[symbol]['last_price'] = mid_price
            
            if symbol in self.callbacks:
                await self.callbacks[symbol]('orderbook', self.price_data[symbol]['orderbook'])
                    
        except Exception as e:
            logger.error(f"OB error: {e}")
    
    async def _handle_trade_single(self, data: Dict):
        symbol = data.get('s', '').upper()
        if symbol:
            await self._handle_trade(symbol, {
                'p': data.get('p'), 'q': data.get('q'),
                'T': data.get('T'), 'm': data.get('m')
            })
    
    async def _handle_orderbook_single(self, data: Dict):
        symbol = data.get('s', '').upper()
        if not symbol:
            return
            
        bids = [[float(b[0]), float(b[1])] for b in data.get('b', [])]
        asks = [[float(a[0]), float(a[1])] for a in data.get('a', [])]
        
        await self._handle_orderbook(symbol, {'bids': bids, 'asks': asks})
    
    def get_price_data(self, symbol: str) -> Dict:
        return self.price_data.get(symbol, {})
    
    def get_recent_trades(self, symbol: str, limit: int = 30) -> list:  # Reduced from 50
        data = self.price_data.get(symbol, {})
        trades = data.get('trades', [])
        return trades[-limit:] if trades else []
    
    def get_last_price(self, symbol: str) -> float:
        data = self.price_data.get(symbol, {})
        return data.get('last_price', 0)
    
    def register_callback(self, symbol: str, callback: Callable):
        self.callbacks[symbol] = callback
    
    def is_connected(self) -> bool:
        return self.connected and self.running
    
    def get_stats(self) -> Dict:
        return {
            'connected': self.connected,
            'symbols_tracked': len(self.price_data),
            'messages_processed': self.message_count,
        }
    
    def stop(self):
        self.running = False
        self.connected = False

# Global instance
ws_manager = WebSocketManager()
