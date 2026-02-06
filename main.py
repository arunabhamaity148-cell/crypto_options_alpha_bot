"""
Crypto Options Alpha Bot - Main Entry Point
Fixed: telegram -> tg_bot folder, ParseMode removed (use string literals)
"""

import os
import sys
import asyncio
import logging
import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass
from threading import Thread

# Flask for Railway
from flask import Flask, jsonify

# Telegram (python-telegram-bot library) - FIXED: No ParseMode import
from telegram import Bot

# Local imports - using tg_bot (renamed from telegram)
from config.settings import (
    PORT, 
    TELEGRAM_TOKEN, 
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

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# ============== FLASK APP ==============
flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    """Root endpoint"""
    return {
        'status': 'running',
        'bot': 'Crypto Options Alpha Bot',
        'version': '2.0',
        'timestamp': datetime.now().isoformat()
    }

@flask_app.route('/health')
def health():
    """Health check for Railway"""
    return {'status': 'healthy'}, 200

@flask_app.route('/api/status')
def api_status():
    """Detailed status API"""
    return {
        'status': 'running',
        'version': '2.0',
        'timestamp': datetime.now().isoformat(),
        'assets': list(ASSETS_CONFIG.keys()),
        'config': {
            'min_score': TRADING_CONFIG['min_score_threshold'],
            'max_signals_per_day': TRADING_CONFIG['max_signals_per_day']
        }
    }

# ============== MAIN BOT CLASS ==============
class AlphaBot:
    def __init__(self):
        self.telegram = AlphaTelegramBot(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID)
        self.stealth = StealthRequest(STEALTH_CONFIG)
        self.data_agg = DataAggregator(self.stealth)
        self.asset_manager = MultiAssetManager(TRADING_CONFIG, ASSETS_CONFIG)
        self.time_filter = TimeFilter()
        self.running = False
        self.cycle_count = 0
        self.ws_connected = False
        
    async def run(self):
        """Main bot loop"""
        self.running = True
        logger.info("🚀 Alpha Bot v2.0 Started!")
        logger.info(f"Active assets: {self.asset_manager.active_assets}")
        
        # Send startup message
        try:
            await self.telegram.send_status(
                "🟢 <b>Bot Started v2.0</b>\n\n"
                f"<b>Assets:</b> {', '.join(TRADING_CONFIG['assets'])}\n"
                f"<b>Min Score:</b> {TRADING_CONFIG['min_score_threshold']}\n"
                f"<b>Max Signals:</b> {TRADING_CONFIG['max_signals_per_day']}/day\n\n"
                f"<i>Monitoring started at {datetime.now().strftime('%H:%M:%S')}</i>"
            )
        except Exception as e:
            logger.error(f"Failed to send startup message: {e}")
        
        # Start Flask in background thread
        flask_thread = Thread(target=self._run_flask, daemon=True)
        flask_thread.start()
        logger.info(f"Flask server started on port {PORT}")
        
        # Main loop
        while self.running:
            try:
                self.cycle_count += 1
                logger.info(f"=== Cycle {self.cycle_count} ===")
                
                # Check daily reset
                if self.asset_manager.should_reset_daily():
                    self.asset_manager.reset_daily_counters()
                    await self.telegram.send_status("🌅 <b>Daily counters reset</b>")
                
                # Check news guard
                trading_allowed, news_reason = await news_guard.check_trading_allowed()
                if not trading_allowed:
                    logger.warning(f"🛑 Trading halted: {news_reason}")
                    await self.telegram.send_status(f"⏸️ <b>TRADING HALTED</b>\n\n{news_reason}")
                    await asyncio.sleep(300)
                    continue
                
                if "caution" in news_reason.lower():
                    logger.warning(f"⚠️ Caution: {news_reason}")
                
                # Fetch market data for all assets
                logger.info("Fetching market data...")
                market_data = await self.data_agg.get_all_assets_data(ASSETS_CONFIG)
                logger.info(f"✅ Fetched data for {len(market_data)} assets")
                
                # Generate and process signals
                if market_data:
                    await self._process_market_data(market_data)
                
                # Sleep between cycles
                logger.info(f"Sleeping 60 seconds... (Cycle {self.cycle_count} complete)")
                await asyncio.sleep(60)
                
            except Exception as e:
                logger.error(f"❌ Error in main loop: {e}", exc_info=True)
                await asyncio.sleep(60)
    
    async def _process_market_data(self, market_data: Dict[str, AssetData]):
        """Process market data and generate signals"""
        from strategies.liquidity_hunt import LiquidityHuntStrategy
        from strategies.gamma_squeeze import GammaSqueezeStrategy
        from indicators.greeks_engine import GreeksEngine
        from signals.scorer import AlphaScorer
        
        signals = []
        
        for asset, data in market_data.items():
            logger.info(f"Analyzing {asset}...")
            
            # Check if we can send signal for this asset
            if not self.asset_manager.can_send_signal(asset):
                logger.info(f"⏭️ {asset}: Daily limit reached")
                continue
            
            # Check time filter
            mock_setup = {'confidence': 90}
            time_ok, time_reason = self.time_filter.should_process_signal(asset, mock_setup)
            
            if not time_ok:
                logger.info(f"⏭️ {asset}: {time_reason}")
                continue
            
            config = ASSETS_CONFIG[asset]
            recent_trades = ws_manager.get_price_data(config['symbol']).get('trades', [])
            
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
                    logger.info(f"🎯 {asset}: Liquidity Hunt signal found (score: {lh_setup.get('confidence', 0)})")
                    
            except Exception as e:
                logger.error(f"Liquidity Hunt error for {asset}: {e}")
            
            # Strategy 2: Gamma Squeeze
            try:
                greeks = GreeksEngine()
                gs_strategy = GammaSqueezeStrategy(asset, config, greeks)
                
                options_chain = []
                gs_setup = await gs_strategy.analyze(
                    {'orderbook': data.orderbook},
                    options_chain
                )
                
                if gs_setup:
                    gs_setup['asset'] = asset
                    signals.append(('gamma_squeeze', gs_setup))
                    logger.info(f"🎯 {asset}: Gamma Squeeze signal found (score: {gs_setup.get('confidence', 0)})")
                    
            except Exception as e:
                logger.error(f"Gamma Squeeze error for {asset}: {e}")
        
        # Score and filter signals
        if signals:
            await self._score_and_send_signals(signals, market_data)
    
    async def _score_and_send_signals(self, signals: List[tuple], market_data: Dict):
        """Score signals and send to Telegram"""
        from signals.scorer import AlphaScorer
        
        scored_signals = []
        scorer = AlphaScorer(TRADING_CONFIG)
        
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
            
            logger.info(f"📊 {asset} {strategy_name}: Score {score['total_score']}/100 "
                       f"(Confidence: {score['confidence']})")
        
        # Sort by score
        scored_signals.sort(key=lambda x: x[2]['total_score'], reverse=True)
        
        # Convert to TradingSignal objects and filter correlations
        trading_signals = []
        for strategy_name, setup, score in scored_signals:
            if score['recommendation'] in ['take', 'strong_take']:
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
                    timestamp=datetime.now()
                )
                trading_signals.append(signal)
        
        # Filter correlated signals
        filtered_signals = self.asset_manager.filter_correlated_signals(trading_signals)
        
        # Send top signals
        for signal in filtered_signals[:TRADING_CONFIG['max_signals_per_day']]:
            if not self.asset_manager.can_send_signal(signal.asset):
                continue
            
            original = next((s for s in scored_signals if s[1]['asset'] == signal.asset), None)
            if not original:
                continue
            
            _, setup, score = original
            
            try:
                await self.telegram.send_signal(setup, score, {
                    'orderbook': market_data[signal.asset].orderbook
                })
                
                self.asset_manager.record_signal(signal.asset)
                logger.info(f"✅ Signal sent: {signal.asset} @ {score['total_score']}")
                
                await asyncio.sleep(2)
                
            except Exception as e:
                logger.error(f"Failed to send signal for {signal.asset}: {e}")
    
    def _run_flask(self):
        """Run Flask server in background"""
        try:
            flask_app.run(
                host='0.0.0.0',
                port=PORT,
                threaded=True,
                debug=False,
                use_reloader=False
            )
        except Exception as e:
            logger.error(f"Flask server error: {e}")
    
    def stop(self):
        """Stop the bot"""
        self.running = False
        ws_manager.stop()
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
