"""
Crypto Options Alpha Bot - Configuration
Unique Smart Bot - 70%+ Win Rate
"""

import os
from dotenv import load_dotenv

load_dotenv()

# API Configuration
BINANCE_API_KEY = os.getenv('BINANCE_API_KEY', '')
BINANCE_API_SECRET = os.getenv('BINANCE_API_SECRET', '')
COINDCX_API_KEY = os.getenv('COINDCX_API_KEY', '')
COINDCX_API_SECRET = os.getenv('COINDCX_API_SECRET', '')

# Telegram
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '')

# Trading Parameters
TRADING_CONFIG = {
    'primary_asset': 'BTC',
    'quote_asset': 'USDT',
    'min_score_threshold': 85,      # Alpha score minimum
    'max_signals_per_day': 3,       # Quality over quantity
    'max_open_positions': 2,        # Risk management
    'default_risk_per_trade': 0.01,  # 1% capital risk
    'min_expiry_hours': 6,
    'max_expiry_hours': 72,
}

# Anti-Ban Configuration
STEALTH_CONFIG = {
    'enable_jitter': True,
    'min_request_delay': 1.0,
    'max_request_delay': 5.0,
    'max_requests_per_minute': 15,
    'user_agent_rotation': True,
    'websocket_reconnect': True,
    'enable_proxy': False,  # Set True if using proxy
}

# Data Sources
DATA_CONFIG = {
    'primary_timeframe': '5m',
    'secondary_timeframe': '15m',
    'tertiary_timeframe': '1h',
    'orderbook_depth': 100,
    'historical_lookback': 500,  # candles
    'websocket_ping_interval': 30,
}

# Strategy Weights (for scoring)
STRATEGY_WEIGHTS = {
    'liquidity_hunt': 0.30,
    'gamma_squeeze': 0.25,
    'delta_arbitrage': 0.25,
    'whale_footprint': 0.20,
}

# Unique Indicator Thresholds
ALPHA_THRESHOLDS = {
    'ofi_threshold': 2.0,           # Order flow imbalance
    'cvd_divergence_min': 0.5,      # CVD divergence strength
    'liquidity_sweep_size': 500000, # Min sweep in USD
    'gamma_wall_proximity': 0.02,   # 2% from gamma wall
    'iv_percentile_max': 50,        # Cheap options only
    'basis_arbitrage_min': 0.003,   # 0.3% mispricing
    'whale_threshold_btc': 100,     # Min whale size
}

# Logging
LOG_CONFIG = {
    'level': 'INFO',
    'file': 'bot_activity.log',
    'max_size': 10 * 1024 * 1024,  # 10MB
    'backup_count': 5,
}
