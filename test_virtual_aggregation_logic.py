import os
import shutil
import tempfile
import unittest
from unittest.mock import patch

from virtual_aggregation import (
    sanitize_filename,
    read_codes,
    perform_aggregation,
    OperationCanceled
)


class TestVirtualAggregationLogic(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_sanitize_filename(self):
        self.assertEqual(sanitize_filename("010460123456789021<ABC>?"), "010460123456789021_ABC__")
        self.assertEqual(sanitize_filename("  test/code\\123  "), "test_code_123")
        self.assertEqual(sanitize_filename(""), "set_code")
        self.assertEqual(sanitize_filename(":::"), "___")

    def test_read_codes_encodings(self):
        # UTF-8 with BOM
        utf8_file = os.path.join(self.temp_dir, "utf8.txt")
        with open(utf8_file, "w", encoding="utf-8-sig") as f:
            f.write("CODE1\nCODE2\n")
        self.assertEqual(read_codes(utf8_file), ["CODE1", "CODE2"])

        # UTF-16
        utf16_file = os.path.join(self.temp_dir, "utf16.txt")
        with open(utf16_file, "w", encoding="utf-16") as f:
            f.write("CODE3\nCODE4\n")
        self.assertEqual(read_codes(utf16_file), ["CODE3", "CODE4"])

        # CP1251
        cp1251_file = os.path.join(self.temp_dir, "cp1251.txt")
        with open(cp1251_file, "w", encoding="cp1251") as f:
            f.write("КОД1\nКОД2\n")
        self.assertEqual(read_codes(cp1251_file), ["КОД1", "КОД2"])

    def test_read_codes_encoding_error(self):
        bad_file = os.path.join(self.temp_dir, "bad.txt")
        with open(bad_file, "wb") as f:
            f.write(b"\xff\xff\xff\xff")

        with patch("builtins.open", side_effect=UnicodeDecodeError("utf-8", b"", 0, 1, "bad")):
            with self.assertRaises(UnicodeError):
                read_codes(bad_file)

    def test_perform_aggregation_success(self):
        parent_file = os.path.join(self.temp_dir, "parents.txt")
        with open(parent_file, "w", encoding="utf-8") as f:
            f.write("SET_001\nSET_002\n")

        child1_file = os.path.join(self.temp_dir, "child1.txt")
        with open(child1_file, "w", encoding="utf-8") as f:
            f.write("ITEM_1\nITEM_2\nITEM_3\n")

        child2_file = os.path.join(self.temp_dir, "child2.txt")
        with open(child2_file, "w", encoding="utf-8") as f:
            f.write("ITEM_4\nITEM_5\nITEM_6\n")

        out_dir = os.path.join(self.temp_dir, "out_results")

        res = perform_aggregation(
            parent_file=parent_file,
            child_files=[child1_file, child2_file],
            count_per_parent=3,
            output_dir=out_dir
        )

        self.assertEqual(res['created_files'], 2)
        self.assertEqual(res['used_children'], 6)
        self.assertTrue(os.path.isdir(out_dir))

        # Check SET_001.txt content
        file1 = os.path.join(out_dir, "SET_001.txt")
        self.assertTrue(os.path.isfile(file1))
        with open(file1, "r", encoding="utf-8") as f:
            lines = [l.strip() for l in f.readlines()]
        self.assertEqual(lines, ["SET_001", "ITEM_1", "ITEM_2", "ITEM_3"])

        # Check SET_002.txt content
        file2 = os.path.join(out_dir, "SET_002.txt")
        self.assertTrue(os.path.isfile(file2))
        with open(file2, "r", encoding="utf-8") as f:
            lines = [l.strip() for l in f.readlines()]
        self.assertEqual(lines, ["SET_002", "ITEM_4", "ITEM_5", "ITEM_6"])

    def test_perform_aggregation_filename_collision(self):
        parent_file = os.path.join(self.temp_dir, "parents.txt")
        with open(parent_file, "w", encoding="utf-8") as f:
            f.write("SET/001\nSET?001\n")  # Both sanitize to SET_001

        child_file = os.path.join(self.temp_dir, "child.txt")
        with open(child_file, "w", encoding="utf-8") as f:
            f.write("ITEM_1\nITEM_2\n")

        out_dir = os.path.join(self.temp_dir, "out_collision")

        res = perform_aggregation(
            parent_file=parent_file,
            child_files=[child_file],
            count_per_parent=1,
            output_dir=out_dir
        )

        self.assertEqual(res['created_files'], 2)
        self.assertTrue(os.path.isfile(os.path.join(out_dir, "SET_001.txt")))
        self.assertTrue(os.path.isfile(os.path.join(out_dir, "SET_001_1.txt")))

    def test_perform_aggregation_insufficient_children_canceled(self):
        parent_file = os.path.join(self.temp_dir, "parents.txt")
        with open(parent_file, "w", encoding="utf-8") as f:
            f.write("SET_001\nSET_002\n")

        child_file = os.path.join(self.temp_dir, "child.txt")
        with open(child_file, "w", encoding="utf-8") as f:
            f.write("ITEM_1\n")

        out_dir = os.path.join(self.temp_dir, "out_cancel")

        def callback_cancel(msg):
            return False

        with self.assertRaises(OperationCanceled):
            perform_aggregation(
                parent_file=parent_file,
                child_files=[child_file],
                count_per_parent=2,
                output_dir=out_dir,
                confirm_callback=callback_cancel
            )

    def test_perform_aggregation_invalid_inputs(self):
        parent_file = os.path.join(self.temp_dir, "parents.txt")
        with open(parent_file, "w", encoding="utf-8") as f:
            f.write("SET_001\n")

        child_file = os.path.join(self.temp_dir, "child.txt")
        with open(child_file, "w", encoding="utf-8") as f:
            f.write("ITEM_1\n")

        with self.assertRaises(ValueError):
            perform_aggregation("non_existent.txt", [child_file], 1)

        with self.assertRaises(ValueError):
            perform_aggregation(parent_file, [], 1)

        with self.assertRaises(ValueError):
            perform_aggregation(parent_file, [child_file], 0)


if __name__ == "__main__":
    unittest.main()
