"""
Crypto Options Alpha Bot - Multi Asset Configuration
WebSocket + Webhook Support
"""

import os
from dotenv import load_dotenv

load_dotenv()

# Railway specific
PORT = int(os.getenv('PORT', 8080))
RAILWAY_STATIC_URL = os.getenv('RAILWAY_STATIC_URL', '')

# API Keys - Use Railway variables
BINANCE_API_KEY = os.getenv('BINANCE_API_KEY', '')
BINANCE_API_SECRET = os.getenv('BINANCE_API_SECRET', '')
COINDCX_API_KEY = os.getenv('COINDCX_API_KEY', '')
COINDCX_API_SECRET = os.getenv('COINDCX_API_SECRET', '')

# Telegram - Separate bot for alerts
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '')

# Webhook settings
WEBHOOK_ENABLED = os.getenv('WEBHOOK_ENABLED', 'false').lower() == 'true'
WEBHOOK_URL = os.getenv('WEBHOOK_URL', '')  # Railway URL
WEBHOOK_SECRET = os.getenv('WEBHOOK_SECRET', 'your_secret_here')

# WebSocket settings
WEBSOCKET_ENABLED = True
WEBSOCKET_RECONNECT_INTERVAL = 5  # seconds
WEBSOCKET_PING_INTERVAL = 20  # seconds

# Health check
HEALTH_CHECK_INTERVAL = 30  # seconds

# Multi-Asset Configuration
ASSETS_CONFIG = {
    'BTC': {
        'symbol': 'BTCUSDT',
        'coindcx_symbol': 'BTC-USDT',
        'min_quantity': 0.001,
        'strike_step': 100,
        'ws_streams': ['btcusdt@trade', 'btcusdt@depth20@100ms'],
        'enable': True
    },
    'ETH': {
        'symbol': 'ETHUSDT',
        'coindcx_symbol': 'ETH-USDT',
        'min_quantity': 0.01,
        'strike_step': 10,
        'ws_streams': ['ethusdt@trade', 'ethusdt@depth20@100ms'],
        'enable': True
    },
    'SOL': {
        'symbol': 'SOLUSDT',
        'coindcx_symbol': 'SOL-USDT',
        'min_quantity': 0.1,
        'strike_step': 1,
        'ws_streams': ['solusdt@trade', 'solusdt@depth20@100ms'],
        'enable': True
    }
}

# Trading Configuration
TRADING_CONFIG = {
    'assets': ['BTC', 'ETH', 'SOL'],
    'min_score_threshold': 85,
    'max_signals_per_day': 6,
    'max_signals_per_asset': 2,
    'max_open_positions': 3,
    'default_risk_per_trade': 0.01,
    'account_size': 100000,
    'min_expiry_hours': 6,
    'max_expiry_hours': 72,
    'correlation_threshold': 0.8,
}

# Asset Thresholds
ASSET_THRESHOLDS = {
    'BTC': {'ofi_threshold': 2.0, 'liquidity_sweep_size': 500000, 'min_gamma_wall': 1000000},
    'ETH': {'ofi_threshold': 1.5, 'liquidity_sweep_size': 300000, 'min_gamma_wall': 600000},
    'SOL': {'ofi_threshold': 1.0, 'liquidity_sweep_size': 100000, 'min_gamma_wall': 200000}
}

# Anti-Ban
STEALTH_CONFIG = {
    'enable_jitter': True,
    'min_request_delay': 1.5,
    'max_request_delay': 5.0,
    'max_requests_per_minute': 15,
    'user_agent_rotation': True,
    'websocket_primary': True,  # Use WebSocket as primary
}

# Logging
LOG_CONFIG = {
    'level': 'INFO',
    'file': 'bot.log',
    'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
}
