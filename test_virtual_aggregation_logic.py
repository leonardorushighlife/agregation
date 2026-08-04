import unittest
import os
import tempfile
import shutil
from unittest.mock import patch, MagicMock

# Импортируем тестируемые функции
from virtual_aggregation import read_codes, sanitize_filename, perform_aggregation

class TestVirtualAggregationLogic(unittest.TestCase):
    def setUp(self):
        # Создаем временную директорию для тестов
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        # Удаляем временную директорию после каждого теста
        shutil.rmtree(self.test_dir)

    def test_sanitize_filename(self):
        self.assertEqual(sanitize_filename("parent/code:1"), "parent_code_1")
        self.assertEqual(sanitize_filename("abc\\def*ghi?jkl|mno"), "abc_def_ghi_jkl_mno")
        self.assertEqual(sanitize_filename("clean_code"), "clean_code")

    def test_read_codes_various_encodings(self):
        # Создаем файлы в разных кодировках
        encodings = ["utf-8", "utf-16", "cp1251"]
        content = "code1\ncode2\ncode3\n"

        for enc in encodings:
            filepath = os.path.join(self.test_dir, f"test_{enc}.txt")
            with open(filepath, "w", encoding=enc) as f:
                f.write(content)

            codes = read_codes(filepath)
            self.assertEqual(codes, ["code1", "code2", "code3"])

    def test_read_codes_unicode_error_handling(self):
        # Патчим builtins.open так, чтобы он всегда вызывал UnicodeError при попытке прочесть файл
        with patch("builtins.open", side_effect=UnicodeError("Failed to decode")):
            filepath = os.path.join(self.test_dir, "nonexistent.txt")
            with self.assertRaises(ValueError):
                read_codes(filepath)

    def test_perform_aggregation_success(self):
        # Подготовка данных
        parent_filepath = os.path.join(self.test_dir, "parents.txt")
        with open(parent_filepath, "w", encoding="utf-8") as f:
            f.write("parent1\nparent2\n")

        child1_filepath = os.path.join(self.test_dir, "children1.txt")
        with open(child1_filepath, "w", encoding="utf-8") as f:
            f.write("child1\nchild2\nchild3\n")

        child2_filepath = os.path.join(self.test_dir, "children2.txt")
        with open(child2_filepath, "w", encoding="utf-8") as f:
            f.write("child4\nchild5\nchild6\nchild7\nchild8\n")

        # Нам нужно 4 вложения на родителя.
        # Всего у нас 2 родителя и 8 детей (3 + 5). 2 * 4 = 8.
        target_dir, created_files = perform_aggregation(
            parent_file=parent_filepath,
            child_files=[child1_filepath, child2_filepath],
            count_per_parent=4,
            output_dir=self.test_dir
        )

        self.assertEqual(len(created_files), 2)

        # Проверим первый созданный файл
        p1_file = os.path.join(target_dir, "parent1.txt")
        self.assertTrue(os.path.exists(p1_file))
        p1_codes = read_codes(p1_file)
        self.assertEqual(p1_codes, ["parent1", "child1", "child2", "child3", "child4"])

        # Проверим второй созданный файл
        p2_file = os.path.join(target_dir, "parent2.txt")
        self.assertTrue(os.path.exists(p2_file))
        p2_codes = read_codes(p2_file)
        self.assertEqual(p2_codes, ["parent2", "child5", "child6", "child7", "child8"])

    def test_perform_aggregation_insufficient_children_confirm_yes(self):
        parent_filepath = os.path.join(self.test_dir, "parents.txt")
        with open(parent_filepath, "w", encoding="utf-8") as f:
            f.write("parent1\nparent2\n")

        child_filepath = os.path.join(self.test_dir, "children.txt")
        with open(child_filepath, "w", encoding="utf-8") as f:
            # Всего 6 детей, требуется 8 для двух родителей по 4 вложения
            f.write("child1\nchild2\nchild3\nchild4\nchild5\nchild6\n")

        confirm_mock = MagicMock(return_value=True)

        target_dir, created_files = perform_aggregation(
            parent_file=parent_filepath,
            child_files=[child_filepath],
            count_per_parent=4,
            confirm_callback=confirm_mock,
            output_dir=self.test_dir
        )

        confirm_mock.assert_called_once_with(6, 8)
        # Так как детей 6, а нужно по 4 на каждый родитель, реальное количество наборов составит 6 // 4 = 1.
        self.assertEqual(len(created_files), 1)
        self.assertTrue(os.path.exists(os.path.join(target_dir, "parent1.txt")))
        self.assertFalse(os.path.exists(os.path.join(target_dir, "parent2.txt")))

    def test_perform_aggregation_insufficient_children_confirm_no(self):
        parent_filepath = os.path.join(self.test_dir, "parents.txt")
        with open(parent_filepath, "w", encoding="utf-8") as f:
            f.write("parent1\nparent2\n")

        child_filepath = os.path.join(self.test_dir, "children.txt")
        with open(child_filepath, "w", encoding="utf-8") as f:
            f.write("child1\nchild2\n")

        confirm_mock = MagicMock(return_value=False)

        result = perform_aggregation(
            parent_file=parent_filepath,
            child_files=[child_filepath],
            count_per_parent=4,
            confirm_callback=confirm_mock,
            output_dir=self.test_dir
        )

        confirm_mock.assert_called_once_with(2, 8)
        self.assertIsNone(result)

    def test_perform_aggregation_filename_collision(self):
        # Файл с повторяющимися очищенными родительскими кодами
        parent_filepath = os.path.join(self.test_dir, "parents.txt")
        with open(parent_filepath, "w", encoding="utf-8") as f:
            # Два кода, которые очистятся в одинаковые имена файлов: parent/1 и parent\\1
            f.write("parent/1\nparent\\1\n")

        child_filepath = os.path.join(self.test_dir, "children.txt")
        with open(child_filepath, "w", encoding="utf-8") as f:
            f.write("child1\nchild2\nchild3\nchild4\nchild5\nchild6\nchild7\nchild8\n")

        target_dir, created_files = perform_aggregation(
            parent_file=parent_filepath,
            child_files=[child_filepath],
            count_per_parent=4,
            output_dir=self.test_dir
        )

        self.assertEqual(len(created_files), 2)
        self.assertTrue(os.path.exists(os.path.join(target_dir, "parent_1.txt")))
        self.assertTrue(os.path.exists(os.path.join(target_dir, "parent_1_1.txt")))


if __name__ == "__main__":
    unittest.main()
