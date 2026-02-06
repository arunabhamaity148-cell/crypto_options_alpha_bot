"""
Crypto Options Alpha Bot - Main Entry Point
Single file version - Reliable for Railway deployment
"""

import os
import sys
import asyncio
import logging
import json
import random
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from threading import Thread

from flask import Flask, jsonify
from telegram import Bot

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
from core.trade_monitor import TradeMonitor, ActiveTrade
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
        'status': 'running',
        'bot': 'Crypto Options Alpha Bot',
        'version': '2.0',
        'timestamp': datetime.now(timezone.utc).isoformat()
    }

@flask_app.route('/health')
def health():
    ws_stats = ws_manager.get_stats()
    return {
        'status': 'healthy',
        'websocket_connected': ws_stats['connected'],
        'timestamp': datetime.now(timezone.utc).isoformat()
    }, 200

# ============== MAIN BOT CLASS ==============
class AlphaBot:
    def __init__(self):
        self.telegram = AlphaTelegramBot(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)
        self.stealth = StealthRequest(STEALTH_CONFIG)
        self.data_agg = DataAggregator(self.stealth)
        self.asset_manager = MultiAssetManager(TRADING_CONFIG, ASSETS_CONFIG)
        self.time_filter = TimeFilter()
        self.trade_monitor = TradeMonitor(self.telegram)
        self.running = False
        self.cycle_count = 0
        
    async def run(self):
        """Main bot loop"""
        self.running = True
        logger.info("🚀 Bot starting v2.0")
        
        # Start WebSocket
        ws_task = asyncio.create_task(ws_manager.start(ASSETS_CONFIG))
        await asyncio.sleep(3)
        
        # Start Trade Monitor
        monitor_task = asyncio.create_task(
            self.trade_monitor.start_monitoring(self._get_current_price)
        )
        
        # Start Flask
        flask_thread = Thread(target=self._run_flask, daemon=True)
        flask_thread.start()
        
        # Startup message
        try:
            await self.telegram.send_status("🟢 Bot Started v2.0")
        except Exception as e:
            logger.error(f"Startup message failed: {e}")
        
        # Main loop
        while self.running:
            try:
                self.cycle_count += 1
                logger.info(f"=== Cycle {self.cycle_count} ===")
                
                # Check daily reset
                if self.asset_manager.should_reset_daily():
                    self.asset_manager.reset_daily_counters()
                
                # Check news guard
                trading_allowed, news_reason = await news_guard.check_trading_allowed()
                if not trading_allowed:
                    logger.warning(f"Trading halted: {news_reason}")
                    await asyncio.sleep(300)
                    continue
                
                # Fetch data
                logger.info("Fetching market data...")
                market_data = await self.data_agg.get_all_assets_data(ASSETS_CONFIG)
                ws_data = self._get_websocket_data()
                
                logger.info(f"Data: REST={len(market_data)}, WS={len(ws_data)}")
                
                # Merge and process
                merged_data = self._merge_data(market_data, ws_data)
                if merged_data:
                    await self._process_market_data(merged_data)
                
                logger.info(f"Cycle {self.cycle_count} complete")
                await asyncio.sleep(60)
                
            except Exception as e:
                logger.error(f"Error: {e}", exc_info=True)
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
        return merged
    
    async def _get_current_price(self, asset: str) -> float:
        symbol = ASSETS_CONFIG[asset]['symbol']
        ws_data = ws_manager.get_price_data(symbol)
        if ws_data and 'last_price' in ws_data:
            return ws_data['last_price']
        try:
            return await self.data_agg._get_spot_price(symbol)
        except:
            return 0
    
    async def _process_market_data(self, market_data: Dict):
        """Process market data and generate signals"""
        from strategies.liquidity_hunt import LiquidityHuntStrategy
        from strategies.gamma_squeeze import GammaSqueezeStrategy
        from indicators.greeks_engine import GreeksEngine
        from signals.scorer import AlphaScorer
        
        signals = []
        
        for asset, data in market_data.items():
            logger.info(f"Analyzing {asset}...")
            
            if not self.asset_manager.can_send_signal(asset):
                continue
            
            config = ASSETS_CONFIG[asset]
            symbol = config['symbol']
            recent_trades = ws_manager.get_recent_trades(symbol, 50)
            
            # Strategy 1: Liquidity Hunt
            try:
                lh_strategy = LiquidityHuntStrategy(asset, config)
                lh_setup = await lh_strategy.analyze(
                    {'orderbook': data.orderbook}, 
                    recent_trades
                )
                
                if lh_setup:
                    lh_setup['asset'] = asset
                    signals.append(('liquidity_hunt', lh_setup))
                    logger.info(f"🎯 Signal: Liquidity Hunt {asset} @ {lh_setup.get('confidence', 0)}")
                    
            except Exception as e:
                logger.error(f"LH error: {e}")
            
            # Strategy 2: Gamma Squeeze
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
                    logger.info(f"🎯 Signal: Gamma Squeeze {asset} @ {gs_setup.get('confidence', 0)}")
                    
            except Exception as e:
                logger.error(f"GS error: {e}")
        
        if signals:
            await self._score_and_send_signals(signals, market_data)
    
    async def _score_and_send_signals(self, signals: List, market_data: Dict):
        """Score and send signals"""
        from signals.scorer import AlphaScorer
        
        scorer = AlphaScorer(TRADING_CONFIG)
        scored_signals = []
        
        for strategy_name, setup in signals:
            asset = setup['asset']
            data = market_data.get(asset)
            if not data:
                continue
            
            score = scorer.calculate_score(
                setup, 
                {'orderbook': data.orderbook},
                news_status="safe",
                time_quality="excellent"
            )
            
            setup['score_data'] = score
            scored_signals.append((strategy_name, setup, score))
            
            logger.info(f"📊 {asset}: Score={score['total_score']}, Rec={score['recommendation']}")
        
        # Sort by score
        scored_signals.sort(key=lambda x: x[2]['total_score'], reverse=True)
        
        # Accept signals with score >= threshold
        trading_signals = []
        for strategy_name, setup, score in scored_signals:
            if score['total_score'] >= TRADING_CONFIG['min_score_threshold']:
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
                logger.info(f"✅ ACCEPTED: {setup['asset']} @ {score['total_score']}")
        
        logger.info(f"Signals: {len(trading_signals)}/{len(scored_signals)}")
        
        # Send signals (skip correlation filter for now)
        for signal in trading_signals[:TRADING_CONFIG['max_signals_per_day']]:
            if not self.asset_manager.can_send_signal(signal.asset):
                continue
            
            original = next((s for s in scored_signals if s[1]['asset'] == signal.asset), None)
            if not original:
                continue
            
            _, setup, score = original
            
            try:
                # FORCE PRINT
                print("\n" + "="*50)
                print(f"🚨 SIGNAL: {signal.asset} {signal.direction.upper()}")
                print(f"Score: {score['total_score']}/100")
                print(f"Entry: {signal.entry_price}")
                print(f"Stop: {signal.stop_loss}")
                print(f"Target: {signal.target_1} / {signal.target_2}")
                print("="*50 + "\n")
                
                # Send to Telegram
                await self.telegram.send_signal(setup, score, {
                    'orderbook': market_data[signal.asset].orderbook
                })
                
                # Add to monitor
                trade = ActiveTrade(
                    asset=signal.asset,
                    direction=signal.direction,
                    entry_price=signal.entry_price,
                    stop_loss=signal.stop_loss,
                    tp1=signal.target_1,
                    tp2=signal.target_2,
                    strike=signal.strike_selection,
                    expiry=datetime.now(timezone.utc) + timedelta(hours=48),
                    position_size=self.asset_manager.calculate_position_size(
                        signal.asset, signal.entry_price, signal.stop_loss
                    )
                )
                self.trade_monitor.add_trade(trade)
                
                self.asset_manager.record_signal(signal.asset)
                logger.info(f"✅ SENT: {signal.asset}")
                
                await asyncio.sleep(2)
                
            except Exception as e:
                logger.error(f"Send failed: {e}", exc_info=True)
    
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
        self.trade_monitor.stop_monitoring()
        logger.info("Bot stopped")

# ============== ENTRY POINT ==============
if __name__ == "__main__":
    bot = AlphaBot()
    try:
        asyncio.run(bot.run())
    except KeyboardInterrupt:
        bot.stop()
        logger.info("Stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        raise
