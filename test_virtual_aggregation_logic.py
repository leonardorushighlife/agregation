import os
import shutil
import tempfile
import unittest
from unittest.mock import patch, mock_open

from virtual_aggregation import read_codes, sanitize_filename, perform_aggregation


class TestVirtualAggregationLogic(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_sanitize_filename(self):
        self.assertEqual(sanitize_filename("CODE/123*45?67"), "CODE_123_45_67")
        self.assertEqual(sanitize_filename("  "), "set_code")
        self.assertEqual(sanitize_filename("NORMAL_CODE_123"), "NORMAL_CODE_123")

    def test_read_codes_encodings(self):
        # UTF-8 with BOM
        p1 = os.path.join(self.test_dir, "utf8_bom.txt")
        with open(p1, "w", encoding="utf-8-sig") as f:
            f.write("CODE1\nCODE2\n")
        self.assertEqual(read_codes(p1), ["CODE1", "CODE2"])

        # UTF-16
        p2 = os.path.join(self.test_dir, "utf16.txt")
        with open(p2, "w", encoding="utf-16") as f:
            f.write("CODE3\nCODE4\n")
        self.assertEqual(read_codes(p2), ["CODE3", "CODE4"])

        # CP1251
        p3 = os.path.join(self.test_dir, "cp1251.txt")
        with open(p3, "w", encoding="cp1251") as f:
            f.write("КОД1\nКОД2\n")
        self.assertEqual(read_codes(p3), ["КОД1", "КОД2"])

    def test_read_codes_unicode_error_handling(self):
        with patch("builtins.open", side_effect=UnicodeError("Decode error")):
            with self.assertRaises(ValueError):
                read_codes("dummy.txt")

    def test_perform_aggregation_success(self):
        parent_file = os.path.join(self.test_dir, "parent.txt")
        with open(parent_file, "w", encoding="utf-8") as f:
            f.write("SET_001\nSET_002\n")

        child_file1 = os.path.join(self.test_dir, "child1.txt")
        with open(child_file1, "w", encoding="utf-8") as f:
            f.write("ITEM_001\nITEM_002\n")

        child_file2 = os.path.join(self.test_dir, "child2.txt")
        with open(child_file2, "w", encoding="utf-8") as f:
            f.write("ITEM_003\nITEM_004\n")

        success, msg, out_folder = perform_aggregation(
            parent_file=parent_file,
            child_files=[child_file1, child_file2],
            count_per_parent=2,
            output_base_dir=self.test_dir
        )

        self.assertTrue(success)
        self.assertTrue(os.path.exists(out_folder))

        files = sorted(os.listdir(out_folder))
        self.assertEqual(files, ["SET_001.txt", "SET_002.txt"])

        with open(os.path.join(out_folder, "SET_001.txt"), "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip()]
        self.assertEqual(lines, ["SET_001", "ITEM_001", "ITEM_002"])

        with open(os.path.join(out_folder, "SET_002.txt"), "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip()]
        self.assertEqual(lines, ["SET_002", "ITEM_003", "ITEM_004"])

    def test_perform_aggregation_partial_with_confirm(self):
        parent_file = os.path.join(self.test_dir, "parent.txt")
        with open(parent_file, "w", encoding="utf-8") as f:
            f.write("SET_001\nSET_002\nSET_003\n")

        child_file = os.path.join(self.test_dir, "child.txt")
        with open(child_file, "w", encoding="utf-8") as f:
            f.write("ITEM_001\nITEM_002\nITEM_003\n")  # total 3 items, count_per_parent=2 => max 1 set

        confirm_called = []

        def confirm_cb(msg):
            confirm_called.append(msg)
            return True

        success, msg, out_folder = perform_aggregation(
            parent_file=parent_file,
            child_files=[child_file],
            count_per_parent=2,
            confirm_callback=confirm_cb,
            output_base_dir=self.test_dir
        )

        self.assertTrue(success)
        self.assertEqual(len(confirm_called), 1)
        files = os.listdir(out_folder)
        self.assertEqual(len(files), 1)
        self.assertEqual(files[0], "SET_001.txt")

    def test_perform_aggregation_filename_collision(self):
        parent_file = os.path.join(self.test_dir, "parent.txt")
        with open(parent_file, "w", encoding="utf-8") as f:
            f.write("SET/001\nSET:001\n")  # Both sanitize to SET_001

        child_file = os.path.join(self.test_dir, "child.txt")
        with open(child_file, "w", encoding="utf-8") as f:
            f.write("ITEM_1\nITEM_2\n")

        success, msg, out_folder = perform_aggregation(
            parent_file=parent_file,
            child_files=[child_file],
            count_per_parent=1,
            output_base_dir=self.test_dir
        )

        self.assertTrue(success)
        files = sorted(os.listdir(out_folder))
        self.assertEqual(files, ["SET_001.txt", "SET_001_1.txt"])


if __name__ == "__main__":
    unittest.main()
