import sqlite3
import threading
import os
from datetime import datetime

DB_PATH = "data/warehouse.db"

class WarehouseManager:
    _local = threading.local()

    def __init__(self):
        self._init_db()

    def _get_conn(self):
        if not hasattr(self._local, "conn"):
            self._local.conn = sqlite3.connect(DB_PATH)
            self._local.conn.execute("PRAGMA journal_mode=WAL")
            self._local.conn.execute("PRAGMA synchronous=NORMAL")
        return self._local.conn

    def _init_db(self):
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS wh_units (
                code TEXT PRIMARY KEY,
                gtin TEXT,
                serial TEXT,
                box_sscc TEXT,
                status TEXT DEFAULT 'in_stock',
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS wh_boxes (
                sscc TEXT PRIMARY KEY,
                gtin TEXT,
                pallet_sscc TEXT,
                status TEXT DEFAULT 'in_stock',
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS wh_pallets (
                sscc TEXT PRIMARY KEY,
                gtin TEXT,
                status TEXT DEFAULT 'in_stock',
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS wh_orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_num TEXT,
                product_name TEXT,
                gtin TEXT,
                total_units INTEGER,
                shipped_units INTEGER DEFAULT 0,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS wh_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT,
                event_type TEXT,
                operator TEXT,
                workplace TEXT,
                order_num TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.commit()
        conn.close()

    def add_unit(self, code, gtin, serial, box_sscc=None, operator="", workplace=""):
        conn = self._get_conn()
        try:
            conn.execute("INSERT INTO wh_units (code, gtin, serial, box_sscc) VALUES (?, ?, ?, ?)",
                         (code, gtin, serial, box_sscc))
            conn.execute("INSERT INTO wh_history (code, event_type, operator, workplace) VALUES (?, 'received', ?, ?)",
                         (code, operator, workplace))
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def get_unit(self, code):
        conn = self._get_conn()
        return conn.execute("SELECT * FROM wh_units WHERE code = ?", (code,)).fetchone()

    def ship_unit(self, code, order_num, operator="", workplace=""):
        conn = self._get_conn()
        unit = self.get_unit(code)
        if not unit or unit[4] != 'in_stock':
            return False

        conn.execute("UPDATE wh_units SET status = 'shipped' WHERE code = ?", (code,))
        conn.execute("INSERT INTO wh_history (code, event_type, operator, workplace, order_num) VALUES (?, 'shipped', ?, ?, ?)",
                     (code, operator, workplace, order_num))
        conn.execute("UPDATE wh_orders SET shipped_units = shipped_units + 1 WHERE order_num = ?", (order_num,))
        conn.commit()
        return True

    def ship_box(self, sscc, order_num, operator="", workplace=""):
        conn = self._get_conn()
        # Проверяем, есть ли такой короб
        box = conn.execute("SELECT * FROM wh_boxes WHERE sscc = ?", (sscc,)).fetchone()
        if not box: return 0

        # Находим все юниты в этом коробе, которые еще на складе
        units = conn.execute("SELECT code FROM wh_units WHERE box_sscc = ? AND status = 'in_stock'", (sscc,)).fetchall()
        shipped_count = 0
        for (code,) in units:
            if self.ship_unit(code, order_num, operator, workplace):
                shipped_count += 1

        if shipped_count > 0:
            conn.execute("UPDATE wh_boxes SET status = 'shipped' WHERE sscc = ?", (sscc,))
            conn.commit()
        return shipped_count

    def return_unit(self, code, operator="", workplace=""):
        conn = self._get_conn()
        unit = self.get_unit(code)
        if not unit or unit[4] != 'shipped':
            return False

        conn.execute("UPDATE wh_units SET status = 'in_stock' WHERE code = ?", (code,))
        conn.execute("INSERT INTO wh_history (code, event_type, operator, workplace) VALUES (?, 'returned', ?, ?)",
                     (code, operator, workplace))
        conn.commit()
        return True

    def add_box(self, sscc, gtin, pallet_sscc=None, codes=None, operator="", workplace=""):
        conn = self._get_conn()
        try:
            # Если это SSCC паллеты (эвристика или передается тип, но тут упростим)
            # В данном приложении мы используем wh_boxes для обоих уровней или wh_pallets
            # Давайте использовать wh_pallets если это паллета
            is_pallet = False
            if codes and codes[0].startswith("00"):
                is_pallet = True

            if is_pallet:
                conn.execute("INSERT INTO wh_pallets (sscc, gtin) VALUES (?, ?)", (sscc, gtin))
                for code in codes:
                    conn.execute("UPDATE wh_boxes SET pallet_sscc = ? WHERE sscc = ?", (sscc, code))
            else:
                conn.execute("INSERT INTO wh_boxes (sscc, gtin, pallet_sscc) VALUES (?, ?, ?)",
                             (sscc, gtin, pallet_sscc))
                if codes:
                    for code in codes:
                        conn.execute("UPDATE wh_units SET box_sscc = ? WHERE code = ?", (sscc, code))

            conn.execute("INSERT INTO wh_history (code, event_type, operator, workplace) VALUES (?, 'aggregated', ?, ?)",
                         (sscc, operator, workplace))
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def get_order_by_gtin(self, gtin):
        conn = self._get_conn()
        return conn.execute("SELECT * FROM wh_orders WHERE gtin = ? AND status = 'pending' LIMIT 1", (gtin,)).fetchone()

    def get_all_orders(self):
        conn = self._get_conn()
        return conn.execute("SELECT * FROM wh_orders").fetchall()
