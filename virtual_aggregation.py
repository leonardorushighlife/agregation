"""
Скрипт для виртуальной агрегации кодов маркировки.

Инструкция по сборке в EXE:
Для сборки этого скрипта в автономный исполняемый файл (EXE) для Windows 8, 10, 11 выполните следующую команду:
pyinstaller --noconsole --onefile virtual_aggregation.py
"""

import os
import sys
from datetime import datetime
import traceback
import re

try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
    HAS_TKINTER = True
except ImportError:
    HAS_TKINTER = False
    tk = None

def read_codes(filepaths):
    """Считывает коды из списка файлов с поддержкой различных кодировок."""
    if isinstance(filepaths, str):
        filepaths = [filepaths]

    codes = []
    # Порядок кодировок для перебора: UTF-8-SIG, UTF-16, UTF-8, CP1251
    encodings = ["utf-8-sig", "utf-16", "utf-8", "cp1251"]

    for path in filepaths:
        success = False
        for enc in encodings:
            try:
                with open(path, "r", encoding=enc) as f:
                    # Считываем строки, убираем пробелы и пустые строки
                    file_codes = [line.strip() for line in f if line.strip()]
                    codes.extend(file_codes)
                success = True
                break
            except (UnicodeDecodeError, UnicodeError):
                continue
        if not success:
            raise Exception(f"Не удалось прочитать файл {path} в поддерживаемых кодировках.")
    return codes

def sanitize_filename(filename):
    """Очищает строку от символов, недопустимых в именах файлов Windows."""
    # Заменяем символы \ / : * ? " < > | на подчеркивание
    return re.sub(r'[\\/:*?"<>|]', '_', filename)

def perform_aggregation(parent_codes, child_codes, count_per_parent, confirm_callback=None):
    """Основная логика агрегации."""
    required_children = len(parent_codes) * count_per_parent

    if len(child_codes) < required_children:
        # Избегаем деления на ноль, если count_per_parent неверен, но мы валидируем его раньше
        actual_sets = len(child_codes) // count_per_parent if count_per_parent > 0 else 0
        if confirm_callback:
            if not confirm_callback(len(child_codes), required_children, actual_sets):
                return None
        parent_codes = parent_codes[:actual_sets]

    # Создаем папку для результатов
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = f"aggregation_results_{timestamp}"
    os.makedirs(output_dir, exist_ok=True)

    created_files = []
    child_idx = 0
    filename_counts = {}

    for parent in parent_codes:
        sanitized = sanitize_filename(parent)

        # Обработка дубликатов имен файлов
        if sanitized in filename_counts:
            filename_counts[sanitized] += 1
            filename = f"{sanitized}_{filename_counts[sanitized]}.txt"
        else:
            filename_counts[sanitized] = 0
            filename = f"{sanitized}.txt"

        filepath = os.path.join(output_dir, filename)

        # Файлы кодов наборов создаются в формате UTF-8 без BOM
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(parent + "\n")
            for _ in range(count_per_parent):
                f.write(child_codes[child_idx] + "\n")
                child_idx += 1

        created_files.append(filepath)

    return output_dir, len(created_files)

if HAS_TKINTER:
    class VirtualAggregationApp:
        def __init__(self, root):
            self.root = root
            self.root.title("Виртуальная агрегация")
            self.root.geometry("600x400")

            self.parent_file = ""
            self.child_files = []

            self.create_widgets()

        def create_widgets(self):
            # Фрейм для выбора файлов
            frame_files = ttk.LabelFrame(self.root, text="Выбор файлов", padding=10)
            frame_files.pack(fill="x", padx=10, pady=5)

            ttk.Button(frame_files, text="Выбрать файл с кодами набора (родитель)",
                       command=self.select_parent_file).pack(fill="x", pady=2)
            self.lbl_parent = ttk.Label(frame_files, text="Файл не выбран", foreground="gray")
            self.lbl_parent.pack(fill="x", pady=2)

            ttk.Button(frame_files, text="Выбрать файлы с кодами вложений (дети)",
                       command=self.select_child_files).pack(fill="x", pady=2)
            self.lbl_children = ttk.Label(frame_files, text="Файлы не выбраны", foreground="gray")
            self.lbl_children.pack(fill="x", pady=2)

            # Фрейм для настроек
            frame_settings = ttk.LabelFrame(self.root, text="Настройки", padding=10)
            frame_settings.pack(fill="x", padx=10, pady=5)

            ttk.Label(frame_settings, text="Количество вложений в каждый набор:").pack(side="left", padx=5)
            self.entry_count = ttk.Entry(frame_settings, width=10)
            self.entry_count.insert(0, "4")  # По умолчанию 4 вложения, как просил пользователь
            self.entry_count.pack(side="left", padx=5)

            # Кнопка запуска
            ttk.Button(self.root, text="Выполнить агрегацию",
                       command=self.run_aggregation).pack(pady=20)

        def select_parent_file(self):
            file = filedialog.askopenfilename(filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
            if file:
                self.parent_file = file
                self.lbl_parent.config(text=os.path.basename(file), foreground="black")

        def select_child_files(self):
            files = filedialog.askopenfilenames(filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
            if files:
                self.child_files = list(files)
                self.lbl_children.config(text=f"Выбрано файлов: {len(files)}", foreground="black")

        def confirm_partial(self, available, required, actual):
            return messagebox.askyesno(
                "Внимание",
                f"Кодов вложений ({available}) меньше чем требуется ({required}).\n"
                f"Будет создано только {actual} наборов.\nПродолжить?"
            )

        def run_aggregation(self):
            try:
                if not self.parent_file:
                    messagebox.showwarning("Ошибка", "Выберите файл с родительскими кодами")
                    return
                if not self.child_files:
                    messagebox.showwarning("Ошибка", "Выберите файлы с кодами вложений")
                    return

                try:
                    count = int(self.entry_count.get())
                    if count <= 0: raise ValueError
                except ValueError:
                    messagebox.showwarning("Ошибка", "Введите корректное число вложений (больше 0)")
                    return

                parents = read_codes(self.parent_file)
                children = read_codes(self.child_files)

                if not parents:
                    messagebox.showwarning("Ошибка", "Файл родителей пуст")
                    return
                if not children:
                    messagebox.showwarning("Ошибка", "Файлы вложений пусты")
                    return

                result = perform_aggregation(parents, children, count, self.confirm_partial)

                if result:
                    output_dir, total = result
                    messagebox.showinfo("Успех", f"Агрегация завершена!\nСоздано наборов: {total}\nПапка: {output_dir}")

            except Exception:
                messagebox.showerror("Ошибка", traceback.format_exc())

if __name__ == "__main__":
    if HAS_TKINTER:
        try:
            root = tk.Tk()
            app = VirtualAggregationApp(root)
            root.mainloop()
        except Exception:
            # На случай если ошибка произойдет до инициализации GUI
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror("Критическая ошибка", traceback.format_exc())
    else:
        print("Ошибка: Графическая среда (Tkinter) недоступна.")
        sys.exit(1)
