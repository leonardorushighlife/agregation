import os
import shutil
import tempfile
import unittest
from unittest.mock import patch, MagicMock

from virtual_aggregation import sanitize_filename, read_codes, perform_aggregation


class TestVirtualAggregationLogic(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_sanitize_filename(self):
        self.assertEqual(sanitize_filename('010461234567890121ABC/DEF?G*H'), '010461234567890121ABC_DEF_G_H')
        self.assertEqual(sanitize_filename('SET:123<456>789|'), 'SET_123_456_789_')
        self.assertEqual(sanitize_filename('  CLEAN_CODE_123  '), 'CLEAN_CODE_123')

    def test_read_codes_utf8_and_cp1251(self):
        # UTF-8 test file
        utf8_file = os.path.join(self.test_dir, 'utf8.txt')
        with open(utf8_file, 'w', encoding='utf-8') as f:
            f.write("CODE1\nCODE2\n\nCODE3  \n")

        codes = read_codes(utf8_file)
        self.assertEqual(codes, ['CODE1', 'CODE2', 'CODE3'])

        # CP1251 test file
        cp1251_file = os.path.join(self.test_dir, 'cp1251.txt')
        with open(cp1251_file, 'w', encoding='cp1251') as f:
            f.write("КОД1\nКОД2\n")

        codes_cp = read_codes(cp1251_file)
        self.assertEqual(codes_cp, ['КОД1', 'КОД2'])

    def test_read_codes_encoding_fallback(self):
        file_path = os.path.join(self.test_dir, 'fallback.txt')
        with open(file_path, 'wb') as f:
            f.write(b"CODE1\nCODE2\n")

        with patch('builtins.open', side_effect=[UnicodeError("Test Error"), open(file_path, 'r', encoding='utf-8')]):
            codes = read_codes(file_path)
            self.assertEqual(codes, ['CODE1', 'CODE2'])

    def test_perform_aggregation_success(self):
        parents = ['SET001', 'SET002']
        children = ['ITEM1', 'ITEM2', 'ITEM3', 'ITEM4', 'ITEM5', 'ITEM6', 'ITEM7', 'ITEM8']
        count_per_parent = 4

        created_count, folder_name = perform_aggregation(parents, children, count_per_parent)
        self.assertTrue(os.path.exists(folder_name))
        self.assertEqual(created_count, 2)

        # Verify generated files content
        file1 = os.path.join(folder_name, 'SET001.txt')
        file2 = os.path.join(folder_name, 'SET002.txt')
        self.assertTrue(os.path.exists(file1))
        self.assertTrue(os.path.exists(file2))

        with open(file1, 'r', encoding='utf-8') as f:
            lines = [line.strip() for line in f if line.strip()]
        self.assertEqual(lines, ['SET001', 'ITEM1', 'ITEM2', 'ITEM3', 'ITEM4'])

        with open(file2, 'r', encoding='utf-8') as f:
            lines = [line.strip() for line in f if line.strip()]
        self.assertEqual(lines, ['SET002', 'ITEM5', 'ITEM6', 'ITEM7', 'ITEM8'])

        # Clean up created folder
        shutil.rmtree(folder_name)

    def test_perform_aggregation_duplicate_parent_filenames(self):
        parents = ['SET/001', 'SET\\001']
        children = ['I1', 'I2', 'I3', 'I4']
        count_per_parent = 2

        created_count, folder_name = perform_aggregation(parents, children, count_per_parent)
        self.assertEqual(created_count, 2)

        file1 = os.path.join(folder_name, 'SET_001.txt')
        file2 = os.path.join(folder_name, 'SET_001_1.txt')
        self.assertTrue(os.path.exists(file1))
        self.assertTrue(os.path.exists(file2))

        shutil.rmtree(folder_name)

    def test_perform_aggregation_partial_confirm(self):
        parents = ['SET1', 'SET2', 'SET3']
        children = ['I1', 'I2', 'I3', 'I4']  # Only enough for 2 sets of 2
        count_per_parent = 2

        confirm_mock = MagicMock(return_value=True)
        created_count, folder_name = perform_aggregation(parents, children, count_per_parent, confirm_callback=confirm_mock)

        confirm_mock.assert_called_once()
        self.assertEqual(created_count, 2)

        shutil.rmtree(folder_name)

    def test_perform_aggregation_partial_reject(self):
        parents = ['SET1', 'SET2']
        children = ['I1', 'I2']  # Not enough for 2 sets of 2
        count_per_parent = 2

        confirm_mock = MagicMock(return_value=False)
        created_count, folder_name = perform_aggregation(parents, children, count_per_parent, confirm_callback=confirm_mock)

        confirm_mock.assert_called_once()
        self.assertEqual(created_count, 0)
        self.assertEqual(folder_name, "")


if __name__ == '__main__':
    unittest.main()
