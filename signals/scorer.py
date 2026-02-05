"""
Alpha Score Calculator
Combines all unique factors into single score
Includes News Guard and Time Filter adjustments
"""

from typing import Dict
import logging

logger = logging.getLogger(__name__)

class AlphaScorer:
    """Proprietary scoring algorithm with news and time adjustments"""
    
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
        """
        Calculate comprehensive alpha score with all adjustments
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
        
        # Base weighted total
        total = sum(scores[k] * self.weights[k] for k in scores)
        
        # TIME FILTER PENALTY/BONUS
        time_multiplier = 1.0
        time_note = ""
        
        if time_quality == "excellent":
            time_multiplier = 1.05  # 5% bonus
            time_note = "Excellent timing +5%"
        elif time_quality == "moderate":
            time_multiplier = 0.95  # 5% penalty
            time_note = "Moderate timing -5%"
        elif time_quality == "avoid":
            time_multiplier = 0.80  # 20% penalty
            time_note = "Poor timing -20%"
        
        total *= time_multiplier
        
        # NEWS GUARD PENALTY
        news_multiplier = 1.0
        news_note = ""
        
        if news_status == "extreme_event":
            news_multiplier = 0.50  # 50% penalty
            news_note = "🛑 EXTREME NEWS - Score halved!"
        elif news_status == "high_impact":
            news_multiplier = 0.70  # 30% penalty
            news_note = "⚠️ High impact news -30%"
        elif news_status == "volatility_spike":
            news_multiplier = 0.80  # 20% penalty
            news_note = "⚡ Volatility spike -20%"
        elif news_status == "funding_reset":
            news_multiplier = 0.90  # 10% penalty
            news_note = "⏰ Funding reset time -10%"
        else:
            news_note = "✅ No news concerns"
        
        total *= news_multiplier
        
        # Final score cap
        total = min(100, max(0, total))
        
        # Confidence level
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
        
        # Adjust recommendation based on news/time
        if news_status == "extreme_event" and total < 50:
            recommendation = "avoid"
        if time_quality == "avoid" and total < 70:
            recommendation = "avoid"
        
        return {
            'total_score': round(total, 1),
            'confidence': confidence,
            'recommendation': recommendation,
            'component_scores': scores,
            'setup_quality': self._assess_quality(total, news_status, time_quality),
            'time_adjustment': time_note,
            'news_adjustment': news_note,
            'raw_score': round(total / (time_multiplier * news_multiplier), 1) if (time_multiplier * news_multiplier) > 0 else 0
        }
    
    def _score_microstructure(self, setup: Dict, data: Dict) -> float:
        """Score order flow and microstructure"""
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
        
        # Signal type bonus
        signal_type = rationale.get('signal_type', '')
        if 'sweep' in signal_type:
            score += 5  # Liquidity sweeps are reliable
        
        return min(100, score)
    
    def _score_greeks(self, setup: Dict, data: Dict) -> float:
        """Score options Greeks alignment"""
        score = 65
        
        rationale = setup.get('rationale', {})
        
        # Gamma wall presence
        if 'gamma_wall' in rationale:
            score += 20
        
        # IV check (prefer low IV for buying)
        # Would need IV data
        
        # Time to expiry (prefer 24-72h)
        expiry = setup.get('expiry_suggestion', '')
        if '24' in expiry or '48' in expiry:
            score += 10
        elif '72' in expiry:
            score += 5
        
        return min(100, score)
    
    def _score_liquidity(self, setup: Dict, data: Dict) -> float:
        """Score liquidity conditions"""
        score = 55
        
        ob = data.get('orderbook', {})
        
        # Spread tightness
        spread_pct = ob.get('spread_pct', 0.1)
        if spread_pct < 0.03:
            score += 30
        elif spread_pct < 0.05:
            score += 20
        elif spread_pct < 0.1:
            score += 10
        else:
            score -= 10  # Wide spread penalty
        
        # Wall strength
        bid_walls = ob.get('bid_walls', [])
        ask_walls = ob.get('ask_walls', [])
        
        if len(bid_walls) > 0 or len(ask_walls) > 0:
            score += 10
        
        # Liquidity hunt quality
        if ob.get('liquidity_voids_below') or ob.get('liquidity_voids_above'):
            score += 5
        
        return min(100, max(0, score))
    
    def _score_momentum(self, setup: Dict, data: Dict) -> float:
        """Score momentum alignment"""
        score = 55
        
        # Funding rate check
        funding = data.get('funding_rate', 0)
        direction = setup.get('direction', 'long')
        
        # Contrarian bonus (trade against extreme funding)
        if direction == 'long' and funding < -0.0005:
            score += 30  # Extreme negative funding = long opportunity
        elif direction == 'short' and funding > 0.0005:
            score += 30  # Extreme positive funding = short opportunity
        elif abs(funding) < 0.0001:
            score += 15  # Neutral funding
        else:
            score += 5  # Mild funding against us
        
        # Basis check
        spot = data.get('spot_price', 0)
        perp = data.get('perp_price', 0)
        
        if spot > 0 and perp > 0:
            basis = (perp - spot) / spot
            
            if direction == 'long' and basis < -0.001:
                score += 10  # Perp discount = bullish
            elif direction == 'short' and basis > 0.002:
                score += 10  # Perp premium = bearish
        
        return min(100, score)
    
    def _score_sentiment(self, setup: Dict, data: Dict) -> float:
        """Score market sentiment"""
        score = 60
        
        ob = data.get('orderbook', {})
        
        # Buy/sell pressure
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
            elif direction == 'long' and buy_pct > 55:
                score += 15
            elif direction == 'short' and buy_pct < 45:
                score += 15
        
        # Open interest trend (would need historical)
        
        return min(100, score)
    
    def _assess_quality(self, score: float, news_status: str, time_quality: str) -> str:
        """Assess overall setup quality"""
        
        if score >= 90 and news_status == "safe" and time_quality == "excellent":
            return 'institutional_grade'
        elif score >= 85 and news_status in ["safe", "funding_reset"]:
            return 'professional_grade'
        elif score >= 80:
            return 'standard'
        elif score >= 70:
            return 'marginal'
        else:
            return 'poor'
    
    def get_component_breakdown(self, scores: Dict) -> str:
        """Format component scores for display"""
        lines = []
        for component, score in scores.items():
            bar = "█" * int(score / 5) + "░" * (20 - int(score / 5))
            lines.append(f"{component:15} | {bar} | {score:.0f}/100")
        return "\n".join(lines)
