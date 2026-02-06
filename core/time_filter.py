"""
Time-based signal filtering
"""

import logging
from typing import Dict, Tuple
from datetime import datetime
import pytz

logger = logging.getLogger(__name__)

IST = pytz.timezone('Asia/Kolkata')

# Embedded trading hours config
TRADING_SESSIONS = {
    'best': {
        'us_market_open': {
            'name': 'US Market Open',
            'utc_start': '13:30',
            'utc_end': '16:00',
            'description': 'Highest volatility',
            'priority': 1,
            'assets': ['BTC', 'ETH', 'SOL'],
            'expected_moves': '1.5-3%'
        }
    },
    'moderate': {},
    'avoid': {}
}

class TradingHoursManager:
    def __init__(self):
        self.ist = IST
        
    def get_current_ist_time(self) -> datetime:
        return datetime.now(self.ist)
    
    def is_best_time(self, asset: str = None) -> Tuple[bool, Dict]:
        now = self.get_current_ist_time()
        current_hour = now.hour
        current_minute = now.minute
        
        # US Market Open: 7:00 PM - 9:30 PM IST (19:00 - 21:30)
        if 19 <= current_hour < 21 or (current_hour == 21 and current_minute <= 30):
            return True, {
                'session': 'US Market Open',
                'quality': 'excellent',
                'priority': 1,
                'expected_move': '1.5-3%'
            }
        
        # Moderate times
        if 17 <= current_hour < 19:  # Europe overlap
            return True, {
                'session': 'Europe-US Overlap',
                'quality': 'moderate',
                'priority': 2
            }
        
        return True, {
            'session': 'Regular hours',
            'quality': 'moderate',
            'priority': 3
        }

trading_hours = TradingHoursManager()

class TimeFilter:
    def __init__(self):
        self.hours_manager = trading_hours
        self.last_session = None
        
    def should_process_signal(self, asset: str, setup: Dict) -> Tuple[bool, str]:
        is_good_time, time_info = self.hours_manager.is_best_time(asset)
        
        current_session = time_info.get('session', 'Unknown')
        if current_session != self.last_session:
            logger.info(f"Current session: {current_session} ({time_info.get('quality')})")
            self.last_session = current_session
        
        if time_info.get('quality') == 'excellent':
            return True, f"Excellent time: {current_session}"
        
        if time_info.get('quality') == 'moderate':
            score = setup.get('confidence', 0)
            if score >= 90:
                return True, f"Moderate time but exceptional score: {score}"
            else:
                return False, f"Moderate time, score {score} < 90 threshold"
        
        return True, "Regular hours"
    
    def get_trading_recommendation(self) -> str:
        is_good, info = self.hours_manager.is_best_time()
        
        if not is_good:
            return f"AVOID TRADING\nReason: {info.get('reason')}"
        
        quality = info.get('quality', 'unknown')
        session = info.get('session', 'Unknown')
        
        if quality == 'excellent':
            return f"EXCELLENT TIME\nSession: {session}"
        
        return f"MODERATE TIME\nSession: {session}"
