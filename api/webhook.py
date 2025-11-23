import os
import json
from http.server import BaseHTTPRequestHandler
import urllib.request

BOT_TOKEN = os.getenv("BOT_TOKEN")

def send_message(chat_id, text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = json.dumps({"chat_id": chat_id, "text": text}).encode("utf-8")

    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    urllib.request.urlopen(req)


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        try:
            update = json.loads(body.decode("utf-8"))

            message = update.get("message", {}).get("text")
            chat_id = update.get("message", {}).get("chat", {}).get("id")

            if message == "/event":
                send_message(chat_id, "Подія: спорт-бот працює!")

        except Exception as e:
            pass  # важливо — Telegram не любить 500 errors

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"ok": True}).encode("utf-8"))
