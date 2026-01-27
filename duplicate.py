import sqlite3
import os

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
            # Таблица для КМ
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS seen_codes (
                    code TEXT PRIMARY KEY,
                    scan_time DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            # Таблица для SSCC
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS seen_sscc (
                    code TEXT PRIMARY KEY,
                    scan_time DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

    def check(self, clean_code: str):
        """Проверка КМ на дубликаты"""
        with sqlite3.connect(self.db_path, timeout=10) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT code FROM seen_codes WHERE code = ?", (clean_code,))
            if cursor.fetchone():
                raise ValueError("Код маркировки уже был отсканирован ранее")

            cursor.execute("INSERT INTO seen_codes (code) VALUES (?)", (clean_code,))
            conn.commit()

    def check_sscc(self, sscc: str):
        """Проверка SSCC на дубликаты"""
        with sqlite3.connect(self.db_path, timeout=10) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT code FROM seen_sscc WHERE code = ?", (sscc,))
            if cursor.fetchone():
                raise ValueError("Этот SSCC код уже использовался ранее")

            cursor.execute("INSERT INTO seen_sscc (code) VALUES (?)", (sscc,))
            conn.commit()
