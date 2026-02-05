"""
Telegram Bot - Multi Asset
"""

import asyncio
import logging
from typing import Dict
from telegram import Bot, ParseMode
import matplotlib.pyplot as plt
import io

logger = logging.getLogger(__name__)

class AlphaTelegramBot:
    
    def __init__(self, token: str, chat_id: str):
        self.bot = Bot(token=token)
        self.chat_id = chat_id
    
    async def send_signal(self, setup: Dict, score: Dict, market_data: Dict):
        """Send signal"""
        try:
            message = self._format_message(setup, score, market_data)
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode=ParseMode.HTML
            )
            
            chart = self._generate_chart(setup)
            if chart:
                await self.bot.send_photo(chat_id=self.chat_id, photo=chart)
                
        except Exception as e:
            logger.error(f"Send error: {e}")
    
    def _format_message(self, setup: Dict, score: Dict, data: Dict) -> str:
        asset = setup.get('asset', 'BTC')
        direction = setup.get('direction', 'long')
        
        emojis = {'BTC': '₿', 'ETH': 'Ξ', 'SOL': '◎'}
        asset_emoji = emojis.get(asset, '💰')
        dir_emoji = "🟢" if direction == 'long' else "🔴"
        total_score = score.get('total_score', 0)
        stars = "⭐" * int(total_score / 20)
        
        message = f"""
{dir_emoji} <b>{asset} ALPHA SIGNAL</b> {asset_emoji}

<b>Strategy:</b> <code>{setup.get('strategy', '').replace('_', ' ').title()}</code>
<b>Direction:</b> {direction.upper()}
<b>Strike:</b> <code>{setup.get('strike_selection', 'ATM')}</code>
<b>Expiry:</b> {setup.get('expiry_suggestion', '24h')}

<b>━━━━━━━━━━━━━━━━━━━━━</b>
🎯 <b>ALPHA SCORE: {total_score}/100</b> {stars}
<b>Quality:</b> {score.get('setup_quality', 'standard').title()}
<b>Verdict:</b> {score.get('recommendation', 'pass').upper()}
<b>━━━━━━━━━━━━━━━━━━━━━</b>

💰 <b>TRADE PLAN</b>
├ Entry: <code>{setup.get('entry_price', 0)}</code>
├ Stop: <code>{setup.get('stop_loss', 0)}</code> ({self._calc_risk(setup)}%)
├ Target 1: <code>{setup.get('target_1', 0)}</code>
├ Target 2: <code>{setup.get('target_2', 0)}</code>
└ Position: <code>{setup.get('position_size', 0)} {asset}</code>

<b>━━━━━━━━━━━━━━━━━━━━━</b>
🔬 <b>RATIONALE</b>
"""
        rationale = setup.get('rationale', {})
        for key, value in list(rationale.items())[:4]:
            message += f"\n├ <i>{key.replace('_', ' ').title()}:</i> <code>{str(value)[:40]}</code>"

        components = score.get('component_scores', {})
        message += f"""

<b>━━━━━━━━━━━━━━━━━━━━━</b>
📊 <b>SCORES</b>
├ Micro: {components.get('microstructure', 0)}/100
├ Greeks: {components.get('greeks', 0)}/100
├ Liquidity: {components.get('liquidity', 0)}/100
├ Momentum: {components.get('momentum', 0)}/100
└ Sentiment: {components.get('sentiment', 0)}/100

⏱ <b>Valid:</b> 60 min | ⚠️ <b>Risk:</b> 1% max
<i>Alpha Bot v2.0 | Multi-Asset</i>
"""
        return message
    
    def _calc_risk(self, setup: Dict) -> float:
        entry = setup.get('entry_price', 0)
        stop = setup.get('stop_loss', 0)
        if entry == 0:
            return 0
        return round(abs(entry - stop) / entry * 100, 2)
    
    def _generate_chart(self, setup: Dict) -> bytes:
        try:
            fig, ax = plt.subplots(figsize=(10, 6))
            
            asset = setup.get('asset', 'BTC')
            current = setup.get('entry_price', 0)
            stop = setup.get('stop_loss', 0)
            t1 = setup.get('target_1', 0)
            t2 = setup.get('target_2', 0)
            
            x = range(20)
            y = [current * (1 + (i-10)*0.002) for i in x]
            
            ax.plot(x, y, 'b-', linewidth=2, label=f'{asset} Price')
            ax.axhline(y=current, color='blue', linestyle='--', alpha=0.7, label='Entry')
            ax.axhline(y=stop, color='red', linestyle='--', alpha=0.7, label='Stop')
            ax.axhline(y=t1, color='green', linestyle='--', alpha=0.7, label='T1')
            ax.axhline(y=t2, color='darkgreen', linestyle='--', alpha=0.7, label='T2')
            
            if setup.get('direction') == 'long':
                ax.fill_between(x, stop, current, alpha=0.2, color='red')
                ax.fill_between(x, current, t2, alpha=0.2, color='green')
            else:
                ax.fill_between(x, current, stop, alpha=0.2, color='red')
                ax.fill_between(x, t2, current, alpha=0.2, color='green')
            
            ax.set_title(f"{asset} {setup.get('strategy', '').replace('_', ' ').title()}", 
                        fontsize=14, fontweight='bold')
            ax.legend()
            ax.grid(True, alpha=0.3)
            
            buf = io.BytesIO()
            plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
            buf.seek(0)
            plt.close()
            
            return buf
            
        except Exception as e:
            logger.error(f"Chart error: {e}")
            return None
    
    async def send_status(self, message: str):
        try:
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            logger.error(f"Status error: {e}")
