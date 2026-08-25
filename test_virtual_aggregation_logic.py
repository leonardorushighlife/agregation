import unittest
import os
import shutil
import tempfile
from unittest.mock import patch, mock_open

from virtual_aggregation import (
    read_codes,
    sanitize_filename,
    perform_aggregation
)


class TestVirtualAggregationLogic(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_sanitize_filename(self):
        dirty_name = '010460000000000021SET/001:ABC*123?XYZ"1<2>3|END'
        cleaned = sanitize_filename(dirty_name)
        self.assertEqual(cleaned, '010460000000000021SET_001_ABC_123_XYZ_1_2_3_END')

    def test_read_codes_encodings(self):
        content_lines = ["CODE123", "CODE456", "CODE789"]
        text_data = "\n".join(content_lines) + "\n"

        for enc in ['utf-8', 'utf-8-sig', 'utf-16', 'cp1251']:
            file_path = os.path.join(self.test_dir, f"test_{enc}.txt")
            with open(file_path, 'w', encoding=enc) as f:
                f.write(text_data)

            codes = read_codes(file_path)
            self.assertEqual(codes, content_lines, f"Failed for encoding: {enc}")

    def test_read_codes_unsupported_encoding(self):
        file_path = os.path.join(self.test_dir, "invalid.txt")
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write("test content")

        with patch('builtins.open', mock_open()) as mock_file:
            mock_file.side_effect = UnicodeError("Decode error")
            with self.assertRaises(ValueError):
                read_codes(file_path)

    def test_perform_aggregation_success(self):
        parent_file = os.path.join(self.test_dir, "parents.txt")
        parent_codes = ["SET_PARENT_01", "SET_PARENT_02"]
        with open(parent_file, 'w', encoding='utf-8') as f:
            f.write("\n".join(parent_codes) + "\n")

        child_file1 = os.path.join(self.test_dir, "children1.txt")
        child_codes1 = ["CHILD_01", "CHILD_02"]
        with open(child_file1, 'w', encoding='utf-8') as f:
            f.write("\n".join(child_codes1) + "\n")

        child_file2 = os.path.join(self.test_dir, "children2.txt")
        child_codes2 = ["CHILD_03", "CHILD_04"]
        with open(child_file2, 'w', encoding='utf-8') as f:
            f.write("\n".join(child_codes2) + "\n")

        output_dir, created_count = perform_aggregation(
            parent_file=parent_file,
            child_files=[child_file1, child_file2],
            count_per_parent=2,
            output_dir_base=self.test_dir
        )

        self.assertEqual(created_count, 2)
        self.assertTrue(os.path.exists(output_dir))

        # Check file 1
        file1 = os.path.join(output_dir, "SET_PARENT_01.txt")
        self.assertTrue(os.path.exists(file1))
        with open(file1, 'r', encoding='utf-8') as f:
            lines1 = [line.strip() for line in f if line.strip()]
        self.assertEqual(lines1, ["SET_PARENT_01", "CHILD_01", "CHILD_02"])

        # Check file 2
        file2 = os.path.join(output_dir, "SET_PARENT_02.txt")
        self.assertTrue(os.path.exists(file2))
        with open(file2, 'r', encoding='utf-8') as f:
            lines2 = [line.strip() for line in f if line.strip()]
        self.assertEqual(lines2, ["SET_PARENT_02", "CHILD_03", "CHILD_04"])

    def test_perform_aggregation_partial_confirmation(self):
        parent_file = os.path.join(self.test_dir, "parents.txt")
        parent_codes = ["SET_PARENT_01", "SET_PARENT_02"]
        with open(parent_file, 'w', encoding='utf-8') as f:
            f.write("\n".join(parent_codes) + "\n")

        child_file = os.path.join(self.test_dir, "children.txt")
        child_codes = ["CHILD_01", "CHILD_02", "CHILD_03"] # Only enough for 1 set of 2
        with open(child_file, 'w', encoding='utf-8') as f:
            f.write("\n".join(child_codes) + "\n")

        # Refusal callback
        def confirm_no(msg):
            return False

        with self.assertRaises(Exception) as ctx:
            perform_aggregation(
                parent_file=parent_file,
                child_files=[child_file],
                count_per_parent=2,
                output_dir_base=self.test_dir,
                confirm_callback=confirm_no
            )
        self.assertIn("Операция отменена", str(ctx.exception))

        # Approval callback
        def confirm_yes(msg):
            return True

        output_dir, created_count = perform_aggregation(
            parent_file=parent_file,
            child_files=[child_file],
            count_per_parent=2,
            output_dir_base=self.test_dir,
            confirm_callback=confirm_yes
        )
        self.assertEqual(created_count, 1)

    def test_perform_aggregation_filename_collision(self):
        parent_file = os.path.join(self.test_dir, "parents.txt")
        parent_codes = ["SET/PARENT/SAME", "SET*PARENT*SAME"]
        with open(parent_file, 'w', encoding='utf-8') as f:
            f.write("\n".join(parent_codes) + "\n")

        child_file = os.path.join(self.test_dir, "children.txt")
        child_codes = ["C1", "C2"]
        with open(child_file, 'w', encoding='utf-8') as f:
            f.write("\n".join(child_codes) + "\n")

        output_dir, created_count = perform_aggregation(
            parent_file=parent_file,
            child_files=[child_file],
            count_per_parent=1,
            output_dir_base=self.test_dir
        )

        self.assertEqual(created_count, 2)
        file1 = os.path.join(output_dir, "SET_PARENT_SAME.txt")
        file2 = os.path.join(output_dir, "SET_PARENT_SAME_1.txt")
        self.assertTrue(os.path.exists(file1))
        self.assertTrue(os.path.exists(file2))


if __name__ == "__main__":
    unittest.main()
