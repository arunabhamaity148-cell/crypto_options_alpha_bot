"""
Trading Hours Configuration
Best times to trade and times to avoid
Indian Time (IST) + Market Analysis
"""

from typing import Dict, List, Tuple
from datetime import datetime, time
import pytz

# Indian Standard Time
IST = pytz.timezone('Asia/Kolkata')

# UTC times (convert to IST: UTC+5:30)
TRADING_SESSIONS = {
    'best': {
        'us_market_open': {
            'name': 'US Market Open',
            'utc_start': '13:30',  # 7:00 PM IST
            'utc_end': '16:00',    # 9:30 PM IST
            'description': 'Highest volatility, institutional entry',
            'priority': 1,
            'assets': ['BTC', 'ETH', 'SOL'],
            'expected_moves': '1.5-3%'
        },
        'us_europe_overlap': {
            'name': 'US-Europe Overlap',
            'utc_start': '12:00',  # 5:30 PM IST
            'utc_end': '13:30',    # 7:00 PM IST
            'description': 'Pre-US momentum building',
            'priority': 2,
            'assets': ['BTC', 'ETH'],
            'expected_moves': '1-2%'
        },
        'asia_open': {
            'name': 'Asia Market Open',
            'utc_start': '00:00',  # 5:30 AM IST
            'utc_end': '02:00',    # 7:30 AM IST
            'description': 'Tokyo/Hong Kong active',
            'priority': 3,
            'assets': ['BTC', 'SOL'],
            'expected_moves': '0.8-1.5%'
        },
        'us_close': {
            'name': 'US Close',
            'utc_start': '20:00',  # 1:30 AM IST
            'utc_end': '21:00',    # 2:30 AM IST
            'description': 'Position squaring, late moves',
            'priority': 4,
            'assets': ['BTC', 'ETH'],
            'expected_moves': '1-2%'
        }
    },
    
    'moderate': {
        'europe_open': {
            'name': 'Europe Open',
            'utc_start': '07:00',  # 12:30 PM IST
            'utc_end': '09:00',    # 2:30 PM IST
            'description': 'London session, moderate flow',
            'priority': 5,
            'assets': ['BTC', 'ETH'],
            'expected_moves': '0.5-1%'
        },
        'asia_close': {
            'name': 'Asia Close',
            'utc_start': '06:00',  # 11:30 AM IST
            'utc_end': '07:00',    # 12:30 PM IST
            'description': 'Handover to Europe',
            'priority': 6,
            'assets': ['BTC'],
            'expected_moves': '0.5-1%'
        }
    },
    
    'avoid': {
        'dead_zone_1': {
            'name': 'Post-Asia Dead Zone',
            'utc_start': '04:00',  # 9:30 AM IST
            'utc_end': '07:00',    # 12:30 PM IST
            'description': 'Low liquidity, false breakouts',
            'reason': 'Asia closed, Europe not active yet'
        },
        'dead_zone_2': {
            'name': 'Mid-Asia Quiet',
            'utc_start': '02:00',  # 7:30 AM IST
            'utc_end': '04:00',    # 9:30 AM IST
            'description': 'Tokyo lunch, low activity',
            'reason': 'Japanese lunch break, thin orderbook'
        },
        'weekend': {
            'name': 'Weekend Low Vol',
            'utc_start': 'Friday 21:00',  # Saturday 2:30 AM IST
            'utc_end': 'Sunday 22:00',    # Monday 3:30 AM IST
            'description': 'Institutional traders offline',
            'reason': 'CME closed, low institutional flow'
        },
        'high_impact_news': {
            'name': 'Major News Events',
            'events': [
                'FOMC (Fed meetings)',
                'CPI/PPI releases',
                'Non-Farm Payroll (NFP)',
                'Major exchange hacks',
                'SEC announcements'
            ],
            'description': 'Extreme volatility, spreads widen',
            'reason': 'Unpredictable moves, stop hunts common'
        },
        'option_expiry': {
            'name': 'Monthly Option Expiry',
            'utc_time': 'Friday 08:00',  # 1:30 PM IST (last Friday)
            'description': 'Pin risk, gamma squeeze chaos',
            'reason': 'Max pain games, avoid 2 hours before/after'
        },
        'funding_reset': {
            'name': 'Funding Rate Reset',
            'utc_times': ['00:00', '08:00', '16:00'],  # Every 8 hours
            'description': 'Short-term volatility spike',
            'reason': 'Perp funding payments cause brief chaos'
        }
    }
}

# Asset-specific best times
ASSET_BEST_TIMES = {
    'BTC': {
        'primary': ['us_market_open', 'us_europe_overlap'],
        'secondary': ['asia_open', 'us_close'],
        'avoid': ['dead_zone_1', 'weekend']
    },
    'ETH': {
        'primary': ['us_market_open', 'us_europe_overlap'],
        'secondary': ['us_close'],
        'avoid': ['dead_zone_1', 'dead_zone_2']
    },
    'SOL': {
        'primary': ['us_market_open', 'asia_open'],
        'secondary': ['us_close'],
        'avoid': ['dead_zone_1', 'dead_zone_2', 'weekend']
    }
}

# Day of week analysis
DAY_ANALYSIS = {
    'Monday': {
        'quality': 'Good',
        'note': 'Weekend gap fill, fresh institutional positioning',
        'best_hours': ['us_market_open', 'asia_open']
    },
    'Tuesday': {
        'quality': 'Excellent',
        'note': 'Full liquidity, clear trends',
        'best_hours': ['all_best_sessions']
    },
    'Wednesday': {
        'quality': 'Excellent',
        'note': 'Mid-week momentum, high volume',
        'best_hours': ['all_best_sessions']
    },
    'Thursday': {
        'quality': 'Good',
        'note': 'Positioning for weekend',
        'best_hours': ['us_market_open', 'us_close'],
        'avoid': ['After 9 PM IST - weekly expiry']
    },
    'Friday': {
        'quality': 'Moderate',
        'note': 'Profit taking, low conviction',
        'best_hours': ['asia_open', 'europe_open'],
        'avoid': ['After US open - weekend risk']
    },
    'Saturday': {
        'quality': 'Avoid',
        'note': 'Retail only, manipulation risk',
        'best_hours': [],
        'avoid': ['All day']
    },
    'Sunday': {
        'quality': 'Poor',
        'note': 'Low volume, fakeouts',
        'best_hours': ['asia_open (Monday early)'],
        'avoid': ['Until Asia open']
    }
}

class TradingHoursManager:
    """Manages trading hours and filters"""
    
    def __init__(self):
        self.ist = pytz.timezone('Asia/Kolkata')
        
    def get_current_ist_time(self) -> datetime:
        """Get current IST time"""
        return datetime.now(self.ist)
    
    def is_best_time(self, asset: str = None) -> Tuple[bool, Dict]:
        """Check if current time is best for trading"""
        
        now = self.get_current_ist_time()
        current_time = now.time()
        current_weekday = now.strftime('%A')
        
        # Convert current time to UTC for comparison
        current_utc = now.astimezone(pytz.UTC)
        current_hour = current_utc.hour
        current_minute = current_utc.minute
        current_time_float = current_hour + current_minute / 60
        
        # Check if weekend
        if current_weekday in ['Saturday', 'Sunday']:
            return False, {
                'reason': 'Weekend - low institutional activity',
                'quality': 'avoid',
                'next_best': self._get_next_best_time(now)
            }
        
        # Check best sessions
        for session_type, sessions in TRADING_SESSIONS['best'].items():
            start = self._parse_utc_time(sessions['utc_start'])
            end = self._parse_utc_time(sessions['utc_end'])
            
            if start <= current_time_float <= end:
                # Check asset specific
                if asset and asset in sessions['assets']:
                    return True, {
                        'session': sessions['name'],
                        'quality': 'excellent',
                        'priority': sessions['priority'],
                        'expected_move': sessions['expected_moves'],
                        'description': sessions['description']
                    }
                elif not asset:
                    return True, {
                        'session': sessions['name'],
                        'quality': 'excellent',
                        'priority': sessions['priority']
                    }
        
        # Check moderate sessions
        for session_type, sessions in TRADING_SESSIONS['moderate'].items():
            start = self._parse_utc_time(sessions['utc_start'])
            end = self._parse_utc_time(sessions['utc_end'])
            
            if start <= current_time_float <= end:
                return True, {
                    'session': sessions['name'],
                    'quality': 'moderate',
                    'priority': sessions['priority'],
                    'expected_move': sessions['expected_moves']
                }
        
        # Check avoid times
        for avoid_type, avoid_data in TRADING_SESSIONS['avoid'].items():
            if 'utc_start' in avoid_data:
                start = self._parse_utc_time(avoid_data['utc_start'])
                end = self._parse_utc_time(avoid_data['utc_end'])
                
                if start <= current_time_float <= end:
                    return False, {
                        'reason': avoid_data['description'],
                        'quality': 'avoid',
                        'explanation': avoid_data['reason'],
                        'next_best': self._get_next_best_time(now)
                    }
        
        # Default: moderate
        return True, {
            'session': 'Regular hours',
            'quality': 'moderate',
            'priority': 7
        }
    
    def _parse_utc_time(self, time_str: str) -> float:
        """Parse UTC time string to float hours"""
        if ' ' in time_str:
            time_str = time_str.split(' ')[1]
        hour, minute = map(int, time_str.split(':'))
        return hour + minute / 60
    
    def _get_next_best_time(self, current: datetime) -> str:
        """Calculate next best trading time"""
        # Simplified - would check schedule
        current_hour = current.hour
        
        if current_hour < 17:  # Before 5:30 PM IST
            return "5:30 PM IST (US-Europe overlap)"
        elif current_hour < 19:  # Before 7:00 PM IST
            return "7:00 PM IST (US Market Open)"
        else:
            return "Tomorrow 5:30 AM IST (Asia Open)"
    
    def get_asset_recommendation(self, asset: str) -> Dict:
        """Get best times for specific asset"""
        
        asset_times = ASSET_BEST_TIMES.get(asset, ASSET_BEST_TIMES['BTC'])
        
        now = self.get_current_ist_time()
        is_good, time_info = self.is_best_time(asset)
        
        return {
            'asset': asset,
            'current_quality': time_info.get('quality', 'unknown'),
            'best_sessions': asset_times['primary'],
            'avoid_sessions': asset_times['avoid'],
            'should_trade_now': is_good and time_info.get('quality') in ['excellent', 'moderate']
        }
    
    def get_daily_schedule(self) -> List[Dict]:
        """Get full daily schedule in IST"""
        
        schedule = []
        
        for session_type, sessions in TRADING_SESSIONS['best'].items():
            ist_start = self._utc_to_ist(sessions['utc_start'])
            ist_end = self._utc_to_ist(sessions['utc_end'])
            
            schedule.append({
                'time': f"{ist_start} - {ist_end}",
                'name': sessions['name'],
                'quality': '⭐⭐⭐ EXCELLENT',
                'assets': ', '.join(sessions['assets']),
                'expected': sessions['expected_moves']
            })
        
        for session_type, sessions in TRADING_SESSIONS['moderate'].items():
            ist_start = self._utc_to_ist(sessions['utc_start'])
            ist_end = self._utc_to_ist(sessions['utc_end'])
            
            schedule.append({
                'time': f"{ist_start} - {ist_end}",
                'name': sessions['name'],
                'quality': '⭐⭐ MODERATE',
                'assets': ', '.join(sessions['assets']),
                'expected': sessions['expected_moves']
            })
        
        return sorted(schedule, key=lambda x: x['time'])
    
    def _utc_to_ist(self, utc_time: str) -> str:
        """Convert UTC time to IST"""
        hour, minute = map(int, utc_time.split(':'))
        ist_hour = (hour + 5) % 24
        ist_minute = (minute + 30) % 60
        if minute + 30 >= 60:
            ist_hour = (ist_hour + 1) % 24
        
        return f"{ist_hour:02d}:{ist_minute:02d}"
    
    def is_news_event_time(self) -> Tuple[bool, str]:
        """Check if near major news event"""
        # Would integrate with economic calendar API
        # For now, return False
        return False, "No major events"
    
    def get_sleep_duration(self) -> int:
        """Get seconds to sleep until next best time"""
        
        now = self.get_current_ist_time()
        is_good, info = self.is_best_time()
        
        if is_good and info.get('quality') == 'excellent':
            return 60  # Check every minute during best times
        
        elif is_good:
            return 300  # 5 minutes during moderate times
        
        else:
            return 600  # 10 minutes during avoid times

# Global instance
trading_hours = TradingHoursManager()

# Quick reference for manual trading
QUICK_REFERENCE = """
╔════════════════════════════════════════════════════════════╗
║           ⏰ BEST TRADING TIMES (IST)                      ║
╠════════════════════════════════════════════════════════════╣
║  🟢 EXCELLENT (Must Trade)                                 ║
║  ├─ 5:30 PM - 7:00 PM  → US-Europe Overlap                 ║
║  ├─ 7:00 PM - 9:30 PM  → US Market Open ⭐ BEST            ║
║  ├─ 1:30 AM - 2:30 AM  → US Close                          ║
║  └─ 5:30 AM - 7:30 AM  → Asia Open                         ║
╠════════════════════════════════════════════════════════════╣
║  🟡 MODERATE (Optional)                                    ║
║  ├─ 12:30 PM - 2:30 PM → Europe Open                       ║
║  └─ 11:30 AM - 12:30 PM → Asia Close                       ║
╠════════════════════════════════════════════════════════════╣
║  🔴 AVOID (Don't Trade)                                    ║
║  ├─ 9:30 AM - 12:30 PM → Post-Asia Dead Zone               ║
║  ├─ 7:30 AM - 9:30 AM  → Mid-Asia Quiet                    ║
║  ├─ Saturday All Day   → Weekend Low Vol                   ║
║  ├─ Sunday Until 5 AM  → Low Liquidity                     ║
║  └─ Thursday 9 PM+     → Weekly Expiry Risk                ║
╠════════════════════════════════════════════════════════════╣
║  ⚠️ SPECIAL AVOID                                          ║
║  ├─ FOMC/CPI/NFP days → Check economic calendar            ║
║  ├─ Monthly expiry Friday → After 1 PM IST                 ║
║  └─ Major exchange news → Wait 2 hours                     ║
╚════════════════════════════════════════════════════════════╝
"""
