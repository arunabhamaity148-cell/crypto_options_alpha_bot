"""
Trade Monitor & Auto-Management System - FIXED
"""

import asyncio
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum

from tg_bot.bot import AlphaTelegramBot

logger = logging.getLogger(__name__)

class AlertType(Enum):
    SL_APPROACHING = "sl_approaching"
    TP1_APPROACHING = "tp1_approaching"
    TP2_APPROACHING = "tp2_approaching"
    BREAKEVEN_TRIGGER = "breakeven_trigger"
    TRAIL_STOP_TRIGGER = "trail_stop_trigger"
    TIME_EXPIRING = "time_expiring"
    REVERSAL_DETECTED = "reversal_detected"
    VOLATILITY_SPIKE = "volatility_spike"
    PARTIAL_CLOSE = "partial_close"

@dataclass
class ActiveTrade:
    asset: str
    direction: str
    entry_price: float
    stop_loss: float
    tp1: float
    tp2: float
    strike: str
    expiry: datetime
    position_size: float
    entry_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))  # FIX: Timezone aware
    status: str = "open"
    alerts_sent: List[AlertType] = field(default_factory=list)
    current_price: float = 0.0
    pnl_percent: float = 0.0
    auto_manage: bool = True
    be_triggered: bool = False
    tp1_triggered: bool = False
    tp2_triggered: bool = False
    trail_stop_active: bool = False
    trail_stop_price: float = 0.0

    def update_price(self, price: float):
        """Update current price and PnL"""
        self.current_price = price
        
        if self.direction == 'long':
            self.pnl_percent = ((price - self.entry_price) / self.entry_price) * 100
        else:
            self.pnl_percent = ((self.entry_price - price) / self.entry_price) * 100

class TradeMonitor:
    """Monitors active trades with auto-management"""
    
    ALERT_THRESHOLDS = {
        AlertType.SL_APPROACHING: {
            'distance_percent': 0.5,
            'message': '🚨 SL APPROACHING! Consider early exit'
        },
        AlertType.TP1_APPROACHING: {
            'distance_percent': 0.3,
            'message': '🎯 TP1 NEAR! Prepare for partial close'
        },
        AlertType.BREAKEVEN_TRIGGER: {
            'profit_percent': 1.0,
            'message': '✅ Move SL to BREAKEVEN now!'
        },
        AlertType.TRAIL_STOP_TRIGGER: {
            'profit_percent': 2.0,
            'message': '📈 Activate TRAILING STOP'
        },
        AlertType.PARTIAL_CLOSE: {
            'profit_percent': 2.0,
            'close_percent': 0.5,
            'message': '🔒 Close 50% position at TP1'
        }
    }
    
    def __init__(self, telegram_bot: AlphaTelegramBot):
        self.active_trades: List[ActiveTrade] = []
        self.telegram = telegram_bot
        self.monitoring = False
        self.price_history: Dict[str, List[Tuple[datetime, float]]] = {}
        self.performance_callback = None
        
    def add_trade(self, trade: ActiveTrade) -> Optional[asyncio.Task]:
        """Add new trade to monitor - FIX: Return task for proper handling"""
        self.active_trades.append(trade)
        self.price_history[trade.asset] = []
        logger.info(f"📊 Added trade: {trade.asset} {trade.direction} @ {trade.entry_price}")
        
        # Return task so caller can await if needed
        return asyncio.create_task(self._send_trade_confirmation(trade))
    
    async def _send_trade_confirmation(self, trade: ActiveTrade):
        """Send trade entry confirmation"""
        message = (
            f"✅ <b>TRADE ACTIVE - AUTO MANAGED</b>\n\n"
            f"Asset: {trade.asset}\n"
            f"Direction: {trade.direction.upper()}\n"
            f"Entry: {trade.entry_price:,.2f}\n"
            f"SL: {trade.stop_loss:,.2f}\n"
            f"TP1: {trade.tp1:,.2f} | TP2: {trade.tp2:,.2f}\n"
            f"Size: {trade.position_size:.3f}\n\n"
            f"<b>Auto-actions enabled:</b>\n"
            f"• SL → BE at +1%\n"
            f"• 50% close at TP1\n"
            f"• Trail stop after TP1"
        )
        await self.telegram.send_status(message)
    
    async def start_monitoring(self, data_fetcher):
        """Start continuous monitoring loop"""
        self.monitoring = True
        
        while self.monitoring:
            try:
                if not self.active_trades:
                    await asyncio.sleep(5)
                    continue
                
                # Update all trade prices
                for trade in self.active_trades.copy():
                    if trade.status != "open":
                        continue
                    
                    # FIX: Add timeout to prevent hanging
                    try:
                        current_price = await asyncio.wait_for(
                            data_fetcher(trade.asset),
                            timeout=10.0
                        )
                    except asyncio.TimeoutError:
                        logger.error(f"Price fetch timeout for {trade.asset}")
                        continue
                    except Exception as e:
                        logger.error(f"Price fetch error for {trade.asset}: {e}")
                        continue
                    
                    if current_price == 0:
                        continue
                    
                    trade.update_price(current_price)
                    
                    # Store price history
                    self.price_history[trade.asset].append((datetime.now(timezone.utc), current_price))
                    
                    # Keep only last 100 prices
                    if len(self.price_history[trade.asset]) > 100:
                        self.price_history[trade.asset] = self.price_history[trade.asset][-100:]
                    
                    # Check all alert conditions
                    await self._check_alerts(trade)
                    
                    # Check if trade hit SL/TP
                    await self._check_trade_status(trade)
                    
                    # Auto-management
                    if trade.auto_manage:
                        await self._auto_manage(trade)
                
                # Clean up closed trades
                self.active_trades = [t for t in self.active_trades if t.status == "open"]
                
                await asyncio.sleep(5)
                
            except Exception as e:
                logger.error(f"Monitor error: {e}")
                await asyncio.sleep(10)
    
    async def _auto_manage(self, trade: ActiveTrade):
        """Auto-manage trade based on profit levels"""
        
        # 1. Move to breakeven at +1%
        if not trade.be_triggered and trade.pnl_percent >= 1.0:
            trade.stop_loss = trade.entry_price
            trade.be_triggered = True
            await self._send_alert(trade, AlertType.BREAKEVEN_TRIGGER, {
                'new_sl': trade.entry_price,
                'current_pnl': trade.pnl_percent
            })
            logger.info(f"Auto-moved SL to BE for {trade.asset}")
        
        # 2. Partial close at TP1 (+2%)
        if not trade.tp1_triggered and trade.pnl_percent >= 2.0:
            trade.tp1_triggered = True
            await self._send_alert(trade, AlertType.PARTIAL_CLOSE, {
                'close_percent': 50,
                'keep_running': 50,
                'current_pnl': trade.pnl_percent
            })
            logger.info(f"Auto-partial close triggered for {trade.asset}")
        
        # 3. Activate trailing stop after TP1
        if trade.tp1_triggered and not trade.trail_stop_active:
            if trade.pnl_percent >= 3.0:
                trade.trail_stop_active = True
                trade.trail_stop_price = trade.current_price * 0.99 if trade.direction == 'long' else trade.current_price * 1.01
                await self._send_alert(trade, AlertType.TRAIL_STOP_TRIGGER, {
                    'trail_price': trade.trail_stop_price
                })
                logger.info(f"Auto-trail stop activated for {trade.asset}")
        
        # 4. Update trailing stop
        if trade.trail_stop_active:
            new_trail = trade.current_price * 0.99 if trade.direction == 'long' else trade.current_price * 1.01
            
            if trade.direction == 'long' and new_trail > trade.trail_stop_price:
                trade.trail_stop_price = new_trail
                trade.stop_loss = new_trail
                logger.info(f"Trail stop updated for {trade.asset}: {new_trail:,.2f}")
            elif trade.direction == 'short' and new_trail < trade.trail_stop_price:
                trade.trail_stop_price = new_trail
                trade.stop_loss = new_trail
                logger.info(f"Trail stop updated for {trade.asset}: {new_trail:,.2f}")
    
    async def _check_alerts(self, trade: ActiveTrade):
        """Check and send alerts"""
        # Check SL approaching
        if trade.direction == 'long':
            distance_to_sl = ((trade.current_price - trade.stop_loss) / trade.entry_price) * 100
        else:
            distance_to_sl = ((trade.stop_loss - trade.current_price) / trade.entry_price) * 100
        
        if distance_to_sl < 0.5 and AlertType.SL_APPROACHING not in trade.alerts_sent:
            await self._send_alert(trade, AlertType.SL_APPROACHING, {
                'distance': f"{distance_to_sl:.2f}%",
                'current': trade.current_price
            })
            trade.alerts_sent.append(AlertType.SL_APPROACHING)
        
        # Check TP1 approaching
        if not trade.tp1_triggered:
            if trade.direction == 'long':
                distance_to_tp1 = ((trade.tp1 - trade.current_price) / trade.entry_price) * 100
            else:
                distance_to_tp1 = ((trade.current_price - trade.tp1) / trade.entry_price) * 100
            
            if distance_to_tp1 < 0.3 and AlertType.TP1_APPROACHING not in trade.alerts_sent:
                await self._send_alert(trade, AlertType.TP1_APPROACHING, {
                    'distance': f"{distance_to_tp1:.2f}%",
                    'current': trade.current_price
                })
                trade.alerts_sent.append(AlertType.TP1_APPROACHING)
    
    async def _check_trade_status(self, trade: ActiveTrade):
        """Check if SL or TP hit"""
        
        if trade.direction == 'long':
            if trade.current_price <= trade.stop_loss:
                trade.status = "sl_hit"
                await self._close_trade(trade, "STOP LOSS", "loss")
                
            elif trade.current_price >= trade.tp2:
                trade.status = "tp2_hit"
                await self._close_trade(trade, "TP2 HIT - FULL TARGET", "win")
                
            elif trade.current_price >= trade.tp1 and trade.tp1_triggered:
                # TP1 already handled by auto-manage, wait for TP2 or trail
                pass
                
        else:  # short
            if trade.current_price >= trade.stop_loss:
                trade.status = "sl_hit"
                await self._close_trade(trade, "STOP LOSS", "loss")
                
            elif trade.current_price <= trade.tp2:
                trade.status = "tp2_hit"
                await self._close_trade(trade, "TP2 HIT - FULL TARGET", "win")
    
    async def _close_trade(self, trade: ActiveTrade, reason: str, result: str):
        """Close trade and notify"""
        emoji = "✅" if result == "win" else "❌"
        
        # FIX: Proper timezone aware duration calculation
        duration = datetime.now(timezone.utc) - trade.entry_time
        hours, remainder = divmod(duration.seconds, 3600)
        minutes, _ = divmod(remainder, 60)
        duration_str = f"{hours}h {minutes}m"
        
        message = (
            f"{emoji} <b>TRADE CLOSED - {reason}</b>\n\n"
            f"Asset: {trade.asset}\n"
            f"Direction: {trade.direction.upper()}\n"
            f"Entry: {trade.entry_price:,.2f}\n"
            f"Exit: {trade.current_price:,.2f}\n"
            f"<b>P&L: {trade.pnl_percent:+.2f}%</b>\n"
            f"Duration: {duration_str}\n\n"
            f"<i>{datetime.now(timezone.utc).strftime('%H:%M:%S')} UTC</i>"
        )
        
        await self.telegram.send_status(message)
        logger.info(f"Trade closed: {trade.asset} | P&L: {trade.pnl_percent:.2f}%")
        
        # Record for performance
        if self.performance_callback:
            await self.performance_callback(result, trade.pnl_percent, trade.asset)
    
    async def _send_alert(self, trade: ActiveTrade, alert_type: AlertType, data: dict):
        """Send alert to Telegram"""
        emoji_map = {
            AlertType.SL_APPROACHING: '🚨',
            AlertType.TP1_APPROACHING: '🎯',
            AlertType.BREAKEVEN_TRIGGER: '✅',
            AlertType.TRAIL_STOP_TRIGGER: '📈',
            AlertType.PARTIAL_CLOSE: '🔒'
        }
        
        emoji = emoji_map.get(alert_type, '⚠️')
        base_message = self.ALERT_THRESHOLDS.get(alert_type, {}).get('message', 'Alert')
        
        message = (
            f"{emoji} <b>{alert_type.value.upper().replace('_', ' ')}</b>\n\n"
            f"Asset: {trade.asset}\n"
            f"Direction: {trade.direction.upper()}\n"
            f"Entry: {trade.entry_price:,.2f}\n"
            f"Current: {trade.current_price:,.2f}\n"
            f"P&L: {trade.pnl_percent:+.2f}%\n\n"
            f"<b>{base_message}</b>\n"
        )
        
        for key, value in data.items():
            formatted_key = key.replace('_', ' ').title()
            message += f"\n{formatted_key}: {value}"
        
        await self.telegram.send_status(message)
    
    def stop_monitoring(self):
        """Stop monitoring loop"""
        self.monitoring = False
        logger.info("Trade monitoring stopped")
