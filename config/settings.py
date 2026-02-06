"""
Crypto Options Alpha Bot - Optimized Settings
High Quality Signal + Low Railway Resource Usage
"""

import os
from dotenv import load_dotenv

load_dotenv()

# Railway
PORT = int(os.getenv('PORT', 8080))

# API Keys
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '')

BINANCE_API_KEY = os.getenv('BINANCE_API_KEY', '')
BINANCE_API_SECRET = os.getenv('BINANCE_API_SECRET', '')

# Assets - Only BTC/ETH for quality (SOL removed to save resources)
ASSETS_CONFIG = {
    'BTC': {
        'symbol': 'BTCUSDT',
        'min_quantity': 0.001,
        'strike_step': 100,
        'enable': True,
        'ws_streams': ['btcusdt@trade', 'btcusdt@depth20@100ms'],
        'volatility_regime': 'medium',
        'weight': 0.6  # Higher weight for BTC
    },
    'ETH': {
        'symbol': 'ETHUSDT',
        'min_quantity': 0.01,
        'strike_step': 10,
        'enable': True,
        'ws_streams': ['ethusdt@trade', 'ethusdt@depth20@100ms'],
        'volatility_regime': 'high',
        'weight': 0.4
    }
}

# Trading - Adaptive Threshold System
TRADING_CONFIG = {
    'assets': ['BTC', 'ETH'],  # Focused for quality
    'min_score_threshold': 82,  # Sweet spot: 82 (was 85)
    'exceptional_threshold': 90,  # 90+ = Strong Take
    'max_signals_per_day': 4,  # Reduced for quality
    'max_signals_per_asset': 2,
    'default_risk_per_trade': 0.01,
    'account_size': 100000,
    'correlation_threshold': 0.8,
    'consecutive_pass_limit': 3,  # After 3 passes, lower threshold temporarily
    'adaptive_threshold': True,  # Auto-adjust based on market
}

# Stealth - Aggressive optimization for Railway Hobby
STEALTH_CONFIG = {
    'enable_jitter': True,
    'min_request_delay': 0.3,  # Reduced from 1.5
    'max_request_delay': 1.2,  # Reduced from 5.0
    'max_requests_per_minute': 30  # Increased from 15
}

# Cache settings to reduce API calls
CACHE_CONFIG = {
    'funding_rate_ttl': 300,  # 5 minutes
    'open_interest_ttl': 60,  # 1 minute
    'orderbook_ttl': 2,  # 2 seconds
}
