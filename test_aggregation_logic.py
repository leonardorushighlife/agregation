import os
import shutil
from virtual_aggregation import perform_aggregation

def test_aggregation():
    # 1. Подготовка тестовых данных
    parent_file = "test_parents.txt"
    child_file1 = "test_children1.txt"
    child_file2 = "test_children2.txt"

    parents = ["P1", "P2", "P3/Special*"]
    children1 = ["C1", "C2"]
    children2 = ["C3", "C4", "C5", "C6"]

    with open(parent_file, "w", encoding="utf-8") as f:
        f.write("\n".join(parents))

    with open(child_file1, "w", encoding="utf-8") as f:
        f.write("\n".join(children1))

    with open(child_file2, "w", encoding="utf-8") as f:
        f.write("\n".join(children2))

    print("Тестовые файлы созданы.")

    # 2. Запуск агрегации (2 вложения на 1 родителя)
    # Ожидаем 3 набора (P1: C1,C2; P2: C3,C4; P3: C5,C6)
    count = 2
    try:
        result = perform_aggregation(parent_file, [child_file1, child_file2], count, lambda m: True)

        if result:
            folder, actual_sets, used_children = result
            print(f"Агрегация завершена: {folder}, наборов: {actual_sets}, вложений: {used_children}")

            # 3. Проверка результатов
            assert actual_sets == 3
            assert used_children == 6
            assert os.path.isdir(folder)

            files = os.listdir(folder)
            assert len(files) == 3

            # Проверка санитизации имени файла (P3/Special* -> P3_Special_)
            expected_filename = "P3_Special_.txt"
            assert expected_filename in files

            # Проверка содержимого одного файла
            with open(os.path.join(folder, "P1.txt"), "r", encoding="utf-8") as f:
                content = f.read().splitlines()
                assert content == ["P1", "C1", "C2"]

            print("Тест успешно пройден!")

            # Очистка
            shutil.rmtree(folder)
        else:
            print("Ошибка: агрегация вернула None")
            exit(1)

    except Exception as e:
        print(f"Тест провалился с ошибкой: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
    finally:
        # Удаление временных файлов
        for f in [parent_file, child_file1, child_file2]:
            if os.path.exists(f):
                os.remove(f)

if __name__ == "__main__":
    test_aggregation()
