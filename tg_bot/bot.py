"""
Telegram Bot with Premium Style - Ultra Luxury Edition
"""

import asyncio
import logging
from typing import Dict, Optional
from datetime import datetime, timezone

from telegram import Bot

logger = logging.getLogger(__name__)

class AlphaTelegramBot:
    # Premium emoji sets
    ASSET_EMOJIS = {
        'BTC': '₿',
        'ETH': 'Ξ',
        'SOL': '◎'
    }
    
    DIRECTION_EMOJIS = {
        'long': '🟢',
        'short': '🔴',
        'buy': '💚',
        'sell': '❤️'
    }
    
    QUALITY_EMOJIS = {
        'institutional_grade': '👑',
        'professional_grade': '💎',
        'standard': '🏅',
        'below_standard': '⚪'
    }
    
    COMPONENT_EMOJIS = {
        'microstructure': '📊',
        'greeks': '🔮',
        'liquidity': '💧',
        'momentum': '🚀',
        'sentiment': '🧠'
    }
    
    STATUS_EMOJIS = {
        'success': '✅',
        'warning': '⚠️',
        'error': '❌',
        'info': 'ℹ️',
        'profit': '💰',
        'loss': '📉',
        'neutral': '➖'
    }
    
    def __init__(self, token: str, chat_id: str):
        self.bot = Bot(token=token) if token else None
        self.chat_id = chat_id
        self.last_alert_time: Dict[str, datetime] = {}
        self.min_alert_interval = 60
    
    async def send_signal(self, setup: Dict, score: Dict, market_data: Dict):
        """Send premium trading signal"""
        try:
            message = self._format_premium_signal(setup, score, market_data)
            
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode='HTML',
                disable_web_page_preview=True
            )
            
        except Exception as e:
            logger.error(f"Signal send error: {e}")
    
    def _format_premium_signal(self, setup: Dict, score: Dict, data: Dict) -> str:
        """Ultra premium signal formatting"""
        asset = setup.get('asset', 'BTC')
        direction = setup.get('direction', 'long')
        
        # Core emojis
        asset_emoji = self.ASSET_EMOJIS.get(asset, '💎')
        dir_emoji = self.DIRECTION_EMOJIS.get(direction, '⚪')
        quality = score.get('setup_quality', 'standard')
        quality_emoji = self.QUALITY_EMOJIS.get(quality, '🏅')
        
        # Score visualization
        total_score = score.get('total_score', 0)
        score_bars = self._score_bars(total_score)
        stars = "★" * int(total_score / 20) + "☆" * (5 - int(total_score / 20))
        
        # Time
        current_time = datetime.now(timezone.utc).strftime('%H:%M UTC')
        
        # Position sizing
        position_size = setup.get('position_size', data.get('position_size', 'N/A'))
        if isinstance(position_size, (int, float)):
            pos_str = f"{position_size:.4f}" if asset == 'BTC' else f"{position_size:.3f}"
        else:
            pos_str = str(position_size)
        
        # Options data section
        options_section = self._format_options_section(setup, data)
        
        # Rationale
        rationale_section = self._format_rationale(setup)
        
        # Components
        components_section = self._format_components(score)
        
        # Regime & MTF info
        regime_info = ""
        if setup.get('regime'):
            regime_info = f"\n📍 <b>Market Regime:</b> <code>{setup['regime'].replace('_', ' ').title()}</code>"
        if setup.get('mtf_score'):
            regime_info += f"\n🎯 <b>MTF Score:</b> <code>{setup['mtf_score']:.0f}/100</code>"
        
        # Build message
        message = f"""╔══════════════════════════════════════╗
║  {dir_emoji}  <b>{asset} ALPHA SIGNAL</b>  {asset_emoji}  ║
╚══════════════════════════════════════╝

<b>━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━</b>
{quality_emoji} <b>Strategy:</b> <code>{setup.get('strategy', '').replace('_', ' ').title()}</code>
📌 <b>Direction:</b> <code>{direction.upper()}</code>
🎯 <b>Strike:</b> <code>{setup.get('strike_selection', 'ATM')}</code>
⏳ <b>Expiry:</b> <code>{setup.get('expiry_suggestion', '48h')}</code>{regime_info}
<b>━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━</b>

{score_bars}
<b>🎯 ALPHA SCORE: {total_score}/100</b>
<code>{stars}</code>
<b>{quality_emoji} Quality:</b> <code>{quality.replace('_', ' ').title()}</code>
<b>📋 Verdict:</b> <code>{score.get('recommendation', 'PASS').upper()}</code>

<b>💰 TRADE CONFIGURATION</b>
<b>┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓</b>
<b>┃</b> 🚪 Entry:     <code>{setup.get('entry_price', 0):>12,.2f}</code> <b>┃</b>
<b>┃</b> 🛡️  Stop:      <code>{setup.get('stop_loss', 0):>12,.2f}</code> <b>┃</b>
<b>┃</b> 🎯 Target 1:  <code>{setup.get('target_1', 0):>12,.2f}</code> <b>┃</b>
<b>┃</b> 🏆 Target 2:  <code>{setup.get('target_2', 0):>12,.2f}</code> <b>┃</b>
<b>┃</b> 📦 Size:      <code>{pos_str:>12}</code> <b>┃</b>
<b>┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛</b>{options_section}{rationale_section}{components_section}

<b>⚡ EXECUTION</b>
<code>Entry ▶ SL ▶ BE ▶ TP1(50%) ▶ Trail ▶ TP2</code>

<b>⏱️ Valid Until:</b> <code>{(datetime.now(timezone.utc) + timedelta(minutes=60)).strftime('%H:%M UTC')}</code>
<b>⚠️ Risk:</b> <code>Max 1% per trade</code>

<code>══════════════════════════════════</code>
<i>🤖 Alpha Bot v3.4 Premium | {current_time}</i>
<code>══════════════════════════════════</code>"""
        
        return message
    
    def _score_bars(self, score: float) -> str:
        """Visual score bar"""
        filled = int(score / 5)
        empty = 20 - filled
        bar = "█" * filled + "░" * empty
        color = "🟢" if score >= 85 else "🟡" if score >= 75 else "🔴"
        return f"<code>{color} {bar} {score:.1f}%</code>"
    
    def _format_options_section(self, setup: Dict, data: Dict) -> str:
        """Format options data with premium styling"""
        options_data = data.get('options_data', {}) or setup.get('options_validation', {})
        
        if not options_data or not any(v for v in options_data.values() if v is not None and v != 0):
            return ""
        
        iv = options_data.get('iv', 0)
        premium = options_data.get('premium', 0)
        delta = options_data.get('delta', 0)
        oi = options_data.get('oi', 0)
        
        if iv == 0 and premium == 0:
            return ""
        
        # IV color coding
        iv_emoji = "🟢" if 30 <= iv <= 80 else "🟡" if 80 < iv <= 120 else "🔴"
        
        return f"""

<b>📊 OPTIONS ANALYTICS (CoinDCX)</b>
<b>┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓</b>
<b>┃</b> {iv_emoji} IV:        <code>{iv:>10.1f}%</code> <b>┃</b>
<b>┃</b> 💵 Premium:   <code>${premium:>10.2f}</code> <b>┃</b>
<b>┃</b> ⚖️  Delta:      <code>{delta:>10.3f}</code> <b>┃</b>
<b>┃</b> 📈 OI:        <code>{oi:>10,.0f}</code> <b>┃</b>
<b>┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛</b>"""
    
    def _format_rationale(self, setup: Dict) -> str:
        """Format key factors"""
        rationale = setup.get('rationale', {})
        if not rationale:
            return ""
        
        lines = []
        for key, value in list(rationale.items())[:3]:
            display_key = key.replace('_', ' ').title()
            if isinstance(value, float):
                if abs(value) < 0.01:
                    display_val = f"{value:.4f}"
                elif abs(value) < 1:
                    display_val = f"{value:.3f}"
                else:
                    display_val = f"{value:.2f}"
            else:
                display_val = str(value)[:20]
            
            emoji = "🔹"
            lines.append(f"<b>┃</b> {emoji} <i>{display_key}:</i> <code>{display_val}</code>")
        
        return f"""

<b>🔬 KEY METRICS</b>
<b>┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓</b>
{chr(10).join(lines)}
<b>┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛</b>"""
    
    def _format_components(self, score: Dict) -> str:
        """Format component scores"""
        components = score.get('component_scores', {})
        if not components:
            return ""
        
        lines = []
        for comp, val in components.items():
            emoji = self.COMPONENT_EMOJIS.get(comp, '📊')
            bar = "█" * int(val / 10) + "░" * (10 - int(val / 10))
            lines.append(f"<b>┃</b> {emoji} <i>{comp.title():<12}</i> <code>{bar} {val}</code>")
        
        return f"""

<b>📊 COMPONENT BREAKDOWN</b>
<b>┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓</b>
{chr(10).join(lines)}
<b>┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛</b>"""
    
    async def send_status(self, message: str):
        """Send status update with premium formatting"""
        try:
            if not self.bot or not self.chat_id:
                logger.warning(f"MOCK: {message}")
                return
            
            # Add premium wrapper
            premium_msg = f"""<code>╔══════════════════════════════════════╗
║         🤖 ALPHA BOT STATUS          ║
╚══════════════════════════════════════╝</code>

{message}

<code>══════════════════════════════════════</code>"""
            
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=premium_msg,
                parse_mode='HTML'
            )
        except Exception as e:
            logger.error(f"Status send error: {e}")
    
    async def send_alert(self, title: str, message: str, impact: str = "medium"):
        """Send premium alert with rate limiting"""
        try:
            now = datetime.now(timezone.utc)
            
            # Rate limiting
            alert_key = f"{title}_{impact}"
            last_time = self.last_alert_time.get(alert_key)
            if last_time and (now - last_time).seconds < self.min_alert_interval:
                return
            
            self.last_alert_time[alert_key] = now
            
            # Impact styling
            impact_styles = {
                'low': ('ℹ️', '🔵', 'INFO'),
                'medium': ('⚠️', '🟡', 'WARNING'),
                'high': ('🚨', '🔴', 'ALERT'),
                'extreme': ('⛔', '⚫', 'CRITICAL')
            }
            
            emoji, color, label = impact_styles.get(impact, ('⚠️', '🟡', 'WARNING'))
            
            formatted = f"""<code>╔══════════════════════════════════════╗
║  {color}  <b>{label}</b>  {color}  ║
╚══════════════════════════════════════╝</code>

{emoji} <b>{title}</b>

{message}

<code>⏱️ {now.strftime('%H:%M:%S')} UTC</code>"""
            
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=formatted,
                parse_mode='HTML'
            )
            
        except Exception as e:
            logger.error(f"Alert error: {e}")
    
    async def send_trade_close(self, trade_data: Dict):
        """Premium trade close notification"""
        result = trade_data.get('result', 'neutral')
        
        if result == 'win':
            header = "🎉 TRADE SUCCESS 🎉"
            color = "🟢"
            pnl_emoji = "💰"
        elif result == 'loss':
            header = "📉 TRADE CLOSED"
            color = "🔴"
            pnl_emoji = "🛡️"
        else:
            header = "⏹️ TRADE EXPIRED"
            color = "⚪"
            pnl_emoji = "➖"
        
        pnl = trade_data.get('pnl_percent', 0)
        
        message = f"""<code>╔══════════════════════════════════════╗
║  {color}  <b>{header}</b>  {color}  ║
╚══════════════════════════════════════╝</code>

<b>📊 Trade Summary</b>
<b>┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓</b>
<b>┃</b> 💎 Asset:      <code>{trade_data.get('asset', 'N/A'):>12}</code> <b>┃</b>
<b>┃</b> 📈 Direction:  <code>{trade_data.get('direction', 'N/A').upper():>12}</code> <b>┃</b>
<b>┃</b> 🚪 Entry:      <code>{trade_data.get('entry_price', 0):>12,.2f}</code> <b>┃</b>
<b>┃</b> 🏁 Exit:       <code>{trade_data.get('exit_price', 0):>12,.2f}</code> <b>┃</b>
<b>┃</b> {pnl_emoji} P&L:        <code>{pnl:>+11.2f}%</code> <b>┃</b>
<b>┃</b> ⏱️ Duration:   <code>{trade_data.get('duration', 'N/A'):>12}</code> <b>┃</b>
<b>┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛</b>

<code>══════════════════════════════════════</code>
<i>🤖 Alpha Bot v3.4 Premium | {datetime.now(timezone.utc).strftime('%H:%M UTC')}</i>"""
        
        try:
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode='HTML'
            )
        except Exception as e:
            logger.error(f"Trade close send error: {e}")
