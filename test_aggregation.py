import unittest
import os
import shutil
from virtual_aggregation import sanitize_filename, read_codes, perform_aggregation

class TestAggregation(unittest.TestCase):
    def setUp(self):
        self.test_dir = "test_files"
        os.makedirs(self.test_dir, exist_ok=True)
        self.parent_file = os.path.join(self.test_dir, "parents.txt")
        self.child_file1 = os.path.join(self.test_dir, "children1.txt")
        self.child_file2 = os.path.join(self.test_dir, "children2.txt")

        with open(self.parent_file, "w", encoding="utf-8") as f:
            f.write("PARENT1\nPARENT2\nPARENT/3")

        with open(self.child_file1, "w", encoding="utf-8") as f:
            f.write("CHILD1\nCHILD2")

        with open(self.child_file2, "w", encoding="cp1251") as f:
            f.write("CHILD3\nCHILD4")

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
        # Cleanup aggregation result folders
        for d in os.listdir('.'):
            if d.startswith("aggregation_results_"):
                shutil.rmtree(d)

    def test_sanitize_filename(self):
        self.assertEqual(sanitize_filename("abc/def"), "abc_def")
        self.assertEqual(sanitize_filename("a:b*c?d"), "a_b_c_d")

    def test_read_codes(self):
        parents = read_codes(self.parent_file)
        self.assertEqual(len(parents), 3)
        self.assertEqual(parents[0], "PARENT1")

        children2 = read_codes(self.child_file2)
        self.assertEqual(len(children2), 2)
        self.assertEqual(children2[0], "CHILD3")

    def test_perform_aggregation(self):
        # 3 parents, 4 children total, 1 per set -> should result in 3 sets
        out_dir, count = perform_aggregation(self.parent_file, [self.child_file1, self.child_file2], 1)
        self.assertEqual(count, 3)
        self.assertTrue(os.path.exists(out_dir))
        files = os.listdir(out_dir)
        self.assertEqual(len(files), 3)

        # Check one file
        with open(os.path.join(out_dir, "PARENT1.txt"), "r") as f:
            lines = f.read().splitlines()
            self.assertEqual(lines[0], "PARENT1")
            self.assertEqual(lines[1], "CHILD1")

    def test_insufficient_children(self):
        # 3 parents, 4 children total, 2 per set -> should result in 2 sets
        out_dir, count = perform_aggregation(self.parent_file, [self.child_file1, self.child_file2], 2)
        self.assertEqual(count, 2)

if __name__ == "__main__":
    unittest.main()
