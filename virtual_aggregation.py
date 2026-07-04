"""
Скрипт для виртуальной агрегации кодов маркировки.
Инструкция по сборке в EXE:
1. Установите pyinstaller: pip install pyinstaller
2. Соберите проект: pyinstaller --noconsole --onefile virtual_aggregation.py
3. Готовый файл появится в папке dist/
"""

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import os
import re
from datetime import datetime

class VirtualAggregationApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Виртуальная агрегация")
        self.root.geometry("600x450")

        self.parent_file = ""
        self.child_files = []

        self.create_widgets()

    def create_widgets(self):
        # Frame for Parent File
        parent_frame = tk.LabelFrame(self.root, text="Коды маркировки набора (родительские)", padx=10, pady=10)
        parent_frame.pack(fill="x", padx=20, pady=10)

        self.btn_parent = tk.Button(parent_frame, text="Выбрать файл наборов", command=self.select_parent_file)
        self.btn_parent.pack(side="left")

        self.lbl_parent = tk.Label(parent_frame, text="Файл не выбран", fg="gray")
        self.lbl_parent.pack(side="left", padx=10)

        # Frame for Child Files
        child_frame = tk.LabelFrame(self.root, text="Коды маркировки вложений (дочерние)", padx=10, pady=10)
        child_frame.pack(fill="x", padx=20, pady=10)

        self.btn_children = tk.Button(child_frame, text="Выбрать файлы вложений", command=self.select_child_files)
        self.btn_children.pack(side="left")

        self.lbl_children = tk.Label(child_frame, text="Файлы не выбраны", fg="gray")
        self.lbl_children.pack(side="left", padx=10)

        # Frame for Count
        count_frame = tk.Frame(self.root, padx=20, pady=10)
        count_frame.pack(fill="x")

        tk.Label(count_frame, text="Количество вложений в один набор:").pack(side="left")
        self.ent_count = tk.Entry(count_frame, width=10)
        self.ent_count.insert(0, "4")
        self.ent_count.pack(side="left", padx=10)

        # Action Button
        self.btn_start = tk.Button(self.root, text="Начать агрегацию", command=self.start_aggregation, bg="green", fg="white", font=("Arial", 12, "bold"))
        self.btn_start.pack(pady=30)

        # Progress bar
        self.progress = ttk.Progressbar(self.root, orient="horizontal", length=500, mode="determinate")
        self.progress.pack(pady=10)

    def select_parent_file(self):
        file = filedialog.askopenfilename(filetypes=[("Text files", "*.txt")])
        if file:
            self.parent_file = file
            self.lbl_parent.config(text=os.path.basename(file), fg="black")

    def select_child_files(self):
        files = filedialog.askopenfilenames(filetypes=[("Text files", "*.txt")])
        if files:
            self.child_files = list(files)
            self.lbl_children.config(text=f"Выбрано файлов: {len(files)}", fg="black")

    def start_aggregation(self):
        if not self.parent_file:
            messagebox.showerror("Ошибка", "Выберите файл с кодами наборов")
            return
        if not self.child_files:
            messagebox.showerror("Ошибка", "Выберите файлы с кодами вложений")
            return

        try:
            count_per_set = int(self.ent_count.get())
            if count_per_set <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Ошибка", "Введите корректное количество вложений (целое число > 0)")
            return

        try:
            folder_name = perform_aggregation(
                self.parent_file,
                self.child_files,
                count_per_set,
                progress_callback=self.update_progress,
                confirm_callback=messagebox.askyesno
            )
            messagebox.showinfo("Успех", f"Агрегация завершена успешно!\nРезультаты сохранены в папку:\n{folder_name}")
        except Exception as e:
            messagebox.showerror("Ошибка", f"Произошла ошибка при агрегации:\n{str(e)}")
        finally:
            self.progress["value"] = 0

    def update_progress(self, current, total):
        self.progress["maximum"] = total
        self.progress["value"] = current
        self.root.update_idletasks()

def sanitize_filename(filename):
    """Очищает строку от символов, недопустимых в именах файлов."""
    return re.sub(r'[\\/*?:"<>|]', "_", filename)

def read_codes(filepath):
    """Считывает коды из файла с поддержкой различных кодировок."""
    encodings = ['utf-8-sig', 'utf-16', 'utf-8', 'cp1251']
    for enc in encodings:
        try:
            with open(filepath, "r", encoding=enc) as f:
                return [line.strip() for line in f if line.strip()]
        except (UnicodeDecodeError, UnicodeError):
            continue
    # Если ничего не подошло, пробуем с игнорированием ошибок
    with open(filepath, "r", encoding='utf-8', errors='ignore') as f:
        return [line.strip() for line in f if line.strip()]

def perform_aggregation(parent_file, child_files, count_per_set, progress_callback=None, confirm_callback=None):
    parent_codes = read_codes(parent_file)
    all_child_codes = []
    for cf in child_files:
        all_child_codes.extend(read_codes(cf))

    total_parents = len(parent_codes)
    needed_children = total_parents * count_per_set

    if len(all_child_codes) < needed_children:
        actual_sets = len(all_child_codes) // count_per_set
        if confirm_callback:
            if not confirm_callback("Предупреждение",
                f"Вложений ({len(all_child_codes)}) недостаточно для всех наборов ({total_parents}).\n"
                f"Будет создано только {actual_sets} полных наборов. Продолжить?"):
                raise Exception("Отменено пользователем из-за нехватки кодов вложений")
        else:
            # Если коллбэк не передан (например, в тестах), просто продолжаем с тем, что есть
            pass
        parent_codes = parent_codes[:actual_sets]
        total_parents = actual_sets

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = f"aggregation_results_{timestamp}"
    os.makedirs(output_dir, exist_ok=True)

    used_filenames = {}
    for i, p_code in enumerate(parent_codes):
        # Очищаем код родителя для использования в качестве имени файла
        safe_p_code = sanitize_filename(p_code)
        # Ограничиваем длину имени файла на всякий случай
        base_name = (safe_p_code[:50] + "...") if len(safe_p_code) > 50 else safe_p_code

        file_name = base_name
        if file_name in used_filenames:
            used_filenames[base_name] += 1
            file_name = f"{base_name}_{used_filenames[base_name]}"
        else:
            used_filenames[base_name] = 0

        file_path = os.path.join(output_dir, f"{file_name}.txt")

        start_idx = i * count_per_set
        current_children = all_child_codes[start_idx : start_idx + count_per_set]

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(p_code + "\n")
            for c_code in current_children:
                f.write(c_code + "\n")

        if progress_callback:
            progress_callback(i + 1, total_parents)

    return output_dir

if __name__ == "__main__":
    import traceback

    def exception_handler(etype, value, tb):
        err = "".join(traceback.format_exception(etype, value, tb))
        messagebox.showerror("Критическая ошибка", err)

    root = tk.Tk()
    root.report_callback_exception = exception_handler

    try:
        app = VirtualAggregationApp(root)
        root.mainloop()
    except Exception:
        exception_handler(*sys.exc_info())
