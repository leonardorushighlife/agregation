import os
import shutil
from virtual_aggregation import perform_aggregation, sanitize_filename

def test_aggregation_logic():
    print("Запуск теста логики агрегации...")

    parents = ["PARENT1", "PARENT2", "PARENT/WITH/SLASH"]
    children = ["CHILD1", "CHILD2", "CHILD3", "CHILD4", "CHILD5", "CHILD6"]
    count_per_parent = 2

    # Мы не передаем confirm_fn, так что если вложений хватит, он не будет спрашивать.
    # Если вложений НЕ хватит, он вернет (0, None) если нет confirm_fn или он вернет False.

    success_count, output_dir = perform_aggregation(parents, children, count_per_parent)

    assert success_count == 3, f"Ожидалось 3 файла, создано {success_count}"
    assert os.path.exists(output_dir), "Папка вывода не создана"

    # Проверка имен файлов
    expected_files = ["PARENT1.txt", "PARENT2.txt", "PARENT_WITH_SLASH.txt"]
    actual_files = os.listdir(output_dir)
    for ef in expected_files:
        assert ef in actual_files, f"Файл {ef} не найден в {actual_files}"

    # Проверка содержимого
    with open(os.path.join(output_dir, "PARENT1.txt"), "r", encoding="utf-8") as f:
        lines = f.read().splitlines()
        assert lines == ["PARENT1", "CHILD1", "CHILD2"], f"Неверное содержимое PARENT1.txt: {lines}"

    with open(os.path.join(output_dir, "PARENT_WITH_SLASH.txt"), "r", encoding="utf-8") as f:
        lines = f.read().splitlines()
        assert lines == ["PARENT/WITH/SLASH", "CHILD5", "CHILD6"], f"Неверное содержимое PARENT_WITH_SLASH.txt: {lines}"

    print("Тест успешно пройден!")

    # Уборка
    shutil.rmtree(output_dir)

if __name__ == "__main__":
    try:
        test_aggregation_logic()
    except Exception as e:
        print(f"Тест провалился: {e}")
        exit(1)
