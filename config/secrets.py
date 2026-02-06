"""
API Secrets - CoinDCX Added
"""

import os
from dotenv import load_dotenv

load_dotenv()

# Telegram
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '')

# Binance
BINANCE_API_KEY = os.getenv('BINANCE_API_KEY', '')
BINANCE_API_SECRET = os.getenv('BINANCE_API_SECRET', '')

# CoinDCX (NEW)
COINDCX_API_KEY = os.getenv('COINDCX_API_KEY', '')
COINDCX_API_SECRET = os.getenv('COINDCX_API_SECRET', '')
