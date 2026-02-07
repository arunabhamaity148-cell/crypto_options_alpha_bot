"""
Gamma Squeeze Strategy - FIXED
"""

from typing import Dict, Optional, List
import logging

logger = logging.getLogger(__name__)

class GammaSqueezeStrategy:
    def __init__(self, asset: str, config: Dict, greeks_engine):
        self.asset = asset
        self.config = config
        self.greeks = greeks_engine
        self.min_score = config.get('min_score_threshold', 85)
    
    async def analyze(self, market_data: Dict, options_chain: List[Dict]) -> Optional[Dict]:
        spot = market_data.get('orderbook', {}).get('mid_price', 0)
        if not spot or not options_chain:
            return None
        
        # FIX: Use actual expiry instead of hardcoded 7 days
        time_to_expiry = self._calculate_time_to_expiry(options_chain)
        if time_to_expiry <= 0:
            time_to_expiry = 7 / 365  # Fallback
        
        gamma_data = self.greeks.calculate_gamma_exposure(spot, options_chain, time_to_expiry)
        
        squeeze = self.greeks.get_gamma_squeeze_setup(spot, gamma_data)
        
        if not squeeze or squeeze['strength'] < self.min_score:
            return None
        
        ofi = market_data.get('orderbook', {}).get('ofi_ratio', 0)
        if squeeze['direction'] == 'long' and ofi < 0:
            return None
        if squeeze['direction'] == 'short' and ofi > 0:
            return None
        
        return self._build_setup(squeeze, spot, gamma_data)
    
    def _calculate_time_to_expiry(self, options_chain: List[Dict]) -> float:
        """FIX: Calculate actual time to expiry from options chain"""
        from datetime import datetime
        
        if not options_chain:
            return 7 / 365
        
        # Find nearest expiry
        expiries = []
        for opt in options_chain:
            expiry_str = opt.get('expiry_date') or opt.get('expiry')
            if expiry_str:
                try:
                    expiry = datetime.fromisoformat(expiry_str.replace('Z', '+00:00'))
                    days_to_expiry = (expiry - datetime.now(timezone.utc)).days
                    if days_to_expiry > 0:
                        expiries.append(days_to_expiry)
                except:
                    pass
        
        if expiries:
            nearest = min(expiries)
            return nearest / 365
        
        return 7 / 365  # Default 7 days
    
    def _build_setup(self, squeeze: Dict, spot: float, gamma_data: Dict) -> Optional[Dict]:
        direction = squeeze['direction']
        magnet = squeeze['magnet_price']
        
        # FIX: Validate magnet price
        if direction == 'long' and magnet <= spot:
            logger.warning(f"Invalid gamma squeeze: magnet {magnet} <= spot {spot}")
            return None
        elif direction == 'short' and magnet >= spot:
            logger.warning(f"Invalid gamma squeeze: magnet {magnet} >= spot {spot}")
            return None
        
        step = self.config.get('strike_step', 100)
        strike = round(magnet / step) * step
        option_type = 'CE' if direction == 'long' else 'PE'
        
        if direction == 'long':
            entry = spot
            stop = spot * 0.98
            # FIX: Ensure target1 > entry
            target1 = max(magnet, entry * 1.01)
            target2 = target1 + (target1 - entry) * 0.5
        else:
            entry = spot
            stop = spot * 1.02
            # FIX: Ensure target1 < entry
            target1 = min(magnet, entry * 0.99)
            target2 = target1 - (entry - target1) * 0.5
        
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
            }
        }
