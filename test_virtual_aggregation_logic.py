import os
import shutil
import tempfile
import unittest

from virtual_aggregation import (
    read_codes,
    sanitize_filename,
    perform_aggregation
)


class TestVirtualAggregationLogic(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_sanitize_filename(self):
        self.assertEqual(sanitize_filename("010460123456789021SET123"), "010460123456789021SET123")
        self.assertEqual(sanitize_filename('SET/123\\456:789*?"<>|'), "SET_123_456_789______")
        self.assertEqual(sanitize_filename("   "), "set")

    def test_read_codes_encodings(self):
        f1 = os.path.join(self.test_dir, "utf8.txt")
        with open(f1, "w", encoding="utf-8") as f:
            f.write("CODE1\nCODE2\n")

        f2 = os.path.join(self.test_dir, "utf16.txt")
        with open(f2, "w", encoding="utf-16") as f:
            f.write("CODE3\nCODE4\n")

        f3 = os.path.join(self.test_dir, "cp1251.txt")
        with open(f3, "w", encoding="cp1251") as f:
            f.write("КОД1\nКОД2\n")

        self.assertEqual(read_codes(f1), ["CODE1", "CODE2"])
        self.assertEqual(read_codes(f2), ["CODE3", "CODE4"])
        self.assertEqual(read_codes(f3), ["КОД1", "КОД2"])

    def test_perform_aggregation_success(self):
        parent_path = os.path.join(self.test_dir, "parents.txt")
        with open(parent_path, "w", encoding="utf-8") as f:
            f.write("PARENT1\nPARENT2\n")

        child1_path = os.path.join(self.test_dir, "child1.txt")
        with open(child1_path, "w", encoding="utf-8") as f:
            f.write("CHILD1\nCHILD2\nCHILD3\n")

        child2_path = os.path.join(self.test_dir, "child2.txt")
        with open(child2_path, "w", encoding="utf-8") as f:
            f.write("CHILD4\nCHILD5\nCHILD6\n")

        child3_path = os.path.join(self.test_dir, "child3.txt")
        with open(child3_path, "w", encoding="utf-8") as f:
            f.write("\n")

        out_dir = os.path.join(self.test_dir, "output")
        res = perform_aggregation(
            parent_file=parent_path,
            child_files=[child1_path, child2_path, child3_path],
            count_per_parent=3,
            output_dir=out_dir
        )

        self.assertEqual(res["created_files"], 2)
        self.assertTrue(os.path.exists(os.path.join(out_dir, "PARENT1.txt")))
        self.assertTrue(os.path.exists(os.path.join(out_dir, "PARENT2.txt")))

        with open(os.path.join(out_dir, "PARENT1.txt"), "r", encoding="utf-8") as f:
            lines = [l.strip() for l in f if l.strip()]
            self.assertEqual(lines, ["PARENT1", "CHILD1", "CHILD2", "CHILD3"])

        with open(os.path.join(out_dir, "PARENT2.txt"), "r", encoding="utf-8") as f:
            lines = [l.strip() for l in f if l.strip()]
            self.assertEqual(lines, ["PARENT2", "CHILD4", "CHILD5", "CHILD6"])

    def test_perform_aggregation_partial_confirm(self):
        parent_path = os.path.join(self.test_dir, "parents.txt")
        with open(parent_path, "w", encoding="utf-8") as f:
            f.write("PARENT1\nPARENT2\nPARENT3\n")

        child1_path = os.path.join(self.test_dir, "child1.txt")
        with open(child1_path, "w", encoding="utf-8") as f:
            f.write("CHILD1\nCHILD2\nCHILD3\nCHILD4\n")

        out_dir = os.path.join(self.test_dir, "output_partial")

        # Если пользователь отменяет:
        res_cancel = perform_aggregation(
            parent_file=parent_path,
            child_files=[child1_path],
            count_per_parent=2,
            output_dir=out_dir,
            confirm_callback=lambda needed, avail, poss: False
        )
        self.assertTrue(res_cancel["cancelled"])

        # Если пользователь соглашается:
        res_ok = perform_aggregation(
            parent_file=parent_path,
            child_files=[child1_path],
            count_per_parent=2,
            output_dir=out_dir,
            confirm_callback=lambda needed, avail, poss: True
        )
        self.assertEqual(res_ok["created_files"], 2)


if __name__ == "__main__":
    unittest.main()
