"""
Crypto Options Alpha Bot - Settings
"""

import os
from dotenv import load_dotenv

load_dotenv()

# Railway
PORT = int(os.getenv('PORT', 8080))

# API Keys
BINANCE_API_KEY = os.getenv('BINANCE_API_KEY', '')
BINANCE_API_SECRET = os.getenv('BINANCE_API_SECRET', '')
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '')

# Assets
ASSETS_CONFIG = {
    'BTC': {
        'symbol': 'BTCUSDT',
        'min_quantity': 0.001,
        'strike_step': 100,
        'enable': True,
        'ws_streams': ['btcusdt@trade', 'btcusdt@depth20@100ms']
    },
    'ETH': {
        'symbol': 'ETHUSDT',
        'min_quantity': 0.01,
        'strike_step': 10,
        'enable': True,
        'ws_streams': ['ethusdt@trade', 'ethusdt@depth20@100ms']
    },
    'SOL': {
        'symbol': 'SOLUSDT',
        'min_quantity': 0.1,
        'strike_step': 1,
        'enable': True,
        'ws_streams': ['solusdt@trade', 'solusdt@depth20@100ms']
    }
}

# Trading
TRADING_CONFIG = {
    'assets': ['BTC', 'ETH', 'SOL'],
    'min_score_threshold': 85,
    'max_signals_per_day': 6,
    'max_signals_per_asset': 2,
    'default_risk_per_trade': 0.01,
    'account_size': 100000,
    'correlation_threshold': 0.8
}

# Stealth
STEALTH_CONFIG = {
    'enable_jitter': True,
    'min_request_delay': 1.5,
    'max_request_delay': 5.0,
    'max_requests_per_minute': 15
}
