"""
Flask Webhook Server
"""

import os
import logging
from flask import Flask, request, jsonify
from threading import Thread
from datetime import datetime

logger = logging.getLogger(__name__)

app = Flask(__name__)
bot_instance = None

@app.route('/')
def home():
    return jsonify({
        'status': 'running',
        'bot': 'Crypto Options Alpha Bot',
        'version': '2.0',
        'timestamp': datetime.now().isoformat()
    })

@app.route('/health')
def health_check():
    try:
        status = {
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
        }
        
        if bot_instance:
            status['cycle_count'] = getattr(bot_instance, 'cycle_count', 0)
        
        return jsonify(status), 200
        
    except Exception as e:
        logger.error(f"Health check error: {e}")
        return jsonify({'status': 'unhealthy', 'error': str(e)}), 500

@app.route('/webhook/telegram', methods=['POST'])
def telegram_webhook():
    try:
        data = request.get_json()
        
        if 'message' in data:
            message = data['message']
            text = message.get('text', '')
            
            if text.startswith('/status'):
                return jsonify({'message': 'Bot is running'}), 200
        
        return jsonify({'ok': True}), 200
        
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return jsonify({'ok': False, 'error': str(e)}), 500

def start_webhook_server(bot, port=8080):
    global bot_instance
    bot_instance = bot
    
    def run_server():
        app.run(host='0.0.0.0', port=port, threaded=True, debug=False, use_reloader=False)
    
    server_thread = Thread(target=run_server, daemon=True)
    server_thread.start()
    logger.info(f"Webhook server started on port {port}")
    
    return server_thread

application = app
