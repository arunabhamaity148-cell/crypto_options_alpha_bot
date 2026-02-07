"""
Liquidity Hunt Strategy with Real Options Validation - FIXED
"""

from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)

class LiquidityHuntStrategy:
    def __init__(self, asset: str, config: Dict):
        self.asset = asset
        self.config = config
        self.min_score = config.get('min_score_threshold', 85)
        # FIX: Configurable IV thresholds for crypto
        self.max_iv = config.get('max_iv', 150)  # Crypto can have high IV
        self.min_iv = config.get('min_iv', 15)
    
    async def analyze(self, market_data: Dict, recent_trades: list) -> Optional[Dict]:
        from indicators.microstructure import MicrostructureAnalyzer
        
        orderbook = market_data.get('orderbook', {})
        current_price = market_data.get('current_price', 0)
        options_data = market_data.get('options_data', {})
        
        if not orderbook or not current_price:
            return None
        
        # FIX: Validate with options data based on direction
        if options_data:
            direction = self._preliminary_direction(orderbook)
            validation = self._validate_with_options(options_data, current_price, direction)
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
            direction = setup.get('direction', 'long')
            option_key = 'call' if direction == 'long' else 'put'
            option_data = options_data.get(option_key, {})
            
            setup['options_validation'] = {
                'iv': option_data.get('iv', 0),
                'premium': option_data.get('mark_price', 0),
                'delta': option_data.get('delta', 0),
                'oi': option_data.get('oi', 0),
            }
        
        return setup
    
    def _preliminary_direction(self, orderbook: Dict) -> str:
        """Get preliminary direction from orderbook"""
        ofi = orderbook.get('ofi_ratio', 0)
        return 'long' if ofi > 0 else 'short'
    
    def _validate_with_options(self, options_data: Dict, spot_price: float, direction: str) -> Dict:
        """Validate signal with real options data - FIX: Check both call and put"""
        
        # FIX: Use appropriate option type based on direction
        option_key = 'call' if direction == 'long' else 'put'
        option_data = options_data.get(option_key, {})
        
        if not option_data:
            return {'valid': True, 'reason': f'No {option_key} options data, using spot only'}
        
        iv = option_data.get('iv', 0)
        premium = option_data.get('mark_price', 0)
        delta = option_data.get('delta', 0.5)
        
        # FIX: Configurable IV check
        if iv > self.max_iv:
            return {'valid': False, 'reason': f'IV too high: {iv}% (max {self.max_iv}%)'}
        
        if iv < self.min_iv:
            return {'valid': False, 'reason': f'IV too low: {iv}% (min {self.min_iv}%)'}
        
        if premium < 5:
            return {'valid': False, 'reason': f'Premium too low: ${premium}'}
        
        # FIX: Check delta direction
        if direction == 'long' and delta < 0.3:
            return {'valid': False, 'reason': f'Call delta too low: {delta} (far OTM)'}
        elif direction == 'short' and delta > -0.3:
            return {'valid': False, 'reason': f'Put delta too high: {delta} (far OTM)'}
        
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
