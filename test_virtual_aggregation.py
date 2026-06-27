import unittest
import os
import shutil
from virtual_aggregation import sanitize_filename, read_codes, perform_aggregation

class TestVirtualAggregation(unittest.TestCase):
    def setUp(self):
        self.test_dir = "test_aggregation_temp"
        os.makedirs(self.test_dir, exist_ok=True)
        self.parent_file = os.path.join(self.test_dir, "parents.txt")
        self.child_file1 = os.path.join(self.test_dir, "children1.txt")
        self.child_file2 = os.path.join(self.test_dir, "children2.txt")

        with open(self.parent_file, "w", encoding="utf-8") as f:
            f.write("SET001\nSET002\nSET/003")

        with open(self.child_file1, "w", encoding="utf-8") as f:
            f.write("CHILD001\nCHILD002")

        with open(self.child_file2, "w", encoding="utf-8") as f:
            f.write("CHILD003\nCHILD004\nCHILD005")

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_sanitize_filename(self):
        self.assertEqual(sanitize_filename("valid_name"), "valid_name")
        self.assertEqual(sanitize_filename("invalid/name"), "invalid_name")
        self.assertEqual(sanitize_filename("name?*"), "name__")
        self.assertEqual(sanitize_filename("  spaces  "), "spaces")

    def test_read_codes(self):
        parents = read_codes(self.parent_file)
        self.assertEqual(len(parents), 3)
        self.assertEqual(parents[0], "SET001")

        children = read_codes([self.child_file1, self.child_file2])
        self.assertEqual(len(children), 5)
        self.assertEqual(children[2], "CHILD003")

    def test_perform_aggregation(self):
        parents = ["P1", "P2"]
        children = ["C1", "C2", "C3", "C4", "C5"]
        count = 2
        out_dir = os.path.join(self.test_dir, "results")
        os.makedirs(out_dir, exist_ok=True)

        success = perform_aggregation(parents, children, count, out_dir)

        self.assertEqual(success, 2)
        self.assertTrue(os.path.exists(os.path.join(out_dir, "P1.txt")))
        self.assertTrue(os.path.exists(os.path.join(out_dir, "P2.txt")))

        with open(os.path.join(out_dir, "P1.txt"), "r") as f:
            lines = f.read().splitlines()
            self.assertEqual(lines, ["P1", "C1", "C2"])

    def test_perform_aggregation_insufficient_children(self):
        parents = ["P1", "P2", "P3"]
        children = ["C1", "C2", "C3"]
        count = 2
        out_dir = os.path.join(self.test_dir, "results_partial")
        os.makedirs(out_dir, exist_ok=True)

        success = perform_aggregation(parents, children, count, out_dir)

        self.assertEqual(success, 1) # Only P1 can be filled
        self.assertTrue(os.path.exists(os.path.join(out_dir, "P1.txt")))
        self.assertFalse(os.path.exists(os.path.join(out_dir, "P2.txt")))

if __name__ == "__main__":
    unittest.main()
