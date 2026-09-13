import unittest
import os
import shutil
import tempfile
from unittest.mock import patch

from virtual_aggregation import (
    read_codes_from_file,
    read_all_codes,
    sanitize_filename,
    perform_aggregation
)


class TestVirtualAggregationLogic(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def create_temp_file(self, filename, content, encoding="utf-8"):
        filepath = os.path.join(self.test_dir, filename)
        with open(filepath, "w", encoding=encoding) as f:
            f.write(content)
        return filepath

    def test_sanitize_filename(self):
        raw = 'CODE/123\\456*789?012"345<678>901|abc'
        sanitized = sanitize_filename(raw)
        self.assertNotIn('/', sanitized)
        self.assertNotIn('\\', sanitized)
        self.assertNotIn('*', sanitized)
        self.assertNotIn('?', sanitized)
        self.assertNotIn('"', sanitized)
        self.assertNotIn('<', sanitized)
        self.assertNotIn('>', sanitized)
        self.assertNotIn('|', sanitized)
        self.assertEqual(sanitized, 'CODE_123_456_789_012_345_678_901_abc')

    def test_read_codes_from_file_encodings(self):
        # Test utf-8
        utf8_file = self.create_temp_file("utf8.txt", "CODE1\nCODE2\n\nCODE3\n", encoding="utf-8")
        codes = read_codes_from_file(utf8_file)
        self.assertEqual(codes, ["CODE1", "CODE2", "CODE3"])

        # Test cp1251
        cp1251_file = self.create_temp_file("cp1251.txt", "КОД1\nКОД2\n", encoding="cp1251")
        codes_cp = read_codes_from_file(cp1251_file)
        self.assertEqual(codes_cp, ["КОД1", "КОД2"])

    def test_read_codes_unsupported_encoding_raises(self):
        # Mock file open to raise UnicodeError
        fake_file = os.path.join(self.test_dir, "fake.txt")
        with open(fake_file, "w") as f:
            f.write("test")

        with patch("builtins.open", side_effect=UnicodeError("Decoding failed")):
            with self.assertRaises(ValueError):
                read_codes_from_file(fake_file)

    def test_perform_aggregation_success(self):
        parent_file = self.create_temp_file("parents.txt", "SET_01\nSET_02\n")
        child_file1 = self.create_temp_file("child1.txt", "ITEM_1\nITEM_2\nITEM_3\n")
        child_file2 = self.create_temp_file("child2.txt", "ITEM_4\nITEM_5\nITEM_6\n")

        # 2 sets, 3 items per set -> 6 children required, 6 available
        orig_cwd = os.getcwd()
        os.chdir(self.test_dir)
        try:
            res = perform_aggregation(parent_file, [child_file1, child_file2], 3)
            self.assertEqual(res["status"], "success")
            self.assertEqual(res["created_sets"], 2)
            self.assertEqual(res["used_children"], 6)

            folder = res["folder"]
            self.assertTrue(os.path.isdir(folder))

            files = sorted(os.listdir(folder))
            self.assertEqual(len(files), 2)
            self.assertIn("SET_01.txt", files)
            self.assertIn("SET_02.txt", files)

            # Check content of SET_01.txt
            with open(os.path.join(folder, "SET_01.txt"), "r", encoding="utf-8") as f:
                lines = [line.strip() for line in f.readlines() if line.strip()]
            self.assertEqual(lines, ["SET_01", "ITEM_1", "ITEM_2", "ITEM_3"])

            # Check content of SET_02.txt
            with open(os.path.join(folder, "SET_02.txt"), "r", encoding="utf-8") as f:
                lines = [line.strip() for line in f.readlines() if line.strip()]
            self.assertEqual(lines, ["SET_02", "ITEM_4", "ITEM_5", "ITEM_6"])
        finally:
            os.chdir(orig_cwd)

    def test_perform_aggregation_insufficient_children_confirmed(self):
        parent_file = self.create_temp_file("parents.txt", "SET_01\nSET_02\nSET_03\n")
        child_file = self.create_temp_file("child.txt", "ITEM_1\nITEM_2\nITEM_3\nITEM_4\n")

        # 3 sets, 2 items per set needed (6 items), but only 4 items available.
        # Max possible sets = 4 // 2 = 2 sets.
        orig_cwd = os.getcwd()
        os.chdir(self.test_dir)
        try:
            confirmed = False
            def confirm_cb(msg):
                nonlocal confirmed
                confirmed = True
                return True

            res = perform_aggregation(parent_file, [child_file], 2, confirm_callback=confirm_cb)
            self.assertTrue(confirmed)
            self.assertEqual(res["status"], "success")
            self.assertEqual(res["created_sets"], 2)
            self.assertEqual(res["used_children"], 4)
        finally:
            os.chdir(orig_cwd)

    def test_perform_aggregation_insufficient_children_cancelled(self):
        parent_file = self.create_temp_file("parents.txt", "SET_01\nSET_02\n")
        child_file = self.create_temp_file("child.txt", "ITEM_1\n")

        orig_cwd = os.getcwd()
        os.chdir(self.test_dir)
        try:
            res = perform_aggregation(parent_file, [child_file], 2, confirm_callback=lambda msg: False)
            self.assertEqual(res["status"], "cancelled")
        finally:
            os.chdir(orig_cwd)

    def test_perform_aggregation_invalid_inputs(self):
        # Items per parent <= 0
        with self.assertRaises(ValueError):
            perform_aggregation("fake.txt", ["fake_child.txt"], 0)

        # Parent file doesn't exist
        with self.assertRaises(ValueError):
            perform_aggregation("non_existent.txt", ["fake_child.txt"], 2)

        # Child files empty list
        parent_file = self.create_temp_file("parents.txt", "SET_01\n")
        with self.assertRaises(ValueError):
            perform_aggregation(parent_file, [], 2)


if __name__ == "__main__":
    unittest.main()
