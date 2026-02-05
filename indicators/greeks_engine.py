"""
Options Greeks Calculator
Real-time gamma exposure analysis
"""

import numpy as np
from scipy.stats import norm
from typing import Dict, List, Tuple
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

@dataclass
class GreeksData:
    delta: float
    gamma: float
    theta: float
    vega: float
    iv: float

class GreeksEngine:
    """Calculates option Greeks and gamma exposure"""
    
    def __init__(self):
        self.risk_free_rate = 0.05  # 5% annual
        
    def calculate_greeks(self, S: float, K: float, T: float, 
                        r: float, sigma: float, option_type: str = 'call') -> GreeksData:
        """
        Black-Scholes Greeks calculation
        
        S: Spot price
        K: Strike price
        T: Time to expiry (years)
        r: Risk-free rate
        sigma: Implied volatility
        """
        try:
            d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
            d2 = d1 - sigma * np.sqrt(T)
            
            if option_type == 'call':
                delta = norm.cdf(d1)
                theta = (-S * norm.pdf(d1) * sigma / (2 * np.sqrt(T)) - 
                        r * K * np.exp(-r * T) * norm.cdf(d2)) / 365
            else:
                delta = norm.cdf(d1) - 1
                theta = (-S * norm.pdf(d1) * sigma / (2 * np.sqrt(T)) + 
                        r * K * np.exp(-r * T) * norm.cdf(-d2)) / 365
            
            gamma = norm.pdf(d1) / (S * sigma * np.sqrt(T))
            vega = S * norm.pdf(d1) * np.sqrt(T) / 100
            
            return GreeksData(
                delta=round(delta, 4),
                gamma=round(gamma, 6),
                theta=round(theta, 4),
                vega=round(vega, 4),
                iv=round(sigma, 4)
            )
            
        except Exception as e:
            logger.error(f"Greeks calculation error: {e}")
            return GreeksData(0, 0, 0, 0, 0)
    
    def calculate_gamma_exposure(self, spot: float, strikes: List[Dict], 
                                time_to_expiry: float) -> Dict:
        """
        Calculate total gamma exposure by strike
        Identifies gamma walls and flip points
        """
        try:
            gamma_by_strike = {}
            total_gamma = 0
            
            for strike_data in strikes:
                strike = strike_data['strike']
                call_oi = strike_data.get('call_oi', 0)
                put_oi = strike_data.get('put_oi', 0)
                call_iv = strike_data.get('call_iv', 0.5)
                put_iv = strike_data.get('put_iv', 0.5)
                
                # Calculate gamma for calls and puts
                call_greeks = self.calculate_greeks(spot, strike, time_to_expiry, 
                                                   self.risk_free_rate, call_iv, 'call')
                put_greeks = self.calculate_greeks(spot, strike, time_to_expiry, 
                                                  self.risk_free_rate, put_iv, 'put')
                
                # Weight by open interest
                call_gamma_exposure = call_greeks.gamma * call_oi * spot
                put_gamma_exposure = put_greeks.gamma * put_oi * spot
                
                total_strike_gamma = call_gamma_exposure + put_gamma_exposure
                gamma_by_strike[strike] = total_strike_gamma
                total_gamma += total_strike_gamma
            
            # Find gamma walls (highest exposure)
            sorted_gamma = sorted(gamma_by_strike.items(), key=lambda x: x[1], reverse=True)
            
            # Find zero gamma crossing (flip point)
            spot_gamma = gamma_by_strike.get(spot, 0)
            
            # Calculate gamma-weighted average strike (magnet)
            if total_gamma > 0:
                gamma_weighted_price = sum(k * g for k, g in gamma_by_strike.items()) / total_gamma
            else:
                gamma_weighted_price = spot
            
            return {
                'total_gamma': total_gamma,
                'gamma_walls': sorted_gamma[:5],
                'max_gamma_strike': sorted_gamma[0][0] if sorted_gamma else spot,
                'max_gamma_value': sorted_gamma[0][1] if sorted_gamma else 0,
                'gamma_flip_point': self._find_flip_point(gamma_by_strike, spot),
                'gamma_weighted_price': gamma_weighted_price,
                'spot_gamma_exposure': spot_gamma,
                'gamma_by_strike': gamma_by_strike
            }
            
        except Exception as e:
            logger.error(f"Gamma exposure error: {e}")
            return {}
    
    def _find_flip_point(self, gamma_by_strike: Dict, spot: float) -> float:
        """Find price where gamma exposure flips sign"""
        strikes = sorted(gamma_by_strike.keys())
        if not strikes:
            return spot
            
        # Find strike closest to spot with highest gamma
        closest_strike = min(strikes, key=lambda x: abs(x - spot))
        return closest_strike
    
    def get_gamma_squeeze_probability(self, gamma_data: Dict, spot: float, 
                                     price_change: float) -> Dict:
        """
        Calculate probability of gamma squeeze
        """
        try:
            max_gamma_strike = gamma_data.get('max_gamma_strike', spot)
            max_gamma = gamma_data.get('max_gamma_value', 0)
            
            distance_to_wall = abs(spot - max_gamma_strike) / spot
            
            # If close to gamma wall and gamma is high, squeeze likely
            if distance_to_wall < 0.02 and max_gamma > 1000000:
                squeeze_prob = 'high'
                direction = 'up' if spot < max_gamma_strike else 'down'
            elif distance_to_wall < 0.05 and max_gamma > 500000:
                squeeze_prob = 'medium'
                direction = 'up' if spot < max_gamma_strike else 'down'
            else:
                squeeze_prob = 'low'
                direction = 'neutral'
            
            # Calculate acceleration zone
            if direction == 'up':
                acceleration_zone = (spot, max_gamma_strike)
                target = max_gamma_strike + (max_gamma_strike - spot) * 0.5
            elif direction == 'down':
                acceleration_zone = (max_gamma_strike, spot)
                target = max_gamma_strike - (spot - max_gamma_strike) * 0.5
            else:
                acceleration_zone = (spot * 0.98, spot * 1.02)
                target = spot
            
            return {
                'squeeze_probability': squeeze_prob,
                'direction': direction,
                'distance_to_gamma_wall': distance_to_wall,
                'acceleration_zone': acceleration_zone,
                'magnet_price': max_gamma_strike,
                'potential_target': target,
                'gamma_acceleration': max_gamma > 2000000
            }
            
        except Exception as e:
            logger.error(f"Gamma squeeze error: {e}")
            return {}
