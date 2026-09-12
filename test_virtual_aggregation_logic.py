import os
import shutil
import tempfile
import unittest

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
        self.assertEqual(sanitize_filename('abc:def?ghi'), 'abc_def_ghi')
        self.assertEqual(sanitize_filename('code/123\\456*'), 'code_123_456_')
        self.assertEqual(sanitize_filename('<parent>"code"|'), '_parent__code__')

    def test_read_codes_encodings(self):
        # UTF-8
        path_utf8 = os.path.join(self.test_dir, 'utf8.txt')
        with open(path_utf8, 'w', encoding='utf-8') as f:
            f.write("CODE1\nCODE2\n\nCODE3\n")
        codes = read_codes(path_utf8)
        self.assertEqual(codes, ["CODE1", "CODE2", "CODE3"])

        # CP1251
        path_cp1251 = os.path.join(self.test_dir, 'cp1251.txt')
        with open(path_cp1251, 'w', encoding='cp1251') as f:
            f.write("КОД1\nКОД2\n")
        codes = read_codes(path_cp1251)
        self.assertEqual(codes, ["КОД1", "КОД2"])

        # UTF-16
        path_utf16 = os.path.join(self.test_dir, 'utf16.txt')
        with open(path_utf16, 'w', encoding='utf-16') as f:
            f.write("CODE_A\nCODE_B\n")
        codes = read_codes(path_utf16)
        self.assertEqual(codes, ["CODE_A", "CODE_B"])

    def test_perform_aggregation_success(self):
        parent_file = os.path.join(self.test_dir, 'parents.txt')
        with open(parent_file, 'w', encoding='utf-8') as f:
            f.write("PARENT_1\nPARENT_2\n")

        child_file1 = os.path.join(self.test_dir, 'child1.txt')
        with open(child_file1, 'w', encoding='utf-8') as f:
            f.write("CHILD_1\nCHILD_2\n")

        child_file2 = os.path.join(self.test_dir, 'child2.txt')
        with open(child_file2, 'w', encoding='utf-8') as f:
            f.write("CHILD_3\nCHILD_4\n")

        out_dir, count = perform_aggregation(
            parent_file=parent_file,
            child_files=[child_file1, child_file2],
            count_per_parent=2,
            output_dir=os.path.join(self.test_dir, 'output')
        )

        self.assertEqual(count, 2)
        self.assertTrue(os.path.exists(out_dir))

        file1 = os.path.join(out_dir, 'PARENT_1.txt')
        file2 = os.path.join(out_dir, 'PARENT_2.txt')
        self.assertTrue(os.path.exists(file1))
        self.assertTrue(os.path.exists(file2))

        with open(file1, 'r', encoding='utf-8') as f:
            content1 = [line.strip() for line in f]
        self.assertEqual(content1, ["PARENT_1", "CHILD_1", "CHILD_2"])

        with open(file2, 'r', encoding='utf-8') as f:
            content2 = [line.strip() for line in f]
        self.assertEqual(content2, ["PARENT_2", "CHILD_3", "CHILD_4"])

    def test_filename_collisions(self):
        parent_file = os.path.join(self.test_dir, 'parents.txt')
        with open(parent_file, 'w', encoding='utf-8') as f:
            f.write("PARENT:1\nPARENT/1\n")

        child_file = os.path.join(self.test_dir, 'child.txt')
        with open(child_file, 'w', encoding='utf-8') as f:
            f.write("C1\nC2\nC3\nC4\n")

        out_dir, count = perform_aggregation(
            parent_file=parent_file,
            child_files=[child_file],
            count_per_parent=2,
            output_dir=os.path.join(self.test_dir, 'output_collision')
        )

        self.assertEqual(count, 2)
        file1 = os.path.join(out_dir, 'PARENT_1.txt')
        file2 = os.path.join(out_dir, 'PARENT_1_1.txt')
        self.assertTrue(os.path.exists(file1))
        self.assertTrue(os.path.exists(file2))

    def test_insufficient_children_callback(self):
        parent_file = os.path.join(self.test_dir, 'parents.txt')
        with open(parent_file, 'w', encoding='utf-8') as f:
            f.write("PARENT_1\nPARENT_2\n")

        child_file = os.path.join(self.test_dir, 'child.txt')
        with open(child_file, 'w', encoding='utf-8') as f:
            f.write("CHILD_1\nCHILD_2\n")  # Only enough for 1 set of 2

        # Callback returns False (user cancels)
        out_dir, count = perform_aggregation(
            parent_file=parent_file,
            child_files=[child_file],
            count_per_parent=2,
            confirm_callback=lambda msg: False
        )
        self.assertIsNone(out_dir)
        self.assertEqual(count, 0)

        # Callback returns True (user proceeds)
        out_dir, count = perform_aggregation(
            parent_file=parent_file,
            child_files=[child_file],
            count_per_parent=2,
            output_dir=os.path.join(self.test_dir, 'output_partial'),
            confirm_callback=lambda msg: True
        )
        self.assertEqual(count, 1)
        self.assertTrue(os.path.exists(os.path.join(out_dir, 'PARENT_1.txt')))
        self.assertFalse(os.path.exists(os.path.join(out_dir, 'PARENT_2.txt')))

    def test_errors(self):
        # Non-existent parent file
        with self.assertRaises(ValueError):
            perform_aggregation(
                parent_file='non_existent.txt',
                child_files=['child.txt'],
                count_per_parent=2
            )

        # Count per parent <= 0
        parent_file = os.path.join(self.test_dir, 'parents.txt')
        with open(parent_file, 'w', encoding='utf-8') as f:
            f.write("PARENT_1\n")

        with self.assertRaises(ValueError):
            perform_aggregation(
                parent_file=parent_file,
                child_files=['child.txt'],
                count_per_parent=0
            )


if __name__ == '__main__':
    unittest.main()
