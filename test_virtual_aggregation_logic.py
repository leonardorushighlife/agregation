import os
import shutil
import tempfile
import unittest
from unittest.mock import patch

from virtual_aggregation import sanitize_filename, read_codes, perform_aggregation

class TestVirtualAggregationLogic(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_sanitize_filename(self):
        self.assertEqual(sanitize_filename("010460123456789021ABC/DEF"), "010460123456789021ABC_DEF")
        self.assertEqual(sanitize_filename("a\\b/c:d*e?f\"g<h>i|j"), "a_b_c_d_e_f_g_h_i_j")
        self.assertEqual(sanitize_filename("  clean_name  "), "clean_name")

    def test_read_codes_encodings(self):
        utf8_path = os.path.join(self.test_dir, "utf8.txt")
        with open(utf8_path, "w", encoding="utf-8") as f:
            f.write("CODE1\n\nCODE2\n  CODE3  \n")

        codes = read_codes(utf8_path)
        self.assertEqual(codes, ["CODE1", "CODE2", "CODE3"])

        cp1251_path = os.path.join(self.test_dir, "cp1251.txt")
        with open(cp1251_path, "w", encoding="cp1251") as f:
            f.write("КОД1\nКОД2\n")

        codes_cp = read_codes(cp1251_path)
        self.assertEqual(codes_cp, ["КОД1", "КОД2"])

    def test_perform_aggregation_success(self):
        parent_file = os.path.join(self.test_dir, "parents.txt")
        with open(parent_file, "w", encoding="utf-8") as f:
            f.write("SET_001\nSET_002\n")

        child_file1 = os.path.join(self.test_dir, "child1.txt")
        with open(child_file1, "w", encoding="utf-8") as f:
            f.write("ITEM_1\nITEM_2\nITEM_3\nITEM_4\n")

        child_file2 = os.path.join(self.test_dir, "child2.txt")
        with open(child_file2, "w", encoding="utf-8") as f:
            f.write("ITEM_5\nITEM_6\nITEM_7\nITEM_8\n")

        out_dir = os.path.join(self.test_dir, "output")

        res = perform_aggregation(
            parent_file=parent_file,
            child_files=[child_file1, child_file2],
            count_per_parent=4,
            output_dir=out_dir
        )

        self.assertIsNotNone(res)
        self.assertEqual(res["sets_created"], 2)
        self.assertEqual(res["total_children_used"], 8)

        # Проверка содержимого сгенерированных файлов
        f1 = os.path.join(out_dir, "SET_001.txt")
        self.assertTrue(os.path.exists(f1))
        with open(f1, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f]
        self.assertEqual(lines, ["SET_001", "ITEM_1", "ITEM_2", "ITEM_3", "ITEM_4"])

        f2 = os.path.join(out_dir, "SET_002.txt")
        self.assertTrue(os.path.exists(f2))
        with open(f2, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f]
        self.assertEqual(lines, ["SET_002", "ITEM_5", "ITEM_6", "ITEM_7", "ITEM_8"])

    def test_perform_aggregation_insufficient_children_canceled(self):
        parent_file = os.path.join(self.test_dir, "parents.txt")
        with open(parent_file, "w", encoding="utf-8") as f:
            f.write("SET_001\nSET_002\n")

        child_file = os.path.join(self.test_dir, "child.txt")
        with open(child_file, "w", encoding="utf-8") as f:
            f.write("ITEM_1\nITEM_2\nITEM_3\nITEM_4\n") # Только на 1 набор

        out_dir = os.path.join(self.test_dir, "output")

        # Отмена через callback
        res = perform_aggregation(
            parent_file=parent_file,
            child_files=[child_file],
            count_per_parent=4,
            output_dir=out_dir,
            confirm_callback=lambda msg: False
        )

        self.assertIsNone(res)

    def test_perform_aggregation_filename_collision(self):
        parent_file = os.path.join(self.test_dir, "parents.txt")
        with open(parent_file, "w", encoding="utf-8") as f:
            # Две строки, дающие одинаковое очищенное имя файла
            f.write("SET/001\nSET\\001\n")

        child_file = os.path.join(self.test_dir, "child.txt")
        with open(child_file, "w", encoding="utf-8") as f:
            f.write("ITEM_1\nITEM_2\n")

        out_dir = os.path.join(self.test_dir, "output")

        res = perform_aggregation(
            parent_file=parent_file,
            child_files=[child_file],
            count_per_parent=1,
            output_dir=out_dir
        )

        self.assertEqual(res["sets_created"], 2)
        f1 = os.path.join(out_dir, "SET_001.txt")
        f2 = os.path.join(out_dir, "SET_001_1.txt")
        self.assertTrue(os.path.exists(f1))
        self.assertTrue(os.path.exists(f2))

if __name__ == "__main__":
    unittest.main()
