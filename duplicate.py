import sqlite3
import os

class DuplicateChecker:
    def __init__(self, db_path="data/duplicates.db"):
        self.db_path = db_path
        # Ensure directory exists
        db_dir = os.path.dirname(self.db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
        self._init_db()

    def _init_db(self):
        # Using timeout for basic multi-user support over network share
        with sqlite3.connect(self.db_path, timeout=10) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS seen_codes (
                    code TEXT PRIMARY KEY,
                    scan_time DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

    def check(self, clean_code: str):
        with sqlite3.connect(self.db_path, timeout=10) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT code FROM seen_codes WHERE code = ?", (clean_code,))
            if cursor.fetchone():
                raise ValueError("Код уже был отсканирован ранее")

            cursor.execute("INSERT INTO seen_codes (code) VALUES (?)", (clean_code,))
            conn.commit()
