"""
Скрипт для виртуальной агрегации кодов маркировки.
Позволяет объединять коды вложений с кодами наборов в отдельные файлы.

Инструкция по сборке в EXE:
1. Установите PyInstaller: pip install pyinstaller
2. Соберите проект: pyinstaller --noconsole --onefile virtual_aggregation.py
"""

import os
import re
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from datetime import datetime

def sanitize_filename(filename):
    """Очистка имени файла от недопустимых символов."""
    # Ограничиваем длину имени файла и убираем запрещенные символы
    sanitized = re.sub(r'[\\/*?:"<>|]', '_', filename)
    return sanitized[:150] # Ограничение длины для безопасности

def read_codes(filepaths):
    """Чтение кодов из одного или нескольких файлов с поддержкой разных кодировок."""
    encodings = ['utf-8-sig', 'utf-16', 'utf-8', 'cp1251']
    codes = []

    if isinstance(filepaths, str):
        filepaths = [filepaths]

    for path in filepaths:
        content = None
        for enc in encodings:
            try:
                with open(path, 'r', encoding=enc) as f:
                    content = f.read().splitlines()
                break
            except (UnicodeDecodeError, UnicodeError):
                continue

        if content is not None:
            # Очистка от пустых строк и пробелов
            codes.extend([line.strip() for line in content if line.strip()])
        else:
            raise Exception(f"Не удалось прочитать файл {path}. Проверьте кодировку.")

    return codes

def perform_aggregation(parent_file, child_files, count_per_parent, progress_callback=None, confirm_callback=None):
    """Основная логика агрегации."""
    parents = read_codes(parent_file)
    children = read_codes(child_files)

    if not parents:
        raise Exception("Файл с кодами наборов пуст.")
    if not children:
        raise Exception("Файлы с кодами вложений пусты.")

    total_required_children = len(parents) * count_per_parent

    if len(children) < total_required_children:
        actual_sets = len(children) // count_per_parent
        if actual_sets == 0:
            raise Exception(f"Недостаточно кодов вложений даже для одного набора.\nВсего вложений: {len(children)}, требуется на набор: {count_per_parent}")

        msg = f"Предупреждение: Недостаточно кодов вложений.\n" \
              f"Доступно вложений: {len(children)}\n" \
              f"Требуется для всех наборов ({len(parents)} шт.): {total_required_children}\n" \
              f"Будет создано полных наборов: {actual_sets}\n\n" \
              f"Продолжить?"
        if confirm_callback and not confirm_callback(msg):
            return None

        # Ограничиваем количество родителей, если вложений мало
        parents = parents[:actual_sets]

    # Создание папки результатов
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = f"aggregation_results_{timestamp}"
    os.makedirs(output_dir, exist_ok=True)

    count = 0
    total_parents = len(parents)
    for i, parent_code in enumerate(parents):
        start_idx = i * count_per_parent
        end_idx = start_idx + count_per_parent
        current_children = children[start_idx:end_idx]

        # Санитизация имени файла (берем часть кода, если он слишком длинный)
        safe_name = sanitize_filename(parent_code)
        filename = f"{safe_name}.txt"
        filepath = os.path.join(output_dir, filename)

        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(parent_code + '\n')
                for child in current_children:
                    f.write(child + '\n')
            count += 1
        except Exception as e:
            print(f"Ошибка при сохранении файла {filename}: {e}")

        if progress_callback:
            progress_callback(i + 1, total_parents)

    return output_dir, count

class AggregatorGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Виртуальная Агрегация")
        self.root.geometry("650x450")

        self.parent_file = ""
        self.child_files = []

        self.setup_ui()

    def setup_ui(self):
        # Файл наборов (родители)
        frame1 = tk.LabelFrame(self.root, text="Коды наборов (родители)", padx=10, pady=10)
        frame1.pack(fill="x", padx=20, pady=10)

        self.btn_parent = tk.Button(frame1, text="Выбрать файл с кодами наборов", command=self.select_parent_file)
        self.btn_parent.pack(side="left")

        self.lbl_parent = tk.Label(frame1, text="Файл не выбран", fg="gray", wraplength=400, justify="left")
        self.lbl_parent.pack(side="left", padx=10)

        # Файлы вложений (дети)
        frame2 = tk.LabelFrame(self.root, text="Коды вложений (дети)", padx=10, pady=10)
        frame2.pack(fill="x", padx=20, pady=10)

        self.btn_children = tk.Button(frame2, text="Выбрать файлы с вложениями", command=self.select_child_files)
        self.btn_children.pack(side="left")

        self.lbl_children = tk.Label(frame2, text="Файлы не выбраны", fg="gray", wraplength=400, justify="left")
        self.lbl_children.pack(side="left", padx=10)

        # Настройки
        frame3 = tk.Frame(self.root, padx=20, pady=10)
        frame3.pack(fill="x")

        tk.Label(frame3, text="Кол-во вложений в один набор:").pack(side="left")
        self.ent_count = tk.Entry(frame3, width=10)
        self.ent_count.insert(0, "1")
        self.ent_count.pack(side="left", padx=5)

        # Прогресс и запуск
        self.progress = ttk.Progressbar(self.root, orient="horizontal", length=400, mode="determinate")
        self.progress.pack(pady=20)

        self.btn_start = tk.Button(self.root, text="ЗАПУСТИТЬ АГРЕГАЦИЮ", font=("Arial", 12, "bold"),
                                  bg="#4CAF50", fg="white", height=2, command=self.start)
        self.btn_start.pack(pady=10)

    def select_parent_file(self):
        path = filedialog.askopenfilename(filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if path:
            self.parent_file = path
            self.lbl_parent.config(text=os.path.basename(path), fg="black")

    def select_child_files(self):
        paths = filedialog.askopenfilenames(filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if paths:
            self.child_files = list(paths)
            self.lbl_children.config(text=f"Выбрано файлов: {len(paths)}", fg="black")

    def update_progress(self, current, total):
        self.progress["value"] = (current / total) * 100
        self.root.update_idletasks()

    def start(self):
        if not self.parent_file:
            messagebox.showerror("Ошибка", "Выберите файл с кодами наборов!")
            return
        if not self.child_files:
            messagebox.showerror("Ошибка", "Выберите файлы с вложениями!")
            return

        try:
            count_per_parent = int(self.ent_count.get())
            if count_per_parent <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Ошибка", "Введите корректное число вложений!")
            return

        self.btn_start.config(state="disabled")
        try:
            result = perform_aggregation(
                self.parent_file,
                self.child_files,
                count_per_parent,
                progress_callback=self.update_progress,
                confirm_callback=messagebox.askyesno
            )

            if result:
                output_dir, count = result
                messagebox.showinfo("Готово", f"Успешно создано {count} наборов в папке:\n{output_dir}")
        except Exception as e:
            messagebox.showerror("Ошибка", f"Произошла ошибка: {str(e)}")
        finally:
            self.btn_start.config(state="normal")
            self.progress["value"] = 0

if __name__ == "__main__":
    root = tk.Tk()
    app = AggregatorGUI(root)
    root.mainloop()
