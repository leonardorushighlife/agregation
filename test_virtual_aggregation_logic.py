import os
import shutil
import tempfile
import unittest

from virtual_aggregation import (
    sanitize_filename,
    read_codes_from_file,
    perform_aggregation
)


class TestVirtualAggregationLogic(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_sanitize_filename(self):
        self.assertEqual(sanitize_filename("010460123456789021ABC/DEF"), "010460123456789021ABC_DEF")
        self.assertEqual(sanitize_filename('code:123*456?789"a<b>c|d'), "code_123_456_789_a_b_c_d")
        self.assertEqual(sanitize_filename("   "), "set")

        long_code = "A" * 150
        sanitized = sanitize_filename(long_code, max_len=50)
        self.assertEqual(len(sanitized), 50)

    def test_read_codes_from_file_encodings(self):
        # UTF-8 with BOM and blank lines
        file_utf8 = os.path.join(self.test_dir, "utf8.txt")
        with open(file_utf8, "w", encoding="utf-8-sig") as f:
            f.write("CODE1\n\n  CODE2  \nCODE3\n")

        codes = read_codes_from_file(file_utf8)
        self.assertEqual(codes, ["CODE1", "CODE2", "CODE3"])

        # CP1251
        file_cp1251 = os.path.join(self.test_dir, "cp1251.txt")
        with open(file_cp1251, "w", encoding="cp1251") as f:
            f.write("КОД1\nКОД2\n")

        codes_cp = read_codes_from_file(file_cp1251)
        self.assertEqual(codes_cp, ["КОД1", "КОД2"])

    def test_perform_aggregation_success(self):
        parent_file = os.path.join(self.test_dir, "parents.txt")
        with open(parent_file, "w", encoding="utf-8") as f:
            f.write("PARENT_001\nPARENT_002\n")

        child_file1 = os.path.join(self.test_dir, "child1.txt")
        with open(child_file1, "w", encoding="utf-8") as f:
            f.write("CHILD_1\nCHILD_2\nCHILD_3\nCHILD_4\n")

        child_file2 = os.path.join(self.test_dir, "child2.txt")
        with open(child_file2, "w", encoding="utf-8") as f:
            f.write("CHILD_5\nCHILD_6\nCHILD_7\nCHILD_8\n")

        out_dir = os.path.join(self.test_dir, "output")

        res = perform_aggregation(
            parent_file=parent_file,
            child_files=[child_file1, child_file2],
            count_per_parent=4,
            output_dir=out_dir
        )

        self.assertIsNotNone(res)
        self.assertEqual(res['sets_created'], 2)
        self.assertEqual(res['child_used'], 8)

        # Проверяем первый файл
        f1_path = os.path.join(out_dir, "PARENT_001.txt")
        self.assertTrue(os.path.exists(f1_path))
        with open(f1_path, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f.readlines() if line.strip()]
        self.assertEqual(lines, ["PARENT_001", "CHILD_1", "CHILD_2", "CHILD_3", "CHILD_4"])

        # Проверяем второй файл
        f2_path = os.path.join(out_dir, "PARENT_002.txt")
        self.assertTrue(os.path.exists(f2_path))
        with open(f2_path, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f.readlines() if line.strip()]
        self.assertEqual(lines, ["PARENT_002", "CHILD_5", "CHILD_6", "CHILD_7", "CHILD_8"])

    def test_perform_aggregation_partial(self):
        parent_file = os.path.join(self.test_dir, "parents.txt")
        with open(parent_file, "w", encoding="utf-8") as f:
            f.write("PARENT_1\nPARENT_2\nPARENT_3\n")

        child_file = os.path.join(self.test_dir, "children.txt")
        with open(child_file, "w", encoding="utf-8") as f:
            f.write("C1\nC2\nC3\nC4\nC5\n")  # Только 5 дочерних кодов при count=2 -> хватит только на 2 набора

        out_dir = os.path.join(self.test_dir, "output_partial")

        # Если confirm_callback возвращает True
        res = perform_aggregation(
            parent_file=parent_file,
            child_files=[child_file],
            count_per_parent=2,
            output_dir=out_dir,
            confirm_callback=lambda msg: True
        )

        self.assertIsNotNone(res)
        self.assertEqual(res['sets_created'], 2)
        self.assertEqual(res['child_used'], 4)

    def test_perform_aggregation_errors(self):
        parent_file = os.path.join(self.test_dir, "empty_parents.txt")
        open(parent_file, "w").close()

        child_file = os.path.join(self.test_dir, "children.txt")
        with open(child_file, "w", encoding="utf-8") as f:
            f.write("C1\nC2\n")

        # Ошибка при вызове с невалидным числом вложений
        with self.assertRaises(ValueError):
            perform_aggregation(parent_file, [child_file], 0)

        # Ошибка при пустом файле родительских кодов
        with self.assertRaises(ValueError):
            perform_aggregation(parent_file, [child_file], 2)


if __name__ == "__main__":
    unittest.main()
