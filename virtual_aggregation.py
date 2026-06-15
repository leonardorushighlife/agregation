import tkinter as tk
from tkinter import filedialog, messagebox
import os
import datetime
import re
import sys
import traceback

def sanitize_filename(name):
    """Очищает строку от символов, недопустимых в именах файлов Windows."""
    return re.sub(r'[<>:"/\\|?*]', '_', name)

def read_codes(filepath):
    """Читает коды из файла, пробуя различные кодировки."""
    encodings = ['utf-8-sig', 'utf-8', 'cp1251', 'utf-16']
    for enc in encodings:
        try:
            with open(filepath, 'r', encoding=enc) as f:
                return [line.strip() for line in f if line.strip()]
        except (UnicodeDecodeError, Exception):
            continue
    raise Exception(f"Не удалось прочитать файл {filepath}. Проверьте кодировку.")

def perform_aggregation(parent_file, child_files, count_per_set, output_dir=None):
    """
    Основная логика агрегации. Вынесена отдельно для возможности тестирования.
    """
    parent_codes = read_codes(parent_file)
    child_codes = []
    for f in child_files:
        child_codes.extend(read_codes(f))

    if not output_dir:
        output_dir = f"aggregation_results_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    processed_count = 0
    child_idx = 0

    actual_sets = min(len(parent_codes), len(child_codes) // count_per_set) if count_per_set > 0 else 0

    for i in range(actual_sets):
        parent = parent_codes[i]
        attachments = child_codes[child_idx : child_idx + count_per_set]
        child_idx += count_per_set

        filename = sanitize_filename(parent) + ".txt"
        filepath = os.path.join(output_dir, filename)

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(parent + "\n")
            for att in attachments:
                f.write(att + "\n")

        processed_count += 1

    return processed_count, output_dir, len(parent_codes), len(child_codes)

class AggregatorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Виртуальная Агрегация")
        self.root.geometry("600x450")

        self.parent_file = ""
        self.child_files = []

        # Стили
        self.root.configure(padx=20, pady=20)

        tk.Label(root, text="Виртуальная Агрегация Кодов", font=("Arial", 16, "bold")).pack(pady=(0, 20))

        # Секция родительского файла
        self.btn_parent = tk.Button(root, text="1. Выбрать файл с кодами НАБОРОВ (Родитель)",
                                     command=self.select_parent, height=2, bg="#f0f0f0")
        self.btn_parent.pack(fill=tk.X, pady=5)
        self.lbl_parent = tk.Label(root, text="Файл не выбран", fg="red", wraplength=550)
        self.lbl_parent.pack(pady=(0, 10))

        # Секция дочерних файлов
        self.btn_children = tk.Button(root, text="2. Выбрать файлы с кодами ВЛОЖЕНИЙ (Дети)",
                                       command=self.select_children, height=2, bg="#f0f0f0")
        self.btn_children.pack(fill=tk.X, pady=5)
        self.lbl_children = tk.Label(root, text="Файлы не выбраны", fg="red", wraplength=550)
        self.lbl_children.pack(pady=(0, 10))

        # Настройка количества
        frame_count = tk.Frame(root)
        frame_count.pack(pady=10)
        tk.Label(frame_count, text="Количество вложений в один набор:", font=("Arial", 10)).pack(side=tk.LEFT)
        self.entry_count = tk.Entry(frame_count, justify="center", width=10, font=("Arial", 12))
        self.entry_count.insert(0, "1")
        self.entry_count.pack(side=tk.LEFT, padx=10)

        # Кнопка запуска
        self.btn_run = tk.Button(root, text="ЗАПУСТИТЬ АГРЕГАЦИЮ", command=self.run_aggregation,
                                  bg="#4CAF50", fg="white", font=("Arial", 12, "bold"), height=2)
        self.btn_run.pack(fill=tk.X, pady=20)

    def select_parent(self):
        file = filedialog.askopenfilename(title="Выберите файл с кодами наборов",
                                          filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if file:
            self.parent_file = file
            self.lbl_parent.config(text=os.path.basename(file), fg="green")

    def select_children(self):
        files = filedialog.askopenfilenames(title="Выберите файлы с кодами содержимого",
                                            filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if files:
            self.child_files = list(files)
            self.lbl_children.config(text=f"Выбрано файлов: {len(files)}", fg="green")

    def run_aggregation(self):
        if not self.parent_file:
            messagebox.showerror("Ошибка", "Выберите файл с кодами наборов!")
            return
        if not self.child_files:
            messagebox.showerror("Ошибка", "Выберите файлы с кодами содержимого!")
            return

        try:
            count_per_set = int(self.entry_count.get())
            if count_per_set <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Ошибка", "Введите корректное целое число вложений (больше 0)!")
            return

        try:
            processed, folder, total_p, total_c = perform_aggregation(self.parent_file, self.child_files, count_per_set)

            summary = (f"Агрегация успешно завершена!\n\n"
                       f"Создано файлов: {processed}\n"
                       f"Всего кодов наборов: {total_p}\n"
                       f"Всего кодов вложений: {total_c}\n"
                       f"Папка с результатом: {folder}")

            messagebox.showinfo("Успех", summary)

            # Открываем папку в проводнике (только для Windows)
            if sys.platform == 'win32':
                os.startfile(folder)

        except Exception as e:
            error_msg = f"Произошла ошибка:\n{str(e)}\n\n{traceback.format_exc()}"
            messagebox.showerror("Ошибка", error_msg)

if __name__ == "__main__":
    root = tk.Tk()
    app = AggregatorApp(root)
    root.mainloop()
