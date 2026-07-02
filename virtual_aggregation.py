"""
Скрипт для виртуальной агрегации кодов маркировки.
Позволяет сопоставить родительские коды (наборы) и дочерние коды (вложения).

Инструкция для сборки в EXE:
1. Установите pyinstaller: pip install pyinstaller
2. Выполните команду: pyinstaller --noconsole --onefile virtual_aggregation.py
"""

import os
import re
import sys
import traceback
from datetime import datetime
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

# -----------------------------------------------------------------------------
# ЛОГИКА
# -----------------------------------------------------------------------------

def sanitize_filename(name):
    """Удаляет недопустимые символы для имен файлов Windows."""
    return re.sub(r'[\\/*?:"<>|]', "_", name)[:150]

def read_codes(file_path):
    """Читает коды из файла с поддержкой разных кодировок."""
    encodings = ['utf-8-sig', 'utf-16', 'utf-8', 'cp1251']
    for enc in encodings:
        try:
            with open(file_path, 'r', encoding=enc) as f:
                codes = [line.strip() for line in f if line.strip()]
                return codes
        except (UnicodeDecodeError, UnicodeError):
            continue
    raise Exception(f"Не удалось прочитать файл {file_path}. Попробуйте сохранить его в кодировке UTF-8.")

def perform_aggregation(parent_file, child_files, count_per_parent, progress_callback=None, confirm_callback=None):
    """Основная логика агрегации."""
    parents = read_codes(parent_file)
    if not parents:
        raise Exception("Файл с кодами наборов пуст.")

    all_children = []
    for cf in child_files:
        all_children.extend(read_codes(cf))

    if not all_children:
        raise Exception("Файлы с кодами вложений пусты.")

    total_parents = len(parents)
    required_children = total_parents * count_per_parent

    if len(all_children) < required_children:
        can_make = len(all_children) // count_per_parent
        msg = (f"ВНИМАНИЕ: Недостаточно кодов вложений.\n"
               f"Требуется: {required_children} (для {total_parents} наборов по {count_per_parent} шт).\n"
               f"Найдено вложений: {len(all_children)}.\n"
               f"Можно собрать только {can_make} полных наборов.\n\n"
               f"Продолжить сборку {can_make} наборов?")

        if confirm_callback:
            if not confirm_callback(msg):
                return "Операция отменена."

        actual_sets = can_make
    else:
        actual_sets = total_parents

    if actual_sets == 0:
        raise Exception("Невозможно создать ни одного набора (недостаточно вложений).")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = f"aggregation_results_{timestamp}"
    os.makedirs(output_dir, exist_ok=True)

    for i in range(actual_sets):
        p_code = parents[i]
        c_codes = all_children[i * count_per_parent : (i + 1) * count_per_parent]

        safe_name = sanitize_filename(p_code)
        out_file = os.path.join(output_dir, f"{safe_name}.txt")

        with open(out_file, 'w', encoding='utf-8') as f:
            f.write(p_code + "\n")
            for c in c_codes:
                f.write(c + "\n")

        if progress_callback:
            progress_callback(i + 1, actual_sets)

    return f"Успешно!\nСоздано наборов: {actual_sets}\nРезультаты в папке:\n{os.path.abspath(output_dir)}"

# -----------------------------------------------------------------------------
# GUI
# -----------------------------------------------------------------------------

class AggregatorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Виртуальная Агрегация в Наборы")
        self.root.geometry("600x450")

        self.parent_file = ""
        self.child_files = []

        # UI элементы
        tk.Label(root, text="Виртуальная агрегация", font=("Arial", 16, "bold")).pack(pady=10)

        # Родительский файл
        self.btn_parent = tk.Button(root, text="Выбрать файл с кодами НАБОРОВ", command=self.select_parent, width=40)
        self.btn_parent.pack(pady=5)
        self.lbl_parent = tk.Label(root, text="Файл не выбран", fg="gray")
        self.lbl_parent.pack()

        # Дочерние файлы
        self.btn_children = tk.Button(root, text="Выбрать файлы с кодами ВЛОЖЕНИЙ", command=self.select_children, width=40)
        self.btn_children.pack(pady=5)
        self.lbl_children = tk.Label(root, text="Файлы не выбраны", fg="gray")
        self.lbl_children.pack()

        # Количество вложений
        frame_count = tk.Frame(root)
        frame_count.pack(pady=15)
        tk.Label(frame_count, text="Кол-во вложений в один набор:").pack(side="left")
        self.ent_count = tk.Entry(frame_count, width=5)
        self.ent_count.insert(0, "4")
        self.ent_count.pack(side="left", padx=5)

        # Кнопка Старт
        self.btn_start = tk.Button(root, text="НАЧАТЬ АГРЕГАЦИЮ", command=self.start, bg="green", fg="white", font=("Arial", 12, "bold"), width=30)
        self.btn_start.pack(pady=20)

        # Прогресс
        self.progress = ttk.Progressbar(root, orient="horizontal", length=400, mode="determinate")
        self.progress.pack(pady=5)
        self.lbl_status = tk.Label(root, text="")
        self.lbl_status.pack()

    def select_parent(self):
        file = filedialog.askopenfilename(title="Выберите файл с кодами наборов", filetypes=[("Text files", "*.txt")])
        if file:
            self.parent_file = file
            self.lbl_parent.config(text=os.path.basename(file), fg="black")

    def select_children(self):
        files = filedialog.askopenfilenames(title="Выберите файлы с кодами вложений", filetypes=[("Text files", "*.txt")])
        if files:
            self.child_files = list(files)
            self.lbl_children.config(text=f"Выбрано файлов: {len(files)}", fg="black")

    def update_progress(self, current, total):
        val = (current / total) * 100
        self.progress['value'] = val
        self.lbl_status.config(text=f"Обработка: {current} / {total}")
        self.root.update_idletasks()

    def confirm_dialog(self, message):
        return messagebox.askyesno("Подтверждение", message)

    def start(self):
        if not self.parent_file:
            messagebox.showerror("Ошибка", "Выберите файл с кодами наборов.")
            return
        if not self.child_files:
            messagebox.showerror("Ошибка", "Выберите хотя бы один файл с кодами вложений.")
            return

        try:
            count = int(self.ent_count.get())
            if count <= 0: raise ValueError
        except ValueError:
            messagebox.showerror("Ошибка", "Введите корректное число вложений (целое, больше 0).")
            return

        self.btn_start.config(state="disabled")
        self.lbl_status.config(text="Запуск...")
        self.progress['value'] = 0

        try:
            result = perform_aggregation(
                self.parent_file,
                self.child_files,
                count,
                self.update_progress,
                self.confirm_dialog
            )
            messagebox.showinfo("Готово", result)
        except Exception as e:
            messagebox.showerror("Ошибка", str(e))
            traceback.print_exc()
        finally:
            self.btn_start.config(state="normal")
            self.lbl_status.config(text="")

if __name__ == "__main__":
    def handle_exception(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        err_msg = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        messagebox.showerror("Критическая ошибка", err_msg)

    sys.excepthook = handle_exception

    root = tk.Tk()
    app = AggregatorApp(root)
    root.mainloop()
