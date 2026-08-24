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

class TestVirtualAggregation(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_sanitize_filename(self):
        self.assertEqual(sanitize_filename("010460123456789021ABC/DEF"), "010460123456789021ABC_DEF")
        self.assertEqual(sanitize_filename("test:file*name?"), "test_file_name_")
        self.assertEqual(sanitize_filename("..."), "set_code")
        self.assertEqual(sanitize_filename("  CODE123  "), "CODE123")

    def test_read_codes_encodings(self):
        # UTF-8 with BOM
        p1 = os.path.join(self.test_dir, "utf8_bom.txt")
        with open(p1, 'w', encoding='utf-8-sig') as f:
            f.write("CODE1\nCODE2\n")
        self.assertEqual(read_codes(p1), ["CODE1", "CODE2"])

        # UTF-16
        p2 = os.path.join(self.test_dir, "utf16.txt")
        with open(p2, 'w', encoding='utf-16') as f:
            f.write("CODE3\nCODE4\n")
        self.assertEqual(read_codes(p2), ["CODE3", "CODE4"])

        # CP1251
        p3 = os.path.join(self.test_dir, "cp1251.txt")
        with open(p3, 'w', encoding='cp1251') as f:
            f.write("КОД1\nКОД2\n")
        self.assertEqual(read_codes(p3), ["КОД1", "КОД2"])

    def test_read_codes_fallback_binary(self):
        p = os.path.join(self.test_dir, "invalid.txt")
        with open(p, "wb") as f:
            f.write(b"CODE1\nCODE2\n")

        orig_open = open
        def custom_open(file, mode='r', *args, **kwargs):
            if 'b' not in mode:
                raise UnicodeError("Simulated decode error for text mode")
            return orig_open(file, mode, *args, **kwargs)

        with patch("builtins.open", side_effect=custom_open):
            codes = read_codes(p)
            self.assertEqual(codes, ["CODE1", "CODE2"])

    def test_perform_aggregation_full(self):
        parent_path = os.path.join(self.test_dir, "parents.txt")
        with open(parent_path, "w", encoding="utf-8") as f:
            f.write("PARENT1\nPARENT2\n")

        child1_path = os.path.join(self.test_dir, "child1.txt")
        with open(child1_path, "w", encoding="utf-8") as f:
            f.write("C1\nC2\nC3\n")

        child2_path = os.path.join(self.test_dir, "child2.txt")
        with open(child2_path, "w", encoding="utf-8") as f:
            f.write("C4\nC5\nC6\n")

        # 2 parents, 3 children each = 6 children total required
        res = perform_aggregation(
            parent_file=parent_path,
            child_files=[child1_path, child2_path],
            count_per_parent=3,
            output_dir_base=self.test_dir
        )

        self.assertTrue(res['success'])
        self.assertEqual(res['sets_created'], 2)
        self.assertEqual(res['total_children_used'], 6)

        out_folder = res['output_folder']
        self.assertTrue(os.path.exists(out_folder))

        # Check PARENT1.txt
        p1_file = os.path.join(out_folder, "PARENT1.txt")
        self.assertTrue(os.path.exists(p1_file))
        with open(p1_file, "r", encoding="utf-8") as f:
            lines = [l.strip() for l in f if l.strip()]
        self.assertEqual(lines, ["PARENT1", "C1", "C2", "C3"])

        # Check PARENT2.txt
        p2_file = os.path.join(out_folder, "PARENT2.txt")
        self.assertTrue(os.path.exists(p2_file))
        with open(p2_file, "r", encoding="utf-8") as f:
            lines = [l.strip() for l in f if l.strip()]
        self.assertEqual(lines, ["PARENT2", "C4", "C5", "C6"])

    def test_perform_aggregation_partial_confirmed(self):
        parent_path = os.path.join(self.test_dir, "parents.txt")
        with open(parent_path, "w", encoding="utf-8") as f:
            f.write("PARENT1\nPARENT2\n")

        child_path = os.path.join(self.test_dir, "child.txt")
        with open(child_path, "w", encoding="utf-8") as f:
            f.write("C1\nC2\nC3\n") # Only 3 children, needs 4 for 2 sets of 2

        callback_called = []
        def confirm_cb(msg):
            callback_called.append(msg)
            return True

        res = perform_aggregation(
            parent_file=parent_path,
            child_files=[child_path],
            count_per_parent=2,
            output_dir_base=self.test_dir,
            confirm_partial_callback=confirm_cb
        )

        self.assertTrue(res['success'])
        self.assertEqual(len(callback_called), 1)
        self.assertEqual(res['sets_created'], 2)
        self.assertEqual(res['total_children_used'], 3)

        out_folder = res['output_folder']
        # PARENT1 gets C1, C2; PARENT2 gets C3
        with open(os.path.join(out_folder, "PARENT1.txt"), "r", encoding="utf-8") as f:
            p1_lines = [l.strip() for l in f if l.strip()]
        self.assertEqual(p1_lines, ["PARENT1", "C1", "C2"])

        with open(os.path.join(out_folder, "PARENT2.txt"), "r", encoding="utf-8") as f:
            p2_lines = [l.strip() for l in f if l.strip()]
        self.assertEqual(p2_lines, ["PARENT2", "C3"])

    def test_perform_aggregation_filename_collision(self):
        parent_path = os.path.join(self.test_dir, "parents.txt")
        with open(parent_path, "w", encoding="utf-8") as f:
            f.write("PARENT/1\nPARENT:1\n")

        child_path = os.path.join(self.test_dir, "child.txt")
        with open(child_path, "w", encoding="utf-8") as f:
            f.write("C1\nC2\n")

        res = perform_aggregation(
            parent_file=parent_path,
            child_files=[child_path],
            count_per_parent=1,
            output_dir_base=self.test_dir
        )

        self.assertTrue(res['success'])
        out_folder = res['output_folder']
        self.assertTrue(os.path.exists(os.path.join(out_folder, "PARENT_1.txt")))
        self.assertTrue(os.path.exists(os.path.join(out_folder, "PARENT_1_1.txt")))

if __name__ == "__main__":
    unittest.main()
