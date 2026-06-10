import os
import re
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from datetime import datetime

def sanitize_filename(filename):
    """Удаляет недопустимые символы для имен файлов Windows."""
    return re.sub(r'[\\/*?:"<>|]', "", filename)

def read_file_with_encoding(filepath):
    """Пытается прочитать файл с разными кодировками."""
    encodings = ['utf-8-sig', 'utf-8', 'cp1251', 'utf-16']
    for enc in encodings:
        try:
            with open(filepath, 'r', encoding=enc) as f:
                return [line.strip() for line in f if line.strip()]
        except (UnicodeDecodeError, LookupError):
            continue
    raise Exception(f"Не удалось определить кодировку файла: {filepath}")

def perform_aggregation(parent_codes, child_codes, count_per_set, output_dir):
    """Логика агрегации кодов."""
    if not parent_codes:
        raise Exception("Список родительских кодов пуст")
    if not child_codes:
        raise Exception("Список вложений пуст")

    total_needed = len(parent_codes) * count_per_set
    if len(child_codes) < total_needed:
        actual_sets = len(child_codes) // count_per_set
        if actual_sets == 0:
             raise Exception(f"Недостаточно вложений для создания даже одного набора. Нужно {count_per_set}, есть {len(child_codes)}.")
        parent_codes = parent_codes[:actual_sets]
        messagebox.showwarning("Внимание", f"Вложений ({len(child_codes)}) хватит только на {actual_sets} полных наборов. Будет обработано {actual_sets} наборов.")

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    for i, parent_code in enumerate(parent_codes):
        start_idx = i * count_per_set
        end_idx = start_idx + count_per_set
        current_children = child_codes[start_idx:end_idx]

        safe_name = sanitize_filename(parent_code)
        file_path = os.path.join(output_dir, f"{safe_name}.txt")

        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(parent_code + "\n")
            for child in current_children:
                f.write(child + "\n")

    return len(parent_codes)

class AggregationApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Виртуальная агрегация наборов")
        self.root.geometry("600x450")

        self.parent_file = ""
        self.child_files = []

        style = ttk.Style()
        style.configure("TButton", font=("Arial", 10))
        style.configure("TLabel", font=("Arial", 10))

        frame = ttk.Frame(root, padding="20")
        frame.pack(expand=True, fill="both")

        # Выбор файла наборов (родителей)
        ttk.Label(frame, text="1. Выберите файл с кодами наборов (родители):").pack(anchor="w", pady=(0, 5))
        btn_parent = ttk.Button(frame, text="Выбрать файл", command=self.select_parent_file)
        btn_parent.pack(fill="x", pady=(0, 10))
        self.lbl_parent = ttk.Label(frame, text="Файл не выбран", foreground="gray")
        self.lbl_parent.pack(anchor="w", pady=(0, 15))

        # Выбор файлов вложений (детей)
        ttk.Label(frame, text="2. Выберите файлы с кодами вложений (дети):").pack(anchor="w", pady=(0, 5))
        btn_child = ttk.Button(frame, text="Выбрать файлы", command=self.select_child_files)
        btn_child.pack(fill="x", pady=(0, 10))
        self.lbl_child = ttk.Label(frame, text="Файлы не выбраны", foreground="gray")
        self.lbl_child.pack(anchor="w", pady=(0, 15))

        # Количество вложений
        ttk.Label(frame, text="3. Количество вложений в один набор:").pack(anchor="w", pady=(0, 5))
        self.entry_count = ttk.Entry(frame)
        self.entry_count.insert(0, "1")
        self.entry_count.pack(fill="x", pady=(0, 20))

        # Кнопка Запуск
        btn_run = ttk.Button(frame, text="ВЫПОЛНИТЬ АГРЕГАЦИЮ", command=self.run_aggregation)
        btn_run.pack(fill="x", ipady=10)

    def select_parent_file(self):
        file = filedialog.askopenfilename(filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if file:
            self.parent_file = file
            self.lbl_parent.config(text=os.path.basename(file), foreground="black")

    def select_child_files(self):
        files = filedialog.askopenfilenames(filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if files:
            self.child_files = list(files)
            self.lbl_child.config(text=f"Выбрано файлов: {len(files)}", foreground="black")

    def run_aggregation(self):
        if not self.parent_file:
            messagebox.showerror("Ошибка", "Выберите файл с родительскими кодами")
            return
        if not self.child_files:
            messagebox.showerror("Ошибка", "Выберите хотя бы один файл с вложениями")
            return

        try:
            count_per_set = int(self.entry_count.get())
            if count_per_set <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Ошибка", "Введите корректное число вложений (больше 0)")
            return

        try:
            parent_codes = read_file_with_encoding(self.parent_file)

            all_child_codes = []
            for cf in self.child_files:
                all_child_codes.extend(read_file_with_encoding(cf))

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_dir = f"aggregation_results_{timestamp}"

            count = perform_aggregation(parent_codes, all_child_codes, count_per_set, output_dir)

            messagebox.showinfo("Успех", f"Агрегация завершена!\nОбработано наборов: {count}\nРезультаты в папке: {output_dir}")

        except Exception as e:
            messagebox.showerror("Ошибка", str(e))

if __name__ == "__main__":
    root = tk.Tk()
    app = AggregationApp(root)
    root.mainloop()
