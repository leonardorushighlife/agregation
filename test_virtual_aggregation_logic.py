import unittest
import os
import shutil
import tempfile
from unittest.mock import MagicMock
import sys

# Добавляем корневую директорию проекта в sys.path на случай, если тесты запущены в другой директории
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from virtual_aggregation import read_codes, sanitize_filename, perform_aggregation

class TestVirtualAggregationLogic(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_sanitize_filename(self):
        self.assertEqual(sanitize_filename("valid_name"), "valid_name")
        self.assertEqual(sanitize_filename("invalid:char*name?"), "invalid_char_name_")
        self.assertEqual(sanitize_filename("a/b\\c:d*e?f\"g<h>i|j"), "a_b_c_d_e_f_g_h_i_j")

    def test_read_codes_utf8(self):
        filepath = os.path.join(self.test_dir, "utf8.txt")
        # UTF-8 with some Russian characters and blank lines
        content = "Код_1\n\n  Код_2  \nКод_3\n"
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

        codes = read_codes(filepath)
        self.assertEqual(codes, ["Код_1", "Код_2", "Код_3"])

    def test_read_codes_utf16(self):
        filepath = os.path.join(self.test_dir, "utf16.txt")
        content = "Код_А\nКод_Б"
        with open(filepath, "w", encoding="utf-16") as f:
            f.write(content)

        codes = read_codes(filepath)
        self.assertEqual(codes, ["Код_А", "Код_Б"])

    def test_read_codes_cp1251(self):
        filepath = os.path.join(self.test_dir, "cp1251.txt")
        content = "Код_Раз\nКод_Два"
        with open(filepath, "w", encoding="cp1251") as f:
            f.write(content)

        codes = read_codes(filepath)
        self.assertEqual(codes, ["Код_Раз", "Код_Два"])

    def test_perform_aggregation_success(self):
        parent_file = os.path.join(self.test_dir, "parents.txt")
        with open(parent_file, "w", encoding="utf-8") as f:
            f.write("Parent1\nParent2\n")

        child1 = os.path.join(self.test_dir, "child1.txt")
        with open(child1, "w", encoding="utf-8") as f:
            f.write("Child1\nChild2\n")

        child2 = os.path.join(self.test_dir, "child2.txt")
        with open(child2, "w", encoding="utf-8") as f:
            f.write("Child3\nChild4\n")

        # Агрегируем по 2 вложения
        res = perform_aggregation(parent_file, [child1, child2], 2, output_dir_base=self.test_dir)
        self.assertIsNotNone(res)
        out_dir, total_files = res
        self.assertEqual(total_files, 2)

        # Проверим содержимое файлов
        file1 = os.path.join(out_dir, "Parent1.txt")
        file2 = os.path.join(out_dir, "Parent2.txt")
        self.assertTrue(os.path.exists(file1))
        self.assertTrue(os.path.exists(file2))

        with open(file1, "r", encoding="utf-8") as f:
            lines = f.read().splitlines()
        self.assertEqual(lines, ["Parent1", "Child1", "Child2"])

        with open(file2, "r", encoding="utf-8") as f:
            lines = f.read().splitlines()
        self.assertEqual(lines, ["Parent2", "Child3", "Child4"])

    def test_perform_aggregation_collision_handling(self):
        # Если у нас родительские коды отличаются спецсимволами, которые заменяются на одинаковые,
        # должно сработать добавление суффикса.
        parent_file = os.path.join(self.test_dir, "parents.txt")
        with open(parent_file, "w", encoding="utf-8") as f:
            f.write("Parent:One\nParent*One\n")

        child = os.path.join(self.test_dir, "child.txt")
        with open(child, "w", encoding="utf-8") as f:
            f.write("C1\nC2\n")

        res = perform_aggregation(parent_file, [child], 1, output_dir_base=self.test_dir)
        self.assertIsNotNone(res)
        out_dir, total_files = res
        self.assertEqual(total_files, 2)

        file1 = os.path.join(out_dir, "Parent_One.txt")
        file2 = os.path.join(out_dir, "Parent_One_1.txt")
        self.assertTrue(os.path.exists(file1))
        self.assertTrue(os.path.exists(file2))

    def test_perform_aggregation_insufficient_children_accept(self):
        parent_file = os.path.join(self.test_dir, "parents.txt")
        with open(parent_file, "w", encoding="utf-8") as f:
            f.write("P1\nP2\nP3\n")

        child = os.path.join(self.test_dir, "child.txt")
        with open(child, "w", encoding="utf-8") as f:
            f.write("C1\nC2\nC3\nC4\nC5\n") # только 5 дочерних кодов, нужно 6 для 3 полных наборов по 2

        confirm_mock = MagicMock(return_value=True) # соглашаемся на частичную сборку
        res = perform_aggregation(parent_file, [child], 2, output_dir_base=self.test_dir, confirm_callback=confirm_mock)
        self.assertIsNotNone(res)
        out_dir, total_files = res
        self.assertEqual(total_files, 2) # только 2 набора (P1 и P2), так как доступно лишь 5 кодов, а для 3 наборов по 2 нужно 6

        confirm_mock.assert_called_once_with(5, 6)

    def test_perform_aggregation_insufficient_children_cancel(self):
        parent_file = os.path.join(self.test_dir, "parents.txt")
        with open(parent_file, "w", encoding="utf-8") as f:
            f.write("P1\nP2\n")

        child = os.path.join(self.test_dir, "child.txt")
        with open(child, "w", encoding="utf-8") as f:
            f.write("C1\n")

        confirm_mock = MagicMock(return_value=False) # отказываемся от частичной сборки
        res = perform_aggregation(parent_file, [child], 2, output_dir_base=self.test_dir, confirm_callback=confirm_mock)
        self.assertIsNone(res)
        confirm_mock.assert_called_once_with(1, 4)

if __name__ == "__main__":
    unittest.main()
