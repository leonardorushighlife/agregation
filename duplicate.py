class DuplicateChecker:
    def __init__(self):
        self.seen = set()

    def check(self, clean_code: str):
        if clean_code in self.seen:
            raise ValueError("Дубликат кода маркировки")
        self.seen.add(clean_code)
