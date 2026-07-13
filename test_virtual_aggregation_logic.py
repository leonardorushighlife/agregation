import unittest
import os
import shutil
import tempfile
from virtual_aggregation import VirtualAggregationApp
from unittest.mock import MagicMock

class MockApp(VirtualAggregationApp):
    def __init__(self):
        self.parent_file = ""
        self.child_files = []
        import tkinter as tk
        from tkinter import messagebox
        self.root = MagicMock()

    def log(self, message):
        print(f"LOG: {message}")

class TestAggregationLogic(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        import virtual_aggregation
        virtual_aggregation.messagebox = MagicMock()
        self.app = MockApp()

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_sanitize_filename(self):
        self.assertEqual(self.app.sanitize_filename("valid_name"), "valid_name")
        self.assertEqual(self.app.sanitize_filename("name/with\\chars*"), "name_with_chars_")
        self.assertEqual(self.app.sanitize_filename("010460123456789021ABC123"), "010460123456789021ABC123")

    def test_read_codes(self):
        file_path = os.path.join(self.test_dir, "codes.txt")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("code1\n  code2  \n\ncode3\n")

        codes = self.app.read_codes(file_path)
        self.assertEqual(codes, ["code1", "code2", "code3"])

    def test_pairing_and_writing(self):
        output_dir = os.path.join(self.test_dir, "output")
        os.makedirs(output_dir)

        parents = ["P1", "P2/P2", "P1"] # One collision
        children = ["C1", "C2", "C3", "C4", "C5", "C6"]
        count = 2

        self.app.perform_pairing_and_writing(parents, children, count, output_dir)

        files = os.listdir(output_dir)
        self.assertIn("P1.txt", files)
        self.assertIn("P2_P2.txt", files)
        self.assertIn("P1_1.txt", files)

        with open(os.path.join(output_dir, "P1.txt"), "r") as f:
            lines = f.read().splitlines()
            self.assertEqual(lines, ["P1", "C1", "C2"])

        with open(os.path.join(output_dir, "P1_1.txt"), "r") as f:
            lines = f.read().splitlines()
            self.assertEqual(lines, ["P1", "C5", "C6"])

if __name__ == "__main__":
    unittest.main()
