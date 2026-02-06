"""
Crypto Options Alpha Bot - Final Version
WebSocket + Webhook + Flask Health Check
Railway Optimized - Never Stops
"""

import asyncio
import logging
import os
from datetime import datetime, timedelta

from config.settings import (
    TRADING_CONFIG, ASSETS_CONFIG, ASSET_THRESHOLDS,
    TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, PORT
)

from core.websocket_manager import ws_manager
from core.data_aggregator import DataAggregator
from core.multi_asset_manager import MultiAssetManager, TradingSignal
from core.time_filter import TimeFilter
from core.news_guard import news_guard
from core.trade_monitor import TradeMonitor, ActiveTrade
from signals.scorer import AlphaScorer
from telegram.bot import AlphaTelegramBot
from webhook_server import start_webhook_server

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class AlphaBot:
    """Production-ready bot with WebSocket and Webhook"""
    
    def __init__(self):
        logger.info("🚀 Alpha Bot v2.0 - WebSocket Edition")
        
        self.telegram = AlphaTelegramBot(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)
        self.asset_manager = MultiAssetManager(TRADING_CONFIG, ASSETS_CONFIG)
        self.time_filter = TimeFilter()
        self.news_guard = news_guard
        self.scorer = AlphaScorer(TRADING_CONFIG)
        self.trade_monitor = TradeMonitor(self.telegram)
        self.data_agg = DataAggregator(None)  # WebSocket primary
        
        # State
        self.running = False
        self.paused = False
        self.cycle_count = 0
        self.ws_connected = False
        self._alerted_events = set()
        
        # WebSocket data cache
        self.ws_data = {}
        
        logger.info("✅ Bot initialized")
    
    async def run(self):
        """Main loop with WebSocket"""
        self.running = True
        
        # Start Webhook server for Railway
        start_webhook_server(self, PORT)
        
        # Start WebSocket manager
        asyncio.create_task(self._websocket_loop())
        
        # Start background tasks
        asyncio.create_task(self._news_watcher())
        asyncio.create_task(self._trade_monitor_loop())
        
        # Startup message
        await self.telegram.send_status(
            "🟢 <b>Bot Started v2.0</b>\n\n"
            f"WebSocket: Connecting...\n"
            f"Health Check: http://0.0.0.0:{PORT}/health\n"
            f"Assets: {', '.join(TRADING_CONFIG['assets'])}"
        )
        
        # Main processing loop
        while self.running:
            try:
                if self.paused:
                    await asyncio.sleep(60)
                    continue
                
                self.cycle_count += 1
                logger.info(f"\n{'='*50}")
                logger.info(f"🔄 Cycle #{self.cycle_count}")
                
                # Check news
                allowed, news_reason = await self.news_guard.check_trading_allowed()
                if not allowed:
                    logger.warning(f"🛑 NEWS BLOCK: {news_reason}")
                    await asyncio.sleep(180)
                    continue
                
                # Check time
                is_good, time_info = self.time_filter.is_best_time()
                time_quality = time_info.get('quality', 'unknown')
                
                if time_quality == 'avoid':
                    sleep = self.time_filter.get_sleep_time()
                    logger.info(f"⏰ Avoid time, sleep {sleep//60}m")
                    await asyncio.sleep(sleep)
                    continue
                
                # Get data from WebSocket cache
                assets_data = self._get_ws_data()
                
                if not assets_data:
                    logger.warning("⏳ Waiting for WebSocket data...")
                    await asyncio.sleep(5)
                    continue
                
                # Analyze
                all_signals = []
                for asset, data in assets_data.items():
                    if not self.asset_manager.can_send_signal(asset):
                        continue
                    
                    # Quick analysis on WebSocket data
                    signal = await self._quick_analyze(asset, data)
                    if signal:
                        signal['time_quality'] = time_quality
                        signal['news_status'] = news_reason
                        all_signals.append(signal)
                
                # Process signals
                if all_signals:
                    await self._process_signals(all_signals)
                
                # Dynamic sleep
                sleep = 30 if time_quality == 'excellent' else 60
                logger.info(f"⏳ Sleep {sleep}s")
                await asyncio.sleep(sleep)
                
            except Exception as e:
                logger.error(f"❌ Error: {e}")
                await asyncio.sleep(60)
    
    async def _websocket_loop(self):
        """WebSocket connection loop"""
        try:
            # Register callbacks
            for asset in ASSETS_CONFIG:
                symbol = ASSETS_CONFIG[asset]['symbol'].lower()
                ws_manager.register_callback(symbol, self._on_ws_update)
            
            # Start WebSocket
            await ws_manager.start(ASSETS_CONFIG)
            
        except Exception as e:
            logger.error(f"WebSocket loop error: {e}")
            self.ws_connected = False
    
    def _on_ws_update(self, symbol: str, data_type: str, data: dict):
        """Handle WebSocket updates"""
        self.ws_connected = True
        
        if symbol not in self.ws_data:
            self.ws_data[symbol] = {
                'trades': [],
                'orderbook': {},
                'last_update': datetime.now()
            }
        
        if data_type == 'trade':
            self.ws_data[symbol]['trades'].append(data)
            if len(self.ws_data[symbol]['trades']) > 100:
                self.ws_data[symbol]['trades'] = self.ws_data[symbol]['trades'][-100:]
        
        elif data_type == 'orderbook':
            self.ws_data[symbol]['orderbook'] = data
    
    def _get_ws_data(self) -> dict:
        """Get current WebSocket data for all assets"""
        result = {}
        
        for asset, config in ASSETS_CONFIG.items():
            symbol = config['symbol'].lower()
            
            if symbol in self.ws_data:
                data = self.ws_data[symbol]
                
                # Check freshness (max 10 seconds old)
                age = (datetime.now() - data.get('last_update', datetime.now())).seconds
                
                if age < 10 and data.get('orderbook'):
                    result[asset] = type('Data', (), {
                        'spot_price': data['trades'][-1]['price'] if data['trades'] else 0,
                        'orderbook': data['orderbook'],
                        'trades': data['trades'][-20:],
                        'timestamp': datetime.now()
                    })()
        
        return result
    
    async def _quick_analyze(self, asset: str, data) -> dict:
        """Quick analysis on WebSocket data"""
        # Simplified - check for liquidity sweep
        ob = data.orderbook
        
        if not ob or not data.trades:
            return None
        
        # Get recent CVD
        buy_vol = sum(t['qty'] for t in data.trades if not t.get('is_buyer_maker', False))
        sell_vol = sum(t['qty'] for t in data.trades if t.get('is_buyer_maker', False))
        
        cvd = buy_vol - sell_vol
        
        # Check for sweep pattern
        bids = ob.get('bids', [])
        asks = ob.get('asks', [])
        
        if not bids or not asks:
            return None
        
        current_price = (bids[0][0] + asks[0][0]) / 2
        
        # Simple sweep detection
        if cvd > 0 and len(bids) > 5:
            # Potential long setup
            return {
                'asset': asset,
                'strategy': 'ws_liquidity_sweep',
                'direction': 'long',
                'entry_price': current_price,
                'stop_loss': bids[5][0] if len(bids) > 5 else current_price * 0.99,
                'target_1': current_price * 1.015,
                'target_2': current_price * 1.03,
                'confidence': 75,
                'strike_selection': f"{round(current_price/100)*100} CE",
                'expiry_suggestion': '24h',
                'rationale': {'cvd': cvd, 'source': 'websocket'}
            }
        
        return None
    
    async def _process_signals(self, signals: list):
        """Process and send signals"""
        for sig in signals:
            # Score
            score_data = self.scorer.calculate_score(
                sig, {}, sig.get('news_status', 'safe'), sig.get('time_quality', 'moderate')
            )
            
            if score_data['total_score'] < 85:
                continue
            
            # Send
            await self.telegram.send_signal(sig, score_data, {})
            
            # Add to monitor
            trade = ActiveTrade(
                asset=sig['asset'],
                direction=sig['direction'],
                entry_price=sig['entry_price'],
                stop_loss=sig['stop_loss'],
                tp1=sig['target_1'],
                tp2=sig['target_2'],
                strike=sig['strike_selection'],
                expiry=datetime.now() + timedelta(hours=24),
                position_size=0.01
            )
            self.trade_monitor.add_trade(trade)
            
            self.asset_manager.record_signal(sig['asset'])
    
    async def _news_watcher(self):
        """News monitoring"""
        while self.running:
            try:
                await asyncio.sleep(120)
                
                events = await self.news_guard.fetch_economic_calendar()
                
                for event in events:
                    if event.get('hours_until', 999) <= 24:
                        key = f"{event['event']}_{event['date']}"
                        
                        if key not in self._alerted_events:
                            self._alerted_events.add(key)
                            
                            await self.telegram.send_news_alert(
                                f"📅 UPCOMING: {event['event']}",
                                f"Date: {event['date']}\nImpact: {event.get('impact', 'high')}",
                                event.get('impact', 'high'),
                                f"Avoid ±2 hours of {event['event']}"
                            )
                
                # Check for immediate halt
                is_safe, reason = await self.news_guard.check_trading_allowed()
                
                if not is_safe and "just" in reason.lower():
                    await self.telegram.send_news_alert(
                        "⏸️ TRADING PAUSED",
                        reason,
                        "extreme",
                        "Bot will resume after event"
                    )
                    
            except Exception as e:
                logger.error(f"News watcher error: {e}")
    
    async def _trade_monitor_loop(self):
        """Monitor active trades"""
        while self.running:
            try:
                if self.trade_monitor.active_trades:
                    # Update prices from WebSocket
                    for trade in self.trade_monitor.active_trades:
                        symbol = ASSETS_CONFIG[trade.asset]['symbol'].lower()
                        if symbol in self.ws_data and self.ws_data[symbol]['trades']:
                            price = self.ws_data[symbol]['trades'][-1]['price']
                            trade.update_price(price)
                    
                    # Check alerts
                    await self.trade_monitor.check_alerts()
                
                await asyncio.sleep(5)
                
            except Exception as e:
                logger.error(f"Monitor error: {e}")
                await asyncio.sleep(10)
    
    async def stop(self):
        """Shutdown"""
        self.running = False
        ws_manager.stop()
        self.trade_monitor.stop_monitoring()
        await self.telegram.send_status("🔴 Bot Stopped")


async def main():
    """Entry point"""
    bot = AlphaBot()
    
    try:
        await bot.run()
    except Exception as e:
        logging.critical(f"Fatal: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    asyncio.run(main())
