import os
import shutil
import tempfile
import unittest
from virtual_aggregation import read_codes_from_file, sanitize_filename, perform_aggregation

class TestVirtualAggregationLogic(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory for test files
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        # Clean up the directory after tests
        shutil.rmtree(self.test_dir)
        # Also clean up any aggregation results folders created in the current directory during tests
        for item in os.listdir('.'):
            if item.startswith('aggregation_results_') and os.path.isdir(item):
                try:
                    shutil.rmtree(item)
                except Exception:
                    pass

    def test_sanitize_filename(self):
        self.assertEqual(sanitize_filename("valid_name"), "valid_name")
        self.assertEqual(sanitize_filename("name/with\\slash:colon*star?question\"quote<less>greater|pipe"), "name_with_slash_colon_star_question_quote_less_greater_pipe")
        self.assertEqual(sanitize_filename("   trimmed_spaces   "), "trimmed_spaces")
        self.assertEqual(sanitize_filename(""), "empty_code")
        self.assertEqual(sanitize_filename('   /\\:*?"<>|   '), "_________")

    def test_read_codes_from_file_encodings(self):
        # Test UTF-8-SIG
        utf8_sig_path = os.path.join(self.test_dir, "utf8_sig.txt")
        with open(utf8_sig_path, "w", encoding="utf-8-sig") as f:
            f.write("code1\n\n  code2  \ncode3\n")
        self.assertEqual(read_codes_from_file(utf8_sig_path), ["code1", "code2", "code3"])

        # Test UTF-16
        utf16_path = os.path.join(self.test_dir, "utf16.txt")
        with open(utf16_path, "w", encoding="utf-16") as f:
            f.write("utf16_code1\nutf16_code2")
        self.assertEqual(read_codes_from_file(utf16_path), ["utf16_code1", "utf16_code2"])

        # Test UTF-8
        utf8_path = os.path.join(self.test_dir, "utf8.txt")
        with open(utf8_path, "w", encoding="utf-8") as f:
            f.write("utf8_1\nutf8_2")
        self.assertEqual(read_codes_from_file(utf8_path), ["utf8_1", "utf8_2"])

        # Test CP1251
        cp1251_path = os.path.join(self.test_dir, "cp1251.txt")
        with open(cp1251_path, "w", encoding="cp1251") as f:
            f.write("русский_код1\nрусский_код2")
        self.assertEqual(read_codes_from_file(cp1251_path), ["русский_код1", "русский_код2"])

    def test_perform_aggregation_success(self):
        # Create set file
        set_path = os.path.join(self.test_dir, "parents.txt")
        with open(set_path, "w", encoding="utf-8") as f:
            f.write("setA\nsetB\n")

        # Create child files
        child1_path = os.path.join(self.test_dir, "children1.txt")
        with open(child1_path, "w", encoding="utf-8") as f:
            f.write("child1\nchild2\n")

        child2_path = os.path.join(self.test_dir, "children2.txt")
        with open(child2_path, "w", encoding="utf-8") as f:
            f.write("child3\nchild4\n")

        # We have 2 sets and 4 children total, 2 per set
        out_dir, total = perform_aggregation(set_path, [child1_path, child2_path], 2)
        self.assertEqual(total, 2)
        self.assertTrue(os.path.isdir(out_dir))

        # Check files inside output dir
        files = os.listdir(out_dir)
        self.assertEqual(len(files), 2)
        self.assertIn("setA.txt", files)
        self.assertIn("setB.txt", files)

        # Check file content of setA.txt
        with open(os.path.join(out_dir, "setA.txt"), "r", encoding="utf-8") as f:
            lines = f.read().splitlines()
        self.assertEqual(lines, ["setA", "child1", "child2"])

        # Check file content of setB.txt
        with open(os.path.join(out_dir, "setB.txt"), "r", encoding="utf-8") as f:
            lines = f.read().splitlines()
        self.assertEqual(lines, ["setB", "child3", "child4"])

    def test_perform_aggregation_collision(self):
        # Test collision handling: multiple parent codes that map to same sanitized file name
        set_path = os.path.join(self.test_dir, "parents_collision.txt")
        with open(set_path, "w", encoding="utf-8") as f:
            # Both "set/1" and "set\\1" will sanitize to "set_1"
            f.write("set/1\nset\\1\nset:1\n")

        child_path = os.path.join(self.test_dir, "children.txt")
        with open(child_path, "w", encoding="utf-8") as f:
            f.write("c1\nc2\nc3\n")

        out_dir, total = perform_aggregation(set_path, [child_path], 1)
        self.assertEqual(total, 3)

        files = sorted(os.listdir(out_dir))
        # Expected: set_1.txt, set_1_1.txt, set_1_2.txt
        self.assertEqual(files, ["set_1.txt", "set_1_1.txt", "set_1_2.txt"])

        # Let's verify the content of each
        with open(os.path.join(out_dir, "set_1.txt"), "r", encoding="utf-8") as f:
            self.assertEqual(f.read().splitlines(), ["set/1", "c1"])
        with open(os.path.join(out_dir, "set_1_1.txt"), "r", encoding="utf-8") as f:
            self.assertEqual(f.read().splitlines(), ["set\\1", "c2"])
        with open(os.path.join(out_dir, "set_1_2.txt"), "r", encoding="utf-8") as f:
            self.assertEqual(f.read().splitlines(), ["set:1", "c3"])

    def test_perform_aggregation_fewer_attachments_proceed(self):
        # 3 parents, but only 4 children. Count per set is 2 (needs 6 children)
        set_path = os.path.join(self.test_dir, "parents.txt")
        with open(set_path, "w", encoding="utf-8") as f:
            f.write("set1\nset2\nset3\n")

        child_path = os.path.join(self.test_dir, "children.txt")
        with open(child_path, "w", encoding="utf-8") as f:
            f.write("c1\nc2\nc3\nc4\n")

        # Callback returns True -> proceed with 2 sets (4 children)
        callback_called = []
        def confirm_cb(actual, needed):
            callback_called.append((actual, needed))
            return True

        out_dir, total = perform_aggregation(set_path, [child_path], 2, confirm_callback=confirm_cb)
        self.assertEqual(total, 2)
        self.assertEqual(callback_called, [(4, 6)])

        files = sorted(os.listdir(out_dir))
        self.assertEqual(files, ["set1.txt", "set2.txt"])

    def test_perform_aggregation_fewer_attachments_cancel(self):
        # 3 parents, but only 4 children. Count per set is 2 (needs 6 children)
        set_path = os.path.join(self.test_dir, "parents.txt")
        with open(set_path, "w", encoding="utf-8") as f:
            f.write("set1\nset2\nset3\n")

        child_path = os.path.join(self.test_dir, "children.txt")
        with open(child_path, "w", encoding="utf-8") as f:
            f.write("c1\nc2\nc3\nc4\n")

        # Callback returns False -> cancel
        def confirm_cb(actual, needed):
            return False

        with self.assertRaises(ValueError) as context:
            perform_aggregation(set_path, [child_path], 2, confirm_callback=confirm_cb)
        self.assertIn("Операция отменена", str(context.exception))

    def test_perform_aggregation_insufficient_for_even_one(self):
        # 2 parents, 1 child, count per set is 2
        set_path = os.path.join(self.test_dir, "parents.txt")
        with open(set_path, "w", encoding="utf-8") as f:
            f.write("set1\nset2\n")

        child_path = os.path.join(self.test_dir, "children.txt")
        with open(child_path, "w", encoding="utf-8") as f:
            f.write("c1\n")

        with self.assertRaises(ValueError) as context:
            perform_aggregation(set_path, [child_path], 2)
        self.assertIn("Недостаточно кодов вложений даже для одного набора", str(context.exception))
