import os
import shutil
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from virtual_aggregation import (
    perform_aggregation,
    read_codes,
    sanitize_filename
)


class TestVirtualAggregationLogic(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_sanitize_filename(self):
        self.assertEqual(sanitize_filename("SET123/456"), "SET123_456")
        self.assertEqual(sanitize_filename("SET?*:<|>"), "SET______")
        self.assertEqual(sanitize_filename("  SET_NORMAL\n"), "SET_NORMAL")
        self.assertEqual(sanitize_filename("???"), "___")

    def test_read_codes_encodings(self):
        # UTF-8 with BOM / standard UTF-8
        utf8_file = os.path.join(self.test_dir, "utf8.txt")
        with open(utf8_file, "w", encoding="utf-8-sig") as f:
            f.write("CODE1\nCODE2\n\nCODE3\n")
        self.assertEqual(read_codes(utf8_file), ["CODE1", "CODE2", "CODE3"])

        # CP1251
        cp1251_file = os.path.join(self.test_dir, "cp1251.txt")
        with open(cp1251_file, "w", encoding="cp1251") as f:
            f.write("КОД1\nКОД2\n")
        self.assertEqual(read_codes(cp1251_file), ["КОД1", "КОД2"])

    def test_perform_aggregation_success(self):
        # Create parent file (2 parent codes)
        parent_file = os.path.join(self.test_dir, "parents.txt")
        with open(parent_file, "w", encoding="utf-8") as f:
            f.write("PARENT_01\nPARENT_02\n")

        # Create 3 child files (total 8 child codes, 4 per parent)
        child1 = os.path.join(self.test_dir, "child1.txt")
        with open(child1, "w", encoding="utf-8") as f:
            f.write("CHILD_01\nCHILD_02\nCHILD_03\n")

        child2 = os.path.join(self.test_dir, "child2.txt")
        with open(child2, "w", encoding="utf-8") as f:
            f.write("CHILD_04\nCHILD_05\nCHILD_06\n")

        child3 = os.path.join(self.test_dir, "child3.txt")
        with open(child3, "w", encoding="utf-8") as f:
            f.write("CHILD_07\nCHILD_08\nCHILD_09\n")  # 9th code will remain unused

        output_dir, num_sets, num_children = perform_aggregation(
            parent_file,
            [child1, child2, child3],
            count_per_parent=4
        )

        self.assertEqual(num_sets, 2)
        self.assertEqual(num_children, 8)
        self.assertTrue(os.path.exists(output_dir))

        # Check content of first generated file
        file1 = os.path.join(output_dir, "PARENT_01.txt")
        self.assertTrue(os.path.exists(file1))
        lines1 = read_codes(file1)
        self.assertEqual(lines1, ["PARENT_01", "CHILD_01", "CHILD_02", "CHILD_03", "CHILD_04"])

        # Check content of second generated file
        file2 = os.path.join(output_dir, "PARENT_02.txt")
        self.assertTrue(os.path.exists(file2))
        lines2 = read_codes(file2)
        self.assertEqual(lines2, ["PARENT_02", "CHILD_05", "CHILD_06", "CHILD_07", "CHILD_08"])

    def test_perform_aggregation_insufficient_children_canceled(self):
        parent_file = os.path.join(self.test_dir, "parents.txt")
        with open(parent_file, "w", encoding="utf-8") as f:
            f.write("PARENT_01\nPARENT_02\n")

        child_file = os.path.join(self.test_dir, "child.txt")
        with open(child_file, "w", encoding="utf-8") as f:
            f.write("CHILD_01\nCHILD_02\nCHILD_03\nCHILD_04\nCHILD_05\n")

        confirm_cb = MagicMock(return_value=False)
        with self.assertRaises(InterruptedError):
            perform_aggregation(
                parent_file,
                [child_file],
                count_per_parent=4,
                confirm_callback=confirm_cb
            )
        confirm_cb.assert_called_once()

    def test_perform_aggregation_insufficient_children_accepted(self):
        parent_file = os.path.join(self.test_dir, "parents.txt")
        with open(parent_file, "w", encoding="utf-8") as f:
            f.write("PARENT_01\nPARENT_02\n")

        child_file = os.path.join(self.test_dir, "child.txt")
        with open(child_file, "w", encoding="utf-8") as f:
            f.write("CHILD_01\nCHILD_02\nCHILD_03\nCHILD_04\nCHILD_05\n")

        confirm_cb = MagicMock(return_value=True)
        output_dir, num_sets, num_children = perform_aggregation(
            parent_file,
            [child_file],
            count_per_parent=4,
            confirm_callback=confirm_cb
        )
        self.assertEqual(num_sets, 1)
        self.assertEqual(num_children, 4)

    def test_filename_collision(self):
        parent_file = os.path.join(self.test_dir, "parents.txt")
        with open(parent_file, "w", encoding="utf-8") as f:
            f.write("PARENT/01\nPARENT?01\n")

        child_file = os.path.join(self.test_dir, "child.txt")
        with open(child_file, "w", encoding="utf-8") as f:
            f.write("\n".join([f"CHILD_{i:02d}" for i in range(1, 9)]))

        output_dir, num_sets, _ = perform_aggregation(
            parent_file,
            [child_file],
            count_per_parent=4
        )

        self.assertEqual(num_sets, 2)
        self.assertTrue(os.path.exists(os.path.join(output_dir, "PARENT_01.txt")))
        self.assertTrue(os.path.exists(os.path.join(output_dir, "PARENT_01_1.txt")))


if __name__ == "__main__":
    unittest.main()
