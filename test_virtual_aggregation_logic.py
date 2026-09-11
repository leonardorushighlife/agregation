import os
import shutil
import tempfile
import unittest
from unittest.mock import patch

from virtual_aggregation import (
    sanitize_filename,
    read_codes_from_file,
    perform_aggregation
)


class TestVirtualAggregationLogic(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_sanitize_filename(self):
        self.assertEqual(sanitize_filename('010460123456789021ABC/DEF'), '010460123456789021ABC_DEF')
        self.assertEqual(sanitize_filename('test:file*name?.txt'), 'test_file_name_.txt')
        self.assertEqual(sanitize_filename('  '), 'set_code')

    def test_read_codes_from_file_encodings(self):
        # UTF-8
        utf8_file = os.path.join(self.test_dir, "utf8.txt")
        with open(utf8_file, "w", encoding="utf-8") as f:
            f.write("CODE1\nCODE2\n\nCODE3\n")
        self.assertEqual(read_codes_from_file(utf8_file), ["CODE1", "CODE2", "CODE3"])

        # UTF-16
        utf16_file = os.path.join(self.test_dir, "utf16.txt")
        with open(utf16_file, "w", encoding="utf-16") as f:
            f.write("CODE_A\nCODE_B\n")
        self.assertEqual(read_codes_from_file(utf16_file), ["CODE_A", "CODE_B"])

        # CP1251
        cp1251_file = os.path.join(self.test_dir, "cp1251.txt")
        with open(cp1251_file, "w", encoding="cp1251") as f:
            f.write("КОД1\nКОД2\n")
        self.assertEqual(read_codes_from_file(cp1251_file), ["КОД1", "КОД2"])

    def test_perform_aggregation_success(self):
        parent_file = os.path.join(self.test_dir, "parents.txt")
        with open(parent_file, "w", encoding="utf-8") as f:
            f.write("PARENT1\nPARENT2\n")

        child_file1 = os.path.join(self.test_dir, "children1.txt")
        with open(child_file1, "w", encoding="utf-8") as f:
            f.write("CHILD1\nCHILD2\nCHILD3\nCHILD4\n")

        child_file2 = os.path.join(self.test_dir, "children2.txt")
        with open(child_file2, "w", encoding="utf-8") as f:
            f.write("CHILD5\nCHILD6\nCHILD7\nCHILD8\n")

        out_dir = os.path.join(self.test_dir, "output")
        res = perform_aggregation(
            parent_file=parent_file,
            child_files=[child_file1, child_file2],
            count_per_set=4,
            output_dir=out_dir
        )

        self.assertEqual(res["status"], "success")
        self.assertEqual(res["sets_created"], 2)
        self.assertEqual(res["children_used"], 8)

        # Verify output files
        file1 = os.path.join(out_dir, "PARENT1.txt")
        self.assertTrue(os.path.exists(file1))
        with open(file1, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip()]
            self.assertEqual(lines, ["PARENT1", "CHILD1", "CHILD2", "CHILD3", "CHILD4"])

        file2 = os.path.join(out_dir, "PARENT2.txt")
        self.assertTrue(os.path.exists(file2))
        with open(file2, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip()]
            self.assertEqual(lines, ["PARENT2", "CHILD5", "CHILD6", "CHILD7", "CHILD8"])

    def test_perform_aggregation_filename_collision(self):
        parent_file = os.path.join(self.test_dir, "parents_collision.txt")
        with open(parent_file, "w", encoding="utf-8") as f:
            f.write("PARENT/1\nPARENT?1\n")

        child_file = os.path.join(self.test_dir, "children.txt")
        with open(child_file, "w", encoding="utf-8") as f:
            f.write("C1\nC2\nC3\nC4\n")

        out_dir = os.path.join(self.test_dir, "output_collision")
        res = perform_aggregation(
            parent_file=parent_file,
            child_files=[child_file],
            count_per_set=2,
            output_dir=out_dir
        )

        self.assertEqual(res["sets_created"], 2)
        file1 = os.path.join(out_dir, "PARENT_1.txt")
        file2 = os.path.join(out_dir, "PARENT_1_1.txt")
        self.assertTrue(os.path.exists(file1))
        self.assertTrue(os.path.exists(file2))

    def test_perform_aggregation_insufficient_children_accepted(self):
        parent_file = os.path.join(self.test_dir, "parents.txt")
        with open(parent_file, "w", encoding="utf-8") as f:
            f.write("PARENT1\nPARENT2\nPARENT3\n")

        child_file = os.path.join(self.test_dir, "children.txt")
        with open(child_file, "w", encoding="utf-8") as f:
            f.write("C1\nC2\nC3\nC4\nC5\n")  # Only enough for 1 set of 4

        out_dir = os.path.join(self.test_dir, "output_partial")
        res = perform_aggregation(
            parent_file=parent_file,
            child_files=[child_file],
            count_per_set=4,
            output_dir=out_dir,
            confirm_partial_cb=lambda msg: True
        )

        self.assertEqual(res["status"], "success")
        self.assertEqual(res["sets_created"], 1)

    def test_perform_aggregation_insufficient_children_cancelled(self):
        parent_file = os.path.join(self.test_dir, "parents.txt")
        with open(parent_file, "w", encoding="utf-8") as f:
            f.write("PARENT1\nPARENT2\n")

        child_file = os.path.join(self.test_dir, "children.txt")
        with open(child_file, "w", encoding="utf-8") as f:
            f.write("C1\nC2\nC3\n")  # Not enough for even 1 set of 4

        out_dir = os.path.join(self.test_dir, "output_cancelled")

        with self.assertRaises(ValueError):
            perform_aggregation(
                parent_file=parent_file,
                child_files=[child_file],
                count_per_set=4,
                output_dir=out_dir
            )


if __name__ == "__main__":
    unittest.main()
