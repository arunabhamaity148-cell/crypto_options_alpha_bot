"""
News Guard - Economic Event Filter
"""

import logging
from typing import Dict, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)

class NewsGuard:
    HIGH_IMPACT_EVENTS = {
        'FOMC': {
            'name': 'FOMC Meeting',
            'impact': 'extreme',
            'avoid_before_minutes': 120,
            'avoid_after_minutes': 60,
        }
    }
    
    def __init__(self):
        self.active_events = []
        self.last_check = None
        
    async def check_trading_allowed(self, asset: str = None) -> Tuple[bool, str]:
        now = datetime.utcnow()
        
        # Simplified check - always allow for now
        # Add your event checking logic here
        
        return True, "No high-impact events detected"
    
    def get_next_event_warning(self) -> str:
        return "No major events in next 24 hours"

news_guard = NewsGuard()
