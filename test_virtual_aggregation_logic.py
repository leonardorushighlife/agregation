# -*- coding: utf-8 -*-
import unittest
import os
import shutil
import tempfile
from unittest.mock import MagicMock
from virtual_aggregation import read_codes, sanitize_filename, get_unique_filepath, perform_aggregation

class TestVirtualAggregationLogic(unittest.TestCase):
    def setUp(self):
        # Создаем временную директорию для тестовых файлов
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        # Удаляем временную директорию после тестов
        shutil.rmtree(self.test_dir)

    def test_read_codes_encodings(self):
        # Проверяем поддержку различных кодировок
        test_cases = [
            ("utf-8-sig", ["Код1", "Код2"]),
            ("utf-16", ["Код3", "Код4"]),
            ("utf-8", ["Код5", "Код6"]),
            ("cp1251", ["Код7", "Код8"])
        ]

        for enc, codes in test_cases:
            file_path = os.path.join(self.test_dir, f"test_{enc}.txt")
            # Записываем с нужной кодировкой
            with open(file_path, 'w', encoding=enc) as f:
                f.write("\n".join(codes) + "\n")

            # Читаем и сверяем результат
            read_result = read_codes(file_path)
            self.assertEqual(read_result, codes, f"Ошибка при чтении кодировки {enc}")

    def test_sanitize_filename(self):
        self.assertEqual(sanitize_filename("parent/code:123"), "parent_code_123")
        self.assertEqual(sanitize_filename("abc?*|"), "abc___")
        self.assertEqual(sanitize_filename("   "), "unnamed_parent")

    def test_get_unique_filepath(self):
        sanitized = "test_parent"
        path1 = get_unique_filepath(self.test_dir, sanitized)
        self.assertEqual(os.path.basename(path1), "test_parent.txt")

        # Создаем файл
        with open(path1, 'w') as f:
            f.write("test")

        path2 = get_unique_filepath(self.test_dir, sanitized)
        self.assertEqual(os.path.basename(path2), "test_parent_1.txt")

    def test_perform_aggregation_success(self):
        # Подготовка файлов
        parent_file = os.path.join(self.test_dir, "parents.txt")
        with open(parent_file, 'w', encoding='utf-8') as f:
            f.write("Parent1\nParent2\n")

        child_file1 = os.path.join(self.test_dir, "children1.txt")
        with open(child_file1, 'w', encoding='utf-8') as f:
            f.write("Child1\nChild2\n")

        child_file2 = os.path.join(self.test_dir, "children2.txt")
        with open(child_file2, 'w', encoding='utf-8') as f:
            f.write("Child3\nChild4\n")

        # Агрегируем по 2 вложения
        output_dir, created = perform_aggregation(
            parent_file,
            [child_file1, child_file2],
            2,
            output_dir_base=self.test_dir
        )

        self.assertIsNotNone(output_dir)
        self.assertEqual(len(created), 2)

        # Проверяем содержимое созданных файлов
        file1 = os.path.join(output_dir, "Parent1.txt")
        file2 = os.path.join(output_dir, "Parent2.txt")

        self.assertTrue(os.path.exists(file1))
        self.assertTrue(os.path.exists(file2))

        with open(file1, 'r', encoding='utf-8') as f:
            content1 = f.read().splitlines()
        self.assertEqual(content1, ["Parent1", "Child1", "Child2"])

        with open(file2, 'r', encoding='utf-8') as f:
            content2 = f.read().splitlines()
        self.assertEqual(content2, ["Parent2", "Child3", "Child4"])

    def test_perform_aggregation_partial_confirm(self):
        # Подготовка файлов, когда детей не хватает для всех родителей
        parent_file = os.path.join(self.test_dir, "parents.txt")
        with open(parent_file, 'w', encoding='utf-8') as f:
            f.write("Parent1\nParent2\n")

        child_file = os.path.join(self.test_dir, "children.txt")
        with open(child_file, 'w', encoding='utf-8') as f:
            f.write("Child1\nChild2\nChild3\n") # только 3 дочерних кода, а надо 4

        # Если коллбэк возвращает True, продолжаем
        confirm_mock = MagicMock(return_value=True)
        output_dir, created = perform_aggregation(
            parent_file,
            [child_file],
            2,
            output_dir_base=self.test_dir,
            confirm_callback=confirm_mock
        )

        self.assertIsNotNone(output_dir)
        self.assertEqual(len(created), 1) # Только 1 полный набор собран
        confirm_mock.assert_called_once()

    def test_perform_aggregation_partial_cancel(self):
        parent_file = os.path.join(self.test_dir, "parents.txt")
        with open(parent_file, 'w', encoding='utf-8') as f:
            f.write("Parent1\nParent2\n")

        child_file = os.path.join(self.test_dir, "children.txt")
        with open(child_file, 'w', encoding='utf-8') as f:
            f.write("Child1\nChild2\nChild3\n")

        # Если коллбэк возвращает False, отменяем
        confirm_mock = MagicMock(return_value=False)
        res, msg = perform_aggregation(
            parent_file,
            [child_file],
            2,
            output_dir_base=self.test_dir,
            confirm_callback=confirm_mock
        )

        self.assertIsNone(res)
        self.assertEqual(msg, "Агрегация отменена пользователем.")
        confirm_mock.assert_called_once()

if __name__ == '__main__':
    unittest.main()
