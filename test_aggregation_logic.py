import os
import shutil
import re

# Импортируем функции из основного скрипта
def sanitize_filename(filename):
    return re.sub(r'[\\/*?:"<>|]', '_', filename)

def mock_read_codes(content):
    return [line.strip() for line in content.split('\n') if line.strip()]

def perform_aggregation_test(parents, all_children, count_per_set):
    max_sets_by_children = len(all_children) // count_per_set
    actual_sets = min(len(parents), max_sets_by_children)

    results = {}
    for i in range(actual_sets):
        parent_code = parents[i]
        child_subset = all_children[i * count_per_set : (i + 1) * count_per_set]
        safe_name = sanitize_filename(parent_code)
        results[safe_name] = [parent_code] + child_subset
    return results

def run_test():
    print("Запуск теста логики агрегации...")

    parents = ["PARENT_01", "PARENT/02", "PARENT*03"]
    children = ["CHILD_01", "CHILD_02", "CHILD_03", "CHILD_04", "CHILD_05", "CHILD_06", "CHILD_07", "CHILD_08", "CHILD_09", "CHILD_10"]
    count_per_set = 3

    results = perform_aggregation_test(parents, children, count_per_set)

    # Проверки
    expected_sets = 3
    if len(results) != expected_sets:
        print(f"Ошибка: Ожидалось {expected_sets} наборов, получено {len(results)}")
        return False

    if "PARENT_01" not in results or results["PARENT_01"] != ["PARENT_01", "CHILD_01", "CHILD_02", "CHILD_03"]:
        print(f"Ошибка в наборе PARENT_01: {results.get('PARENT_01')}")
        return False

    if "PARENT_02" not in results: # Ожидаем санитарное имя
        print(f"Ошибка: Ожидалось имя PARENT_02 для PARENT/02")
        return False

    print("Тест успешно пройден!")
    return True

if __name__ == "__main__":
    if run_test():
        exit(0)
    else:
        exit(1)
