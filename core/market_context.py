"""
Market Context Analyzer
Prevents trading in bad market conditions
"""

import logging
from typing import Dict, List
from datetime import datetime

logger = logging.getLogger(__name__)

class MarketContext:
    def __init__(self):
        self.iv_threshold_high = 80
        self.iv_threshold_extreme = 120
        self.max_both_sides_bleeding = -30
        
    def analyze(self, market_data: Dict) -> Dict:
        """
        Analyze market context and return trading permission
        """
        context = {
            'trade_allowed': True,
            'risk_level': 'normal',
            'position_size_mult': 1.0,
            'reason': '',
            'recommendations': []
        }
        
        # Check 1: Both calls and puts bleeding (choppy market)
        both_bleeding = self._check_options_bleeding(market_data)
        if both_bleeding:
            context['trade_allowed'] = False
            context['reason'] = 'Both calls and puts bleeding - choppy market'
            context['recommendations'].append('Wait for directional clarity')
            return context
        
        # Check 2: Implied Volatility too high
        iv_check = self._check_iv_levels(market_data)
        if iv_check == 'extreme':
            context['risk_level'] = 'extreme'
            context['position_size_mult'] = 0.25
            context['recommendations'].append('IV extreme - 75% size reduction')
        elif iv_check == 'high':
            context['risk_level'] = 'high'
            context['position_size_mult'] = 0.5
            context['recommendations'].append('IV high - 50% size reduction')
        
        # Check 3: Funding rate extreme
        funding_check = self._check_funding(market_data)
        if funding_check == 'extreme':
            context['risk_level'] = 'extreme'
            context['position_size_mult'] *= 0.5
            context['recommendations'].append('Funding extreme - additional 50% reduction')
        
        # Check 4: Low liquidity
        if self._check_low_liquidity(market_data):
            context['trade_allowed'] = False
            context['reason'] = 'Low liquidity - wide spreads'
            return context
        
        # Check 5: Recent volatility spike
        if self._check_volatility_spike(market_data):
            context['risk_level'] = 'high'
            context['position_size_mult'] *= 0.7
            context['recommendations'].append('Recent volatility - 30% reduction')
        
        # Ensure multiplier doesn't go too low
        context['position_size_mult'] = max(context['position_size_mult'], 0.1)
        
        return context
    
    def _check_options_bleeding(self, data: Dict) -> bool:
        """Check if both calls and puts are down big"""
        # This would need options chain data
        # Simplified check using available data
        calls_change = data.get('calls_avg_change', -10)
        puts_change = data.get('puts_avg_change', -10)
        
        return calls_change < self.max_both_sides_bleeding and puts_change < self.max_both_sides_bleeding
    
    def _check_iv_levels(self, data: Dict) -> str:
        """Check implied volatility levels"""
        iv = data.get('implied_volatility', 50)
        
        if iv > self.iv_threshold_extreme:
            return 'extreme'
        elif iv > self.iv_threshold_high:
            return 'high'
        return 'normal'
    
    def _check_funding(self, data: Dict) -> str:
        """Check funding rate extremes"""
        funding = abs(data.get('funding_rate', 0))
        
        if funding > 0.001:  # 0.1%
            return 'extreme'
        elif funding > 0.0005:  # 0.05%
            return 'high'
        return 'normal'
    
    def _check_low_liquidity(self, data: Dict) -> bool:
        """Check for low liquidity conditions"""
        spread_pct = data.get('spread_pct', 0)
        return spread_pct > 0.1  # 10% spread = illiquid
    
    def _check_volatility_spike(self, data: Dict) -> bool:
        """Check for recent volatility spike"""
        recent_trades = data.get('recent_trades', [])
        if len(recent_trades) < 10:
            return False
        
        # Calculate recent volatility
        prices = [t.get('price', 0) for t in recent_trades[-10:]]
        if len(prices) < 2:
            return False
        
        returns = [abs(prices[i] - prices[i-1]) / prices[i-1] for i in range(1, len(prices))]
        avg_volatility = sum(returns) / len(returns)
        
        return avg_volatility > 0.002  # 0.2% average move = volatile
