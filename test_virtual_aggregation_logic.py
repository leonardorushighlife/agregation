import unittest
import os
import shutil
import tempfile
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
        dirty = 'code/with:invalid*chars?"<>|'
        clean = sanitize_filename(dirty)
        self.assertEqual(clean, 'code_with_invalid_chars_____')

    def test_read_codes_encodings(self):
        # UTF-8
        path_utf8 = os.path.join(self.test_dir, "utf8.txt")
        with open(path_utf8, "w", encoding="utf-8") as f:
            f.write("code1\ncode2\n  code3  \n\n")

        codes = read_codes(path_utf8)
        self.assertEqual(codes, ["code1", "code2", "code3"])

        # CP1251
        path_cp1251 = os.path.join(self.test_dir, "cp1251.txt")
        with open(path_cp1251, "w", encoding="cp1251") as f:
            f.write("код1\nкод2\n")

        codes_1251 = read_codes(path_cp1251)
        self.assertEqual(codes_1251, ["код1", "код2"])

    def test_read_codes_error(self):
        path_err = os.path.join(self.test_dir, "invalid.txt")
        with open(path_err, "wb") as f:
            f.write(b"\xff\xfe\xff\xff")

        # Mock open to raise UnicodeError
        with patch("builtins.open", side_effect=UnicodeError("Decode error")):
            with self.assertRaises(ValueError):
                read_codes(path_err)

    def test_perform_aggregation_success(self):
        parent_file = os.path.join(self.test_dir, "parents.txt")
        with open(parent_file, "w", encoding="utf-8") as f:
            f.write("SET_001\nSET_002\n")

        child_file_1 = os.path.join(self.test_dir, "children1.txt")
        with open(child_file_1, "w", encoding="utf-8") as f:
            f.write("ITEM_1\nITEM_2\n")

        child_file_2 = os.path.join(self.test_dir, "children2.txt")
        with open(child_file_2, "w", encoding="utf-8") as f:
            f.write("ITEM_3\nITEM_4\n")

        out_dir = os.path.join(self.test_dir, "output")

        res_dir, created_count = perform_aggregation(
            parent_file=parent_file,
            child_files=[child_file_1, child_file_2],
            items_per_parent=2,
            output_dir=out_dir
        )

        self.assertEqual(created_count, 2)
        self.assertTrue(os.path.exists(os.path.join(out_dir, "SET_001.txt")))
        self.assertTrue(os.path.exists(os.path.join(out_dir, "SET_002.txt")))

        with open(os.path.join(out_dir, "SET_001.txt"), "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip()]
            self.assertEqual(lines, ["SET_001", "ITEM_1", "ITEM_2"])

        with open(os.path.join(out_dir, "SET_002.txt"), "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip()]
            self.assertEqual(lines, ["SET_002", "ITEM_3", "ITEM_4"])

    def test_perform_aggregation_filename_collision(self):
        parent_file = os.path.join(self.test_dir, "parents.txt")
        # Same code or sanitized code causing collisions
        with open(parent_file, "w", encoding="utf-8") as f:
            f.write("SET/001\nSET:001\n")

        child_file = os.path.join(self.test_dir, "children.txt")
        with open(child_file, "w", encoding="utf-8") as f:
            f.write("I1\nI2\nI3\nI4\n")

        out_dir = os.path.join(self.test_dir, "output_collision")

        res_dir, created_count = perform_aggregation(
            parent_file=parent_file,
            child_files=[child_file],
            items_per_parent=2,
            output_dir=out_dir
        )

        self.assertEqual(created_count, 2)
        self.assertTrue(os.path.exists(os.path.join(out_dir, "SET_001.txt")))
        self.assertTrue(os.path.exists(os.path.join(out_dir, "SET_001_1.txt")))

    def test_perform_aggregation_insufficient_children_cancel(self):
        parent_file = os.path.join(self.test_dir, "parents.txt")
        with open(parent_file, "w", encoding="utf-8") as f:
            f.write("SET_001\nSET_002\n")

        child_file = os.path.join(self.test_dir, "children.txt")
        with open(child_file, "w", encoding="utf-8") as f:
            f.write("ITEM_1\nITEM_2\n")  # Only enough for 1 parent if 2 per parent

        out_dir = os.path.join(self.test_dir, "output_cancel")

        def confirm_no(msg):
            return False

        res_dir, created_count = perform_aggregation(
            parent_file=parent_file,
            child_files=[child_file],
            items_per_parent=2,
            output_dir=out_dir,
            confirm_callback=confirm_no
        )

        self.assertIsNone(res_dir)
        self.assertEqual(created_count, 0)


if __name__ == "__main__":
    unittest.main()
