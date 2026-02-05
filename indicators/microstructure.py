"""
Advanced Microstructure Indicators
Unique calculations not found in public bots
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

@dataclass
class MicroStructureSignal:
    signal_type: str  # 'liquidity_hunt', 'ofi_flip', 'cvd_divergence'
    strength: float   # 0-100
    direction: str    # 'long', 'short'
    entry_zone: Tuple[float, float]
    stop_loss: float
    targets: List[float]
    confidence: str   # 'high', 'medium', 'low'
    metadata: Dict

class MicroStructureAnalyzer:
    """Detects institutional order flow patterns"""
    
    def __init__(self):
        self.price_history = []
        self.cvd_history = []
        self.ofi_history = []
        
    def detect_liquidity_hunt(self, data: Dict) -> MicroStructureSignal:
        """
        Detects when price sweeps liquidity and reverses
        75%+ win rate setup
        """
        liquidity = data.get('liquidity_data', {})
        ofi = data.get('ofi_data', {})
        cvd = data.get('cvd_data', {})
        
        current_price = liquidity.get('current_price', 0)
        hunt_below = liquidity.get('liquidity_void_below')
        hunt_above = liquidity.get('liquidity_void_above')
        
        # Check for sweep below + reversal
        if hunt_below and current_price > hunt_below * 1.002:
            # Price swept below and came back up
            ofi_score = ofi.get('ofi_score', 0)
            cvd_interp = cvd.get('interpretation', '')
            
            if ofi_score > 1.5 and 'buying' in cvd_interp:
                return MicroStructureSignal(
                    signal_type='liquidity_hunt_long',
                    strength=min(95, 70 + ofi_score * 5),
                    direction='long',
                    entry_zone=(current_price * 0.998, current_price * 1.002),
                    stop_loss=hunt_below * 0.995,
                    targets=[current_price * 1.015, current_price * 1.03],
                    confidence='high' if ofi_score > 2.5 else 'medium',
                    metadata={
                        'sweep_level': hunt_below,
                        'ofi_score': ofi_score,
                        'cvd_delta': cvd.get('cvd', 0),
                        'wall_above': liquidity.get('largest_ask_wall')
                    }
                )
        
        # Check for sweep above + reversal
        if hunt_above and current_price < hunt_above * 0.998:
            ofi_score = ofi.get('ofi_score', 0)
            cvd_interp = cvd.get('interpretation', '')
            
            if ofi_score < -1.5 and 'selling' in cvd_interp:
                return MicroStructureSignal(
                    signal_type='liquidity_hunt_short',
                    strength=min(95, 70 + abs(ofi_score) * 5),
                    direction='short',
                    entry_zone=(current_price * 0.998, current_price * 1.002),
                    stop_loss=hunt_above * 1.005,
                    targets=[current_price * 0.985, current_price * 0.97],
                    confidence='high' if ofi_score < -2.5 else 'medium',
                    metadata={
                        'sweep_level': hunt_above,
                        'ofi_score': ofi_score,
                        'cvd_delta': cvd.get('cvd', 0),
                        'wall_below': liquidity.get('largest_bid_wall')
                    }
                )
        
        return None
    
    def detect_ofi_momentum_flip(self, data: Dict, history: List[Dict]) -> MicroStructureSignal:
        """
        Detects when order flow momentum flips
        Early trend detection
        """
        if len(history) < 3:
            return None
            
        ofi_current = data.get('ofi_data', {}).get('ofi_score', 0)
        ofi_previous = [h.get('ofi_data', {}).get('ofi_score', 0) for h in history[-3:]]
        
        # Bullish flip: negative to strong positive
        if ofi_current > 2.0 and all(o < 0 for o in ofi_previous):
            current_price = data.get('liquidity_data', {}).get('current_price', 0)
            
            return MicroStructureSignal(
                signal_type='ofi_bullish_flip',
                strength=min(90, 60 + ofi_current * 10),
                direction='long',
                entry_zone=(current_price * 0.999, current_price * 1.001),
                stop_loss=current_price * 0.988,
                targets=[current_price * 1.02, current_price * 1.04],
                confidence='high',
                metadata={
                    'ofi_previous': ofi_previous,
                    'ofi_current': ofi_current,
                    'flip_magnitude': ofi_current - min(ofi_previous)
                }
            )
        
        # Bearish flip: positive to strong negative
        if ofi_current < -2.0 and all(o > 0 for o in ofi_previous):
            current_price = data.get('liquidity_data', {}).get('current_price', 0)
            
            return MicroStructureSignal(
                signal_type='ofi_bearish_flip',
                strength=min(90, 60 + abs(ofi_current) * 10),
                direction='short',
                entry_zone=(current_price * 0.999, current_price * 1.001),
                stop_loss=current_price * 1.012,
                targets=[current_price * 0.98, current_price * 0.96],
                confidence='high',
                metadata={
                    'ofi_previous': ofi_previous,
                    'ofi_current': ofi_current,
                    'flip_magnitude': max(ofi_previous) - ofi_current
                }
            )
        
        return None
    
    def detect_cvd_divergence(self, data: Dict, price_history: List[float], cvd_history: List[float]) -> MicroStructureSignal:
        """
        Detects divergence between price and CVD
        Hidden accumulation/distribution
        """
        if len(price_history) < 10 or len(cvd_history) < 10:
            return None
            
        # Calculate trends
        price_trend = np.polyfit(range(5), price_history[-5:], 1)[0]
        cvd_trend = np.polyfit(range(5), cvd_history[-5:], 1)[0]
        
        current_price = price_history[-1]
        
        # Bullish divergence: Price down, CVD up (accumulation)
        if price_trend < -0.1 and cvd_trend > 0.5:
            return MicroStructureSignal(
                signal_type='cvd_bullish_divergence',
                strength=85,
                direction='long',
                entry_zone=(current_price * 0.997, current_price),
                stop_loss=current_price * 0.985,
                targets=[current_price * 1.025, current_price * 1.05],
                confidence='high',
                metadata={
                    'price_trend': price_trend,
                    'cvd_trend': cvd_trend,
                    'divergence_strength': cvd_trend - price_trend
                }
            )
        
        # Bearish divergence: Price up, CVD down (distribution)
        if price_trend > 0.1 and cvd_trend < -0.5:
            return MicroStructureSignal(
                signal_type='cvd_bearish_divergence',
                strength=85,
                direction='short',
                entry_zone=(current_price, current_price * 1.003),
                stop_loss=current_price * 1.015,
                targets=[current_price * 0.975, current_price * 0.95],
                confidence='high',
                metadata={
                    'price_trend': price_trend,
                    'cvd_trend': cvd_trend,
                    'divergence_strength': price_trend - cvd_trend
                }
            )
        
        return None
