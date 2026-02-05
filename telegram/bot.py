"""
Telegram Bot - Multi Asset with News Alerts
"""

import asyncio
import logging
from typing import Dict, Optional
from telegram import Bot, ParseMode, InlineKeyboardButton, InlineKeyboardMarkup
import matplotlib.pyplot as plt
import io
from datetime import datetime

logger = logging.getLogger(__name__)

class AlphaTelegramBot:
    
    def __init__(self, token: str, chat_id: str):
        self.bot = Bot(token=token)
        self.chat_id = chat_id
        self.last_alert_time = {}
    
    # ========== SIGNAL MESSAGES ==========
    
    async def send_signal(self, setup: Dict, score: Dict, market_data: Dict):
        """Send trading signal"""
        try:
            message = self._format_signal_message(setup, score, market_data)
            
            # Send text
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True
            )
            
            # Send chart
            chart = self._generate_chart(setup)
            if chart:
                await self.bot.send_photo(
                    chat_id=self.chat_id,
                    photo=chart,
                    caption=f"📊 {setup.get('asset')} Setup Chart"
                )
            
        except Exception as e:
            logger.error(f"Signal send error: {e}")
    
    def _format_signal_message(self, setup: Dict, score: Dict, data: Dict) -> str:
        """Format rich signal message"""
        
        asset = setup.get('asset', 'BTC')
        direction = setup.get('direction', 'long')
        
        # Emojis
        emojis = {'BTC': '₿', 'ETH': 'Ξ', 'SOL': '◎'}
        asset_emoji = emojis.get(asset, '💰')
        dir_emoji = "🟢" if direction == 'long' else "🔴"
        
        # Score stars
        total_score = score.get('total_score', 0)
        stars = "⭐" * int(total_score / 20)
        
        # Quality badge
        quality = score.get('setup_quality', 'standard')
        quality_emoji = "🥇" if quality == 'institutional_grade' else "🥈" if quality == 'professional_grade' else "🥉"
        
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
            f"├ Entry: <code>{setup.get('entry_price', 0)}</code>\n"
            f"├ Stop: <code>{setup.get('stop_loss', 0)}</code> ({self._calc_risk(setup)}%)\n"
            f"├ Target 1: <code>{setup.get('target_1', 0)}</code>\n"
            f"├ Target 2: <code>{setup.get('target_2', 0)}</code>\n"
            f"└ Position: <code>{setup.get('position_size', 0)} {asset}</code>\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"🔬 <b>RATIONALE</b>\n"
        )
        
        # Add rationale
        rationale = setup.get('rationale', {})
        for key, value in list(rationale.items())[:4]:
            display_key = key.replace('_', ' ').title()
            display_value = str(value)[:40]
            message += f"├ <i>{display_key}:</i> <code>{display_value}</code>\n"
        
        # Score breakdown
        components = score.get('component_scores', {})
        message += (
            f"\n━━━━━━━━━━━━━━━━━━━━━\n"
            f"📊 <b>SCORE BREAKDOWN</b>\n"
            f"├ Microstructure: {components.get('microstructure', 0)}/100\n"
            f"├ Greeks: {components.get('greeks', 0)}/100\n"
            f"├ Liquidity: {components.get('liquidity', 0)}/100\n"
            f"├ Momentum: {components.get('momentum', 0)}/100\n"
            f"└ Sentiment: {components.get('sentiment', 0)}/100\n"
        )
        
        # Adjustments
        time_note = score.get('time_adjustment', '')
        news_note = score.get('news_adjustment', '')
        
        if time_note or news_note:
            message += f"\n⚙️ <b>ADJUSTMENTS</b>\n"
            if time_note:
                message += f"├ {time_note}\n"
            if news_note:
                message += f"└ {news_note}\n"
        
        message += (
            f"\n⏱ <b>Valid:</b> 60 minutes\n"
            f"⚠️ <b>Risk:</b> 1% max per trade\n"
            f"<i>Alpha Bot v2.0 | {datetime.now().strftime('%H:%M')}</i>"
        )
        
        return message
    
    # ========== NEWS ALERTS ==========
    
    async def send_news_alert(self, title: str, message: str, 
                             impact: str = "medium", action: str = ""):
        """
        Send priority news alert
        impact: low, medium, high, extreme
        """
        
        try:
            # Prevent spam - max 1 alert per 5 minutes for same title
            now = datetime.now()
            last_time = self.last_alert_time.get(title)
            
            if last_time and (now - last_time).seconds < 300:
                return
            
            self.last_alert_time[title] = now
            
            # Color code by impact
            impact_emoji = {
                'low': 'ℹ️',
                'medium': '⚠️',
                'high': '🚨',
                'extreme': '⛔'
            }.get(impact, '⚠️')
            
            impact_color = {
                'low': '🟢',
                'medium': '🟡',
                'high': '🟠',
                'extreme': '🔴'
            }.get(impact, '🟡')
            
            formatted = (
                f"{impact_emoji} <b>{title}</b> {impact_color}\n\n"
                f"{message}\n\n"
            )
            
            if action:
                formatted += f"<b>🎯 ACTION:</b> {action}\n"
            
            formatted += f"\n<i>Alert time: {now.strftime('%H:%M:%S')}</i>"
            
            # Add buttons for quick actions
            keyboard = None
            if "TRADING HALTED" in title or "PAUSED" in title:
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔄 Check Status", callback_data="check_status")]
                ])
            
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=formatted,
                parse_mode=ParseMode.HTML,
                reply_markup=keyboard
            )
            
            logger.warning(f"News alert sent: {title} ({impact})")
            
        except Exception as e:
            logger.error(f"News alert error: {e}")
    
    async def send_upcoming_event_alert(self, event_name: str, event_time: str, 
                                        hours_until: int, impact: str):
        """Alert for upcoming economic event"""
        
        title = f"📅 UPCOMING: {event_name}"
        
        message = (
            f"<b>Event:</b> {event_name}\n"
            f"<b>Time:</b> {event_time}\n"
            f"<b>Countdown:</b> {hours_until} hours\n"
            f"<b>Impact:</b> {impact.upper()}"
        )
        
        action = f"Avoid trading ±2 hours of {event_name}"
        
        await self.send_news_alert(title, message, impact, action)
    
    async def send_breaking_news_alert(self, headline: str, source: str = ""):
        """Breaking news alert"""
        
        title = "🚨 BREAKING NEWS"
        
        message = headline
        if source:
            message += f"\n\n<i>Source: {source}</i>"
        
        await self.send_news_alert(title, message, "high", "Review all active trades")
    
    # ========== TRADE ALERTS ==========
    
    async def send_trade_alert(self, title: str, trade_info: Dict, 
                               priority: str = "normal"):
        """Trade-related alerts (SL approaching, TP hit, etc)"""
        
        try:
            emoji = {
                'high': '🚨',
                'medium': '⚠️',
                'normal': 'ℹ️'
            }.get(priority, 'ℹ️')
            
            message = f"{emoji} <b>{title}</b>\n\n"
            
            for key, value in trade_info.items():
                formatted_key = key.replace('_', ' ').title()
                message += f"<b>{formatted_key}:</b> {value}\n"
            
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode=ParseMode.HTML
            )
            
        except Exception as e:
            logger.error(f"Trade alert error: {e}")
    
    async def send_trade_close_alert(self, asset: str, result: str, 
                                     pnl_percent: float, duration: str):
        """Trade closure notification"""
        
        emoji = "✅" if result == "win" else "❌" if result == "loss" else "⚪"
        pnl_emoji = "🟢" if pnl_percent > 0 else "🔴"
        
        message = (
            f"{emoji} <b>TRADE CLOSED - {result.upper()}</b>\n\n"
            f"<b>Asset:</b> {asset}\n"
            f"<b>P&L:</b> {pnl_emoji} {pnl_percent:+.2f}%\n"
            f"<b>Duration:</b> {duration}\n\n"
            f"<i>{datetime.now().strftime('%H:%M:%S')}</i>"
        )
        
        await self.bot.send_message(
            chat_id=self.chat_id,
            text=message,
            parse_mode=ParseMode.HTML
        )
    
    # ========== STATUS MESSAGES ==========
    
    async def send_status(self, message: str):
        """General status update"""
        try:
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            logger.error(f"Status send error: {e}")
    
    async def send_daily_summary(self, stats: Dict):
        """Daily performance summary"""
        
        message = (
            f"📊 <b>DAILY SUMMARY</b>\n\n"
            f"<b>Date:</b> {datetime.now().strftime('%Y-%m-%d')}\n"
            f"<b>Total Signals:</b> {stats.get('total_signals', 0)}\n"
            f"<b>Wins:</b> {stats.get('wins', 0)}\n"
            f"<b>Losses:</b> {stats.get('losses', 0)}\n"
            f"<b>Win Rate:</b> {stats.get('win_rate', 0):.1f}%\n"
            f"<b>Net P&L:</b> {stats.get('net_pnl', 0):+.2f}%\n\n"
            f"<b>By Asset:</b>\n"
        )
        
        for asset, asset_stats in stats.get('by_asset', {}).items():
            message += f"├ {asset}: {asset_stats['signals']} sig, {asset_stats['pnl']:+.2f}%\n"
        
        await self.send_status(message)
    
    # ========== HELPER METHODS ==========
    
    def _calc_risk(self, setup: Dict) -> float:
        """Calculate risk percentage"""
        entry = setup.get('entry_price', 0)
        stop = setup.get('stop_loss', 0)
        if entry == 0:
            return 0
        return round(abs(entry - stop) / entry * 100, 2)
    
    def _generate_chart(self, setup: Dict) -> Optional[bytes]:
        """Generate setup chart"""
        try:
            fig, ax = plt.subplots(figsize=(10, 6))
            
            asset = setup.get('asset', 'BTC')
            current = setup.get('entry_price', 0)
            stop = setup.get('stop_loss', 0)
            t1 = setup.get('target_1', 0)
            t2 = setup.get('target_2', 0)
            
            # Mock price action
            x = list(range(20))
            y = [current * (1 + (i-10)*0.002) for i in x]
            
            ax.plot(x, y, 'b-', linewidth=2, label=f'{asset} Price')
            ax.axhline(y=current, color='blue', linestyle='--', alpha=0.7, label=f'Entry {current}')
            ax.axhline(y=stop, color='red', linestyle='--', alpha=0.7, label=f'SL {stop}')
            ax.axhline(y=t1, color='green', linestyle='--', alpha=0.7, label=f'TP1 {t1}')
            ax.axhline(y=t2, color='darkgreen', linestyle='--', alpha=0.7, label=f'TP2 {t2}')
            
            # Fill zones
            if setup.get('direction') == 'long':
                ax.fill_between(x, stop, current, alpha=0.2, color='red', label='Risk Zone')
                ax.fill_between(x, current, t2, alpha=0.2, color='green', label='Reward Zone')
            else:
                ax.fill_between(x, current, stop, alpha=0.2, color='red')
                ax.fill_between(x, t2, current, alpha=0.2, color='green')
            
            ax.set_title(
                f"{asset} {setup.get('strategy', '').replace('_', ' ').title()}", 
                fontsize=14, 
                fontweight='bold'
            )
            ax.legend(loc='upper left', fontsize=8)
            ax.grid(True, alpha=0.3)
            
            # Save
            buf = io.BytesIO()
            plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
            buf.seek(0)
            plt.close()
            
            return buf
            
        except Exception as e:
            logger.error(f"Chart error: {e}")
            return None
