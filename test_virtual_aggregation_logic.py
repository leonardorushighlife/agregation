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
        self.assertEqual(sanitize_filename("010460123456789021ABC/DEF"), "010460123456789021ABC_DEF")
        self.assertEqual(sanitize_filename("a\\b/c:d*e?f\"g<h>i|j"), "a_b_c_d_e_f_g_h_i_j")
        self.assertEqual(sanitize_filename("normal_filename"), "normal_filename")

    def test_read_codes_encodings(self):
        # Test UTF-8
        utf8_file = os.path.join(self.test_dir, "utf8.txt")
        with open(utf8_file, "w", encoding="utf-8") as f:
            f.write("CODE1\nCODE2\n\nCODE3\n")
        self.assertEqual(read_codes(utf8_file), ["CODE1", "CODE2", "CODE3"])

        # Test UTF-16
        utf16_file = os.path.join(self.test_dir, "utf16.txt")
        with open(utf16_file, "w", encoding="utf-16") as f:
            f.write("CODE_A\nCODE_B\n")
        self.assertEqual(read_codes(utf16_file), ["CODE_A", "CODE_B"])

        # Test CP1251
        cp1251_file = os.path.join(self.test_dir, "cp1251.txt")
        with open(cp1251_file, "w", encoding="cp1251") as f:
            f.write("КОД1\nКОД2\n")
        self.assertEqual(read_codes(cp1251_file), ["КОД1", "КОД2"])

    def test_read_codes_not_found(self):
        with self.assertRaises(FileNotFoundError):
            read_codes(os.path.join(self.test_dir, "non_existent.txt"))

    def test_read_codes_unicode_error(self):
        err_file = os.path.join(self.test_dir, "error.txt")
        with open(err_file, "w") as f:
            f.write("test")

        with patch("builtins.open", side_effect=UnicodeError("Decoding error")):
            with self.assertRaises(UnicodeError):
                read_codes(err_file)

    def test_perform_aggregation_success(self):
        parent_file = os.path.join(self.test_dir, "parents.txt")
        with open(parent_file, "w", encoding="utf-8") as f:
            f.write("PARENT1\nPARENT2\n")

        child_file1 = os.path.join(self.test_dir, "child1.txt")
        with open(child_file1, "w", encoding="utf-8") as f:
            f.write("CHILD1\nCHILD2\nCHILD3\n")

        child_file2 = os.path.join(self.test_dir, "child2.txt")
        with open(child_file2, "w", encoding="utf-8") as f:
            f.write("CHILD4\nCHILD5\nCHILD6\n")

        out_dir = os.path.join(self.test_dir, "output")
        res_dir, created = perform_aggregation(
            parent_file=parent_file,
            child_files=[child_file1, child_file2],
            count_per_set=3,
            output_dir=out_dir
        )

        self.assertEqual(res_dir, out_dir)
        self.assertEqual(created, 2)

        # Verify PARENT1 file
        file1 = os.path.join(out_dir, "PARENT1.txt")
        self.assertTrue(os.path.exists(file1))
        with open(file1, "r", encoding="utf-8") as f:
            lines = [l.strip() for l in f]
        self.assertEqual(lines, ["PARENT1", "CHILD1", "CHILD2", "CHILD3"])

        # Verify PARENT2 file
        file2 = os.path.join(out_dir, "PARENT2.txt")
        self.assertTrue(os.path.exists(file2))
        with open(file2, "r", encoding="utf-8") as f:
            lines = [l.strip() for l in f]
        self.assertEqual(lines, ["PARENT2", "CHILD4", "CHILD5", "CHILD6"])

    def test_perform_aggregation_validation(self):
        # Empty inputs
        with self.assertRaises(ValueError):
            perform_aggregation(parent_file="", child_files=["c.txt"], count_per_set=2)

        with self.assertRaises(ValueError):
            perform_aggregation(parent_file="p.txt", child_files=[], count_per_set=2)

        with self.assertRaises(ValueError):
            perform_aggregation(parent_file="p.txt", child_files=["c.txt"], count_per_set=0)

    def test_perform_aggregation_insufficient_children_confirmed(self):
        parent_file = os.path.join(self.test_dir, "parents.txt")
        with open(parent_file, "w", encoding="utf-8") as f:
            f.write("PARENT1\nPARENT2\nPARENT3\n")

        child_file = os.path.join(self.test_dir, "child.txt")
        with open(child_file, "w", encoding="utf-8") as f:
            f.write("CHILD1\nCHILD2\nCHILD3\nCHILD4\n")

        out_dir = os.path.join(self.test_dir, "output")
        res_dir, created = perform_aggregation(
            parent_file=parent_file,
            child_files=[child_file],
            count_per_set=2,
            output_dir=out_dir,
            confirm_callback=lambda msg: True
        )

        self.assertEqual(created, 2)
        self.assertTrue(os.path.exists(os.path.join(out_dir, "PARENT1.txt")))
        self.assertTrue(os.path.exists(os.path.join(out_dir, "PARENT2.txt")))
        self.assertFalse(os.path.exists(os.path.join(out_dir, "PARENT3.txt")))

    def test_perform_aggregation_insufficient_children_rejected(self):
        parent_file = os.path.join(self.test_dir, "parents.txt")
        with open(parent_file, "w", encoding="utf-8") as f:
            f.write("PARENT1\nPARENT2\n")

        child_file = os.path.join(self.test_dir, "child.txt")
        with open(child_file, "w", encoding="utf-8") as f:
            f.write("CHILD1\n")

        out_dir = os.path.join(self.test_dir, "output")
        res_dir, created = perform_aggregation(
            parent_file=parent_file,
            child_files=[child_file],
            count_per_set=2,
            output_dir=out_dir,
            confirm_callback=lambda msg: False
        )

        self.assertIsNone(res_dir)
        self.assertEqual(created, 0)

    def test_perform_aggregation_filename_collision(self):
        parent_file = os.path.join(self.test_dir, "parents.txt")
        # Same code twice or codes resulting in same sanitized filename
        with open(parent_file, "w", encoding="utf-8") as f:
            f.write("PARENT:1\nPARENT/1\n")

        child_file = os.path.join(self.test_dir, "child.txt")
        with open(child_file, "w", encoding="utf-8") as f:
            f.write("C1\nC2\nC3\nC4\n")

        out_dir = os.path.join(self.test_dir, "output")
        res_dir, created = perform_aggregation(
            parent_file=parent_file,
            child_files=[child_file],
            count_per_set=2,
            output_dir=out_dir
        )

        self.assertEqual(created, 2)
        self.assertTrue(os.path.exists(os.path.join(out_dir, "PARENT_1.txt")))
        self.assertTrue(os.path.exists(os.path.join(out_dir, "PARENT_1_1.txt")))


if __name__ == "__main__":
    unittest.main()
