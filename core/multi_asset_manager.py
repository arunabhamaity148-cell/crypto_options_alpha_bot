"""
Multi-Asset Manager - EMERGENCY FIX
Prevents signal spam, enforces cooldowns
"""

import logging
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

@dataclass
class TradingSignal:
    asset: str
    strategy: str
    direction: str
    entry_price: float
    stop_loss: float
    target_1: float
    target_2: float
    strike_selection: str
    expiry_suggestion: str
    confidence: float
    score_breakdown: Dict
    rationale: Dict
    timestamp: datetime
    total_score: float = 0  # Added for sorting

class MultiAssetManager:
    CORRELATIONS = {
        ('BTC', 'ETH'): 0.85,
        ('BTC', 'SOL'): 0.80,
        ('ETH', 'SOL'): 0.90,
    }
    
    def __init__(self, config: Dict, assets_config: Dict):
        self.config = config
        self.assets_config = assets_config
        self.active_assets = [a for a in config.get('assets', []) 
                             if assets_config.get(a, {}).get('enable', True)]
        self.daily_signals = {asset: 0 for asset in self.active_assets}
        self.last_reset = datetime.now()
        self.sent_signals = []
        self.active_directions = {}  # asset -> direction
        self.last_signal_time = None  # Global cooldown
        self.active_trades = {}  # asset -> entry_price
        
    def should_reset_daily(self) -> bool:
        return (datetime.now() - self.last_reset).days >= 1
    
    def reset_daily_counters(self):
        self.daily_signals = {asset: 0 for asset in self.active_assets}
        self.active_directions = {}
        self.active_trades = {}
        self.last_reset = datetime.now()
        self.sent_signals = []
        logger.info("Daily counters reset")
    
    def can_send_signal(self, asset: str, direction: str = None, 
                       entry_price: float = None) -> bool:
        """Strict checks to prevent spam"""
        
        # 1. Global cooldown (30 min between ANY signal)
        if self.last_signal_time:
            time_since = (datetime.now() - self.last_signal_time).total_seconds()
            if time_since < 1800:  # 30 minutes
                logger.warning(f"🚫 Global cooldown: {time_since/60:.1f}min remaining")
                return False
        
        # 2. Asset cooldown (60 min between same asset)
        last_asset_signal = None
        for sig in reversed(self.sent_signals):
            if sig['asset'] == asset:
                last_asset_signal = sig
                break
        
        if last_asset_signal:
            time_since = (datetime.now() - last_asset_signal['timestamp']).total_seconds()
            if time_since < 3600:  # 60 minutes
                logger.warning(f"🚫 {asset} cooldown: {time_since/60:.1f}min remaining")
                return False
        
        # 3. Direction lock (opposite direction blocked)
        if asset in self.active_directions:
            if direction and direction != self.active_directions[asset]:
                logger.warning(f"🚫 {asset} opposite direction active: {self.active_directions[asset]}")
                return False
        
        # 4. Daily limit
        max_per_asset = self.config.get('max_signals_per_asset', 2)
        if self.daily_signals.get(asset, 0) >= max_per_asset:
            logger.warning(f"🚫 {asset} daily limit reached: {max_per_asset}")
            return False
        
        # 5. Price proximity check (avoid churn)
        if asset in self.active_trades and entry_price:
            last_entry = self.active_trades[asset]
            price_diff = abs(entry_price - last_entry) / last_entry
            if price_diff < 0.005:  # 0.5% price difference
                logger.warning(f"🚫 {asset} price too close to last: {price_diff:.2%}")
                return False
        
        return True
    
    def record_signal(self, asset: str, direction: str, entry_price: float):
        """Record with strict tracking"""
        self.daily_signals[asset] = self.daily_signals.get(asset, 0) + 1
        self.active_directions[asset] = direction
        self.active_trades[asset] = entry_price
        self.last_signal_time = datetime.now()
        self.sent_signals.append({
            'asset': asset,
            'direction': direction,
            'entry_price': entry_price,
            'timestamp': datetime.now()
        })
        logger.info(f"✅ Recorded: {asset} {direction} @ {entry_price}")
    
    def close_trade(self, asset: str):
        """Release direction lock when trade closes"""
        if asset in self.active_directions:
            del self.active_directions[asset]
        if asset in self.active_trades:
            del self.active_trades[asset]
        logger.info(f"🔓 Released: {asset}")
    
    def filter_correlated_signals(self, signals: List[TradingSignal]) -> List[TradingSignal]:
        """Only return TOP 1 signal to prevent correlation risk"""
        if not signals:
            return []
        
        # Sort by score
        sorted_signals = sorted(signals, key=lambda x: x.total_score, reverse=True)
        
        # Return only the best signal
        best = sorted_signals[0]
        logger.info(f"Selected best: {best.asset} {best.direction} @ {best.total_score}")
        return [best]
    
    def calculate_position_size(self, asset: str, entry: float, stop: float) -> float:
        """Conservative position sizing for OPTIONS"""
        account = self.config.get('account_size', 100000)
        
        # Max 1% risk per trade (premium paid)
        max_premium = account * 0.01  # $1000 for $100k account
        
        # Conservative sizing based on asset volatility
        sizing = {
            'BTC': {'contract_value': 100, 'max_contracts': 0.5},
            'ETH': {'contract_value': 10, 'max_contracts': 5},
            'SOL': {'contract_value': 1, 'max_contracts': 50}
        }
        
        config = sizing.get(asset, {'contract_value': 100, 'max_contracts': 1})
        
        # Calculate based on risk
        risk_per_contract = config['contract_value'] * 0.1  # Assume 10% move
        max_by_risk = max_premium / risk_per_contract
        
        # Take minimum of risk-based and max limit
        position = min(max_by_risk, config['max_contracts'])
        
        return round(position, 3)
