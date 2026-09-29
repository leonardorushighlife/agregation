import unittest
import os
import shutil
import tempfile
from unittest.mock import patch, MagicMock

import virtual_aggregation as va


class TestVirtualAggregationLogic(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_sanitize_filename(self):
        self.assertEqual(va.sanitize_filename("SET/123\\456:789*?\"<>|"), "SET_123_456_789______")
        self.assertEqual(va.sanitize_filename("   "), "unnamed_set")
        self.assertEqual(va.sanitize_filename("010460123456789021SET123456"), "010460123456789021SET123456")

    def test_read_codes_encodings(self):
        # UTF-8 with BOM
        utf8_bom_file = os.path.join(self.test_dir, "utf8_bom.txt")
        with open(utf8_bom_file, "w", encoding="utf-8-sig") as f:
            f.write("CODE1\nCODE2\n")
        self.assertEqual(va.read_codes(utf8_bom_file), ["CODE1", "CODE2"])

        # UTF-16
        utf16_file = os.path.join(self.test_dir, "utf16.txt")
        with open(utf16_file, "w", encoding="utf-16") as f:
            f.write("CODE3\nCODE4\n")
        self.assertEqual(va.read_codes(utf16_file), ["CODE3", "CODE4"])

        # CP1251
        cp1251_file = os.path.join(self.test_dir, "cp1251.txt")
        with open(cp1251_file, "w", encoding="cp1251") as f:
            f.write("КОД1\nКОД2\n")
        self.assertEqual(va.read_codes(cp1251_file), ["КОД1", "КОД2"])

    def test_read_codes_unicode_error(self):
        bad_file = os.path.join(self.test_dir, "bad.txt")
        with open(bad_file, "wb") as f:
            f.write(b"\x80\x81\x82")  # invalid bytes for utf-8/16

        # With mock to ensure UnicodeError raises ValueError
        with patch("builtins.open", side_effect=UnicodeError("Decoding failed")):
            with self.assertRaises(ValueError):
                va.read_codes(bad_file)

    def test_perform_aggregation_success(self):
        parent_file = os.path.join(self.test_dir, "parents.txt")
        with open(parent_file, "w", encoding="utf-8") as f:
            f.write("SET_001\nSET_002\n")

        child1 = os.path.join(self.test_dir, "child1.txt")
        with open(child1, "w", encoding="utf-8") as f:
            f.write("ITEM_1\nITEM_2\nITEM_3\nITEM_4\n")

        child2 = os.path.join(self.test_dir, "child2.txt")
        with open(child2, "w", encoding="utf-8") as f:
            f.write("ITEM_5\nITEM_6\nITEM_7\nITEM_8\n")

        result = va.perform_aggregation(
            parent_file=parent_file,
            child_files=[child1, child2],
            count_per_parent=4,
            output_base_dir=self.test_dir
        )

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["created_files"], 2)
        self.assertEqual(result["used_children"], 8)

        # Check output contents of SET_001.txt
        set1_path = os.path.join(result["output_dir"], "SET_001.txt")
        self.assertTrue(os.path.exists(set1_path))
        with open(set1_path, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip()]
        self.assertEqual(lines, ["SET_001", "ITEM_1", "ITEM_2", "ITEM_3", "ITEM_4"])

        # Check output contents of SET_002.txt
        set2_path = os.path.join(result["output_dir"], "SET_002.txt")
        self.assertTrue(os.path.exists(set2_path))
        with open(set2_path, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip()]
        self.assertEqual(lines, ["SET_002", "ITEM_5", "ITEM_6", "ITEM_7", "ITEM_8"])

    def test_perform_aggregation_filename_collision(self):
        parent_file = os.path.join(self.test_dir, "parents.txt")
        with open(parent_file, "w", encoding="utf-8") as f:
            f.write("SET/001\nSET?001\n")  # Both sanitize to SET_001

        child_file = os.path.join(self.test_dir, "child.txt")
        with open(child_file, "w", encoding="utf-8") as f:
            f.write("ITEM_1\nITEM_2\nITEM_3\nITEM_4\n")

        result = va.perform_aggregation(
            parent_file=parent_file,
            child_files=[child_file],
            count_per_parent=2,
            output_base_dir=self.test_dir
        )

        self.assertEqual(result["created_files"], 2)
        set1_path = os.path.join(result["output_dir"], "SET_001.txt")
        set2_path = os.path.join(result["output_dir"], "SET_001_1.txt")
        self.assertTrue(os.path.exists(set1_path))
        self.assertTrue(os.path.exists(set2_path))

    def test_perform_aggregation_partial_confirmation(self):
        parent_file = os.path.join(self.test_dir, "parents.txt")
        with open(parent_file, "w", encoding="utf-8") as f:
            f.write("SET_1\nSET_2\nSET_3\n")

        child_file = os.path.join(self.test_dir, "child.txt")
        with open(child_file, "w", encoding="utf-8") as f:
            f.write("ITEM_1\nITEM_2\nITEM_3\nITEM_4\n")  # Only enough for 2 sets of 2

        # User confirms partial
        confirm_mock = MagicMock(return_value=True)
        result = va.perform_aggregation(
            parent_file=parent_file,
            child_files=[child_file],
            count_per_parent=2,
            output_base_dir=self.test_dir,
            confirm_callback=confirm_mock
        )

        confirm_mock.assert_called_once_with(2, 3)
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["created_files"], 2)

        # User cancels partial
        confirm_cancel_mock = MagicMock(return_value=False)
        result_cancelled = va.perform_aggregation(
            parent_file=parent_file,
            child_files=[child_file],
            count_per_parent=2,
            output_base_dir=self.test_dir,
            confirm_callback=confirm_cancel_mock
        )
        self.assertEqual(result_cancelled["status"], "cancelled")


if __name__ == "__main__":
    unittest.main()
