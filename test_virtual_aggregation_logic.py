import unittest
import os
import shutil
import tempfile
from unittest.mock import patch, MagicMock

from virtual_aggregation import sanitize_filename, read_codes, perform_aggregation


class TestVirtualAggregationLogic(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_sanitize_filename(self):
        self.assertEqual(sanitize_filename("valid_name"), "valid_name")
        self.assertEqual(sanitize_filename("code/with:invalid*chars?"), "code_with_invalid_chars_")
        self.assertEqual(sanitize_filename("  "), "unnamed")
        self.assertEqual(sanitize_filename(None), "unnamed")

    def test_read_codes_utf8(self):
        file_path = os.path.join(self.test_dir, "codes.txt")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("CODE1\nCODE2\n\nCODE3\n")

        codes = read_codes(file_path)
        self.assertEqual(codes, ["CODE1", "CODE2", "CODE3"])

    def test_read_codes_cp1251(self):
        file_path = os.path.join(self.test_dir, "codes_cp1251.txt")
        with open(file_path, "w", encoding="cp1251") as f:
            f.write("КОД1\nКОД2\n")

        codes = read_codes(file_path)
        self.assertEqual(codes, ["КОД1", "КОД2"])

    def test_perform_aggregation_success(self):
        parent_path = os.path.join(self.test_dir, "parents.txt")
        with open(parent_path, "w", encoding="utf-8") as f:
            f.write("SET001\nSET002\n")

        child1_path = os.path.join(self.test_dir, "children1.txt")
        with open(child1_path, "w", encoding="utf-8") as f:
            f.write("ITEM1\nITEM2\n")

        child2_path = os.path.join(self.test_dir, "children2.txt")
        with open(child2_path, "w", encoding="utf-8") as f:
            f.write("ITEM3\nITEM4\n")

        out_dir, created_count = perform_aggregation(parent_path, [child1_path, child2_path], 2)
        self.assertEqual(created_count, 2)
        self.assertTrue(os.path.exists(out_dir))

        f1_path = os.path.join(out_dir, "SET001.txt")
        self.assertTrue(os.path.exists(f1_path))
        with open(f1_path, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f]
        self.assertEqual(lines, ["SET001", "ITEM1", "ITEM2"])

        f2_path = os.path.join(out_dir, "SET002.txt")
        self.assertTrue(os.path.exists(f2_path))
        with open(f2_path, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f]
        self.assertEqual(lines, ["SET002", "ITEM3", "ITEM4"])

        # Удаляем созданный результатом агрегации каталог
        shutil.rmtree(out_dir, ignore_errors=True)

    def test_perform_aggregation_filename_collision(self):
        parent_path = os.path.join(self.test_dir, "parents.txt")
        with open(parent_path, "w", encoding="utf-8") as f:
            f.write("SET:001\nSET*001\n")  # Оба заменятся на SET_001

        child_path = os.path.join(self.test_dir, "children.txt")
        with open(child_path, "w", encoding="utf-8") as f:
            f.write("ITEM1\nITEM2\n")

        out_dir, created_count = perform_aggregation(parent_path, [child_path], 1)
        self.assertEqual(created_count, 2)

        self.assertTrue(os.path.exists(os.path.join(out_dir, "SET_001.txt")))
        self.assertTrue(os.path.exists(os.path.join(out_dir, "SET_001_1.txt")))

        shutil.rmtree(out_dir, ignore_errors=True)

    def test_perform_aggregation_partial_confirmation(self):
        parent_path = os.path.join(self.test_dir, "parents.txt")
        with open(parent_path, "w", encoding="utf-8") as f:
            f.write("SET001\nSET002\n")

        child_path = os.path.join(self.test_dir, "children.txt")
        with open(child_path, "w", encoding="utf-8") as f:
            f.write("ITEM1\nITEM2\n")  # Только на 1 набор по 2 шт.

        # Случай 1: Пользователь отказался
        confirm_false = MagicMock(return_value=False)
        out_dir, count = perform_aggregation(parent_path, [child_path], 2, confirm_callback=confirm_false)
        self.assertEqual(count, 0)
        self.assertIsNone(out_dir)

        # Случай 2: Пользователь согласился
        confirm_true = MagicMock(return_value=True)
        out_dir, count = perform_aggregation(parent_path, [child_path], 2, confirm_callback=confirm_true)
        self.assertEqual(count, 1)
        shutil.rmtree(out_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
