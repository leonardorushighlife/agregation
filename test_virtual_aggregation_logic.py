import os
import unittest
import tempfile
import shutil
from virtual_aggregation import read_codes, sanitize_filename, perform_aggregation

class TestVirtualAggregationLogic(unittest.TestCase):
    def setUp(self):
        # Создаем временную директорию для тестов
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        # Удаляем временную директорию после выполнения тестов
        shutil.rmtree(self.test_dir)

    def test_read_codes_encodings(self):
        # 1. Проверяем чтение UTF-8 без BOM
        utf8_path = os.path.join(self.test_dir, "utf8.txt")
        with open(utf8_path, "w", encoding="utf-8") as f:
            f.write("code1\ncode2\n\ncode3\n")
        self.assertEqual(read_codes(utf8_path), ["code1", "code2", "code3"])

        # 2. Проверяем чтение UTF-8-SIG (с BOM)
        utf8sig_path = os.path.join(self.test_dir, "utf8sig.txt")
        with open(utf8sig_path, "w", encoding="utf-8-sig") as f:
            f.write("sig1\nsig2\n")
        self.assertEqual(read_codes(utf8sig_path), ["sig1", "sig2"])

        # 3. Проверяем чтение UTF-16
        utf16_path = os.path.join(self.test_dir, "utf16.txt")
        with open(utf16_path, "w", encoding="utf-16") as f:
            f.write("u16_1\nu16_2\n")
        self.assertEqual(read_codes(utf16_path), ["u16_1", "u16_2"])

        # 4. Проверяем чтение CP1251 (Windows-1251)
        cp1251_path = os.path.join(self.test_dir, "cp1251.txt")
        with open(cp1251_path, "w", encoding="windows-1251") as f:
            f.write("кириллица1\nкириллица2\n")
        self.assertEqual(read_codes(cp1251_path), ["кириллица1", "кириллица2"])

    def test_sanitize_filename(self):
        # Проверяем замену недопустимых символов
        dirty = "parent\\code/with:invalid*chars?and\"quotes<more>or|pipes"
        expected = "parent_code_with_invalid_chars_and_quotes_more_or_pipes"
        self.assertEqual(sanitize_filename(dirty), expected)

    def test_collision_handling(self):
        # Создаем файлы для теста коллизий
        p_path = os.path.join(self.test_dir, "parents.txt")
        with open(p_path, "w", encoding="utf-8") as f:
            # Два одинаковых родительских кода вызовут потенциальную коллизию имен файлов
            f.write("collision_code\ncollision_code\n")

        c_path = os.path.join(self.test_dir, "children.txt")
        with open(c_path, "w", encoding="utf-8") as f:
            f.write("\n".join([f"child_{i}" for i in range(10)]) + "\n")

        out_subdir = os.path.join(self.test_dir, "out_collision")
        count, out_dir = perform_aggregation(
            parent_file=p_path,
            child_files=[c_path],
            count_per_parent=3,
            output_dir=out_subdir
        )

        self.assertEqual(count, 2)
        # Ожидаем файлы: collision_code.txt и collision_code_1.txt
        expected_file1 = os.path.join(out_subdir, "collision_code.txt")
        expected_file2 = os.path.join(out_subdir, "collision_code_1.txt")

        self.assertTrue(os.path.exists(expected_file1))
        self.assertTrue(os.path.exists(expected_file2))

        # Проверим содержимое файлов
        with open(expected_file1, "r", encoding="utf-8") as f:
            content1 = f.read().splitlines()
        self.assertEqual(content1, ["collision_code", "child_0", "child_1", "child_2"])

        with open(expected_file2, "r", encoding="utf-8") as f:
            content2 = f.read().splitlines()
        self.assertEqual(content2, ["collision_code", "child_3", "child_4", "child_5"])

    def test_partial_aggregation_with_callback(self):
        # Проверяем поведение при нехватке кодов вложений
        p_path = os.path.join(self.test_dir, "parents.txt")
        with open(p_path, "w", encoding="utf-8") as f:
            # Нам нужно 3 набора
            f.write("p1\np2\np3\n")

        c_path = os.path.join(self.test_dir, "children.txt")
        with open(c_path, "w", encoding="utf-8") as f:
            # Всего 6 кодов вложений. При 4 вложениях на набор сможем собрать только 1 полный набор (6 // 4 = 1)
            f.write("\n".join([f"child_{i}" for i in range(6)]) + "\n")

        out_subdir = os.path.join(self.test_dir, "out_partial")

        # Наш коллбек подтверждения
        callback_called = []
        def mock_confirm_callback(available, required, actual):
            callback_called.append((available, required, actual))
            return True # Соглашаемся на частичный результат

        count, out_dir = perform_aggregation(
            parent_file=p_path,
            child_files=[c_path],
            count_per_parent=4,
            output_dir=out_subdir,
            confirm_callback=mock_confirm_callback
        )

        self.assertEqual(count, 1)
        self.assertEqual(callback_called, [(6, 12, 1)])

        # Ожидаем только один файл p1.txt
        p1_path = os.path.join(out_subdir, "p1.txt")
        p2_path = os.path.join(out_subdir, "p2.txt")
        self.assertTrue(os.path.exists(p1_path))
        self.assertFalse(os.path.exists(p2_path))

        with open(p1_path, "r", encoding="utf-8") as f:
            content = f.read().splitlines()
        self.assertEqual(content, ["p1", "child_0", "child_1", "child_2", "child_3"])

    def test_insufficient_codes_error(self):
        # Проверяем выброс исключения, если нельзя собрать ни одного набора
        p_path = os.path.join(self.test_dir, "parents.txt")
        with open(p_path, "w", encoding="utf-8") as f:
            f.write("p1\n")

        c_path = os.path.join(self.test_dir, "children.txt")
        with open(c_path, "w", encoding="utf-8") as f:
            # Всего 2 вложения, а требуется 3
            f.write("child_1\nchild_2\n")

        out_subdir = os.path.join(self.test_dir, "out_fail")
        with self.assertRaises(ValueError) as context:
            perform_aggregation(
                parent_file=p_path,
                child_files=[c_path],
                count_per_parent=3,
                output_dir=out_subdir
            )
        self.assertIn("Недостаточно кодов вложений", str(context.exception))


if __name__ == "__main__":
    unittest.main()
