import unittest
import os
import shutil
import tempfile
from unittest.mock import MagicMock

# Импортируем тестируемые функции
from virtual_aggregation import sanitize_filename, read_codes, perform_aggregation


class TestVirtualAggregation(unittest.TestCase):
    def setUp(self):
        # Создаем временную директорию для тестов
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        # Удаляем временную директорию после тестов
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_sanitize_filename(self):
        # Тестируем замену запрещенных символов в ОС Windows
        self.assertEqual(sanitize_filename("valid_name_123"), "valid_name_123")
        self.assertEqual(sanitize_filename("invalid:name/with\\chars?"), "invalid_name_with_chars_")
        self.assertEqual(sanitize_filename(""), "empty_code")
        self.assertEqual(sanitize_filename(None), "empty_code")
        # Ограничение по длине до 120 символов
        long_name = "a" * 150
        self.assertEqual(len(sanitize_filename(long_name)), 120)

    def test_read_codes_multi_encoding(self):
        # Создаем тестовые файлы с различными кодировками
        test_codes = ["code1", "code2", "code3"]

        # 1. UTF-8
        utf8_path = os.path.join(self.test_dir, "codes_utf8.txt")
        with open(utf8_path, "w", encoding="utf-8") as f:
            f.write("\n".join(test_codes))

        # 2. UTF-8 with BOM
        utf8_bom_path = os.path.join(self.test_dir, "codes_utf8_bom.txt")
        with open(utf8_bom_path, "w", encoding="utf-8-sig") as f:
            f.write("\n".join(test_codes))

        # 3. CP1251 (русский текст)
        test_codes_ru = ["код1", "код2", "код3"]
        cp1251_path = os.path.join(self.test_dir, "codes_cp1251.txt")
        with open(cp1251_path, "w", encoding="cp1251") as f:
            f.write("\n".join(test_codes_ru))

        # 4. UTF-16
        utf16_path = os.path.join(self.test_dir, "codes_utf16.txt")
        with open(utf16_path, "w", encoding="utf-16") as f:
            f.write("\n".join(test_codes))

        # Проверяем успешное чтение
        self.assertEqual(read_codes(utf8_path), test_codes)
        self.assertEqual(read_codes(utf8_bom_path), test_codes)
        self.assertEqual(read_codes(cp1251_path), test_codes_ru)
        self.assertEqual(read_codes(utf16_path), test_codes)

    def test_perform_aggregation_success(self):
        # Создаем файлы
        parents = ["parent1", "parent2"]
        children = ["child1", "child2", "child3", "child4", "child5", "child6", "child7", "child8"]

        parent_file = os.path.join(self.test_dir, "parents.txt")
        with open(parent_file, "w", encoding="utf-8") as f:
            f.write("\n".join(parents))

        child_file = os.path.join(self.test_dir, "children.txt")
        with open(child_file, "w", encoding="utf-8") as f:
            f.write("\n".join(children))

        # Запускаем агрегацию (количество вложений = 4)
        confirm_mock = MagicMock(return_value=True)
        info_mock = MagicMock()
        error_mock = MagicMock()

        res = perform_aggregation(
            parent_file=parent_file,
            child_files=[child_file],
            count_per_parent=4,
            confirm_callback=confirm_mock,
            info_callback=info_mock,
            error_callback=error_mock
        )

        self.assertTrue(res)
        error_mock.assert_not_called()
        info_mock.assert_called_once()

        # Находим созданную папку
        subdirs = [d for d in os.listdir(self.test_dir) if d.startswith("aggregation_results_")]
        self.assertEqual(len(subdirs), 1)
        out_dir = os.path.join(self.test_dir, subdirs[0])

        # Проверяем содержимое созданных файлов
        parent1_file = os.path.join(out_dir, "parent1.txt")
        parent2_file = os.path.join(out_dir, "parent2.txt")

        self.assertTrue(os.path.exists(parent1_file))
        self.assertTrue(os.path.exists(parent2_file))

        # Проверяем, что в первом файле родительский код parent1 и первые 4 вложения
        p1_content = read_codes(parent1_file)
        self.assertEqual(p1_content, ["parent1", "child1", "child2", "child3", "child4"])

        # Проверяем, что во втором файле родительский код parent2 и следующие 4 вложения
        p2_content = read_codes(parent2_file)
        self.assertEqual(p2_content, ["parent2", "child5", "child6", "child7", "child8"])

    def test_perform_aggregation_insufficient_children(self):
        parents = ["parent1", "parent2"]
        # Только 6 вложений, а нужно 2 * 4 = 8
        children = ["child1", "child2", "child3", "child4", "child5", "child6"]

        parent_file = os.path.join(self.test_dir, "parents.txt")
        with open(parent_file, "w", encoding="utf-8") as f:
            f.write("\n".join(parents))

        child_file = os.path.join(self.test_dir, "children.txt")
        with open(child_file, "w", encoding="utf-8") as f:
            f.write("\n".join(children))

        confirm_mock = MagicMock(return_value=True) # Пользователь подтверждает продолжение
        info_mock = MagicMock()
        error_mock = MagicMock()

        res = perform_aggregation(
            parent_file=parent_file,
            child_files=[child_file],
            count_per_parent=4,
            confirm_callback=confirm_mock,
            info_callback=info_mock,
            error_callback=error_mock
        )

        self.assertTrue(res)
        confirm_mock.assert_called_once() # Должно запросить подтверждение

        # Находим созданную папку
        subdirs = [d for d in os.listdir(self.test_dir) if d.startswith("aggregation_results_")]
        self.assertEqual(len(subdirs), 1)
        out_dir = os.path.join(self.test_dir, subdirs[0])

        # Должен быть создан только один файл набора (parent1.txt), т.к. на второй не хватает вложений
        self.assertTrue(os.path.exists(os.path.join(out_dir, "parent1.txt")))
        self.assertFalse(os.path.exists(os.path.join(out_dir, "parent2.txt")))

    def test_perform_aggregation_collision_handling(self):
        # Случай, когда родительские коды дают одинаковое имя файла при очистке (например "parent:1" и "parent/1" -> "parent_1.txt")
        parents = ["parent:1", "parent/1"]
        children = ["child1", "child2", "child3", "child4", "child5", "child6", "child7", "child8"]

        parent_file = os.path.join(self.test_dir, "parents.txt")
        with open(parent_file, "w", encoding="utf-8") as f:
            f.write("\n".join(parents))

        child_file = os.path.join(self.test_dir, "children.txt")
        with open(child_file, "w", encoding="utf-8") as f:
            f.write("\n".join(children))

        res = perform_aggregation(
            parent_file=parent_file,
            child_files=[child_file],
            count_per_parent=4,
            confirm_callback=MagicMock(return_value=True),
            info_callback=MagicMock(),
            error_callback=MagicMock()
        )

        self.assertTrue(res)

        subdirs = [d for d in os.listdir(self.test_dir) if d.startswith("aggregation_results_")]
        out_dir = os.path.join(self.test_dir, subdirs[0])

        # Должны быть созданы два файла: parent_1.txt и parent_1_1.txt
        file1 = os.path.join(out_dir, "parent_1.txt")
        file2 = os.path.join(out_dir, "parent_1_1.txt")

        self.assertTrue(os.path.exists(file1))
        self.assertTrue(os.path.exists(file2))

        p1_content = read_codes(file1)
        p2_content = read_codes(file2)

        self.assertEqual(p1_content, ["parent:1", "child1", "child2", "child3", "child4"])
        self.assertEqual(p2_content, ["parent/1", "child5", "child6", "child7", "child8"])


if __name__ == "__main__":
    unittest.main()
