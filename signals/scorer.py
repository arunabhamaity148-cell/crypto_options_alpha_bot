"""
Alpha Score Calculator - Enhanced for High Quality Signals
"""

from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)

class AlphaScorer:
    def __init__(self, config: Dict):
        self.config = config
        # Adjusted weights for better signal quality
        self.weights = {
            'microstructure': 0.40,  # Increased (was 0.35)
            'greeks': 0.20,          # Decreased (was 0.25)
            'liquidity': 0.20,       # Same
            'momentum': 0.15,        # Increased (was 0.12)
            'sentiment': 0.05        # Decreased (was 0.08)
        }
        self.consecutive_passes = 0
    
    def calculate_score(self, setup: Dict, market_data: Dict, 
                       news_status: str = "safe",
                       time_quality: str = "excellent") -> Dict:
        scores = {}
        
        scores['microstructure'] = self._score_microstructure(setup, market_data)
        scores['greeks'] = self._score_greeks(setup, market_data)
        scores['liquidity'] = self._score_liquidity(setup, market_data)
        scores['momentum'] = self._score_momentum(setup, market_data)
        scores['sentiment'] = self._score_sentiment(setup, market_data)
        
        total = sum(scores[k] * self.weights[k] for k in scores)
        
        # Adaptive time multiplier
        time_multiplier = 1.0
        if time_quality == "excellent":
            time_multiplier = 1.08
        elif time_quality == "good":
            time_multiplier = 1.03
        elif time_quality == "moderate":
            time_multiplier = 0.95
        elif time_quality == "avoid":
            time_multiplier = 0.75
        
        total *= time_multiplier
        
        # News multiplier
        news_multiplier = 1.0
        if news_status == "extreme_event":
            news_multiplier = 0.30  # Heavy penalty
        
        total *= news_multiplier
        total = min(100, max(0, total))
        
        # Adaptive threshold logic
        base_threshold = self.config.get('min_score_threshold', 82)
        if self.config.get('adaptive_threshold', False):
            if self.consecutive_passes >= 3:
                base_threshold = max(78, base_threshold - 2)  # Lower slightly
                logger.info(f"Adaptive threshold: {base_threshold} (consecutive passes: {self.consecutive_passes})")
        
        # Quality grading
        if total >= 90:
            confidence = 'exceptional'
            recommendation = 'strong_take'
            self.consecutive_passes = 0
        elif total >= base_threshold:
            confidence = 'high'
            recommendation = 'take'
            self.consecutive_passes = 0
        elif total >= base_threshold - 5:
            confidence = 'medium'
            recommendation = 'consider'
            self.consecutive_passes += 1
        else:
            confidence = 'low'
            recommendation = 'pass'
            self.consecutive_passes += 1
        
        return {
            'total_score': round(total, 1),
            'confidence': confidence,
            'recommendation': recommendation,
            'component_scores': scores,
            'threshold_used': base_threshold,
            'time_multiplier': time_multiplier,
        }
    
    def _score_microstructure(self, setup: Dict, data: Dict) -> float:
        # Enhanced base score with better OFI detection
        score = 72  # Increased from 60
        rationale = setup.get('rationale', {})
        
        # OFI scoring - more aggressive
        ofi = abs(rationale.get('ofi_ratio', 0))
        if ofi > 0.5:
            score += 20
        elif ofi > 0.3:
            score += 15
        elif ofi > 0.15:
            score += 8
        
        # CVD confirmation
        cvd = rationale.get('cvd_delta', 0)
        direction = setup.get('direction', 'long')
        
        if direction == 'long' and cvd > 0:
            score += 12
        elif direction == 'short' and cvd < 0:
            score += 12
        elif cvd != 0:  # Wrong direction but some activity
            score -= 5
        
        # Signal type bonus
        signal_type = rationale.get('signal_type', '')
        if 'sweep' in signal_type:
            score += 5  # Liquidity sweep bonus
        
        return min(100, score)
    
    def _score_greeks(self, setup: Dict, data: Dict) -> float:
        score = 70  # Increased from 65
        expiry = setup.get('expiry_suggestion', '')
        
        # Optimal expiry bonus
        if '24' in expiry or '48' in expiry:
            score += 15
        
        # Gamma squeeze bonus
        if 'gamma' in setup.get('strategy', ''):
            score += 10
        
        return min(100, score)
    
    def _score_liquidity(self, setup: Dict, data: Dict) -> float:
        score = 70  # Increased from 55
        ob = data.get('orderbook', {})
        
        spread_pct = ob.get('spread_pct', 0.1)
        
        # Tighter spread = better
        if spread_pct < 0.02:
            score += 25
        elif spread_pct < 0.04:
            score += 18
        elif spread_pct < 0.06:
            score += 10
        
        # Wall presence bonus
        if ob.get('bid_walls') or ob.get('ask_walls'):
            score += 5
        
        return min(100, score)
    
    def _score_momentum(self, setup: Dict, data: Dict) -> float:
        score = 68  # Increased from 55
        funding = data.get('funding_rate', 0)
        direction = setup.get('direction', 'long')
        
        # Extreme funding = contrarian opportunity
        if direction == 'long' and funding < -0.0008:
            score += 25
        elif direction == 'long' and funding < -0.0005:
            score += 18
        elif direction == 'short' and funding > 0.0008:
            score += 25
        elif direction == 'short' and funding > 0.0005:
            score += 18
        
        # Basis (spot-perp spread)
        spot = data.get('spot_price', 0)
        perp = data.get('perp_price', 0)
        if spot and perp:
            basis = (perp - spot) / spot
            if direction == 'long' and basis < -0.0005:
                score += 10
            elif direction == 'short' and basis > 0.0005:
                score += 10
        
        return min(100, score)
    
    def _score_sentiment(self, setup: Dict, data: Dict) -> float:
        score = 65  # Increased from 60
        ob = data.get('orderbook', {})
        
        buy_pressure = ob.get('bid_pressure', 0)
        ask_pressure = ob.get('ask_pressure', 0)
        total_pressure = buy_pressure + ask_pressure
        
        if total_pressure > 0:
            buy_pct = (buy_pressure / total_pressure) * 100
            direction = setup.get('direction', 'long')
            
            if direction == 'long' and buy_pct > 65:
                score += 25
            elif direction == 'long' and buy_pct > 55:
                score += 15
            elif direction == 'short' and buy_pct < 35:
                score += 25
            elif direction == 'short' and buy_pct < 45:
                score += 15
        
        return min(100, score)
