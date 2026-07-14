import unittest
import os
import shutil
from unittest.mock import MagicMock, patch
from virtual_aggregation import sanitize_filename, read_codes, perform_aggregation

class TestVirtualAggregation(unittest.TestCase):
    def setUp(self):
        self.test_dir = "test_data"
        os.makedirs(self.test_dir, exist_ok=True)
        self.parent_file = os.path.join(self.test_dir, "parents.txt")
        self.child_file = os.path.join(self.test_dir, "children.txt")

        with open(self.parent_file, 'w', encoding='utf-8') as f:
            f.write("PARENT1\nPARENT2\nPARENT:3\n")

        with open(self.child_file, 'w', encoding='utf-8') as f:
            for i in range(10):
                f.write(f"CHILD{i}\n")

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
        # Очистка созданных папок агрегации
        for d in os.listdir('.'):
            if d.startswith("aggregation_results_"):
                shutil.rmtree(d)

    def test_sanitize_filename(self):
        self.assertEqual(sanitize_filename("valid_name"), "valid_name")
        self.assertEqual(sanitize_filename("name/with:illegal?chars"), "name_with_illegal_chars")

    def test_read_codes(self):
        codes = read_codes(self.parent_file)
        self.assertEqual(len(codes), 3)
        self.assertEqual(codes[0], "PARENT1")

    @patch('tkinter.messagebox.askyesno', return_value=True)
    def test_perform_aggregation(self, mock_msgbox):
        # 3 родителя, по 2 вложения = 6 детей нужно. У нас 10.
        result = perform_aggregation(self.parent_file, [self.child_file], 2)
        self.assertIsNotNone(result)
        output_dir, count = result
        self.assertEqual(count, 3)
        self.assertTrue(os.path.isdir(output_dir))

        # Проверка содержимого одного файла
        files = os.listdir(output_dir)
        self.assertIn("PARENT1.txt", files)
        self.assertIn("PARENT_3.txt", files) # Проверка санитизации

        with open(os.path.join(output_dir, "PARENT1.txt"), 'r') as f:
            lines = f.read().splitlines()
            self.assertEqual(lines[0], "PARENT1")
            self.assertEqual(lines[1], "CHILD0")
            self.assertEqual(lines[2], "CHILD1")

    @patch('tkinter.messagebox.askyesno', return_value=False)
    def test_perform_aggregation_insufficient_cancel(self, mock_msgbox):
        # 3 родителя, по 5 вложений = 15 детей нужно. У нас 10.
        result = perform_aggregation(self.parent_file, [self.child_file], 5)
        self.assertIsNone(result)

    @patch('tkinter.messagebox.askyesno', return_value=True)
    def test_perform_aggregation_insufficient_continue(self, mock_msgbox):
        # 3 родителя, по 5 вложений = 15 детей нужно. У нас 10.
        # Должно создаться 10 // 5 = 2 набора.
        result = perform_aggregation(self.parent_file, [self.child_file], 5)
        self.assertIsNotNone(result)
        output_dir, count = result
        self.assertEqual(count, 2)

if __name__ == "__main__":
    unittest.main()
