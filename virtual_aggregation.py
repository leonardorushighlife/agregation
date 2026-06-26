import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import os
import sys
import traceback
from datetime import datetime
import re

"""
Инструкция по сборке в EXE:
1. Установите pyinstaller: pip install pyinstaller
2. Выполните команду:
   pyinstaller --noconsole --onefile virtual_aggregation.py
"""

def sanitize_filename(filename):
    # Удаляем недопустимые символы для имен файлов Windows
    return re.sub(r'[\\/*?:"<>|]', '_', filename)

def read_codes_from_file(file_path):
    encodings = ['utf-8-sig', 'utf-16', 'utf-8', 'cp1251']
    for enc in encodings:
        try:
            with open(file_path, 'r', encoding=enc) as f:
                content = f.read().splitlines()
                # Удаляем пустые строки
                return [line.strip() for line in content if line.strip()]
        except (UnicodeDecodeError, UnicodeError):
            continue
    raise Exception(f"Не удалось прочитать файл {file_path}. Поддерживаемые кодировки: UTF-8, UTF-16, CP1251.")

class VirtualAggregationApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Виртуальная агрегация наборов")
        self.root.geometry("600x450")

        self.parent_file = ""
        self.child_files = []

        self.create_widgets()

    def create_widgets(self):
        # Основной контейнер
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Выбор родительского файла
        ttk.Label(main_frame, text="Файл с кодами наборов (родители):").pack(anchor=tk.W, pady=(0, 5))
        self.btn_parent = ttk.Button(main_frame, text="Выбрать файл", command=self.select_parent_file)
        self.btn_parent.pack(fill=tk.X, pady=(0, 10))
        self.lbl_parent = ttk.Label(main_frame, text="Файл не выбран", foreground="gray")
        self.lbl_parent.pack(anchor=tk.W, pady=(0, 15))

        # Выбор дочерних файлов
        ttk.Label(main_frame, text="Файлы с кодами вложений (дети):").pack(anchor=tk.W, pady=(0, 5))
        self.btn_children = ttk.Button(main_frame, text="Выбрать файлы", command=self.select_child_files)
        self.btn_children.pack(fill=tk.X, pady=(0, 10))
        self.lbl_children = ttk.Label(main_frame, text="Файлы не выбраны", foreground="gray")
        self.lbl_children.pack(anchor=tk.W, pady=(0, 15))

        # Количество вложений
        ttk.Label(main_frame, text="Количество вложений в один набор:").pack(anchor=tk.W, pady=(0, 5))
        self.ent_count = ttk.Entry(main_frame)
        self.ent_count.insert(0, "1")
        self.ent_count.pack(fill=tk.X, pady=(0, 20))

        # Кнопка запуска
        self.btn_start = ttk.Button(main_frame, text="Запустить агрегацию", command=self.run_aggregation)
        self.btn_start.pack(fill=tk.X, pady=(20, 0))

    def select_parent_file(self):
        file_path = filedialog.askopenfilename(
            title="Выберите файл с кодами наборов",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        if file_path:
            self.parent_file = file_path
            self.lbl_parent.config(text=os.path.basename(file_path), foreground="black")

    def select_child_files(self):
        file_paths = filedialog.askopenfilenames(
            title="Выберите файлы с кодами вложений",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        if file_paths:
            self.child_files = list(file_paths)
            self.lbl_children.config(
                text=f"Выбрано файлов: {len(self.child_files)}",
                foreground="black"
            )

    def run_aggregation(self):
        if not self.parent_file:
            messagebox.showwarning("Внимание", "Выберите файл с кодами наборов.")
            return
        if not self.child_files:
            messagebox.showwarning("Внимание", "Выберите файлы с кодами вложений.")
            return

        try:
            count_per_parent = int(self.ent_count.get())
            if count_per_parent <= 0:
                raise ValueError
        except ValueError:
            messagebox.showwarning("Внимание", "Введите корректное число вложений (целое число больше 0).")
            return

        try:
            # Чтение кодов
            parent_codes = read_codes_from_file(self.parent_file)
            all_child_codes = []
            for cf in self.child_files:
                all_child_codes.extend(read_codes_from_file(cf))

            if not parent_codes:
                messagebox.showerror("Ошибка", "Файл с кодами наборов пуст.")
                return
            if not all_child_codes:
                messagebox.showerror("Ошибка", "Выбранные файлы вложений пусты.")
                return

            # Создание папки
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_dir = f"aggregation_results_{timestamp}"
            os.makedirs(output_dir, exist_ok=True)

            # Агрегация
            self.perform_aggregation(parent_codes, all_child_codes, count_per_parent, output_dir)

        except Exception as e:
            messagebox.showerror("Ошибка", f"Произошла ошибка при выполнении: {str(e)}")

    def perform_aggregation(self, parents, children, count, folder):
        total_parents = len(parents)
        total_children_needed = total_parents * count
        actual_children = len(children)

        if actual_children < total_children_needed:
            msg = f"Предупреждение: Кодов вложений ({actual_children}) меньше, чем требуется для полной агрегации ({total_children_needed}).\n"
            msg += f"Будет агрегировано только {actual_children // count} полных наборов. Продолжить?"
            if not messagebox.askyesno("Внимание", msg):
                return

        sets_created = 0
        child_idx = 0

        for parent_code in parents:
            if child_idx + count > actual_children:
                break

            # Берем порцию дочерних кодов
            current_children = children[child_idx : child_idx + count]
            child_idx += count

            # Имя файла на основе санитарного родительского кода
            filename = sanitize_filename(parent_code) + ".txt"
            filepath = os.path.join(folder, filename)

            try:
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(parent_code + "\n")
                    for child in current_children:
                        f.write(child + "\n")
                sets_created += 1
            except Exception as e:
                messagebox.showerror("Ошибка", f"Не удалось создать файл {filename}: {e}")
                continue

        messagebox.showinfo("Успех", f"Агрегация завершена!\nСоздано наборов: {sets_created}\nПапка: {folder}")

def handle_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    error_msg = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    print(error_msg)
    messagebox.showerror("Критическая ошибка", f"Произошла непредвиденная ошибка:\n{error_msg}")

if __name__ == "__main__":
    sys.excepthook = handle_exception
    root = tk.Tk()
    app = VirtualAggregationApp(root)
    root.mainloop()
