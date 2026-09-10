import unittest
import os
import shutil
import tempfile
from virtual_aggregation import (
    sanitize_filename,
    read_codes_from_file,
    read_codes_from_files,
    perform_aggregation,
)


class TestVirtualAggregation(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_sanitize_filename(self):
        self.assertEqual(sanitize_filename("SET/123*456?"), "SET_123_456_")
        self.assertEqual(sanitize_filename("  0104601234567890  "), "0104601234567890")
        self.assertEqual(sanitize_filename(""), "set")

    def test_read_codes_from_file(self):
        file_path = os.path.join(self.temp_dir, "codes.txt")
        lines = [" CODE1 \n", "\n", "CODE2\r\n", "   ", "CODE3"]
        with open(file_path, "w", encoding="utf-8") as f:
            f.writelines(lines)

        codes = read_codes_from_file(file_path)
        self.assertEqual(codes, ["CODE1", "CODE2", "CODE3"])

    def test_read_codes_from_files(self):
        f1 = os.path.join(self.temp_dir, "c1.txt")
        f2 = os.path.join(self.temp_dir, "c2.txt")
        f3 = os.path.join(self.temp_dir, "c3.txt")

        with open(f1, "w", encoding="utf-8") as f:
            f.write("CHILD1\nCHILD2\n")
        with open(f2, "w", encoding="utf-8") as f:
            f.write("CHILD3\nCHILD4\n")
        with open(f3, "w", encoding="utf-8") as f:
            f.write("CHILD5\nCHILD6\n")

        codes = read_codes_from_files([f1, f2, f3])
        self.assertEqual(codes, ["CHILD1", "CHILD2", "CHILD3", "CHILD4", "CHILD5", "CHILD6"])

    def test_perform_aggregation_success(self):
        parent_file = os.path.join(self.temp_dir, "parents.txt")
        with open(parent_file, "w", encoding="utf-8") as f:
            f.write("PARENT1\nPARENT2\n")

        child_f1 = os.path.join(self.temp_dir, "ch1.txt")
        child_f2 = os.path.join(self.temp_dir, "ch2.txt")
        child_f3 = os.path.join(self.temp_dir, "ch3.txt")

        with open(child_f1, "w", encoding="utf-8") as f:
            f.write("C1\nC2\nC3\n")
        with open(child_f2, "w", encoding="utf-8") as f:
            f.write("C4\nC5\nC6\n")
        with open(child_f3, "w", encoding="utf-8") as f:
            f.write("C7\nC8\n")

        # 2 parents, 8 children total. items_per_set = 4 -> requires 8 children total.
        count, out_dir = perform_aggregation(
            parent_file=parent_file,
            child_files=[child_f1, child_f2, child_f3],
            items_per_set=4,
            output_base_dir=self.temp_dir
        )

        self.assertEqual(count, 2)
        self.assertTrue(os.path.exists(out_dir))

        # Check PARENT1 file
        p1_file = os.path.join(out_dir, "PARENT1.txt")
        self.assertTrue(os.path.exists(p1_file))
        with open(p1_file, "r", encoding="utf-8") as f:
            p1_lines = [line.strip() for line in f if line.strip()]
        self.assertEqual(p1_lines, ["PARENT1", "C1", "C2", "C3", "C4"])

        # Check PARENT2 file
        p2_file = os.path.join(out_dir, "PARENT2.txt")
        self.assertTrue(os.path.exists(p2_file))
        with open(p2_file, "r", encoding="utf-8") as f:
            p2_lines = [line.strip() for line in f if line.strip()]
        self.assertEqual(p2_lines, ["PARENT2", "C5", "C6", "C7", "C8"])

    def test_perform_aggregation_insufficient_children_raises(self):
        parent_file = os.path.join(self.temp_dir, "parents.txt")
        with open(parent_file, "w", encoding="utf-8") as f:
            f.write("PARENT1\n")

        child_f1 = os.path.join(self.temp_dir, "ch1.txt")
        with open(child_f1, "w", encoding="utf-8") as f:
            f.write("C1\nC2\n")

        # items_per_set = 4, but only 2 children available
        with self.assertRaises(ValueError):
            perform_aggregation(
                parent_file=parent_file,
                child_files=[child_f1],
                items_per_set=4,
                output_base_dir=self.temp_dir
            )

    def test_perform_aggregation_partial_confirmation_cancel(self):
        parent_file = os.path.join(self.temp_dir, "parents.txt")
        with open(parent_file, "w", encoding="utf-8") as f:
            f.write("PARENT1\nPARENT2\n")

        child_f1 = os.path.join(self.temp_dir, "ch1.txt")
        with open(child_f1, "w", encoding="utf-8") as f:
            f.write("C1\nC2\nC3\nC4\n")

        # Needed 8, available 4 (1 full set out of 2 requested)
        def cancel_callback(msg):
            return False

        with self.assertRaises(InterruptedError):
            perform_aggregation(
                parent_file=parent_file,
                child_files=[child_f1],
                items_per_set=4,
                output_base_dir=self.temp_dir,
                confirm_callback=cancel_callback
            )


if __name__ == "__main__":
    unittest.main()
