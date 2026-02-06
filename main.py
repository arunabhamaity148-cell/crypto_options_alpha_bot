"""
Crypto Options Alpha Bot - Main Entry Point
"""

import os
import sys
import asyncio
import logging
from datetime import datetime
from threading import Thread

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Flask
from flask import Flask, jsonify

# Telegram
try:
    from telegram import Bot, ParseMode
except ImportError as e:
    print(f"ERROR: {e}")
    print("Run: pip install python-telegram-bot==20.7")
    sys.exit(1)

# Local imports
from config.settings import PORT, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, ASSETS_CONFIG, TRADING_CONFIG, STEALTH_CONFIG
from core.websocket_manager import ws_manager
from core.stealth_request import StealthRequest
from core.data_aggregator import DataAggregator
from core.multi_asset_manager import MultiAssetManager
from core.time_filter import TimeFilter
from core.news_guard import news_guard
from telegram.bot import AlphaTelegramBot

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Flask app
flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return {
        'status': 'running',
        'bot': 'Crypto Options Alpha Bot',
        'version': '2.0',
        'timestamp': datetime.now().isoformat()
    }

@flask_app.route('/health')
def health():
    return {'status': 'healthy'}, 200

class AlphaBot:
    def __init__(self):
        self.telegram = AlphaTelegramBot(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID)
        self.stealth = StealthRequest(STEALTH_CONFIG)
        self.data_agg = DataAggregator(self.stealth)
        self.asset_manager = MultiAssetManager(TRADING_CONFIG, ASSETS_CONFIG)
        self.time_filter = TimeFilter()
        self.running = False
        self.cycle_count = 0
        
    async def run(self):
        self.running = True
        logger.info("✅ Alpha Bot v2.0 Started!")
        
        # Send startup message
        await self.telegram.send_status(
            "🟢 <b>Bot Started v2.0</b>\n\n"
            f"Assets: {', '.join(TRADING_CONFIG['assets'])}\n"
            f"Min Score: {TRADING_CONFIG['min_score_threshold']}\n"
            f"Max Signals: {TRADING_CONFIG['max_signals_per_day']}/day"
        )
        
        # Start Flask in background
        Thread(target=self._run_flask, daemon=True).start()
        
        # Main loop
        while self.running:
            try:
                self.cycle_count += 1
                logger.info(f"Cycle {self.cycle_count}")
                
                # Check daily reset
                if self.asset_manager.should_reset_daily():
                    self.asset_manager.reset_daily_counters()
                
                # Check news guard
                trading_allowed, news_reason = await news_guard.check_trading_allowed()
                if not trading_allowed:
                    logger.warning(f"Trading halted: {news_reason}")
                    await self.telegram.send_status(f"⏸️ TRADING HALTED\n\n{news_reason}")
                    await asyncio.sleep(300)
                    continue
                
                # Fetch data for all assets
                market_data = await self.data_agg.get_all_assets_data(ASSETS_CONFIG)
                logger.info(f"Fetched data for {len(market_data)} assets")
                
                # Generate signals (simplified for now)
                await self._generate_signals(market_data)
                
                await asyncio.sleep(60)  # 1 minute between cycles
                
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                await asyncio.sleep(60)
    
    async def _generate_signals(self, market_data: Dict):
        """Generate trading signals"""
        from strategies.liquidity_hunt import LiquidityHuntStrategy
        
        for asset, data in market_data.items():
            if not self.asset_manager.can_send_signal(asset):
                continue
            
            # Check time filter
            time_ok, time_reason = self.time_filter.should_process_signal(
                asset, {'confidence': 90}  # Mock setup
            )
            
            if not time_ok:
                logger.info(f"Skipping {asset}: {time_reason}")
                continue
            
            # Run strategy
            config = ASSETS_CONFIG[asset]
            strategy = LiquidityHuntStrategy(asset, config)
            
            recent_trades = []  # Would come from WebSocket
            
            try:
                setup = await strategy.analyze({'orderbook': data.orderbook}, recent_trades)
                
                if setup:
                    # Calculate score
                    from signals.scorer import AlphaScorer
                    scorer = AlphaScorer(TRADING_CONFIG)
                    score = scorer.calculate_score(setup, {'orderbook': data.orderbook})
                    
                    if score['recommendation'] in ['take', 'strong_take']:
                        # Send signal
                        await self.telegram.send_signal(setup, score, {'orderbook': data.orderbook})
                        self.asset_manager.record_signal(asset)
                        logger.info(f"Signal sent: {asset} @ {score['total_score']}")
                        
            except Exception as e:
                logger.error(f"Strategy error for {asset}: {e}")
    
    def _run_flask(self):
        """Run Flask server"""
        flask_app.run(
            host='0.0.0.0',
            port=PORT,
            threaded=True,
            debug=False,
            use_reloader=False
        )
        logger.info(f"Flask server started on port {PORT}")
    
    def stop(self):
        self.running = False
        ws_manager.stop()
        logger.info("Bot stopped")

if __name__ == "__main__":
    bot = AlphaBot()
    try:
        asyncio.run(bot.run())
    except KeyboardInterrupt:
        bot.stop()
        logger.info("Stopped by user")
