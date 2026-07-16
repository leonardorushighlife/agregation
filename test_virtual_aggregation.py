import os
import shutil
import tempfile
import unittest
from unittest.mock import MagicMock

from virtual_aggregation import (
    read_codes,
    sanitize_filename,
    get_unique_filepath,
    perform_aggregation
)

class TestVirtualAggregation(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_read_codes_encodings(self):
        # Create test files with different encodings
        encodings = {
            'utf-8-sig': 'utf-8-sig',
            'utf-16': 'utf-16',
            'utf-8': 'utf-8',
            'cp1251': 'cp1251'
        }
        test_lines = ["Код1", "Код2", "  Код3  ", ""]

        for enc_name, enc_val in encodings.items():
            filepath = os.path.join(self.temp_dir, f"test_{enc_name}.txt")
            with open(filepath, 'w', encoding=enc_val) as f:
                f.write("\n".join(test_lines))

            # Read and verify
            res = read_codes(filepath)
            self.assertEqual(res, ["Код1", "Код2", "Код3"])

    def test_sanitize_filename(self):
        dirty = r'parent/code\with:invalid*chars?and"angle<brackets>|pipe'
        expected = 'parent_code_with_invalid_chars_and_angle_brackets__pipe'
        self.assertEqual(sanitize_filename(dirty), expected)

    def test_get_unique_filepath(self):
        base_name = "test_file"
        path0 = get_unique_filepath(self.temp_dir, base_name)
        self.assertEqual(path0, os.path.join(self.temp_dir, f"{base_name}.txt"))

        # Create the file
        with open(path0, 'w') as f:
            f.write("test")

        path1 = get_unique_filepath(self.temp_dir, base_name)
        self.assertEqual(path1, os.path.join(self.temp_dir, f"{base_name}_1.txt"))

        with open(path1, 'w') as f:
            f.write("test1")

        path2 = get_unique_filepath(self.temp_dir, base_name)
        self.assertEqual(path2, os.path.join(self.temp_dir, f"{base_name}_2.txt"))

    def test_perform_aggregation_success(self):
        # Setup files
        parent_file = os.path.join(self.temp_dir, "parents.txt")
        with open(parent_file, 'w', encoding='utf-8') as f:
            f.write("Parent1\nParent2\n")

        child_file1 = os.path.join(self.temp_dir, "children1.txt")
        with open(child_file1, 'w', encoding='utf-8') as f:
            f.write("Child1\nChild2\nChild3\n")

        child_file2 = os.path.join(self.temp_dir, "children2.txt")
        with open(child_file2, 'w', encoding='utf-8') as f:
            f.write("Child4\nChild5\nChild6\n")

        # Perform aggregation: 2 parents, 5 children, 2 per parent (requires 4 children, we have 6)
        output_dir, created_files = perform_aggregation(
            parent_file=parent_file,
            child_files=[child_file1, child_file2],
            count_per_parent=2,
            output_dir_base=self.temp_dir
        )

        self.assertIsNotNone(output_dir)
        self.assertEqual(len(created_files), 2)

        # Verify the files contents
        # File 1: Parent1 -> Child1, Child2
        file1 = os.path.join(output_dir, "Parent1.txt")
        self.assertTrue(os.path.exists(file1))
        with open(file1, 'r', encoding='utf-8') as f:
            lines = f.read().splitlines()
        self.assertEqual(lines, ["Parent1", "Child1", "Child2"])

        # File 2: Parent2 -> Child3, Child4
        file2 = os.path.join(output_dir, "Parent2.txt")
        self.assertTrue(os.path.exists(file2))
        with open(file2, 'r', encoding='utf-8') as f:
            lines = f.read().splitlines()
        self.assertEqual(lines, ["Parent2", "Child3", "Child4"])

    def test_perform_aggregation_partial_confirm(self):
        parent_file = os.path.join(self.temp_dir, "parents.txt")
        with open(parent_file, 'w', encoding='utf-8') as f:
            f.write("Parent1\nParent2\nParent3\n")

        child_file = os.path.join(self.temp_dir, "children.txt")
        with open(child_file, 'w', encoding='utf-8') as f:
            f.write("Child1\nChild2\nChild3\n")

        # 3 parents, 3 children, 2 per parent (requires 6 children).
        # max possible full sets = 1.
        confirm_callback = MagicMock(return_value=True)

        output_dir, created_files = perform_aggregation(
            parent_file=parent_file,
            child_files=[child_file],
            count_per_parent=2,
            output_dir_base=self.temp_dir,
            confirm_callback=confirm_callback
        )

        # Confirm callback should have been called
        confirm_callback.assert_called_once()
        self.assertIsNotNone(output_dir)
        self.assertEqual(len(created_files), 1)

        file1 = os.path.join(output_dir, "Parent1.txt")
        self.assertTrue(os.path.exists(file1))
        with open(file1, 'r', encoding='utf-8') as f:
            lines = f.read().splitlines()
        self.assertEqual(lines, ["Parent1", "Child1", "Child2"])

    def test_perform_aggregation_partial_cancel(self):
        parent_file = os.path.join(self.temp_dir, "parents.txt")
        with open(parent_file, 'w', encoding='utf-8') as f:
            f.write("Parent1\nParent2\n")

        child_file = os.path.join(self.temp_dir, "children.txt")
        with open(child_file, 'w', encoding='utf-8') as f:
            f.write("Child1\n")

        # Requires 2 * 2 = 4 children, we have 1. C // n = 0, which raises ValueError
        with self.assertRaises(ValueError):
            perform_aggregation(
                parent_file=parent_file,
                child_files=[child_file],
                count_per_parent=2,
                output_dir_base=self.temp_dir
            )

        # Now test where C // n > 0 but less than required (e.g. 2 children)
        # We have 1 possible set, but user cancels
        with open(child_file, 'w', encoding='utf-8') as f:
            f.write("Child1\nChild2\n")

        confirm_callback = MagicMock(return_value=False)
        output_dir, created_files = perform_aggregation(
            parent_file=parent_file,
            child_files=[child_file],
            count_per_parent=2,
            output_dir_base=self.temp_dir,
            confirm_callback=confirm_callback
        )

        self.assertIsNone(output_dir)
        self.assertIsNone(created_files)

if __name__ == '__main__':
    unittest.main()
