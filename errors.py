from datetime import datetime


class ErrorLog:
    def __init__(self):
        self.items = []

    def add(self, raw_code: str, error_text: str):
        self.items.append({
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "code": raw_code,
            "error": error_text
        })
