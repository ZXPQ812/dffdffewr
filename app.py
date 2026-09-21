from flask import Flask, render_template, request, jsonify
import os
from bot import BotManager, ACCOUNTS

app = Flask(__name__)
bot_manager = BotManager()

@app.route('/')
def index():
    return render_template('index.html', accounts=ACCOUNTS)

@app.route('/start', methods=['POST'])
def start():
    data = request.json
    live_url = data.get('live_url', '').strip()
    if not live_url:
        return jsonify({'error': 'No live URL provided'}), 400
    
    cookies_map = data.get('cookies', {})
    interval = int(data.get('interval', 30))
    custom_messages = data.get('custom_messages', {})
    
    bot_manager.start(live_url, cookies_map, interval, custom_messages)
    return jsonify({'status': 'started'})

@app.route('/stop', methods=['POST'])
def stop():
    bot_manager.stop()
    return jsonify({'status': 'stopped'})

@app.route('/status')
def status():
    return jsonify(bot_manager.get_status())

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
