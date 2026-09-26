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
        shutil.rmtree(self.test_dir)

    def test_sanitize_filename(self):
        self.assertEqual(sanitize_filename("valid_filename"), "valid_filename")
        self.assertEqual(sanitize_filename("010461234567890121abc/def\\ghi"), "010461234567890121abc_def_ghi")
        self.assertEqual(sanitize_filename('code:*?"<>|'), "code_______")

    def test_read_codes_encodings(self):
        codes = ["010460000000000121SET001", "010460000000000121SET002"]

        # Test UTF-8 with BOM
        path_utf8_sig = os.path.join(self.test_dir, "utf8_sig.txt")
        with open(path_utf8_sig, "w", encoding="utf-8-sig") as f:
            f.write("\n".join(codes) + "\n")
        self.assertEqual(read_codes(path_utf8_sig), codes)

        # Test UTF-16
        path_utf16 = os.path.join(self.test_dir, "utf16.txt")
        with open(path_utf16, "w", encoding="utf-16") as f:
            f.write("\n".join(codes) + "\n")
        self.assertEqual(read_codes(path_utf16), codes)

        # Test CP1251
        path_cp1251 = os.path.join(self.test_dir, "cp1251.txt")
        with open(path_cp1251, "w", encoding="cp1251") as f:
            f.write("\n".join(codes) + "\n")
        self.assertEqual(read_codes(path_cp1251), codes)

    def test_read_codes_invalid_encoding(self):
        path_err = os.path.join(self.test_dir, "invalid.txt")
        with open(path_err, "w", encoding="utf-8") as f:
            f.write("test")

        with patch("builtins.open", side_effect=UnicodeError("Decode error")):
            with self.assertRaises(ValueError):
                read_codes(path_err)

    def test_perform_aggregation_success(self):
        parent_file = os.path.join(self.test_dir, "parents.txt")
        parents = ["SET_01", "SET_02"]
        with open(parent_file, "w", encoding="utf-8") as f:
            f.write("\n".join(parents))

        child_file1 = os.path.join(self.test_dir, "children1.txt")
        children1 = ["CHILD_1", "CHILD_2"]
        with open(child_file1, "w", encoding="utf-8") as f:
            f.write("\n".join(children1))

        child_file2 = os.path.join(self.test_dir, "children2.txt")
        children2 = ["CHILD_3", "CHILD_4", "CHILD_5", "CHILD_6"]
        with open(child_file2, "w", encoding="utf-8") as f:
            f.write("\n".join(children2))

        # items_per_parent = 3, required = 2 * 3 = 6, total children = 6
        result = perform_aggregation(parent_file, [child_file1, child_file2], 3)
        self.assertIsNotNone(result)
        self.assertEqual(result["sets_count"], 2)

        out_dir = result["output_dir"]
        self.assertTrue(os.path.exists(out_dir))

        # Check SET_01.txt
        f1_path = os.path.join(out_dir, "SET_01.txt")
        self.assertTrue(os.path.exists(f1_path))
        with open(f1_path, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip()]
        self.assertEqual(lines, ["SET_01", "CHILD_1", "CHILD_2", "CHILD_3"])

        # Check SET_02.txt
        f2_path = os.path.join(out_dir, "SET_02.txt")
        self.assertTrue(os.path.exists(f2_path))
        with open(f2_path, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip()]
        self.assertEqual(lines, ["SET_02", "CHILD_4", "CHILD_5", "CHILD_6"])

        # Cleanup created output directory
        if os.path.exists(out_dir):
            shutil.rmtree(out_dir)

    def test_perform_aggregation_insufficient_children_canceled(self):
        parent_file = os.path.join(self.test_dir, "parents.txt")
        with open(parent_file, "w", encoding="utf-8") as f:
            f.write("SET_01\nSET_02")

        child_file = os.path.join(self.test_dir, "children.txt")
        with open(child_file, "w", encoding="utf-8") as f:
            f.write("CHILD_1\nCHILD_2\nCHILD_3")  # 3 children, needs 4 for 2 sets of 2

        # User cancels via callback
        confirm_cb = lambda msg: False
        result = perform_aggregation(parent_file, [child_file], 2, confirm_partial_callback=confirm_cb)
        self.assertIsNone(result)

    def test_perform_aggregation_insufficient_children_confirmed(self):
        parent_file = os.path.join(self.test_dir, "parents.txt")
        with open(parent_file, "w", encoding="utf-8") as f:
            f.write("SET_01\nSET_02")

        child_file = os.path.join(self.test_dir, "children.txt")
        with open(child_file, "w", encoding="utf-8") as f:
            f.write("CHILD_1\nCHILD_2\nCHILD_3")

        # User confirms via callback -> should form 1 set (3 // 2 = 1)
        confirm_cb = lambda msg: True
        result = perform_aggregation(parent_file, [child_file], 2, confirm_partial_callback=confirm_cb)
        self.assertIsNotNone(result)
        self.assertEqual(result["sets_count"], 1)

        out_dir = result["output_dir"]
        if os.path.exists(out_dir):
            shutil.rmtree(out_dir)

    def test_perform_aggregation_filename_collisions(self):
        parent_file = os.path.join(self.test_dir, "parents.txt")
        # Identical or sanitization-colliding parent codes
        with open(parent_file, "w", encoding="utf-8") as f:
            f.write("SET/01\nSET\\01")

        child_file = os.path.join(self.test_dir, "children.txt")
        with open(child_file, "w", encoding="utf-8") as f:
            f.write("C1\nC2")

        result = perform_aggregation(parent_file, [child_file], 1)
        self.assertIsNotNone(result)
        self.assertEqual(result["sets_count"], 2)

        out_dir = result["output_dir"]
        self.assertTrue(os.path.exists(os.path.join(out_dir, "SET_01.txt")))
        self.assertTrue(os.path.exists(os.path.join(out_dir, "SET_01_1.txt")))

        if os.path.exists(out_dir):
            shutil.rmtree(out_dir)


if __name__ == "__main__":
    unittest.main()
