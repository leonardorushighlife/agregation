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
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        # Clean up any created aggregation_results directories
        for entry in os.listdir("."):
            if entry.startswith("aggregation_results_") and os.path.isdir(entry):
                shutil.rmtree(entry, ignore_errors=True)

    def test_sanitize_filename(self):
        self.assertEqual(sanitize_filename("010460000000000121XXXXX"), "010460000000000121XXXXX")
        self.assertEqual(sanitize_filename("SET/123\\456*789?"), "SET_123_456_789_")
        self.assertEqual(sanitize_filename('  <code:"val">|  '), "_code__val___")
        self.assertEqual(sanitize_filename("   "), "set")

    def test_read_codes_encodings(self):
        content = ["0104601234567890", "0104601234567891", "0104601234567892"]

        # UTF-8
        utf8_path = os.path.join(self.temp_dir, "utf8.txt")
        with open(utf8_path, "w", encoding="utf-8") as f:
            f.write("\n".join(content) + "\n")
        self.assertEqual(read_codes(utf8_path), content)

        # UTF-16
        utf16_path = os.path.join(self.temp_dir, "utf16.txt")
        with open(utf16_path, "w", encoding="utf-16") as f:
            f.write("\n".join(content) + "\n")
        self.assertEqual(read_codes(utf16_path), content)

        # CP1251
        cp1251_path = os.path.join(self.temp_dir, "cp1251.txt")
        with open(cp1251_path, "w", encoding="cp1251") as f:
            f.write("\n".join(content) + "\n")
        self.assertEqual(read_codes(cp1251_path), content)

    def test_read_codes_unsupported_encoding(self):
        bad_path = os.path.join(self.temp_dir, "bad.txt")
        with open(bad_path, "wb") as f:
            f.write(b"\x80\x81\x82\x83\xff\xfe")

        with patch("builtins.open", side_effect=UnicodeError("Decoding failed")):
            with self.assertRaises(ValueError):
                read_codes(bad_path)

    def test_perform_aggregation_success(self):
        parent_path = os.path.join(self.temp_dir, "parents.txt")
        child1_path = os.path.join(self.temp_dir, "children1.txt")
        child2_path = os.path.join(self.temp_dir, "children2.txt")

        parents = ["PARENT_001", "PARENT_002"]
        children1 = ["CHILD_001", "CHILD_002"]
        children2 = ["CHILD_003", "CHILD_004"]

        with open(parent_path, "w", encoding="utf-8") as f:
            f.write("\n".join(parents))
        with open(child1_path, "w", encoding="utf-8") as f:
            f.write("\n".join(children1))
        with open(child2_path, "w", encoding="utf-8") as f:
            f.write("\n".join(children2))

        result = perform_aggregation(
            parent_file=parent_path,
            child_files=[child1_path, child2_path],
            items_per_parent=2
        )

        self.assertIsNotNone(result)
        self.assertEqual(result["total_created"], 2)
        self.assertEqual(result["actual_sets"], 2)
        self.assertTrue(os.path.exists(result["folder_path"]))

        # Check content of created files
        file1 = os.path.join(result["folder_path"], "PARENT_001.txt")
        file2 = os.path.join(result["folder_path"], "PARENT_002.txt")

        self.assertTrue(os.path.exists(file1))
        self.assertTrue(os.path.exists(file2))

        with open(file1, "r", encoding="utf-8") as f:
            lines1 = [line.strip() for line in f if line.strip()]
        self.assertEqual(lines1, ["PARENT_001", "CHILD_001", "CHILD_002"])

        with open(file2, "r", encoding="utf-8") as f:
            lines2 = [line.strip() for line in f if line.strip()]
        self.assertEqual(lines2, ["PARENT_002", "CHILD_003", "CHILD_004"])

    def test_perform_aggregation_filename_collision(self):
        parent_path = os.path.join(self.temp_dir, "parents.txt")
        child_path = os.path.join(self.temp_dir, "children.txt")

        # Parent codes that map to identical sanitized filenames
        parents = ["PARENT/001", "PARENT*001"]
        children = ["C1", "C2", "C3", "C4"]

        with open(parent_path, "w", encoding="utf-8") as f:
            f.write("\n".join(parents))
        with open(child_path, "w", encoding="utf-8") as f:
            f.write("\n".join(children))

        result = perform_aggregation(
            parent_file=parent_path,
            child_files=[child_path],
            items_per_parent=2
        )

        self.assertIsNotNone(result)
        file1 = os.path.join(result["folder_path"], "PARENT_001.txt")
        file2 = os.path.join(result["folder_path"], "PARENT_001_1.txt")

        self.assertTrue(os.path.exists(file1))
        self.assertTrue(os.path.exists(file2))

    def test_perform_aggregation_insufficient_children_accept(self):
        parent_path = os.path.join(self.temp_dir, "parents.txt")
        child_path = os.path.join(self.temp_dir, "children.txt")

        parents = ["P1", "P2", "P3"]
        children = ["C1", "C2", "C3", "C4"]  # Only enough for 2 sets of 2

        with open(parent_path, "w", encoding="utf-8") as f:
            f.write("\n".join(parents))
        with open(child_path, "w", encoding="utf-8") as f:
            f.write("\n".join(children))

        confirm_called = []

        def mock_confirm(msg):
            confirm_called.append(msg)
            return True

        result = perform_aggregation(
            parent_file=parent_path,
            child_files=[child_path],
            items_per_parent=2,
            confirm_callback=mock_confirm
        )

        self.assertEqual(len(confirm_called), 1)
        self.assertEqual(result["actual_sets"], 2)
        self.assertEqual(result["total_created"], 2)

    def test_perform_aggregation_insufficient_children_decline(self):
        parent_path = os.path.join(self.temp_dir, "parents.txt")
        child_path = os.path.join(self.temp_dir, "children.txt")

        parents = ["P1", "P2", "P3"]
        children = ["C1", "C2", "C3", "C4"]

        with open(parent_path, "w", encoding="utf-8") as f:
            f.write("\n".join(parents))
        with open(child_path, "w", encoding="utf-8") as f:
            f.write("\n".join(children))

        def mock_confirm(msg):
            return False

        result = perform_aggregation(
            parent_file=parent_path,
            child_files=[child_path],
            items_per_parent=2,
            confirm_callback=mock_confirm
        )

        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
