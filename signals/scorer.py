"""
Alpha Score Calculator
"""

from typing import Dict, Optional  # FIXED: Added Optional
import logging

logger = logging.getLogger(__name__)

class AlphaScorer:
    def __init__(self, config: Dict):
        self.config = config
        self.weights = {
            'microstructure': 0.35,
            'greeks': 0.25,
            'liquidity': 0.20,
            'momentum': 0.12,
            'sentiment': 0.08
        }
    
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
            time_multiplier = 1.05
        elif time_quality == "moderate":
            time_multiplier = 0.95
        elif time_quality == "avoid":
            time_multiplier = 0.80
        
        total *= time_multiplier
        
        # News multiplier
        news_multiplier = 1.0
        if news_status == "extreme_event":
            news_multiplier = 0.50
        
        total *= news_multiplier
        total = min(100, max(0, total))
        
        if total >= 90:
            confidence = 'exceptional'
            recommendation = 'strong_take'
        elif total >= 85:
            confidence = 'high'
            recommendation = 'take'
        elif total >= 80:
            confidence = 'medium'
            recommendation = 'consider'
        else:
            confidence = 'low'
            recommendation = 'pass'
        
        return {
            'total_score': round(total, 1),
            'confidence': confidence,
            'recommendation': recommendation,
            'component_scores': scores,
        }
    
    def _score_microstructure(self, setup: Dict, data: Dict) -> float:
        score = 60
        rationale = setup.get('rationale', {})
        
        ofi = abs(rationale.get('ofi_ratio', 0))
        score += min(20, ofi * 50)
        
        cvd = rationale.get('cvd_delta', 0)
        if setup.get('direction') == 'long' and cvd > 0:
            score += 15
        elif setup.get('direction') == 'short' and cvd < 0:
            score += 15
        
        return min(100, score)
    
    def _score_greeks(self, setup: Dict, data: Dict) -> float:
        score = 65
        expiry = setup.get('expiry_suggestion', '')
        if '24' in expiry or '48' in expiry:
            score += 10
        return min(100, score)
    
    def _score_liquidity(self, setup: Dict, data: Dict) -> float:
        score = 55
        ob = data.get('orderbook', {})
        
        spread_pct = ob.get('spread_pct', 0.1)
        if spread_pct < 0.03:
            score += 30
        elif spread_pct < 0.05:
            score += 20
        
        return min(100, score)
    
    def _score_momentum(self, setup: Dict, data: Dict) -> float:
        score = 55
        funding = data.get('funding_rate', 0)
        direction = setup.get('direction', 'long')
        
        if direction == 'long' and funding < -0.0005:
            score += 30
        elif direction == 'short' and funding > 0.0005:
            score += 30
        
        return min(100, score)
    
    def _score_sentiment(self, setup: Dict, data: Dict) -> float:
        score = 60
        ob = data.get('orderbook', {})
        
        buy_pressure = ob.get('bid_pressure', 0)
        ask_pressure = ob.get('ask_pressure', 0)
        total_pressure = buy_pressure + ask_pressure
        
        if total_pressure > 0:
            buy_pct = (buy_pressure / total_pressure) * 100
            direction = setup.get('direction', 'long')
            
            if direction == 'long' and buy_pct > 60:
                score += 25
            elif direction == 'short' and buy_pct < 40:
                score += 25
        
        return min(100, score)
