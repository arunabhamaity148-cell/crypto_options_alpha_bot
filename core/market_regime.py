"""
Market Regime Detector - FREE Upgrade
Detects trending, ranging, volatile, choppy markets
"""

import logging
from typing import Dict, List, Tuple
from dataclasses import dataclass
import numpy as np

logger = logging.getLogger(__name__)

@dataclass
class RegimeConfig:
    min_adx_trending: float = 25.0
    max_adx_ranging: float = 15.0
    volatility_threshold: float = 0.02  # 2% ATR
    choppy_atr_multiple: float = 1.5

class MarketRegimeDetector:
    """Detect market conditions and adjust strategy"""
    
    REGIMES = {
        'trending_bull': {
            'direction_bias': 'long',
            'position_mult': 1.2,
            'target_mult': 1.5,
            'stop_tightness': 1.0,
            'min_score_threshold': 82
        },
        'trending_bear': {
            'direction_bias': 'short',
            'position_mult': 1.2,
            'target_mult': 1.5,
            'stop_tightness': 1.0,
            'min_score_threshold': 82
        },
        'ranging': {
            'mean_reversion': True,
            'position_mult': 0.8,
            'target_mult': 0.8,
            'stop_tightness': 0.8,
            'min_score_threshold': 87  # Require higher quality
        },
        'volatile': {
            'position_mult': 0.5,
            'target_mult': 2.0,  # Wider targets for volatility
            'stop_tightness': 1.5,  # Wider stops
            'min_score_threshold': 85
        },
        'choppy': {
            'block_trades': True,  # Don't trade
            'position_mult': 0.0,
            'reason': 'Low quality chop - avoid'
        }
    }
    
    def __init__(self, config: RegimeConfig = None):
        self.config = config or RegimeConfig()
        self.price_history: Dict[str, List[float]] = {}
        self.current_regime: Dict[str, str] = {}
    
    def update_price(self, asset: str, price: float):
        """Track price for regime detection"""
        if asset not in self.price_history:
            self.price_history[asset] = []
        
        self.price_history[asset].append(price)
        
        # Keep last 100 prices
        if len(self.price_history[asset]) > 100:
            self.price_history[asset] = self.price_history[asset][-100:]
    
    def detect_regime(self, asset: str, market_data: Dict = None) -> str:
        """Detect current market regime"""
        prices = self.price_history.get(asset, [])
        
        if len(prices) < 20:
            return 'unknown'
        
        # Calculate indicators
        adx = self._calculate_adx(prices)
        atr = self._calculate_atr(prices)
        current_price = prices[-1]
        
        # Price change over last 20 periods
        price_change = (prices[-1] - prices[-20]) / prices[-20]
        
        # Volatility as % of price
        volatility = atr / current_price if current_price > 0 else 0
        
        # Detect regime
        if adx > self.config.min_adx_trending:
            regime = 'trending_bull' if price_change > 0 else 'trending_bear'
        elif volatility > self.config.volatility_threshold:
            regime = 'volatile'
        elif adx < self.config.max_adx_ranging:
            # Check if choppy (high volatility but no direction)
            if volatility > self.config.volatility_threshold * self.config.choppy_atr_multiple:
                regime = 'choppy'
            else:
                regime = 'ranging'
        else:
            regime = 'ranging'
        
        self.current_regime[asset] = regime
        logger.info(f"{asset} regime: {regime} (ADX: {adx:.1f}, Vol: {volatility:.3f})")
        
        return regime
    
    def get_regime_config(self, regime: str) -> Dict:
        """Get trading parameters for regime"""
        return self.REGIMES.get(regime, self.REGIMES['ranging'])
    
    def should_trade(self, asset: str, direction: str = None) -> Tuple[bool, Dict]:
        """Check if we should trade in current regime"""
        regime = self.current_regime.get(asset, 'unknown')
        config = self.get_regime_config(regime)
        
        if config.get('block_trades'):
            return False, config
        
        # Check direction alignment for trending markets
        if 'trending' in regime and direction:
            bias = config.get('direction_bias')
            if bias != direction:
                logger.info(f"{asset}: Direction mismatch - {direction} vs {bias}")
                return False, config
        
        return True, config
    
    def adjust_setup(self, setup: Dict, regime: str) -> Dict:
        """Modify setup based on regime"""
        config = self.get_regime_config(regime)
        
        adjusted = setup.copy()
        
        # Adjust position size
        if 'position_size' in adjusted:
            adjusted['position_size'] *= config.get('position_mult', 1.0)
        
        # Adjust targets
        if 'target_1' in adjusted and 'target_2' in adjusted:
            mult = config.get('target_mult', 1.0)
            entry = adjusted['entry_price']
            
            if adjusted['direction'] == 'long':
                t1_distance = adjusted['target_1'] - entry
                t2_distance = adjusted['target_2'] - entry
                adjusted['target_1'] = entry + t1_distance * mult
                adjusted['target_2'] = entry + t2_distance * mult
            else:
                t1_distance = entry - adjusted['target_1']
                t2_distance = entry - adjusted['target_2']
                adjusted['target_1'] = entry - t1_distance * mult
                adjusted['target_2'] = entry - t2_distance * mult
        
        # Adjust stop loss
        if 'stop_loss' in adjusted:
            tightness = config.get('stop_tightness', 1.0)
            entry = adjusted['entry_price']
            current_sl = adjusted['stop_loss']
            
            sl_distance = abs(entry - current_sl)
            new_sl_distance = sl_distance * tightness
            
            if adjusted['direction'] == 'long':
                adjusted['stop_loss'] = entry - new_sl_distance
            else:
                adjusted['stop_loss'] = entry + new_sl_distance
        
        adjusted['regime'] = regime
        adjusted['regime_adjusted'] = True
        
        return adjusted
    
    def _calculate_adx(self, prices: List[float], period: int = 14) -> float:
        """Simplified ADX calculation"""
        if len(prices) < period + 1:
            return 0
        
        # Calculate +DM and -DM
        plus_dm = []
        minus_dm = []
        tr_list = []
        
        for i in range(1, len(prices)):
            high = max(prices[i], prices[i-1])
            low = min(prices[i], prices[i-1])
            prev_close = prices[i-1]
            
            tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
            tr_list.append(tr)
            
            up_move = prices[i] - prices[i-1]
            down_move = prices[i-1] - prices[i]
            
            if up_move > down_move and up_move > 0:
                plus_dm.append(up_move)
            else:
                plus_dm.append(0)
            
            if down_move > up_move and down_move > 0:
                minus_dm.append(down_move)
            else:
                minus_dm.append(0)
        
        # Smooth
        atr = sum(tr_list[-period:]) / period
        plus_di = 100 * sum(plus_dm[-period:]) / period / atr if atr > 0 else 0
        minus_di = 100 * sum(minus_dm[-period:]) / period / atr if atr > 0 else 0
        
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di) if (plus_di + minus_di) > 0 else 0
        
        # Simplified ADX (smoothed DX)
        adx = sum([dx] * period) / period  # Approximation
        
        return adx
    
    def _calculate_atr(self, prices: List[float], period: int = 14) -> float:
        """Calculate Average True Range"""
        if len(prices) < period + 1:
            return 0
        
        tr_list = []
        
        for i in range(1, len(prices)):
            high = prices[i]
            low = prices[i]
            prev_close = prices[i-1]
            
            tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
            tr_list.append(tr)
        
        return sum(tr_list[-period:]) / period

# Global instance
regime_detector = MarketRegimeDetector()
