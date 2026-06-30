"""
Скрипт для виртуальной агрегации кодов маркировки.
Позволяет объединить коды наборов с кодами вложений.

Инструкция для сборки в EXE:
1. Установите PyInstaller: pip install pyinstaller
2. Соберите проект: pyinstaller --noconsole --onefile virtual_aggregation.py
"""

import os
import sys
import tkinter as tk
from tkinter import filedialog, messagebox
from datetime import datetime
import re

class VirtualAggregationApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Виртуальная агрегация")
        self.root.geometry("600x450")

        self.parent_file = ""
        self.child_files = []

        # UI Elements
        self.setup_ui()

    def setup_ui(self):
        # Frame for parent file
        tk.Label(self.root, text="Коды маркировки наборов (родитель):", font=("Arial", 10, "bold")).pack(pady=(20, 5))
        self.btn_parent = tk.Button(self.root, text="Выбрать файл с наборами", command=self.select_parent_file, width=40)
        self.btn_parent.pack()
        self.lbl_parent = tk.Label(self.root, text="Файл не выбран", fg="grey")
        self.lbl_parent.pack(pady=5)

        # Frame for child files
        tk.Label(self.root, text="Коды маркировки вложений (дети):", font=("Arial", 10, "bold")).pack(pady=(15, 5))
        self.btn_children = tk.Button(self.root, text="Выбрать файлы с вложениями", command=self.select_child_files, width=40)
        self.btn_children.pack()
        self.lbl_children = tk.Label(self.root, text="Файлы не выбраны", fg="grey")
        self.lbl_children.pack(pady=5)

        # Count of attachments
        tk.Label(self.root, text="Количество вложений в один набор:", font=("Arial", 10, "bold")).pack(pady=(15, 5))
        self.entry_count = tk.Entry(self.root, width=10, justify="center")
        self.entry_count.insert(0, "1")
        self.entry_count.pack()

        # Start button
        self.btn_start = tk.Button(self.root, text="Начать агрегацию", command=self.start_aggregation,
                                   bg="#4CAF50", fg="white", font=("Arial", 12, "bold"), height=2, width=20)
        self.btn_start.pack(pady=30)

    def select_parent_file(self):
        file = filedialog.askopenfilename(title="Выберите файл с кодами наборов", filetypes=[("Text files", "*.txt")])
        if file:
            self.parent_file = file
            self.lbl_parent.config(text=os.path.basename(file), fg="black")

    def select_child_files(self):
        files = filedialog.askopenfilenames(title="Выберите файлы с кодами вложений", filetypes=[("Text files", "*.txt")])
        if files:
            self.child_files = list(files)
            count = len(self.child_files)
            self.lbl_children.config(text=f"Выбрано файлов: {count}", fg="black")

    def start_aggregation(self):
        # Check inputs
        if not self.parent_file:
            messagebox.showerror("Ошибка", "Выберите файл с кодами наборов!")
            return
        if not self.child_files:
            messagebox.showerror("Ошибка", "Выберите файлы с вложениями!")
            return

        try:
            count_per_parent = int(self.entry_count.get())
            if count_per_parent <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Ошибка", "Введите корректное число вложений (больше 0)!")
            return

        # Perform aggregation
        try:
            def ask_confirmation(n_children, n_parents, actual_sets):
                return messagebox.askyesno("Предупреждение",
                                   f"Вложений ({n_children}) недостаточно для всех наборов ({n_parents}).\n"
                                   f"Будет собрано наборов: {actual_sets}.\nПродолжить?")

            result_folder = perform_aggregation(
                self.parent_file,
                self.child_files,
                count_per_parent,
                status_callback=ask_confirmation
            )
            messagebox.showinfo("Готово", f"Агрегация завершена!\nРезультаты сохранены в папку:\n{result_folder}")
        except Exception as e:
            messagebox.showerror("Ошибка", f"Произошла ошибка при агрегации:\n{str(e)}")

def sanitize_filename(filename):
    """Очищает строку для использования в качестве имени файла."""
    return re.sub(r'[\\/*?:"<>|]', "_", filename)

def read_codes(file_path):
    """Считывает коды из файла, пробуя разные кодировки."""
    encodings = ['utf-8-sig', 'utf-16', 'utf-8', 'cp1251']
    for enc in encodings:
        try:
            with open(file_path, 'r', encoding=enc) as f:
                codes = [line.strip() for line in f if line.strip()]
                return codes
        except (UnicodeDecodeError, UnicodeError):
            continue
    raise Exception(f"Не удалось прочитать файл {file_path} (неизвестная кодировка)")

def perform_aggregation(parent_file, child_files, count_per_parent, status_callback=None):
    # Read parents
    parents = read_codes(parent_file)
    if not parents:
        raise Exception("Файл с кодами наборов пуст!")

    # Read all children from all selected files
    all_children = []
    for cf in child_files:
        all_children.extend(read_codes(cf))

    if not all_children:
        raise Exception("Файлы с кодами вложений пусты!")

    required_children = len(parents) * count_per_parent
    if len(all_children) < required_children:
        actual_sets = len(all_children) // count_per_parent
        if status_callback:
            if not status_callback(len(all_children), len(parents), actual_sets):
                raise Exception("Отменено пользователем")
        else:
            # If no callback, we just proceed with what we have or raise error?
            # For headless tests we might want to just proceed.
            pass
        parents = parents[:actual_sets]

    # Create result folder
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = f"aggregation_results_{timestamp}"
    os.makedirs(output_dir, exist_ok=True)

    # Process
    child_idx = 0
    for parent_code in parents:
        safe_name = sanitize_filename(parent_code)
        output_file = os.path.join(output_dir, f"{safe_name}.txt")

        # Take N children
        set_children = all_children[child_idx : child_idx + count_per_parent]
        child_idx += count_per_parent

        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(parent_code + "\n")
            for c in set_children:
                f.write(c + "\n")

    return os.path.abspath(output_dir)

if __name__ == "__main__":
    try:
        root = tk.Tk()
        app = VirtualAggregationApp(root)
        root.mainloop()
    except Exception as e:
        import traceback
        error_msg = traceback.format_exc()
        # Create a temporary root if needed to show error
        temp_root = tk.Tk()
        temp_root.withdraw()
        messagebox.showerror("Критическая ошибка", f"Приложение упало:\n{error_msg}")
