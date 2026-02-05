"""
Gamma Squeeze Strategy
"""

from typing import Dict, Optional, List
import logging
from indicators.greeks_engine import GreeksEngine

logger = logging.getLogger(__name__)

class GammaSqueezeStrategy:
    """Exploits gamma hedging pressure"""
    
    def __init__(self, asset: str, config: Dict, greeks_engine: GreeksEngine):
        self.asset = asset
        self.config = config
        self.greeks = greeks_engine
        self.min_score = config.get('min_score_threshold', 85)
    
    async def analyze(self, market_data: Dict, options_chain: List[Dict]) -> Optional[Dict]:
        """Analyze gamma squeeze"""
        
        spot = market_data.get('orderbook', {}).get('mid_price', 0)
        if not spot or not options_chain:
            return None
        
        # Calculate gamma exposure
        time_to_expiry = 7 / 365  # Assume weekly
        gamma_data = self.greeks.calculate_gamma_exposure(spot, options_chain, time_to_expiry)
        
        # Check for squeeze setup
        squeeze = self.greeks.get_gamma_squeeze_setup(spot, gamma_data)
        
        if not squeeze or squeeze['strength'] < self.min_score:
            return None
        
        # Confirm with order flow
        ofi = market_data.get('orderbook', {}).get('ofi_ratio', 0)
        if squeeze['direction'] == 'long' and ofi < 0:
            return None
        if squeeze['direction'] == 'short' and ofi > 0:
            return None
        
        return self._build_setup(squeeze, spot, gamma_data)
    
    def _build_setup(self, squeeze: Dict, spot: float, gamma_data: Dict) -> Dict:
        """Build trade setup"""
        
        direction = squeeze['direction']
        magnet = squeeze['magnet_price']
        
        step = self.config.get('strike_step', 100)
        strike = round(magnet / step) * step
        option_type = 'CE' if direction == 'long' else 'PE'
        
        if direction == 'long':
            entry = spot
            stop = spot * 0.98
            target1 = magnet
            target2 = magnet + (magnet - spot) * 0.5
        else:
            entry = spot
            stop = spot * 1.02
            target1 = magnet
            target2 = magnet - (spot - magnet) * 0.5
        
        return {
            'strategy': 'gamma_squeeze',
            'direction': direction,
            'entry_price': round(entry, 2),
            'stop_loss': round(stop, 2),
            'target_1': round(target1, 2),
            'target_2': round(target2, 2),
            'confidence': squeeze['strength'],
            'strike_selection': f"{strike} {option_type}",
            'expiry_suggestion': '24-48h',
            'rationale': {
                'gamma_wall': magnet,
                'distance_to_wall': squeeze['distance'],
                'total_gamma': gamma_data['total_gamma'],
                'max_gamma_value': gamma_data['max_gamma_value']
            }
        }
