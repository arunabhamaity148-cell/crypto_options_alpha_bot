"""
Telegram Bot
"""

import asyncio
import logging
from typing import Dict, Optional
from datetime import datetime

try:
    from telegram import Bot, ParseMode
except ImportError:
    logging.error("python-telegram-bot not installed")
    raise

logger = logging.getLogger(__name__)

class AlphaTelegramBot:
    def __init__(self, token: str, chat_id: str):
        self.bot = Bot(token=token) if token else None
        self.chat_id = chat_id
        self.last_alert_time = {}
    
    async def send_signal(self, setup: Dict, score: Dict, market_data: Dict):
        try:
            message = self._format_signal_message(setup, score, market_data)
            
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True
            )
            
        except Exception as e:
            logger.error(f"Signal send error: {e}")
    
    def _format_signal_message(self, setup: Dict, score: Dict, data: Dict) -> str:
        asset = setup.get('asset', 'BTC')
        direction = setup.get('direction', 'long')
        
        emojis = {'BTC': '₿', 'ETH': 'Ξ', 'SOL': '◎'}
        asset_emoji = emojis.get(asset, '💰')
        dir_emoji = "🟢" if direction == 'long' else "🔴"
        
        total_score = score.get('total_score', 0)
        stars = "⭐" * int(total_score / 20)
        
        message = (
            f"{dir_emoji} <b>{asset} ALPHA SIGNAL</b> {asset_emoji}\n\n"
            f"<b>Strategy:</b> <code>{setup.get('strategy', '').replace('_', ' ').title()}</code>\n"
            f"<b>Direction:</b> {direction.upper()}\n"
            f"<b>Strike:</b> <code>{setup.get('strike_selection', 'ATM')}</code>\n"
            f"<b>Expiry:</b> {setup.get('expiry_suggestion', '48h')}\n\n"
            f"🎯 <b>ALPHA SCORE: {total_score}/100</b> {stars}\n\n"
            f"💰 <b>TRADE PLAN</b>\n"
            f"├ Entry: <code>{setup.get('entry_price', 0)}</code>\n"
            f"├ Stop: <code>{setup.get('stop_loss', 0)}</code>\n"
            f"├ Target 1: <code>{setup.get('target_1', 0)}</code>\n"
            f"├ Target 2: <code>{setup.get('target_2', 0)}</code>\n\n"
            f"⏱ <b>Valid:</b> 60 minutes\n"
            f"⚠️ <b>Risk:</b> 1% max per trade\n"
            f"<i>{datetime.now().strftime('%H:%M')}</i>"
        )
        
        return message
    
    async def send_news_alert(self, title: str, message: str, impact: str = "medium"):
        try:
            now = datetime.now()
            last_time = self.last_alert_time.get(title)
            
            if last_time and (now - last_time).seconds < 300:
                return
            
            self.last_alert_time[title] = now
            
            formatted = f"🚨 <b>{title}</b>\n\n{message}\n\n<i>{now.strftime('%H:%M:%S')}</i>"
            
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=formatted,
                parse_mode=ParseMode.HTML
            )
            
        except Exception as e:
            logger.error(f"News alert error: {e}")
    
    async def send_status(self, message: str):
        try:
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            logger.error(f"Status send error: {e}")
    
    async def send_trade_close_alert(self, asset: str, result: str, pnl_percent: float):
        emoji = "✅" if result == "win" else "❌"
        
        message = (
            f"{emoji} <b>TRADE CLOSED - {result.upper()}</b>\n\n"
            f"<b>Asset:</b> {asset}\n"
            f"<b>P&L:</b> {pnl_percent:+.2f}%\n\n"
            f"<i>{datetime.now().strftime('%H:%M:%S')}</i>"
        )
        
        await self.bot.send_message(
            chat_id=self.chat_id,
            text=message,
            parse_mode=ParseMode.HTML
        )
