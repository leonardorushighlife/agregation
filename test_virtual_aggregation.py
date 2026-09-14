import os
import shutil
import tempfile
import unittest

from virtual_aggregation import sanitize_filename, read_codes, perform_aggregation


class TestVirtualAggregation(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_sanitize_filename(self):
        self.assertEqual(sanitize_filename("SET/123:45?*"), "SET_123_45__")
        self.assertEqual(sanitize_filename("  clean_code  "), "clean_code")
        self.assertEqual(sanitize_filename(""), "set_output")

    def test_read_codes(self):
        file_path = os.path.join(self.test_dir, "codes.txt")
        content = "CODE1\n\n  CODE2  \nCODE3\n"
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)

        codes = read_codes(file_path)
        self.assertEqual(codes, ["CODE1", "CODE2", "CODE3"])

    def test_perform_aggregation_success(self):
        # Родительский файл с 2 наборами
        parent_file = os.path.join(self.test_dir, "parent.txt")
        with open(parent_file, "w", encoding="utf-8") as f:
            f.write("SET_001\nSET_002\n")

        # 3 детских файла
        child1 = os.path.join(self.test_dir, "child1.txt")
        with open(child1, "w", encoding="utf-8") as f:
            f.write("ITEM_1\nITEM_2\n")

        child2 = os.path.join(self.test_dir, "child2.txt")
        with open(child2, "w", encoding="utf-8") as f:
            f.write("ITEM_3\nITEM_4\n")

        child3 = os.path.join(self.test_dir, "child3.txt")
        with open(child3, "w", encoding="utf-8") as f:
            f.write("ITEM_5\nITEM_6\n")

        output_dir = os.path.join(self.test_dir, "results")
        out_dir, created, used_child = perform_aggregation(
            parent_file=parent_file,
            child_files=[child1, child2, child3],
            items_per_set=3,
            output_dir=output_dir
        )

        self.assertEqual(created, 2)
        self.assertEqual(used_child, 6)
        self.assertTrue(os.path.exists(output_dir))

        # Проверяем содержимое первого файла
        set1_path = os.path.join(output_dir, "SET_001.txt")
        self.assertTrue(os.path.exists(set1_path))
        with open(set1_path, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f.readlines() if line.strip()]

        self.assertEqual(lines, ["SET_001", "ITEM_1", "ITEM_2", "ITEM_3"])

        # Проверяем содержимое второго файла
        set2_path = os.path.join(output_dir, "SET_002.txt")
        self.assertTrue(os.path.exists(set2_path))
        with open(set2_path, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f.readlines() if line.strip()]

        self.assertEqual(lines, ["SET_002", "ITEM_4", "ITEM_5", "ITEM_6"])

    def test_perform_aggregation_insufficient_children(self):
        # 2 родительских кода
        parent_file = os.path.join(self.test_dir, "parent.txt")
        with open(parent_file, "w", encoding="utf-8") as f:
            f.write("SET_001\nSET_002\n")

        # 4 вложения (недостаточно для 2 наборов по 3 вложения)
        child1 = os.path.join(self.test_dir, "child1.txt")
        with open(child1, "w", encoding="utf-8") as f:
            f.write("ITEM_1\nITEM_2\nITEM_3\nITEM_4\n")

        output_dir = os.path.join(self.test_dir, "results_partial")
        out_dir, created, used_child = perform_aggregation(
            parent_file=parent_file,
            child_files=[child1],
            items_per_set=3,
            output_dir=output_dir
        )

        # Должен создаться только 1 набор
        self.assertEqual(created, 1)
        self.assertEqual(used_child, 3)


if __name__ == "__main__":
    unittest.main()
