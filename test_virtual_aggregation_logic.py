import unittest
import tempfile
import os
import shutil
from unittest.mock import patch, MagicMock

import virtual_aggregation


class TestVirtualAggregationLogic(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_sanitize_filename(self):
        self.assertEqual(virtual_aggregation.sanitize_filename("valid_name"), "valid_name")
        self.assertEqual(virtual_aggregation.sanitize_filename('invalid/name:*?"<>|test'), "invalid_name_______test")
        self.assertEqual(virtual_aggregation.sanitize_filename(""), "unnamed")
        self.assertEqual(virtual_aggregation.sanitize_filename("   "), "unnamed")
        self.assertEqual(virtual_aggregation.sanitize_filename("  code 123 / test  "), "code 123 _ test")

    def test_read_codes_encodings(self):
        # UTF-8 with BOM
        utf8_bom_path = os.path.join(self.test_dir, "utf8_bom.txt")
        with open(utf8_bom_path, "w", encoding="utf-8-sig") as f:
            f.write("SET_001\nSET_002\n")

        codes = virtual_aggregation.read_codes(utf8_bom_path)
        self.assertEqual(codes, ["SET_001", "SET_002"])

        # CP1251
        cp1251_path = os.path.join(self.test_dir, "cp1251.txt")
        with open(cp1251_path, "w", encoding="cp1251") as f:
            f.write("КОД_001\nКОД_002\n")

        codes = virtual_aggregation.read_codes(cp1251_path)
        self.assertEqual(codes, ["КОД_001", "КОД_002"])

    def test_read_codes_unicode_error_handling(self):
        file_path = os.path.join(self.test_dir, "dummy.txt")
        with open(file_path, "w") as f:
            f.write("data")

        # Имитируем исключение UnicodeError при открытии файла
        with patch("builtins.open", side_effect=UnicodeError("Decode error")):
            with self.assertRaises(ValueError):
                virtual_aggregation.read_codes(file_path)

    def test_perform_aggregation_success(self):
        parent_path = os.path.join(self.test_dir, "parents.txt")
        with open(parent_path, "w", encoding="utf-8") as f:
            f.write("PARENT_001\nPARENT_002\n")

        child1_path = os.path.join(self.test_dir, "child1.txt")
        with open(child1_path, "w", encoding="utf-8") as f:
            f.write("CHILD_001\nCHILD_002\nCHILD_003\nCHILD_004\n")

        child2_path = os.path.join(self.test_dir, "child2.txt")
        with open(child2_path, "w", encoding="utf-8") as f:
            f.write("CHILD_005\nCHILD_006\nCHILD_007\nCHILD_008\n")

        res = virtual_aggregation.perform_aggregation(
            parent_file=parent_path,
            child_files=[child1_path, child2_path],
            count_per_set=4,
            output_parent_dir=self.test_dir
        )

        self.assertEqual(res["status"], "success")
        self.assertEqual(res["created_files"], 2)
        self.assertEqual(res["total_children_used"], 8)

        output_dir = res["output_dir"]
        self.assertTrue(os.path.exists(output_dir))

        # Проверяем содержимое первого файла
        f1_path = os.path.join(output_dir, "PARENT_001.txt")
        self.assertTrue(os.path.exists(f1_path))
        with open(f1_path, "r", encoding="utf-8") as f:
            lines = [l.strip() for l in f.readlines() if l.strip()]
        self.assertEqual(lines, ["PARENT_001", "CHILD_001", "CHILD_002", "CHILD_003", "CHILD_004"])

        # Проверяем содержимое второго файла
        f2_path = os.path.join(output_dir, "PARENT_002.txt")
        self.assertTrue(os.path.exists(f2_path))
        with open(f2_path, "r", encoding="utf-8") as f:
            lines = [l.strip() for l in f.readlines() if l.strip()]
        self.assertEqual(lines, ["PARENT_002", "CHILD_005", "CHILD_006", "CHILD_007", "CHILD_008"])

    def test_perform_aggregation_collision_handling(self):
        parent_path = os.path.join(self.test_dir, "parents.txt")
        # Два родительских кода, которые превратятся в одинаковые имена файлов при очистке
        with open(parent_path, "w", encoding="utf-8") as f:
            f.write("PARENT/001\nPARENT?001\n")

        child_path = os.path.join(self.test_dir, "child.txt")
        with open(child_path, "w", encoding="utf-8") as f:
            f.write("\n".join([f"CHILD_{i}" for i in range(1, 9)]))

        res = virtual_aggregation.perform_aggregation(
            parent_file=parent_path,
            child_files=[child_path],
            count_per_set=4,
            output_parent_dir=self.test_dir
        )

        output_dir = res["output_dir"]
        self.assertTrue(os.path.exists(os.path.join(output_dir, "PARENT_001.txt")))
        self.assertTrue(os.path.exists(os.path.join(output_dir, "PARENT_001_1.txt")))

    def test_perform_aggregation_insufficient_children_confirmed(self):
        parent_path = os.path.join(self.test_dir, "parents.txt")
        with open(parent_path, "w", encoding="utf-8") as f:
            f.write("PARENT_001\nPARENT_002\nPARENT_003\n")

        child_path = os.path.join(self.test_dir, "child.txt")
        # Хватит только на 1 набор из 4 элементов (всего 5 кодов)
        with open(child_path, "w", encoding="utf-8") as f:
            f.write("\n".join([f"CHILD_{i}" for i in range(1, 6)]))

        mock_confirm = MagicMock(return_value=True)

        res = virtual_aggregation.perform_aggregation(
            parent_file=parent_path,
            child_files=[child_path],
            count_per_set=4,
            confirm_callback=mock_confirm,
            output_parent_dir=self.test_dir
        )

        mock_confirm.assert_called_once_with(7, 1)  # не хватает 7 кодов для 3 наборов, доступен 1 набор
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["created_files"], 1)

    def test_perform_aggregation_insufficient_children_cancelled(self):
        parent_path = os.path.join(self.test_dir, "parents.txt")
        with open(parent_path, "w", encoding="utf-8") as f:
            f.write("PARENT_001\nPARENT_002\n")

        child_path = os.path.join(self.test_dir, "child.txt")
        with open(child_path, "w", encoding="utf-8") as f:
            f.write("CHILD_001\nCHILD_002\n")

        mock_confirm = MagicMock(return_value=False)

        res = virtual_aggregation.perform_aggregation(
            parent_file=parent_path,
            child_files=[child_path],
            count_per_set=4,
            confirm_callback=mock_confirm,
            output_parent_dir=self.test_dir
        )

        mock_confirm.assert_called_once()
        self.assertEqual(res["status"], "cancelled")


if __name__ == "__main__":
    unittest.main()
