"""
Инструкция по сборке в EXE:
1. Установите PyInstaller: pip install pyinstaller
2. Соберите проект: pyinstaller --noconsole --onefile virtual_aggregation.py
"""

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import os
import re
from datetime import datetime

def sanitize_filename(name):
    """Удаляет недопустимые символы из имени файла."""
    return re.sub(r'[\\/*?:"<>|]', "_", name).strip()

def read_codes(filepath):
    """Читает коды из файла, пробуя разные кодировки."""
    encodings = ['utf-8-sig', 'utf-16', 'utf-8', 'cp1251']
    for enc in encodings:
        try:
            with open(filepath, 'r', encoding=enc) as f:
                content = f.read()
            # Разделяем по строкам, удаляем пустые и пробелы
            lines = [line.strip() for line in content.splitlines() if line.strip()]
            return lines
        except (UnicodeDecodeError, UnicodeError):
            continue
    raise Exception(f"Не удалось прочитать файл {filepath}. Проверьте кодировку.")

def perform_aggregation(parent_codes, child_codes, count_per_parent):
    """
    Распределяет дочерние коды по родительским.
    Возвращает список кортежей (parent, children_list).
    """
    results = []
    total_needed = len(parent_codes) * count_per_parent

    if len(child_codes) < total_needed:
        actual_sets = len(child_codes) // count_per_parent
        if not messagebox.askyesno("Предупреждение",
                                   f"Кодов вложений недостаточно для всех наборов.\n"
                                   f"Доступно вложений: {len(child_codes)}\n"
                                   f"Требуется для всех наборов: {total_needed}\n"
                                   f"Будет создано полных наборов: {actual_sets}\n"
                                   f"Продолжить?"):
            return None
        parent_codes = parent_codes[:actual_sets]

    for i, parent in enumerate(parent_codes):
        start_idx = i * count_per_parent
        end_idx = start_idx + count_per_parent
        current_children = child_codes[start_idx:end_idx]
        results.append((parent, current_children))

    return results

class VirtualAggregationApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Виртуальная Агрегация")
        self.root.geometry("600x480")

        self.parent_file = ""
        self.child_files = []

        # UI Elements
        frame = tk.Frame(root, padx=20, pady=20)
        frame.pack(expand=True, fill="both")

        # Parent file selection
        tk.Label(frame, text="Файл с кодами наборов (родительские):").pack(anchor="w")
        self.lbl_parent = tk.Label(frame, text="Файл не выбран", fg="gray", wraplength=500, justify="left")
        self.lbl_parent.pack(anchor="w", pady=(0, 5))
        tk.Button(frame, text="Выбрать файл наборов", command=self.select_parent_file).pack(anchor="w", pady=(0, 15))

        # Child files selection
        tk.Label(frame, text="Файлы с кодами вложений (дочерние):").pack(anchor="w")
        self.lbl_children = tk.Label(frame, text="Файлы не выбраны", fg="gray", wraplength=500, justify="left")
        self.lbl_children.pack(anchor="w", pady=(0, 5))
        tk.Button(frame, text="Выбрать файлы вложений", command=self.select_child_files).pack(anchor="w", pady=(0, 15))

        # Count of attachments
        tk.Label(frame, text="Количество вложений в один набор:").pack(anchor="w")
        self.entry_count = tk.Entry(frame, width=10)
        self.entry_count.insert(0, "1")
        self.entry_count.pack(anchor="w", pady=(0, 20))

        # Action button
        self.btn_run = tk.Button(frame, text="Выполнить агрегацию", command=self.run_aggregation,
                                 bg="#4CAF50", fg="white", font=("Arial", 12, "bold"), height=2, width=20)
        self.btn_run.pack(pady=10)

    def select_parent_file(self):
        file = filedialog.askopenfilename(filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if file:
            self.parent_file = file
            self.lbl_parent.config(text=os.path.basename(file), fg="black")

    def select_child_files(self):
        files = filedialog.askopenfilenames(filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if files:
            self.child_files = list(files)
            names = ", ".join([os.path.basename(f) for f in files])
            if len(names) > 100:
                names = names[:97] + "..."
            self.lbl_children.config(text=names, fg="black")

    def run_aggregation(self):
        if not self.parent_file:
            messagebox.showerror("Ошибка", "Выберите файл с кодами наборов.")
            return
        if not self.child_files:
            messagebox.showerror("Ошибка", "Выберите файлы с кодами вложений.")
            return

        try:
            count_per_parent = int(self.entry_count.get())
            if count_per_parent <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Ошибка", "Введите корректное количество вложений (целое число > 0).")
            return

        try:
            parents = read_codes(self.parent_file)
            all_children = []
            for cf in self.child_files:
                all_children.extend(read_codes(cf))

            aggregation_results = perform_aggregation(parents, all_children, count_per_parent)

            if aggregation_results is None: # User cancelled
                return

            # Создание папки
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_dir = f"aggregation_results_{timestamp}"
            os.makedirs(output_dir, exist_ok=True)

            # Сохранение файлов
            for parent, children in aggregation_results:
                safe_name = sanitize_filename(parent)
                # Если имя файла слишком длинное, обрезаем (актуально для DataMatrix)
                if len(safe_name) > 100:
                    safe_name = safe_name[:100]

                filepath = os.path.join(output_dir, f"{safe_name}.txt")

                # Если такой файл уже существует (например, при дублях родительских кодов), добавим индекс
                counter = 1
                while os.path.exists(filepath):
                    filepath = os.path.join(output_dir, f"{safe_name}_{counter}.txt")
                    counter += 1

                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(parent + "\n")
                    for child in children:
                        f.write(child + "\n")

            messagebox.showinfo("Успех", f"Агрегация завершена!\nСоздано наборов: {len(aggregation_results)}\nРезультаты в папке: {output_dir}")

        except Exception as e:
            messagebox.showerror("Ошибка", f"Произошла ошибка при выполнении: {str(e)}")

if __name__ == "__main__":
    root = tk.Tk()
    app = VirtualAggregationApp(root)
    root.mainloop()
