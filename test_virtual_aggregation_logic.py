import unittest
import os
import shutil
import tempfile
from unittest.mock import patch

from virtual_aggregation import sanitize_filename, read_codes, perform_aggregation


class TestVirtualAggregationLogic(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_sanitize_filename(self):
        self.assertEqual(sanitize_filename('010460000000000021ABC/DEF'), '010460000000000021ABC_DEF')
        self.assertEqual(sanitize_filename('SET:123*456?789'), 'SET_123_456_789')
        self.assertEqual(sanitize_filename(''), 'set')
        self.assertEqual(sanitize_filename('  code_with_spaces  '), 'code_with_spaces')

    def test_read_codes_encodings(self):
        # UTF-8 file
        utf8_file = os.path.join(self.test_dir, 'utf8.txt')
        with open(utf8_file, 'w', encoding='utf-8') as f:
            f.write("CODE1\nCODE2\nCODE3\n")

        codes = read_codes(utf8_file)
        self.assertEqual(codes, ["CODE1", "CODE2", "CODE3"])

        # UTF-16 file
        utf16_file = os.path.join(self.test_dir, 'utf16.txt')
        with open(utf16_file, 'w', encoding='utf-16') as f:
            f.write("CODE_16_1\nCODE_16_2\n")

        codes16 = read_codes(utf16_file)
        self.assertEqual(codes16, ["CODE_16_1", "CODE_16_2"])

        # CP1251 file
        cp1251_file = os.path.join(self.test_dir, 'cp1251.txt')
        with open(cp1251_file, 'w', encoding='cp1251') as f:
            f.write("КОД_1\nКОД_2\n")

        codes_cp = read_codes(cp1251_file)
        self.assertEqual(codes_cp, ["КОД_1", "КОД_2"])

    def test_read_codes_unicode_error(self):
        # Simulate open raising UnicodeError
        fake_file = os.path.join(self.test_dir, 'fake.txt')
        with open(fake_file, 'w') as f:
            f.write("test")

        with patch("builtins.open", side_effect=UnicodeError("Decoding error")):
            with self.assertRaises(ValueError) as cm:
                read_codes(fake_file)
            self.assertIn("Не удалось прочитать файл", str(cm.exception))

    def test_perform_aggregation_success(self):
        parent_file = os.path.join(self.test_dir, 'parents.txt')
        with open(parent_file, 'w', encoding='utf-8') as f:
            f.write("PARENT_01\nPARENT_02\n")

        child_file_1 = os.path.join(self.test_dir, 'child_1.txt')
        with open(child_file_1, 'w', encoding='utf-8') as f:
            f.write("CHILD_01\nCHILD_02\nCHILD_03\n")

        child_file_2 = os.path.join(self.test_dir, 'child_2.txt')
        with open(child_file_2, 'w', encoding='utf-8') as f:
            f.write("CHILD_04\nCHILD_05\nCHILD_06\n")

        out_folder, count = perform_aggregation(
            parent_file=parent_file,
            child_files=[child_file_1, child_file_2],
            count_per_parent=3,
            output_base_dir=self.test_dir
        )

        self.assertEqual(count, 2)
        self.assertTrue(os.path.exists(out_folder))

        p1_path = os.path.join(out_folder, "PARENT_01.txt")
        p2_path = os.path.join(out_folder, "PARENT_02.txt")

        self.assertTrue(os.path.exists(p1_path))
        self.assertTrue(os.path.exists(p2_path))

        with open(p1_path, 'r', encoding='utf-8') as f:
            lines1 = [l.strip() for l in f if l.strip()]
        self.assertEqual(lines1, ["PARENT_01", "CHILD_01", "CHILD_02", "CHILD_03"])

        with open(p2_path, 'r', encoding='utf-8') as f:
            lines2 = [l.strip() for l in f if l.strip()]
        self.assertEqual(lines2, ["PARENT_02", "CHILD_04", "CHILD_05", "CHILD_06"])

    def test_perform_aggregation_filename_collision(self):
        # Parents with identical sanitized names (e.g., PARENT/01 and PARENT?01 both become PARENT_01)
        parent_file = os.path.join(self.test_dir, 'parents.txt')
        with open(parent_file, 'w', encoding='utf-8') as f:
            f.write("PARENT/01\nPARENT?01\n")

        child_file = os.path.join(self.test_dir, 'child.txt')
        with open(child_file, 'w', encoding='utf-8') as f:
            f.write("C1\nC2\n")

        out_folder, count = perform_aggregation(
            parent_file=parent_file,
            child_files=[child_file],
            count_per_parent=1,
            output_base_dir=self.test_dir
        )

        self.assertEqual(count, 2)
        p1_path = os.path.join(out_folder, "PARENT_01.txt")
        p2_path = os.path.join(out_folder, "PARENT_01_1.txt")

        self.assertTrue(os.path.exists(p1_path))
        self.assertTrue(os.path.exists(p2_path))

    def test_perform_aggregation_insufficient_children_confirmed(self):
        parent_file = os.path.join(self.test_dir, 'parents.txt')
        with open(parent_file, 'w', encoding='utf-8') as f:
            f.write("PARENT_01\nPARENT_02\nPARENT_03\n")

        child_file = os.path.join(self.test_dir, 'child.txt')
        with open(child_file, 'w', encoding='utf-8') as f:
            f.write("C1\nC2\nC3\nC4\n")  # Only 4 children, count=2 -> 2 sets possible

        confirmed = False

        def mock_confirm(msg):
            nonlocal confirmed
            confirmed = True
            return True

        out_folder, count = perform_aggregation(
            parent_file=parent_file,
            child_files=[child_file],
            count_per_parent=2,
            output_base_dir=self.test_dir,
            confirm_callback=mock_confirm
        )

        self.assertTrue(confirmed)
        self.assertEqual(count, 2)

    def test_perform_aggregation_insufficient_children_cancelled(self):
        parent_file = os.path.join(self.test_dir, 'parents.txt')
        with open(parent_file, 'w', encoding='utf-8') as f:
            f.write("PARENT_01\nPARENT_02\nPARENT_03\n")

        child_file = os.path.join(self.test_dir, 'child.txt')
        with open(child_file, 'w', encoding='utf-8') as f:
            f.write("C1\nC2\n")

        def mock_confirm(msg):
            return False

        out_folder, count = perform_aggregation(
            parent_file=parent_file,
            child_files=[child_file],
            count_per_parent=2,
            output_base_dir=self.test_dir,
            confirm_callback=mock_confirm
        )

        self.assertIsNone(out_folder)
        self.assertEqual(count, 0)


if __name__ == '__main__':
    unittest.main()
