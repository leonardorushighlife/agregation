import uuid
import socket
import hashlib
import requests
import os
import threading
import time

def get_hwid():
    """Генерирует уникальный ID оборудования"""
    try:
        # Используем MAC-адрес и имя хоста для создания фингерпринта
        node = uuid.getnode()
        hostname = socket.gethostname()
        combined = f"{node}:{hostname}"
        return hashlib.sha256(combined.encode()).hexdigest()[:16].upper()
    except:
        return "UNKNOWN_ID"

def check_license(server_url):
    """Проверяет лицензию на удаленном сервере администратора"""
    hwid = get_hwid()
    local_ip = get_my_ip()

    if not server_url:
        return True, "Сервер лицензий не настроен"

    try:
        payload = {
            "hwid": hwid,
            "ip": local_ip,
            "hostname": socket.gethostname()
        }
        resp = requests.post(f"{server_url}/check", json=payload, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            status = data.get("status") == "allowed"
            msg = data.get("message", "OK")
            return status, msg
        return True, "Сервер недоступен, работа в оффлайн режиме"
    except Exception as e:
        # Если интернета вообще нет, возвращаем True для оффлайн работы,
        # но gui.py может проверить наличие интернета отдельно если нужно
        return True, f"Оффлайн режим: {e}"

def get_my_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"

def start_license_heartbeat(server_url, on_blocked_callback=None):
    def heartbeat():
        hwid = get_hwid()
        while True:
            try:
                payload = {
                    "hwid": hwid,
                    "ip": get_my_ip(),
                    "hostname": socket.gethostname()
                }
                resp = requests.post(f"{server_url}/check", json=payload, timeout=5)
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("status") == "blocked":
                        if on_blocked_callback:
                            on_blocked_callback(data.get("message", "Blocked by administrator"))
            except:
                pass
            time.sleep(60) # Раз в минуту

    thread = threading.Thread(target=heartbeat, daemon=True)
    thread.start()
    return thread
