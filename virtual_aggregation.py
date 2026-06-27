import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from datetime import datetime
import re

"""
Скрипт для виртуальной агрегации кодов маркировки.
Инструкция по сборке в EXE:
1. Установите PyInstaller: pip install pyinstaller
2. Выполните команду: pyinstaller --noconsole --onefile virtual_aggregation.py
"""

def sanitize_filename(name):
    """Очищает строку от символов, недопустимых в именах файлов Windows."""
    return re.sub(r'[\\/*?:"<>|]', "_", name).strip()

def read_codes(filepaths):
    """Читает коды из одного или нескольких файлов, пробуя разные кодировки."""
    codes = []
    if isinstance(filepaths, str):
        filepaths = [filepaths]

    for path in filepaths:
        if not os.path.exists(path):
            continue
        # Пробуем разные кодировки для кириллицы и разных систем
        for encoding in ['utf-8-sig', 'utf-16', 'utf-8', 'cp1251']:
            try:
                with open(path, 'r', encoding=encoding) as f:
                    lines = [line.strip() for line in f if line.strip()]
                    if lines:
                        codes.extend(lines)
                        break # Если успешно прочитали и файл не пуст, выходим из цикла кодировок
            except (UnicodeDecodeError, UnicodeError):
                continue
    return codes

def perform_aggregation(parents, children, count_per_parent, output_dir):
    """Логика агрегации: сопоставление родительских кодов с дочерними и запись в файлы."""
    success_count = 0
    child_idx = 0

    for p_code in parents:
        if child_idx + count_per_parent > len(children):
            break

        safe_name = sanitize_filename(p_code)
        # Если имя пустое после очистки, используем индекс
        if not safe_name:
            safe_name = f"unnamed_parent_{success_count}"

        file_path = os.path.join(output_dir, f"{safe_name}.txt")

        # Обработка дубликатов имен файлов (если коды одинаковые после санитизации)
        counter = 1
        original_safe_name = safe_name
        while os.path.exists(file_path):
            safe_name = f"{original_safe_name}_{counter}"
            file_path = os.path.join(output_dir, f"{safe_name}.txt")
            counter += 1

        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(p_code + "\n")
            for _ in range(count_per_parent):
                f.write(children[child_idx] + "\n")
                child_idx += 1
        success_count += 1

    return success_count

class AggregationApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Виртуальная агрегация")
        self.root.geometry("600x500")

        self.parent_file = ""
        self.child_files = []

        self.create_widgets()

    def create_widgets(self):
        padding = {"padx": 15, "pady": 5}

        # Секция родительского файла
        tk.Label(self.root, text="1. Выберите файл с кодами наборов (родители):", font=("Arial", 10, "bold")).pack(anchor="w", **padding)
        self.parent_label = tk.Label(self.root, text="Файл не выбран", fg="red", wraplength=550, justify="left")
        self.parent_label.pack(anchor="w", **padding)
        tk.Button(self.root, text="Обзор...", command=self.select_parent).pack(anchor="w", **padding)

        ttk.Separator(self.root, orient="horizontal").pack(fill="x", pady=10, padx=15)

        # Секция вложений
        tk.Label(self.root, text="2. Укажите количество вложений в один набор:", font=("Arial", 10, "bold")).pack(anchor="w", **padding)
        self.count_entry = tk.Entry(self.root, width=10)
        self.count_entry.insert(0, "1")
        self.count_entry.pack(anchor="w", **padding)

        ttk.Separator(self.root, orient="horizontal").pack(fill="x", pady=10, padx=15)

        # Секция дочерних файлов
        tk.Label(self.root, text="3. Выберите файлы с кодами вложений (дети):", font=("Arial", 10, "bold")).pack(anchor="w", **padding)
        self.child_listbox = tk.Listbox(self.root, height=6)
        self.child_listbox.pack(fill="both", expand=True, **padding)

        btn_frame = tk.Frame(self.root)
        btn_frame.pack(anchor="w", **padding)
        tk.Button(btn_frame, text="Добавить файлы...", command=self.select_children).pack(side="left", padx=5)
        tk.Button(btn_frame, text="Очистить список", command=self.clear_children).pack(side="left", padx=5)

        # Кнопка запуска
        self.run_btn = tk.Button(self.root, text="ЗАПУСТИТЬ АГРЕГАЦИЮ", bg="#4CAF50", fg="white",
                                font=("Arial", 12, "bold"), height=2, command=self.run_aggregation)
        self.run_btn.pack(fill="x", padx=15, pady=20)

    def select_parent(self):
        path = filedialog.askopenfilename(title="Выберите файл родителей", filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if path:
            self.parent_file = path
            self.parent_label.config(text=os.path.basename(path), fg="black")

    def select_children(self):
        paths = filedialog.askopenfilenames(title="Выберите файлы вложений", filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if paths:
            for p in paths:
                if p not in self.child_files:
                    self.child_files.append(p)
                    self.child_listbox.insert(tk.END, os.path.basename(p))

    def clear_children(self):
        self.child_files = []
        self.child_listbox.delete(0, tk.END)

    def run_aggregation(self):
        if not self.parent_file:
            messagebox.showerror("Ошибка", "Не выбран файл с кодами наборов!")
            return

        if not self.child_files:
            messagebox.showerror("Ошибка", "Не выбраны файлы с кодами вложений!")
            return

        try:
            count_per_parent = int(self.count_entry.get())
            if count_per_parent <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Ошибка", "Введите целое положительное число вложений!")
            return

        # Чтение кодов
        parents = read_codes(self.parent_file)
        children = read_codes(self.child_files)

        if not parents:
            messagebox.showerror("Ошибка", "Файл наборов пуст или не удалось его прочитать!")
            return

        if not children:
            messagebox.showerror("Ошибка", "Файлы вложений пусты или не удалось их прочитать!")
            return

        actual_sets = min(len(parents), len(children) // count_per_parent)
        total_required = len(parents) * count_per_parent

        if len(children) < total_required:
            msg = f"Внимание!\n\nКодов вложений: {len(children)}\nКодов наборов: {len(parents)}\nТребуется вложений: {total_required}\n\nБудет создано только {actual_sets} полных наборов.\nПродолжить?"
            if not messagebox.askyesno("Предупреждение", msg):
                return

        # Создаем папку
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = f"aggregation_results_{timestamp}"

        try:
            os.makedirs(output_dir, exist_ok=True)
            success_count = perform_aggregation(parents, children, count_per_parent, output_dir)

            messagebox.showinfo("Успех", f"Агрегация завершена!\n\nСоздано наборов: {success_count}\nРезультаты в папке:\n{os.path.abspath(output_dir)}")

            # Открываем папку с результатом (Windows)
            if os.name == 'nt':
                os.startfile(output_dir)

        except Exception as e:
            messagebox.showerror("Критическая ошибка", f"Произошла ошибка при выполнении:\n{str(e)}")

if __name__ == "__main__":
    root = tk.Tk()
    # Установка иконки, если была бы, но пока так
    app = AggregationApp(root)
    root.mainloop()
