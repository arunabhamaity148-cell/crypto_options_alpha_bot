"""
Alpha Score Calculator - FIXED VERSION
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
        
        # Time multiplier
        time_multiplier = 1.0
        if time_quality == "excellent":
            time_multiplier = 1.05  # Reduced from 1.08
        elif time_quality == "good":
            time_multiplier = 1.02
        elif time_quality == "moderate":
            time_multiplier = 0.95
        
        total *= time_multiplier
        
        # News multiplier
        if news_status == "extreme_event":
            total *= 0.30
        
        total = min(100, max(0, total))
        
        # FIXED: Proper quality grading
        if total >= 95:
            confidence = 'exceptional'
            recommendation = 'strong_take'
            setup_quality = 'institutional_grade'
        elif total >= 90:
            confidence = 'exceptional'
            recommendation = 'strong_take'
            setup_quality = 'professional_grade'
        elif total >= 85:
            confidence = 'high'
            recommendation = 'take'
            setup_quality = 'professional_grade'
        elif total >= 82:
            confidence = 'medium'
            recommendation = 'take'
            setup_quality = 'standard'
        else:
            confidence = 'low'
            recommendation = 'pass'
            setup_quality = 'standard'
        
        return {
            'total_score': round(total, 1),
            'confidence': confidence,
            'recommendation': recommendation,
            'setup_quality': setup_quality,  # FIXED
            'component_scores': scores,
            'threshold_used': self.config.get('min_score_threshold', 82),
        }
    
    def _score_microstructure(self, setup: Dict, data: Dict) -> float:
        score = 72
        rationale = setup.get('rationale', {})
        
        ofi = abs(rationale.get('ofi_ratio', 0))
        if ofi > 0.5:
            score += 12
        elif ofi > 0.3:
            score += 8
        elif ofi > 0.15:
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
            score += 3
        
        return min(95, score)  # HARD CAP
    
    def _score_greeks(self, setup: Dict, data: Dict) -> float:
        score = 70
        expiry = setup.get('expiry_suggestion', '')
        if '24' in expiry or '48' in expiry:
            score += 10
        if 'gamma' in setup.get('strategy', ''):
            score += 5
        return min(90, score)
    
    def _score_liquidity(self, setup: Dict, data: Dict) -> float:
        score = 70
        ob = data.get('orderbook', {})
        
        spread_pct = ob.get('spread_pct', 0.1)
        if spread_pct < 0.02:
            score += 20
        elif spread_pct < 0.04:
            score += 15
        elif spread_pct < 0.06:
            score += 8
        
        if ob.get('bid_walls') or ob.get('ask_walls'):
            score += 3
        
        return min(95, score)
    
    def _score_momentum(self, setup: Dict, data: Dict) -> float:
        score = 68
        funding = data.get('funding_rate', 0)
        direction = setup.get('direction', 'long')
        
        if direction == 'long' and funding < -0.0008:
            score += 20
        elif direction == 'long' and funding < -0.0005:
            score += 12
        elif direction == 'short' and funding > 0.0008:
            score += 20
        elif direction == 'short' and funding > 0.0005:
            score += 12
        
        return min(88, score)
    
    def _score_sentiment(self, setup: Dict, data: Dict) -> float:
        score = 65
        ob = data.get('orderbook', {})
        
        buy_pressure = ob.get('bid_pressure', 0)
        ask_pressure = ob.get('ask_pressure', 0)
        total_pressure = buy_pressure + ask_pressure
        
        if total_pressure > 0:
            buy_pct = (buy_pressure / total_pressure) * 100
            direction = setup.get('direction', 'long')
            
            if direction == 'long' and buy_pct > 65:
                score += 20
            elif direction == 'long' and buy_pct > 55:
                score += 12
            elif direction == 'short' and buy_pct < 35:
                score += 20
            elif direction == 'short' and buy_pct < 45:
                score += 12
        
        return min(85, score)
