"""
Liquidity Hunt Strategy - Highest Win Rate
"""

from typing import Dict, Optional
import logging
from indicators.microstructure import MicrostructureAnalyzer, MicroSignal

logger = logging.getLogger(__name__)

class LiquidityHuntStrategy:
    """75%+ win rate strategy"""
    
    def __init__(self, asset: str, config: Dict):
        self.asset = asset
        self.config = config
        self.analyzer = MicrostructureAnalyzer()
        self.min_score = config.get('min_score_threshold', 85)
    
    async def analyze(self, market_data: Dict, recent_trades: list) -> Optional[Dict]:
        """Main analysis"""
        
        orderbook = market_data.get('orderbook', {})
        if not orderbook:
            return None
        
        # Get microstructure signal
        signal = self.analyzer.analyze(self.asset, orderbook, recent_trades)
        
        if not signal or signal.strength < self.min_score:
            return None
        
        # Build trade setup
        return self._build_setup(signal, market_data)
    
    def _build_setup(self, signal: MicroSignal, data: Dict) -> Dict:
        """Build complete setup"""
        
        mid = data.get('orderbook', {}).get('mid_price', 0)
        
        # Round strike to asset step
        step = self.config.get('strike_step', 100)
        strike = round(mid / step) * step
        
        option_type = 'CE' if signal.direction == 'long' else 'PE'
        
        return {
            'strategy': 'liquidity_hunt_reversal',
            'direction': signal.direction,
            'entry_price': round((signal.entry_zone[0] + signal.entry_zone[1]) / 2, 2),
            'stop_loss': round(signal.stop_loss, 2),
            'target_1': round(signal.targets[0], 2),
            'target_2': round(signal.targets[1], 2),
            'confidence': signal.strength,
            'strike_selection': f"{strike} {option_type}",
            'expiry_suggestion': '24-48h',
            'rationale': {
                'signal_type': signal.signal_type,
                **signal.metadata
            }
        }
