"""
Time-based signal filtering with SLEEP MODE
Bot only runs during golden hours to save Railway resources
"""

import logging
from typing import Dict, Tuple, Optional
from datetime import datetime, time
import pytz

logger = logging.getLogger(__name__)

IST = pytz.timezone('Asia/Kolkata')

class TimeFilter:
    def __init__(self):
        self.ist = IST
        self.last_session = None
        
        # GOLDEN HOURS - Only trade these times (IST)
        self.golden_hours = [
            # US Market Open - Best liquidity
            (time(19, 0), time(21, 30)),   # 7:00 PM - 9:30 PM IST
            
            # Pre-US momentum (optional, comment out to save more)
            # (time(17, 30), time(19, 0)),   # 5:30 PM - 7:00 PM IST
        ]
        
        # Days to trade (0=Monday, 4=Friday)
        self.trading_days = [0, 1, 2, 3]  # Mon-Thu only
        # Friday off completely or reduce:
        # self.trading_days = [0, 1, 2, 3, 4]  # Include Friday
        
    def should_bot_run(self) -> Tuple[bool, Optional[int], str]:
        """
        Main check - should bot be running at all?
        Returns: (should_run, sleep_seconds, reason)
        """
        now = datetime.now(self.ist)
        weekday = now.weekday()
        current_time = now.time()
        
        # Check if trading day
        if weekday not in self.trading_days:
            # Calculate sleep until next Monday 7 PM
            if weekday == 4:  # Friday
                # Sleep until Monday 7 PM
                sleep_seconds = self._seconds_until_monday_7pm(now)
                return False, sleep_seconds, "Weekend - bot sleeping until Monday"
            elif weekday in [5, 6]:  # Saturday/Sunday
                sleep_seconds = self._seconds_until_monday_7pm(now)
                return False, sleep_seconds, "Weekend - bot sleeping"
            else:
                return False, 3600, "Non-trading day"
        
        # Check if within golden hours
        in_golden_hour, next_window = self._check_golden_hours(current_time)
        
        if not in_golden_hour:
            if next_window:
                sleep_seconds = self._seconds_until_time(now, next_window)
                return False, sleep_seconds, f"Outside golden hours - sleeping until {next_window}"
            else:
                # No more windows today, sleep until tomorrow 7 PM
                sleep_seconds = self._seconds_until_tomorrow_7pm(now)
                return False, sleep_seconds, "Golden hours over - sleeping until tomorrow"
        
        return True, None, "Golden hour - trading active"
    
    def _check_golden_hours(self, current_time: time) -> Tuple[bool, Optional[time]]:
        """Check if current time is in golden hours"""
        for start, end in self.golden_hours:
            if start <= current_time <= end:
                return True, None
        
        # Find next window today
        for start, end in self.golden_hours:
            if current_time < start:
                return False, start
        
        return False, None
    
    def _seconds_until_time(self, now: datetime, target_time: time) -> int:
        """Calculate seconds until target time today"""
        target = now.replace(hour=target_time.hour, minute=target_time.minute, second=0)
        if target < now:
            target += timedelta(days=1)
        return int((target - now).total_seconds())
    
    def _seconds_until_tomorrow_7pm(self, now: datetime) -> int:
        """Calculate seconds until tomorrow 7 PM"""
        tomorrow = now + timedelta(days=1)
        target = tomorrow.replace(hour=19, minute=0, second=0, microsecond=0)
        # Skip to Monday if tomorrow is weekend
        if target.weekday() >= 5:
            target += timedelta(days=(7 - target.weekday()))
        return int((target - now).total_seconds())
    
    def _seconds_until_monday_7pm(self, now: datetime) -> int:
        """Calculate seconds until next Monday 7 PM"""
        days_until_monday = (7 - now.weekday()) % 7
        if days_until_monday == 0:
            days_until_monday = 7
        target = now + timedelta(days=days_until_monday)
        target = target.replace(hour=19, minute=0, second=0, microsecond=0)
        return int((target - now).total_seconds())
    
    def is_best_time(self, asset: str = None) -> Tuple[bool, Dict]:
        """Legacy method - kept for compatibility"""
        now = datetime.now(self.ist)
        current_hour = now.hour
        current_minute = now.minute
        
        # Only called during golden hours now
        if 19 <= current_hour < 21 or (current_hour == 21 and current_minute <= 30):
            return True, {
                'session': 'US Market Open',
                'quality': 'excellent',
                'priority': 1
            }
        
        return True, {
            'session': 'Regular',
            'quality': 'moderate',
            'priority': 3
        }
    
    def is_high_risk_time(self) -> Tuple[bool, str]:
        """Legacy - now handled by should_bot_run"""
        return False, "OK"
    
    def get_sleep_recommendation(self) -> Dict:
        """Get detailed sleep info for logging"""
        should_run, sleep_seconds, reason = self.should_bot_run()
        
        if should_run:
            return {
                'action': 'trade',
                'sleep_seconds': 0,
                'reason': 'Golden hour active',
                'next_check': 60  # Check again in 1 min
            }
        
        sleep_hours = sleep_seconds / 3600
        
        return {
            'action': 'sleep',
            'sleep_seconds': sleep_seconds,
            'sleep_hours': round(sleep_hours, 1),
            'reason': reason,
            'next_run': (datetime.now(self.ist) + timedelta(seconds=sleep_seconds)).strftime('%a %H:%M IST')
        }
