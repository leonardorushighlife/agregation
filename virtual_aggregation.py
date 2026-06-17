import os
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from datetime import datetime
import traceback
import re

def sanitize_filename(name):
    # Убираем недопустимые символы для имен файлов Windows
    return re.sub(r'[\\/*?:"<>|]', "_", name)

def read_codes(filepath):
    encodings = ['utf-8-sig', 'utf-8', 'cp1251', 'utf-16']
    for enc in encodings:
        try:
            with open(filepath, 'r', encoding=enc) as f:
                return [line.strip() for line in f if line.strip()]
        except (UnicodeDecodeError, UnicodeError):
            continue
    raise Exception(f"Не удалось прочитать файл {filepath}. Попробуйте сохранить его в кодировке UTF-8.")

def perform_aggregation(parent_file, child_files, count_per_set):
    # Чтение родительских кодов
    parents = read_codes(parent_file)
    if not parents:
        raise Exception("Файл наборов пуст.")

    # Чтение дочерних кодов из всех выбранных файлов
    all_children = []
    for cf in child_files:
        all_children.extend(read_codes(cf))

    if not all_children:
        raise Exception("Файлы вложений пусты.")

    # Расчет количества возможных наборов
    num_sets_by_children = len(all_children) // count_per_set
    num_sets = min(len(parents), num_sets_by_children)

    if num_sets == 0:
        raise Exception(f"Недостаточно кодов для формирования хотя бы одного набора. Дочерних кодов: {len(all_children)}, нужно на один набор: {count_per_set}")

    # Создание папки для результатов
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = f"aggregation_results_{timestamp}"
    os.makedirs(output_dir, exist_ok=True)

    # Процесс агрегации
    for i in range(num_sets):
        parent_code = parents[i]
        start_idx = i * count_per_set
        end_idx = start_idx + count_per_set
        set_children = all_children[start_idx:end_idx]

        safe_name = sanitize_filename(parent_code)
        filename = f"{safe_name}.txt"
        filepath = os.path.join(output_dir, filename)

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(parent_code + "\n")
            for child in set_children:
                f.write(child + "\n")

    return num_sets, output_dir

class VirtualAggregationApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Виртуальная Агрегация")
        self.root.geometry("600x450")

        self.parent_file = ""
        self.child_files = []

        # Элементы интерфейса
        self.frame = tk.Frame(root, padx=20, pady=20)
        self.frame.pack(fill=tk.BOTH, expand=True)

        # Выбор родительского файла
        tk.Label(self.frame, text="1. Выберите файл с кодами наборов (родительские):", font=("Arial", 10, "bold")).pack(anchor="w")
        self.parent_btn = tk.Button(self.frame, text="Выбрать файл", command=self.select_parent_file)
        self.parent_btn.pack(fill=tk.X, pady=(5, 5))
        self.parent_label = tk.Label(self.frame, text="Файл не выбран", fg="gray", wraplength=550)
        self.parent_label.pack(anchor="w", pady=(0, 15))

        # Выбор дочерних файлов
        tk.Label(self.frame, text="2. Выберите файлы с кодами вложений (дочерние):", font=("Arial", 10, "bold")).pack(anchor="w")
        self.child_btn = tk.Button(self.frame, text="Выбрать файлы", command=self.select_child_files)
        self.child_btn.pack(fill=tk.X, pady=(5, 5))
        self.child_label = tk.Label(self.frame, text="Файлы не выбраны", fg="gray", wraplength=550)
        self.child_label.pack(anchor="w", pady=(0, 15))

        # Количество вложений
        tk.Label(self.frame, text="3. Укажите количество вложений в один набор:", font=("Arial", 10, "bold")).pack(anchor="w")
        self.count_var = tk.StringVar(value="1")
        self.count_entry = tk.Entry(self.frame, textvariable=self.count_var)
        self.count_entry.pack(fill=tk.X, pady=(5, 20))

        # Кнопка запуска
        self.process_btn = tk.Button(self.frame, text="Выполнить агрегацию", bg="#4CAF50", fg="white", font=("Arial", 12, "bold"), command=self.process)
        self.process_btn.pack(fill=tk.X, pady=10)

    def select_parent_file(self):
        file = filedialog.askopenfilename(filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if file:
            self.parent_file = file
            self.parent_label.config(text=file, fg="black")

    def select_child_files(self):
        files = filedialog.askopenfilenames(filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if files:
            self.child_files = list(files)
            self.child_label.config(text=f"Выбрано файлов: {len(files)}\n" + "\n".join([os.path.basename(f) for f in files[:5]]) + ("\n..." if len(files) > 5 else ""), fg="black")

    def process(self):
        try:
            if not self.parent_file:
                raise Exception("Выберите файл с кодами наборов.")
            if not self.child_files:
                raise Exception("Выберите файлы с кодами вложений.")

            try:
                count_per_set = int(self.count_var.get())
                if count_per_set <= 0:
                    raise ValueError()
            except ValueError:
                raise Exception("Количество вложений должно быть целым числом больше 0.")

            num_sets, output_dir = perform_aggregation(self.parent_file, self.child_files, count_per_set)

            messagebox.showinfo("Успех", f"Агрегация завершена!\nСоздано наборов: {num_sets}\nРезультаты сохранены в папку:\n{os.path.abspath(output_dir)}")

        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Ошибка", str(e))

if __name__ == "__main__":
    root = tk.Tk()
    app = VirtualAggregationApp(root)
    root.mainloop()
