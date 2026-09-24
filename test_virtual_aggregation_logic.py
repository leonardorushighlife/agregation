import os
import shutil
import tempfile
import unittest
from unittest.mock import patch

from virtual_aggregation import (
    read_codes,
    sanitize_filename,
    perform_aggregation
)


class TestVirtualAggregationLogic(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_sanitize_filename(self):
        existing = set()

        # '010460123456789021<ABC>?/*' -> '<' -> '_', '>?/*' -> '____' stripped trailing spaces/dots -> '010460123456789021_ABC____'
        fn1 = sanitize_filename('010460123456789021<ABC>?/*', existing)
        self.assertEqual(fn1, '010460123456789021_ABC____.txt')

        # Повторное имя должно получить суффикс _1
        fn2 = sanitize_filename('010460123456789021<ABC>?/*', existing)
        self.assertEqual(fn2, '010460123456789021_ABC_____1.txt')

    def test_read_codes_encodings(self):
        # UTF-8 с BOM
        file_utf8_sig = os.path.join(self.test_dir, 'utf8_sig.txt')
        with open(file_utf8_sig, 'w', encoding='utf-8-sig') as f:
            f.write("CODE1\nCODE2\n")

        # UTF-16
        file_utf16 = os.path.join(self.test_dir, 'utf16.txt')
        with open(file_utf16, 'w', encoding='utf-16') as f:
            f.write("CODE3\nCODE4\n")

        # CP1251
        file_cp1251 = os.path.join(self.test_dir, 'cp1251.txt')
        with open(file_cp1251, 'w', encoding='cp1251') as f:
            f.write("КОД5\nКОД6\n")

        self.assertEqual(read_codes(file_utf8_sig), ["CODE1", "CODE2"])
        self.assertEqual(read_codes(file_utf16), ["CODE3", "CODE4"])
        self.assertEqual(read_codes(file_cp1251), ["КОД5", "КОД6"])

    def test_read_codes_unicode_error_handling(self):
        file_path = os.path.join(self.test_dir, 'dummy.txt')
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write("test")

        with patch('builtins.open', side_effect=UnicodeError("Simulated decode error")):
            with self.assertRaises(ValueError) as ctx:
                read_codes(file_path)
            self.assertIn("Неподдерживаемая кодировка", str(ctx.exception))

    def test_perform_aggregation_success(self):
        parent_file = os.path.join(self.test_dir, 'parent.txt')
        with open(parent_file, 'w', encoding='utf-8') as f:
            f.write("SET_001\nSET_002\n")

        child_file_1 = os.path.join(self.test_dir, 'child1.txt')
        with open(child_file_1, 'w', encoding='utf-8') as f:
            f.write("ITEM_1\nITEM_2\n")

        child_file_2 = os.path.join(self.test_dir, 'child2.txt')
        with open(child_file_2, 'w', encoding='utf-8') as f:
            f.write("ITEM_3\nITEM_4\n")

        out_dir = os.path.join(self.test_dir, 'output')
        res = perform_aggregation(
            parent_file=parent_file,
            child_files=[child_file_1, child_file_2],
            count_per_set=2,
            output_dir=out_dir
        )

        self.assertIsNotNone(res)
        self.assertEqual(res['sets_created'], 2)
        self.assertEqual(res['total_children_used'], 4)

        # Проверка содержания первого набора
        f1_path = os.path.join(out_dir, 'SET_001.txt')
        self.assertTrue(os.path.exists(f1_path))
        with open(f1_path, 'r', encoding='utf-8') as f:
            lines = [line.strip() for line in f if line.strip()]
        self.assertEqual(lines, ['SET_001', 'ITEM_1', 'ITEM_2'])

        # Проверка содержания второго набора
        f2_path = os.path.join(out_dir, 'SET_002.txt')
        self.assertTrue(os.path.exists(f2_path))
        with open(f2_path, 'r', encoding='utf-8') as f:
            lines = [line.strip() for line in f if line.strip()]
        self.assertEqual(lines, ['SET_002', 'ITEM_3', 'ITEM_4'])

    def test_perform_aggregation_partial_confirm(self):
        parent_file = os.path.join(self.test_dir, 'parent.txt')
        with open(parent_file, 'w', encoding='utf-8') as f:
            f.write("SET_001\nSET_002\nSET_003\n")

        child_file = os.path.join(self.test_dir, 'child.txt')
        with open(child_file, 'w', encoding='utf-8') as f:
            # Кодов хватает только на 2 полного набора по 2 штуки (всего 5 кодов)
            f.write("ITEM_1\nITEM_2\nITEM_3\nITEM_4\nITEM_5\n")

        out_dir = os.path.join(self.test_dir, 'output')

        # Отмена частичного формирования
        res_cancel = perform_aggregation(
            parent_file=parent_file,
            child_files=[child_file],
            count_per_set=2,
            output_dir=out_dir,
            confirm_partial_callback=lambda msg: False
        )
        self.assertIsNone(res_cancel)

        # Подтверждение частичного формирования
        res_confirm = perform_aggregation(
            parent_file=parent_file,
            child_files=[child_file],
            count_per_set=2,
            output_dir=out_dir,
            confirm_partial_callback=lambda msg: True
        )
        self.assertIsNotNone(res_confirm)
        self.assertEqual(res_confirm['sets_created'], 2)
        self.assertEqual(res_confirm['total_children_used'], 4)


if __name__ == '__main__':
    unittest.main()
