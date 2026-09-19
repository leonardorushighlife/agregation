import os
import shutil
import tempfile
import unittest
from unittest.mock import patch

from virtual_aggregation import (
    read_codes,
    sanitize_filename,
    perform_aggregation
)


class TestVirtualAggregationLogic(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_sanitize_filename(self):
        self.assertEqual(sanitize_filename('010460123456789021SET123'), '010460123456789021SET123')
        self.assertEqual(sanitize_filename('SET/01:02*03?04"05<06>07|08\\09'), 'SET_01_02_03_04_05_06_07_08_09')
        self.assertEqual(sanitize_filename('   '), 'set_code')
        self.assertEqual(sanitize_filename('...'), 'set_code')

    def test_read_codes_encodings(self):
        # UTF-8
        path_utf8 = os.path.join(self.test_dir, "utf8.txt")
        with open(path_utf8, "w", encoding="utf-8") as f:
            f.write("CODE1\nCODE2\n  \nCODE3\n")

        codes = read_codes(path_utf8)
        self.assertEqual(codes, ["CODE1", "CODE2", "CODE3"])

        # CP1251
        path_cp1251 = os.path.join(self.test_dir, "cp1251.txt")
        with open(path_cp1251, "w", encoding="cp1251") as f:
            f.write("КОД1\nКОД2\n")

        codes = read_codes(path_cp1251)
        self.assertEqual(codes, ["КОД1", "КОД2"])

        # UTF-16
        path_utf16 = os.path.join(self.test_dir, "utf16.txt")
        with open(path_utf16, "w", encoding="utf-16") as f:
            f.write("CODE16_1\nCODE16_2\n")

        codes = read_codes(path_utf16)
        self.assertEqual(codes, ["CODE16_1", "CODE16_2"])

    def test_read_codes_unicode_error(self):
        invalid_file = os.path.join(self.test_dir, "invalid.txt")
        with open(invalid_file, "wb") as f:
            f.write(b"\x80\x81\x82\xff\xfe\xfd")

        with patch("builtins.open", side_effect=UnicodeError("Decode error")):
            with self.assertRaises(ValueError):
                read_codes(invalid_file)

    def test_perform_aggregation_success(self):
        parent_file = os.path.join(self.test_dir, "parent.txt")
        with open(parent_file, "w", encoding="utf-8") as f:
            f.write("PARENT_001\nPARENT_002\n")

        child1 = os.path.join(self.test_dir, "child1.txt")
        with open(child1, "w", encoding="utf-8") as f:
            f.write("C01\nC02\nC03\n")

        child2 = os.path.join(self.test_dir, "child2.txt")
        with open(child2, "w", encoding="utf-8") as f:
            f.write("C04\nC05\nC06\n")

        out_dir = os.path.join(self.test_dir, "output")

        res = perform_aggregation(
            parent_file=parent_file,
            child_files=[child1, child2],
            items_per_parent=3,
            output_dir=out_dir
        )

        self.assertEqual(res["status"], "success")
        self.assertEqual(res["created_sets"], 2)
        self.assertEqual(res["used_children"], 6)

        # Check content of generated files
        file1 = os.path.join(out_dir, "PARENT_001.txt")
        self.assertTrue(os.path.exists(file1))
        with open(file1, "r", encoding="utf-8") as f:
            lines = [l.strip() for l in f.readlines() if l.strip()]
        self.assertEqual(lines, ["PARENT_001", "C01", "C02", "C03"])

        file2 = os.path.join(out_dir, "PARENT_002.txt")
        self.assertTrue(os.path.exists(file2))
        with open(file2, "r", encoding="utf-8") as f:
            lines = [l.strip() for l in f.readlines() if l.strip()]
        self.assertEqual(lines, ["PARENT_002", "C04", "C05", "C06"])

    def test_perform_aggregation_filename_collisions(self):
        parent_file = os.path.join(self.test_dir, "parent.txt")
        # Same code or codes that map to same sanitized filename
        with open(parent_file, "w", encoding="utf-8") as f:
            f.write("SET/01\nSET:01\n")

        child_file = os.path.join(self.test_dir, "child.txt")
        with open(child_file, "w", encoding="utf-8") as f:
            f.write("C1\nC2\nC3\nC4\n")

        out_dir = os.path.join(self.test_dir, "output_collisions")

        res = perform_aggregation(
            parent_file=parent_file,
            child_files=[child_file],
            items_per_parent=2,
            output_dir=out_dir
        )

        self.assertEqual(res["created_sets"], 2)
        f1 = os.path.join(out_dir, "SET_01.txt")
        f2 = os.path.join(out_dir, "SET_01_1.txt")
        self.assertTrue(os.path.exists(f1))
        self.assertTrue(os.path.exists(f2))

    def test_perform_aggregation_insufficient_children_approved(self):
        parent_file = os.path.join(self.test_dir, "parent.txt")
        with open(parent_file, "w", encoding="utf-8") as f:
            f.write("PARENT_1\nPARENT_2\nPARENT_3\n")

        child_file = os.path.join(self.test_dir, "child.txt")
        with open(child_file, "w", encoding="utf-8") as f:
            f.write("C1\nC2\nC3\nC4\n")

        out_dir = os.path.join(self.test_dir, "output_partial")

        # 4 children with items_per_parent=2 -> can make 2 sets. Required=3.
        confirm_called = []

        def mock_confirm(actual, required):
            confirm_called.append((actual, required))
            return True

        res = perform_aggregation(
            parent_file=parent_file,
            child_files=[child_file],
            items_per_parent=2,
            output_dir=out_dir,
            confirm_callback=mock_confirm
        )

        self.assertEqual(confirm_called, [(2, 3)])
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["created_sets"], 2)

    def test_perform_aggregation_insufficient_children_cancelled(self):
        parent_file = os.path.join(self.test_dir, "parent.txt")
        with open(parent_file, "w", encoding="utf-8") as f:
            f.write("PARENT_1\nPARENT_2\nPARENT_3\n")

        child_file = os.path.join(self.test_dir, "child.txt")
        with open(child_file, "w", encoding="utf-8") as f:
            f.write("C1\nC2\n")

        out_dir = os.path.join(self.test_dir, "output_cancelled")

        def mock_confirm(actual, required):
            return False

        res = perform_aggregation(
            parent_file=parent_file,
            child_files=[child_file],
            items_per_parent=2,
            output_dir=out_dir,
            confirm_callback=mock_confirm
        )

        self.assertEqual(res["status"], "cancelled")

    def test_perform_aggregation_validation_errors(self):
        # Invalid items_per_parent
        with self.assertRaises(ValueError):
            perform_aggregation("nonexistent.txt", ["child.txt"], 0)

        # Missing parent file
        with self.assertRaises(ValueError):
            perform_aggregation("nonexistent.txt", ["child.txt"], 2)


if __name__ == "__main__":
    unittest.main()
