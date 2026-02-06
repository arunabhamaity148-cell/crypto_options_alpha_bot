"""
Multi-Asset Manager with Risk-Based Sizing
"""

import logging
from typing import Dict, List, Tuple
from dataclasses import dataclass
from datetime import datetime

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
    total_score: float = 0

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
        self.active_directions = {}
        self.active_trades = {}
        
    def should_reset_daily(self) -> bool:
        return (datetime.now() - self.last_reset).days >= 1
    
    def reset_daily_counters(self):
        self.daily_signals = {asset: 0 for asset in self.active_assets}
        self.active_directions = {}
        self.active_trades = {}
        self.last_reset = datetime.now()
        logger.info("Daily counters reset")
    
    def can_send_signal(self, asset: str, direction: str = None, 
                       entry_price: float = None) -> bool:
        max_per_asset = self.config.get('max_signals_per_asset', 2)
        if self.daily_signals.get(asset, 0) >= max_per_asset:
            return False
        
        if asset in self.active_directions:
            if direction and direction != self.active_directions[asset]:
                logger.warning(f"🚫 {asset}: Opposite direction active")
                return False
        
        for sig in reversed(self.sent_signals):
            if sig['asset'] == asset:
                if (datetime.now() - sig['timestamp']).seconds < 3600:
                    logger.warning(f"🚫 {asset}: 60min cooldown")
                    return False
                break
        
        if asset in self.active_trades and entry_price:
            last = self.active_trades[asset]
            if abs(entry_price - last) / last < 0.005:
                logger.warning(f"🚫 {asset}: Price too close")
                return False
        
        return True
    
    def record_signal(self, asset: str, direction: str, entry_price: float):
        self.daily_signals[asset] = self.daily_signals.get(asset, 0) + 1
        self.active_directions[asset] = direction
        self.active_trades[asset] = entry_price
        self.sent_signals.append({
            'asset': asset,
            'direction': direction,
            'entry_price': entry_price,
            'timestamp': datetime.now()
        })
        logger.info(f"✅ Recorded: {asset} {direction} @ {entry_price}")
    
    def close_trade(self, asset: str):
        if asset in self.active_directions:
            del self.active_directions[asset]
        if asset in self.active_trades:
            del self.active_trades[asset]
    
    def filter_correlated_signals(self, signals: List[TradingSignal]) -> List[TradingSignal]:
        if not signals:
            return []
        best = max(signals, key=lambda x: x.total_score)
        return [best]
    
    def calculate_position_size(self, asset: str, entry: float, stop: float,
                               risk_level: str = 'normal') -> float:
        account = self.config.get('account_size', 100000)
        risk_pct = self.config.get('default_risk_per_trade', 0.01)
        risk_amount = account * risk_pct
        
        if entry == 0 or stop == 0:
            return 0.1
        
        stop_distance = abs(entry - stop) / entry
        notional = risk_amount / stop_distance
        
        risk_multipliers = {
            'normal': 1.0,
            'high': 0.5,
            'extreme': 0.25
        }
        mult = risk_multipliers.get(risk_level, 1.0)
        
        if 'BTC' in asset:
            contracts = (notional / entry) * mult
            return round(contracts, 3)
        elif 'ETH' in asset:
            contracts = (notional / entry) * mult * 10
            return round(contracts, 2)
        
        return round((notional / entry) * mult, 2)
