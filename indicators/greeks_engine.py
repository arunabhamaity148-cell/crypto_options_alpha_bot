"""
Options Greeks Calculation for Crypto
"""

import numpy as np
from scipy.stats import norm
from typing import Dict, List, Tuple
import logging

logger = logging.getLogger(__name__)

class GreeksEngine:
    """Calculate option Greeks and gamma exposure"""
    
    def __init__(self, risk_free_rate: float = 0.05):
        self.r = risk_free_rate
    
    def calculate_greeks(self, S: float, K: float, T: float, 
                        sigma: float, option_type: str = 'call') -> Dict:
        """Black-Scholes Greeks"""
        
        try:
            d1 = (np.log(S / K) + (self.r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
            d2 = d1 - sigma * np.sqrt(T)
            
            if option_type == 'call':
                delta = norm.cdf(d1)
                theta = (-S * norm.pdf(d1) * sigma / (2 * np.sqrt(T)) - 
                        self.r * K * np.exp(-self.r * T) * norm.cdf(d2)) / 365
            else:
                delta = norm.cdf(d1) - 1
                theta = (-S * norm.pdf(d1) * sigma / (2 * np.sqrt(T)) + 
                        self.r * K * np.exp(-self.r * T) * norm.cdf(-d2)) / 365
            
            gamma = norm.pdf(d1) / (S * sigma * np.sqrt(T))
            vega = S * norm.pdf(d1) * np.sqrt(T) / 100
            
            return {
                'delta': round(delta, 4),
                'gamma': round(gamma, 6),
                'theta': round(theta, 4),
                'vega': round(vega, 4),
                'iv': round(sigma, 4)
            }
            
        except Exception as e:
            logger.error(f"Greeks calc error: {e}")
            return {'delta': 0, 'gamma': 0, 'theta': 0, 'vega': 0, 'iv': 0}
    
    def calculate_gamma_exposure(self, spot: float, strikes: List[Dict], 
                                time_to_expiry: float) -> Dict:
        """Calculate total gamma exposure by strike"""
        
        gamma_by_strike = {}
        total_gamma = 0
        
        for strike_data in strikes:
            K = strike_data['strike']
            call_oi = strike_data.get('call_oi', 0)
            put_oi = strike_data.get('put_oi', 0)
            call_iv = strike_data.get('call_iv', 0.5)
            put_iv = strike_data.get('put_iv', 0.5)
            
            # Calculate gamma
            call_greeks = self.calculate_greeks(spot, K, time_to_expiry, call_iv, 'call')
            put_greeks = self.calculate_greeks(spot, K, time_to_expiry, put_iv, 'put')
            
            # Weight by open interest
            call_gamma_exposure = call_greeks['gamma'] * call_oi * spot
            put_gamma_exposure = put_greeks['gamma'] * put_oi * spot
            
            total_strike_gamma = call_gamma_exposure + put_gamma_exposure
            gamma_by_strike[K] = total_strike_gamma
            total_gamma += total_strike_gamma
        
        # Find gamma walls
        sorted_gamma = sorted(gamma_by_strike.items(), key=lambda x: x[1], reverse=True)
        
        return {
            'total_gamma': total_gamma,
            'gamma_walls': sorted_gamma[:5],
            'max_gamma_strike': sorted_gamma[0][0] if sorted_gamma else spot,
            'max_gamma_value': sorted_gamma[0][1] if sorted_gamma else 0,
            'gamma_by_strike': gamma_by_strike
        }
    
    def get_gamma_squeeze_setup(self, spot: float, gamma_data: Dict) -> Optional[Dict]:
        """Detect gamma squeeze opportunity"""
        
        max_gamma_strike = gamma_data.get('max_gamma_strike', spot)
        max_gamma = gamma_data.get('max_gamma_value', 0)
        
        distance = abs(spot - max_gamma_strike) / spot
        
        # High gamma wall nearby
        if distance < 0.03 and max_gamma > 100000:
            direction = 'up' if spot < max_gamma_strike else 'down'
            
            return {
                'type': 'gamma_squeeze',
                'direction': direction,
                'magnet_price': max_gamma_strike,
                'distance': distance,
                'strength': min(95, 80 + (0.03 - distance) * 500),
                'acceleration_zone': (spot, max_gamma_strike) if direction == 'up' else (max_gamma_strike, spot)
            }
        
        return None
