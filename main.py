"""
Crypto Options Alpha Bot - Main Entry Point
Fixed: ParseMode removed, imports corrected
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

# Telegram - FIXED: Only Bot, no ParseMode
from telegram import Bot

# Local imports
from config.settings import (
    PORT, 
    TELEGRAM_TOKEN,        # This matches settings.py
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
    return {
        'status': 'running',
        'bot': 'Crypto Options Alpha Bot',
        'version': '2.0',
        'timestamp': datetime.now().isoformat()
    }

@flask_app.route('/health')
def health():
    return {'status': 'healthy'}, 200

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
        
    async def run(self):
        self.running = True
        logger.info("🚀 Alpha Bot v2.0 Started!")
        
        # Start Flask
        flask_thread = Thread(target=self._run_flask, daemon=True)
        flask_thread.start()
        
        # Main loop
        while self.running:
            try:
                self.cycle_count += 1
                logger.info(f"Cycle {self.cycle_count}")
                
                await asyncio.sleep(60)
                
            except Exception as e:
                logger.error(f"Error: {e}")
                await asyncio.sleep(60)
    
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

# ============== ENTRY POINT ==============
if __name__ == "__main__":
    bot = AlphaBot()
    try:
        asyncio.run(bot.run())
    except KeyboardInterrupt:
        bot.stop()
