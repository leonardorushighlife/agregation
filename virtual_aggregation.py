"""
Скрипт для виртуальной агрегации кодов маркировки.
Позволяет выбрать файл с кодами наборов (родители) и файлы с кодами вложений (дети),
задать количество вложений на один набор и сформировать индивидуальные TXT файлы.

Инструкция по сборке в EXE:
1. Установите PyInstaller: pip install pyinstaller
2. Выполните команду: pyinstaller --noconsole --onefile virtual_aggregation.py
"""

import os
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from datetime import datetime
import re

def sanitize_filename(name):
    """Удаляет недопустимые символы из имени файла."""
    return re.sub(r'[\\/*?:"<>|]', '_', name).strip()

def read_codes(filepath):
    """Читает коды из файла, пробуя различные кодировки."""
    encodings = ['utf-8-sig', 'utf-16', 'utf-8', 'cp1251']
    for enc in encodings:
        try:
            with open(filepath, 'r', encoding=enc) as f:
                codes = [line.strip() for line in f if line.strip()]
            return codes
        except (UnicodeDecodeError, UnicodeError):
            continue
    raise Exception(f"Не удалось прочитать файл {filepath}. Проверьте кодировку.")

def perform_aggregation(parent_codes, child_codes, count_per_parent, output_dir):
    """Выполняет агрегацию и сохраняет файлы."""
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    total_parents = len(parent_codes)
    total_children_needed = total_parents * count_per_parent

    if len(child_codes) < total_children_needed:
        actual_sets = len(child_codes) // count_per_parent
        confirm = messagebox.askyesno(
            "Предупреждение",
            f"Кодов вложений ({len(child_codes)}) недостаточно для всех наборов ({total_parents}).\n"
            f"Будет создано только {actual_sets} полных наборов. Продолжить?"
        )
        if not confirm:
            return False
        parent_codes = parent_codes[:actual_sets]

    used_filenames = {}

    for i, p_code in enumerate(parent_codes):
        start_idx = i * count_per_parent
        end_idx = start_idx + count_per_parent
        current_children = child_codes[start_idx:end_idx]

        base_name = sanitize_filename(p_code)
        filename = f"{base_name}.txt"

        # Обработка дубликатов имен файлов
        if filename in used_filenames:
            used_filenames[filename] += 1
            filename = f"{base_name}_{used_filenames[filename]}.txt"
        else:
            used_filenames[filename] = 0

        file_path = os.path.join(output_dir, filename)

        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(p_code + '\n')
            for c_code in current_children:
                f.write(c_code + '\n')

    return True

class AggregationApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Виртуальная агрегация")
        self.root.geometry("600x450")

        self.parent_file = ""
        self.child_files = []

        self.create_widgets()

    def create_widgets(self):
        # Выбор файла родителей
        tk.Label(self.root, text="Файл с кодами наборов (родители):", font=("Arial", 10, "bold")).pack(pady=(10, 0))
        self.lbl_parent = tk.Label(self.root, text="Файл не выбран", fg="gray")
        self.lbl_parent.pack()
        tk.Button(self.root, text="Выбрать файл родителей", command=self.select_parent_file).pack(pady=5)

        # Выбор файлов детей
        tk.Label(self.root, text="Файлы с кодами вложений (дети):", font=("Arial", 10, "bold")).pack(pady=(15, 0))
        self.lbl_children = tk.Label(self.root, text="Файлы не выбраны", fg="gray", wraplength=500)
        self.lbl_children.pack()
        tk.Button(self.root, text="Выбрать файлы детей", command=self.select_child_files).pack(pady=5)

        # Количество вложений
        tk.Label(self.root, text="Количество вложений в один набор:", font=("Arial", 10, "bold")).pack(pady=(15, 0))
        self.ent_count = tk.Entry(self.root, justify="center")
        self.ent_count.insert(0, "4")
        self.ent_count.pack(pady=5)

        # Кнопка старта
        self.btn_run = tk.Button(
            self.root,
            text="НАЧАТЬ АГРЕГАЦИЮ",
            command=self.run_aggregation,
            bg="green",
            fg="white",
            font=("Arial", 12, "bold"),
            height=2,
            width=25
        )
        self.btn_run.pack(pady=30)

    def select_parent_file(self):
        path = filedialog.askopenfilename(filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if path:
            self.parent_file = path
            self.lbl_parent.config(text=os.path.basename(path), fg="black")

    def select_child_files(self):
        paths = filedialog.askopenfilenames(filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if paths:
            self.child_files = list(paths)
            names = ", ".join([os.path.basename(p) for p in paths])
            if len(names) > 60:
                names = names[:57] + "..."
            self.lbl_children.config(text=names, fg="black")

    def run_aggregation(self):
        if not self.parent_file:
            messagebox.showerror("Ошибка", "Выберите файл с кодами наборов!")
            return
        if not self.child_files:
            messagebox.showerror("Ошибка", "Выберите файлы с кодами вложений!")
            return

        try:
            count = int(self.ent_count.get())
            if count <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Ошибка", "Введите корректное число вложений!")
            return

        try:
            parent_codes = read_codes(self.parent_file)
            child_codes = []
            for f in self.child_files:
                child_codes.extend(read_codes(f))

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_dir = f"aggregation_results_{timestamp}"

            success = perform_aggregation(parent_codes, child_codes, count, output_dir)

            if success:
                messagebox.showinfo("Готово", f"Агрегация завершена!\nРезультаты в папке: {output_dir}")
        except Exception as e:
            messagebox.showerror("Ошибка", f"Произошла ошибка: {str(e)}")

if __name__ == "__main__":
    root = tk.Tk()
    app = AggregationApp(root)
    root.mainloop()
