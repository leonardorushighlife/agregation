import os
import shutil
import tempfile
import unittest

from virtual_aggregation import clean_filename, read_codes, perform_aggregation


class TestVirtualAggregationLogic(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_clean_filename(self):
        self.assertEqual(clean_filename("010460123456789021abc/def"), "010460123456789021abc_def")
        self.assertEqual(clean_filename('code:123*456?"<>|'), "code_123_456_____")
        self.assertEqual(clean_filename(""), "set_code")

    def test_read_codes_encodings(self):
        # UTF-8 with BOM
        utf8_sig_path = os.path.join(self.test_dir, "utf8_sig.txt")
        with open(utf8_sig_path, "w", encoding="utf-8-sig") as f:
            f.write("CODE1\nCODE2\n")

        # CP1251
        cp1251_path = os.path.join(self.test_dir, "cp1251.txt")
        with open(cp1251_path, "w", encoding="cp1251") as f:
            f.write("КОД1\nКОД2\n")

        self.assertEqual(read_codes(utf8_sig_path), ["CODE1", "CODE2"])
        self.assertEqual(read_codes(cp1251_path), ["КОД1", "КОД2"])

    def test_perform_aggregation_success(self):
        parent_file = os.path.join(self.test_dir, "parents.txt")
        with open(parent_file, "w", encoding="utf-8") as f:
            f.write("PARENT_001\nPARENT_002\n")

        child1 = os.path.join(self.test_dir, "child1.txt")
        with open(child1, "w", encoding="utf-8") as f:
            f.write("CHILD_001\nCHILD_002\n")

        child2 = os.path.join(self.test_dir, "child2.txt")
        with open(child2, "w", encoding="utf-8") as f:
            f.write("CHILD_003\nCHILD_004\n")

        out_dir = os.path.join(self.test_dir, "output")
        res_dir, count, total_used = perform_aggregation(
            parent_file=parent_file,
            child_files=[child1, child2],
            items_per_parent=2,
            output_dir=out_dir
        )

        self.assertEqual(res_dir, out_dir)
        self.assertEqual(count, 2)
        self.assertEqual(total_used, 4)

        # Check output files
        f1_path = os.path.join(out_dir, "PARENT_001.txt")
        f2_path = os.path.join(out_dir, "PARENT_002.txt")
        self.assertTrue(os.path.exists(f1_path))
        self.assertTrue(os.path.exists(f2_path))

        with open(f1_path, "r", encoding="utf-8") as f:
            lines = [l.strip() for l in f.readlines()]
        self.assertEqual(lines, ["PARENT_001", "CHILD_001", "CHILD_002"])

        with open(f2_path, "r", encoding="utf-8") as f:
            lines = [l.strip() for l in f.readlines()]
        self.assertEqual(lines, ["PARENT_002", "CHILD_003", "CHILD_004"])

    def test_perform_aggregation_partial(self):
        parent_file = os.path.join(self.test_dir, "parents.txt")
        with open(parent_file, "w", encoding="utf-8") as f:
            f.write("PARENT_001\nPARENT_002\nPARENT_003\n")

        child1 = os.path.join(self.test_dir, "child1.txt")
        with open(child1, "w", encoding="utf-8") as f:
            f.write("CHILD_001\nCHILD_002\nCHILD_003\n")

        out_dir = os.path.join(self.test_dir, "output")

        # User declines partial confirmation
        res_dir, count, total_used = perform_aggregation(
            parent_file=parent_file,
            child_files=[child1],
            items_per_parent=2,
            output_dir=out_dir,
            confirm_partial_callback=lambda msg: False
        )
        self.assertIsNone(res_dir)
        self.assertEqual(count, 0)

        # User accepts partial confirmation (only 1 set of 2 items can be formed from 3 items)
        res_dir, count, total_used = perform_aggregation(
            parent_file=parent_file,
            child_files=[child1],
            items_per_parent=2,
            output_dir=out_dir,
            confirm_partial_callback=lambda msg: True
        )
        self.assertEqual(res_dir, out_dir)
        self.assertEqual(count, 1)
        self.assertEqual(total_used, 2)


if __name__ == "__main__":
    unittest.main()
