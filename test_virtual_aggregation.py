import os
import shutil
import unittest
from virtual_aggregation import sanitize_filename, read_codes, perform_aggregation

class TestVirtualAggregation(unittest.TestCase):
    def setUp(self):
        # Создаем временную директорию для тестов
        self.test_dir = "test_data"
        os.makedirs(self.test_dir, exist_ok=True)

        self.parent_file = os.path.join(self.test_dir, "parents.txt")
        with open(self.parent_file, "w", encoding="utf-8") as f:
            f.write("PARENT1\nPARENT2\nPARENT:INVALID/CHAR\n")

        self.child_file = os.path.join(self.test_dir, "children.txt")
        with open(self.child_file, "w", encoding="utf-8") as f:
            for i in range(25):
                f.write(f"CHILD{i}\n")

    def tearDown(self):
        # Удаляем временную директорию и созданные результаты
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
        for d in os.listdir("."):
            if d.startswith("aggregation_results_"):
                shutil.rmtree(d)

    def test_sanitize_filename(self):
        self.assertEqual(sanitize_filename("valid_name"), "valid_name")
        self.assertEqual(sanitize_filename("name/with:chars"), "name_with_chars")

    def test_read_codes(self):
        codes = read_codes(self.parent_file)
        self.assertEqual(len(codes), 3)
        self.assertEqual(codes[0], "PARENT1")

    def test_perform_aggregation(self):
        count_per_parent = 10
        result = perform_aggregation(self.parent_file, [self.child_file], count_per_parent)

        self.assertIsNotNone(result)
        output_dir, actual_sets = result

        # У нас 3 родителя и 25 детей. При 10 на родителя должно получиться 2 полных набора.
        self.assertEqual(actual_sets, 2)
        self.assertTrue(os.path.exists(output_dir))

        files = os.listdir(output_dir)
        self.assertEqual(len(files), 2)

        # Проверка содержимого одного из файлов
        p1_file = os.path.join(output_dir, "PARENT1.txt")
        self.assertTrue(os.path.exists(p1_file))

        with open(p1_file, 'r', encoding='utf-8') as f:
            lines = [line.strip() for line in f]
            self.assertEqual(lines[0], "PARENT1")
            self.assertEqual(len(lines), 11) # 1 родитель + 10 детей
            self.assertEqual(lines[1], "CHILD0")
            self.assertEqual(lines[10], "CHILD9")

    def test_partial_aggregation_confirm(self):
        # Тестируем случай, когда пользователь отказывается от частичной агрегации
        count_per_parent = 30 # Нужно 90 детей, а у нас 25

        def mock_confirm(msg):
            return False

        result = perform_aggregation(self.parent_file, [self.child_file], count_per_parent, confirm_callback=mock_confirm)
        self.assertIsNone(result)

if __name__ == "__main__":
    unittest.main()
