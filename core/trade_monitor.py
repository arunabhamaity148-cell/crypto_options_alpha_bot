"""
Trade Monitor & Alert System
"""

import asyncio
import logging
from typing import Dict, List
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)

class AlertType(Enum):
    SL_APPROACHING = "sl_approaching"
    TP1_APPROACHING = "tp1_approaching"
    TP2_APPROACHING = "tp2_approaching"
    BREAKEVEN_TRIGGER = "breakeven_trigger"
    TRAIL_STOP_TRIGGER = "trail_stop_trigger"

@dataclass
class ActiveTrade:
    asset: str
    direction: str
    entry_price: float
    stop_loss: float
    tp1: float
    tp2: float
    current_price: float = 0.0
    pnl_percent: float = 0.0
    alerts_sent: List[AlertType] = field(default_factory=list)
    
    def update_price(self, price: float):
        self.current_price = price
        
        if self.direction == 'long':
            self.pnl_percent = ((price - self.entry_price) / self.entry_price) * 100
        else:
            self.pnl_percent = ((self.entry_price - price) / self.entry_price) * 100
    
    def get_distance_to_sl(self) -> float:
        if self.direction == 'long':
            return ((self.current_price - self.stop_loss) / self.entry_price) * 100
        else:
            return ((self.stop_loss - self.current_price) / self.entry_price) * 100

class TradeMonitor:
    ALERT_THRESHOLDS = {
        AlertType.SL_APPROACHING: {
            'distance_percent': 0.5,
            'message': 'SL APPROACHING!'
        },
        AlertType.BREAKEVEN_TRIGGER: {
            'profit_percent': 1.0,
            'message': 'Move SL to BREAKEVEN now!'
        },
        AlertType.TRAIL_STOP_TRIGGER: {
            'profit_percent': 2.0,
            'message': 'Activate TRAILING STOP'
        }
    }
    
    def __init__(self, telegram_bot):
        self.active_trades: List[ActiveTrade] = []
        self.telegram = telegram_bot
        self.monitoring = False
        
    def add_trade(self, trade: ActiveTrade):
        self.active_trades.append(trade)
        logger.info(f"Added trade: {trade.asset} {trade.direction} @ {trade.entry_price}")
    
    async def start_monitoring(self, data_fetcher):
        self.monitoring = True
        
        while self.monitoring:
            try:
                if not self.active_trades:
                    await asyncio.sleep(10)
                    continue
                
                for trade in self.active_trades.copy():
                    if trade.pnl_percent != 0:  # Skip closed trades
                        continue
                    
                    current_price = await data_fetcher.get_current_price(trade.asset)
                    trade.update_price(current_price)
                    
                    await self._check_alerts(trade)
                
                self.active_trades = [t for t in self.active_trades if t.pnl_percent == 0]
                
                await asyncio.sleep(5)
                
            except Exception as e:
                logger.error(f"Monitor error: {e}")
                await asyncio.sleep(10)
    
    async def _check_alerts(self, trade: ActiveTrade):
        # SL Approaching
        if AlertType.SL_APPROACHING not in trade.alerts_sent:
            distance_to_sl = trade.get_distance_to_sl()
            threshold = self.ALERT_THRESHOLDS[AlertType.SL_APPROACHING]['distance_percent']
            
            if distance_to_sl <= threshold and trade.pnl_percent < 0:
                await self._send_alert(trade, AlertType.SL_APPROACHING)
                trade.alerts_sent.append(AlertType.SL_APPROACHING)
        
        # Breakeven Trigger - FIXED LINE (removed duplicate)
        if AlertType.BREAKEVEN_TRIGGER not in trade.alerts_sent:
            profit_threshold = self.ALERT_THRESHOLDS[AlertType.BREAKEVEN_TRIGGER]['profit_percent']
            
            if trade.pnl_percent >= profit_threshold:
                await self._send_alert(trade, AlertType.BREAKEVEN_TRIGGER)
                trade.alerts_sent.append(AlertType.BREAKEVEN_TRIGGER)
        
        # Trailing Stop - FIXED LINE
        if AlertType.TRAIL_STOP_TRIGGER not in trade.alerts_sent:
            profit_threshold = self.ALERT_THRESHOLDS[AlertType.TRAIL_STOP_TRIGGER]['profit_percent']
            
            if trade.pnl_percent >= profit_threshold:
                await self._send_alert(trade, AlertType.TRAIL_STOP_TRIGGER)
                trade.alerts_sent.append(AlertType.TRAIL_STOP_TRIGGER)
    
    async def _send_alert(self, trade: ActiveTrade, alert_type: AlertType):
        message = (
            f"{alert_type.value.upper()}\n\n"
            f"Asset: {trade.asset}\n"
            f"Direction: {trade.direction.upper()}\n"
            f"Entry: {trade.entry_price}\n"
            f"Current: {trade.current_price}\n"
            f"P&L: {trade.pnl_percent:+.2f}%"
        )
        
        await self.telegram.send_status(message)
        logger.warning(f"Alert sent: {alert_type.value} for {trade.asset}")
    
    def stop_monitoring(self):
        self.monitoring = False
        logger.info("Trade monitoring stopped")
