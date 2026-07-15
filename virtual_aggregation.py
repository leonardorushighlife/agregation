# Сборка в EXE:
# pyinstaller --noconsole --onefile virtual_aggregation.py

import tkinter as tk
from tkinter import filedialog, messagebox
import os
import re
from datetime import datetime
import traceback

def read_codes(filepath):
    encodings = ['utf-8-sig', 'utf-16', 'utf-8', 'cp1251']
    for enc in encodings:
        try:
            with open(filepath, 'r', encoding=enc) as f:
                return [line.strip() for line in f if line.strip()]
        except (UnicodeDecodeError, UnicodeError):
            continue
    raise Exception(f"Не удалось прочитать файл {filepath}. Проверьте кодировку.")

def sanitize_filename(name):
    # Заменяем недопустимые символы на подчеркивание
    return re.sub(r'[\\/*?:"<>|]', '_', name)

def perform_aggregation(parent_file, child_files, count_per_parent, status_callback=None, confirm_callback=None):
    parents = read_codes(parent_file)
    all_children = []
    for f in child_files:
        all_children.extend(read_codes(f))

    total_needed = len(parents) * count_per_parent
    if len(all_children) < total_needed:
        msg = f"Предупреждение: недостаточно кодов вложений.\nВсего вложений: {len(all_children)}\nТребуется для всех наборов: {total_needed}\nБудет собрано наборов: {len(all_children) // count_per_parent}"
        if confirm_callback:
            if not confirm_callback(msg):
                return
        else:
            print(msg)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = f"aggregation_results_{timestamp}"
    os.makedirs(output_dir, exist_ok=True)

    actual_sets = min(len(parents), len(all_children) // count_per_parent)

    for i in range(actual_sets):
        parent_code = parents[i]
        filename = sanitize_filename(parent_code) + ".txt"
        file_path = os.path.join(output_dir, filename)

        # Если файл уже существует (редкий случай дублирования кодов), добавим индекс
        counter = 1
        original_file_path = file_path
        while os.path.exists(file_path):
            file_path = f"{original_file_path[:-4]}_{counter}.txt"
            counter += 1

        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(parent_code + "\n")
            for j in range(count_per_parent):
                child_code = all_children[i * count_per_parent + j]
                f.write(child_code + "\n")

    return output_dir, actual_sets

class VirtualAggregationApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Виртуальная агрегация наборов")
        self.root.geometry("600x450")

        self.parent_file = ""
        self.child_files = []

        # UI Elements
        tk.Label(root, text="Виртуальная агрегация", font=("Arial", 16, "bold")).pack(pady=10)

        # Parent file selection
        self.btn_parent = tk.Button(root, text="Выбрать файл кодов наборов (родители)", command=self.select_parent_file)
        self.btn_parent.pack(pady=5)
        self.lbl_parent = tk.Label(root, text="Файл не выбран", fg="gray")
        self.lbl_parent.pack()

        # Child files selection
        self.btn_children = tk.Button(root, text="Выбрать файлы кодов вложений (дети)", command=self.select_child_files)
        self.btn_children.pack(pady=5)
        self.lbl_children = tk.Label(root, text="Файлы не выбраны", fg="gray")
        self.lbl_children.pack()

        # Attachment count
        tk.Label(root, text="Количество вложений в один набор:").pack(pady=(10, 0))
        self.ent_count = tk.Entry(root, justify="center")
        self.ent_count.insert(0, "1")
        self.ent_count.pack(pady=5)

        # Process button
        self.btn_run = tk.Button(root, text="Начать агрегацию", command=self.run_process, bg="green", fg="white", font=("Arial", 12, "bold"), height=2, width=20)
        self.btn_run.pack(pady=20)

    def select_parent_file(self):
        path = filedialog.askopenfilename(filetypes=[("Text files", "*.txt")])
        if path:
            self.parent_file = path
            self.lbl_parent.config(text=os.path.basename(path), fg="black")

    def select_child_files(self):
        paths = filedialog.askopenfilenames(filetypes=[("Text files", "*.txt")])
        if paths:
            self.child_files = list(paths)
            self.lbl_children.config(text=f"Выбрано файлов: {len(paths)}", fg="black")

    def run_process(self):
        if not self.parent_file:
            messagebox.showerror("Ошибка", "Выберите файл с кодами наборов")
            return
        if not self.child_files:
            messagebox.showerror("Ошибка", "Выберите файлы с кодами вложений")
            return

        try:
            count = int(self.ent_count.get())
            if count <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Ошибка", "Введите корректное количество вложений (целое число > 0)")
            return

        # Core logic will be called here
        try:
            def confirm(msg):
                return messagebox.askyesno("Внимание", msg)

            result = perform_aggregation(
                self.parent_file,
                self.child_files,
                count,
                confirm_callback=confirm
            )

            if result:
                output_dir, actual_sets = result
                messagebox.showinfo("Успех", f"Агрегация завершена!\nСоздано наборов: {actual_sets}\nПапка: {output_dir}")
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Ошибка", f"Произошла ошибка при выполнении:\n{str(e)}")

if __name__ == "__main__":
    root = tk.Tk()
    app = VirtualAggregationApp(root)
    root.mainloop()
