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


class TestVirtualAggregationLogic(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_sanitize_filename(self):
        self.assertEqual(sanitize_filename("010460000000000021SET123"), "010460000000000021SET123")
        self.assertEqual(sanitize_filename("CODE/123\\456:789*?\"<>|"), "CODE_123_456_789______")
        self.assertEqual(sanitize_filename("   "), "unnamed")

    def test_read_codes_encodings(self):
        # UTF-8 with BOM
        p1 = os.path.join(self.temp_dir, "utf8_bom.txt")
        with open(p1, "w", encoding="utf-8-sig") as f:
            f.write("CODE1\nCODE2\n\nCODE3\n")
        self.assertEqual(read_codes(p1), ["CODE1", "CODE2", "CODE3"])

        # UTF-16
        p2 = os.path.join(self.temp_dir, "utf16.txt")
        with open(p2, "w", encoding="utf-16") as f:
            f.write("CODE4\nCODE5\n")
        self.assertEqual(read_codes(p2), ["CODE4", "CODE5"])

        # CP1251
        p3 = os.path.join(self.temp_dir, "cp1251.txt")
        with open(p3, "w", encoding="cp1251") as f:
            f.write("КОД1\nКОД2\n")
        self.assertEqual(read_codes(p3), ["КОД1", "КОД2"])

    def test_read_codes_unicode_error(self):
        p = os.path.join(self.temp_dir, "bad.txt")
        with open(p, "wb") as f:
            f.write(b"\xff\xff\xff\xff")

        # Mock open to raise UnicodeError across encodings
        with patch("builtins.open", side_effect=UnicodeError("Decoding error")):
            with self.assertRaises(ValueError):
                read_codes(p)

    def test_perform_aggregation_success(self):
        parent_file = os.path.join(self.temp_dir, "parents.txt")
        with open(parent_file, "w", encoding="utf-8") as f:
            f.write("PARENT_001\nPARENT_002\n")

        child_file1 = os.path.join(self.temp_dir, "child1.txt")
        with open(child_file1, "w", encoding="utf-8") as f:
            f.write("CHILD_A1\nCHILD_A2\nCHILD_B1\n")

        child_file2 = os.path.join(self.temp_dir, "child2.txt")
        with open(child_file2, "w", encoding="utf-8") as f:
            f.write("CHILD_B2\n")

        out_dir = os.path.join(self.temp_dir, "output")
        res = perform_aggregation(
            parent_file=parent_file,
            child_files=[child_file1, child_file2],
            count_per_parent=2,
            output_dir=out_dir
        )

        self.assertEqual(res["status"], "success")
        self.assertEqual(len(res["created_files"]), 2)

        # Verify contents of set 1
        set1_file = os.path.join(out_dir, "PARENT_001.txt")
        self.assertTrue(os.path.exists(set1_file))
        with open(set1_file, "r", encoding="utf-8") as f:
            lines = [l.strip() for l in f.readlines() if l.strip()]
        self.assertEqual(lines, ["PARENT_001", "CHILD_A1", "CHILD_A2"])

        # Verify contents of set 2
        set2_file = os.path.join(out_dir, "PARENT_002.txt")
        self.assertTrue(os.path.exists(set2_file))
        with open(set2_file, "r", encoding="utf-8") as f:
            lines = [l.strip() for l in f.readlines() if l.strip()]
        self.assertEqual(lines, ["PARENT_002", "CHILD_B1", "CHILD_B2"])

    def test_perform_aggregation_filename_collision(self):
        parent_file = os.path.join(self.temp_dir, "parents.txt")
        with open(parent_file, "w", encoding="utf-8") as f:
            f.write("PARENT/001\nPARENT:001\n")  # Both sanitize to PARENT_001

        child_file = os.path.join(self.temp_dir, "children.txt")
        with open(child_file, "w", encoding="utf-8") as f:
            f.write("C1\nC2\n")

        out_dir = os.path.join(self.temp_dir, "output_collision")
        res = perform_aggregation(
            parent_file=parent_file,
            child_files=[child_file],
            count_per_parent=1,
            output_dir=out_dir
        )

        self.assertEqual(res["status"], "success")
        self.assertEqual(len(res["created_files"]), 2)
        self.assertTrue(os.path.exists(os.path.join(out_dir, "PARENT_001.txt")))
        self.assertTrue(os.path.exists(os.path.join(out_dir, "PARENT_001_1.txt")))

    def test_perform_aggregation_partial_confirmation(self):
        parent_file = os.path.join(self.temp_dir, "parents.txt")
        with open(parent_file, "w", encoding="utf-8") as f:
            f.write("PARENT_1\nPARENT_2\nPARENT_3\n")

        child_file = os.path.join(self.temp_dir, "children.txt")
        with open(child_file, "w", encoding="utf-8") as f:
            f.write("C1\nC2\nC3\n")  # Only 3 children, count per parent = 2 -> 1 full set possible

        out_dir = os.path.join(self.temp_dir, "output_partial")

        # Test cancelled
        res_cancel = perform_aggregation(
            parent_file=parent_file,
            child_files=[child_file],
            count_per_parent=2,
            output_dir=out_dir,
            confirm_callback=lambda avail, req, poss: False
        )
        self.assertEqual(res_cancel["status"], "cancelled")

        # Test approved
        res_approved = perform_aggregation(
            parent_file=parent_file,
            child_files=[child_file],
            count_per_parent=2,
            output_dir=out_dir,
            confirm_callback=lambda avail, req, poss: True
        )
        self.assertEqual(res_approved["status"], "success")
        self.assertEqual(len(res_approved["created_files"]), 1)


if __name__ == "__main__":
    unittest.main()
