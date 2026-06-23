"""
Скрипт для виртуальной агрегации кодов маркировки.
Позволяет объединить коды вложений (unit) с кодами наборов (parent).

Инструкция для сборки в EXE:
1. Установите pyinstaller: pip install pyinstaller
2. Выполните команду: pyinstaller --noconsole --onefile virtual_aggregation.py
"""

import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from datetime import datetime
import re

def sanitize_filename(filename):
    """Очищает строку от символов, недопустимых в имени файла Windows."""
    return re.sub(r'[\\/*?:"<>|]', '_', filename)

def read_codes(filepaths):
    """Читает коды из одного или нескольких файлов."""
    if isinstance(filepaths, str):
        filepaths = [filepaths]

    codes = []
    for path in filepaths:
        if not os.path.exists(path):
            continue
        # Пробуем разные кодировки
        for encoding in ['utf-8-sig', 'utf-16', 'utf-8', 'cp1251']:
            try:
                with open(path, 'r', encoding=encoding) as f:
                    lines = [line.strip() for line in f if line.strip()]
                    codes.extend(lines)
                break
            except (UnicodeDecodeError, UnicodeError):
                continue
    return codes

def perform_aggregation(parent_file, child_files, count_per_set, status_callback=None):
    """
    Основная логика агрегации.
    parent_file: путь к файлу с кодами наборов.
    child_files: список путей к файлам с кодами вложений.
    count_per_set: количество вложений на один набор.
    """
    parents = read_codes(parent_file)
    children = read_codes(child_files)

    if not parents:
        raise ValueError("Файл с кодами наборов пуст или не прочитан.")
    if not children:
        raise ValueError("Файлы с кодами вложений пусты или не прочитаны.")

    try:
        count = int(count_per_set)
        if count <= 0:
            raise ValueError
    except ValueError:
        raise ValueError("Количество вложений должно быть положительным целым числом.")

    needed_children = len(parents) * count
    if len(children) < needed_children:
        actual_sets = len(children) // count
        if status_callback:
            status_callback(f"Предупреждение: Недостаточно вложений. Будет собрано {actual_sets} полных наборов из {len(parents)}.")
        parents = parents[:actual_sets]

    # Создаем папку для результатов
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = f"aggregation_results_{timestamp}"
    os.makedirs(output_dir, exist_ok=True)

    for i, parent_code in enumerate(parents):
        sanitized_name = sanitize_filename(parent_code)
        output_path = os.path.join(output_dir, f"{sanitized_name}.txt")

        # Берем порцию вложений
        start_idx = i * count
        end_idx = start_idx + count
        current_children = children[start_idx:end_idx]

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(parent_code + '\n')
            for child in current_children:
                f.write(child + '\n')

    return output_dir, len(parents)

class AggregationApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Виртуальная Агрегация")
        self.root.geometry("600x450")

        self.parent_file = ""
        self.child_files = []

        self.setup_ui()

    def setup_ui(self):
        style = ttk.Style()
        style.configure("TButton", font=("Arial", 10))
        style.configure("TLabel", font=("Arial", 10))

        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Секция родительского файла
        ttk.Label(main_frame, text="Файл с кодами НАБОРОВ (Parent):").pack(anchor="w")
        self.parent_btn = ttk.Button(main_frame, text="Выбрать файл", command=self.select_parent)
        self.parent_btn.pack(fill=tk.X, pady=(5, 15))
        self.parent_label = ttk.Label(main_frame, text="Файл не выбран", foreground="gray")
        self.parent_label.pack(anchor="w", pady=(0, 15))

        # Секция файлов вложений
        ttk.Label(main_frame, text="Файлы с кодами ВЛОЖЕНИЙ (Children):").pack(anchor="w")
        self.child_btn = ttk.Button(main_frame, text="Выбрать файлы", command=self.select_children)
        self.child_btn.pack(fill=tk.X, pady=(5, 15))
        self.child_label = ttk.Label(main_frame, text="Файлы не выбраны", foreground="gray")
        self.child_label.pack(anchor="w", pady=(0, 15))

        # Количество вложений
        count_frame = ttk.Frame(main_frame)
        count_frame.pack(fill=tk.X, pady=10)
        ttk.Label(count_frame, text="Количество вложений в один набор:").pack(side=tk.LEFT)
        self.count_entry = ttk.Entry(count_frame, width=10)
        self.count_entry.insert(0, "1")
        self.count_entry.pack(side=tk.LEFT, padx=10)

        # Кнопка запуска
        self.run_btn = ttk.Button(main_frame, text="НАЧАТЬ АГРЕГАЦИЮ", command=self.run_aggregation)
        self.run_btn.pack(fill=tk.X, pady=30)

    def select_parent(self):
        file = filedialog.askopenfilename(title="Выберите файл с кодами наборов",
                                         filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if file:
            self.parent_file = file
            self.parent_label.config(text=os.path.basename(file), foreground="black")

    def select_children(self):
        files = filedialog.askopenfilenames(title="Выберите файлы с кодами вложений",
                                           filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if files:
            self.child_files = list(files)
            self.child_label.config(text=f"Выбрано файлов: {len(files)}", foreground="black")

    def run_aggregation(self):
        if not self.parent_file:
            messagebox.showerror("Ошибка", "Выберите файл с кодами наборов!")
            return
        if not self.child_files:
            messagebox.showerror("Ошибка", "Выберите файлы с кодами вложений!")
            return

        try:
            output_dir, count = perform_aggregation(
                self.parent_file,
                self.child_files,
                self.count_entry.get(),
                status_callback=lambda m: messagebox.showwarning("Внимание", m)
            )
            messagebox.showinfo("Готово", f"Успешно создано {count} наборов.\nРезультаты в папке: {output_dir}")
        except Exception as e:
            messagebox.showerror("Ошибка", str(e))

if __name__ == "__main__":
    root = tk.Tk()
    app = AggregationApp(root)
    root.mainloop()
