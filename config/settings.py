"""
Crypto Options Alpha Bot - Settings v3.1
Sleep Mode Configuration - Railway Resource Optimized
"""

import os
from dotenv import load_dotenv

load_dotenv()

PORT = int(os.getenv('PORT', 8080))
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '')

# Assets
ASSETS_CONFIG = {
    'BTC': {
        'symbol': 'BTCUSDT',
        'strike_step': 100,
        'enable': True,
    },
    'ETH': {
        'symbol': 'ETHUSDT',
        'strike_step': 10,
        'enable': True,
    }
}

# Trading - Golden Hours Only
TRADING_CONFIG = {
    'assets': ['BTC', 'ETH'],
    'min_score_threshold': 85,
    'max_signals_per_day': 4,
    'max_signals_per_asset': 2,
    'default_risk_per_trade': 0.01,
    'account_size': 100000,
}

# Stealth config (REQUIRED for main.py)
STEALTH_CONFIG = {
    'enable_jitter': True,
    'min_request_delay': 0.3,
    'max_request_delay': 1.2,
    'max_requests_per_minute': 30
}

# Golden Hours (IST)
GOLDEN_HOURS = {
    'enabled': True,
    'windows': [
        {'start': '19:00', 'end': '21:30'},  # US Market Open
    ],
    'trading_days': ['Mon', 'Tue', 'Wed', 'Thu'],  # Friday OFF
    'friday_enabled': False,
}

# Sleep Mode
SLEEP_CONFIG = {
    'deep_sleep': True,
    'wake_before_minutes': 2,
    'health_check_interval': 300,  # 5 min during sleep
}
