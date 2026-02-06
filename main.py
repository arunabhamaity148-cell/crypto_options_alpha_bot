"""
Crypto Options Alpha Bot - SLEEP MODE ENABLED
Only runs during golden hours to save Railway resources
"""

import os
import sys
import asyncio
import logging
from datetime import datetime, timezone, timedelta, time
from typing import Dict, List, Optional, Tuple
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
from core.websocket_manager import ws_manager
from core.stealth_request import StealthRequest
from core.data_aggregator import DataAggregator
from core.multi_asset_manager import MultiAssetManager, TradingSignal
from core.time_filter import TimeFilter
from core.news_guard import news_guard
from core.trade_monitor import TradeMonitor, ActiveTrade
from core.market_context import MarketContext
from core.performance_tracker import PerformanceTracker
from tg_bot.bot import AlphaTelegramBot

# ============== LOGGING ==============
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# ============== FLASK APP ==============
flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return {
        'status': 'sleeping' if bot and bot.is_sleeping else 'active',
        'bot': 'Crypto Options Alpha Bot',
        'version': '3.1-sleep-mode',
        'mode': 'GOLDEN_HOURS_ONLY',
        'next_run': bot.next_run_time if bot else 'unknown',
        'timestamp': datetime.now(timezone.utc).isoformat()
    }

@flask_app.route('/health')
def health():
    return {
        'status': 'healthy',
        'mode': 'sleeping' if bot and bot.is_sleeping else 'active',
        'timestamp': datetime.now(timezone.utc).isoformat()
    }, 200

# ============== MAIN BOT CLASS ==============
class AlphaBot:
    def __init__(self):
        self.telegram = AlphaTelegramBot(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)
        self.time_filter = TimeFilter()
        self.is_sleeping = False
        self.next_run_time = None
        self.running = False
        
        # Only initialize if in golden hours (lazy loading)
        self._components = None
        
    def _init_components(self):
        """Initialize components only when needed"""
        if self._components is not None:
            return self._components
            
        logger.info("🔄 Initializing trading components...")
        
        self._components = {
            'stealth': StealthRequest(STEALTH_CONFIG),
            'data_agg': None,  # Will init on first use
            'asset_manager': MultiAssetManager(TRADING_CONFIG, ASSETS_CONFIG),
            'trade_monitor': TradeMonitor(self.telegram),
            'market_context': MarketContext(),
            'performance': PerformanceTracker()
        }
        
        self.cycle_count = 0
        self.last_signal_time = None
        self.signals_sent_this_hour = 0
        self.hour_start = datetime.now(timezone.utc)
        
        return self._components
        
    async def run(self):
        """Main loop with sleep mode"""
        self.running = True
        logger.info("🚀 Bot v3.1-SLEEP-MODE starting")
        
        # Start Flask (always running for health checks)
        flask_thread = Thread(target=self._run_flask, daemon=True)
        flask_thread.start()
        
        while self.running:
            try:
                # Check if should run or sleep
                should_run, sleep_seconds, reason = self.time_filter.should_bot_run()
                
                if not should_run:
                    await self._enter_sleep_mode(sleep_seconds, reason)
                    continue
                
                # Golden hour - start trading
                await self._start_trading_session()
                
            except Exception as e:
                logger.error(f"Main loop error: {e}", exc_info=True)
                await asyncio.sleep(60)
    
    async def _enter_sleep_mode(self, sleep_seconds: int, reason: str):
        """Enter sleep mode to save Railway resources"""
        self.is_sleeping = True
        sleep_hours = sleep_seconds / 3600
        
        self.next_run_time = (datetime.now(timezone.utc) + 
                             timedelta(seconds=sleep_seconds)).isoformat()
        
        logger.info(f"😴 SLEEP MODE: {reason}")
        logger.info(f"   Sleeping for {sleep_hours:.1f} hours")
        logger.info(f"   Next run: {self.next_run_time}")
        
        # Send sleep notification (once)
        if not hasattr(self, '_sleep_notified'):
            await self.telegram.send_status(
                f"😴 <b>Bot Entering Sleep Mode</b>\n\n"
                f"Reason: {reason}\n"
                f"Duration: {sleep_hours:.1f} hours\n"
                f"Next Run: {self.next_run_time[:16]} UTC\n\n"
                f"<i>Saving Railway resources...</i>"
            )
            self._sleep_notified = True
        
        # Deep sleep - minimal resource usage
        # Wake up 2 minutes early to initialize
        actual_sleep = max(0, sleep_seconds - 120)
        
        if actual_sleep > 0:
            await asyncio.sleep(actual_sleep)
        
        # Reset notification flag
        self._sleep_notified = False
        self.is_sleeping = False
        logger.info("⏰ Waking up from sleep mode...")
    
    async def _start_trading_session(self):
        """Start trading during golden hours"""
        logger.info("🌟 GOLDEN HOUR - Starting trading session")
        
        # Initialize components
        comps = self._init_components()
        
        # Send wake notification
        await self.telegram.send_status(
            "🌟 <b>Golden Hour Started</b>\n\n"
            "Trading session active\n"
            "Monitoring for high-quality signals..."
        )
        
        # Start WebSocket
        ws_task = asyncio.create_task(ws_manager.start(ASSETS_CONFIG))
        await asyncio.sleep(3)  # Quick warmup during golden hour
        
        # Start trade monitor
        monitor_task = asyncio.create_task(
            comps['trade_monitor'].start_monitoring(self._get_current_price)
        )
        
        # Trading loop - run until golden hour ends
        session_active = True
        while session_active and self.running:
            try:
                # Check if still golden hour
                should_run, _, _ = self.time_filter.should_bot_run()
                if not should_run:
                    logger.info("Golden hour ended - stopping session")
                    session_active = False
                    break
                
                self.cycle_count += 1
                cycle_start = datetime.now(timezone.utc)
                
                # Reset hourly counter
                if (cycle_start - self.hour_start).seconds >= 3600:
                    self.signals_sent_this_hour = 0
                    self.hour_start = cycle_start
                
                # Check daily reset
                if comps['asset_manager'].should_reset_daily():
                    comps['asset_manager'].reset_daily_counters()
                    comps['performance'].reset_daily()
                
                # Circuit breaker
                if comps['performance'].consecutive_losses >= 3:
                    logger.error("🚨 Circuit breaker - 3 losses")
                    await self.telegram.send_alert(
                        "CIRCUIT BREAKER", 
                        "3 consecutive losses. Stopping for today.",
                        "high"
                    )
                    break
                
                # Fetch and process data
                await self._process_cycle(comps)
                
                # Sleep between cycles (faster during golden hour)
                await asyncio.sleep(45)  # 45 sec vs 60 sec normal
                
            except Exception as e:
                logger.error(f"Trading cycle error: {e}")
                await asyncio.sleep(30)
        
        # Cleanup session
        ws_manager.stop()
        comps['trade_monitor'].stop_monitoring()
        logger.info("Trading session ended")
    
    async def _process_cycle(self, comps: Dict):
        """Process one trading cycle"""
        from strategies.liquidity_hunt import LiquidityHuntStrategy
        from strategies.gamma_squeeze import GammaSqueezeStrategy
        from indicators.greeks_engine import GreeksEngine
        from signals.scorer import AlphaScorer
        
        # Check limits
        if self.signals_sent_this_hour >= 2:
            return
        
        # Fetch data
        logger.info(f"=== Cycle {self.cycle_count} ===")
        
        if comps['data_agg'] is None:
            comps['data_agg'] = DataAggregator(comps['stealth'])
        
        market_data = await comps['data_agg'].get_all_assets_data(ASSETS_CONFIG)
        ws_data = self._get_websocket_data()
        merged_data = self._merge_data(market_data, ws_data)
        
        if not merged_data:
            return
        
        # Process each asset
        signals = []
        for asset, data in merged_data.items():
            if not comps['asset_manager'].can_send_signal(asset):
                continue
            
            current_price = await self._get_current_price(asset)
            if current_price == 0:
                continue
            
            # Check market context
            context = comps['market_context'].analyze({
                'orderbook': data.orderbook,
                'funding_rate': data.funding_rate,
                'asset': asset
            })
            
            if not context['trade_allowed']:
                continue
            
            # Strategy
            try:
                strategy = LiquidityHuntStrategy(asset, ASSETS_CONFIG[asset])
                recent_trades = ws_manager.get_recent_trades(ASSETS_CONFIG[asset]['symbol'], 30)
                
                setup = await strategy.analyze(
                    {
                        'orderbook': data.orderbook,
                        'funding_rate': data.funding_rate,
                        'current_price': current_price
                    },
                    recent_trades
                )
                
                if setup:
                    setup['asset'] = asset
                    setup['current_price'] = current_price
                    setup['context'] = context
                    signals.append(('liquidity_hunt', setup))
                    
            except Exception as e:
                logger.error(f"Strategy error: {e}")
        
        # Score and send
        if signals:
            await self._execute_best_signal(signals, merged_data, comps)
    
    async def _execute_best_signal(self, signals: List, market_data: Dict, comps: Dict):
        """Execute best signal"""
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
            
            score = scorer.calculate_score(
                setup,
                {
                    'orderbook': data.orderbook,
                    'funding_rate': data.funding_rate,
                    'spot_price': current_price
                },
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
        
        if score['total_score'] < 85:
            return
        
        # Position size with risk adjustment
        position_size = comps['asset_manager'].calculate_position_size(
            setup['asset'],
            setup['entry_price'],
            setup['stop_loss'],
            setup.get('context', {}).get('risk_level', 'normal')
        )
        
        position_size *= setup.get('context', {}).get('position_size_mult', 1.0)
        setup['position_size'] = position_size
        
        # Send signal
        await self.telegram.send_signal(setup, score, {
            'orderbook': market_data[setup['asset']].orderbook,
            'position_size': position_size
        })
        
        # Add to monitor
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
            setup['asset'],
            setup['direction'],
            setup['entry_price']
        )
        
        self.last_signal_time = datetime.now(timezone.utc)
        self.signals_sent_this_hour += 1
        
        logger.info(f"✅ Signal sent: {setup['asset']} @ {score['total_score']}")
    
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
        flask_app.run(
            host='0.0.0.0',
            port=PORT,
            threaded=True,
            debug=False,
            use_reloader=False
        )
    
    def stop(self):
        self.running = False
        ws_manager.stop()

# Global
bot = None

if __name__ == "__main__":
    bot = AlphaBot()
    try:
        asyncio.run(bot.run())
    except KeyboardInterrupt:
        bot.stop()
