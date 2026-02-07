"""
Alpha Score Calculator - FIXED with Realistic Caps
"""

from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)

class AlphaScorer:
    def __init__(self, config: Dict):
        self.config = config
        self.weights = {
            'microstructure': 0.40,
            'greeks': 0.20,
            'liquidity': 0.20,
            'momentum': 0.15,
            'sentiment': 0.05
        }
        # REMOVED: self.consecutive_passes = 0 (was unused)
    
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
        
        # Time multiplier (reduced)
        time_multiplier = 1.0
        if time_quality == "excellent":
            time_multiplier = 1.03
        elif time_quality == "good":
            time_multiplier = 1.01
        elif time_quality == "moderate":
            time_multiplier = 0.97
        elif time_quality == "avoid":
            time_multiplier = 0.85
        
        total *= time_multiplier
        
        # News multiplier
        if news_status == "extreme_event":
            total *= 0.30
        
        # HARD CAP at 95 - 100 impossible to prevent overfitting
        total = min(95, max(0, total))
        
        # Quality grading
        if total >= 92:
            confidence = 'exceptional'
            recommendation = 'strong_take'
            setup_quality = 'institutional_grade'
        elif total >= 87:
            confidence = 'exceptional'
            recommendation = 'take'
            setup_quality = 'professional_grade'
        elif total >= 82:
            confidence = 'high'
            recommendation = 'take'
            setup_quality = 'standard'
        elif total >= 78:
            confidence = 'medium'
            recommendation = 'consider'
            setup_quality = 'standard'
        else:
            confidence = 'low'
            recommendation = 'pass'
            setup_quality = 'below_standard'
        
        return {
            'total_score': round(total, 1),
            'confidence': confidence,
            'recommendation': recommendation,
            'setup_quality': setup_quality,
            'component_scores': scores,
            'threshold_used': self.config.get('min_score_threshold', 82),
            'time_multiplier': time_multiplier,
        }
    
    def _score_microstructure(self, setup: Dict, data: Dict) -> float:
        """Capped at 90 - no perfect scores"""
        score = 70  # Base
        rationale = setup.get('rationale', {})
        
        ofi = abs(rationale.get('ofi_ratio', 0))
        if ofi > 0.6:
            score += 12
        elif ofi > 0.4:
            score += 8
        elif ofi > 0.2:
            score += 4
        
        cvd = rationale.get('cvd_delta', 0)
        direction = setup.get('direction', 'long')
        
        if isinstance(cvd, (int, float)):
            cvd_val = cvd
        else:
            cvd_val = cvd.get('cvd', 0) if isinstance(cvd, dict) else 0
        
        if direction == 'long' and cvd_val > 0:
            score += 8
        elif direction == 'short' and cvd_val < 0:
            score += 8
        
        signal_type = rationale.get('signal_type', '')
        if 'sweep' in signal_type:
            score += 4
        
        # Alignment bonus
        if (direction == 'long' and ofi > 0.2) or (direction == 'short' and ofi < -0.2):
            score += 3
        
        return min(90, score)  # HARD CAP
    
    def _score_greeks(self, setup: Dict, data: Dict) -> float:
        score = 70
        expiry = setup.get('expiry_suggestion', '')
        if '24' in expiry or '48' in expiry:
            score += 12
        if 'gamma' in setup.get('strategy', ''):
            score += 6
        return min(88, score)
    
    def _score_liquidity(self, setup: Dict, data: Dict) -> float:
        score = 72
        ob = data.get('orderbook', {})
        
        spread_pct = ob.get('spread_pct', 0.1)
        if spread_pct < 0.015:
            score += 16
        elif spread_pct < 0.03:
            score += 12
        elif spread_pct < 0.05:
            score += 6
        
        if ob.get('bid_walls') or ob.get('ask_walls'):
            score += 4
        
        return min(92, score)
    
    def _score_momentum(self, setup: Dict, data: Dict) -> float:
        score = 68
        funding = data.get('funding_rate', 0)
        direction = setup.get('direction', 'long')
        
        if direction == 'long' and funding < -0.001:
            score += 18
        elif direction == 'long' and funding < -0.0005:
            score += 12
        elif direction == 'short' and funding > 0.001:
            score += 18
        elif direction == 'short' and funding > 0.0005:
            score += 12
        
        return min(86, score)
    
    def _score_sentiment(self, setup: Dict, data: Dict) -> float:
        score = 65
        ob = data.get('orderbook', {})
        
        buy_pressure = ob.get('bid_pressure', 0)
        ask_pressure = ob.get('ask_pressure', 0)
        total_pressure = buy_pressure + ask_pressure
        
        # FIX: Handle zero total pressure
        if total_pressure == 0:
            return 65  # Neutral score
        
        buy_pct = (buy_pressure / total_pressure) * 100
        direction = setup.get('direction', 'long')
        
        if direction == 'long' and buy_pct > 60:
            score += 18
        elif direction == 'long' and buy_pct > 52:
            score += 10
        elif direction == 'short' and buy_pct < 40:
            score += 18
        elif direction == 'short' and buy_pct < 48:
            score += 10
        
        return min(83, score)
