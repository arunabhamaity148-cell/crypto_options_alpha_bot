"""
Multi-Timeframe Analyzer - FREE Upgrade
Checks confluence across 5m, 15m, 1h, 4h timeframes
"""

import asyncio
import logging
from typing import Dict, List, Tuple
from dataclasses import dataclass
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

@dataclass
class TimeframeAnalysis:
    timeframe: str
    trend: str  # bullish, bearish, neutral
    trend_strength: float  # 0-100
    support: float
    resistance: float
    momentum: float  # -100 to 100
    volume_profile: str  # high, normal, low

class MultiTimeframeAnalyzer:
    """Analyze multiple timeframes for confluence"""
    
    TIMEFRAMES = ['5m', '15m', '1h', '4h']
    WEIGHTS = {'5m': 0.1, '15m': 0.2, '1h': 0.3, '4h': 0.4}  # Higher TF = more weight
    
    def __init__(self):
        self.cache: Dict[str, Dict] = {}
        self.cache_time: Dict[str, datetime] = {}
        self.cache_ttl = 300  # 5 minutes
    
    async def analyze(self, asset: str, data_fetcher) -> Dict:
        """Analyze all timeframes"""
        cache_key = f"mtf_{asset}"
        
        # Check cache
        if cache_key in self.cache:
            if (datetime.now(timezone.utc) - self.cache_time[cache_key]).seconds < self.cache_ttl:
                return self.cache[cache_key]
        
        # Fetch all timeframes
        tasks = []
        for tf in self.TIMEFRAMES:
            tasks.append(self._analyze_timeframe(asset, tf, data_fetcher))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        analyses = {}
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Error analyzing {self.TIMEFRAMES[i]}: {result}")
                continue
            analyses[self.TIMEFRAMES[i]] = result
        
        # Calculate confluence
        confluence = self._calculate_confluence(analyses)
        
        result = {
            'timeframes': analyses,
            'confluence_score': confluence['score'],
            'overall_direction': confluence['direction'],
            'alignment_quality': confluence['quality'],
            'key_levels': confluence['levels'],
            'trade_recommendation': confluence['recommendation']
        }
        
        # Cache
        self.cache[cache_key] = result
        self.cache_time[cache_key] = datetime.now(timezone.utc)
        
        return result
    
    async def _analyze_timeframe(self, asset: str, timeframe: str, data_fetcher) -> TimeframeAnalysis:
        """Analyze single timeframe"""
        # Fetch OHLCV data
        ohlcv = await data_fetcher(asset, timeframe)
        
        if not ohlcv or len(ohlcv) < 20:
            return TimeframeAnalysis(
                timeframe=timeframe,
                trend='neutral',
                trend_strength=0,
                support=0,
                resistance=0,
                momentum=0,
                volume_profile='normal'
            )
        
        closes = [c['close'] for c in ohlcv]
        highs = [c['high'] for c in ohlcv]
        lows = [c['low'] for c in ohlcv]
        volumes = [c['volume'] for c in ohlcv]
        
        # Trend detection
        trend, strength = self._detect_trend(closes)
        
        # Support/Resistance
        support, resistance = self._find_key_levels(highs, lows, closes)
        
        # Momentum
        momentum = self._calculate_momentum(closes)
        
        # Volume
        vol_profile = self._analyze_volume(volumes)
        
        return TimeframeAnalysis(
            timeframe=timeframe,
            trend=trend,
            trend_strength=strength,
            support=support,
            resistance=resistance,
            momentum=momentum,
            volume_profile=vol_profile
        )
    
    def _detect_trend(self, closes: List[float]) -> Tuple[str, float]:
        """Detect trend direction and strength"""
        if len(closes) < 20:
            return 'neutral', 0
        
        # EMAs
        ema_fast = self._ema(closes, 9)
        ema_slow = self._ema(closes, 21)
        
        if ema_fast > ema_slow * 1.001:
            trend = 'bullish'
            strength = min(100, ((ema_fast / ema_slow) - 1) * 10000)
        elif ema_fast < ema_slow * 0.999:
            trend = 'bearish'
            strength = min(100, ((ema_slow / ema_fast) - 1) * 10000)
        else:
            trend = 'neutral'
            strength = 0
        
        return trend, strength
    
    def _find_key_levels(self, highs: List[float], lows: List[float], closes: List[float]) -> Tuple[float, float]:
        """Find support and resistance levels"""
        recent_highs = sorted(highs[-20:], reverse=True)[:5]
        recent_lows = sorted(lows[-20:])[:5]
        
        resistance = sum(recent_highs) / len(recent_highs) if recent_highs else max(highs)
        support = sum(recent_lows) / len(recent_lows) if recent_lows else min(lows)
        
        return support, resistance
    
    def _calculate_momentum(self, closes: List[float]) -> float:
        """Calculate momentum (-100 to 100)"""
        if len(closes) < 14:
            return 0
        
        # RSI approximation
        gains = []
        losses = []
        
        for i in range(1, min(15, len(closes))):
            change = closes[-i] - closes[-i-1]
            if change > 0:
                gains.append(change)
            else:
                losses.append(abs(change))
        
        avg_gain = sum(gains) / len(gains) if gains else 0
        avg_loss = sum(losses) / len(losses) if losses else 0
        
        if avg_loss == 0:
            return 100
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        # Convert to -100 to 100 scale
        return (rsi - 50) * 2
    
    def _analyze_volume(self, volumes: List[float]) -> str:
        """Analyze volume profile"""
        if len(volumes) < 20:
            return 'normal'
        
        recent_avg = sum(volumes[-5:]) / 5
        historical_avg = sum(volumes[-20:]) / 20
        
        ratio = recent_avg / historical_avg if historical_avg > 0 else 1
        
        if ratio > 1.5:
            return 'high'
        elif ratio < 0.5:
            return 'low'
        return 'normal'
    
    def _calculate_confluence(self, analyses: Dict[str, TimeframeAnalysis]) -> Dict:
        """Calculate overall confluence score"""
        if not analyses:
            return {'score': 0, 'direction': 'unknown', 'quality': 'poor', 'levels': [], 'recommendation': 'avoid'}
        
        # Weighted trend score
        bullish_score = 0
        bearish_score = 0
        total_weight = 0
        
        for tf, analysis in analyses.items():
            weight = self.WEIGHTS.get(tf, 0.25)
            total_weight += weight
            
            if analysis.trend == 'bullish':
                bullish_score += analysis.trend_strength * weight
            elif analysis.trend == 'bearish':
                bearish_score += analysis.trend_strength * weight
        
        # Determine direction
        if bullish_score > bearish_score * 1.5:
            direction = 'bullish'
            score = min(100, bullish_score / total_weight)
        elif bearish_score > bullish_score * 1.5:
            direction = 'bearish'
            score = min(100, bearish_score / total_weight)
        else:
            direction = 'mixed'
            score = 50 - abs(bullish_score - bearish_score) / total_weight
        
        # Quality label
        if score > 80:
            quality = 'excellent'
        elif score > 65:
            quality = 'good'
        elif score > 50:
            quality = 'moderate'
        else:
            quality = 'poor'
        
        # Recommendation
        if score > 75 and direction != 'mixed':
            recommendation = 'strong_take'
        elif score > 60 and direction != 'mixed':
            recommendation = 'take'
        elif score > 45:
            recommendation = 'cautious'
        else:
            recommendation = 'avoid'
        
        # Aggregate key levels
        all_supports = [a.support for a in analyses.values()]
        all_resistances = [a.resistance for a in analyses.values()]
        
        levels = {
            'strong_support': max(set(all_supports), key=all_supports.count),
            'strong_resistance': max(set(all_resistances), key=all_resistances.count),
            'nearest_support': min(all_supports),
            'nearest_resistance': max(all_resistances)
        }
        
        return {
            'score': round(score, 1),
            'direction': direction,
            'quality': quality,
            'levels': levels,
            'recommendation': recommendation
        }
    
    def _ema(self, prices: List[float], period: int) -> float:
        """Calculate EMA"""
        if len(prices) < period:
            return prices[-1] if prices else 0
        
        multiplier = 2 / (period + 1)
        ema = sum(prices[:period]) / period  # SMA start
        
        for price in prices[period:]:
            ema = (price - ema) * multiplier + ema
        
        return ema
    
    def check_signal_alignment(self, signal_direction: str, mtf_result: Dict) -> Tuple[bool, float]:
        """Check if signal aligns with MTF analysis"""
        overall = mtf_result.get('overall_direction', 'mixed')
        score = mtf_result.get('confluence_score', 50)
        
        # Strong alignment
        if overall == signal_direction and score > 75:
            return True, 1.2  # Boost size
        
        # Moderate alignment
        if overall == signal_direction and score > 60:
            return True, 1.0  # Normal size
        
        # Weak alignment
        if overall == signal_direction:
            return True, 0.8  # Reduce size
        
        # Conflict
        if overall != 'mixed':
            logger.warning(f"MTF conflict: signal {signal_direction} vs market {overall}")
            return False, 0.0  # Block trade
        
        # Mixed/unclear
        if score < 50:
            return False, 0.0
        
        return True, 0.9

# Global instance
mtf_analyzer = MultiTimeframeAnalyzer()
