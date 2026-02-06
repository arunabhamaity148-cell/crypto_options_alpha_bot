"""
Trade Monitor & Danger Alert System
Monitors active trades and sends alerts for:
- SL approaching
- TP approaching  
- Reversal signals
- Volatility spikes
"""

import asyncio
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum

# CHANGED: telegram -> tg_bot (to avoid import conflict)
from tg_bot.bot import AlphaTelegramBot

logger = logging.getLogger(__name__)

class AlertType(Enum):
    SL_APPROACHING = "sl_approaching"
    TP1_APPROACHING = "tp1_approaching"
    TP2_APPROACHING = "tp2_approaching"
    REVERSAL_DETECTED = "reversal_detected"
    VOLATILITY_SPIKE = "volatility_spike"
    TIME_EXPIRING = "time_expiring"
    BREAKEVEN_TRIGGER = "breakeven_trigger"
    TRAIL_STOP_TRIGGER = "trail_stop_trigger"

@dataclass
class ActiveTrade:
    asset: str
    direction: str  # 'long' or 'short'
    entry_price: float
    stop_loss: float
    tp1: float
    tp2: float
    strike: str
    expiry: datetime
    position_size: float
    entry_time: datetime = field(default_factory=datetime.now)
    status: str = "open"  # open, tp1_hit, tp2_hit, sl_hit, closed
    alerts_sent: List[AlertType] = field(default_factory=list)
    current_price: float = 0.0
    pnl_percent: float = 0.0
    
    def update_price(self, price: float):
        """Update current price and PnL"""
        self.current_price = price
        
        if self.direction == 'long':
            self.pnl_percent = ((price - self.entry_price) / self.entry_price) * 100
        else:
            self.pnl_percent = ((self.entry_price - price) / self.entry_price) * 100
    
    def get_distance_to_sl(self) -> float:
        """Get percentage distance to stop loss"""
        if self.direction == 'long':
            return ((self.current_price - self.stop_loss) / self.entry_price) * 100
        else:
            return ((self.stop_loss - self.current_price) / self.entry_price) * 100
    
    def get_distance_to_tp1(self) -> float:
        """Get percentage distance to TP1"""
        if self.direction == 'long':
            return ((self.tp1 - self.current_price) / self.entry_price) * 100
        else:
            return ((self.current_price - self.tp1) / self.entry_price) * 100

class TradeMonitor:
    """Monitors active trades and sends danger alerts"""
    
    # Alert thresholds
    ALERT_THRESHOLDS = {
        AlertType.SL_APPROACHING: {
            'distance_percent': 0.5,  # Alert when 0.5% away from SL
            'message': '🚨 SL APPROACHING! Move to breakeven or reduce size'
        },
        AlertType.TP1_APPROACHING: {
            'distance_percent': 0.3,  # Alert when 0.3% away from TP1
            'message': '🎯 TP1 NEAR! Prepare to take partial profits'
        },
        AlertType.TP2_APPROACHING: {
            'distance_percent': 0.5,
            'message': '🎯 TP2 NEAR! Final target approaching'
        },
        AlertType.BREAKEVEN_TRIGGER: {
            'profit_percent': 1.0,  # Move SL to breakeven at 1% profit
            'message': '✅ Move SL to BREAKEVEN now!'
        },
        AlertType.TRAIL_STOP_TRIGGER: {
            'profit_percent': 2.0,  # Activate trailing stop at 2% profit
            'message': '📈 Activate TRAILING STOP - Lock in profits'
        },
        AlertType.TIME_EXPIRING: {
            'hours_before_expiry': 4,
            'message': '⏰ Option expiring soon! Close or roll position'
        },
        AlertType.VOLATILITY_SPIKE: {
            'iv_increase_percent': 20,
            'message': '⚠️ Volatility spike detected! Widen stops or reduce'
        }
    }
    
    def __init__(self, telegram_bot: AlphaTelegramBot):
        self.active_trades: List[ActiveTrade] = []
        self.telegram = telegram_bot
        self.monitoring = False
        self.price_history: Dict[str, List[Tuple[datetime, float]]] = {}
        
    def add_trade(self, trade: ActiveTrade):
        """Add new trade to monitor"""
        self.active_trades.append(trade)
        self.price_history[trade.asset] = []
        logger.info(f"📊 Added trade: {trade.asset} {trade.direction} @ {trade.entry_price}")
        
        # Send initial confirmation
        asyncio.create_task(self._send_trade_confirmation(trade))
    
    async def _send_trade_confirmation(self, trade: ActiveTrade):
        """Send trade entry confirmation"""
        message = (
            f"✅ <b>TRADE ACTIVE</b>\n\n"
            f"Asset: {trade.asset}\n"
            f"Direction: {trade.direction.upper()}\n"
            f"Entry: {trade.entry_price}\n"
            f"SL: {trade.stop_loss}\n"
            f"TP1: {trade.tp1} | TP2: {trade.tp2}\n"
            f"Size: {trade.position_size}\n\n"
            f"Monitoring started..."
        )
        await self.telegram.send_status(message)
    
    async def start_monitoring(self, data_fetcher):
        """Start continuous monitoring loop"""
        self.monitoring = True
        
        while self.monitoring:
            try:
                if not self.active_trades:
                    await asyncio.sleep(10)
                    continue
                
                # Update all trade prices
                for trade in self.active_trades.copy():
                    if trade.status != "open":
                        continue
                    
                    # Fetch current price
                    current_price = await data_fetcher.get_current_price(trade.asset)
                    trade.update_price(current_price)
                    
                    # Store price history
                    self.price_history[trade.asset].append((datetime.now(), current_price))
                    
                    # Keep only last 100 prices
                    if len(self.price_history[trade.asset]) > 100:
                        self.price_history[trade.asset] = self.price_history[trade.asset][-100:]
                    
                    # Check all alert conditions
                    await self._check_alerts(trade)
                    
                    # Check if trade hit SL/TP
                    await self._check_trade_status(trade)
                
                # Clean up closed trades
                self.active_trades = [t for t in self.active_trades if t.status == "open"]
                
                await asyncio.sleep(5)  # Check every 5 seconds
                
            except Exception as e:
                logger.error(f"Monitor error: {e}")
                await asyncio.sleep(10)
    
    async def _check_alerts(self, trade: ActiveTrade):
        """Check and send alerts for a trade"""
        
        # 1. SL Approaching Alert
        if AlertType.SL_APPROACHING not in trade.alerts_sent:
            distance_to_sl = trade.get_distance_to_sl()
            threshold = self.ALERT_THRESHOLDS[AlertType.SL_APPROACHING]['distance_percent']
            
            if distance_to_sl <= threshold and trade.pnl_percent < 0:
                await self._send_alert(trade, AlertType.SL_APPROACHING, {
                    'distance': distance_to_sl,
                    'current_pnl': trade.pnl_percent
                })
                trade.alerts_sent.append(AlertType.SL_APPROACHING)
        
        # 2. TP1 Approaching Alert
        if AlertType.TP1_APPROACHING not in trade.alerts_sent:
            distance_to_tp1 = trade.get_distance_to_tp1()
            threshold = self.ALERT_THRESHOLDS[AlertType.TP1_APPROACHING]['distance_percent']
            
            if distance_to_tp1 <= threshold and trade.pnl_percent > 0:
                await self._send_alert(trade, AlertType.TP1_APPROACHING, {
                    'distance': distance_to_tp1,
                    'suggested_action': 'Take 50% profits at TP1'
                })
                trade.alerts_sent.append(AlertType.TP1_APPROACHING)
        
        # 3. Breakeven Trigger
        if AlertType.BREAKEVEN_TRIGGER not in trade.alerts_sent:
            profit_threshold = self.ALERT_THRESHOLDS[AlertType.BREAKEVEN_TRIGGER]['profit_percent']
            
            if trade.pnl_percent >= profit_threshold:
                await self._send_alert(trade, AlertType.BREAKEVEN_TRIGGER, {
                    'current_profit': trade.pnl_percent,
                    'new_sl': trade.entry_price
                })
                trade.alerts_sent.append(AlertType.BREAKEVEN_TRIGGER)
        
        # 4. Trailing Stop Trigger
        if AlertType.TRAIL_STOP_TRIGGER not in trade.alerts_sent:
            profit_threshold = self.ALERT_THRESHOLDS[AlertType.TRAIL_STOP_TRIGGER]['profit_percent']
            
            if trade.pnl_percent >= profit_threshold:
                await self._send_alert(trade, AlertType.TRAIL_STOP_TRIGGER, {
                    'current_profit': trade.pnl_percent,
                    'suggestion': 'Trail 1% below current price'
                })
                trade.alerts_sent.append(AlertType.TRAIL_STOP_TRIGGER)
        
        # 5. Time Expiring Alert
        if AlertType.TIME_EXPIRING not in trade.alerts_sent:
            hours_remaining = (trade.expiry - datetime.now()).total_seconds() / 3600
            threshold = self.ALERT_THRESHOLDS[AlertType.TIME_EXPIRING]['hours_before_expiry']
            
            if hours_remaining <= threshold:
                await self._send_alert(trade, AlertType.TIME_EXPIRING, {
                    'hours_remaining': round(hours_remaining, 1),
                    'theta_decay_warning': 'Time decay accelerating'
                })
                trade.alerts_sent.append(AlertType.TIME_EXPIRING)
        
        # 6. Reversal Detection (using price action)
        await self._check_reversal_signals(trade)
        
        # 7. Volatility Spike Detection
        await self._check_volatility_spike(trade)
    
    async def _check_reversal_signals(self, trade: ActiveTrade):
        """Detect potential reversal against trade direction"""
        
        if len(self.price_history.get(trade.asset, [])) < 20:
            return
        
        recent_prices = [p[1] for p in self.price_history[trade.asset][-20:]]
        
        # Calculate momentum
        if len(recent_prices) >= 10:
            recent_avg = sum(recent_prices[-5:]) / 5
            previous_avg = sum(recent_prices[-10:-5]) / 5
            
            momentum_change = ((recent_avg - previous_avg) / previous_avg) * 100
            
            # Check for reversal against position
            reversal_detected = False
            strength = "moderate"
            
            if trade.direction == 'long' and momentum_change < -0.5:
                # Bearish momentum in long trade
                if trade.pnl_percent > 0.5:
                    reversal_detected = True
                    strength = "moderate"
                elif trade.pnl_percent < -0.3:
                    reversal_detected = True
                    strength = "strong"
                    
            elif trade.direction == 'short' and momentum_change > 0.5:
                # Bullish momentum in short trade
                if trade.pnl_percent > 0.5:
                    reversal_detected = True
                    strength = "moderate"
                elif trade.pnl_percent < -0.3:
                    reversal_detected = True
                    strength = "strong"
            
            if reversal_detected and AlertType.REVERSAL_DETECTED not in trade.alerts_sent:
                await self._send_alert(trade, AlertType.REVERSAL_DETECTED, {
                    'momentum_change': round(momentum_change, 2),
                    'strength': strength,
                    'suggestion': 'Consider early exit or tighten stops'
                })
                trade.alerts_sent.append(AlertType.REVERSAL_DETECTED)
    
    async def _check_volatility_spike(self, trade: ActiveTrade):
        """Detect unusual volatility"""
        
        history = self.price_history.get(trade.asset, [])
        if len(history) < 10:
            return
        
        # Calculate recent volatility
        recent_prices = [p[1] for p in history[-10:]]
        returns = [(recent_prices[i] - recent_prices[i-1]) / recent_prices[i-1] 
                   for i in range(1, len(recent_prices))]
        
        avg_volatility = sum(abs(r) for r in returns) / len(returns)
        current_return = abs(returns[-1]) if returns else 0
        
        # Spike if current volatility > 3x average
        if current_return > avg_volatility * 3 and current_return > 0.005:  # 0.5% move
            if AlertType.VOLATILITY_SPIKE not in trade.alerts_sent:
                await self._send_alert(trade, AlertType.VOLATILITY_SPIKE, {
                    'spike_magnitude': round(current_return * 100, 2),
                    'average_volatility': round(avg_volatility * 100, 2),
                    'impact': 'Widen stops or reduce position'
                })
                trade.alerts_sent.append(AlertType.VOLATILITY_SPIKE)
    
    async def _check_trade_status(self, trade: ActiveTrade):
        """Check if SL or TP hit"""
        
        if trade.direction == 'long':
            if trade.current_price <= trade.stop_loss:
                trade.status = "sl_hit"
                await self._send_trade_close(trade, "STOP LOSS HIT", "loss")
                
            elif trade.current_price >= trade.tp2:
                trade.status = "tp2_hit"
                await self._send_trade_close(trade, "TP2 HIT - FULL TARGET", "win")
                
            elif trade.current_price >= trade.tp1 and trade.status == "open":
                trade.status = "tp1_hit"
                await self._send_tp1_hit(trade)
                
        else:  # short
            if trade.current_price >= trade.stop_loss:
                trade.status = "sl_hit"
                await self._send_trade_close(trade, "STOP LOSS HIT", "loss")
                
            elif trade.current_price <= trade.tp2:
                trade.status = "tp2_hit"
                await self._send_trade_close(trade, "TP2 HIT - FULL TARGET", "win")
                
            elif trade.current_price <= trade.tp1 and trade.status == "open":
                trade.status = "tp1_hit"
                await self._send_tp1_hit(trade)
    
    async def _send_alert(self, trade: ActiveTrade, alert_type: AlertType, data: dict):
        """Send alert to Telegram"""
        
        emoji_map = {
            AlertType.SL_APPROACHING: '🚨',
            AlertType.TP1_APPROACHING: '🎯',
            AlertType.TP2_APPROACHING: '🎯',
            AlertType.BREAKEVEN_TRIGGER: '✅',
            AlertType.TRAIL_STOP_TRIGGER: '📈',
            AlertType.TIME_EXPIRING: '⏰',
            AlertType.REVERSAL_DETECTED: '⚠️',
            AlertType.VOLATILITY_SPIKE: '⚡'
        }
        
        emoji = emoji_map.get(alert_type, '⚠️')
        base_message = self.ALERT_THRESHOLDS.get(alert_type, {}).get('message', 'Alert')
        
        message = (
            f"{emoji} <b>{alert_type.value.upper().replace('_', ' ')}</b>\n\n"
            f"Asset: {trade.asset}\n"
            f"Direction: {trade.direction.upper()}\n"
            f"Entry: {trade.entry_price}\n"
            f"Current: {trade.current_price}\n"
            f"P&L: {trade.pnl_percent:+.2f}%\n\n"
            f"<b>{base_message}</b>\n"
        )
        
        # Add specific data
        for key, value in data.items():
            formatted_key = key.replace('_', ' ').title()
            message += f"\n{formatted_key}: {value}"
        
        await self.telegram.send_status(message)
        logger.warning(f"Alert sent: {alert_type.value} for {trade.asset}")
    
    async def _send_tp1_hit(self, trade: ActiveTrade):
        """Send TP1 hit notification with instructions"""
        
        message = (
            f"🎯 <b>TP1 HIT!</b>\n\n"
            f"Asset: {trade.asset}\n"
            f"Profit: {trade.pnl_percent:+.2f}%\n\n"
            f"<b>ACTION REQUIRED:</b>\n"
            f"1️⃣ Close 50% position now\n"
            f"2️⃣ Move SL to breakeven\n"
            f"3️⃣ Let 50% run to TP2\n\n"
            f"New SL: {trade.entry_price}\n"
            f"TP2 Target: {trade.tp2}"
        )
        
        await self.telegram.send_status(message)
    
    async def _send_trade_close(self, trade: ActiveTrade, reason: str, result: str):
        """Send trade close notification"""
        
        emoji = "✅" if result == "win" else "❌"
        pnl = trade.pnl_percent
        
        message = (
            f"{emoji} <b>TRADE CLOSED - {reason}</b>\n\n"
            f"Asset: {trade.asset}\n"
            f"Direction: {trade.direction.upper()}\n"
            f"Entry: {trade.entry_price}\n"
            f"Exit: {trade.current_price}\n"
            f"<b>Final P&L: {pnl:+.2f}%</b>\n\n"
            f"Duration: {self._format_duration(trade.entry_time)}"
        )
        
        await self.telegram.send_status(message)
        logger.info(f"Trade closed: {trade.asset} | P&L: {pnl:.2f}%")
    
    def _format_duration(self, entry_time: datetime) -> str:
        """Format trade duration"""
        duration = datetime.now() - entry_time
        hours, remainder = divmod(duration.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours}h {minutes}m"
    
    def get_active_trades_summary(self) -> str:
        """Get summary of all active trades"""
        
        if not self.active_trades:
            return "No active trades"
        
        lines = ["📊 ACTIVE TRADES:\n"]
        
        for trade in self.active_trades:
            status_emoji = "🟢" if trade.pnl_percent > 0 else "🔴"
            lines.append(
                f"{status_emoji} {trade.asset} {trade.direction.upper()}\n"
                f"   Entry: {trade.entry_price} | Current: {trade.current_price}\n"
                f"   P&L: {trade.pnl_percent:+.2f}% | SL: {trade.get_distance_to_sl():.2f}% away\n"
            )
        
        return "\n".join(lines)
    
    def stop_monitoring(self):
        """Stop monitoring loop"""
        self.monitoring = False
        logger.info("Trade monitoring stopped")
