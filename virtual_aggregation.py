import os
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog
from datetime import datetime
import re
import traceback

"""
ИНСТРУКЦИЯ ПО СБОРКЕ В EXE:
1. Установите PyInstaller: pip install pyinstaller
2. Выполните команду в терминале:
   pyinstaller --noconsole --onefile virtual_aggregation.py

Скрипт будет упакован в один .exe файл в папке dist.
"""

def sanitize_filename(filename):
    """Удаляет недопустимые символы для имен файлов Windows."""
    return re.sub(r'[\\/*?:"<>|]', "_", filename)

def read_codes(filepath):
    """Читает коды из файла с поддержкой разных кодировок."""
    encodings = ['utf-8-sig', 'utf-16', 'utf-8', 'cp1251']
    for encoding in encodings:
        try:
            with open(filepath, 'r', encoding=encoding) as f:
                return [line.strip() for line in f if line.strip()]
        except (UnicodeDecodeError, UnicodeError):
            continue
    raise ValueError(f"Не удалось прочитать файл {filepath} в поддерживаемых кодировках.")

def perform_aggregation(parent_file, child_files, count_per_parent, confirm_callback=None):
    """
    Выполняет логику агрегации.

    :param parent_file: Путь к файлу с кодами наборов.
    :param child_files: Список путей к файлам с кодами вложений.
    :param count_per_parent: Количество вложений на один набор.
    :param confirm_callback: Функция для подтверждения продолжения (если вложений не хватает).
    :return: (путь к папке, количество созданных файлов) или None
    """
    try:
        parents = read_codes(parent_file)
        all_children = []
        for cf in child_files:
            all_children.extend(read_codes(cf))

        if not parents:
            raise ValueError("Файл с кодами наборов пуст.")
        if not all_children:
            raise ValueError("Файлы с кодами вложений пусты.")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = f"aggregation_results_{timestamp}"
        os.makedirs(output_dir, exist_ok=True)

        total_needed = len(parents) * count_per_parent
        if len(all_children) < total_needed:
            actual_sets = len(all_children) // count_per_parent
            msg = f"Вложений ({len(all_children)}) хватит только на {actual_sets} из {len(parents)} наборов. Продолжить?"
            if confirm_callback:
                if not confirm_callback(msg):
                    return None
            else:
                print(f"ВНИМАНИЕ: {msg}")
            parents = parents[:actual_sets]

        count = 0
        for i, parent in enumerate(parents):
            start_idx = i * count_per_parent
            end_idx = start_idx + count_per_parent
            current_children = all_children[start_idx:end_idx]

            safe_name = sanitize_filename(parent)
            file_path = os.path.join(output_dir, f"{safe_name}.txt")

            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(parent + "\n")
                for child in current_children:
                    f.write(child + "\n")
            count += 1

        return output_dir, count
    except Exception as e:
        # Возвращаем ошибку вверх
        raise e

def main():
    # Создаем скрытое корневое окно для диалогов
    root = tk.Tk()
    root.withdraw()

    try:
        # 1. Выбор файла родительских кодов
        parent_file = filedialog.askopenfilename(
            title="Выберите файл с кодами МАРКИРОВКИ НА НАБОР",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        if not parent_file:
            return

        # 2. Ввод количества вложений
        count_per_parent = simpledialog.askinteger(
            "Количество вложений",
            "Введите количество вложений в каждый набор:",
            initialvalue=1, minvalue=1
        )
        if not count_per_parent:
            return

        # 3. Выбор файлов дочерних кодов
        child_files = filedialog.askopenfilenames(
            title="Выберите файлы с кодами МАРКИРОВКИ ВЛОЖЕНИЙ",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        if not child_files:
            return

        # Колбэк для подтверждения
        def gui_confirm(msg):
            return messagebox.askyesno("Подтверждение", msg)

        # Выполнение агрегации
        result = perform_aggregation(parent_file, list(child_files), count_per_parent, gui_confirm)

        if result:
            output_dir, count = result
            messagebox.showinfo("Успех", f"Агрегация завершена!\n\nСоздано наборов: {count}\nРезультаты сохранены в папку:\n{os.path.abspath(output_dir)}")

    except Exception:
        error_msg = traceback.format_exc()
        messagebox.showerror("Ошибка", f"Произошла ошибка при выполнении:\n\n{error_msg}")
    finally:
        root.destroy()

if __name__ == "__main__":
    main()
