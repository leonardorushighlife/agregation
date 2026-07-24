import unittest
import os
import tempfile
import shutil
from unittest.mock import MagicMock

# Импортируем тестируемые функции
from virtual_aggregation import sanitize_filename, read_codes, perform_aggregation
from virtual_disaggregation import perform_disaggregation

class TestVirtualAggregationLogic(unittest.TestCase):
    def setUp(self):
        # Создаем временную директорию для тестов
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        # Удаляем временную директорию после тестов
        shutil.rmtree(self.test_dir)

    def test_sanitize_filename(self):
        # Проверяем замену недопустимых символов
        dirty = 'p\\a/r:e*n?t"c<o>d|e'
        expected = 'p_a_r_e_n_t_c_o_d_e'
        self.assertEqual(sanitize_filename(dirty), expected)

        # Проверка удаления пробелов по краям
        self.assertEqual(sanitize_filename("  code  "), "code")

    def test_read_codes_encodings(self):
        # Создаем файлы в разных кодировках
        encodings = {
            'utf-8-sig': 'code_utf8_sig_1\ncode_utf8_sig_2',
            'utf-16': 'code_utf16_1\ncode_utf16_2',
            'utf-8': 'code_utf8_1\ncode_utf8_2',
            'windows-1251': 'код_кириллица_1\nкод_кириллица_2'
        }

        for enc, content in encodings.items():
            path = os.path.join(self.test_dir, f"test_{enc}.txt")
            with open(path, 'w', encoding=enc) as f:
                f.write(content)

            codes = read_codes(path)
            self.assertEqual(len(codes), 2)
            if enc == 'windows-1251':
                self.assertEqual(codes[0], 'код_кириллица_1')
            elif 'utf16' in enc:
                self.assertEqual(codes[0], 'code_utf16_1')

    def test_perform_aggregation_success(self):
        # Подготовка входных данных
        parent_file = os.path.join(self.test_dir, "parents.txt")
        with open(parent_file, 'w', encoding='utf-8') as f:
            f.write("parent_1\nparent_2\n")

        child_file_1 = os.path.join(self.test_dir, "children1.txt")
        with open(child_file_1, 'w', encoding='utf-8') as f:
            f.write("child_1_1\nchild_1_2\n")

        child_file_2 = os.path.join(self.test_dir, "children2.txt")
        with open(child_file_2, 'w', encoding='utf-8') as f:
            f.write("child_2_1\nchild_2_2\n")

        # Запуск агрегации по 2 вложения на родителя
        out_dir, count = perform_aggregation(parent_file, [child_file_1, child_file_2], 2)
        self.assertEqual(count, 2)
        self.assertTrue(os.path.exists(out_dir))

        # Проверяем, что созданы файлы
        f1_path = os.path.join(out_dir, "parent_1.txt")
        f2_path = os.path.join(out_dir, "parent_2.txt")
        self.assertTrue(os.path.exists(f1_path))
        self.assertTrue(os.path.exists(f2_path))

        # Проверяем содержимое
        with open(f1_path, 'r', encoding='utf-8') as f:
            lines = f.read().splitlines()
        self.assertEqual(lines, ["parent_1", "child_1_1", "child_1_2"])

        with open(f2_path, 'r', encoding='utf-8') as f:
            lines = f.read().splitlines()
        self.assertEqual(lines, ["parent_2", "child_2_1", "child_2_2"])

    def test_perform_aggregation_collision(self):
        # Тестируем обработку коллизий при совпадении имен родительских кодов
        # Например, родительские коды отличаются только спецсимволами, которые заменяются на '_'
        parent_file = os.path.join(self.test_dir, "parents.txt")
        with open(parent_file, 'w', encoding='utf-8') as f:
            f.write("parent/code\nparent\\code\n")

        child_file = os.path.join(self.test_dir, "children.txt")
        with open(child_file, 'w', encoding='utf-8') as f:
            f.write("c1\nc2\nc3\nc4\n")

        out_dir, count = perform_aggregation(parent_file, [child_file], 2)
        self.assertEqual(count, 2)

        # Должны создаться "parent_code.txt" и "parent_code_1.txt"
        self.assertTrue(os.path.exists(os.path.join(out_dir, "parent_code.txt")))
        self.assertTrue(os.path.exists(os.path.join(out_dir, "parent_code_1.txt")))

    def test_perform_aggregation_not_enough_codes_with_callback_accept(self):
        parent_file = os.path.join(self.test_dir, "parents.txt")
        with open(parent_file, 'w', encoding='utf-8') as f:
            f.write("p1\np2\np3\n")

        child_file = os.path.join(self.test_dir, "children.txt")
        with open(child_file, 'w', encoding='utf-8') as f:
            # 5 кодов, а для 3 родителей по 2 шт требуется 6 кодов
            f.write("c1\nc2\nc3\nc4\nc5\n")

        # Mock-коллбек подтверждения, возвращающий True (продолжить)
        mock_callback = MagicMock(return_value=True)

        out_dir, count = perform_aggregation(parent_file, [child_file], 2, confirm_callback=mock_callback)
        # Должно быть собрано 2 полных набора
        self.assertEqual(count, 2)
        mock_callback.assert_called_once()

    def test_perform_aggregation_not_enough_codes_with_callback_decline(self):
        parent_file = os.path.join(self.test_dir, "parents.txt")
        with open(parent_file, 'w', encoding='utf-8') as f:
            f.write("p1\np2\np3\n")

        child_file = os.path.join(self.test_dir, "children.txt")
        with open(child_file, 'w', encoding='utf-8') as f:
            f.write("c1\nc2\nc3\nc4\nc5\n")

        # Mock-коллбек подтверждения, возвращающий False (отменить)
        mock_callback = MagicMock(return_value=False)

        with self.assertRaises(ValueError) as ctx:
            perform_aggregation(parent_file, [child_file], 2, confirm_callback=mock_callback)
        self.assertIn("Операция отменена пользователем", str(ctx.exception))

    def test_perform_disaggregation_success(self):
        # Создаем папку с файлами наборов
        sets_dir = os.path.join(self.test_dir, "sets")
        os.makedirs(sets_dir, exist_ok=True)

        # Создаем файлы наборов
        with open(os.path.join(sets_dir, "set1.txt"), "w", encoding="utf-8") as f:
            f.write("parent1\nchild1_1\nchild1_2\n")

        with open(os.path.join(sets_dir, "set2.txt"), "w", encoding="utf-8") as f:
            f.write("parent2\nchild2_1\nchild2_2\n")

        parents_file, children_file, file_count = perform_disaggregation(sets_dir)
        self.assertEqual(file_count, 2)

        # Проверяем содержимое parents_consolidated.txt
        parents = read_codes(parents_file)
        self.assertEqual(parents, ["parent1", "parent2"])

        # Проверяем содержимое children_consolidated.txt
        children = read_codes(children_file)
        self.assertEqual(children, ["child1_1", "child1_2", "child2_1", "child2_2"])


if __name__ == "__main__":
    unittest.main()
