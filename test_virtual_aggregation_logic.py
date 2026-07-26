# -*- coding: utf-8 -*-
import unittest
import os
import shutil
from unittest.mock import MagicMock

# Импортируем тестируемые функции
from virtual_aggregation import sanitize_filename, read_codes, perform_aggregation

class TestVirtualAggregationLogic(unittest.TestCase):
    def setUp(self):
        self.test_dir = "test_temp_dir"
        if not os.path.exists(self.test_dir):
            os.makedirs(self.test_dir)

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_sanitize_filename(self):
        self.assertEqual(sanitize_filename("valid_name"), "valid_name")
        self.assertEqual(sanitize_filename("name/with\\invalid:chars*?\"<>|"), "name_with_invalid_chars______")

    def test_read_codes_utf8_sig(self):
        filepath = os.path.join(self.test_dir, "test_utf8_sig.txt")
        # Запись в кодировке UTF-8 с BOM (utf-8-sig)
        with open(filepath, "w", encoding="utf-8-sig") as f:
            f.write("code1\ncode2\n\ncode3\n")

        codes = read_codes(filepath)
        self.assertEqual(codes, ["code1", "code2", "code3"])

    def test_read_codes_utf16(self):
        filepath = os.path.join(self.test_dir, "test_utf16.txt")
        # Запись в кодировке UTF-16
        with open(filepath, "w", encoding="utf-16") as f:
            f.write("code1\ncode2\ncode3\n")

        codes = read_codes(filepath)
        self.assertEqual(codes, ["code1", "code2", "code3"])

    def test_perform_aggregation_success(self):
        parent_codes = ["parent1", "parent2"]
        child_codes = ["child1", "child2", "child3", "child4", "child5", "child6", "child7", "child8"]

        output_path = os.path.join(self.test_dir, "out_success")
        success, created = perform_aggregation(parent_codes, child_codes, 4, output_path)

        self.assertTrue(success)
        self.assertEqual(created, 2)

        # Проверяем, что файлы созданы корректно
        f1_path = os.path.join(output_path, "parent1.txt")
        f2_path = os.path.join(output_path, "parent2.txt")

        self.assertTrue(os.path.exists(f1_path))
        self.assertTrue(os.path.exists(f2_path))

        # Проверяем структуру файлов
        with open(f1_path, "r", encoding="utf-8") as f:
            lines = f.read().splitlines()
        self.assertEqual(lines, ["parent1", "child1", "child2", "child3", "child4"])

    def test_perform_aggregation_insufficient_children_confirmed(self):
        parent_codes = ["parent1", "parent2"]
        child_codes = ["child1", "child2", "child3", "child4", "child5"] # Не хватает на 2 набора

        output_path = os.path.join(self.test_dir, "out_partial")

        confirm_callback = MagicMock(return_value=True)

        success, created = perform_aggregation(
            parent_codes=parent_codes,
            child_codes=child_codes,
            count_per_parent=4,
            output_dir=output_path,
            confirm_callback=confirm_callback
        )

        self.assertTrue(success)
        self.assertEqual(created, 1) # Только один полный набор создан
        confirm_callback.assert_called_once()

    def test_perform_aggregation_insufficient_children_rejected(self):
        parent_codes = ["parent1", "parent2"]
        child_codes = ["child1", "child2", "child3", "child4", "child5"]

        output_path = os.path.join(self.test_dir, "out_partial_rejected")

        confirm_callback = MagicMock(return_value=False)

        success, created = perform_aggregation(
            parent_codes=parent_codes,
            child_codes=child_codes,
            count_per_parent=4,
            output_dir=output_path,
            confirm_callback=confirm_callback
        )

        self.assertFalse(success)
        self.assertEqual(created, 0)

    def test_perform_aggregation_collision_handling(self):
        # Коллизия возникает при одинаковых или санитаризуемых до одинакового вида именах
        parent_codes = ["parent*", "parent?"] # оба превратятся в parent_
        child_codes = ["child1", "child2", "child3", "child4"]

        output_path = os.path.join(self.test_dir, "out_collision")

        success, created = perform_aggregation(
            parent_codes=parent_codes,
            child_codes=child_codes,
            count_per_parent=2,
            output_dir=output_path
        )

        self.assertTrue(success)
        self.assertEqual(created, 2)

        f1_path = os.path.join(output_path, "parent_.txt")
        f2_path = os.path.join(output_path, "parent__1.txt")

        self.assertTrue(os.path.exists(f1_path))
        self.assertTrue(os.path.exists(f2_path))

if __name__ == "__main__":
    unittest.main()
