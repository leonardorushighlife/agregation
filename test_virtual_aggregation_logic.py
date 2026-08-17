import os
import shutil
import tempfile
import unittest
from unittest.mock import patch

from virtual_aggregation import sanitize_filename, read_codes, perform_aggregation


class TestVirtualAggregationLogic(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_sanitize_filename(self):
        self.assertEqual(sanitize_filename("valid_name"), "valid_name")
        self.assertEqual(sanitize_filename('invalid/name\\with:chars*?\"<>|'), "invalid_name_with_chars______")
        self.assertEqual(sanitize_filename("   "), "unnamed")
        self.assertEqual(sanitize_filename(""), "unnamed")

    def test_read_codes_encodings(self):
        # UTF-8
        utf8_path = os.path.join(self.test_dir, "utf8.txt")
        with open(utf8_path, "w", encoding="utf-8") as f:
            f.write("CODE1\nCODE2\n\nCODE3\n")
        self.assertEqual(read_codes(utf8_path), ["CODE1", "CODE2", "CODE3"])

        # UTF-16
        utf16_path = os.path.join(self.test_dir, "utf16.txt")
        with open(utf16_path, "w", encoding="utf-16") as f:
            f.write("CODE1\nCODE2\n")
        self.assertEqual(read_codes(utf16_path), ["CODE1", "CODE2"])

        # CP1251
        cp1251_path = os.path.join(self.test_dir, "cp1251.txt")
        with open(cp1251_path, "w", encoding="cp1251") as f:
            f.write("КОД1\nКОД2\n")
        self.assertEqual(read_codes(cp1251_path), ["КОД1", "КОД2"])

    def test_read_codes_invalid_encoding(self):
        bad_file = os.path.join(self.test_dir, "bad.txt")
        with open(bad_file, "wb") as f:
            f.write(b"\xff\xff\xff\xff\xff")

        with patch("builtins.open", side_effect=UnicodeError("Decode error")):
            with self.assertRaises(ValueError):
                read_codes(bad_file)

    def test_perform_aggregation_success(self):
        parent_path = os.path.join(self.test_dir, "parents.txt")
        child1_path = os.path.join(self.test_dir, "children1.txt")
        child2_path = os.path.join(self.test_dir, "children2.txt")

        with open(parent_path, "w", encoding="utf-8") as f:
            f.write("PARENT_001\nPARENT_002\n")

        with open(child1_path, "w", encoding="utf-8") as f:
            f.write("CHILD_1\nCHILD_2\nCHILD_3\nCHILD_4\n")

        with open(child2_path, "w", encoding="utf-8") as f:
            f.write("CHILD_5\nCHILD_6\nCHILD_7\nCHILD_8\n")

        out_dir = os.path.join(self.test_dir, "out")
        count, path = perform_aggregation(
            parent_file=parent_path,
            child_files=[child1_path, child2_path],
            items_per_set=4,
            output_dir=out_dir
        )

        self.assertEqual(count, 2)
        self.assertTrue(os.path.exists(os.path.join(out_dir, "PARENT_001.txt")))
        self.assertTrue(os.path.exists(os.path.join(out_dir, "PARENT_002.txt")))

        # Verify content of PARENT_001.txt
        with open(os.path.join(out_dir, "PARENT_001.txt"), "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip()]
        self.assertEqual(lines, ["PARENT_001", "CHILD_1", "CHILD_2", "CHILD_3", "CHILD_4"])

    def test_perform_aggregation_filename_collision(self):
        parent_path = os.path.join(self.test_dir, "parents.txt")
        child_path = os.path.join(self.test_dir, "children.txt")

        with open(parent_path, "w", encoding="utf-8") as f:
            f.write("PARENT_SAME\nPARENT_SAME\n")

        with open(child_path, "w", encoding="utf-8") as f:
            f.write("C1\nC2\nC3\nC4\n")

        out_dir = os.path.join(self.test_dir, "out_collision")
        count, path = perform_aggregation(
            parent_file=parent_path,
            child_files=[child_path],
            items_per_set=2,
            output_dir=out_dir
        )

        self.assertEqual(count, 2)
        self.assertTrue(os.path.exists(os.path.join(out_dir, "PARENT_SAME.txt")))
        self.assertTrue(os.path.exists(os.path.join(out_dir, "PARENT_SAME_1.txt")))

    def test_perform_aggregation_insufficient_children_accepted(self):
        parent_path = os.path.join(self.test_dir, "parents.txt")
        child_path = os.path.join(self.test_dir, "children.txt")

        with open(parent_path, "w", encoding="utf-8") as f:
            f.write("PARENT_01\nPARENT_02\nPARENT_03\n")

        with open(child_path, "w", encoding="utf-8") as f:
            f.write("C1\nC2\nC3\nC4\n")  # Only enough for 1 set of 4 items

        out_dir = os.path.join(self.test_dir, "out_partial")

        # Confirmation callback returns True (user accepts)
        count, path = perform_aggregation(
            parent_file=parent_path,
            child_files=[child_path],
            items_per_set=4,
            output_dir=out_dir,
            confirm_callback=lambda msg: True
        )

        self.assertEqual(count, 1)

    def test_perform_aggregation_insufficient_children_rejected(self):
        parent_path = os.path.join(self.test_dir, "parents.txt")
        child_path = os.path.join(self.test_dir, "children.txt")

        with open(parent_path, "w", encoding="utf-8") as f:
            f.write("PARENT_01\nPARENT_02\n")

        with open(child_path, "w", encoding="utf-8") as f:
            f.write("C1\nC2\n")

        out_dir = os.path.join(self.test_dir, "out_rejected")

        # Confirmation callback returns False (user cancels)
        with self.assertRaises(InterruptedError):
            perform_aggregation(
                parent_file=parent_path,
                child_files=[child_path],
                items_per_set=4,
                output_dir=out_dir,
                confirm_callback=lambda msg: False
            )


if __name__ == "__main__":
    unittest.main()
