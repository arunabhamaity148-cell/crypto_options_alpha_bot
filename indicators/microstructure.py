"""
Microstructure Analysis - Fixed & Enhanced
OFI, CVD, Liquidity - High Quality Signal Focus
"""

from typing import Dict, Optional, List
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

@dataclass
class MicroSignal:
    signal_type: str
    direction: str
    strength: float
    entry_zone: tuple
    stop_loss: float
    targets: List[float]
    metadata: Dict

class MicrostructureAnalyzer:
    def analyze(self, asset: str, orderbook: Dict, recent_trades: List[Dict]) -> Optional[MicroSignal]:
        if not orderbook or not recent_trades:
            return None
        
        cvd_data = self._calculate_cvd(recent_trades, orderbook.get('mid_price', 0))
        ofi = orderbook.get('ofi_ratio', 0)
        
        # Priority: Liquidity sweep first (higher quality)
        sweep = self._detect_liquidity_sweep(orderbook, cvd_data, ofi)
        if sweep and sweep['strength'] >= 80:
            return self._build_signal(asset, sweep, ofi, cvd_data, orderbook)
        
        # Secondary: OFI flip
        flip = self._detect_ofi_flip(ofi, cvd_data, orderbook)
        if flip and flip['strength'] >= 75:
            return self._build_flip_signal(asset, flip, orderbook)
        
        return None
    
    def _calculate_cvd(self, trades: List[Dict], mid_price: float) -> Dict:
        """Fixed CVD calculation - correct is_buyer_maker interpretation"""
        buy_volume = 0
        sell_volume = 0
        
        for trade in trades:
            price = float(trade.get('price', 0))
            qty = float(trade.get('qty', 0))
            # FIXED: Correct interpretation
            # is_buyer_maker=True: Buyer is maker (passive) = Seller is aggressive (market sell)
            # is_buyer_maker=False: Seller is maker (passive) = Buyer is aggressive (market buy)
            is_buyer_maker = trade.get('is_buyer_maker', trade.get('m', False))
            
            if is_buyer_maker:
                # Seller aggressive = Sell pressure
                sell_volume += qty * price
            else:
                # Buyer aggressive = Buy pressure
                buy_volume += qty * price
        
        total = buy_volume + sell_volume
        cvd = buy_volume - sell_volume
        
        return {
            'cvd': cvd,
            'buy_volume': buy_volume,
            'sell_volume': sell_volume,
            'delta_ratio': cvd / total if total > 0 else 0,
            'buy_pressure_pct': (buy_volume / total * 100) if total > 0 else 50,
        }
    
    def _detect_liquidity_sweep(self, orderbook: Dict, cvd: Dict, ofi: float) -> Optional[Dict]:
        """Enhanced sweep detection with OFI confirmation"""
        mid = orderbook.get('mid_price', 0)
        if not mid:
            return None
        
        # Get walls (not voids - walls are what we have)
        bid_walls = orderbook.get('bid_walls', [])
        ask_walls = orderbook.get('ask_walls', [])
        
        # Detect sweep below bid walls
        if bid_walls and cvd.get('delta_ratio', 0) > 0.15:
            wall_price = bid_walls[0][0]
            # Price near or below wall with CVD positive = absorption
            if mid <= wall_price * 1.003 and mid >= wall_price * 0.995:
                # OFI confirmation
                ofi_boost = min(10, abs(ofi) * 20) if ofi > 0 else 0
                
                return {
                    'type': 'sweep_low',
                    'sweep_price': wall_price,
                    'direction': 'long',
                    'strength': min(95, 75 + cvd.get('delta_ratio', 0) * 40 + ofi_boost)
                }
        
        # Detect sweep above ask walls
        if ask_walls and cvd.get('delta_ratio', 0) < -0.15:
            wall_price = ask_walls[0][0]
            if mid >= wall_price * 0.997 and mid <= wall_price * 1.005:
                ofi_boost = min(10, abs(ofi) * 20) if ofi < 0 else 0
                
                return {
                    'type': 'sweep_high',
                    'sweep_price': wall_price,
                    'direction': 'short',
                    'strength': min(95, 75 + abs(cvd.get('delta_ratio', 0)) * 40 + ofi_boost)
                }
        
        return None
    
    def _detect_ofi_flip(self, ofi: float, cvd: Dict, orderbook: Dict) -> Optional[Dict]:
        """Enhanced OFI flip with CVD confirmation"""
        if abs(ofi) < 0.25:  # Lowered threshold from 0.3
            return None
        
        # CVD must confirm direction
        cvd_delta = cvd.get('delta_ratio', 0)
        
        if ofi > 0 and cvd_delta > 0:  # Bullish alignment
            return {
                'type': 'ofi_extreme',
                'direction': 'long',
                'strength': min(90, 70 + abs(ofi) * 60 + cvd_delta * 20)
            }
        elif ofi < 0 and cvd_delta < 0:  # Bearish alignment
            return {
                'type': 'ofi_extreme',
                'direction': 'short',
                'strength': min(90, 70 + abs(ofi) * 60 + abs(cvd_delta) * 20)
            }
        
        return None
    
    def _build_signal(self, asset: str, sweep: Dict, ofi: float, cvd: Dict, ob: Dict) -> MicroSignal:
        direction = sweep['direction']
        mid = ob.get('mid_price', 0)
        sweep_price = sweep['sweep_price']
        
        # Tighter stops for higher quality
        if direction == 'long':
            entry = mid
            stop = sweep_price * 0.992  # Tighter (was 0.995)
            target1 = mid + (mid - stop) * 2.0  # Better R:R (was 1.5)
            target2 = mid + (mid - stop) * 3.5  # Extended (was 2.5)
        else:
            entry = mid
            stop = sweep_price * 1.008  # Tighter
            target1 = mid - (stop - mid) * 2.0
            target2 = mid - (stop - mid) * 3.5
        
        return MicroSignal(
            signal_type=f"liquidity_{sweep['type']}",
            direction=direction,
            strength=sweep['strength'],
            entry_zone=(entry * 0.999, entry * 1.001),
            stop_loss=stop,
            targets=[target1, target2],
            metadata={
                'ofi_ratio': ofi,
                'cvd_delta': cvd.get('cvd', 0),
                'sweep_price': sweep_price,
                'buy_pressure_pct': cvd.get('buy_pressure_pct', 50),
            }
        )
    
    def _build_flip_signal(self, asset: str, flip: Dict, ob: Dict) -> MicroSignal:
        direction = flip['direction']
        mid = ob.get('mid_price', 0)
        
        # Wider stops for momentum flip
        if direction == 'long':
            entry = mid
            stop = mid * 0.988
            target1 = mid * 1.025
            target2 = mid * 1.05
        else:
            entry = mid
            stop = mid * 1.012
            target1 = mid * 0.975
            target2 = mid * 0.95
        
        return MicroSignal(
            signal_type='ofi_momentum_flip',
            direction=direction,
            strength=flip['strength'],
            entry_zone=(entry * 0.998, entry * 1.002),
            stop_loss=stop,
            targets=[target1, target2],
            metadata={'ofi_extreme': True}
        )
