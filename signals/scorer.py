"""
Alpha Score Calculator
Combines all unique factors into single score
"""

from typing import Dict, List
import logging

logger = logging.getLogger(__name__)

class AlphaScorer:
    """
    Proprietary scoring algorithm
    Ensures only highest quality signals pass
    """
    
    def __init__(self, config: Dict):
        self.config = config
        self.weights = {
            'microstructure': 0.30,
            'greeks': 0.25,
            'liquidity': 0.20,
            'momentum': 0.15,
            'sentiment': 0.10
        }
        
    def calculate_score(self, setup: Dict, market_data: Dict) -> Dict:
        """
        Calculate comprehensive alpha score
        """
        scores = {}
        
        # 1. Microstructure Score (0-100)
        scores['microstructure'] = self._score_microstructure(setup, market_data)
        
        # 2. Greeks Score (0-100)
        scores['greeks'] = self._score_greeks(setup, market_data)
        
        # 3. Liquidity Score (0-100)
        scores['liquidity'] = self._score_liquidity(setup, market_data)
        
        # 4. Momentum Score (0-100)
        scores['momentum'] = self._score_momentum(setup, market_data)
        
        # 5. Sentiment Score (0-100)
        scores['sentiment'] = self._score_sentiment(setup, market_data)
        
        # Weighted total
        total_score = sum(
            scores[k] * self.weights[k] for k in scores
        )
        
        # Confidence level
        if total_score >= 90:
            confidence = 'exceptional'
        elif total_score >= 85:
            confidence = 'high'
        elif total_score >= 80:
            confidence = 'medium'
        else:
            confidence = 'low'
        
        return {
            'total_score': round(total_score, 1),
            'confidence': confidence,
            'component_scores': scores,
            'recommendation': 'strong_take' if total_score >= 90 else \
                            'take' if total_score >= 85 else \
                            'consider' if total_score >= 80 else 'pass',
            'setup_quality': self._assess_setup_quality(setup, total_score)
        }
    
    def _score_microstructure(self, setup: Dict, data: Dict) -> float:
        """Score order flow and microstructure"""
        score = 50
        
        # OFI strength
        ofi = abs(data.get('ofi_data', {}).get('ofi_score', 0))
        score += min(25, ofi * 5)
        
        # CVD confirmation
        cvd = data.get('cvd_data', {})
        if setup.get('direction') == 'long' and cvd.get('cvd', 0) > 0:
            score += 15
        elif setup.get('direction') == 'short' and cvd.get('cvd', 0) < 0:
            score += 15
        
        # Trade quality
        if 'aggressive' in cvd.get('interpretation', ''):
            score += 10
        
        return min(100, score)
    
    def _score_greeks(self, setup: Dict, data: Dict) -> float:
        """Score options Greeks alignment"""
        score = 60
        
        # IV rank check (prefer cheap options)
        # This would need IV history, assume neutral for now
        score += 10
        
        # Gamma squeeze potential
        if 'gamma_wall' in setup.get('rationale', {}):
            score += 20
        
        # Time to expiry (prefer 24-72h)
        expiry = setup.get('expiry_suggestion', '')
        if '24' in expiry or '48' in expiry:
            score += 10
        
        return min(100, score)
    
    def _score_liquidity(self, setup: Dict, data: Dict) -> float:
        """Score liquidity conditions"""
        score = 50
        
        liquidity = data.get('liquidity_data', {})
        
        # Spread tightness
        spread_pct = liquidity.get('spread_pct', 0.1)
        if spread_pct < 0.05:
            score += 20
        elif spread_pct < 0.1:
            score += 10
        
        # Wall strength
        walls = liquidity.get('bid_walls', []) + liquidity.get('ask_walls', [])
        if walls:
            score += 15
        
        # Liquidity hunt quality
        if liquidity.get('hunt_probability') == 'high':
            score += 15
        
        return min(100, score)
    
    def _score_momentum(self, setup: Dict, data: Dict) -> float:
        """Score momentum alignment"""
        score = 50
        
        # Basis/funding alignment
        basis = data.get('basis_data', {})
        funding = basis.get('funding_rate', 0)
        
        if setup.get('direction') == 'long' and funding < 0:
            score += 25  # Contrarian long, good
        elif setup.get('direction') == 'short' and funding > 0:
            score += 25  # Contrarian short, good
        else:
            score += 10  # Neutral
        
        # Basis extreme
        if abs(basis.get('basis', 0)) > 0.005:
            score += 15
        
        return min(100, score)
    
    def _score_sentiment(self, setup: Dict, data: Dict) -> float:
        """Score market sentiment"""
        score = 50
        
        # Whale activity would go here
        # For now, use CVD as proxy
        cvd = data.get('cvd_data', {})
        buy_pct = cvd.get('buy_pressure_pct', 50)
        
        if setup.get('direction') == 'long' and buy_pct > 55:
            score += 30
        elif setup.get('direction') == 'short' and buy_pct < 45:
            score += 30
        else:
            score += 10
        
        return min(100, score)
    
    def _assess_setup_quality(self, setup: Dict, score: float) -> str:
        """Additional quality assessment"""
        checks = []
        
        # Risk/Reward check
        risk = abs(setup.get('entry_price', 0) - setup.get('stop_loss', 0))
        reward = abs(setup.get('target_1', 0) - setup.get('entry_price', 0))
        
        if risk > 0 and reward / risk >= 1.5:
            checks.append('favorable_risk_reward')
        
        # Confluence check
        confluence_count = sum([
            'sweep' in setup.get('strategy', ''),
            'gamma' in setup.get('strategy', ''),
            'ofi' in str(setup.get('rationale', {}))
        ])
        
        if confluence_count >= 2:
            checks.append('multi_factor_confluence')
        
        if score >= 90 and len(checks) >= 2:
            return 'institutional_grade'
        elif score >= 85:
            return 'professional_grade'
        else:
            return 'standard'
