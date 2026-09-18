import os
import shutil
import tempfile
import unittest
from unittest.mock import patch, MagicMock

from virtual_aggregation import (
    sanitize_filename,
    read_codes,
    perform_aggregation,
)


class TestVirtualAggregationLogic(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_sanitize_filename(self):
        self.assertEqual(sanitize_filename("SET/001:ABC*?"), "SET_001_ABC__")
        self.assertEqual(sanitize_filename("   "), "unnamed")
        self.assertEqual(sanitize_filename(""), "unnamed")
        self.assertEqual(sanitize_filename("NORMAL_CODE_123"), "NORMAL_CODE_123")

    def test_read_codes_encodings(self):
        # UTF-8 with BOM
        utf8_sig_file = os.path.join(self.test_dir, "utf8_sig.txt")
        with open(utf8_sig_file, "w", encoding="utf-8-sig") as f:
            f.write("CODE1\nCODE2\n")

        # CP1251
        cp1251_file = os.path.join(self.test_dir, "cp1251.txt")
        with open(cp1251_file, "w", encoding="cp1251") as f:
            f.write("КОД1\nКОД2\n")

        # UTF-16
        utf16_file = os.path.join(self.test_dir, "utf16.txt")
        with open(utf16_file, "w", encoding="utf-16") as f:
            f.write("CODE_A\nCODE_B\n")

        self.assertEqual(read_codes(utf8_sig_file), ["CODE1", "CODE2"])
        self.assertEqual(read_codes(cp1251_file), ["КОД1", "КОД2"])
        self.assertEqual(read_codes(utf16_file), ["CODE_A", "CODE_B"])

    @patch("builtins.open")
    def test_read_codes_fallback(self, mock_open):
        mock_file = MagicMock()
        mock_file.__enter__.return_value.read.side_effect = [
            UnicodeError("BOM mismatch"),
            UnicodeError("BOM mismatch"),
            UnicodeError("BOM mismatch"),
            UnicodeError("BOM mismatch"),
            "FALLBACK_CODE\n",
        ]
        mock_open.return_value = mock_file

        codes = read_codes("dummy_path.txt")
        self.assertEqual(codes, ["FALLBACK_CODE"])

    def test_perform_aggregation_basic(self):
        parent_file = os.path.join(self.test_dir, "parents.txt")
        with open(parent_file, "w", encoding="utf-8") as f:
            f.write("PARENT_001\nPARENT_002\n")

        child_file1 = os.path.join(self.test_dir, "child1.txt")
        with open(child_file1, "w", encoding="utf-8") as f:
            f.write("CHILD_001\nCHILD_002\n")

        child_file2 = os.path.join(self.test_dir, "child2.txt")
        with open(child_file2, "w", encoding="utf-8") as f:
            f.write("CHILD_003\nCHILD_004\n")

        child_file3 = os.path.join(self.test_dir, "child3.txt")
        with open(child_file3, "w", encoding="utf-8") as f:
            f.write("CHILD_005\nCHILD_006\n")

        output_dir = os.path.join(self.test_dir, "output")

        # Total 1 parent set requires 3 items (3 per parent)
        # 2 parents * 3 children = 6 total child codes across 3 files
        res = perform_aggregation(
            parent_file=parent_file,
            child_files=[child_file1, child_file2, child_file3],
            count_per_parent=3,
            output_dir=output_dir
        )

        self.assertEqual(res["status"], "success")
        self.assertEqual(res["parents_processed"], 2)
        self.assertEqual(res["files_created"], 2)
        self.assertEqual(res["total_children_used"], 6)

        # Check output file content for PARENT_001
        p1_file = os.path.join(output_dir, "PARENT_001.txt")
        self.assertTrue(os.path.exists(p1_file))
        with open(p1_file, "r", encoding="utf-8") as f:
            lines = [l.strip() for l in f if l.strip()]
        self.assertEqual(lines, ["PARENT_001", "CHILD_001", "CHILD_002", "CHILD_003"])

        # Check output file content for PARENT_002
        p2_file = os.path.join(output_dir, "PARENT_002.txt")
        self.assertTrue(os.path.exists(p2_file))
        with open(p2_file, "r", encoding="utf-8") as f:
            lines = [l.strip() for l in f if l.strip()]
        self.assertEqual(lines, ["PARENT_002", "CHILD_004", "CHILD_005", "CHILD_006"])

    def test_perform_aggregation_insufficient_children_confirmed(self):
        parent_file = os.path.join(self.test_dir, "parents.txt")
        with open(parent_file, "w", encoding="utf-8") as f:
            f.write("PARENT_001\nPARENT_002\n")

        child_file = os.path.join(self.test_dir, "child.txt")
        with open(child_file, "w", encoding="utf-8") as f:
            f.write("CHILD_001\nCHILD_002\nCHILD_003\n")  # Only enough for 1 set of 2

        output_dir = os.path.join(self.test_dir, "output")

        confirm_mock = MagicMock(return_value=True)

        res = perform_aggregation(
            parent_file=parent_file,
            child_files=[child_file],
            count_per_parent=2,
            output_dir=output_dir,
            confirm_callback=confirm_mock
        )

        self.assertTrue(confirm_mock.called)
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["parents_processed"], 1)
        self.assertEqual(res["files_created"], 1)

    def test_perform_aggregation_filename_collision(self):
        parent_file = os.path.join(self.test_dir, "parents.txt")
        with open(parent_file, "w", encoding="utf-8") as f:
            f.write("SET/001\nSET?001\n")  # Both sanitize to SET_001

        child_file = os.path.join(self.test_dir, "child.txt")
        with open(child_file, "w", encoding="utf-8") as f:
            f.write("C1\nC2\n")

        output_dir = os.path.join(self.test_dir, "output")

        res = perform_aggregation(
            parent_file=parent_file,
            child_files=[child_file],
            count_per_parent=1,
            output_dir=output_dir
        )

        self.assertEqual(res["files_created"], 2)
        self.assertTrue(os.path.exists(os.path.join(output_dir, "SET_001.txt")))
        self.assertTrue(os.path.exists(os.path.join(output_dir, "SET_001_1.txt")))


if __name__ == "__main__":
    unittest.main()
