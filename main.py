"""
Crypto Options Alpha Bot - Optimized for Railway Hobby
High Quality Signal + Low Resource Usage
"""

import os
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict
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
from core.data_aggregator import DataAggregator, AssetData
from core.multi_asset_manager import MultiAssetManager, TradingSignal
from core.time_filter import TimeFilter
from core.news_guard import news_guard
from tg_bot.bot import AlphaTelegramBot

# ============== LOGGING ==============
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============== FLASK APP ==============
flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return {
        'status': 'running',
        'bot': 'Crypto Options Alpha Bot',
        'version': '2.1-optimized',
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'assets': list(ASSETS_CONFIG.keys())
    }

@flask_app.route('/health')
def health():
    ws_stats = ws_manager.get_stats()
    return {
        'status': 'healthy',
        'websocket': ws_stats,
        'timestamp': datetime.now(timezone.utc).isoformat()
    }, 200

# ============== MAIN BOT ==============
class AlphaBot:
    def __init__(self):
        self.telegram = AlphaTelegramBot(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)
        self.stealth = StealthRequest(STEALTH_CONFIG)
        self.data_agg = DataAggregator(self.stealth)
        self.asset_manager = MultiAssetManager(TRADING_CONFIG, ASSETS_CONFIG)
        self.time_filter = TimeFilter()
        self.running = False
        self.cycle_count = 0
        self.last_signal_time = None
        
    async def run(self):
        """Main loop - optimized"""
        self.running = True
        logger.info("🚀 Bot v2.1-optimized starting")
        
        # Start WebSocket
        ws_task = asyncio.create_task(ws_manager.start(ASSETS_CONFIG))
        await asyncio.sleep(2)  # Reduced from 3
        
        # Start Flask
        flask_thread = Thread(target=self._run_flask, daemon=True)
        flask_thread.start()
        
        # Startup message
        try:
            await self.telegram.send_status(
                "🟢 Bot v2.1 Started\n"
                f"Assets: {', '.join(ASSETS_CONFIG.keys())}\n"
                f"Threshold: {TRADING_CONFIG['min_score_threshold']}+"
            )
        except Exception as e:
            logger.error(f"Startup msg failed: {e}")
        
        # Main loop
        while self.running:
            try:
                self.cycle_count += 1
                cycle_start = datetime.now(timezone.utc)
                
                # Check daily reset
                if self.asset_manager.should_reset_daily():
                    self.asset_manager.reset_daily_counters()
                
                # Check news
                trading_allowed, news_reason = await news_guard.check_trading_allowed()
                if not trading_allowed:
                    logger.warning(f"Trading halted: {news_reason}")
                    await asyncio.sleep(300)
                    continue
                
                # Get time quality
                time_ok, time_info = self.time_filter.is_best_time()
                time_quality = time_info.get('quality', 'moderate')
                
                # Fetch data (parallel)
                logger.info(f"Cycle {self.cycle_count} | Time: {time_quality}")
                market_data = await self.data_agg.get_all_assets_data(ASSETS_CONFIG)
                ws_data = self._get_websocket_data()
                
                # Merge
                merged_data = self._merge_data(market_data, ws_data)
                
                if merged_data:
                    await self._process_market_data(merged_data, time_quality)
                
                # Adaptive sleep based on time quality
                cycle_duration = (datetime.now(timezone.utc) - cycle_start).total_seconds()
                if time_quality == 'excellent':
                    sleep_time = max(30, 45 - cycle_duration)  # Faster in good times
                elif time_quality == 'good':
                    sleep_time = max(45, 60 - cycle_duration)
                else:
                    sleep_time = max(60, 90 - cycle_duration)  # Slower in bad times
                
                logger.info(f"Cycle complete | Duration: {cycle_duration:.1f}s | Sleep: {sleep_time:.0f}s")
                await asyncio.sleep(sleep_time)
                
            except Exception as e:
                logger.error(f"Cycle error: {e}")
                await asyncio.sleep(60)
    
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
                if 'trades' in ws_info:
                    merged[asset].recent_trades = ws_info['trades']
                if 'last_price' in ws_info:
                    merged[asset].spot_price = ws_info['last_price']
                # Add WebSocket OFI if available
                if 'orderbook' in ws_info and 'ofi_ratio' in ws_info['orderbook']:
                    merged[asset].orderbook['ofi_ratio'] = ws_info['orderbook']['ofi_ratio']
        return merged
    
    async def get_current_price(self, asset: str) -> float:
        """Public method for trade monitor"""
        symbol = ASSETS_CONFIG[asset]['symbol']
        ws_data = ws_manager.get_price_data(symbol)
        if ws_data and 'last_price' in ws_data:
            return ws_data['last_price']
        return await self.data_agg.get_spot_price(symbol)
    
    async def _process_market_data(self, market_data: Dict, time_quality: str):
        """Process with enhanced logging"""
        from strategies.liquidity_hunt import LiquidityHuntStrategy
        from strategies.gamma_squeeze import GammaSqueezeStrategy
        from indicators.greeks_engine import GreeksEngine
        from signals.scorer import AlphaScorer
        
        signals = []
        
        for asset, data in market_data.items():
            if not self.asset_manager.can_send_signal(asset):
                continue
            
            config = ASSETS_CONFIG[asset]
            symbol = config['symbol']
            recent_trades = ws_manager.get_recent_trades(symbol, 30)
            
            # Strategy 1: Liquidity Hunt
            try:
                lh_strategy = LiquidityHuntStrategy(asset, config)
                lh_setup = await lh_strategy.analyze(
                    {'orderbook': data.orderbook, 'funding_rate': data.funding_rate}, 
                    recent_trades
                )
                
                if lh_setup:
                    lh_setup['asset'] = asset
                    signals.append(('liquidity_hunt', lh_setup))
                    logger.info(f"🎯 LH Signal: {asset} @ {lh_setup.get('confidence', 0)}")
                    
            except Exception as e:
                logger.error(f"LH error: {e}")
            
            # Strategy 2: Gamma Squeeze (only in excellent time)
            if time_quality in ['excellent', 'good']:
                try:
                    greeks = GreeksEngine()
                    gs_strategy = GammaSqueezeStrategy(asset, config, greeks)
                    gs_setup = await gs_strategy.analyze(
                        {'orderbook': data.orderbook},
                        []
                    )
                    
                    if gs_setup:
                        gs_setup['asset'] = asset
                        signals.append(('gamma_squeeze', gs_setup))
                        logger.info(f"🎯 GS Signal: {asset} @ {gs_setup.get('confidence', 0)}")
                        
                except Exception as e:
                    logger.error(f"GS error: {e}")
        
        if signals:
            await self._score_and_send_signals(signals, market_data, time_quality)
    
    async def _score_and_send_signals(self, signals: List, market_data: Dict, time_quality: str):
        """Score with detailed logging"""
        from signals.scorer import AlphaScorer
        
        scorer = AlphaScorer(TRADING_CONFIG)
        scored_signals = []
        
        for strategy_name, setup in signals:
            asset = setup['asset']
            data = market_data.get(asset)
            if not data:
                continue
            
            # Prepare market data for scoring
            score_data = {
                'orderbook': data.orderbook,
                'funding_rate': data.funding_rate,
                'spot_price': data.spot_price,
                'perp_price': data.perp_price,
            }
            
            score = scorer.calculate_score(
                setup, 
                score_data,
                news_status="safe",
                time_quality=time_quality
            )
            
            setup['score_data'] = score
            scored_signals.append((strategy_name, setup, score))
            
            # Detailed log
            logger.info(f"📊 {asset} | Score: {score['total_score']} | "
                       f"Micro: {score['component_scores']['microstructure']} | "
                       f"Mom: {score['component_scores']['momentum']} | "
                       f"Rec: {score['recommendation']}")
        
        # Sort by score
        scored_signals.sort(key=lambda x: x[2]['total_score'], reverse=True)
        
        # Accept signals
        threshold = TRADING_CONFIG['min_score_threshold']
        trading_signals = []
        
        for strategy_name, setup, score in scored_signals:
            total_score = score['total_score']
            
            # Exceptional signals bypass some limits
            if total_score >= 90:
                logger.info(f"⭐ EXCEPTIONAL: {setup['asset']} @ {total_score}")
                should_add = True
            elif total_score >= threshold:
                should_add = True
            else:
                should_add = False
            
            if should_add:
                signal = TradingSignal(
                    asset=setup['asset'],
                    strategy=strategy_name,
                    direction=setup['direction'],
                    entry_price=setup['entry_price'],
                    stop_loss=setup['stop_loss'],
                    target_1=setup['target_1'],
                    target_2=setup['target_2'],
                    strike_selection=setup['strike_selection'],
                    expiry_suggestion=setup['expiry_suggestion'],
                    confidence=setup['confidence'],
                    score_breakdown=score['component_scores'],
                    rationale=setup['rationale'],
                    timestamp=datetime.now(timezone.utc)
                )
                trading_signals.append(signal)
                logger.info(f"✅ ACCEPTED: {setup['asset']} @ {total_score}")
        
        logger.info(f"Signals: {len(trading_signals)}/{len(scored_signals)} accepted")
        
        # Send top signals
        max_signals = TRADING_CONFIG['max_signals_per_day']
        for signal in trading_signals[:max_signals]:
            if not self.asset_manager.can_send_signal(signal.asset):
                continue
            
            # Cooldown check (min 15 min between signals)
            if self.last_signal_time:
                time_since = (datetime.now(timezone.utc) - self.last_signal_time).seconds
                if time_since < 900:  # 15 minutes
                    logger.info(f"Cooldown: {signal.asset} ({time_since}s remaining)")
                    continue
            
            original = next((s for s in scored_signals if s[1]['asset'] == signal.asset), None)
            if not original:
                continue
            
            _, setup, score = original
            
            try:
                print("\n" + "="*50)
                print(f"🚨 SIGNAL: {signal.asset} {signal.direction.upper()}")
                print(f"Score: {score['total_score']}/100 | Quality: {score['confidence']}")
                print(f"Entry: {signal.entry_price} | Stop: {signal.stop_loss}")
                print(f"Targets: {signal.target_1} / {signal.target_2}")
                print("="*50 + "\n")
                
                await self.telegram.send_signal(setup, score, {
                    'orderbook': market_data[signal.asset].orderbook
                })
                
                self.asset_manager.record_signal(signal.asset)
                self.last_signal_time = datetime.now(timezone.utc)
                logger.info(f"✅ SENT: {signal.asset}")
                
                await asyncio.sleep(2)
                
            except Exception as e:
                logger.error(f"Send failed: {e}")
    
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
        logger.info("Bot stopped")

# ============== ENTRY ==============
if __name__ == "__main__":
    bot = AlphaBot()
    try:
        asyncio.run(bot.run())
    except KeyboardInterrupt:
        bot.stop()
    except Exception as e:
        logger.error(f"Fatal: {e}")
        raise
