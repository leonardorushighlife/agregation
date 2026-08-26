import os
import shutil
import tempfile
import unittest
from unittest.mock import patch, MagicMock

from virtual_aggregation import read_codes, sanitize_filename, perform_aggregation


class TestVirtualAggregationLogic(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_sanitize_filename(self):
        self.assertEqual(sanitize_filename("ABC/123:XYZ?*"), "ABC_123_XYZ__")
        self.assertEqual(sanitize_filename("NORMAL_CODE_123"), "NORMAL_CODE_123")

    def test_read_codes_encodings(self):
        encodings = ['utf-8', 'utf-8-sig', 'cp1251']
        for enc in encodings:
            file_path = os.path.join(self.test_dir, f"test_{enc}.txt")
            with open(file_path, 'w', encoding=enc) as f:
                f.write("CODE1\n  CODE2 \n\nCODE3\n")

            codes = read_codes(file_path)
            self.assertEqual(codes, ["CODE1", "CODE2", "CODE3"])

    def test_read_codes_unicode_error(self):
        file_path = os.path.join(self.test_dir, "test_err.txt")
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write("TEST")

        with patch("builtins.open", side_effect=UnicodeError("Decoding failed")):
            with self.assertRaises(ValueError):
                read_codes(file_path)

    def test_perform_aggregation_success(self):
        parent_file = os.path.join(self.test_dir, "parent.txt")
        with open(parent_file, 'w', encoding='utf-8') as f:
            f.write("PARENT_1\nPARENT_2\n")

        child_file1 = os.path.join(self.test_dir, "child1.txt")
        with open(child_file1, 'w', encoding='utf-8') as f:
            f.write("CHILD_1\nCHILD_2\n")

        child_file2 = os.path.join(self.test_dir, "child2.txt")
        with open(child_file2, 'w', encoding='utf-8') as f:
            f.write("CHILD_3\nCHILD_4\n")

        out_dir, created, used_children = perform_aggregation(
            parent_file=parent_file,
            child_files=[child_file1, child_file2],
            count_per_parent=2
        )

        self.assertTrue(os.path.exists(out_dir))
        self.assertEqual(created, 2)
        self.assertEqual(used_children, 4)

        # Проверяем файлы
        p1_file = os.path.join(out_dir, "PARENT_1.txt")
        self.assertTrue(os.path.exists(p1_file))
        with open(p1_file, 'r', encoding='utf-8') as f:
            lines = [l.strip() for l in f]
        self.assertEqual(lines, ["PARENT_1", "CHILD_1", "CHILD_2"])

        p2_file = os.path.join(out_dir, "PARENT_2.txt")
        self.assertTrue(os.path.exists(p2_file))
        with open(p2_file, 'r', encoding='utf-8') as f:
            lines = [l.strip() for l in f]
        self.assertEqual(lines, ["PARENT_2", "CHILD_3", "CHILD_4"])

        # Очистка созданной папки результатов
        shutil.rmtree(out_dir, ignore_errors=True)

    def test_perform_aggregation_filename_collision(self):
        parent_file = os.path.join(self.test_dir, "parent_col.txt")
        with open(parent_file, 'w', encoding='utf-8') as f:
            f.write("PARENT/1\nPARENT:1\n")

        child_file = os.path.join(self.test_dir, "child_col.txt")
        with open(child_file, 'w', encoding='utf-8') as f:
            f.write("C1\nC2\n")

        out_dir, created, used_children = perform_aggregation(
            parent_file=parent_file,
            child_files=[child_file],
            count_per_parent=1
        )

        self.assertEqual(created, 2)
        f1 = os.path.join(out_dir, "PARENT_1.txt")
        f2 = os.path.join(out_dir, "PARENT_1_1.txt")
        self.assertTrue(os.path.exists(f1))
        self.assertTrue(os.path.exists(f2))

        shutil.rmtree(out_dir, ignore_errors=True)

    def test_perform_aggregation_insufficient_children_canceled(self):
        parent_file = os.path.join(self.test_dir, "parent.txt")
        with open(parent_file, 'w', encoding='utf-8') as f:
            f.write("P1\nP2\n")

        child_file = os.path.join(self.test_dir, "child.txt")
        with open(child_file, 'w', encoding='utf-8') as f:
            f.write("C1\nC2\n")

        confirm_mock = MagicMock(return_value=False)

        out_dir, created, used_children = perform_aggregation(
            parent_file=parent_file,
            child_files=[child_file],
            count_per_parent=2,
            confirm_callback=confirm_mock
        )

        confirm_mock.assert_called_once()
        self.assertIsNone(out_dir)
        self.assertEqual(created, 0)
        self.assertEqual(used_children, 0)


if __name__ == "__main__":
    unittest.main()
