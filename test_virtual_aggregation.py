import unittest
import os
import shutil
from virtual_aggregation import read_codes, sanitize_filename, perform_aggregation

class TestVirtualAggregation(unittest.TestCase):
    def setUp(self):
        # Создаем временные файлы для тестов
        self.test_dir = "test_files"
        os.makedirs(self.test_dir, exist_ok=True)

        self.parent_file = os.path.join(self.test_dir, "parents.txt")
        with open(self.parent_file, "w", encoding="utf-8") as f:
            f.write("PARENT1\nPARENT2\nPARENT3\n")

        self.child_file = os.path.join(self.test_dir, "children.txt")
        with open(self.child_file, "w", encoding="utf-8") as f:
            for i in range(10):
                f.write(f"CHILD{i}\n")

        self.results_dirs = []

    def tearDown(self):
        # Удаляем временные файлы и папки результатов
        shutil.rmtree(self.test_dir)
        for d in self.results_dirs:
            if os.path.exists(d):
                shutil.rmtree(d)

    def test_read_codes(self):
        codes = read_codes(self.parent_file)
        self.assertEqual(codes, ["PARENT1", "PARENT2", "PARENT3"])

    def test_sanitize_filename(self):
        self.assertEqual(sanitize_filename("ABC/DEF*GHI"), "ABC_DEF_GHI")
        self.assertEqual(sanitize_filename("CON"), "CON") # На Windows CON зарезервировано, но sanitize пока только символы правит

    def test_perform_aggregation(self):
        output_dir, actual_sets = perform_aggregation(self.parent_file, [self.child_file], 2)
        self.results_dirs.append(output_dir)

        self.assertEqual(actual_sets, 3)
        self.assertTrue(os.path.exists(output_dir))

        files = os.listdir(output_dir)
        self.assertEqual(len(files), 3)
        self.assertIn("PARENT1.txt", files)

        with open(os.path.join(output_dir, "PARENT1.txt"), "r", encoding="utf-8") as f:
            lines = [l.strip() for l in f if l.strip()]
            self.assertEqual(lines, ["PARENT1", "CHILD0", "CHILD1"])

    def test_partial_aggregation(self):
        # 3 родителя, но всего 3 ребенка, по 2 на каждого -> должно собраться только 1 набор
        output_dir, actual_sets = perform_aggregation(self.parent_file, [self.child_file], 5)
        self.results_dirs.append(output_dir)

        self.assertEqual(actual_sets, 2) # 10 детей // 5 = 2 набора

if __name__ == "__main__":
    unittest.main()
