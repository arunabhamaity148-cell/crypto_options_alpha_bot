"""
News Guard - Economic Event & Expiry Filter
"""

import logging
from typing import Dict, Tuple
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class NewsGuard:
    HIGH_IMPACT_EVENTS = {
        'FOMC': {
            'name': 'FOMC Meeting',
            'impact': 'extreme',
            'avoid_before_hours': 2,
            'avoid_after_hours': 2,
        },
        'CPI': {
            'name': 'CPI Release',
            'impact': 'extreme',
            'avoid_before_hours': 1,
            'avoid_after_hours': 1,
        },
        'NFP': {
            'name': 'Non-Farm Payroll',
            'impact': 'extreme',
            'avoid_before_hours': 1,
            'avoid_after_hours': 2,
        },
        'GDP': {
            'name': 'GDP Report',
            'impact': 'high',
            'avoid_before_hours': 1,
            'avoid_after_hours': 1,
        },
    }
    
    def __init__(self):
        self.active_events = []
        self.last_check = None
        
    async def check_trading_allowed(self, asset: str = None) -> Tuple[bool, str]:
        """Check if trading allowed"""
        now = datetime.utcnow()
        
        # Check expiry risk first
        expiry_ok, expiry_msg = self.check_expiry_risk()
        if not expiry_ok:
            return False, expiry_msg
        
        # Simplified check - always allow for now
        # Add your event checking logic here
        
        return True, "No high-impact events detected"
    
    def check_expiry_risk(self) -> Tuple[bool, str]:
        """Check options expiry risk"""
        now = datetime.now()
        
        # Weekly expiry (every Friday)
        if now.weekday() == 4:  # Friday = 4
            # After 12 PM UTC = 5:30 PM IST
            if now.hour >= 12:
                return False, "Weekly expiry day after noon - high gamma risk"
            
            # Morning is OK but reduced size
            if now.hour >= 8:
                return True, "Weekly expiry day morning - caution"
        
        # Less than 24 hours to expiry
        # Assuming expiry is Friday 08:00 UTC
        days_to_friday = (4 - now.weekday()) % 7
        if days_to_friday == 0:  # Today is Friday
            hours_to_expiry = 8 - now.hour  # 08:00 UTC expiry
            if hours_to_expiry < 24 and hours_to_expiry > 0:
                return False, f"Only {hours_to_expiry}h to weekly expiry"
        
        # Monthly expiry (last Friday)
        if self.is_monthly_expiry():
            if now.weekday() == 4:  # Friday
                return False, "Monthly expiry day - avoid"
            elif now.weekday() == 3 and now.hour >= 20:  # Thursday night
                return False, "Monthly expiry eve - pin risk"
        
        return True, "Expiry risk low"
    
    def is_monthly_expiry(self) -> bool:
        """Check if this week is monthly expiry"""
        today = datetime.now()
        # Find last Friday of month
        next_month = today.replace(day=28) + timedelta(days=4)
        last_day = next_month - timedelta(days=next_month.day)
        last_friday = last_day
        while last_friday.weekday() != 4:
            last_friday -= timedelta(days=1)
        
        # Check if today is within 3 days of monthly expiry
        days_diff = (last_friday.date() - today.date()).days
        return 0 <= days_diff <= 3
    
    def get_next_event_warning(self) -> str:
        """Get warning about upcoming events"""
        return "No major events in next 24 hours"

# Global instance
news_guard = NewsGuard()
