import sqlite3
import os
import json
import socket
import threading
import time

class DuplicateChecker:
    def __init__(self, db_path="data/duplicates.db", is_server=False, access_key="", server_ip=None):
        self.db_path = db_path
        self.is_server = is_server
        self.access_key = access_key
        self.server_ip = server_ip if server_ip and server_ip.strip() else None
        self.port = 5555
        self.udp_port = 5556
        self.running = True

        db_dir = os.path.dirname(self.db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
        self._init_db()

        if self.is_server:
            self.start_server_thread()
        elif not self.server_ip:
            self.start_discovery_thread()

    def _init_db(self):
        with sqlite3.connect(self.db_path, timeout=10) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS seen_codes (
                    code TEXT PRIMARY KEY,
                    scan_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                    operator TEXT,
                    workplace TEXT,
                    sscc TEXT
                )
            """)
            # Миграция для старых баз
            try:
                cursor.execute("ALTER TABLE seen_codes ADD COLUMN operator TEXT")
            except: pass
            try:
                cursor.execute("ALTER TABLE seen_codes ADD COLUMN workplace TEXT")
            except: pass
            try:
                cursor.execute("ALTER TABLE seen_codes ADD COLUMN sscc TEXT")
            except: pass

            cursor.execute("CREATE TABLE IF NOT EXISTS seen_sscc (code TEXT PRIMARY KEY, scan_time DATETIME DEFAULT CURRENT_TIMESTAMP)")
            cursor.execute("CREATE TABLE IF NOT EXISTS recovery_shift (id INTEGER PRIMARY KEY AUTOINCREMENT, sscc TEXT, units_json TEXT, shift_info TEXT)")
            conn.commit()

    # --- СЕТЕВАЯ ЛОГИКА ---

    def start_server_thread(self):
        """Запуск сервера для приема запросов от клиентов"""
        threading.Thread(target=self._run_tcp_server, daemon=True).start()
        threading.Thread(target=self._run_udp_broadcast_responder, daemon=True).start()

    def _run_tcp_server(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind(('0.0.0.0', self.port))
                s.listen()
                while self.running:
                    conn, addr = s.accept()
                    with conn:
                        try:
                            data = conn.recv(4096).decode('utf-8')
                            if not data: continue
                            req = json.loads(data)

                            # Проверка ключа доступа
                            if req.get('key') != self.access_key:
                                res = {"status": "error", "message": "Ошибка безопасности: Неверный ключ доступа к серверу"}
                            else:
                                res = self._handle_network_request(req)

                            conn.sendall(json.dumps(res).encode('utf-8'))
                        except Exception as e:
                            print(f"Server error handling client: {e}")
            except Exception as e:
                print(f"Could not start TCP server: {e}")

    def _run_udp_broadcast_responder(self):
        """Отвечает клиентам, где находится сервер"""
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind(('', self.udp_port))
                while self.running:
                    data, addr = s.recvfrom(1024)
                    if data == b"WHERE_IS_GS1_SERVER":
                        s.sendto(b"I_AM_GS1_SERVER", addr)
            except Exception as e:
                print(f"Could not start UDP responder: {e}")

    def start_discovery_thread(self):
        """Поиск сервера в сети"""
        threading.Thread(target=self._discover_server, daemon=True).start()

    def _discover_server(self):
        while self.running and not self.server_ip:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                s.settimeout(2)
                try:
                    s.sendto(b"WHERE_IS_GS1_SERVER", ('255.255.255.255', self.udp_port))
                    data, addr = s.recvfrom(1024)
                    if data == b"I_AM_GS1_SERVER":
                        self.server_ip = addr[0]
                        print(f"Found server at {self.server_ip}")
                except:
                    time.sleep(3)

    def _handle_network_request(self, req):
        try:
            if req['type'] == 'check_unit':
                self.check_local(req['code'], req.get('operator'), req.get('workplace'))
            elif req['type'] == 'check_sscc':
                self.check_sscc_local(req['code'])
            elif req['type'] == 'update_sscc':
                self.update_sscc_local(req['codes'], req['sscc'])
            return {"status": "ok"}
        except Exception as e:
            if isinstance(e, ValueError) and str(e).startswith("DUPLICATE|"):
                return {"status": "duplicate", "details": str(e)}
            return {"status": "error", "message": str(e)}

    def network_request(self, req):
        if not self.server_ip:
            return {"status": "local_only"}

        req['key'] = self.access_key

        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(3)
                s.connect((self.server_ip, self.port))
                s.sendall(json.dumps(req).encode('utf-8'))
                response = s.recv(4096).decode('utf-8')
                return json.loads(response)
        except Exception as e:
            print(f"Network request failed: {e}")
            return {"status": "local_only"}

    # --- ПРОВЕРКИ ---

    def check(self, code, operator=None, workplace=None):
        if self.is_server:
            self.check_local(code, operator, workplace)
        else:
            res = self.network_request({
                "type": "check_unit",
                "code": code,
                "operator": operator,
                "workplace": workplace
            })
            if res.get("status") == "duplicate":
                raise ValueError(res["details"])
            elif res.get("status") == "error":
                raise ValueError(res["message"])
            self.check_local(code, operator, workplace)

    def check_local(self, code, operator=None, workplace=None):
        with sqlite3.connect(self.db_path, timeout=10) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT operator, workplace, sscc FROM seen_codes WHERE code = ?", (code,))
            row = cursor.fetchone()
            if row:
                op, wp, sscc = row
                raise ValueError(f"DUPLICATE|{op or ''}|{wp or ''}|{sscc or ''}")

            cursor.execute("INSERT INTO seen_codes (code, operator, workplace) VALUES (?, ?, ?)",
                           (code, operator, workplace))
            conn.commit()

    def check_sscc(self, code):
        if self.is_server:
            self.check_sscc_local(code)
        else:
            res = self.network_request({"type": "check_sscc", "code": code})
            if res.get("status") == "error":
                raise ValueError(res["message"])
            self.check_sscc_local(code)

    def check_sscc_local(self, code):
        with sqlite3.connect(self.db_path, timeout=10) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT code FROM seen_sscc WHERE code = ?", (code,))
            if cursor.fetchone(): raise ValueError("Этот SSCC уже использовался")
            cursor.execute("INSERT INTO seen_sscc (code) VALUES (?)", (code,))
            conn.commit()

    def update_sscc_for_units(self, codes, sscc):
        """Связывает коды маркировки с SSCC кодом после закрытия коробки"""
        if self.is_server:
            self.update_sscc_local(codes, sscc)
        else:
            self.network_request({"type": "update_sscc", "codes": codes, "sscc": sscc})
            self.update_sscc_local(codes, sscc)

    def update_sscc_local(self, codes, sscc):
        with sqlite3.connect(self.db_path, timeout=10) as conn:
            cursor = conn.cursor()
            for code in codes:
                cursor.execute("UPDATE seen_codes SET sscc = ? WHERE code = ?", (sscc, code))
            conn.commit()

    # --- РЕЗЕРВИРОВАНИЕ ---
    def save_box_to_recovery(self, sscc, units, shift_info):
        with sqlite3.connect(self.db_path, timeout=10) as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO recovery_shift (sscc, units_json, shift_info) VALUES (?, ?, ?)", (sscc, json.dumps(units), json.dumps(shift_info)))
            conn.commit()

    def get_recovery_data(self):
        try:
            with sqlite3.connect(self.db_path, timeout=10) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT sscc, units_json, shift_info FROM recovery_shift")
                return cursor.fetchall()
        except: return []

    def clear_recovery(self):
        with sqlite3.connect(self.db_path, timeout=10) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM recovery_shift")
            conn.commit()
