# language: Python 3.11 | file: app.py | Flask web server + bot manager bridge

from flask import Flask, render_template, request, jsonify
import os
from bot import BotManager, ACCOUNTS

app = Flask(__name__)
manager = BotManager()


@app.route("/")
def index():
    return render_template("index.html", accounts=ACCOUNTS)


@app.route("/start", methods=["POST"])
def start():
    data = request.get_json(force=True)
    live_url = data.get("live_url", "").strip()
    if not live_url:
        return jsonify({"error": "live_url required"}), 400

    cookies_map = data.get("cookies", {})          # {slot: cookie_string}
    custom_messages = data.get("custom_messages", {})  # {slot: message}
    interval = max(5, int(data.get("interval", 30)))

    manager.start(live_url, cookies_map, interval, custom_messages)
    return jsonify({"status": "started"})


@app.route("/stop", methods=["POST"])
def stop():
    manager.stop()
    return jsonify({"status": "stopped"})


@app.route("/status")
def status():
    return jsonify(manager.get_status())


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
