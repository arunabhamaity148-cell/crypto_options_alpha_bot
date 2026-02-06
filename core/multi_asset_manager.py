"""
Multi-Asset Manager
"""

import logging
from typing import Dict, List
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
        
    def should_reset_daily(self) -> bool:
        return (datetime.now() - self.last_reset).days >= 1
    
    def reset_daily_counters(self):
        self.daily_signals = {asset: 0 for asset in self.active_assets}
        self.last_reset = datetime.now()
        self.sent_signals = []
        logger.info("Daily counters reset")
    
    def can_send_signal(self, asset: str) -> bool:
        max_per_asset = self.config.get('max_signals_per_asset', 2)
        return self.daily_signals.get(asset, 0) < max_per_asset
    
    def record_signal(self, asset: str):
        self.daily_signals[asset] = self.daily_signals.get(asset, 0) + 1
        self.sent_signals.append({
            'asset': asset,
            'timestamp': datetime.now()
        })
    
    def filter_correlated_signals(self, signals: List[TradingSignal]) -> List[TradingSignal]:
        if len(signals) <= 1:
            return signals
        
        sorted_signals = sorted(signals, key=lambda x: x.confidence, reverse=True)
        
        filtered = []
        selected_assets = set()
        
        for signal in sorted_signals:
            asset = signal.asset
            
            is_correlated = False
            for selected in selected_assets:
                pair = tuple(sorted([asset, selected]))
                corr = self.CORRELATIONS.get(pair, 0.5)
                
                if corr > self.config.get('correlation_threshold', 0.8):
                    logger.info(f"Skipping {asset} - correlated with {selected} ({corr:.0%})")
                    is_correlated = True
                    break
            
            if not is_correlated:
                filtered.append(signal)
                selected_assets.add(asset)
        
        return filtered
    
    def calculate_position_size(self, asset: str, entry: float, stop: float) -> float:
        account = self.config.get('account_size', 100000)
        risk_pct = self.config.get('default_risk_per_trade', 0.01)
        
        regime = self.assets_config.get(asset, {}).get('volatility_regime', 'medium')
        multipliers = {'medium': 1.0, 'high': 0.8, 'very_high': 0.6}
        adj = multipliers.get(regime, 1.0)
        
        risk_amount = account * risk_pct * adj
        
        if entry == 0 or stop == 0:
            return 0
        
        risk_per_unit = abs(entry - stop) / entry
        position = risk_amount / (risk_per_unit * entry)
        
        min_qty = self.assets_config.get(asset, {}).get('min_quantity', 0.001)
        return round(position / min_qty) * min_qty
