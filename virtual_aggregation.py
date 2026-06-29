"""
Инструкция по сборке в EXE:
1. Установите PyInstaller: pip install pyinstaller
2. Выполните команду: pyinstaller --noconsole --onefile virtual_aggregation.py
"""

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import os
import re
from datetime import datetime
import traceback

def sanitize_filename(filename):
    """Очистка имени файла от недопустимых символов."""
    return re.sub(r'[\\/*?:"<>|]', '_', filename)

def read_codes(filepath):
    """Чтение кодов из файла с поддержкой различных кодировок."""
    encodings = ['utf-8-sig', 'utf-16', 'utf-8', 'cp1251']
    for enc in encodings:
        try:
            with open(filepath, 'r', encoding=enc) as f:
                return [line.strip() for line in f if line.strip()]
        except (UnicodeDecodeError, UnicodeError):
            continue
    raise Exception(f"Не удалось прочитать файл {filepath}. Проверьте кодировку.")

def perform_aggregation(parent_file, child_files, count_per_parent, progress_callback=None, confirm_callback=None):
    """Основная логика агрегации."""
    parents = read_codes(parent_file)
    all_children = []
    for cf in child_files:
        all_children.extend(read_codes(cf))

    total_needed = len(parents) * count_per_parent
    if len(all_children) < total_needed:
        msg = f"Предупреждение: Недостаточно вложений.\nТребуется: {total_needed}\nДоступно: {len(all_children)}\nПродолжить с частичным результатом?"
        if confirm_callback and not confirm_callback(msg):
            return None

    # Создание папки для результатов
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = f"aggregation_results_{timestamp}"
    os.makedirs(output_dir, exist_ok=True)

    actual_sets = min(len(parents), len(all_children) // count_per_parent)

    for i in range(actual_sets):
        parent_code = parents[i]
        start_idx = i * count_per_parent
        end_idx = start_idx + count_per_parent
        current_children = all_children[start_idx:end_idx]

        safe_name = sanitize_filename(parent_code)
        file_path = os.path.join(output_dir, f"{safe_name}.txt")

        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(parent_code + '\n')
            for child in current_children:
                f.write(child + '\n')

        if progress_callback:
            progress_callback(i + 1, actual_sets)

    return output_dir, actual_sets

class AggregationApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Виртуальная Агрегация")
        self.root.geometry("500x400")

        self.parent_file = ""
        self.child_files = []

        # Интерфейс
        tk.Label(root, text="Файл с кодами наборов (родители):").pack(pady=(10, 0))
        self.btn_parent = tk.Button(root, text="Выбрать файл", command=self.select_parent)
        self.btn_parent.pack(pady=5)
        self.lbl_parent = tk.Label(root, text="Не выбран", fg="gray")
        self.lbl_parent.pack()

        tk.Label(root, text="Количество вложений в один набор:").pack(pady=(15, 0))
        self.ent_count = tk.Entry(root, justify="center")
        self.ent_count.insert(0, "10")
        self.ent_count.pack(pady=5)

        tk.Label(root, text="Файлы с кодами вложений (дети):").pack(pady=(15, 0))
        self.btn_children = tk.Button(root, text="Выбрать файлы", command=self.select_children)
        self.btn_children.pack(pady=5)
        self.lbl_children = tk.Label(root, text="Выбрано: 0", fg="gray")
        self.lbl_children.pack()

        self.btn_start = tk.Button(root, text="НАЧАТЬ АГРЕГАЦИЮ", command=self.start,
                                  bg="green", fg="white", font=("Arial", 12, "bold"))
        self.btn_start.pack(pady=30)

        self.progress = ttk.Progressbar(root, orient="horizontal", length=400, mode="determinate")
        self.progress.pack(pady=10)

    def select_parent(self):
        file = filedialog.askopenfilename(filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if file:
            self.parent_file = file
            self.lbl_parent.config(text=os.path.basename(file), fg="black")

    def select_children(self):
        files = filedialog.askopenfilenames(filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if files:
            self.child_files = list(files)
            self.lbl_children.config(text=f"Выбрано: {len(files)}", fg="black")

    def start(self):
        if not self.parent_file:
            messagebox.showerror("Ошибка", "Выберите файл с кодами наборов")
            return
        if not self.child_files:
            messagebox.showerror("Ошибка", "Выберите файлы с кодами вложений")
            return

        try:
            count = int(self.ent_count.get())
            if count <= 0: raise ValueError
        except ValueError:
            messagebox.showerror("Ошибка", "Введите корректное число вложений")
            return

        def update_progress(current, total):
            self.progress["value"] = (current / total) * 100
            self.root.update_idletasks()

        def confirm(msg):
            return messagebox.askyesno("Подтверждение", msg)

        try:
            result = perform_aggregation(
                self.parent_file,
                self.child_files,
                count,
                update_progress,
                confirm
            )

            if result:
                output_dir, actual_sets = result
                messagebox.showinfo("Готово", f"Агрегация завершена!\nСоздано наборов: {actual_sets}\nРезультаты в папке: {output_dir}")
                self.progress["value"] = 0
        except Exception as e:
            messagebox.showerror("Критическая ошибка", f"Произошла ошибка:\n{traceback.format_exc()}")

if __name__ == "__main__":
    root = tk.Tk()
    app = AggregationApp(root)
    root.mainloop()
