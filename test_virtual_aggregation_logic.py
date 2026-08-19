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
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_sanitize_filename(self):
        self.assertEqual(sanitize_filename('normal_name'), 'normal_name')
        self.assertEqual(sanitize_filename('code/123\\456*789?'), 'code_123_456_789_')
        self.assertEqual(sanitize_filename('   <invalid>|:"   '), '_invalid____')
        self.assertEqual(sanitize_filename('...'), 'set')

    def test_read_codes_encodings(self):
        # Create files with different encodings
        utf8_file = os.path.join(self.test_dir, 'utf8.txt')
        cp1251_file = os.path.join(self.test_dir, 'cp1251.txt')
        utf16_file = os.path.join(self.test_dir, 'utf16.txt')

        with open(utf8_file, 'w', encoding='utf-8') as f:
            f.write("CODE_UTF8_1\nCODE_UTF8_2\n")

        with open(cp1251_file, 'w', encoding='cp1251') as f:
            f.write("КОД_1251_1\nКОД_1251_2\n")

        with open(utf16_file, 'w', encoding='utf-16') as f:
            f.write("CODE_UTF16_1\nCODE_UTF16_2\n")

        codes = read_codes([utf8_file, cp1251_file, utf16_file])
        self.assertEqual(codes, [
            "CODE_UTF8_1", "CODE_UTF8_2",
            "КОД_1251_1", "КОД_1251_2",
            "CODE_UTF16_1", "CODE_UTF16_2"
        ])

    def test_perform_aggregation_success(self):
        parent_file = os.path.join(self.test_dir, 'parents.txt')
        child_file1 = os.path.join(self.test_dir, 'children1.txt')
        child_file2 = os.path.join(self.test_dir, 'children2.txt')
        child_file3 = os.path.join(self.test_dir, 'children3.txt')

        with open(parent_file, 'w', encoding='utf-8') as f:
            f.write("SET_001\nSET_002\n")

        with open(child_file1, 'w', encoding='utf-8') as f:
            f.write("ITEM_1\nITEM_2\n")

        with open(child_file2, 'w', encoding='utf-8') as f:
            f.write("ITEM_3\nITEM_4\n")

        with open(child_file3, 'w', encoding='utf-8') as f:
            f.write("ITEM_5\nITEM_6\n")

        out_dir = os.path.join(self.test_dir, 'output')
        success, msg, created_count = perform_aggregation(
            parent_file=parent_file,
            child_files=[child_file1, child_file2, child_file3],
            count_per_parent=3,
            output_dir=out_dir
        )

        self.assertTrue(success)
        self.assertEqual(created_count, 2)

        file1 = os.path.join(out_dir, 'SET_001.txt')
        file2 = os.path.join(out_dir, 'SET_002.txt')

        self.assertTrue(os.path.exists(file1))
        self.assertTrue(os.path.exists(file2))

        with open(file1, 'r', encoding='utf-8') as f:
            lines1 = [line.strip() for line in f]
        self.assertEqual(lines1, ['SET_001', 'ITEM_1', 'ITEM_2', 'ITEM_3'])

        with open(file2, 'r', encoding='utf-8') as f:
            lines2 = [line.strip() for line in f]
        self.assertEqual(lines2, ['SET_002', 'ITEM_4', 'ITEM_5', 'ITEM_6'])

    def test_perform_aggregation_insufficient_children_approved(self):
        parent_file = os.path.join(self.test_dir, 'parents.txt')
        child_file = os.path.join(self.test_dir, 'children.txt')

        with open(parent_file, 'w', encoding='utf-8') as f:
            f.write("SET_001\nSET_002\nSET_003\n")

        with open(child_file, 'w', encoding='utf-8') as f:
            f.write("ITEM_1\nITEM_2\nITEM_3\n")

        out_dir = os.path.join(self.test_dir, 'output_partial')

        # Mock confirm_callback returning True
        confirm_mock = lambda avail, need: True

        success, msg, created_count = perform_aggregation(
            parent_file=parent_file,
            child_files=[child_file],
            count_per_parent=2,
            output_dir=out_dir,
            confirm_callback=confirm_mock
        )

        self.assertTrue(success)
        self.assertEqual(created_count, 1)

    def test_perform_aggregation_insufficient_children_rejected(self):
        parent_file = os.path.join(self.test_dir, 'parents.txt')
        child_file = os.path.join(self.test_dir, 'children.txt')

        with open(parent_file, 'w', encoding='utf-8') as f:
            f.write("SET_001\nSET_002\n")

        with open(child_file, 'w', encoding='utf-8') as f:
            f.write("ITEM_1\n")

        confirm_mock = lambda avail, need: False

        success, msg, created_count = perform_aggregation(
            parent_file=parent_file,
            child_files=[child_file],
            count_per_parent=2,
            confirm_callback=confirm_mock
        )

        self.assertFalse(success)
        self.assertEqual(created_count, 0)
        self.assertIn("отменена", msg)

    def test_filename_collision_handling(self):
        parent_file = os.path.join(self.test_dir, 'parents.txt')
        child_file = os.path.join(self.test_dir, 'children.txt')

        # Parent codes that sanitize to the same filename 'SET_001'
        with open(parent_file, 'w', encoding='utf-8') as f:
            f.write("SET/001\nSET?001\n")

        with open(child_file, 'w', encoding='utf-8') as f:
            f.write("ITEM_1\nITEM_2\n")

        out_dir = os.path.join(self.test_dir, 'output_collision')

        success, msg, created_count = perform_aggregation(
            parent_file=parent_file,
            child_files=[child_file],
            count_per_parent=1,
            output_dir=out_dir
        )

        self.assertTrue(success)
        self.assertEqual(created_count, 2)

        file1 = os.path.join(out_dir, 'SET_001.txt')
        file2 = os.path.join(out_dir, 'SET_001_1.txt')

        self.assertTrue(os.path.exists(file1))
        self.assertTrue(os.path.exists(file2))


if __name__ == '__main__':
    unittest.main()
