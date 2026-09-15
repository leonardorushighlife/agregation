import os
import shutil
import tempfile
import unittest
from unittest.mock import patch

from virtual_aggregation import (
    sanitize_filename,
    read_codes,
    perform_aggregation
)

_real_open = open


class TestVirtualAggregationLogic(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_sanitize_filename(self):
        self.assertEqual(sanitize_filename("CODE/123*456?"), "CODE_123_456_")
        self.assertEqual(sanitize_filename("  NORMAL_CODE  "), "NORMAL_CODE")
        self.assertEqual(sanitize_filename(""), "set_output")
        long_name = "A" * 150
        self.assertEqual(len(sanitize_filename(long_name)), 100)

    def test_read_codes_utf8(self):
        file_path = os.path.join(self.test_dir, "parent.txt")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("PARENT001\n\nPARENT002\n  PARENT003  \n")

        codes = read_codes(file_path)
        self.assertEqual(codes, ["PARENT001", "PARENT002", "PARENT003"])

    def test_read_codes_cp1251(self):
        file_path = os.path.join(self.test_dir, "parent_cp1251.txt")
        with open(file_path, "w", encoding="cp1251") as f:
            f.write("КОД001\nКОД002\n")

        codes = read_codes(file_path)
        self.assertEqual(codes, ["КОД001", "КОД002"])

    def test_read_codes_unicode_error_fallback(self):
        file_path = os.path.join(self.test_dir, "error_test.txt")
        with _real_open(file_path, "w", encoding="utf-8") as f:
            f.write("TEST_LINE\n")

        def side_effect(path, mode='r', **kwargs):
            encoding = kwargs.get('encoding')
            if encoding in ['utf-8', 'utf-8-sig']:
                raise UnicodeDecodeError("utf-8", b"", 0, 1, "bad byte")
            return _real_open(path, mode, **kwargs)

        with patch("builtins.open", side_effect=side_effect):
            codes = read_codes(file_path)
            self.assertEqual(codes, ["TEST_LINE"])

    def test_perform_aggregation_success(self):
        parent_file = os.path.join(self.test_dir, "parents.txt")
        child_file1 = os.path.join(self.test_dir, "children1.txt")
        child_file2 = os.path.join(self.test_dir, "children2.txt")

        with open(parent_file, "w", encoding="utf-8") as f:
            f.write("SET_001\nSET_002\n")

        with open(child_file1, "w", encoding="utf-8") as f:
            f.write("CHILD_A1\nCHILD_A2\nCHILD_A3\n")

        with open(child_file2, "w", encoding="utf-8") as f:
            f.write("CHILD_B1\nCHILD_B2\nCHILD_B3\n")

        out_dir = os.path.join(self.test_dir, "results")
        out_path, created, used_children = perform_aggregation(
            parent_file=parent_file,
            child_files=[child_file1, child_file2],
            items_per_set=3,
            output_dir=out_dir
        )

        self.assertEqual(created, 2)
        self.assertEqual(used_children, 6)

        file1 = os.path.join(out_dir, "SET_001.txt")
        file2 = os.path.join(out_dir, "SET_002.txt")

        self.assertTrue(os.path.exists(file1))
        self.assertTrue(os.path.exists(file2))

        with open(file1, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f.readlines()]
        self.assertEqual(lines, ["SET_001", "CHILD_A1", "CHILD_A2", "CHILD_A3"])

        with open(file2, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f.readlines()]
        self.assertEqual(lines, ["SET_002", "CHILD_B1", "CHILD_B2", "CHILD_B3"])

    def test_perform_aggregation_partial(self):
        parent_file = os.path.join(self.test_dir, "parents.txt")
        child_file = os.path.join(self.test_dir, "children.txt")

        with open(parent_file, "w", encoding="utf-8") as f:
            f.write("SET_001\nSET_002\nSET_003\n")

        with open(child_file, "w", encoding="utf-8") as f:
            f.write("C1\nC2\nC3\nC4\n")

        out_dir = os.path.join(self.test_dir, "results_partial")
        out_path, created, used_children = perform_aggregation(
            parent_file=parent_file,
            child_files=[child_file],
            items_per_set=3,
            output_dir=out_dir
        )

        self.assertEqual(created, 1)
        self.assertEqual(used_children, 3)
        self.assertTrue(os.path.exists(os.path.join(out_dir, "SET_001.txt")))
        self.assertFalse(os.path.exists(os.path.join(out_dir, "SET_002.txt")))

    def test_perform_aggregation_filename_collision(self):
        parent_file = os.path.join(self.test_dir, "parents.txt")
        child_file = os.path.join(self.test_dir, "children.txt")

        with open(parent_file, "w", encoding="utf-8") as f:
            f.write("SET/001\nSET*001\n")

        with open(child_file, "w", encoding="utf-8") as f:
            f.write("C1\nC2\nC3\nC4\n")

        out_dir = os.path.join(self.test_dir, "results_collision")
        out_path, created, used_children = perform_aggregation(
            parent_file=parent_file,
            child_files=[child_file],
            items_per_set=2,
            output_dir=out_dir
        )

        self.assertEqual(created, 2)
        self.assertTrue(os.path.exists(os.path.join(out_dir, "SET_001.txt")))
        self.assertTrue(os.path.exists(os.path.join(out_dir, "SET_001_1.txt")))

    def test_perform_aggregation_invalid_inputs(self):
        with self.assertRaises(FileNotFoundError):
            perform_aggregation("non_existent.txt", ["some_child.txt"], 3)

        parent_file = os.path.join(self.test_dir, "empty_parent.txt")
        open(parent_file, "w").close()

        with self.assertRaises(ValueError):
            perform_aggregation(parent_file, [], 3)

        child_file = os.path.join(self.test_dir, "child.txt")
        with open(child_file, "w") as f:
            f.write("C1\n")

        with self.assertRaises(ValueError):
            perform_aggregation(parent_file, [child_file], 0)

        with self.assertRaises(ValueError):
            perform_aggregation(parent_file, [child_file], 3)


if __name__ == "__main__":
    unittest.main()
