import os
import shutil
from virtual_aggregation import sanitize_filename, read_codes, perform_aggregation

# Заглушка для messagebox, чтобы тесты не зависали
class MockMessageBox:
    def askyesno(self, title, message):
        return True
    def showinfo(self, title, message):
        print(f"INFO: {title} - {message}")
    def showerror(self, title, message):
        print(f"ERROR: {title} - {message}")

import virtual_aggregation
virtual_aggregation.messagebox = MockMessageBox()

def test_sanitize():
    assert sanitize_filename("abc/def") == "abc_def"
    assert sanitize_filename("a:b?c*d") == "a_b_c_d"
    print("test_sanitize passed")

def test_read_codes():
    with open("test_p.txt", "w", encoding="utf-8") as f:
        f.write("P1\n\nP2\n  \n")
    codes = read_codes("test_p.txt")
    assert codes == ["P1", "P2"]
    os.remove("test_p.txt")
    print("test_read_codes passed")

def test_aggregation_logic():
    # Создаем тестовые данные
    with open("parents.txt", "w", encoding="utf-8") as f:
        f.write("PARENT1\nPARENT2")
    with open("children.txt", "w", encoding="utf-8") as f:
        f.write("CHILD1\nCHILD2\nCHILD3\nCHILD4")

    # 2 вложения на набор
    perform_aggregation("parents.txt", ["children.txt"], "2")

    # Ищем созданную папку
    dirs = [d for d in os.listdir() if d.startswith("aggregation_results_")]
    assert len(dirs) > 0
    latest_dir = sorted(dirs)[-1]

    files = os.listdir(latest_dir)
    assert "PARENT1.txt" in files
    assert "PARENT2.txt" in files

    with open(os.path.join(latest_dir, "PARENT1.txt"), "r") as f:
        lines = f.read().splitlines()
        assert lines == ["PARENT1", "CHILD1", "CHILD2"]

    with open(os.path.join(latest_dir, "PARENT2.txt"), "r") as f:
        lines = f.read().splitlines()
        assert lines == ["PARENT2", "CHILD3", "CHILD4"]

    # Чистка
    os.remove("parents.txt")
    os.remove("children.txt")
    shutil.rmtree(latest_dir)
    print("test_aggregation_logic passed")

if __name__ == "__main__":
    test_sanitize()
    test_read_codes()
    test_aggregation_logic()
    print("All tests passed!")
