"""
Crypto Options Alpha Bot - Main Entry Point
Features: WebSocket, Trade Monitor, Structured Logging
"""

import os
import sys
import asyncio
import logging
import json
import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from threading import Thread

from flask import Flask, jsonify, request
from telegram import Bot

from config.settings import (
    PORT, 
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHAT_ID, 
    ASSETS_CONFIG, 
    TRADING_CONFIG, 
    STEALTH_CONFIG
)
from core.websocket_manager import ws_manager
from core.stealth_request import StealthRequest
from core.data_aggregator import DataAggregator, AssetData
from core.multi_asset_manager import MultiAssetManager, TradingSignal
from core.time_filter import TimeFilter
from core.news_guard import news_guard
from core.trade_monitor import TradeMonitor, ActiveTrade
from tg_bot.bot import AlphaTelegramBot

# ============== STRUCTURED LOGGING ==============
class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging"""
    def format(self, record):
        log_obj = {
            'timestamp': datetime.utcnow().isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno
        }
        
        # Add extra fields if present
        if hasattr(record, 'event'):
            log_obj['event'] = record.event
        if hasattr(record, 'asset'):
            log_obj['asset'] = record.asset
        if hasattr(record, 'score'):
            log_obj['score'] = record.score
        if hasattr(record, 'cycle'):
            log_obj['cycle'] = record.cycle
            
        return json.dumps(log_obj)

# Setup logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Console handler with JSON
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(JSONFormatter())
logger.addHandler(console_handler)

# Also add to root logger
logging.getLogger().handlers = [console_handler]

# ============== FLASK APP ==============
flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return {
        'status': 'running',
        'bot': 'Crypto Options Alpha Bot',
        'version': '2.0',
        'timestamp': datetime.utcnow().isoformat(),
        'features': ['websocket', 'trade_monitor', 'structured_logging']
    }

@flask_app.route('/health')
def health():
    """Health check with detailed status"""
    ws_status = 'connected' if ws_manager.running else 'disconnected'
    active_trades = len(getattr(flask_app, 'trade_monitor', {}).active_trades or [])
    
    return {
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat(),
        'websocket': ws_status,
        'active_trades': active_trades,
        'cycle': getattr(flask_app, 'cycle_count', 0)
    }, 200

@flask_app.route('/api/status')
def api_status():
    """Detailed API status"""
    return {
        'status': 'running',
        'version': '2.0',
        'timestamp': datetime.utcnow().isoformat(),
        'assets': list(ASSETS_CONFIG.keys()),
        'websocket_running': ws_manager.running,
        'price_data_symbols': list(ws_manager.price_data.keys()),
        'config': {
            'min_score': TRADING_CONFIG['min_score_threshold'],
            'max_signals_per_day': TRADING_CONFIG['max_signals_per_day']
        }
    }

@flask_app.route('/api/trades')
def api_trades():
    """Get active trades"""
    monitor = getattr(flask_app, 'trade_monitor', None)
    if not monitor:
        return {'active_trades': []}
    
    trades = []
    for trade in monitor.active_trades:
        trades.append({
            'asset': trade.asset,
            'direction': trade.direction,
            'entry': trade.entry_price,
            'current': trade.current_price,
            'pnl': trade.pnl_percent,
            'status': trade.status
        })
    
    return {'active_trades': trades}

# ============== MAIN BOT CLASS ==============
class AlphaBot:
    def __init__(self):
        self.telegram = AlphaTelegramBot(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)
        self.stealth = StealthRequest(STEALTH_CONFIG)
        self.data_agg = DataAggregator(self.stealth)
        self.asset_manager = MultiAssetManager(TRADING_CONFIG, ASSETS_CONFIG)
        self.time_filter = TimeFilter()
        self.trade_monitor = TradeMonitor(self.telegram)
        self.running = False
        self.cycle_count = 0
        
        # Reference for Flask
        flask_app.trade_monitor = self.trade_monitor
        flask_app.cycle_count = 0
        
    async def run(self):
        """Main bot loop with WebSocket and Trade Monitor"""
        self.running = True
        
        # Log structured startup
        logger.info("Bot starting", extra={
            'event': 'startup',
            'version': '2.0',
            'assets': TRADING_CONFIG['assets']
        })
        
        # Start WebSocket in background
        ws_task = asyncio.create_task(ws_manager.start(ASSETS_CONFIG))
        logger.info("WebSocket task created")
        
        # Wait for WebSocket to connect
        await asyncio.sleep(2)
        
        # Start Trade Monitor
        monitor_task = asyncio.create_task(
            self.trade_monitor.start_monitoring(self._get_current_price)
        )
        logger.info("Trade monitor task created")
        
        # Start Flask
        flask_thread = Thread(target=self._run_flask, daemon=True)
        flask_thread.start()
        
        # Send startup message
        try:
            await self.telegram.send_status(
                "🟢 <b>Bot Started v2.0</b>\n\n"
                f"<b>Features:</b> WebSocket, Trade Monitor, Structured Logging\n"
                f"<b>Assets:</b> {', '.join(TRADING_CONFIG['assets'])}\n"
                f"<b>Min Score:</b> {TRADING_CONFIG['min_score_threshold']}\n"
                f"<b>Max Signals:</b> {TRADING_CONFIG['max_signals_per_day']}/day\n\n"
                f"<i>WebSocket: Connected</i>\n"
                f"<i>Monitor: Active</i>"
            )
        except Exception as e:
            logger.error(f"Startup message failed: {e}")
        
        # Main loop
        while self.running:
            try:
                self.cycle_count += 1
                flask_app.cycle_count = self.cycle_count
                
                logger.info(f"Cycle {self.cycle_count} started", extra={
                    'event': 'cycle_start',
                    'cycle': self.cycle_count
                })
                
                # Check daily reset
                if self.asset_manager.should_reset_daily():
                    self.asset_manager.reset_daily_counters()
                    await self.telegram.send_status("🌅 <b>Daily counters reset</b>")
                
                # Check news guard
                trading_allowed, news_reason = await news_guard.check_trading_allowed()
                if not trading_allowed:
                    logger.warning("Trading halted", extra={
                        'event': 'trading_halted',
                        'reason': news_reason
                    })
                    await self.telegram.send_status(f"⏸️ <b>TRADING HALTED</b>\n\n{news_reason}")
                    await asyncio.sleep(300)
                    continue
                
                # Fetch market data (REST API backup)
                logger.info("Fetching market data...")
                market_data = await self.data_agg.get_all_assets_data(ASSETS_CONFIG)
                
                # Also get WebSocket data
                ws_data = self._get_websocket_data()
                
                logger.info(f"Data fetched", extra={
                    'event': 'data_fetched',
                    'rest_assets': len(market_data),
                    'ws_symbols': len(ws_data),
                    'cycle': self.cycle_count
                })
                
                # Merge data
                merged_data = self._merge_data(market_data, ws_data)
                
                # Generate signals
                if merged_data:
                    await self._process_market_data(merged_data)
                
                # Log cycle completion
                logger.info(f"Cycle {self.cycle_count} complete", extra={
                    'event': 'cycle_complete',
                    'cycle': self.cycle_count
                })
                
                await asyncio.sleep(60)
                
            except Exception as e:
                logger.error(f"Error in main loop: {str(e)}", extra={
                    'event': 'error',
                    'error': str(e),
                    'cycle': self.cycle_count
                }, exc_info=True)
                await asyncio.sleep(60)
    
    def _get_websocket_data(self) -> Dict:
        """Get data from WebSocket"""
        ws_data = {}
        for asset, config in ASSETS_CONFIG.items():
            if config.get('enable'):
                symbol = config['symbol']
                data = ws_manager.get_price_data(symbol)
                if data:
                    ws_data[asset] = data
        return ws_data
    
    def _merge_data(self, rest_data: Dict, ws_data: Dict) -> Dict:
        """Merge REST and WebSocket data"""
        merged = rest_data.copy()
        
        for asset, ws_info in ws_data.items():
            if asset in merged:
                # Update with real-time trades
                if 'trades' in ws_info:
                    merged[asset].recent_trades = ws_info['trades']
                # Update latest price
                if 'last_price' in ws_info:
                    merged[asset].spot_price = ws_info['last_price']
        
        return merged
    
    async def _get_current_price(self, asset: str) -> float:
        """Get current price for trade monitor"""
        # Try WebSocket first
        symbol = ASSETS_CONFIG[asset]['symbol']
        ws_data = ws_manager.get_price_data(symbol)
        if ws_data and 'last_price' in ws_data:
            return ws_data['last_price']
        
        # Fallback to REST
        try:
            price = await self.data_agg._get_spot_price(symbol)
            return price
        except:
            return 0
    
    async def _process_market_data(self, market_data: Dict):
        """Process market data and generate signals"""
        from strategies.liquidity_hunt import LiquidityHuntStrategy
        from strategies.gamma_squeeze import GammaSqueezeStrategy
        from indicators.greeks_engine import GreeksEngine
        from signals.scorer import AlphaScorer
        
        signals = []
        
        for asset, data in market_data.items():
            logger.info(f"Analyzing {asset}...", extra={
                'event': 'analysis_start',
                'asset': asset,
                'cycle': self.cycle_count
            })
            
            # Check limits
            if not self.asset_manager.can_send_signal(asset):
                logger.info(f"{asset}: Daily limit reached", extra={
                    'event': 'limit_reached',
                    'asset': asset
                })
                continue
            
            # Check time filter
            mock_setup = {'confidence': 90}
            time_ok, time_reason = self.time_filter.should_process_signal(asset, mock_setup)
            
            if not time_ok:
                logger.info(f"{asset}: Time filter skip - {time_reason}", extra={
                    'event': 'time_filter_skip',
                    'asset': asset,
                    'reason': time_reason
                })
                continue
            
            config = ASSETS_CONFIG[asset]
            
            # Get recent trades from WebSocket
            symbol = config['symbol']
            recent_trades = ws_manager.get_recent_trades(symbol, 50)
            
            # Strategy 1: Liquidity Hunt
            try:
                lh_strategy = LiquidityHuntStrategy(asset, config)
                lh_setup = await lh_strategy.analyze(
                    {'orderbook': data.orderbook}, 
                    recent_trades
                )
                
                if lh_setup:
                    lh_setup['asset'] = asset
                    signals.append(('liquidity_hunt', lh_setup))
                    logger.info(f"Signal found: Liquidity Hunt", extra={
                        'event': 'signal_found',
                        'asset': asset,
                        'strategy': 'liquidity_hunt',
                        'score': lh_setup.get('confidence', 0)
                    })
                    
            except Exception as e:
                logger.error(f"Liquidity Hunt error: {str(e)}", extra={
                    'event': 'strategy_error',
                    'asset': asset,
                    'strategy': 'liquidity_hunt',
                    'error': str(e)
                })
            
            # Strategy 2: Gamma Squeeze
            try:
                greeks = GreeksEngine()
                gs_strategy = GammaSqueezeStrategy(asset, config, greeks)
                
                options_chain = []  # Would come from API
                gs_setup = await gs_strategy.analyze(
                    {'orderbook': data.orderbook},
                    options_chain
                )
                
                if gs_setup:
                    gs_setup['asset'] = asset
                    signals.append(('gamma_squeeze', gs_setup))
                    logger.info(f"Signal found: Gamma Squeeze", extra={
                        'event': 'signal_found',
                        'asset': asset,
                        'strategy': 'gamma_squeeze',
                        'score': gs_setup.get('confidence', 0)
                    })
                    
            except Exception as e:
                logger.error(f"Gamma Squeeze error: {str(e)}", extra={
                    'event': 'strategy_error',
                    'asset': asset,
                    'strategy': 'gamma_squeeze',
                    'error': str(e)
                })
        
        # Score and send signals
        if signals:
            await self._score_and_send_signals(signals, market_data)
    
    async def _score_and_send_signals(self, signals: List[tuple], market_data: Dict):
        """Score signals and send to Telegram"""
        from signals.scorer import AlphaScorer
        
        scored_signals = []
        scorer = AlphaScorer(TRADING_CONFIG)
        
        for strategy_name, setup in signals:
            asset = setup['asset']
            data = market_data.get(asset)
            
            if not data:
                continue
            
            score = scorer.calculate_score(
                setup, 
                {'orderbook': data.orderbook},
                news_status="safe",
                time_quality="excellent"
            )
            
            setup['score_data'] = score
            scored_signals.append((strategy_name, setup, score))
            
            logger.info(f"Scored {asset}", extra={
                'event': 'signal_scored',
                'asset': asset,
                'score': score['total_score'],
                'recommendation': score['recommendation']
            })
        
        # Sort by score
        scored_signals.sort(key=lambda x: x[2]['total_score'], reverse=True)
        
        # Filter and send
        trading_signals = []
        for strategy_name, setup, score in scored_signals:
            if score['recommendation'] in ['take', 'strong_take']:
                signal = TradingSignal(
                    asset=setup['asset'],
                    strategy=strategy_name,
                    direction=setup['direction'],
                    entry_price=setup['entry_price'],
                    stop_loss=setup['stop_loss'],
                    target_1=setup['target_1'],
                    target_2=setup['target_2'],
                    strike_selection=setup['strike_selection'],
                    expiry_suggestion=setup['expiry_suggestion'],
                    confidence=setup['confidence'],
                    score_breakdown=score['component_scores'],
                    rationale=setup['rationale'],
                    timestamp=datetime.now()
                )
                trading_signals.append(signal)
        
        # Filter correlated signals
        filtered_signals = self.asset_manager.filter_correlated_signals(trading_signals)
        
        # Send top signals and add to trade monitor
        for signal in filtered_signals[:TRADING_CONFIG['max_signals_per_day']]:
            if not self.asset_manager.can_send_signal(signal.asset):
                continue
            
            original = next((s for s in scored_signals if s[1]['asset'] == signal.asset), None)
            if not original:
                continue
            
            _, setup, score = original
            
            try:
                # Send to Telegram
                await self.telegram.send_signal(setup, score, {
                    'orderbook': market_data[signal.asset].orderbook
                })
                
                # Add to trade monitor
                trade = ActiveTrade(
                    asset=signal.asset,
                    direction=signal.direction,
                    entry_price=signal.entry_price,
                    stop_loss=signal.stop_loss,
                    tp1=signal.target_1,
                    tp2=signal.target_2,
                    strike=signal.strike_selection,
                    expiry=datetime.now() + timedelta(hours=48),
                    position_size=self.asset_manager.calculate_position_size(
                        signal.asset, signal.entry_price, signal.stop_loss
                    )
                )
                self.trade_monitor.add_trade(trade)
                
                self.asset_manager.record_signal(signal.asset)
                
                logger.info(f"Signal sent and monitored", extra={
                    'event': 'signal_sent',
                    'asset': signal.asset,
                    'score': score['total_score'],
                    'entry': signal.entry_price,
                    'stop': signal.stop_loss
                })
                
                await asyncio.sleep(2)
                
            except Exception as e:
                logger.error(f"Failed to send signal: {str(e)}", extra={
                    'event': 'signal_send_failed',
                    'asset': signal.asset,
                    'error': str(e)
                })
    
    def _run_flask(self):
        """Run Flask server"""
        try:
            flask_app.run(
                host='0.0.0.0',
                port=PORT,
                threaded=True,
                debug=False,
                use_reloader=False
            )
        except Exception as e:
            logger.error(f"Flask error: {e}")
    
    def stop(self):
        """Stop bot"""
        self.running = False
        ws_manager.stop()
        self.trade_monitor.stop_monitoring()
        logger.info("Bot stopped", extra={'event': 'shutdown'})

# ============== ENTRY POINT ==============
if __name__ == "__main__":
    bot = AlphaBot()
    try:
        asyncio.run(bot.run())
    except KeyboardInterrupt:
        bot.stop()
        logger.info("Stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        raise
