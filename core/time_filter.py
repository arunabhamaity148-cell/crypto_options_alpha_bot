"""
Time-based signal filtering
"""

import logging
from typing import Dict, Tuple
from datetime import datetime
import pytz

logger = logging.getLogger(__name__)

IST = pytz.timezone('Asia/Kolkata')

class TimeFilter:
    def __init__(self):
        self.ist = IST
        self.last_session = None
        
    def is_best_time(self, asset: str = None) -> Tuple[bool, Dict]:
        """Check if current time is good for trading"""
        now = datetime.now(self.ist)
        current_hour = now.hour
        current_minute = now.minute
        current_weekday = now.strftime('%A')
        
        # Friday late check
        if current_weekday == 'Friday' and current_hour >= 22:
            return False, {
                'session': 'Friday Late',
                'quality': 'avoid',
                'reason': 'Weekend risk'
            }
        
        # Weekend check
        if current_weekday in ['Saturday', 'Sunday']:
            return False, {
                'session': 'Weekend',
                'quality': 'avoid',
                'reason': 'Low liquidity'
            }
        
        # US Market Open: 7:00 PM - 9:30 PM IST
        if 19 <= current_hour < 21 or (current_hour == 21 and current_minute <= 30):
            return True, {
                'session': 'US Market Open',
                'quality': 'excellent',
                'priority': 1
            }
        
        # US-Europe Overlap: 5:30 PM - 7:00 PM IST
        if 17 <= current_hour < 19:
            return True, {
                'session': 'US-Europe Overlap',
                'quality': 'good',
                'priority': 2
            }
        
        # Regular hours
        return True, {
            'session': 'Regular',
            'quality': 'moderate',
            'priority': 3
        }
    
    def should_process_signal(self, asset: str, setup: Dict) -> Tuple[bool, str]:
        """Check if should process signal"""
        is_good, time_info = self.is_best_time(asset)
        
        current_session = time_info.get('session', 'Unknown')
        if current_session != self.last_session:
            logger.info(f"Session: {current_session} ({time_info.get('quality')})")
            self.last_session = current_session
        
        if time_info.get('quality') == 'excellent':
            return True, "Excellent time"
        
        if time_info.get('quality') in ['good', 'moderate']:
            score = setup.get('confidence', 0)
            if score >= 85:
                return True, f"Good time, high score: {score}"
            else:
                return False, f"Score {score} < 85 threshold"
        
        return False, time_info.get('reason', 'Avoid time')
    
    def get_trading_recommendation(self) -> str:
        """Get recommendation"""
        is_good, info = self.is_best_time()
        
        if not is_good:
            return f"AVOID: {info.get('reason')}"
        
        return f"OK: {info.get('session')}"
