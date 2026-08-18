import unittest
import os
import shutil
import tempfile
from unittest.mock import patch
from virtual_aggregation import read_codes, sanitize_filename, perform_aggregation


class TestVirtualAggregationLogic(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_sanitize_filename(self):
        self.assertEqual(sanitize_filename('010460000000000021SET/123*456?'), '010460000000000021SET_123_456_')
        self.assertEqual(sanitize_filename('SET_CODE_123'), 'SET_CODE_123')

    def test_read_codes_utf8_and_cp1251(self):
        # Test UTF-8
        utf8_path = os.path.join(self.test_dir, "utf8.txt")
        with open(utf8_path, "w", encoding="utf-8") as f:
            f.write("CODE1\nCODE2\n\n  CODE3  \n")

        codes = read_codes(utf8_path)
        self.assertEqual(codes, ["CODE1", "CODE2", "CODE3"])

        # Test CP1251
        cp1251_path = os.path.join(self.test_dir, "cp1251.txt")
        with open(cp1251_path, "w", encoding="cp1251") as f:
            f.write("КОД1\nКОД2\n")

        codes_cp = read_codes(cp1251_path)
        self.assertEqual(codes_cp, ["КОД1", "КОД2"])

    def test_perform_aggregation_success(self):
        # Create 1 parent file with 2 parent codes
        parent_path = os.path.join(self.test_dir, "parents.txt")
        with open(parent_path, "w", encoding="utf-8") as f:
            f.write("PARENT_01\nPARENT_02\n")

        # Create 3 child files (simulating the user selecting 3 files for child items)
        c1_path = os.path.join(self.test_dir, "child1.txt")
        c2_path = os.path.join(self.test_dir, "child2.txt")
        c3_path = os.path.join(self.test_dir, "child3.txt")

        with open(c1_path, "w", encoding="utf-8") as f:
            f.write("CHILD_01\nCHILD_02\n")
        with open(c2_path, "w", encoding="utf-8") as f:
            f.write("CHILD_03\nCHILD_04\n")
        with open(c3_path, "w", encoding="utf-8") as f:
            f.write("CHILD_05\nCHILD_06\n")

        # Total children = 6. Count per parent = 3. Total parents = 2.
        output_dir = os.path.join(self.test_dir, "results")
        res = perform_aggregation(
            parent_file=parent_path,
            child_files=[c1_path, c2_path, c3_path],
            count_per_parent=3,
            output_dir=output_dir
        )

        self.assertIsNotNone(res)
        self.assertEqual(res['created_files_count'], 2)
        self.assertEqual(res['used_children'], 6)

        # Verify output files content
        file1 = os.path.join(output_dir, "PARENT_01.txt")
        file2 = os.path.join(output_dir, "PARENT_02.txt")

        self.assertTrue(os.path.exists(file1))
        self.assertTrue(os.path.exists(file2))

        with open(file1, "r", encoding="utf-8") as f:
            lines = [l.strip() for l in f.readlines()]
        self.assertEqual(lines, ["PARENT_01", "CHILD_01", "CHILD_02", "CHILD_03"])

        with open(file2, "r", encoding="utf-8") as f:
            lines = [l.strip() for l in f.readlines()]
        self.assertEqual(lines, ["PARENT_02", "CHILD_04", "CHILD_05", "CHILD_06"])

    def test_perform_aggregation_partial_with_confirm(self):
        parent_path = os.path.join(self.test_dir, "parents.txt")
        with open(parent_path, "w", encoding="utf-8") as f:
            f.write("PARENT_01\nPARENT_02\n")

        child_path = os.path.join(self.test_dir, "children.txt")
        with open(child_path, "w", encoding="utf-8") as f:
            f.write("CHILD_01\nCHILD_02\n")  # Only 2 children, needed 4 for 2 sets of 2

        output_dir = os.path.join(self.test_dir, "results_partial")

        # If user denies confirmation
        res_denied = perform_aggregation(
            parent_file=parent_path,
            child_files=[child_path],
            count_per_parent=2,
            output_dir=output_dir,
            confirm_callback=lambda msg: False
        )
        self.assertIsNone(res_denied)

        # If user accepts confirmation
        res_accepted = perform_aggregation(
            parent_file=parent_path,
            child_files=[child_path],
            count_per_parent=2,
            output_dir=output_dir,
            confirm_callback=lambda msg: True
        )
        self.assertIsNotNone(res_accepted)
        self.assertEqual(res_accepted['created_files_count'], 1)
        self.assertEqual(res_accepted['used_children'], 2)


if __name__ == '__main__':
    unittest.main()
