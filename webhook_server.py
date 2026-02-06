"""
Flask Webhook Server for Railway
Health check + Telegram webhook + Status API
"""

import os
import logging
import asyncio
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
                'cycle_count': getattr(bot_instance, 'cycle_count', 0),
                'active_trades': len(getattr(bot_instance, 'trade_monitor', {}).active_trades) if hasattr(bot_instance, 'trade_monitor') else 0,
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
        'cycle_count': getattr(bot_instance, 'cycle_count', 0),
        'assets': getattr(bot_instance, 'asset_manager', {}).active_assets if hasattr(bot_instance, 'asset_manager') else [],
        'timestamp': datetime.now().isoformat()
    })

def _handle_status_command():
    """Handle /status command"""
    if not bot_instance:
        return jsonify({'message': 'Bot initializing...'}), 200
    
    status = f"Bot Status: Cycle {getattr(bot_instance, 'cycle_count', 0)}"
    
    return jsonify({'message': status}), 200

def _handle_trades_command():
    """Handle /trades command"""
    return jsonify({'message': 'Active trades command received'}), 200

def _handle_pause_command():
    """Handle /pause command"""
    return jsonify({'message': 'Pause command received'}), 200

def _handle_resume_command():
    """Handle /resume command"""
    return jsonify({'message': 'Resume command received'}), 200

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
    logger.info(f"Webhook server started on port {port}")
    
    return server_thread

# For gunicorn
application = app
