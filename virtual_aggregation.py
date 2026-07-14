"""
Инструкция по сборке в EXE:
1. Установите PyInstaller: pip install pyinstaller
2. Соберите проект: pyinstaller --noconsole --onefile virtual_aggregation.py
"""

import os
import re
import datetime
import tkinter as tk
from tkinter import filedialog, messagebox

def sanitize_filename(filename):
    """Очищает имя файла от недопустимых символов."""
    return re.sub(r'[\\/*?:"<>|]', "_", filename)

def read_codes(file_paths):
    """Считывает коды из списка файлов, удаляя лишние пробелы и пустые строки."""
    codes = []
    if isinstance(file_paths, str):
        file_paths = [file_paths]

    for path in file_paths:
        try:
            with open(path, 'r', encoding='utf-8') as f:
                for line in f:
                    code = line.strip()
                    if code:
                        codes.append(code)
        except UnicodeDecodeError:
            # Попытка прочитать в другой кодировке, если utf-8 не сработал
            with open(path, 'r', encoding='windows-1251') as f:
                for line in f:
                    code = line.strip()
                    if code:
                        codes.append(code)
    return codes

def perform_aggregation(parent_file, child_files, count_per_parent, progress_callback=None):
    """Основная логика агрегации."""
    parents = read_codes(parent_file)
    children = read_codes(child_files)

    if not parents:
        raise ValueError("Файл с кодами наборов пуст.")
    if not children:
        raise ValueError("Файлы с кодами вложений пусты.")

    total_needed = len(parents) * count_per_parent
    if len(children) < total_needed:
        if not messagebox.askyesno("Предупреждение",
                                   f"Кодов вложений ({len(children)}) меньше, чем требуется ({total_needed}).\n"
                                   f"Будет создано только {len(children) // count_per_parent} полных наборов. Продолжить?"):
            return None

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = f"aggregation_results_{timestamp}"
    os.makedirs(output_dir, exist_ok=True)

    count = 0
    for i, parent_code in enumerate(parents):
        start_idx = i * count_per_parent
        end_idx = start_idx + count_per_parent

        if end_idx > len(children):
            break

        set_children = children[start_idx:end_idx]

        safe_name = sanitize_filename(parent_code)
        file_path = os.path.join(output_dir, f"{safe_name}.txt")

        # Если файл уже существует (например, дубликат кода), добавим индекс
        idx = 1
        original_file_path = file_path
        while os.path.exists(file_path):
            file_path = f"{original_file_path[:-4]}_{idx}.txt"
            idx += 1

        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(parent_code + "\n")
            for child in set_children:
                f.write(child + "\n")

        count += 1
        if progress_callback:
            progress_callback(i + 1, len(parents))

    return output_dir, count

class AggregationApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Виртуальная Агрегация")
        self.root.geometry("500x350")

        self.parent_file = ""
        self.child_files = []

        # UI Элементы
        tk.Label(root, text="Файл с кодами наборов (родители):").pack(pady=(10, 0))
        self.lbl_parent = tk.Label(root, text="Не выбран", fg="gray")
        self.lbl_parent.pack()
        tk.Button(root, text="Выбрать файл", command=self.select_parent_file).pack(pady=5)

        tk.Label(root, text="Количество вложений на один набор:").pack(pady=(10, 0))
        self.entry_count = tk.Entry(root)
        self.entry_count.insert(0, "1")
        self.entry_count.pack(pady=5)

        tk.Label(root, text="Файлы с кодами вложений (дети):").pack(pady=(10, 0))
        self.lbl_children = tk.Label(root, text="Выбрано: 0", fg="gray")
        self.lbl_children.pack()
        tk.Button(root, text="Выбрать файлы", command=self.select_child_files).pack(pady=5)

        self.btn_run = tk.Button(root, text="ЗАПУСТИТЬ АГРЕГАЦИЮ", command=self.run, bg="green", fg="white", font=("Arial", 10, "bold"))
        self.btn_run.pack(pady=20)

    def select_parent_file(self):
        self.parent_file = filedialog.askopenfilename(filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if self.parent_file:
            self.lbl_parent.config(text=os.path.basename(self.parent_file), fg="black")

    def select_child_files(self):
        self.child_files = filedialog.askopenfilenames(filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if self.child_files:
            self.lbl_children.config(text=f"Выбрано: {len(self.child_files)}", fg="black")

    def run(self):
        if not self.parent_file:
            messagebox.showerror("Ошибка", "Выберите файл с кодами наборов")
            return
        if not self.child_files:
            messagebox.showerror("Ошибка", "Выберите файлы с кодами вложений")
            return

        try:
            count_per_parent = int(self.entry_count.get())
            if count_per_parent <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Ошибка", "Введите корректное число вложений")
            return

        try:
            result = perform_aggregation(self.parent_file, list(self.child_files), count_per_parent)
            if result:
                output_dir, count = result
                messagebox.showinfo("Успех", f"Агрегация завершена!\nСоздано наборов: {count}\nРезультаты в папке: {output_dir}")
        except Exception as e:
            messagebox.showerror("Ошибка", f"Произошла ошибка: {str(e)}")

if __name__ == "__main__":
    root = tk.Tk()
    app = AggregationApp(root)
    root.mainloop()
