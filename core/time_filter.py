"""
Time-based signal filtering with HIGH-RISK detection
"""

import logging
from typing import Dict, Tuple
from datetime import datetime, timedelta
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
        
        if current_weekday in ['Saturday', 'Sunday']:
            return False, {
                'session': 'Weekend',
                'quality': 'avoid',
                'reason': 'Low liquidity'
            }
        
        if 19 <= current_hour < 21 or (current_hour == 21 and current_minute <= 30):
            return True, {
                'session': 'US Market Open',
                'quality': 'excellent',
                'priority': 1
            }
        
        if 17 <= current_hour < 19:
            return True, {
                'session': 'US-Europe Overlap',
                'quality': 'good',
                'priority': 2
            }
        
        return True, {
            'session': 'Regular',
            'quality': 'moderate',
            'priority': 3
        }
    
    def is_high_risk_time(self) -> Tuple[bool, str]:
        """Detect high-risk trading periods"""
        now = datetime.now(self.ist)
        weekday = now.strftime('%A')
        hour = now.hour
        minute = now.minute
        
        if weekday == 'Friday' and hour >= 21:
            return True, "Friday late - weekend risk, low liquidity"
        
        if weekday == 'Friday' and hour >= 18:
            return True, "Friday evening - reduce size or avoid"
        
        if weekday in ['Saturday', 'Sunday']:
            return True, "Weekend - markets closed or illiquid"
        
        if weekday == 'Monday' and hour < 5:
            return True, "Monday early - wait for better liquidity"
        
        if weekday == 'Thursday' and hour >= 22:
            return True, "Thursday late - weekly expiry approaching"
        
        if 9 <= hour < 12 or (hour == 12 and minute < 30):
            return True, "Dead zone - Europe not active yet"
        
        if self.is_monthly_expiry() and weekday == 'Friday':
            if hour >= 12:
                return True, "Monthly expiry day - high gamma risk"
        
        return False, "OK"
    
    def is_monthly_expiry(self) -> bool:
        """Check if today is last Friday of month"""
        today = datetime.now(self.ist)
        next_month = today.replace(day=28) + timedelta(days=4)
        last_day = next_month - timedelta(days=next_month.day)
        last_friday = last_day
        while last_friday.weekday() != 4:
            last_friday -= timedelta(days=1)
        
        return today.date() == last_friday.date()
    
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
