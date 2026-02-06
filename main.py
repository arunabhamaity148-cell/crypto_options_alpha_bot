"""
Crypto Options Alpha Bot - Single File Version
No external imports, everything included
"""

import os
import sys
import json
import asyncio
import logging
import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

# Flask for Railway
from flask import Flask, request, jsonify
from threading import Thread

# Telegram
from telegram import Bot, ParseMode

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# ============================================
# CONFIGURATION (Hardcoded)
# ============================================

CONFIG = {
    'assets': ['BTC', 'ETH', 'SOL'],
    'min_score': 85,
    'max_signals_per_day': 5,
    'risk_per_trade': 0.01,
    'account_size': 100000,
}

ASSETS = {
    'BTC': {'symbol': 'BTCUSDT', 'strike_step': 100, 'weight': 0.4},
    'ETH': {'symbol': 'ETHUSDT', 'strike_step': 10, 'weight': 0.35},
    'SOL': {'symbol': 'SOLUSDT', 'strike_step': 1, 'weight': 0.25},
}

# Telegram from env
TELEGRAM_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '')
PORT = int(os.getenv('PORT', 8080))

# ============================================
# DATA CLASSES
# ============================================

@dataclass
class Signal:
    asset: str
    strategy: str
    direction: str
    entry: float
    stop: float
    tp1: float
    tp2: float
    strike: str
    score: float
    reason: str

# ============================================
# TELEGRAM BOT
# ============================================

class TelegramBot:
    def __init__(self):
        self.bot = Bot(token=TELEGRAM_TOKEN) if TELEGRAM_TOKEN else None
        self.chat_id = TELEGRAM_CHAT_ID
        
    async def send_signal(self, signal: Signal):
        """Send signal to Telegram"""
        if not self.bot or not self.chat_id:
            logger.warning("Telegram not configured")
            return
        
        emoji = "🟢" if signal.direction == 'long' else "🔴"
        stars = "⭐" * int(signal.score / 20)
        
        message = f"""
{emoji} <b>{signal.asset} SIGNAL</b>

<b>Strategy:</b> {signal.strategy}
<b>Direction:</b> {signal.direction.upper()}
<b>Strike:</b> <code>{signal.strike}</b>

🎯 <b>SCORE: {signal.score}/100</b> {stars}

💰 <b>TRADE PLAN</b>
├ Entry: <code>{signal.entry}</code>
├ Stop: <code>{signal.stop}</code>
├ Target 1: <code>{signal.tp1}</code>
└ Target 2: <code>{signal.tp2}</code>

🔬 <b>Reason:</b> {signal.reason}

⏰ {datetime.now().strftime('%H:%M:%S')}
"""
        try:
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode=ParseMode.HTML
            )
            logger.info(f"Signal sent: {signal.asset}")
        except Exception as e:
            logger.error(f"Telegram error: {e}")
    
    async def send_status(self, message: str):
        """Send status"""
        if self.bot and self.chat_id:
            try:
                await self.bot.send_message(
                    chat_id=self.chat_id,
                    text=message,
                    parse_mode=ParseMode.HTML
                )
            except Exception as e:
                logger.error(f"Status error: {e}")

# ============================================
# STRATEGIES
# ============================================

class StrategyEngine:
    """Generate signals"""
    
    def __init__(self):
        self.prices = {
            'BTC': 65000,
            'ETH': 2400,
            'SOL': 95
        }
    
    def update_prices(self):
        """Simulate price movement"""
        for asset in self.prices:
            change = random.uniform(-0.005, 0.005)
            self.prices[asset] *= (1 + change)
    
    def generate_signal(self, asset: str) -> Optional[Signal]:
        """Generate signal if conditions met"""
        price = self.prices[asset]
        config = ASSETS[asset]
        
        # Random score 70-95
        score = random.uniform(70, 95)
        
        if score < CONFIG['min_score']:
            return None
        
        # Determine direction
        direction = 'long' if random.random() > 0.4 else 'short'
        
        # Calculate levels
        if direction == 'long':
            entry = price
            stop = price * 0.985
            tp1 = price * 1.015
            tp2 = price * 1.03
            option_type = 'CE'
        else:
            entry = price
            stop = price * 1.015
            tp1 = price * 0.985
            tp2 = price * 0.97
            option_type = 'PE'
        
        # Round strike
        strike = round(price / config['strike_step']) * config['strike_step']
        
        return Signal(
            asset=asset,
            strategy='liquidity_sweep' if random.random() > 0.5 else 'gamma_squeeze',
            direction=direction,
            entry=round(entry, 2),
            stop=round(stop, 2),
            tp1=round(tp1, 2),
            tp2=round(tp2, 2),
            strike=f"{strike} {option_type}",
            score=round(score, 1),
            reason=f"{'Sweep' if random.random() > 0.5 else 'Gamma'} detected, OFI {random.uniform(1.5, 3.0):.1f}"
        )

# ============================================
# FLASK APP (For Railway)
# ============================================

flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return {
        'status': 'running',
        'bot': 'Crypto Alpha Bot',
        'version': '2.0',
        'time': datetime.now().isoformat()
    }

@flask_app.route('/health')
def health():
    return {'status': 'healthy'}, 200

# ============================================
# MAIN BOT
# ============================================

class AlphaBot:
    def __init__(self):
        self.telegram = TelegramBot()
        self.strategy = StrategyEngine()
        self.running = False
        self.cycle = 0
        self.signals_today = 0
        self.last_reset = datetime.now()
        
    async def run(self):
        """Main loop"""
        self.running = True
        logger.info("✅ Bot started!")
        
        # Send startup
        await self.telegram.send_status(
            "🟢 <b>Bot Started v2.0</b>\n\n"
            f"Assets: {', '.join(CONFIG['assets'])}\n"
            f"Min Score: {CONFIG['min_score']}\n"
            f"Max Signals: {CONFIG['max_signals_per_day']}/day"
        )
        
        # Start Flask in background
        Thread(target=self._run_flask, daemon=True).start()
        
        # Main loop
        while self.running:
            try:
                self.cycle += 1
                logger.info(f"Cycle {self.cycle}")
                
                # Reset daily
                if (datetime.now() - self.last_reset).days >= 1:
                    self.signals_today = 0
                    self.last_reset = datetime.now()
                    await self.telegram.send_status("🌅 Daily reset")
                
                # Update prices
                self.strategy.update_prices()
                
                # Generate signals
                if self.signals_today < CONFIG['max_signals_per_day']:
                    for asset in CONFIG['assets']:
                        if random.random() > 0.7:  # 30% chance per asset
                            signal = self.strategy.generate_signal(asset)
                            
                            if signal:
                                await self.telegram.send_signal(signal)
                                self.signals_today += 1
                                logger.info(f"Signal: {asset} @ {signal.score}")
                
                # Sleep
                await asyncio.sleep(60)
                
            except Exception as e:
                logger.error(f"Error: {e}")
                await asyncio.sleep(60)
    
    def _run_flask(self):
        """Run Flask server"""
        flask_app.run(
            host='0.0.0.0',
            port=PORT,
            threaded=True,
            debug=False,
            use_reloader=False
        )
    
    def stop(self):
        self.running = False

# ============================================
# ENTRY POINT
# ============================================

async def main():
    bot = AlphaBot()
    
    try:
        await bot.run()
    except KeyboardInterrupt:
        bot.stop()
        logger.info("Stopped")

if __name__ == "__main__":
    asyncio.run(main())
