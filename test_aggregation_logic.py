import os
import shutil
import unittest
from virtual_aggregation import read_codes, perform_aggregation, sanitize_filename

class TestAggregationLogic(unittest.TestCase):
    def setUp(self):
        # Создаем временные файлы для тестов
        self.test_dir = "test_files"
        if not os.path.exists(self.test_dir):
            os.makedirs(self.test_dir)

        self.parent_file = os.path.join(self.test_dir, "parents.txt")
        with open(self.parent_file, 'w', encoding='utf-8') as f:
            f.write("PARENT001\nPARENT002\nPARENT003\n")

        self.child_file1 = os.path.join(self.test_dir, "children1.txt")
        with open(self.child_file1, 'w', encoding='utf-8') as f:
            f.write("CHILD001\nCHILD002\n")

        self.child_file2 = os.path.join(self.test_dir, "children2.txt")
        with open(self.child_file2, 'w', encoding='utf-8') as f:
            f.write("CHILD003\nCHILD004\nCHILD005\nCHILD006\n")

        self.output_dir = "test_results"

    def tearDown(self):
        # Удаляем временные файлы и папки
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
        if os.path.exists(self.output_dir):
            shutil.rmtree(self.output_dir)

    def test_read_codes_single(self):
        codes = read_codes(self.parent_file)
        self.assertEqual(len(codes), 3)
        self.assertEqual(codes[0], "PARENT001")

    def test_read_codes_multiple(self):
        codes = read_codes([self.child_file1, self.child_file2])
        self.assertEqual(len(codes), 6)
        self.assertEqual(codes[0], "CHILD001")
        self.assertEqual(codes[5], "CHILD006")

    def test_sanitize_filename(self):
        self.assertEqual(sanitize_filename("valid_name"), "valid_name")
        self.assertEqual(sanitize_filename("invalid/name?"), "invalid_name_")

    def test_perform_aggregation_success(self):
        parents = ["P1", "P2"]
        children = ["C1", "C2", "C3", "C4"]
        count = 2

        processed = perform_aggregation(parents, children, count, self.output_dir)

        self.assertEqual(processed, 2)
        self.assertTrue(os.path.exists(os.path.join(self.output_dir, "P1.txt")))
        self.assertTrue(os.path.exists(os.path.join(self.output_dir, "P2.txt")))

        with open(os.path.join(self.output_dir, "P1.txt"), 'r') as f:
            lines = f.read().splitlines()
            self.assertEqual(lines, ["P1", "C1", "C2"])

    def test_perform_aggregation_insufficient_children(self):
        parents = ["P1", "P2"]
        children = ["C1", "C2", "C3"]
        count = 2

        # Будет обработан только 1 набор (3 // 2 = 1)
        processed = perform_aggregation(parents, children, count, self.output_dir)

        self.assertEqual(processed, 1)
        self.assertTrue(os.path.exists(os.path.join(self.output_dir, "P1.txt")))
        self.assertFalse(os.path.exists(os.path.join(self.output_dir, "P2.txt")))

if __name__ == "__main__":
    unittest.main()
