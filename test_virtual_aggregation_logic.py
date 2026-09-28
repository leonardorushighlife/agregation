import os
import shutil
import tempfile
import unittest
from unittest.mock import patch, MagicMock

import virtual_aggregation as va


class TestVirtualAggregationLogic(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_sanitize_filename(self):
        self.assertEqual(va.sanitize_filename("010460123456789021SET123"), "010460123456789021SET123")
        self.assertEqual(va.sanitize_filename("01/0460:123*456?789\"<|>"), "01_0460_123_456_789____")
        self.assertEqual(va.sanitize_filename("   "), "set_code")

    def test_read_codes_encodings(self):
        # UTF-8 with BOM / without BOM
        f_utf8 = os.path.join(self.test_dir, "utf8.txt")
        with open(f_utf8, "w", encoding="utf-8-sig") as f:
            f.write("CODE1\nCODE2\n\nCODE3  \n")

        codes = va.read_codes(f_utf8)
        self.assertEqual(codes, ["CODE1", "CODE2", "CODE3"])

        # CP1251
        f_cp1251 = os.path.join(self.test_dir, "cp1251.txt")
        with open(f_cp1251, "w", encoding="cp1251") as f:
            f.write("КОД1\nКОД2\n")

        codes = va.read_codes(f_cp1251)
        self.assertEqual(codes, ["КОД1", "КОД2"])

    def test_read_codes_unsupported_encoding(self):
        f_bad = os.path.join(self.test_dir, "bad.txt")

        # Симулируем исключение UnicodeError при открытии
        with patch("builtins.open", side_effect=UnicodeError("Decoding failed")):
            with self.assertRaises(ValueError):
                va.read_codes(f_bad)

    def test_perform_aggregation_success(self):
        parent_file = os.path.join(self.test_dir, "parents.txt")
        child_file1 = os.path.join(self.test_dir, "children1.txt")
        child_file2 = os.path.join(self.test_dir, "children2.txt")

        with open(parent_file, "w", encoding="utf-8") as f:
            f.write("SET_001\nSET_002\n")

        with open(child_file1, "w", encoding="utf-8") as f:
            f.write("CHILD_001\nCHILD_002\nCHILD_003\nCHILD_004\n")

        with open(child_file2, "w", encoding="utf-8") as f:
            f.write("CHILD_005\nCHILD_006\nCHILD_007\nCHILD_008\n")

        out_dir = os.path.join(self.test_dir, "output")

        sets_created, children_used = va.perform_aggregation(
            parent_file=parent_file,
            child_files=[child_file1, child_file2],
            count_per_parent=4,
            output_dir=out_dir
        )

        self.assertEqual(sets_created, 2)
        self.assertEqual(children_used, 8)

        # Проверяем содержимое созданных файлов
        out_files = sorted(os.listdir(out_dir))
        self.assertEqual(out_files, ["SET_001.txt", "SET_002.txt"])

        with open(os.path.join(out_dir, "SET_001.txt"), "r", encoding="utf-8") as f:
            lines = [l.strip() for l in f.readlines()]
            self.assertEqual(lines, ["SET_001", "CHILD_001", "CHILD_002", "CHILD_003", "CHILD_004"])

        with open(os.path.join(out_dir, "SET_002.txt"), "r", encoding="utf-8") as f:
            lines = [l.strip() for l in f.readlines()]
            self.assertEqual(lines, ["SET_002", "CHILD_005", "CHILD_006", "CHILD_007", "CHILD_008"])

    def test_perform_aggregation_filename_collision(self):
        parent_file = os.path.join(self.test_dir, "parents_dup.txt")
        child_file = os.path.join(self.test_dir, "children_dup.txt")

        # Оба родительских кода очищаются в одинаковое имя файла (например, SET_CODE)
        with open(parent_file, "w", encoding="utf-8") as f:
            f.write("SET/CODE\nSET*CODE\n")

        with open(child_file, "w", encoding="utf-8") as f:
            f.write("C1\nC2\nC3\nC4\n")

        out_dir = os.path.join(self.test_dir, "output_dup")

        sets_created, children_used = va.perform_aggregation(
            parent_file=parent_file,
            child_files=[child_file],
            count_per_parent=2,
            output_dir=out_dir
        )

        self.assertEqual(sets_created, 2)
        self.assertEqual(children_used, 4)

        out_files = sorted(os.listdir(out_dir))
        self.assertEqual(out_files, ["SET_CODE.txt", "SET_CODE_1.txt"])

    def test_perform_aggregation_insufficient_children_canceled(self):
        parent_file = os.path.join(self.test_dir, "parents_ins.txt")
        child_file = os.path.join(self.test_dir, "children_ins.txt")

        with open(parent_file, "w", encoding="utf-8") as f:
            f.write("SET_1\nSET_2\n")

        with open(child_file, "w", encoding="utf-8") as f:
            f.write("C1\nC2\n")  # Требуется 2 * 4 = 8, но есть только 2

        out_dir = os.path.join(self.test_dir, "output_cancel")

        confirm_cb = MagicMock(return_value=False)

        sets_created, children_used = va.perform_aggregation(
            parent_file=parent_file,
            child_files=[child_file],
            count_per_parent=4,
            output_dir=out_dir,
            confirm_callback=confirm_cb
        )

        confirm_cb.assert_called_once()
        self.assertEqual(sets_created, 0)
        self.assertEqual(children_used, 0)


if __name__ == "__main__":
    unittest.main()
