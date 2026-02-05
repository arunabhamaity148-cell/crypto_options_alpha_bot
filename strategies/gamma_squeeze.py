"""
Strategy 2: Gamma Squeeze Detection
Exploits market maker hedging pressure
"""

from typing import Dict, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class GammaSqueezeStrategy:
    """
    Detects gamma squeeze setups
    Unique edge: Real-time gamma exposure calculation
    """
    
    def __init__(self, greeks_engine, config: Dict):
        self.greeks = greeks_engine
        self.config = config
        self.min_score = config.get('min_score_threshold', 85)
        
    async def analyze(self, data: Dict, options_chain: List[Dict]) -> Optional[Dict]:
        """
        Analyze gamma squeeze probability
        """
        try:
            spot = data.get('liquidity_data', {}).get('current_price', 0)
            if spot == 0 or not options_chain:
                return None
            
            # Calculate time to expiry (assume 7 days for weekly)
            time_to_expiry = 7 / 365
            
            # Get gamma exposure data
            gamma_data = self.greeks.calculate_gamma_exposure(spot, options_chain, time_to_expiry)
            
            # Check for squeeze setup
            squeeze = self.greeks.get_gamma_squeeze_probability(gamma_data, spot, 0.05)
            
            if squeeze.get('squeeze_probability') not in ['high', 'medium']:
                return None
            
            # Confirm with price action
            if not self._confirm_squeeze(squeeze, data):
                return None
            
            return self._build_setup(squeeze, gamma_data, spot, data)
            
        except Exception as e:
            logger.error(f"Gamma squeeze analysis error: {e}")
            return None
    
    def _confirm_squeeze(self, squeeze: Dict, data: Dict) -> bool:
        """Confirm gamma squeeze with market data"""
        
        direction = squeeze.get('direction')
        
        # Check order flow alignment
        ofi = data.get('ofi_data', {})
        ofi_score = ofi.get('ofi_score', 0)
        
        if direction == 'up' and ofi_score < 0:
            return False  # OFI bearish, skip
        if direction == 'down' and ofi_score > 0:
            return False  # OFI bullish, skip
        
        # Check volume
        cvd = data.get('cvd_data', {})
        if cvd.get('buy_pressure_pct', 50) < 40 and direction == 'up':
            return False
        if cvd.get('buy_pressure_pct', 50) > 60 and direction == 'down':
            return False
        
        return True
    
    def _build_setup(self, squeeze: Dict, gamma_data: Dict, spot: float, data: Dict) -> Dict:
        """Build trade setup"""
        
        direction = squeeze.get('direction')
        magnet = squeeze.get('magnet_price', spot)
        acceleration = squeeze.get('acceleration_zone', (spot, spot))
        
        if direction == 'up':
            entry = spot
            stop = min(acceleration[0], spot * 0.985)
            target_1 = magnet
            target_2 = squeeze.get('potential_target', magnet * 1.02)
            option_type = 'CE'
        else:
            entry = spot
            stop = max(acceleration[1], spot * 1.015)
            target_1 = magnet
            target_2 = squeeze.get('potential_target', magnet * 0.98)
            option_type = 'PE'
        
        # Score calculation
        score = 75 if squeeze.get('squeeze_probability') == 'high' else 80
        score += 10 if squeeze.get('gamma_acceleration') else 0
        
        return {
            'strategy': 'gamma_squeeze',
            'direction': direction,
            'entry_price': round(entry, 2),
            'stop_loss': round(stop, 2),
            'target_1': round(target_1, 2),
            'target_2': round(target_2, 2),
            'confidence': min(100, score),
            'expiry_suggestion': '24-48h',
            'strike_selection': f"{round(magnet/100)*100} {option_type}",
            'rationale': {
                'gamma_wall': magnet,
                'distance_to_wall': squeeze.get('distance_to_gamma_wall'),
                'acceleration_zone': acceleration,
                'total_gamma': gamma_data.get('total_gamma'),
                'squeeze_probability': squeeze.get('squeeze_probability')
            }
        }
