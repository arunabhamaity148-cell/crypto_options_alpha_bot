"""
Crypto Options Alpha Bot - with CoinDCX Integration
FIXED VERSION - All Critical Bugs Resolved
"""

import os
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any
from threading import Thread

from flask import Flask, jsonify

from config.settings import (
    PORT, 
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHAT_ID, 
    ASSETS_CONFIG, 
    TRADING_CONFIG, 
    STEALTH_CONFIG
)
from config.secrets import COINDCX_API_KEY, COINDCX_API_SECRET
from core.websocket_manager import ws_manager
from core.stealth_request import StealthRequest
from core.data_aggregator import DataAggregator
from core.multi_asset_manager import MultiAssetManager, TradingSignal
from core.time_filter import TimeFilter
from core.news_guard import news_guard
from core.trade_monitor import TradeMonitor, ActiveTrade
from core.market_context import MarketContext
from core.performance_tracker import PerformanceTracker
from core.coindcx_client import init_coindcx_client
from tg_bot.bot import AlphaTelegramBot

# Constants
WARMUP_SECONDS = 300
CYCLE_INTERVAL_SECONDS = 45
MIN_SCORE_THRESHOLD = 85
MAX_SIGNALS_PER_HOUR = 2
HEALTH_CHECK_INTERVAL = 60

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return {
        'status': 'sleeping' if bot and bot.is_sleeping else 'active',
        'bot': 'Crypto Options Alpha Bot',
        'version': '3.3-fixed',
        'coindcx': 'connected' if COINDCX_API_KEY else 'not_configured',
        'timestamp': datetime.now(timezone.utc).isoformat()
    }

@flask_app.route('/health')
def health():
    return {
        'status': 'healthy',
        'mode': 'sleeping' if bot and bot.is_sleeping else 'active',
        'timestamp': datetime.now(timezone.utc).isoformat()
    }, 200

class AlphaBot:
    def __init__(self):
        self.telegram = AlphaTelegramBot(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)
        self.time_filter = TimeFilter()
        self.is_sleeping = False
        self.next_run_time = None
        self.running = False
        self._components = None
        
        # FIX: Initialize all counters in __init__
        self.cycle_count = 0
        self.last_signal_time = None
        self.signals_sent_this_hour = 0
        self.hour_start = datetime.now(timezone.utc)
        self.start_time = datetime.now(timezone.utc)  # FIX: For WARMUP
        self._sleep_notified = False
        
        # Initialize CoinDCX
        if COINDCX_API_KEY and COINDCX_API_SECRET:
            init_coindcx_client(COINDCX_API_KEY, COINDCX_API_SECRET)
            logger.info("✅ CoinDCX client initialized")
        else:
            logger.warning("⚠️ CoinDCX API keys not set - options data unavailable")
        
    def _init_components(self):
        if self._components is not None:
            return self._components
            
        logger.info("🔄 Initializing trading components...")
        
        self._components = {
            'stealth': StealthRequest(STEALTH_CONFIG),
            'data_agg': None,
            'asset_manager': MultiAssetManager(TRADING_CONFIG, ASSETS_CONFIG),
            'trade_monitor': TradeMonitor(self.telegram),
            'market_context': MarketContext(),
            'performance': PerformanceTracker()
        }
        
        return self._components
        
    def _reset_hourly_counters(self):
        """Reset hourly counters if hour changed"""
        now = datetime.now(timezone.utc)
        if now.hour != self.hour_start.hour or (now - self.hour_start).days > 0:
            self.signals_sent_this_hour = 0
            self.hour_start = now
            logger.info("🔄 Hourly counters reset")
        
    async def run(self):
        self.running = True
        logger.info("🚀 Bot v3.3-FIXED starting")
        
        flask_thread = Thread(target=self._run_flask, daemon=True)
        flask_thread.start()
        
        # Startup message
        coindcx_status = "✅ Connected" if COINDCX_API_KEY else "❌ Not configured"
        try:
            await self.telegram.send_status(
                f"🟢 Bot v3.3 Fixed Started\n"
                f"CoinDCX: {coindcx_status}\n"
                f"Real Options Data: {'Yes' if COINDCX_API_KEY else 'No'}\n"
                f"Mode: Golden Hours Only"
            )
        except Exception as e:
            logger.error(f"Startup message failed: {e}")
        
        while self.running:
            try:
                self.cycle_count += 1
                cycle_start = datetime.now(timezone.utc)
                
                # FIX: Proper WARMUP calculation
                elapsed = (cycle_start - self.start_time).total_seconds()
                if elapsed < WARMUP_SECONDS:
                    remaining = WARMUP_SECONDS - elapsed
                    logger.info(f"⏸️ WARMUP: {remaining:.0f}s remaining")
                    await asyncio.sleep(min(60, remaining))
                    continue
                
                # Reset hourly counters if needed
                self._reset_hourly_counters()
                
                # Check if should run or sleep
                should_run, sleep_seconds, reason = self.time_filter.should_bot_run()
                
                if not should_run:
                    await self._enter_sleep_mode(sleep_seconds, reason)
                    continue
                
                await self._start_trading_session()
                
            except Exception as e:
                logger.error(f"Cycle error: {e}", exc_info=True)
                await asyncio.sleep(60)
    
    async def _enter_sleep_mode(self, sleep_seconds: int, reason: str):
        self.is_sleeping = True
        sleep_hours = sleep_seconds / 3600
        self.next_run_time = (datetime.now(timezone.utc) + timedelta(seconds=sleep_seconds)).isoformat()
        
        logger.info(f"😴 SLEEP: {reason} | {sleep_hours:.1f}h")
        
        if not self._sleep_notified:
            await self.telegram.send_status(
                f"😴 <b>Sleep Mode</b>\nReason: {reason}\n"
                f"Duration: {sleep_hours:.1f}h\nNext: {self.next_run_time[:16]}"
            )
            self._sleep_notified = True
        
        actual_sleep = max(0, sleep_seconds - 120)
        if actual_sleep > 0:
            await asyncio.sleep(actual_sleep)
        
        self._sleep_notified = False
        self.is_sleeping = False
        logger.info("⏰ Waking up...")
    
    async def _start_trading_session(self):
        logger.info("🌟 GOLDEN HOUR - Trading active")
        
        comps = self._init_components()
        
        await self.telegram.send_status("🌟 <b>Golden Hour Started</b>")
        
        # FIX: Proper task management with cancellation
        ws_task = None
        monitor_task = None
        
        try:
            ws_task = asyncio.create_task(ws_manager.start(ASSETS_CONFIG))
            await asyncio.sleep(3)
            
            monitor_task = asyncio.create_task(
                comps['trade_monitor'].start_monitoring(self._get_current_price)
            )
            
            session_active = True
            while session_active and self.running:
                try:
                    should_run, _, _ = self.time_filter.should_bot_run()
                    if not should_run:
                        session_active = False
                        break
                    
                    self._reset_hourly_counters()
                    
                    if self.signals_sent_this_hour >= MAX_SIGNALS_PER_HOUR:
                        await asyncio.sleep(60)
                        continue
                    
                    await self._process_cycle(comps)
                    await asyncio.sleep(CYCLE_INTERVAL_SECONDS)
                    
                except Exception as e:
                    logger.error(f"Trading error: {e}")
                    await asyncio.sleep(30)
                    
        finally:
            # FIX: Proper cleanup
            ws_manager.stop()
            if ws_task:
                ws_task.cancel()
                try:
                    await ws_task
                except asyncio.CancelledError:
                    pass
            
            if monitor_task:
                comps['trade_monitor'].stop_monitoring()
                monitor_task.cancel()
                try:
                    await monitor_task
                except asyncio.CancelledError:
                    pass
            
            logger.info("Session ended")
    
    async def _process_cycle(self, comps: Dict):
        from strategies.liquidity_hunt import LiquidityHuntStrategy
        from signals.scorer import AlphaScorer
        
        logger.info(f"=== Cycle {self.cycle_count} ===")
        
        if comps['data_agg'] is None:
            comps['data_agg'] = DataAggregator(comps['stealth'])
        
        market_data = await comps['data_agg'].get_all_assets_data(ASSETS_CONFIG)
        ws_data = self._get_websocket_data()
        merged_data = self._merge_data(market_data, ws_data)
        
        if not merged_data:
            return
        
        signals = []
        for asset, data in merged_data.items():
            if not comps['asset_manager'].can_send_signal(asset):
                continue
            
            current_price = await self._get_current_price(asset)
            if current_price == 0:
                continue
            
            context = comps['market_context'].analyze({
                'orderbook': data.orderbook,
                'funding_rate': data.funding_rate,
                'asset': asset
            })
            
            if not context['trade_allowed']:
                continue
            
            # FIX: Check news status
            news_ok, news_status = await news_guard.check_trading_allowed(asset)
            if not news_ok:
                logger.warning(f"News guard blocked {asset}: {news_status}")
                continue
            
            try:
                strategy = LiquidityHuntStrategy(asset, ASSETS_CONFIG[asset])
                recent_trades = ws_manager.get_recent_trades(ASSETS_CONFIG[asset]['symbol'], 30)
                
                setup = await strategy.analyze(
                    {
                        'orderbook': data.orderbook,
                        'funding_rate': data.funding_rate,
                        'current_price': current_price,
                        'options_data': data.options_data
                    },
                    recent_trades
                )
                
                if setup:
                    setup['asset'] = asset
                    setup['current_price'] = current_price
                    setup['context'] = context
                    setup['news_status'] = news_status  # FIX: Pass news status
                    signals.append(('liquidity_hunt', setup))
                    
            except Exception as e:
                logger.error(f"Strategy error: {e}")
        
        if signals:
            await self._execute_best_signal(signals, merged_data, comps)
    
    async def _execute_best_signal(self, signals: List, market_data: Dict, comps: Dict):
        from signals.scorer import AlphaScorer
        
        scorer = AlphaScorer(TRADING_CONFIG)
        scored = []
        
        for name, setup in signals:
            asset = setup['asset']
            data = market_data[asset]
            
            current_price = await self._get_current_price(asset)
            setup['entry_price'] = current_price
            setup['stop_loss'] = current_price * 0.992 if setup['direction'] == 'long' else current_price * 1.008
            setup['target_1'] = current_price * 1.018 if setup['direction'] == 'long' else current_price * 0.982
            setup['target_2'] = current_price * 1.030 if setup['direction'] == 'long' else current_price * 0.970
            
            # FIX: Pass news_status to scorer
            score = scorer.calculate_score(
                setup,
                {
                    'orderbook': data.orderbook,
                    'funding_rate': data.funding_rate,
                    'spot_price': current_price
                },
                news_status=setup.get('news_status', 'safe'),
                time_quality='excellent'
            )
            
            setup['score_data'] = score
            setup['total_score'] = score['total_score']
            scored.append((name, setup, score))
        
        if not scored:
            return
        
        scored.sort(key=lambda x: x[2]['total_score'], reverse=True)
        best = scored[0]
        name, setup, score = best
        
        if score['total_score'] < MIN_SCORE_THRESHOLD:
            return
        
        position_size = comps['asset_manager'].calculate_position_size(
            setup['asset'], setup['entry_price'], setup['stop_loss'],
            setup.get('context', {}).get('risk_level', 'normal')
        )
        position_size *= setup.get('context', {}).get('position_size_mult', 1.0)
        setup['position_size'] = position_size
        
        # FIX: Proper options data check
        options_info = setup.get('options_validation', {})
        if options_info and not any(options_info.values()):
            options_info = None
        
        await self.telegram.send_signal(setup, score, {
            'orderbook': market_data[setup['asset']].orderbook,
            'position_size': position_size,
            'options_data': options_info
        })
        
        trade = ActiveTrade(
            asset=setup['asset'],
            direction=setup['direction'],
            entry_price=setup['entry_price'],
            stop_loss=setup['stop_loss'],
            tp1=setup['target_1'],
            tp2=setup['target_2'],
            strike=setup['strike_selection'],
            expiry=datetime.now(timezone.utc) + timedelta(hours=48),
            position_size=position_size,
            auto_manage=True
        )
        comps['trade_monitor'].add_trade(trade)
        
        comps['asset_manager'].record_signal(
            setup['asset'], setup['direction'], setup['entry_price']
        )
        
        self.last_signal_time = datetime.now(timezone.utc)
        self.signals_sent_this_hour += 1
        
        logger.info(f"✅ Signal: {setup['asset']} @ {score['total_score']}")
    
    def _get_websocket_data(self) -> Dict:
        ws_data = {}
        for asset, config in ASSETS_CONFIG.items():
            if config.get('enable'):
                symbol = config['symbol']
                data = ws_manager.get_price_data(symbol)
                if data:
                    ws_data[asset] = data
        return ws_data
    
    def _merge_data(self, rest_data: Dict, ws_data: Dict) -> Dict:
        merged = rest_data.copy()
        for asset, ws_info in ws_data.items():
            if asset in merged:
                if 'last_price' in ws_info:
                    merged[asset].spot_price = ws_info['last_price']
                if 'orderbook' in ws_info:
                    for key in ['ofi_ratio', 'bid_walls', 'ask_walls', 'mid_price']:
                        if key in ws_info['orderbook']:
                            merged[asset].orderbook[key] = ws_info['orderbook'][key]
        return merged
    
    async def _get_current_price(self, asset: str) -> float:
        symbol = ASSETS_CONFIG[asset]['symbol']
        ws_data = ws_manager.get_price_data(symbol)
        if ws_data and 'last_price' in ws_data:
            return ws_data['last_price']
        return 0
    
    def _run_flask(self):
        flask_app.run(host='0.0.0.0', port=PORT, threaded=True, debug=False, use_reloader=False)
    
    def stop(self):
        self.running = False
        ws_manager.stop()

bot = None

if __name__ == "__main__":
    bot = AlphaBot()
    try:
        asyncio.run(bot.run())
    except KeyboardInterrupt:
        bot.stop()
