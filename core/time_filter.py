"""
Time-based signal filtering
Integrates with main bot
"""

import logging
from typing import Dict, Tuple
from config.trading_hours import trading_hours, TRADING_SESSIONS

logger = logging.getLogger(__name__)

class TimeFilter:
    """Filters signals based on trading hours"""
    
    def __init__(self):
        self.hours_manager = trading_hours
        self.last_session = None
        
    def should_process_signal(self, asset: str, setup: Dict) -> Tuple[bool, str]:
        """
        Check if signal should be processed based on time
        Returns: (should_process, reason)
        """
        
        is_good_time, time_info = self.hours_manager.is_best_time(asset)
        
        # Always log current session
        current_session = time_info.get('session', 'Unknown')
        if current_session != self.last_session:
            logger.info(f"🕐 Current session: {current_session} ({time_info.get('quality')})")
            self.last_session = current_session
        
        # EXCELLENT time - process all qualified signals
        if time_info.get('quality') == 'excellent':
            return True, f"Excellent time: {current_session}"
        
        # MODERATE time - only high confidence signals
        if time_info.get('quality') == 'moderate':
            score = setup.get('confidence', 0)
            if score >= 90:
                return True, f"Moderate time but exceptional score: {score}"
            else:
                return False, f"Moderate time, score {score} < 90 threshold"
        
        # AVOID time - skip unless exceptional
        if time_info.get('quality') == 'avoid':
            score = setup.get('confidence', 0)
            if score >= 95:  # Only 95+ scores during avoid times
                return True, f"Avoid time but exceptional score: {score}"
            else:
                return False, f"Avoid time: {time_info.get('reason', 'Low quality hours')}"
        
        # Default: moderate processing
        return True, "Regular hours"
    
    def get_trading_recommendation(self) -> str:
        """Get current trading recommendation"""
        
        is_good, info = self.hours_manager.is_best_time()
        
        if not is_good:
            next_best = info.get('next_best', 'Unknown')
            return f"⏸️ AVOID TRADING\nReason: {info.get('reason')}\nNext best: {next_best}"
        
        quality = info.get('quality', 'unknown')
        session = info.get('session', 'Unknown')
        
        if quality == 'excellent':
            return f"✅ EXCELLENT TIME\nSession: {session}\nExpected move: {info.get('expected_move', '1-2%')}"
        
        return f"⚠️ MODERATE TIME\nSession: {session}\nBe selective with signals"
    
    def get_sleep_time(self) -> int:
        """Get recommended sleep time until next check"""
        return self.hours_manager.get_sleep_duration()
    
    def format_schedule(self) -> str:
        """Format daily schedule for display"""
        schedule = self.hours_manager.get_daily_schedule()
        
        lines = ["📅 DAILY TRADING SCHEDULE (IST)\n"]
        
        for item in schedule:
            lines.append(f"{item['time']} | {item['quality']}")
            lines.append(f"   {item['name']} | Assets: {item['assets']}")
            lines.append(f"   Expected: {item['expected']}\n")
        
        return "\n".join(lines)
