"""
Liquidity Hunt Strategy with Real Options Validation
"""

from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)

class LiquidityHuntStrategy:
    def __init__(self, asset: str, config: Dict):
        self.asset = asset
        self.config = config
        self.min_score = config.get('min_score_threshold', 85)
    
    async def analyze(self, market_data: Dict, recent_trades: list) -> Optional[Dict]:
        from indicators.microstructure import MicrostructureAnalyzer
        
        orderbook = market_data.get('orderbook', {})
        current_price = market_data.get('current_price', 0)
        options_data = market_data.get('options_data', {})
        
        if not orderbook or not current_price:
            return None
        
        # Validate with real options data (NEW)
        if options_data:
            validation = self._validate_with_options(options_data, current_price)
            if not validation['valid']:
                logger.warning(f"Options validation failed: {validation['reason']}")
                return None
        
        analyzer = MicrostructureAnalyzer()
        signal = analyzer.analyze(self.asset, orderbook, recent_trades)
        
        if not signal or signal.strength < self.min_score:
            return None
        
        setup = self._build_setup(signal, market_data, current_price)
        
        # Add real options info to setup
        if options_data:
            setup['options_validation'] = {
                'iv': options_data.get('call', {}).get('iv', 0),
                'premium': options_data.get('call', {}).get('mark_price', 0),
                'delta': options_data.get('call', {}).get('delta', 0),
                'oi': options_data.get('call', {}).get('oi', 0),
            }
        
        return setup
    
    def _validate_with_options(self, options_data: Dict, spot_price: float) -> Dict:
        """Validate signal with real options data"""
        
        call_data = options_data.get('call', {})
        
        if not call_data:
            return {'valid': True, 'reason': 'No options data, using spot only'}
        
        iv = call_data.get('iv', 0)
        premium = call_data.get('mark_price', 0)
        delta = call_data.get('delta', 0.5)
        
        # Check IV not too high
        if iv > 100:
            return {'valid': False, 'reason': f'IV too high: {iv}'}
        
        # Check IV not too low (illiquid)
        if iv < 20:
            return {'valid': False, 'reason': f'IV too low: {iv}, illiquid'}
        
        # Check premium reasonable
        if premium < 5:
            return {'valid': False, 'reason': f'Premium too low: {premium}'}
        
        # Check delta reasonable (not too far OTM)
        if abs(delta) < 0.3:
            return {'valid': False, 'reason': f'Delta too low: {delta}, far OTM'}
        
        return {'valid': True, 'reason': 'Options validation passed'}
    
    def _build_setup(self, signal, data: Dict, current_price: float) -> Optional[Dict]:
        """Build setup with validation"""
        
        direction = signal.direction
        
        if current_price <= 0:
            return None
        
        step = self.config.get('strike_step', 100)
        entry = current_price
        
        if direction == 'long':
            strike = round((entry + step/2) / step) * step
            option_type = 'CE'
            stop = entry * 0.992
            target1 = entry * 1.018
            target2 = entry * 1.030
        else:
            strike = round((entry - step/2) / step) * step
            option_type = 'PE'
            stop = entry * 1.008
            target1 = entry * 0.982
            target2 = entry * 0.970
        
        return {
            'strategy': 'liquidity_hunt_reversal',
            'direction': direction,
            'entry_price': round(entry, 2),
            'stop_loss': round(stop, 2),
            'target_1': round(target1, 2),
            'target_2': round(target2, 2),
            'confidence': signal.strength,
            'strike_selection': f"{strike} {option_type}",
            'expiry_suggestion': '24-48h',
            'rationale': {
                'signal_type': signal.signal_type,
                'ofi_ratio': signal.metadata.get('ofi_ratio', 0),
                'cvd_delta': signal.metadata.get('cvd_delta', 0),
            }
        }
