"""
Crypto Options Alpha Bot - Settings v3.0
Full Auto Mode Configuration
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

# Assets - Only BTC/ETH for quality
ASSETS_CONFIG = {
    'BTC': {
        'symbol': 'BTCUSDT',
        'min_quantity': 0.001,
        'strike_step': 100,
        'enable': True,
        'ws_streams': ['btcusdt@trade', 'btcusdt@depth20@250ms'],
        'volatility_regime': 'medium',
        'weight': 0.6
    },
    'ETH': {
        'symbol': 'ETHUSDT',
        'min_quantity': 0.01,
        'strike_step': 10,
        'enable': True,
        'ws_streams': ['ethusdt@trade', 'ethusdt@depth20@250ms'],
        'volatility_regime': 'high',
        'weight': 0.4
    }
}

# Trading - Full Auto Mode
TRADING_CONFIG = {
    'assets': ['BTC', 'ETH'],
    'min_score_threshold': 85,
    'exceptional_threshold': 92,
    'max_signals_per_day': 4,
    'max_signals_per_asset': 2,
    'default_risk_per_trade': 0.01,
    'account_size': 100000,
    'correlation_threshold': 0.8,
    'auto_mode': True,  # Full auto trading
    'circuit_breaker_enabled': True,
    'max_consecutive_losses': 3,
    'max_daily_losses': 5,
}

# Performance thresholds
PERFORMANCE_CONFIG = {
    'win_rate_threshold': 0.55,
    'profit_factor_threshold': 1.2,
    'min_trades_for_stats': 10,
}

# Risk levels
RISK_CONFIG = {
    'normal_size': 1.0,
    'high_size': 0.5,
    'extreme_size': 0.25,
    'friday_reduction': 0.5,
    'expiry_reduction': 0.3,
}

# Stealth
STEALTH_CONFIG = {
    'enable_jitter': True,
    'min_request_delay': 0.3,
    'max_request_delay': 1.2,
    'max_requests_per_minute': 30
}

# Auto-management
AUTO_CONFIG = {
    'breakeven_at_profit': 1.0,  # 1%
    'partial_close_at': 2.0,     # 2%
    'partial_close_percent': 0.5, # 50%
    'trail_stop_after': 3.0,     # 3%
    'trail_stop_distance': 1.0,   # 1%
}
