import os
import unittest
from virtual_aggregation import perform_aggregation, sanitize_filename

class TestVirtualAggregation(unittest.TestCase):
    def setUp(self):
        # Создаем временные файлы для тестов
        self.parent_file = "test_parents.txt"
        self.child_file1 = "test_children1.txt"
        self.child_file2 = "test_children2.txt"

        with open(self.parent_file, "w", encoding="utf-8") as f:
            f.write("PARENT1\nPARENT2\nPARENT/3\n")

        with open(self.child_file1, "w", encoding="utf-8") as f:
            f.write("CHILD1\nCHILD2\n")

        with open(self.child_file2, "w", encoding="utf-8") as f:
            f.write("CHILD3\nCHILD4\nCHILD5\n")

    def tearDown(self):
        # Удаляем временные файлы
        for f in [self.parent_file, self.child_file1, self.child_file2]:
            if os.path.exists(f):
                os.remove(f)

        # Удаляем папки с результатами
        for d in os.listdir("."):
            if d.startswith("aggregation_results_") and os.path.isdir(d):
                for file in os.listdir(d):
                    os.remove(os.path.join(d, file))
                os.rmdir(d)

    def test_sanitize_filename(self):
        self.assertEqual(sanitize_filename("ABC/123*XYZ"), "ABC_123_XYZ")
        self.assertEqual(sanitize_filename("PRN:123"), "PRN_123")

    def test_aggregation_full(self):
        # 3 родителя, по 1 вложению. Всего 5 вложений доступно.
        # Должно создаться 3 файла.
        result = perform_aggregation(self.parent_file, [self.child_file1, self.child_file2], 1)
        self.assertIsNotNone(result)
        output_dir, count = result
        self.assertEqual(count, 3)
        self.assertTrue(os.path.isdir(output_dir))

        files = os.listdir(output_dir)
        self.assertEqual(len(files), 3)
        self.assertIn("PARENT1.txt", files)
        self.assertIn("PARENT2.txt", files)
        self.assertIn("PARENT_3.txt", files) # Проверка санитайзера

    def test_aggregation_partial(self):
        # 3 родителя, по 2 вложения. Всего 5 вложений.
        # Должно получиться только 2 полных набора (2*2=4 < 5).
        # Эмулируем подтверждение пользователя
        result = perform_aggregation(self.parent_file, [self.child_file1, self.child_file2], 2, confirm_callback=lambda m: True)
        self.assertIsNotNone(result)
        output_dir, count = result
        self.assertEqual(count, 2)

        files = os.listdir(output_dir)
        self.assertEqual(len(files), 2)

        # Проверяем содержимое первого файла
        with open(os.path.join(output_dir, "PARENT1.txt"), "r") as f:
            lines = f.read().splitlines()
            self.assertEqual(lines[0], "PARENT1")
            self.assertEqual(lines[1], "CHILD1")
            self.assertEqual(lines[2], "CHILD2")

    def test_aggregation_insufficient(self):
        # Пытаемся собрать наборы, когда вложений не хватает даже на один.
        with self.assertRaises(Exception):
            perform_aggregation(self.parent_file, [self.child_file1], 10)

if __name__ == "__main__":
    unittest.main()
