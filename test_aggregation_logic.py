import os
import shutil
from virtual_aggregation import perform_aggregation, read_codes

def test_aggregation():
    # Setup test data
    parent_file = "test_parents.txt"
    child_file = "test_children.txt"

    parents = ["PARENT1", "PARENT2", "PARENT/INVALID"]
    children = [f"CHILD{i}" for i in range(1, 11)] # 10 children

    with open(parent_file, "w", encoding="utf-8") as f:
        f.write("\n".join(parents))

    with open(child_file, "w", encoding="utf-16") as f: # Test different encoding
        f.write("\n".join(children))

    print(f"Created test files: {parent_file}, {child_file}")

    try:
        # Test case 1: 3 parents, 3 children per parent = 9 children needed. 10 available.
        # Should create 3 files.
        count = 3
        out_dir, total = perform_aggregation(parent_file, [child_file], count)

        print(f"Aggregation completed. Output dir: {out_dir}, Total sets: {total}")

        assert total == 3
        assert os.path.exists(out_dir)
        files = os.listdir(out_dir)
        assert len(files) == 3

        # Check one file content
        test_file = os.path.join(out_dir, "PARENT1.txt")
        assert os.path.exists(test_file)
        with open(test_file, "r", encoding="utf-8") as f:
            lines = f.read().splitlines()
            assert lines[0] == "PARENT1"
            assert lines[1] == "CHILD1"
            assert lines[2] == "CHILD2"
            assert lines[3] == "CHILD3"
            assert len(lines) == 4

        # Check sanitized filename
        assert os.path.exists(os.path.join(out_dir, "PARENT_INVALID.txt"))

        print("Test Case 1 Passed!")

        # Cleanup first case
        shutil.rmtree(out_dir)
        import time
        time.sleep(1.1) # Ensure different timestamp

        # Test case 2: Not enough children for all parents
        # 3 parents, 4 children each = 12 needed. 10 available -> 2 sets possible.
        count = 4
        out_dir2, total2 = perform_aggregation(parent_file, [child_file], count)
        print(f"Test Case 2: Output dir: {out_dir2}, Total sets: {total2}")
        assert total2 == 2
        assert len(os.listdir(out_dir2)) == 2
        print("Test Case 2 Passed!")

        # Cleanup
        os.remove(parent_file)
        os.remove(child_file)
        shutil.rmtree(out_dir2)
        print("Cleanup done.")

    except Exception as e:
        print(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
        exit(1)

if __name__ == "__main__":
    test_aggregation()
