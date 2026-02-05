"""
News Guard - Economic Calendar & Event Filter
Prevents trading during high-impact events
"""

import asyncio
import logging
from typing import Dict, List, Tuple, Optional
from datetime import datetime, timedelta
import aiohttp
import json

logger = logging.getLogger(__name__)

class NewsGuard:
    """Guards against high-impact news events"""
    
    # High impact events - always avoid
    HIGH_IMPACT_EVENTS = {
        'FOMC': {
            'name': 'FOMC Meeting',
            'impact': 'extreme',
            'avoid_before_minutes': 120,  # 2 hours before
            'avoid_after_minutes': 60,    # 1 hour after
            'assets_affected': ['BTC', 'ETH', 'SOL'],
            'typical_move': '3-8%'
        },
        'CPI': {
            'name': 'CPI Inflation Data',
            'impact': 'extreme',
            'avoid_before_minutes': 60,
            'avoid_after_minutes': 120,
            'assets_affected': ['BTC', 'ETH', 'SOL'],
            'typical_move': '2-5%'
        },
        'PPI': {
            'name': 'PPI Producer Price',
            'impact': 'high',
            'avoid_before_minutes': 60,
            'avoid_after_minutes': 60,
            'assets_affected': ['BTC', 'ETH'],
            'typical_move': '2-4%'
        },
        'NFP': {
            'name': 'Non-Farm Payroll',
            'impact': 'extreme',
            'avoid_before_minutes': 60,
            'avoid_after_minutes': 90,
            'assets_affected': ['BTC', 'ETH', 'SOL'],
            'typical_move': '3-6%'
        },
        'GDP': {
            'name': 'GDP Report',
            'impact': 'high',
            'avoid_before_minutes': 30,
            'avoid_after_minutes': 60,
            'assets_affected': ['BTC', 'ETH'],
            'typical_move': '2-4%'
        },
        'UNEMPLOYMENT': {
            'name': 'Unemployment Rate',
            'impact': 'high',
            'avoid_before_minutes': 30,
            'avoid_after_minutes': 60,
            'assets_affected': ['BTC', 'ETH'],
            'typical_move': '2-4%'
        }
    }
    
    # Crypto-specific events
    CRYPTO_EVENTS = {
        'ETF_APPROVAL': {
            'name': 'Bitcoin ETF Decision',
            'impact': 'extreme',
            'avoid_before_minutes': 240,  # 4 hours
            'avoid_after_minutes': 180,
            'assets_affected': ['BTC'],
            'typical_move': '5-15%'
        },
        'HALVING': {
            'name': 'Bitcoin Halving',
            'impact': 'high',
            'avoid_before_minutes': 60,
            'avoid_after_minutes': 120,
            'assets_affected': ['BTC'],
            'typical_move': '2-5%'
        },
        'EXCHANGE_HACK': {
            'name': 'Major Exchange Hack',
            'impact': 'extreme',
            'avoid_before_minutes': 0,  # Immediate
            'avoid_after_minutes': 180,
            'assets_affected': ['BTC', 'ETH', 'SOL'],
            'typical_move': '5-20%',
            'auto_detect': True
        },
        'SEC_ANNOUNCEMENT': {
            'name': 'SEC Crypto Announcement',
            'impact': 'extreme',
            'avoid_before_minutes': 0,
            'avoid_after_minutes': 240,
            'assets_affected': ['BTC', 'ETH', 'SOL'],
            'typical_move': '5-15%',
            'auto_detect': True
        },
        'LARGE_LIQUIDATION': {
            'name': 'Mass Liquidation Event',
            'impact': 'high',
            'avoid_before_minutes': 0,
            'avoid_after_minutes': 60,
            'assets_affected': ['BTC', 'ETH', 'SOL'],
            'typical_move': '3-8%',
            'auto_detect': True,
            'threshold': 100000000  # $100M liquidated
        }
    }
    
    # Monthly schedule (approximate - should fetch from API)
    MONTHLY_EVENTS = {
        # First Friday of every month
        'NFP': {'day': 'first_friday', 'time': '12:30'},
        # CPI: Second Wednesday of month
        'CPI': {'day': 'second_wednesday', 'time': '12:30'},
        # PPI: Second Thursday of month
        'PPI': {'day': 'second_thursday', 'time': '12:30'},
        # FOMC: 8 times per year (approximate dates)
        'FOMC_2024': [
            '2024-01-31', '2024-03-20', '2024-05-01', '2024-06-12',
            '2024-07-31', '2024-09-18', '2024-11-07', '2024-12-18'
        ]
    }
    
    def __init__(self):
        self.active_events = []
        self.last_check = None
        self.price_volatility_cache = {}
        
    async def check_trading_allowed(self, asset: str = None) -> Tuple[bool, str]:
        """
        Check if trading is allowed now
        Returns: (allowed, reason)
        """
        
        now = datetime.utcnow()
        
        # Check scheduled economic events
        for event_type, event_info in self.HIGH_IMPACT_EVENTS.items():
            if self._is_near_event(event_type, event_info, now):
                return False, f"🛑 HIGH IMPACT EVENT: {event_info['name']}"
        
        # Check crypto-specific events
        for event_type, event_info in self.CRYPTO_EVENTS.items():
            if event_info.get('auto_detect'):
                detected = await self._detect_crypto_event(event_type, event_info, asset)
                if detected:
                    return False, f"🛑 CRYPTO EVENT: {event_info['name']}"
        
        # Check recent volatility spike (indicates news)
        volatility_spike = await self._check_volatility_spike(asset)
        if volatility_spike:
            return False, f"⚠️ VOLATILITY SPIKE: Likely news event, avoiding"
        
        # Check if within 30 min of hour (funding reset)
        if now.minute >= 55 or now.minute <= 5:
            if asset:  # Only for perp trading
                return True, "⏰ Funding reset time - caution advised"
        
        return True, "✅ No high-impact events detected"
    
    def _is_near_event(self, event_type: str, event_info: Dict, now: datetime) -> bool:
        """Check if currently near a scheduled event"""
        
        # For FOMC, check specific dates
        if event_type == 'FOMC':
            fomc_dates = self.MONTHLY_EVENTS.get('FOMC_2024', [])
            for date_str in fomc_dates:
                event_time = datetime.strptime(date_str, '%Y-%m-%d')
                event_time = event_time.replace(hour=18, minute=0)  # 6 PM UTC
                
                diff = abs((now - event_time).total_seconds() / 60)
                
                if diff <= event_info['avoid_before_minutes']:
                    return True
                if diff <= event_info['avoid_after_minutes']:
                    return True
        
        # For monthly events (CPI, NFP, etc)
        if event_type in ['CPI', 'PPI', 'NFP']:
            # Check if today is the event day (simplified)
            if self._is_event_day(event_type, now):
                event_hour, event_min = map(int, self.MONTHLY_EVENTS[event_type]['time'].split(':'))
                event_time = now.replace(hour=event_hour, minute=event_min, second=0)
                
                diff = abs((now - event_time).total_seconds() / 60)
                
                if diff <= event_info['avoid_before_minutes']:
                    return True
                if diff <= event_info['avoid_after_minutes']:
                    return True
        
        return False
    
    def _is_event_day(self, event_type: str, date: datetime) -> bool:
        """Check if given date is an event day"""
        # Simplified - would use actual calendar API
        if event_type == 'NFP':
            # First Friday
            return date.weekday() == 4 and date.day <= 7
        elif event_type == 'CPI':
            # Second Wednesday
            return date.weekday() == 2 and 8 <= date.day <= 14
        elif event_type == 'PPI':
            # Second Thursday
            return date.weekday() == 3 and 8 <= date.day <= 14
        return False
    
    async def _detect_crypto_event(self, event_type: str, event_info: Dict, asset: str) -> bool:
        """Auto-detect crypto events from market data"""
        
        if event_type == 'LARGE_LIQUIDATION':
            # Check recent liquidation data
            # Would fetch from Coinglass or similar API
            return False  # Placeholder
        
        elif event_type == 'EXCHANGE_HACK':
            # Detect unusual price action across exchanges
            return False  # Placeholder
        
        elif event_type == 'SEC_ANNOUNCEMENT':
            # Detect sudden volatility without news
            return False  # Placeholder
        
        return False
    
    async def _check_volatility_spike(self, asset: str = None) -> bool:
        """Detect unusual volatility indicating news"""
        
        # Check if price moved >2% in last 5 minutes
        # Would need recent price data
        return False  # Placeholder
    
    async def fetch_economic_calendar(self) -> List[Dict]:
        """Fetch upcoming events from Forex Factory or similar"""
        
        try:
            # Forex Factory API or scraping
            # For now, return hardcoded near-term events
            
            now = datetime.utcnow()
            upcoming = []
            
            # Add next FOMC if within 7 days
            for date_str in self.MONTHLY_EVENTS.get('FOMC_2024', []):
                event_date = datetime.strptime(date_str, '%Y-%m-%d')
                days_until = (event_date - now).days
                
                if 0 <= days_until <= 7:
                    upcoming.append({
                        'event': 'FOMC',
                        'date': date_str,
                        'days_until': days_until,
                        'impact': 'extreme'
                    })
            
            return upcoming
            
        except Exception as e:
            logger.error(f"Calendar fetch error: {e}")
            return []
    
    def get_next_event_warning(self) -> str:
        """Get warning about upcoming events"""
        
        now = datetime.utcnow()
        warnings = []
        
        # Check next 24 hours:        for event_type, event_info in {**self.HIGH_IMPACT_EVENTS, **self.CRYPTO_EVENTS}.items():
            if event_type in ['FOMC', 'CPI', 'NFP']:
                # Would calculate actual str next occurrence
                pass
        
        if warnings:
            return "\n".join(warnings)
        return "No major events in next 24 hours"
    
    def get_safe_trading_window(self) -> Tuple[datetime, datetime]:
        """Calculate next safe trading window"""
        
        now = datetime.utcnow()
        
        # Find next event
        next_event = None
        min_time = float('inf')
        
        for date_str in self.MONTHLY_EVENTS.get('FOMC_2024', []):
            event_time = datetime.strptime(date_str, '%Y-%m-%d')
            event_time = event_time.replace(hour=16, minute=0)  # 2 hours before
            
            time_until = (event_time - now).total_seconds()
            if 0 < time_until < min_time:
                min_time = time_until
                next_event = event_time
        
        if next_event:
            safe_start = now
            safe_end = next_event - timedelta(hours=2)
            return safe_start, safe_end
        
        return now, now + timedelta(days=1)
    
    async def get:
_sentiment(self        """ -> Dict:
        """Get current news sentiment from CryptoPanic or similar"""
        
        try:
            # Would integrate with news API
            return {
               Detectsent unusual': 'neutral indicating                'breaking_news': False,
                news 'major_headlines': []
            }
        except:
            return {'sentiment': 'unknown"""
'}

# Global instance
news_guard = NewsGuard()

# Quick reference
NEWS_QUICK_REFERENCE = """
╔══════════════════════════════════════════════════════════════╗
║              🛡️ NEWS GUARD REFERENCE                         ║
╠══════════════════════════════════════════════════════════════╣
║  🔴 EXTREME IMPACT - AVOID COMPLETELY                        ║
║  ├─ FOMC (Fed Meeting)                     → if  moved >hr before in to 51 minutes
        # Would needhr after║
         ├─ # Place (
    
    async def fetch                 → 1hr before -> to List[Dict]:
        """
Fetch║ upcoming  ├─ ForexFP Factory (Jobs Report        
               → 1hr # Forex Factory API or5hr            # For now, return ├─ ETF near/SEC
            
           → Immediate effect.utcnow ║            upcoming  []
            
            # Add Hack (> $100MOMC if within → Until confirmed days safe
            ║ for date╠════════════════ in════════════════════════════════.MON══════════════╣TH
LY _EVENTS.get('F IMPACT - CAUTION                                      ║
║ []  ├─ PPI (_dateProducer Prices) datetime.str →ptime(datehr, '%Yafter       ║
d  ├')
─ GDP Report                      = → 30min - nowafter).     ║
║  ├0─ Un days_until Rate <=               → 30min7 before:
                   after    .append
║  └─ Bitcoin                        'event →  'FOM before',
 to '2hrdate': date_str════════════════════════════════════════════════════════ days_until,

║ 'impact 🟡': ' IMPreme'
                    })
 SIZE                                ║ return upcoming║
            
  except ExceptionOMC:
            ( logger meeting.error     "Calendar 30min fetch error:after    e}")

║  ├─ Retail def get →_next30min before_event_warning     ║
║:
 └─ Large Exchange Out about          → Until"""
        
 ║
       ══════════════════════════════════════════════════════════════╣
║ = ⚠️        
 WARNING SIG #NS Check ( next                               
║ hours
        for event  ├ event_info > {**self.HIGH_IMP 5 minutes          , **self.Cely}., avoid                if║  ├─ FundingFOMC', 'C0. '% or <-               0 #.1%    → Extreme sentiment      Would
║  ├
                pass$100M liquidated            return n".join(warnings)
        return "Nohr        → Cascade risk           ║
║  └─ Exchange major issues in → 24 hours"
    
    ║
╠════════════════_tr════════════════════════(self) ->
[datetime  datetime 📅]:
       4 FOMC DATES"""
UTC 18 now =)                              .utcnow
║ #  next event
        next  = None
        1_time = ├─ Julyinf31        
       ─ November 7 self.MON
LY .get('F 20    ├─ June 12):
 ├            Sept _time  ├─ptime 18     , '% ║-%m-%════════════════')
══════════════ event
_time = event## **(hour: `main.py` (16 Guard minute)**

```python
 # Add import
from core.news_guard import news_guard, beforeICK            time_until = (Bot_time.__init__:
total_seconds_guard()
            if 0 < time_until < min run:
                   """ min loop with = time_until.running                True if
    
    # Send startup info with news next_event               safe_start = now
            safe.news_guard.fetch_economic_calendar()
    calendar_msg =_event📅 U(hours EVENT2)
n"
    for event in upcoming
        
        calendar_msg += f"•(days=1event']    asyncevent getdate_sent ({(self)[' -> Dict:
        """Get current newsn"
    
    await self.telegram"""
_status        
        try:
            # Would integrate with news API
            return {
                'sentiment': 'neutral',
                'breaking_news': False,
                'major_headlines': []
            }
        except:
            return {'sentiment': 'unknown'}

# Global instance
news_guard = NewsGuard()

# Quick reference
NEWS_QUICK_REFERENCE = """
╔══════════════════════════════════════════════════════════════╗
║              🛡️ NEWS GUARD REFERENCE                         ║
╠════════════════        calendar══════════════════════════════════════════════╣
║  🔴 EXTREME IMPACT - AVOID COMPLETELY                        ║
║  ├─ FOMC (" +
        NEWS              → 
    )
    
    while self.running:
        try:
            # CHECK NEWS GUARD FIRST─.news CPI.check (Infl()
ation            if not trading_allowed:
                logger1hr before"🛑 {news }")
                await self.telegram.send_status(f"⏸️ TRADING HALTED\n\n{news_reason}")
                await asyncio.sleep(300) . Check every 5 minutes5                continue
            
            if "║aution"║  ├─ ETF Approval/SEC News           →️ effect {news_reason}")
            
            # Rest of existing code...
            # (> $100M implementation         → Until confirmed safe   ║ except Exception as e:
════════════════════════════════.error══════════════════════════════╣
║  🟠 HIGH IMPACT - CAUTION                                      ║
║  ├─ PPI (Producer Prices)           → 1hr before/after       ║
║  ├─ GDP Report                      → 30min before/after     ║
║  ├─ Unemployment Rate               → 30min before/after     ║
║  └─ Bitcoin Halving                 → 1hr before to 2hr after║
╠══════════════════════════════════════════════════════════════╣
║  🟡 MEDIUM IMPACT - REDUCE SIZE                                ║
║  ├─ FOMC Minutes (not meeting)      → 30min before/after     ║
║  ├─ Retail Sales                    → 30min before/after     ║
║  └─ Large Exchange Outflow          → Until confirmed        ║
╠══════════════════════════════════════════════════════════════╣
║  ⚠️ WARNING SIGNS (Auto-Detect)                               ║
║  ├─ >3% move in 5 minutes           → Likely news, avoid     ║
║  ├─ Funding rate >0.1% or <-0.1%    → Extreme sentiment      ║
║  ├─ >$100M liquidated in 1hr        → Cascade risk           ║
║  └─ Exchange API issues             → Stop all trading       ║
╠══════════════════════════════════════════════════════════════╣
║  📅 2024 FOMC DATES (UTC 18:00)                               ║
║  ├─ January 31  ├─ May 1    ├─ July 31  ├─ November 7       ║
║  ├─ March 20    ├─ June 12  ├─ Sept 18  ├─ December 18      ║
╚══════════════════════════════════════════════════════════════╝
"""
