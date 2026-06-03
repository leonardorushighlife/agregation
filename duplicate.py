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

        # Для сервера: список подключенных клиентов {ip: last_seen_timestamp}
        self.active_clients = {}
        self._clients_lock = threading.Lock()

        # Для клиента: статус подключения и постоянное соединение
        self.is_connected = False
        self._socket_lock = threading.Lock()
        self._persistent_socket = None

        # Кеширование соединений (thread-local)
        self._local = threading.local()

        db_dir = os.path.dirname(self.db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
        self._init_db()

        if self.is_server:
            self.start_server_thread()
        else:
            self.start_discovery_thread()
            # Поток для поддержания статуса подключения (heartbeat)
            threading.Thread(target=self._connection_monitor, daemon=True).start()

    def _get_conn(self):
        if not hasattr(self._local, "conn"):
            self._local.conn = sqlite3.connect(self.db_path, timeout=60)
            self._local.conn.execute("PRAGMA journal_mode=WAL")
            self._local.conn.execute("PRAGMA synchronous=NORMAL")
            self._local.conn.execute("PRAGMA cache_size=-128000") # 128MB cache
            self._local.conn.execute("PRAGMA mmap_size=268435456") # 256MB
        return self._local.conn

    def _init_db(self):
        conn = self._get_conn()
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
        # Индексы для скорости
        try:
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_seen_codes_sscc ON seen_codes(sscc)")
        except: pass
        conn.commit()

    # --- СЕТЕВАЯ ЛОГИКА (СЕРВЕР) ---

    def start_server_thread(self):
        threading.Thread(target=self._run_tcp_server, daemon=True).start()
        threading.Thread(target=self._run_udp_broadcast_responder, daemon=True).start()

    def _run_tcp_server(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind(('0.0.0.0', self.port))
                s.listen(20) # Увеличиваем очередь прослушивания
                while self.running:
                    conn, addr = s.accept()
                    # Обновляем список активных клиентов
                    with self._clients_lock:
                        self.active_clients[addr[0]] = time.time()

                    # Обработка в отдельном потоке для предотвращения задержек
                    threading.Thread(target=self._handle_client_connection, args=(conn, addr), daemon=True).start()
            except Exception as e:
                print(f"Could not start TCP server: {e}")

    def _handle_client_connection(self, conn, addr):
        with conn:
            conn.settimeout(10)
            buffer = b""
            try:
                while self.running:
                    chunk = conn.recv(8192)
                    if not chunk: break
                    buffer += chunk

                    while b"\n" in buffer:
                        line, buffer = buffer.split(b"\n", 1)
                        if not line: continue

                        try:
                            req = json.loads(line.decode('utf-8'))
                            if req.get('key') != self.access_key:
                                res = {"status": "error", "message": "Ошибка безопасности: Неверный ключ"}
                            else:
                                res = self._handle_network_request(req)

                            conn.sendall((json.dumps(res) + "\n").encode('utf-8'))
                        except: continue
            except Exception as e:
                pass # Соединение закрыто

    def _run_udp_broadcast_responder(self):
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

    def get_active_clients(self):
        """Возвращает список IP клиентов, активных за последние 30 секунд"""
        now = time.time()
        with self._clients_lock:
            # Очистка старых
            self.active_clients = {ip: t for ip, t in self.active_clients.items() if now - t < 30}
            return list(self.active_clients.keys())

    # --- СЕТЕВАЯ ЛОГИКА (КЛИЕНТ) ---

    def start_discovery_thread(self):
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

    def _connection_monitor(self):
        """Периодически проверяет связь с сервером (Heartbeat)"""
        while self.running:
            if self.server_ip:
                res = self.network_request({"type": "ping"})
                self.is_connected = (res.get("status") == "ok")
            else:
                self.is_connected = False
            time.sleep(5)

    def network_request(self, req):
        if not self.server_ip:
            return {"status": "local_only"}

        req['key'] = self.access_key
        data = (json.dumps(req) + "\n").encode('utf-8')

        with self._socket_lock:
            try:
                if self._persistent_socket is None:
                    self._persistent_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    self._persistent_socket.settimeout(2.0)
                    self._persistent_socket.connect((self.server_ip, self.port))

                self._persistent_socket.sendall(data)

                # Читаем ответ (одна строка JSON)
                resp_data = b""
                while not resp_data.endswith(b"\n"):
                    chunk = self._persistent_socket.recv(4096)
                    if not chunk:
                        raise ConnectionError("Server closed connection")
                    resp_data += chunk

                return json.loads(resp_data.decode('utf-8'))
            except Exception as e:
                if self._persistent_socket:
                    try: self._persistent_socket.close()
                    except: pass
                    self._persistent_socket = None
                return {"status": "error", "message": f"Нет связи с сервером ({e})"}

    # --- ПРОВЕРКИ ---

    def _handle_network_request(self, req):
        try:
            if req['type'] == 'ping':
                return {"status": "ok"}
            elif req['type'] == 'check_unit':
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
                # Если сервер недоступен, продолжаем работу локально (или выбрасываем ошибку по желанию)
                # Пользователь жаловался на задержку, поэтому важно не зависать.
                print(f"Server check skipped/failed: {res.get('message')}")

            # В любом случае пишем в локальную БД для страховки
            self.check_local(code, operator, workplace)

    def check_local(self, code, operator=None, workplace=None):
        conn = self._get_conn()
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
                print(f"Server SSCC check failed: {res.get('message')}")
            self.check_sscc_local(code)

    def check_sscc_local(self, code):
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT code FROM seen_sscc WHERE code = ?", (code,))
        if cursor.fetchone(): raise ValueError("Этот SSCC уже использовался")
        cursor.execute("INSERT INTO seen_sscc (code) VALUES (?)", (code,))
        conn.commit()

    def update_sscc_for_units(self, codes, sscc):
        if self.is_server:
            self.update_sscc_local(codes, sscc)
        else:
            # Делаем это в фоне чтобы не тормозить UI
            threading.Thread(target=self.network_request, args=({"type": "update_sscc", "codes": codes, "sscc": sscc},), daemon=True).start()
            self.update_sscc_local(codes, sscc)

    def update_sscc_local(self, codes, sscc):
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("BEGIN TRANSACTION")
        try:
            cursor.executemany("UPDATE seen_codes SET sscc = ? WHERE code = ?", [(sscc, c) for c in codes])
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e

    # --- РЕЗЕРВИРОВАНИЕ ---
    def save_box_to_recovery(self, sscc, units, shift_info):
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO recovery_shift (sscc, units_json, shift_info) VALUES (?, ?, ?)", (sscc, json.dumps(units), json.dumps(shift_info)))
        conn.commit()

    def get_recovery_data(self):
        try:
            conn = self._get_conn()
            cursor = conn.cursor()
            cursor.execute("SELECT sscc, units_json, shift_info FROM recovery_shift")
            return cursor.fetchall()
        except: return []

    def clear_recovery(self):
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM recovery_shift")
        conn.commit()

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"
