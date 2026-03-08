import requests
import threading
import time
import re
import sqlite3

class StealthProtection:
    def __init__(self, serial, config_callback, db_path="data/warehouse.db"):
        self.serial = serial
        self.config_callback = config_callback
        self.db_path = db_path
        self.bot_token = ""
        self.chat_id = ""
        self.blocked = False
        self.last_update_id = 0
        self.stop_event = threading.Event()
        self.thread = None

    def update_credentials(self, token, chat_id):
        self.bot_token = token
        self.chat_id = chat_id
        if not self.thread or not self.thread.is_alive():
            self.stop_event.clear()
            self.thread = threading.Thread(target=self._polling, daemon=True)
            self.thread.start()

    def send_message(self, text):
        if not self.bot_token or not self.chat_id: return
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {"chat_id": self.chat_id, "text": text}
        try:
            requests.post(url, json=payload, timeout=5)
        except:
            pass

    def _polling(self):
        while not self.stop_event.is_set():
            if not self.bot_token:
                time.sleep(5)
                continue
            url = f"https://api.telegram.org/bot{self.bot_token}/getUpdates?offset={self.last_update_id + 1}&timeout=30"
            try:
                response = requests.get(url, timeout=35)
                if response.status_code == 200:
                    data = response.json()
                    if data.get("ok"):
                        for update in data["result"]:
                            self.last_update_id = update["update_id"]
                            if "message" in update and "text" in update["message"]:
                                self._handle_command(update["message"]["text"])
            except:
                pass
            time.sleep(2)

    def _handle_command(self, text):
        text = text.strip()
        if f"block {self.serial}" in text:
            self.config_callback({"blocked": True})
        elif f"active {self.serial}" in text:
            self.config_callback({"blocked": False})
        elif "order " in text and self.serial in text:
            try:
                # order SERIAL заказ NUM продукт NAME кол-во UNITS GTIN VALUE
                order_num = re.search(r"заказ\s+(\S+)", text).group(1)
                product_name = re.search(r"продукт\s+(\S+)", text).group(1)
                units = int(re.search(r"кол-во\s+(\d+)", text).group(1))
                gtin = re.search(r"GTIN\s+(\d+)", text).group(1)

                conn = sqlite3.connect(self.db_path)
                conn.execute("INSERT INTO wh_orders (order_num, product_name, gtin, total_units) VALUES (?, ?, ?, ?)",
                             (order_num, product_name, gtin, units))
                conn.commit()
                conn.close()
                self.send_message(f"✅ Заказ {order_num} принят устройством {self.serial}")
            except Exception as e:
                self.send_message(f"❌ Ошибка в команде заказа: {e}")

    def stop(self):
        self.stop_event.set()
