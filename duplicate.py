import sqlite3
import os
import json

class DuplicateChecker:
    def __init__(self, db_path="data/duplicates.db"):
        self.db_path = db_path
        db_dir = os.path.dirname(self.db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path, timeout=10) as conn:
            cursor = conn.cursor()
            # Таблица КМ
            cursor.execute("CREATE TABLE IF NOT EXISTS seen_codes (code TEXT PRIMARY KEY, scan_time DATETIME DEFAULT CURRENT_TIMESTAMP)")
            # Таблица SSCC
            cursor.execute("CREATE TABLE IF NOT EXISTS seen_sscc (code TEXT PRIMARY KEY, scan_time DATETIME DEFAULT CURRENT_TIMESTAMP)")
            # Таблица для страховки (текущая смена)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS recovery_shift (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sscc TEXT,
                    units_json TEXT,
                    shift_info TEXT
                )
            """)
            conn.commit()

    def check(self, clean_code: str):
        with sqlite3.connect(self.db_path, timeout=10) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT code FROM seen_codes WHERE code = ?", (clean_code,))
            if cursor.fetchone():
                raise ValueError("Код маркировки уже был отсканирован ранее")
            cursor.execute("INSERT INTO seen_codes (code) VALUES (?)", (clean_code,))
            conn.commit()

    def check_sscc(self, sscc: str):
        with sqlite3.connect(self.db_path, timeout=10) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT code FROM seen_sscc WHERE code = ?", (sscc,))
            if cursor.fetchone():
                raise ValueError("Этот SSCC код уже использовался")
            cursor.execute("INSERT INTO seen_sscc (code) VALUES (?)", (sscc,))
            conn.commit()

    # Методы для страховки данных
    def save_box_to_recovery(self, sscc, units, shift_info):
        with sqlite3.connect(self.db_path, timeout=10) as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO recovery_shift (sscc, units_json, shift_info) VALUES (?, ?, ?)",
                           (sscc, json.dumps(units), json.dumps(shift_info)))
            conn.commit()

    def get_recovery_data(self):
        with sqlite3.connect(self.db_path, timeout=10) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT sscc, units_json, shift_info FROM recovery_shift")
            rows = cursor.fetchall()
            return rows

    def clear_recovery(self):
        with sqlite3.connect(self.db_path, timeout=10) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM recovery_shift")
            conn.commit()
