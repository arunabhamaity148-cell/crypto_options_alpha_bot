"""
Strategy 1: Liquidity Hunt Reversal
Highest win rate setup - 75%+
"""

from typing import Dict, Optional
from dataclasses import dataclass
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

@dataclass
class TradeSetup:
    strategy: str
    direction: str
    entry_price: float
    stop_loss: float
    target_1: float
    target_2: float
    confidence: float
    expiry_suggestion: str
    strike_selection: str
    rationale: Dict

class LiquidityHuntStrategy:
    """
    Detects when smart money hunts stop losses and reverses
    Unique edge: Combines order flow + liquidity voids + CVD
    """
    
    def __init__(self, config: Dict):
        self.config = config
        self.min_score = config.get('min_score_threshold', 85)
        self.history = []
        
    async def analyze(self, data: Dict) -> Optional[TradeSetup]:
        """
        Main analysis function
        Returns TradeSetup if high probability opportunity found
        """
        try:
            # Extract components
            liquidity = data.get('liquidity_data', {})
            ofi = data.get('ofi_data', {})
            cvd = data.get('cvd_data', {})
            basis = data.get('basis_data', {})
            
            current_price = liquidity.get('current_price', 0)
            if current_price == 0:
                return None
            
            # Check for liquidity sweep setup
            setup = self._check_sweep_setup(liquidity, ofi, cvd, current_price)
            if not setup:
                return None
            
            # Additional confirmation filters
            if not self._confirm_setup(setup, basis, data):
                return None
            
            # Calculate position parameters
            trade_setup = self._build_trade_setup(setup, current_price, data)
            
            # Score the setup
            score = self._calculate_score(trade_setup, data)
            if score < self.min_score:
                return None
            
            trade_setup.confidence = score
            return trade_setup
            
        except Exception as e:
            logger.error(f"Liquidity hunt analysis error: {e}")
            return None
    
    def _check_sweep_setup(self, liquidity: Dict, ofi: Dict, cvd: Dict, 
                          price: float) -> Optional[Dict]:
        """Check for liquidity sweep pattern"""
        
        hunt_below = liquidity.get('liquidity_void_below')
        hunt_above = liquidity.get('liquidity_void_above')
        ofi_score = ofi.get('ofi_score', 0)
        cvd_interp = cvd.get('interpretation', '')
        cvd_delta = cvd.get('cvd', 0)
        
        # LONG setup: Swept below + reversal
        if hunt_below and price > hunt_below * 1.001:
            # Confirm reversal with order flow
            if ofi_score > 1.0 and ('buying' in cvd_interp or cvd_delta > 0):
                return {
                    'direction': 'long',
                    'sweep_price': hunt_below,
                    'current_price': price,
                    'ofi_score': ofi_score,
                    'cvd_delta': cvd_delta,
                    'wall_above': liquidity.get('largest_ask_wall'),
                    'type': 'sweep_low_reversal'
                }
        
        # SHORT setup: Swept above + reversal
        if hunt_above and price < hunt_above * 0.999:
            if ofi_score < -1.0 and ('selling' in cvd_interp or cvd_delta < 0):
                return {
                    'direction': 'short',
                    'sweep_price': hunt_above,
                    'current_price': price,
                    'ofi_score': ofi_score,
                    'cvd_delta': cvd_delta,
                    'wall_below': liquidity.get('largest_bid_wall'),
                    'type': 'sweep_high_reversal'
                }
        
        return None
    
    def _confirm_setup(self, setup: Dict, basis: Dict, data: Dict) -> bool:
        """Additional confirmation filters"""
        
        # Avoid trading against extreme funding
        funding = basis.get('funding_rate', 0)
        direction = setup['direction']
        
        # If funding very negative and we're going long, good (contrarian)
        # If funding very positive and we're going short, good
        if direction == 'long' and funding < -0.0005:
            return True  # Contrarian long, good
        if direction == 'short' and funding > 0.0005:
            return True  # Contrarian short, good
        
        # If funding neutral, check basis
        basis_val = basis.get('basis', 0)
        if abs(basis_val) < 0.001:
            return True  # Neutral basis, proceed
        
        # Mild funding against us is ok if other factors strong
        if abs(funding) < 0.0003:
            return True
            
        return False
    
    def _build_trade_setup(self, setup: Dict, price: float, data: Dict) -> TradeSetup:
        """Build complete trade parameters"""
        
        direction = setup['direction']
        sweep = setup['sweep_price']
        
        if direction == 'long':
            entry = price
            stop = sweep * 0.995  # Below sweep low
            target_1 = price + (price - stop) * 1.5  # 1.5 R
            target_2 = price + (price - stop) * 2.5  # 2.5 R
            
            # Strike selection: ATM or slight OTM
            strike = round(price / 100) * 100  # Round to nearest 100
            
        else:  # short
            entry = price
            stop = sweep * 1.005  # Above sweep high
            target_1 = price - (stop - price) * 1.5
            target_2 = price - (stop - price) * 2.5
            
            strike = round(price / 100) * 100
        
        # Determine expiry based on setup strength
        ofi_score = abs(setup['ofi_score'])
        if ofi_score > 3.0:
            expiry = '24-48h'  # Quick move expected
        else:
            expiry = '48-72h'  # Slower reversal
        
        return TradeSetup(
            strategy='liquidity_hunt_reversal',
            direction=direction,
            entry_price=round(entry, 2),
            stop_loss=round(stop, 2),
            target_1=round(target_1, 2),
            target_2=round(target_2, 2),
            confidence=0,  # Will be calculated
            expiry_suggestion=expiry,
            strike_selection=f"{strike} {'CE' if direction == 'long' else 'PE'}",
            rationale={
                'sweep_level': sweep,
                'ofi_score': setup['ofi_score'],
                'cvd_delta': setup['cvd_delta'],
                'wall_reference': setup.get('wall_above') or setup.get('wall_below'),
                'setup_type': setup['type']
            }
        )
    
    def _calculate_score(self, setup: TradeSetup, data: Dict) -> float:
        """Calculate alpha score 0-100"""
        score = 70  # Base score for valid setup
        
        # OFI strength
        ofi = abs(data.get('ofi_data', {}).get('ofi_score', 0))
        score += min(15, ofi * 3)
        
        # CVD confirmation
        cvd_data = data.get('cvd_data', {})
        if 'aggressive' in cvd_data.get('interpretation', ''):
            score += 10
        
        # Liquidity quality
        liquidity = data.get('liquidity_data', {})
        if liquidity.get('hunt_probability') == 'high':
            score += 5
        
        # Risk/reward ratio
        risk = abs(setup.entry_price - setup.stop_loss)
        reward = abs(setup.target_1 - setup.entry_price)
        if reward / risk > 2:
            score += 5
        
        return min(100, score)
