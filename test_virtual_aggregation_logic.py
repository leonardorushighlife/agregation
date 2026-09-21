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
        self.assertEqual(sanitize_filename('0104600000000000215XXXXX'), '0104600000000000215XXXXX')
        self.assertEqual(sanitize_filename('code/123\\456:789*?\"<>|'), 'code_123_456_789______')
        self.assertEqual(sanitize_filename('  .code.  '), 'code')
        self.assertEqual(sanitize_filename(''), 'unnamed')

    def test_read_codes_encodings(self):
        # UTF-8
        utf8_file = os.path.join(self.test_dir, 'utf8.txt')
        with open(utf8_file, 'w', encoding='utf-8') as f:
            f.write("CODE1\nCODE2\n")
        self.assertEqual(read_codes(utf8_file), ["CODE1", "CODE2"])

        # CP1251
        cp1251_file = os.path.join(self.test_dir, 'cp1251.txt')
        with open(cp1251_file, 'w', encoding='cp1251') as f:
            f.write("КОД1\nКОД2\n")
        self.assertEqual(read_codes(cp1251_file), ["КОД1", "КОД2"])

    def test_perform_aggregation_success(self):
        parent_file = os.path.join(self.test_dir, 'parent.txt')
        with open(parent_file, 'w', encoding='utf-8') as f:
            f.write("PARENT1\nPARENT2\n")

        child_file1 = os.path.join(self.test_dir, 'child1.txt')
        with open(child_file1, 'w', encoding='utf-8') as f:
            f.write("CHILD1\nCHILD2\n")

        child_file2 = os.path.join(self.test_dir, 'child2.txt')
        with open(child_file2, 'w', encoding='utf-8') as f:
            f.write("CHILD3\nCHILD4\n")

        output_dir = os.path.join(self.test_dir, 'output')

        created_count, out_path = perform_aggregation(
            parent_file=parent_file,
            child_files=[child_file1, child_file2],
            items_per_parent=2,
            output_dir=output_dir
        )

        self.assertEqual(created_count, 2)
        self.assertEqual(out_path, output_dir)
        self.assertTrue(os.path.exists(output_dir))

        # Проверка содержимого сформированных файлов
        file1 = os.path.join(output_dir, "PARENT1.txt")
        self.assertTrue(os.path.exists(file1))
        with open(file1, 'r', encoding='utf-8') as f:
            lines = [line.strip() for line in f if line.strip()]
        self.assertEqual(lines, ["PARENT1", "CHILD1", "CHILD2"])

        file2 = os.path.join(output_dir, "PARENT2.txt")
        self.assertTrue(os.path.exists(file2))
        with open(file2, 'r', encoding='utf-8') as f:
            lines = [line.strip() for line in f if line.strip()]
        self.assertEqual(lines, ["PARENT2", "CHILD3", "CHILD4"])

    def test_perform_aggregation_filename_collision(self):
        # Если имена кодов родителей очищаются в одинаковые строки
        parent_file = os.path.join(self.test_dir, 'parent.txt')
        with open(parent_file, 'w', encoding='utf-8') as f:
            f.write("PARENT/1\nPARENT?1\n")

        child_file = os.path.join(self.test_dir, 'child.txt')
        with open(child_file, 'w', encoding='utf-8') as f:
            f.write("CHILD1\nCHILD2\n")

        output_dir = os.path.join(self.test_dir, 'output_collision')

        created_count, _ = perform_aggregation(
            parent_file=parent_file,
            child_files=[child_file],
            items_per_parent=1,
            output_dir=output_dir
        )

        self.assertEqual(created_count, 2)
        self.assertTrue(os.path.exists(os.path.join(output_dir, "PARENT_1.txt")))
        self.assertTrue(os.path.exists(os.path.join(output_dir, "PARENT_1_1.txt")))


if __name__ == '__main__':
    unittest.main()
