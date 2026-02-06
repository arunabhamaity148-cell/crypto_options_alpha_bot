"""
Microstructure Analysis - OFI, CVD, Liquidity
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
        cvd_data = self._calculate_cvd(recent_trades, orderbook.get('mid_price', 0))
        ofi = orderbook.get('ofi_ratio', 0)
        
        sweep = self._detect_liquidity_sweep(orderbook, cvd_data)
        
        if sweep:
            return self._build_signal(asset, sweep, ofi, cvd_data, orderbook)
        
        flip = self._detect_ofi_flip(ofi, orderbook)
        if flip:
            return self._build_flip_signal(asset, flip, orderbook)
        
        return None
    
    def _calculate_cvd(self, trades: List[Dict], mid_price: float) -> Dict:
        buy_volume = 0
        sell_volume = 0
        
        for trade in trades:
            price = float(trade.get('price', 0))
            qty = float(trade.get('qty', 0))
            is_buyer_maker = trade.get('isBuyerMaker', False)
            
            if is_buyer_maker:
                sell_volume += qty * price
            else:
                buy_volume += qty * price
        
        total = buy_volume + sell_volume
        cvd = buy_volume - sell_volume
        
        return {
            'cvd': cvd,
            'buy_volume': buy_volume,
            'sell_volume': sell_volume,
            'delta_ratio': cvd / total if total > 0 else 0,
        }
    
    def _detect_liquidity_sweep(self, orderbook: Dict, cvd: Dict) -> Optional[Dict]:
        mid = orderbook.get('mid_price', 0)
        voids_below = orderbook.get('liquidity_voids_below', [])
        voids_above = orderbook.get('liquidity_voids_above', [])
        
        # FIXED: Removed invalid syntax "above sweep level"
        if voids_below and cvd.get('delta_ratio', 0) > 0.2:
            sweep_price = voids_below[0][0]
            # Price came back above sweep level
            if mid > sweep_price * 1.002:
                return {
                    'type': 'sweep_low',
                    'sweep_price': sweep_price,
                    'direction': 'long',
                    'strength': min(95, 70 + cvd.get('delta_ratio', 0) * 50)
                }
        
        if voids_above and cvd.get('delta_ratio', 0) < -0.2:
            sweep_price = voids_above[0][0]
            if mid < sweep_price * 0.998:
                return {
                    'type': 'sweep_high',
                    'sweep_price': sweep_price,
                    'direction': 'short',
                    'strength': min(95, 70 + abs(cvd.get('delta_ratio', 0)) * 50)
                }
        
        return None
    
    def _detect_ofi_flip(self, ofi: float, orderbook: Dict) -> Optional[Dict]:
        if abs(ofi) > 0.3:
            return {
                'type': 'ofi_extreme',
                'direction': 'long' if ofi > 0 else 'short',
                'strength': min(90, 60 + abs(ofi) * 100)
            }
        return None
    
    def _build_signal(self, asset: str, sweep: Dict, ofi: float, cvd: Dict, ob: Dict) -> MicroSignal:
        direction = sweep['direction']
        mid = ob.get('mid_price', 0)
        sweep_price = sweep['sweep_price']
        
        if direction == 'long':
            entry = mid
            stop = sweep_price * 0.995
            target1 = mid + (mid - stop) * 1.5
            target2 = mid + (mid - stop) * 2.5
        else:
            entry = mid
            stop = sweep_price * 1.005
            target1 = mid - (stop - mid) * 1.5
            target2 = mid - (stop - mid) * 2.5
        
        return MicroSignal(
            signal_type=f"liquidity_{sweep['type']}",
            direction=direction,
            strength=sweep['strength'],
            entry_zone=(entry * 0.998, entry * 1.002),
            stop_loss=stop,
            targets=[target1, target2],
            metadata={
                'ofi_ratio': ofi,
                'cvd_delta': cvd.get('cvd', 0),
                'sweep_price': sweep_price,
            }
        )
    
    def _build_flip_signal(self, asset: str, flip: Dict, ob: Dict) -> MicroSignal:
        direction = flip['direction']
        mid = ob.get('mid_price', 0)
        
        if direction == 'long':
            entry = mid
            stop = mid * 0.985
            target1 = mid * 1.02
            target2 = mid * 1.04
        else:
            entry = mid
            stop = mid * 1.015
            target1 = mid * 0.98
            target2 = mid * 0.96
        
        return MicroSignal(
            signal_type='ofi_momentum_flip',
            direction=direction,
            strength=flip['strength'],
            entry_zone=(entry * 0.999, entry * 1.001),
            stop_loss=stop,
            targets=[target1, target2],
            metadata={'ofi_extreme': True}
        )
