import unittest
import os
import shutil
from virtual_aggregation import read_codes, sanitize_filename, perform_aggregation

class TestVirtualAggregation(unittest.TestCase):
    def setUp(self):
        self.test_dir = "test_data"
        if not os.path.exists(self.test_dir):
            os.makedirs(self.test_dir)

        self.parent_path = os.path.join(self.test_dir, "parents.txt")
        with open(self.parent_path, "w", encoding="utf-8") as f:
            f.write("parent1\nparent2\n")

        self.child_path = os.path.join(self.test_dir, "children.txt")
        with open(self.child_path, "w", encoding="utf-8") as f:
            f.write("child1\nchild2\nchild3\nchild4\n")

        self.output_dir = os.path.join(self.test_dir, "output")

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_read_codes(self):
        codes = read_codes(self.parent_path)
        self.assertEqual(codes, ["parent1", "parent2"])

    def test_sanitize_filename(self):
        bad_name = "code:with/illegal*chars?"
        good_name = sanitize_filename(bad_name)
        self.assertEqual(good_name, "code_with_illegal_chars_")

    def test_perform_aggregation_full(self):
        # 2 parents, 4 children, 2 per parent -> success
        success = perform_aggregation(self.parent_path, [self.child_path], 2, self.output_dir)
        self.assertTrue(success)

        files = os.listdir(self.output_dir)
        self.assertEqual(len(files), 2)
        self.assertIn("parent1.txt", files)
        self.assertIn("parent2.txt", files)

        with open(os.path.join(self.output_dir, "parent1.txt"), "r") as f:
            lines = f.read().splitlines()
            self.assertEqual(lines, ["parent1", "child1", "child2"])

    def test_perform_aggregation_partial_confirm(self):
        # 2 parents, 4 children, 3 per parent -> needs 6, only 4 available
        # 4 // 3 = 1 set possible

        def mock_confirm(msg):
            return True

        success = perform_aggregation(self.parent_path, [self.child_path], 3, self.output_dir, confirm_callback=mock_confirm)
        self.assertTrue(success)

        files = os.listdir(self.output_dir)
        self.assertEqual(len(files), 1)
        self.assertIn("parent1.txt", files)

if __name__ == "__main__":
    unittest.main()
