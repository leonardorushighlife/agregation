import unittest
import os
import shutil
import tempfile
from virtual_aggregation import read_codes, perform_aggregation, sanitize_filename

class TestVirtualAggregationLogic(unittest.TestCase):
    def setUp(self):
        # Создаем временную директорию для тестов
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        # Удаляем временную директорию
        shutil.rmtree(self.test_dir)

    def test_read_codes_utf8(self):
        filepath = os.path.join(self.test_dir, "utf8.txt")
        with open(filepath, "w", encoding="utf-8") as f:
            f.write("code1\ncode2\n\ncode3\n")

        codes = read_codes(filepath)
        self.assertEqual(codes, ["code1", "code2", "code3"])

    def test_read_codes_utf8_sig(self):
        filepath = os.path.join(self.test_dir, "utf8_sig.txt")
        with open(filepath, "w", encoding="utf-8-sig") as f:
            f.write("code1\r\ncode2\r\n")

        codes = read_codes(filepath)
        self.assertEqual(codes, ["code1", "code2"])

    def test_read_codes_cp1251(self):
        filepath = os.path.join(self.test_dir, "cp1251.txt")
        with open(filepath, "w", encoding="cp1251") as f:
            f.write("код1\nкод2\n")

        codes = read_codes(filepath)
        self.assertEqual(codes, ["код1", "код2"])

    def test_read_codes_empty_file(self):
        filepath = os.path.join(self.test_dir, "empty.txt")
        with open(filepath, "w", encoding="utf-8") as f:
            f.write("")

        codes = read_codes(filepath)
        self.assertEqual(codes, [])

    def test_perform_aggregation_empty_parents(self):
        with self.assertRaises(ValueError):
            perform_aggregation([], ["child1"], 1, self.test_dir)

    def test_perform_aggregation_empty_children(self):
        with self.assertRaises(ValueError):
            perform_aggregation(["parent1"], [], 1, self.test_dir)

    def test_perform_aggregation_invalid_count(self):
        with self.assertRaises(ValueError):
            perform_aggregation(["parent1"], ["child1"], 0, self.test_dir)

    def test_sanitize_filename(self):
        self.assertEqual(sanitize_filename("abc/def"), "abc_def")
        self.assertEqual(sanitize_filename("p\\a:r*e?n\"t<o>r|"), "p_a_r_e_n_t_o_r_")

    def test_name_collision(self):
        # Два кода, дающих одинаковые очищенные имена
        parents = ["parent/1", "parent*1", "parent_1"]
        children = ["c1", "c2", "c3", "c4", "c5", "c6"]

        success, files = perform_aggregation(parents, children, 2, self.test_dir)
        self.assertTrue(success)
        self.assertEqual(len(files), 3)

        # Проверяем ожидаемые имена файлов
        expected_files = [
            os.path.join(self.test_dir, "parent_1.txt"),
            os.path.join(self.test_dir, "parent_1_1.txt"),
            os.path.join(self.test_dir, "parent_1_2.txt")
        ]
        for ef in expected_files:
            self.assertTrue(os.path.exists(ef), f"File {ef} should exist")

    def test_insufficient_children_approved(self):
        parents = ["parent1", "parent2", "parent3"]
        children = ["c1", "c2", "c3", "c4", "c5", "c6", "c7"] # Нужно 12 для 3 наборов по 4 вложения.
        # Должно получиться 7 // 4 = 1 набор.

        callback_called = []
        def mock_callback(msg):
            callback_called.append(msg)
            return True

        success, files = perform_aggregation(parents, children, 4, self.test_dir, confirm_callback=mock_callback)
        self.assertTrue(success)
        self.assertEqual(len(callback_called), 1)
        self.assertEqual(len(files), 1)
        self.assertTrue(os.path.exists(files[0]))

        # Проверим содержимое созданного файла
        with open(files[0], "r", encoding="utf-8") as f:
            lines = f.read().splitlines()
        self.assertEqual(lines, ["parent1", "c1", "c2", "c3", "c4"])

    def test_insufficient_children_declined(self):
        parents = ["parent1", "parent2"]
        children = ["c1", "c2"]

        callback_called = []
        def mock_callback(msg):
            callback_called.append(msg)
            return False

        success, res = perform_aggregation(parents, children, 4, self.test_dir, confirm_callback=mock_callback)
        self.assertFalse(success)
        self.assertEqual(res, "Операция отменена пользователем.")
        self.assertEqual(len(callback_called), 1)

    def test_insufficient_children_critical(self):
        # 2 вложения, а требуется 4 на набор. Даже 1 набор не собрать.
        parents = ["parent1"]
        children = ["c1", "c2"]

        def mock_callback(msg):
            return True

        with self.assertRaises(ValueError):
            perform_aggregation(parents, children, 4, self.test_dir, confirm_callback=mock_callback)

if __name__ == "__main__":
    unittest.main()
