"""
Liquidity Hunt Strategy - Fixed with Real-Time Entry
"""

from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)

class LiquidityHuntStrategy:
    def __init__(self, asset: str, config: Dict):
        self.asset = asset
        self.config = config
        self.min_score = config.get('min_score_threshold', 85)
    
    async def analyze(self, market_data: Dict, recent_trades: list) -> Optional[Dict]:
        from indicators.microstructure import MicrostructureAnalyzer
        
        orderbook = market_data.get('orderbook', {})
        current_price = market_data.get('current_price', 0)
        
        if not orderbook or not current_price:
            return None
        
        analyzer = MicrostructureAnalyzer()
        signal = analyzer.analyze(self.asset, orderbook, recent_trades)
        
        if not signal or signal.strength < self.min_score:
            return None
        
        return self._build_setup(signal, market_data, current_price)
    
    def _build_setup(self, signal, data: Dict, current_price: float) -> Dict:
        """Build setup with REAL-TIME current price as entry"""
        direction = signal.direction
        
        step = self.config.get('strike_step', 100)
        
        # Use CURRENT real-time price for entry (not historical)
        entry = current_price
        
        # Round strike to nearest step
        if direction == 'long':
            strike = round((entry + step/2) / step) * step
            option_type = 'CE'
            stop = entry * 0.992  # 0.8% stop
            target1 = entry * 1.018  # 1.8% target
            target2 = entry * 1.030  # 3% target
        else:
            strike = round((entry - step/2) / step) * step
            option_type = 'PE'
            stop = entry * 1.008  # 0.8% stop
            target1 = entry * 0.982  # 1.8% target
            target2 = entry * 0.970  # 3% target
        
        return {
            'strategy': 'liquidity_hunt_reversal',
            'direction': direction,
            'entry_price': round(entry, 2),
            'stop_loss': round(stop, 2),
            'target_1': round(target1, 2),
            'target_2': round(target2, 2),
            'confidence': signal.strength,
            'strike_selection': f"{strike} {option_type}",
            'expiry_suggestion': '24-48h',
            'rationale': {
                'signal_type': signal.signal_type,
                'ofi_ratio': signal.metadata.get('ofi_ratio', 0),
                'cvd_delta': signal.metadata.get('cvd_delta', 0),
                **signal.metadata
            }
        }
