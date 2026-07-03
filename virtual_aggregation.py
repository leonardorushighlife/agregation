"""
Скрипт для виртуальной агрегации кодов маркировки.
Позволяет объединять родительские коды (наборы) с кодами вложений в отдельные файлы.

Инструкция по сборке в EXE:
1. Установите PyInstaller: pip install pyinstaller
2. Соберите проект: pyinstaller --noconsole --onefile virtual_aggregation.py
"""

import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog
import os
from datetime import datetime
import re
import traceback

def sanitize_filename(name):
    """Очищает строку от символов, недопустимых в именах файлов Windows."""
    return re.sub(r'[<>:"/\\|?*]', '_', name)

def read_codes(filepath):
    codes = []
    # Пробуем разные кодировки для кириллицы
    encodings = ['utf-8-sig', 'utf-16', 'utf-8', 'cp1251']
    for enc in encodings:
        try:
            with open(filepath, 'r', encoding=enc) as f:
                codes = [line.strip() for line in f if line.strip()]
            return codes
        except (UnicodeDecodeError, UnicodeError):
            continue
    return []

def perform_aggregation(parent_file, child_files, count, confirm_callback=None):
    """
    Основная логика агрегации.
    confirm_callback: функция для подтверждения продолжения при нехватке кодов.
    """
    parents = read_codes(parent_file)
    children = []
    for cf in child_files:
        children.extend(read_codes(cf))

    if not parents:
        raise ValueError("Файл наборов пуст")
    if not children:
        raise ValueError("Файлы вложений пусты")

    total_needed = len(parents) * count
    if len(children) < total_needed:
        msg = f"Недостаточно вложений.\nТребуется: {total_needed}\nДоступно: {len(children)}\n\nПродолжить агрегацию для возможного количества наборов?"
        if confirm_callback and not confirm_callback(msg):
            return None

    # Создаем папку
    folder_name = f"aggregation_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    os.makedirs(folder_name, exist_ok=True)

    actual_sets = 0
    child_idx = 0

    for p_code in parents:
        if child_idx + count > len(children):
            break

        safe_name = sanitize_filename(p_code)
        if len(safe_name) > 150:
            safe_name = safe_name[:150]

        filepath = os.path.join(folder_name, f"{safe_name}.txt")

        counter = 1
        while os.path.exists(filepath):
            filepath = os.path.join(folder_name, f"{safe_name}_{counter}.txt")
            counter += 1

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(p_code + '\n')
            for _ in range(count):
                f.write(children[child_idx] + '\n')
                child_idx += 1

        actual_sets += 1

    return folder_name, actual_sets, child_idx

class AggregationApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Виртуальная агрегация")
        self.root.geometry("500x400")

        self.parent_file = ""
        self.child_files = []
        self.count_per_parent = tk.IntVar(value=1)

        self.create_widgets()

    def create_widgets(self):
        # Файл наборов
        tk.Label(self.root, text="Коды наборов (родительские):", font=("Arial", 10, "bold")).pack(pady=(20, 5))
        self.lbl_parent = tk.Label(self.root, text="Файл не выбран", fg="gray")
        self.lbl_parent.pack()
        tk.Button(self.root, text="Выбрать файл наборов", command=self.select_parent_file).pack(pady=5)

        # Файлы вложений
        tk.Label(self.root, text="Коды вложений (дочерние):", font=("Arial", 10, "bold")).pack(pady=(20, 5))
        self.lbl_children = tk.Label(self.root, text="Файлы не выбраны (0)", fg="gray")
        self.lbl_children.pack()
        tk.Button(self.root, text="Выбрать файлы вложений", command=self.select_child_files).pack(pady=5)

        # Количество вложений
        tk.Label(self.root, text="Количество вложений в один набор:", font=("Arial", 10, "bold")).pack(pady=(20, 5))
        tk.Entry(self.root, textvariable=self.count_per_parent, width=10, justify="center").pack()

        # Кнопка старта
        tk.Button(self.root, text="НАЧАТЬ АГРЕГАЦИЮ", font=("Arial", 12, "bold"),
                  bg="green", fg="white", height=2, width=20, command=self.run_aggregation).pack(pady=30)

    def select_parent_file(self):
        filename = filedialog.askopenfilename(title="Выберите файл с кодами наборов",
                                             filetypes=[("Text files", "*.txt")])
        if filename:
            self.parent_file = filename
            self.lbl_parent.config(text=os.path.basename(filename), fg="black")

    def select_child_files(self):
        filenames = filedialog.askopenfilenames(title="Выберите файлы с кодами вложений",
                                               filetypes=[("Text files", "*.txt")])
        if filenames:
            self.child_files = list(filenames)
            self.lbl_children.config(text=f"Выбрано файлов: {len(filenames)}", fg="black")

    def run_aggregation(self):
        if not self.parent_file:
            messagebox.showerror("Ошибка", "Выберите файл с кодами наборов")
            return
        if not self.child_files:
            messagebox.showerror("Ошибка", "Выберите файлы с кодами вложений")
            return

        try:
            count = self.count_per_parent.get()
            if count <= 0:
                raise ValueError
        except:
            messagebox.showerror("Ошибка", "Введите корректное число вложений")
            return

        def confirm_cb(msg):
            return messagebox.askyesno("Предупреждение", msg)

        try:
            result = perform_aggregation(self.parent_file, self.child_files, count, confirm_cb)
            if result:
                folder_name, actual_sets, child_idx = result
                messagebox.showinfo("Готово",
                                   f"Агрегация завершена успешно!\n\n"
                                   f"Создано наборов: {actual_sets}\n"
                                   f"Использовано вложений: {child_idx}\n"
                                   f"Папка с результатом: {folder_name}")
        except Exception as e:
            err_msg = traceback.format_exc()
            messagebox.showerror("Критическая ошибка", f"Произошла ошибка:\n{str(e)}\n\n{err_msg}")

if __name__ == "__main__":
    root = tk.Tk()
    app = AggregationApp(root)
    root.mainloop()
