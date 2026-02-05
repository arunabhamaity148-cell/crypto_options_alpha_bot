"""
Crypto Options Alpha Bot - Multi Asset Configuration
BTC + ETH + SOL Support
"""

import os
from dotenv import load_dotenv

load_dotenv()

# API Keys
BINANCE_API_KEY = os.getenv('BINANCE_API_KEY', '')
BINANCE_API_SECRET = os.getenv('BINANCE_API_SECRET', '')
COINDCX_API_KEY = os.getenv('COINDCX_API_KEY', '')
COINDCX_API_SECRET = os.getenv('COINDCX_API_SECRET', '')
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '')

# Multi-Asset Configuration
ASSETS_CONFIG = {
    'BTC': {
        'symbol': 'BTCUSDT',
        'coindcx_symbol': 'BTC-USDT',
        'min_quantity': 0.001,
        'strike_step': 100,
        'tick_size': 0.01,
        'volatility_regime': 'medium',
        'weight': 0.4,
        'enable': True
    },
    'ETH': {
        'symbol': 'ETHUSDT',
        'coindcx_symbol': 'ETH-USDT',
        'min_quantity': 0.01,
        'strike_step': 10,
        'tick_size': 0.01,
        'volatility_regime': 'high',
        'weight': 0.35,
        'enable': True
    },
    'SOL': {
        'symbol': 'SOLUSDT',
        'coindcx_symbol': 'SOL-USDT',
        'min_quantity': 0.1,
        'strike_step': 1,
        'tick_size': 0.001,
        'volatility_regime': 'very_high',
        'weight': 0.25,
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
    'account_size': 100000,  # USDT
    'min_expiry_hours': 6,
    'max_expiry_hours': 72,
    'correlation_threshold': 0.8,
}

# Asset-Specific Thresholds
ASSET_THRESHOLDS = {
    'BTC': {
        'ofi_threshold': 2.0,
        'liquidity_sweep_size': 500000,
        'min_gamma_wall': 1000000,
        'min_volume_24h': 1000000000,
    },
    'ETH': {
        'ofi_threshold': 1.5,
        'liquidity_sweep_size': 300000,
        'min_gamma_wall': 600000,
        'min_volume_24h': 500000000,
    },
    'SOL': {
        'ofi_threshold': 1.0,
        'liquidity_sweep_size': 100000,
        'min_gamma_wall': 200000,
        'min_volume_24h': 100000000,
    }
}

# Anti-Ban Configuration
STEALTH_CONFIG = {
    'enable_jitter': True,
    'min_request_delay': 1.5,
    'max_request_delay': 5.0,
    'max_requests_per_minute': 15,
    'user_agent_rotation': True,
    'websocket_reconnect': True,
    'enable_proxy': False,
    'proxy_list': [],
}

# Data Configuration
DATA_CONFIG = {
    'primary_timeframe': '5m',
    'secondary_timeframe': '15m',
    'tertiary_timeframe': '1h',
    'orderbook_depth': 100,
    'historical_lookback': 500,
    'websocket_ping_interval': 30,
}

# Strategy Weights
STRATEGY_WEIGHTS = {
    'liquidity_hunt': 0.35,
    'gamma_squeeze': 0.30,
    'delta_arbitrage': 0.20,
    'whale_footprint': 0.15,
}

# Logging
LOG_CONFIG = {
    'level': 'INFO',
    'file': 'bot.log',
    'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
}
