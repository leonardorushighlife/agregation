import requests
import threading
import time
import socket
from datetime import datetime

class StealthProtection:
    def __init__(self, token, chat_id, hwid, on_block_callback, on_active_callback):
        self.token = token
        self.chat_id = chat_id
        self.hwid = hwid
        self.on_block_callback = on_block_callback
        self.on_active_callback = on_active_callback
        self.running = True
        self.last_update_id = 0

    def get_ip(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return "127.0.0.1"

    def send_notification(self, status):
        if not self.token or not self.chat_id: return
        ip = self.get_ip()
        date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        msg = (f"🚀 System Start\n"
               f"🆔 HWID: {self.hwid}\n"
               f"🌐 IP: {ip}\n"
               f"📅 Date: {date}\n"
               f"📊 Status: {status}")
        try:
            requests.post(f"https://api.telegram.org/bot{self.token}/sendMessage",
                          data={"chat_id": self.chat_id, "text": msg}, timeout=10)
        except: pass

    def poll(self):
        while self.running:
            if not self.token:
                time.sleep(30)
                continue
            try:
                resp = requests.get(f"https://api.telegram.org/bot{self.token}/getUpdates",
                                    params={"offset": self.last_update_id + 1, "timeout": 20}, timeout=25)
                if resp.status_code == 200:
                    data = resp.json()
                    for update in data.get("result", []):
                        self.last_update_id = update["update_id"]
                        message = update.get("message", {})
                        text = message.get("text", "").strip()
                        # Command format: "HWID block" or "HWID active"
                        if text:
                            parts = text.split()
                            if len(parts) >= 2:
                                target_hwid = parts[0].upper()
                                command = parts[1].lower()
                                if target_hwid == self.hwid:
                                    if command == "block":
                                        self.on_block_callback()
                                        self.reply(message.get("chat", {}).get("id"), f"✅ HWID {self.hwid} BLOCKED")
                                    elif command == "active":
                                        self.on_active_callback()
                                        self.reply(message.get("chat", {}).get("id"), f"✅ HWID {self.hwid} ACTIVATED")
            except:
                time.sleep(10)
            time.sleep(1)

    def reply(self, chat_id, text):
        try:
            requests.post(f"https://api.telegram.org/bot{self.token}/sendMessage",
                          data={"chat_id": chat_id, "text": text}, timeout=10)
        except: pass

    def start(self):
        threading.Thread(target=self.poll, daemon=True).start()

    def stop(self):
        self.running = False
