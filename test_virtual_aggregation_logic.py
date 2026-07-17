import unittest
import os
import shutil
import tempfile
from virtual_aggregation import read_codes, sanitize_filename, perform_aggregation

class TestVirtualAggregationLogic(unittest.TestCase):
    def setUp(self):
        # Создаем временную директорию для тестов
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        # Удаляем временную директорию после тестов
        shutil.rmtree(self.test_dir)
        # Также удаляем созданные папки результатов в текущей директории
        for item in os.listdir('.'):
            if item.startswith('aggregation_results_') and os.path.isdir(item):
                shutil.rmtree(item)

    def test_sanitize_filename(self):
        self.assertEqual(sanitize_filename("valid_name"), "valid_name")
        self.assertEqual(sanitize_filename("invalid/name?"), "invalid_name_")
        self.assertEqual(sanitize_filename("PRN:123*"), "PRN_123_")

    def test_read_codes(self):
        # Создаем тестовый файл в кодировке UTF-8
        path = os.path.join(self.test_dir, "test.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write("code1\ncode2\n\ncode3  \n")

        codes = read_codes(path)
        self.assertEqual(codes, ["code1", "code2", "code3"])

    def test_read_codes_encodings(self):
        # Тестируем чтение в CP1251
        path = os.path.join(self.test_dir, "test_cp1251.txt")
        with open(path, "w", encoding="cp1251") as f:
            f.write("код1\nкод2\n")

        codes = read_codes(path)
        self.assertEqual(codes, ["код1", "код2"])

    def test_perform_aggregation_full(self):
        parents = ["P1", "P2"]
        children = ["C1", "C2", "C3", "C4"]
        count = 2

        output_dir, total = perform_aggregation(parents, children, count)

        self.assertEqual(total, 2)
        self.assertTrue(os.path.exists(output_dir))

        # Проверяем содержимое файлов
        with open(os.path.join(output_dir, "P1.txt"), "r", encoding="utf-8") as f:
            lines = f.read().splitlines()
            self.assertEqual(lines, ["P1", "C1", "C2"])

        with open(os.path.join(output_dir, "P2.txt"), "r", encoding="utf-8") as f:
            lines = f.read().splitlines()
            self.assertEqual(lines, ["P2", "C3", "C4"])

    def test_perform_aggregation_partial_confirm(self):
        parents = ["P1", "P2"]
        children = ["C1", "C2", "C3"]
        count = 2

        # Колбэк для подтверждения (всегда True)
        confirm = lambda a, r, act: True

        output_dir, total = perform_aggregation(parents, children, count, confirm)

        self.assertEqual(total, 1)
        self.assertTrue(os.path.exists(os.path.join(output_dir, "P1.txt")))
        self.assertFalse(os.path.exists(os.path.join(output_dir, "P2.txt")))

    def test_perform_aggregation_partial_reject(self):
        parents = ["P1", "P2"]
        children = ["C1", "C2", "C3"]
        count = 2

        # Колбэк для подтверждения (отказ - False)
        confirm = lambda a, r, act: False

        result = perform_aggregation(parents, children, count, confirm)
        self.assertIsNone(result)

    def test_duplicate_parents(self):
        parents = ["P1", "P1"]
        children = ["C1", "C2", "C3", "C4"]
        count = 2

        output_dir, total = perform_aggregation(parents, children, count)

        self.assertEqual(total, 2)
        self.assertTrue(os.path.exists(os.path.join(output_dir, "P1.txt")))
        self.assertTrue(os.path.exists(os.path.join(output_dir, "P1_1.txt")))

if __name__ == "__main__":
    unittest.main()
