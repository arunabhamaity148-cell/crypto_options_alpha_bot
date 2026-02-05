"""
Flask Webhook Server for Railway
Health check + Telegram webhook + Status API
"""

import os
import logging
from flask import Flask, request, jsonify
from threading import Thread
from datetime import datetime

logger = logging.getLogger(__name__)

app = Flask(__name__)

# Bot instance (will be set from main)
bot_instance = None

@app.route('/')
def home():
    """Root endpoint"""
    return jsonify({
        'status': 'running',
        'bot': 'Crypto Options Alpha Bot',
        'version': '2.0',
        'timestamp': datetime.now().isoformat()
    })

@app.route('/health')
def health_check():
    """Railway health check endpoint"""
    try:
        status = {
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'uptime': 'running'
        }
        
        if bot_instance:
            status.update({
                'cycle_count': bot_instance.cycle_count,
                'active_trades': len(bot_instance.trade_monitor.active_trades) if hasattr(bot_instance, 'trade_monitor') else 0,
                'websocket_connected': getattr(bot_instance, 'ws_connected', False)
            })
        
        return jsonify(status), 200
        
    except Exception as e:
        logger.error(f"Health check error: {e}")
        return jsonify({'status': 'unhealthy', 'error': str(e)}), 500

@app.route('/webhook/telegram', methods=['POST'])
def telegram_webhook():
    """Telegram bot webhook"""
    try:
        data = request.get_json()
        
        # Process Telegram update
        if 'message' in data:
            message = data['message']
            text = message.get('text', '')
            chat_id = message.get('chat', {}).get('id')
            
            # Handle commands
            if text.startswith('/status'):
                return _handle_status_command()
            elif text.startswith('/trades'):
                return _handle_trades_command()
            elif text.startswith('/pause'):
                return _handle_pause_command()
            elif text.startswith('/resume'):
                return _handle_resume_command()
        
        return jsonify({'ok': True}), 200
        
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return jsonify({'ok': False, 'error': str(e)}), 500

@app.route('/api/signals')
def get_signals():
    """Get recent signals"""
    return jsonify({
        'signals': [],
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/stats')
def get_stats():
    """Get bot statistics"""
    if not bot_instance:
        return jsonify({'error': 'Bot not initialized'}), 503
    
    return jsonify({
        'cycle_count': bot_instance.cycle_count,
        'assets': bot_instance.asset_manager.active_assets if hasattr(bot_instance, 'asset_manager') else [],
        'timestamp': datetime.now().isoformat()
    })

def _handle_status_command():
    """Handle /status command"""
    if not bot_instance:
        return jsonify({'message': 'Bot initializing...'}), 200
    
    status = f"""
🤖 <b>Bot Status</b>

Cycles: {bot_instance.cycle_count}
Active Trades: {len(bot_instance.trade_monitor.active_trades)}
WebSocket: {'✅ Connected' if getattr(bot_instance, 'ws_connected', False) else '❌ Disconnected'}
Time: {datetime.now().strftime('%H:%M:%S')}
    """
    
    # Send via Telegram if available
    if hasattr(bot_instance, 'telegram'):
        asyncio.create_task(bot_instance.telegram.send_status(status))
    
    return jsonify({'message': 'Status sent'}), 200

def _handle_trades_command():
    """Handle /trades command"""
    if not bot_instance or not hasattr(bot_instance, 'trade_monitor'):
        return jsonify({'message': 'No active trades'}), 200
    
    summary = bot_instance.trade_monitor.get_active_trades_summary()
    
    if hasattr(bot_instance, 'telegram'):
        asyncio.create_task(bot_instance.telegram.send_status(summary))
    
    return jsonify({'message': 'Trades sent'}), 200

def _handle_pause_command():
    """Handle /pause command"""
    if bot_instance and hasattr(bot_instance, 'running'):
        # Don't stop, just pause new signals
        bot_instance.paused = True
        return jsonify({'message': 'Bot paused - no new signals'}), 200
    return jsonify({'message': 'Cannot pause'}), 400

def _handle_resume_command():
    """Handle /resume command"""
    if bot_instance and hasattr(bot_instance, 'paused'):
        bot_instance.paused = False
        return jsonify({'message': 'Bot resumed'}), 200
    return jsonify({'message': 'Cannot resume'}), 400

def start_webhook_server(bot, port=8080):
    """Start Flask server in background thread"""
    global bot_instance
    bot_instance = bot
    
    def run_server():
        app.run(
            host='0.0.0.0',
            port=port,
            threaded=True,
            debug=False,
            use_reloader=False
        )
    
    server_thread = Thread(target=run_server, daemon=True)
    server_thread.start()
    logger.info(f"🌐 Webhook server started on port {port}")
    
    return server_thread

# For gunicorn
application = app
