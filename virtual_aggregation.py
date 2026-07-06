import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from datetime import datetime
import traceback

"""
Инструкция по сборке в EXE:
1. Установите pyinstaller: pip install pyinstaller
2. Соберите проект: pyinstaller --noconsole --onefile virtual_aggregation.py
"""

def read_codes(filepath):
    """Читает коды из файла, пробуя разные кодировки."""
    encodings = ['utf-8-sig', 'utf-16', 'utf-8', 'cp1251']
    for enc in encodings:
        try:
            with open(filepath, 'r', encoding=enc) as f:
                return [line.strip() for line in f if line.strip()]
        except (UnicodeDecodeError, UnicodeError):
            continue
    raise Exception(f"Не удалось прочитать файл {filepath}. Проверьте кодировку.")

def sanitize_filename(filename):
    """Удаляет недопустимые для имен файлов символы."""
    for char in ['<', '>', ':', '"', '/', '\\', '|', '?', '*']:
        filename = filename.replace(char, '_')
    return filename

def perform_aggregation(parent_file, child_files, count_per_parent, output_dir, confirm_callback=None):
    """Основная логика агрегации."""
    parents = read_codes(parent_file)
    all_children = []
    for cf in child_files:
        all_children.extend(read_codes(cf))

    total_needed = len(parents) * count_per_parent
    actual_available = len(all_children)

    actual_sets = len(parents)
    if actual_available < total_needed:
        possible_sets = actual_available // count_per_parent
        msg = f"Кодов вложений ({actual_available}) недостаточно для всех наборов ({total_needed}).\n"
        msg += f"Будет создано только {possible_sets} полных наборов. Продолжить?"
        if confirm_callback and not confirm_callback(msg):
            return False
        actual_sets = possible_sets

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    for i in range(actual_sets):
        parent_code = parents[i]
        safe_name = sanitize_filename(parent_code)

        # Обработка возможных дублей имен файлов (хотя коды должны быть уникальны)
        file_path = os.path.join(output_dir, f"{safe_name}.txt")
        counter = 1
        while os.path.exists(file_path):
            file_path = os.path.join(output_dir, f"{safe_name}_{counter}.txt")
            counter += 1

        start_idx = i * count_per_parent
        end_idx = start_idx + count_per_parent
        set_children = all_children[start_idx:end_idx]

        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(parent_code + '\n')
            for child in set_children:
                f.write(child + '\n')

    return True

class AggregatorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Виртуальная агрегация наборов")
        self.root.geometry("600x450")

        self.parent_file = ""
        self.child_files = []

        # UI
        main_frame = ttk.Frame(root, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Parent file
        ttk.Label(main_frame, text="Файл с кодами наборов (родители):").pack(anchor=tk.W)
        self.btn_parent = ttk.Button(main_frame, text="Выбрать файл", command=self.select_parent)
        self.btn_parent.pack(fill=tk.X, pady=(0, 10))
        self.lbl_parent = ttk.Label(main_frame, text="Файл не выбран", foreground="gray")
        self.lbl_parent.pack(anchor=tk.W, pady=(0, 20))

        # Child files
        ttk.Label(main_frame, text="Файлы с кодами вложений (дети):").pack(anchor=tk.W)
        self.btn_children = ttk.Button(main_frame, text="Выбрать файлы", command=self.select_children)
        self.btn_children.pack(fill=tk.X, pady=(0, 10))
        self.lbl_children = ttk.Label(main_frame, text="Файлы не выбраны", foreground="gray")
        self.lbl_children.pack(anchor=tk.W, pady=(0, 20))

        # Count per parent
        count_frame = ttk.Frame(main_frame)
        count_frame.pack(fill=tk.X, pady=(0, 20))
        ttk.Label(count_frame, text="Количество вложений в одном наборе:").pack(side=tk.LEFT)
        self.ent_count = ttk.Entry(count_frame, width=10)
        self.ent_count.pack(side=tk.LEFT, padx=10)
        self.ent_count.insert(0, "1")

        # Start button
        self.btn_run = ttk.Button(main_frame, text="НАЧАТЬ АГРЕГАЦИЮ", command=self.run)
        self.btn_run.pack(fill=tk.X, pady=20)

    def select_parent(self):
        file = filedialog.askopenfilename(filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if file:
            self.parent_file = file
            self.lbl_parent.config(text=os.path.basename(file), foreground="black")

    def select_children(self):
        files = filedialog.askopenfilenames(filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if files:
            self.child_files = list(files)
            names = ", ".join([os.path.basename(f) for f in files])
            if len(names) > 60:
                names = names[:57] + "..."
            self.lbl_children.config(text=f"Выбрано файлов: {len(files)} ({names})", foreground="black")

    def run(self):
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
            messagebox.showerror("Ошибка", "Введите корректное число вложений (целое число больше 0)!")
            return

        output_dir = f"aggregation_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        try:
            success = perform_aggregation(
                self.parent_file,
                self.child_files,
                count,
                output_dir,
                confirm_callback=messagebox.askyesno
            )

            if success:
                messagebox.showinfo("Готово", f"Агрегация завершена!\nРезультаты в папке: {output_dir}")
        except Exception as e:
            error_msg = f"Произошла ошибка:\n{str(e)}\n\n{traceback.format_exc()}"
            print(error_msg)
            messagebox.showerror("Критическая ошибка", error_msg)

if __name__ == "__main__":
    root = tk.Tk()
    app = AggregatorApp(root)
    root.mainloop()
