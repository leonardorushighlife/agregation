import requests
import threading
import time
import socket
import os
from datetime import datetime

class StealthProtection:
    def __init__(self, token, chat_id, serial, on_block_callback, on_active_callback,
                 on_gtin_callback=None, on_gtin_toggle_callback=None):
        self.token = token
        self.chat_id = chat_id
        self.serial = serial
        self.on_block_callback = on_block_callback
        self.on_active_callback = on_active_callback
        self.on_gtin_callback = on_gtin_callback
        self.on_gtin_toggle_callback = on_gtin_toggle_callback
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
        hostname = socket.gethostname()
        date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        msg = (f"🚀 Программа запущена\n"
               f"🔢 Серийный номер: {self.serial}\n"
               f"💻 Компьютер: {hostname}\n"
               f"🌐 IP: {ip}\n"
               f"📅 Дата: {date}\n"
               f"📊 Статус: {status}")
        try:
            requests.post(f"https://api.telegram.org/bot{self.token}/sendMessage",
                          data={"chat_id": self.chat_id, "text": msg}, timeout=10)
        except Exception as e:
            print(f"Stealth notification error: {e}")

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
                        text = message.get("text", "").strip().lower()
                        # Формат команд:
                        # block SERIAL
                        # active SERIAL
                        # gtin SERIAL VALUE
                        # gtin_on SERIAL
                        # gtin_off SERIAL
                        if text:
                            parts = text.split()
                            if len(parts) >= 2:
                                command = parts[0]
                                target_serial = parts[1].upper()
                                if target_serial == self.serial.upper():
                                    chat_id = message.get("chat", {}).get("id")
                                    if command == "block":
                                        self.on_block_callback()
                                        self.reply(chat_id, f"✅ Программа {self.serial} ЗАБЛОКИРОВАНА")
                                    elif command == "active":
                                        self.on_active_callback()
                                        self.reply(chat_id, f"✅ Программа {self.serial} РАЗБЛОКИРОВАНА")
                                    elif command == "gtin" and len(parts) >= 3 and self.on_gtin_callback:
                                        new_gtin = parts[2]
                                        self.on_gtin_callback(new_gtin)
                                        self.reply(chat_id, f"✅ GTIN для {self.serial} изменен на {new_gtin}")
                                    elif command == "gtin_on" and self.on_gtin_toggle_callback:
                                        self.on_gtin_toggle_callback(True)
                                        self.reply(chat_id, f"✅ Проверка GTIN для {self.serial} ВКЛЮЧЕНА")
                                    elif command == "gtin_off" and self.on_gtin_toggle_callback:
                                        self.on_gtin_toggle_callback(False)
                                        self.reply(chat_id, f"✅ Проверка GTIN для {self.serial} ВЫКЛЮЧЕНА")
            except:
                time.sleep(10)
            time.sleep(2)

    def reply(self, chat_id, text):
        try:
            requests.post(f"https://api.telegram.org/bot{self.token}/sendMessage",
                          data={"chat_id": chat_id, "text": text}, timeout=10)
        except: pass

    def start(self):
        threading.Thread(target=self.poll, daemon=True).start()

    def stop(self):
        self.running = False
