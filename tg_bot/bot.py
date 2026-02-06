"""
Telegram Bot - Fixed with Position Size Display
"""

import asyncio
import logging
from typing import Dict, Optional
from datetime import datetime, timezone

from telegram import Bot

logger = logging.getLogger(__name__)

class AlphaTelegramBot:
    def __init__(self, token: str, chat_id: str):
        self.bot = Bot(token=token) if token else None
        self.chat_id = chat_id
        self.last_alert_time = {}
    
    async def send_signal(self, setup: Dict, score: Dict, market_data: Dict):
        """Send trading signal with position size"""
        try:
            message = self._format_signal_message(setup, score, market_data)
            
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode='HTML',
                disable_web_page_preview=True
            )
            
        except Exception as e:
            logger.error(f"Signal send error: {e}")
    
    def _format_signal_message(self, setup: Dict, score: Dict, data: Dict) -> str:
        """Format rich signal message with position size"""
        asset = setup.get('asset', 'BTC')
        direction = setup.get('direction', 'long')
        
        emojis = {'BTC': '₿', 'ETH': 'Ξ', 'SOL': '◎'}
        asset_emoji = emojis.get(asset, '💰')
        dir_emoji = "🟢" if direction == 'long' else "🔴"
        
        total_score = score.get('total_score', 0)
        stars = "⭐" * int(total_score / 20)
        
        quality = score.get('setup_quality', 'standard')
        quality_emoji = {
            'institutional_grade': '🏆',
            'professional_grade': '🥇',
            'standard': '🥈',
            'below_standard': '🥉'
        }.get(quality, '🥉')
        
        current_time = datetime.now(timezone.utc).strftime('%H:%M')
        
        # Get position size
        position_size = setup.get('position_size', data.get('position_size', 'N/A'))
        if isinstance(position_size, (int, float)):
            position_str = f"{position_size:.3f}" if asset == 'BTC' else f"{position_size:.2f}"
        else:
            position_str = str(position_size)
        
        message = (
            f"{dir_emoji} <b>{asset} ALPHA SIGNAL</b> {asset_emoji}\n\n"
            f"<b>Strategy:</b> <code>{setup.get('strategy', '').replace('_', ' ').title()}</code>\n"
            f"<b>Direction:</b> {direction.upper()}\n"
            f"<b>Strike:</b> <code>{setup.get('strike_selection', 'ATM')}</code>\n"
            f"<b>Expiry:</b> {setup.get('expiry_suggestion', '48h')}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"🎯 <b>ALPHA SCORE: {total_score}/100</b> {stars}\n"
            f"{quality_emoji} <b>Quality:</b> {quality.replace('_', ' ').title()}\n"
            f"<b>Verdict:</b> {score.get('recommendation', 'pass').upper()}\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"💰 <b>TRADE PLAN</b>\n"
            f"├ Entry: <code>{setup.get('entry_price', 0):,.2f}</code>\n"
            f"├ Stop: <code>{setup.get('stop_loss', 0):,.2f}</code>\n"
            f"├ Target 1: <code>{setup.get('target_1', 0):,.2f}</code>\n"
            f"├ Target 2: <code>{setup.get('target_2', 0):,.2f}</code>\n"
            f"└ Position: <code>{position_str} contracts</code>\n\n"
        )
        
        rationale = setup.get('rationale', {})
        if rationale:
            message += f"🔬 <b>Key Factors:</b>\n"
            for key, value in list(rationale.items())[:3]:
                display_key = key.replace('_', ' ').title()
                if isinstance(value, float):
                    display_val = f"{value:.4f}" if abs(value) < 1 else f"{value:.2f}"
                else:
                    display_val = str(value)[:30]
                message += f"├ <i>{display_key}:</i> <code>{display_val}</code>\n"
        
        components = score.get('component_scores', {})
        if components:
            message += f"\n📊 <b>Components:</b>\n"
            for comp, val in components.items():
                message += f"├ {comp.title()}: {val}/100\n"
        
        message += (
            f"\n⏱ <b>Valid:</b> 60 minutes\n"
            f"⚠️ <b>Risk:</b> 1% max per trade\n"
            f"<i>Alpha Bot v2.2 | {current_time} UTC</i>"
        )
        
        return message
    
    async def send_news_alert(self, title: str, message: str, impact: str = "medium", action: str = ""):
        """Send priority news alert"""
        try:
            now = datetime.now(timezone.utc)
            last_time = self.last_alert_time.get(title)
            
            if last_time and (now - last_time).seconds < 300:
                return
            
            self.last_alert_time[title] = now
            
            impact_emoji = {
                'low': 'ℹ️',
                'medium': '⚠️',
                'high': '🚨',
                'extreme': '⛔'
            }.get(impact, '⚠️')
            
            formatted = (
                f"{impact_emoji} <b>{title}</b>\n\n"
                f"{message}\n\n"
            )
            
            if action:
                formatted += f"<b>🎯 ACTION:</b> {action}\n"
            
            formatted += f"\n<i>{now.strftime('%H:%M:%S')} UTC</i>"
            
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=formatted,
                parse_mode='HTML'
            )
            
            logger.warning(f"News alert sent: {title} ({impact})")
            
        except Exception as e:
            logger.error(f"News alert error: {e}")
    
    async def send_status(self, message: str):
        """Send general status update"""
        try:
            if not self.bot or not self.chat_id:
                logger.warning(f"MOCK TELEGRAM: {message}")
                return
                
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode='HTML'
            )
        except Exception as e:
            logger.error(f"Status send error: {e}")
    
    async def send_trade_close_alert(self, asset: str, result: str, pnl_percent: float, duration: str = ""):
        """Send trade closure notification"""
        emoji = "✅" if result == "win" else "❌" if result == "loss" else "⚪"
        pnl_emoji = "🟢" if pnl_percent > 0 else "🔴"
        
        current_time = datetime.now(timezone.utc).strftime('%H:%M:%S')
        
        msg = (
            f"{emoji} <b>TRADE CLOSED - {result.upper()}</b>\n\n"
            f"<b>Asset:</b> {asset}\n"
            f"<b>P&L:</b> {pnl_emoji} {pnl_percent:+.2f}%\n"
        )
        
        if duration:
            msg += f"<b>Duration:</b> {duration}\n"
        
        msg += f"\n<i>{current_time} UTC</i>"
        
        try:
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=msg,
                parse_mode='HTML'
            )
        except Exception as e:
            logger.error(f"Trade close alert error: {e}")
