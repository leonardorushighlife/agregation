import os
import unittest
import tempfile
import shutil
from unittest.mock import MagicMock, patch

from virtual_aggregation import (
    sanitize_filename,
    read_codes,
    perform_aggregation
)

class TestVirtualAggregation(unittest.TestCase):
    def setUp(self):
        # Создаем временную директорию для тестов
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        # Удаляем временную директорию после тестов
        shutil.rmtree(self.test_dir)

    def test_sanitize_filename(self):
        # Проверяем замену запрещенных символов
        name = "parent:code/with\\invalid?chars"
        sanitized = sanitize_filename(name)
        self.assertEqual(sanitized, "parent_code_with_invalid_chars")

        # Проверяем, что разрешенные символы не изменяются
        valid_name = "parent-code_123.abc"
        self.assertEqual(sanitize_filename(valid_name), valid_name)

    def test_read_codes_various_encodings(self):
        # Тестируем чтение в разных кодировках (utf-8, utf-16, cp1251)
        test_cases = [
            ("utf-8", "code1\ncode2\ncode3"),
            ("utf-16", "code1\ncode2\ncode3"),
            ("cp1251", "код1\nкод2\nкод3")
        ]

        for enc, content in test_cases:
            filepath = os.path.join(self.test_dir, f"test_{enc}.txt")
            with open(filepath, "w", encoding=enc) as f:
                f.write(content)

            codes = read_codes(filepath)
            self.assertEqual(len(codes), 3)
            if enc == "cp1251":
                self.assertEqual(codes[0], "код1")
            else:
                self.assertEqual(codes[0], "code1")

    def test_read_codes_unicode_error(self):
        # Имитируем ошибку декодирования для всех попыток чтения
        with patch("builtins.open", side_effect=UnicodeError("Симулированная ошибка кодировки")):
            with self.assertRaises(ValueError) as ctx:
                read_codes("fake_path.txt")
            self.assertIn("Не удалось прочитать файл", str(ctx.exception))

    def test_perform_aggregation_success(self):
        parent_codes = ["parent1", "parent2"]
        child_codes = ["child1", "child2", "child3", "child4", "child5"]
        count_per_parent = 2

        output_dir = os.path.join(self.test_dir, "output")

        actual_sets, created_files = perform_aggregation(
            parent_codes=parent_codes,
            child_codes=child_codes,
            count_per_parent=count_per_parent,
            output_dir=output_dir
        )

        self.assertEqual(actual_sets, 2)
        self.assertEqual(len(created_files), 2)

        # Проверяем содержимое созданных файлов
        file1 = os.path.join(output_dir, "parent1.txt")
        self.assertTrue(os.path.exists(file1))
        with open(file1, "r", encoding="utf-8") as f:
            lines = f.read().splitlines()
            self.assertEqual(lines, ["parent1", "child1", "child2"])

        file2 = os.path.join(output_dir, "parent2.txt")
        self.assertTrue(os.path.exists(file2))
        with open(file2, "r", encoding="utf-8") as f:
            lines = f.read().splitlines()
            self.assertEqual(lines, ["parent2", "child3", "child4"])

    def test_perform_aggregation_insufficient_codes_cancel(self):
        parent_codes = ["parent1", "parent2"]
        child_codes = ["child1", "child2"]  # нужно 4, есть 2
        count_per_parent = 2

        output_dir = os.path.join(self.test_dir, "output_cancel")

        # Колбэк отклонения частичной агрегации (пользователь нажал "Нет")
        confirm_callback = MagicMock(return_value=False)

        actual_sets, created_files = perform_aggregation(
            parent_codes=parent_codes,
            child_codes=child_codes,
            count_per_parent=count_per_parent,
            output_dir=output_dir,
            confirm_callback=confirm_callback
        )

        confirm_callback.assert_called_once_with(2, 4)
        self.assertEqual(actual_sets, 0)
        self.assertEqual(len(created_files), 0)

    def test_perform_aggregation_insufficient_codes_confirm(self):
        parent_codes = ["parent1", "parent2"]
        child_codes = ["child1", "child2", "child3"]  # нужно 4, есть 3 (хватит только на 1 полный набор)
        count_per_parent = 2

        output_dir = os.path.join(self.test_dir, "output_confirm")

        # Колбэк согласия на частичную агрегацию (пользователь нажал "Да")
        confirm_callback = MagicMock(return_value=True)

        actual_sets, created_files = perform_aggregation(
            parent_codes=parent_codes,
            child_codes=child_codes,
            count_per_parent=count_per_parent,
            output_dir=output_dir,
            confirm_callback=confirm_callback
        )

        confirm_callback.assert_called_once_with(3, 4)
        self.assertEqual(actual_sets, 1)  # 3 // 2 = 1 набор
        self.assertEqual(len(created_files), 1)

    def test_perform_aggregation_collisions(self):
        # Тестируем коллизии имен при санитаризации (например, "parent/1" и "parent\\1" оба санируются в "parent_1")
        parent_codes = ["parent/1", "parent\\1"]
        child_codes = ["c1", "c2", "c3", "c4"]
        count_per_parent = 2

        output_dir = os.path.join(self.test_dir, "output_collision")

        actual_sets, created_files = perform_aggregation(
            parent_codes=parent_codes,
            child_codes=child_codes,
            count_per_parent=count_per_parent,
            output_dir=output_dir
        )

        self.assertEqual(actual_sets, 2)
        self.assertEqual(len(created_files), 2)

        # Первый должен записаться как parent_1.txt
        file1 = os.path.join(output_dir, "parent_1.txt")
        self.assertTrue(os.path.exists(file1))

        # Второй должен записаться как parent_1_1.txt из-за коллизии
        file2 = os.path.join(output_dir, "parent_1_1.txt")
        self.assertTrue(os.path.exists(file2))

if __name__ == "__main__":
    unittest.main()
