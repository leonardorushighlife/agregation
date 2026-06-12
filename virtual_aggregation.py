import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import os
import time
import traceback
import re

def sanitize_filename(filename):
    """Удаляет недопустимые символы для имен файлов в Windows."""
    return re.sub(r'[\\/*?:"<>|]', "_", filename).strip()

def show_error(title, message, detail=None):
    if detail:
        message = f"{message}\n\nПодробности:\n{detail}"
    messagebox.showerror(title, message)

def global_exception_handler(exctype, value, tb):
    error_msg = "".join(traceback.format_exception(exctype, value, tb))
    print(error_msg)
    show_error("Критическая ошибка", "Произошла непредвиденная ошибка.", error_msg)

# Установка глобального обработчика исключений
tk.Tk.report_callback_exception = global_exception_handler

def read_codes_from_files(filepaths):
    """Читает коды из списка файлов, поддерживая разные кодировки."""
    codes = []
    encodings = ['utf-8-sig', 'utf-8', 'cp1251', 'utf-16']

    for filepath in filepaths:
        success = False
        for enc in encodings:
            try:
                with open(filepath, 'r', encoding=enc) as f:
                    content = f.read().splitlines()
                    # Убираем пустые строки и пробелы
                    codes.extend([line.strip() for line in content if line.strip()])
                success = True
                break
            except (UnicodeDecodeError, Exception):
                continue
        if not success:
            raise Exception(f"Не удалось прочитать файл: {filepath}. Попробуйте сохранить его в UTF-8.")
    return codes

class VirtualAggregationApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Виртуальная агрегация")
        self.root.geometry("600x400")

        self.parent_file = ""
        self.child_files = []

        self.create_widgets()

    def create_widgets(self):
        frame = ttk.Frame(self.root, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)

        # Родительский файл
        ttk.Label(frame, text="Файл с кодами наборов (родители):").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.btn_parent = ttk.Button(frame, text="Выбрать файл", command=self.select_parent_file)
        self.btn_parent.grid(row=0, column=1, sticky=tk.EW, pady=5)
        self.lbl_parent_path = ttk.Label(frame, text="Не выбран", foreground="gray")
        self.lbl_parent_path.grid(row=1, column=0, columnspan=2, sticky=tk.W, pady=(0, 10))

        # Количество вложений
        ttk.Label(frame, text="Количество вложений в каждый набор:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.ent_count = ttk.Entry(frame)
        self.ent_count.insert(0, "1")
        self.ent_count.grid(row=2, column=1, sticky=tk.EW, pady=5)

        # Дочерние файлы
        ttk.Label(frame, text="Файлы с кодами вложений (дети):").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.btn_children = ttk.Button(frame, text="Выбрать файлы", command=self.select_child_files)
        self.btn_children.grid(row=3, column=1, sticky=tk.EW, pady=5)
        self.lbl_children_count = ttk.Label(frame, text="Выбрано файлов: 0", foreground="gray")
        self.lbl_children_count.grid(row=4, column=0, columnspan=2, sticky=tk.W, pady=(0, 20))

        # Кнопка Запуск
        self.btn_run = ttk.Button(frame, text="ЗАПУСТИТЬ АГРЕГАЦИЮ", command=self.run_aggregation)
        self.btn_run.grid(row=5, column=0, columnspan=2, sticky=tk.NSEW, pady=10)

        frame.columnconfigure(1, weight=1)

    def select_parent_file(self):
        file = filedialog.askopenfilename(filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if file:
            self.parent_file = file
            self.lbl_parent_path.config(text=os.path.basename(file), foreground="black")

    def select_child_files(self):
        files = filedialog.askopenfilenames(filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if files:
            self.child_files = list(files)
            self.lbl_children_count.config(text=f"Выбрано файлов: {len(files)}", foreground="black")

    def run_aggregation(self):
        if not self.parent_file:
            messagebox.showwarning("Внимание", "Выберите файл с кодами наборов.")
            return
        if not self.child_files:
            messagebox.showwarning("Внимание", "Выберите файлы с кодами вложений.")
            return

        try:
            count_per_set = int(self.ent_count.get())
            if count_per_set <= 0:
                raise ValueError
        except ValueError:
            messagebox.showwarning("Внимание", "Введите корректное число вложений (больше 0).")
            return

        try:
            parents = read_codes_from_files([self.parent_file])
            children = read_codes_from_files(self.child_files)

            if not parents:
                messagebox.showwarning("Внимание", "В файле наборов нет кодов.")
                return
            if not children:
                messagebox.showwarning("Внимание", "В файлах вложений нет кодов.")
                return

            total_needed = len(parents) * count_per_set
            if len(children) < total_needed:
                if not messagebox.askyesno("Недостаточно кодов",
                    f"Кодов вложений ({len(children)}) меньше, чем требуется для всех наборов ({total_needed}).\n"
                    f"Будет создано только {len(children) // count_per_set} полных наборов. Продолжить?"):
                    return

            # Создание папки
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            output_dir = f"aggregation_results_{timestamp}"
            os.makedirs(output_dir, exist_ok=True)

            actual_sets = min(len(parents), len(children) // count_per_set)

            for i in range(actual_sets):
                parent_code = parents[i]
                safe_name = sanitize_filename(parent_code)
                # Если имя получилось пустым или слишком длинным
                if not safe_name:
                    safe_name = f"set_{i+1}"

                filepath = os.path.join(output_dir, f"{safe_name}.txt")

                # Если файл уже существует (дубликат кода родителя), добавим индекс
                counter = 1
                while os.path.exists(filepath):
                    filepath = os.path.join(output_dir, f"{safe_name}_{counter}.txt")
                    counter += 1

                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(parent_code + "\n")
                    for j in range(count_per_set):
                        child_code = children[i * count_per_set + j]
                        f.write(child_code + "\n")

            messagebox.showinfo("Готово", f"Агрегация завершена!\nСоздано наборов: {actual_sets}\nРезультаты в папке: {output_dir}")

        except Exception as e:
            global_exception_handler(type(e), e, e.__traceback__)

if __name__ == "__main__":
    root = tk.Tk()
    app = VirtualAggregationApp(root)
    root.mainloop()
