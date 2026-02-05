"""
Alpha Score Calculator
"""

from typing import Dict

class AlphaScorer:
    """Proprietary scoring algorithm"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.weights = {
            'microstructure': 0.35,
            'greeks': 0.25,
            'liquidity': 0.20,
            'momentum': 0.12,
            'sentiment': 0.08
        }
    
    def calculate_score(self, setup: Dict, market_data: Dict) -> Dict:
        """Calculate comprehensive score"""
        
        scores = {}
        
        # Component scores
        scores['microstructure'] = self._score_microstructure(setup, market_data)
        scores['greeks'] = self._score_greeks(setup, market_data)
        scores['liquidity'] = self._score_liquidity(setup, market_data)
        scores['momentum'] = self._score_momentum(setup, market_data)
        scores['sentiment'] = self._score_sentiment(setup, market_data)
        
        # Weighted total
        total = sum(scores[k] * self.weights[k] for k in scores)
        
        # Confidence level
        if total >= 90:
            confidence = 'exceptional'
        elif total >= 85:
            confidence = 'high'
        elif total >= 80:
            confidence = 'medium'
        else:
            confidence = 'low'
        
        return {
            'total_score': round(total, 1),
            'confidence': confidence,
            'recommendation': 'strong_take' if total >= 90 else 'take' if total >= 85 else 'pass',
            'component_scores': scores,
            'setup_quality': 'institutional' if total >= 90 else 'professional' if total >= 85 else 'standard'
        }
    
    def _score_microstructure(self, setup: Dict, data: Dict) -> float:
        score = 60
        rationale = setup.get('rationale', {})
        
        # OFI strength
        ofi = abs(rationale.get('ofi_ratio', 0))
        score += min(20, ofi * 50)
        
        # CVD confirmation
        cvd = rationale.get('cvd_delta', 0)
        if setup.get('direction') == 'long' and cvd > 0:
            score += 15
        elif setup.get('direction') == 'short' and cvd < 0:
            score += 15
        
        return min(100, score)
    
    def _score_greeks(self, setup: Dict, data: Dict) -> float:
        score = 65
        if 'gamma_wall' in setup.get('rationale', {}):
            score += 25
        return min(100, score)
    
    def _score_liquidity(self, setup: Dict, data: Dict) -> float:
        score = 60
        ob = data.get('orderbook', {})
        
        spread = ob.get('spread_pct', 0.1)
        if spread < 0.05:
            score += 25
        elif spread < 0.1:
            score += 15
        
        return min(100, score)
    
    def _score_momentum(self, setup: Dict, data: Dict) -> float:
        score = 55
        # Funding rate check
        funding = data.get('funding_rate', 0)
        if setup.get('direction') == 'long' and funding < 0:
            score += 30
        elif setup.get('direction') == 'short' and funding > 0:
            score += 30
        return min(100, score)
    
    def _score_sentiment(self, setup: Dict, data: Dict) -> float:
        score = 60
        ob = data.get('orderbook', {})
        pressure = ob.get('buy_pressure_pct', 50)
        
        if setup.get('direction') == 'long' and pressure > 55:
            score += 30
        elif setup.get('direction') == 'short' and pressure < 45:
            score += 30
        return min(100, score)
