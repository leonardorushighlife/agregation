"""
Утилита для виртуальной агрегации кодов маркировки.
Позволяет объединить один файл с родительскими кодами (наборы)
и несколько файлов с дочерними кодами (вложения) в отдельные файлы агрегации.

Инструкция по сборке в EXE:
1. Установите PyInstaller: pip install pyinstaller
2. Соберите проект: pyinstaller --noconsole --onefile virtual_aggregation.py
"""

import os
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from datetime import datetime
import traceback
import re

def sanitize_filename(filename):
    """Очистка имени файла от недопустимых символов Windows."""
    return re.sub(r'[\\/*?:"<>|]', '_', filename)

def read_codes(file_paths):
    """Чтение кодов из списка файлов с поддержкой различных кодировок."""
    encodings = ['utf-8-sig', 'utf-16', 'utf-8', 'cp1251']
    codes = []

    if isinstance(file_paths, str):
        file_paths = [file_paths]

    for path in file_paths:
        content = None
        for enc in encodings:
            try:
                with open(path, 'r', encoding=enc) as f:
                    content = f.read()
                break
            except (UnicodeDecodeError, UnicodeError):
                continue

        if content is None:
            raise Exception(f"Не удалось прочитать файл {path}. Проверьте кодировку.")

        # Очистка и фильтрация пустых строк
        lines = [line.strip() for line in content.splitlines() if line.strip()]
        codes.extend(lines)

    return codes

def perform_aggregation(parent_file, child_files, count_per_parent, output_callback=None):
    """
    Основная логика агрегации.
    parent_file: путь к файлу с кодами наборов
    child_files: список путей к файлам с кодами вложений
    count_per_parent: количество вложений на один набор
    """
    parents = read_codes(parent_file)
    children = read_codes(child_files)

    if not parents:
        raise Exception("Файл с кодами наборов пуст.")
    if not children:
        raise Exception("Файлы с кодами вложений пусты.")

    total_required = len(parents) * count_per_parent
    if len(children) < total_required:
        actual_sets = len(children) // count_per_parent
        if actual_sets == 0:
            raise Exception(f"Недостаточно вложений. Нужно {count_per_parent}, а есть {len(children)}.")

        confirm = True
        if output_callback:
            confirm = output_callback(
                f"Вложений хватит только на {actual_sets} из {len(parents)} наборов. Продолжить?"
            )

        if not confirm:
            return None
        parents = parents[:actual_sets]

    # Создание папки результата
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    folder_name = f"aggregation_results_{timestamp}"
    os.makedirs(folder_name, exist_ok=True)

    used_filenames = {}

    for i, parent_code in enumerate(parents):
        # Очищаем имя файла
        base_name = sanitize_filename(parent_code)
        filename = f"{base_name}.txt"

        # Обработка дубликатов имен файлов в одной сессии
        if filename in used_filenames:
            used_filenames[filename] += 1
            filename = f"{base_name}_{used_filenames[filename]}.txt"
        else:
            used_filenames[filename] = 0

        file_path = os.path.join(folder_name, filename)

        # Срез вложений
        start_idx = i * count_per_parent
        end_idx = start_idx + count_per_parent
        current_children = children[start_idx:end_idx]

        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(parent_code + '\n')
            for child in current_children:
                f.write(child + '\n')

    return folder_name

class AggregationApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Виртуальная агрегация наборов")
        self.root.geometry("600x450")

        self.parent_file = tk.StringVar()
        self.child_files = []
        self.count_per_parent = tk.IntVar(value=10)

        self.create_widgets()

    def create_widgets(self):
        padding = {'padx': 10, 'pady': 5}

        # Секция родительского файла
        tk.Label(self.root, text="Файл с кодами наборов (родители):").pack(anchor='w', **padding)
        parent_frame = tk.Frame(self.root)
        parent_frame.pack(fill='x', **padding)
        tk.Entry(parent_frame, textvariable=self.parent_file).pack(side='left', fill='x', expand=True)
        tk.Button(parent_frame, text="Обзор", command=self.select_parent_file).pack(side='right', padx=5)

        # Секция количества вложений
        tk.Label(self.root, text="Количество вложений в один набор:").pack(anchor='w', **padding)
        tk.Entry(self.root, textvariable=self.count_per_parent).pack(fill='x', **padding)

        # Секция файлов вложений
        tk.Label(self.root, text="Файлы с кодами вложений (дети):").pack(anchor='w', **padding)
        self.child_listbox = tk.Listbox(self.root, height=8)
        self.child_listbox.pack(fill='both', expand=True, **padding)

        btn_frame = tk.Frame(self.root)
        btn_frame.pack(fill='x', **padding)
        tk.Button(btn_frame, text="Добавить файлы", command=self.select_child_files).pack(side='left', padx=5)
        tk.Button(btn_frame, text="Очистить список", command=self.clear_children).pack(side='left', padx=5)

        # Кнопка запуска
        tk.Button(self.root, text="ЗАПУСТИТЬ АГРЕГАЦИЮ",
                  command=self.run_process,
                  bg='green', fg='white', font=('Arial', 10, 'bold'), height=2).pack(fill='x', **padding)

    def select_parent_file(self):
        path = filedialog.askopenfilename(filetypes=[("Text files", "*.txt")])
        if path:
            self.parent_file.set(path)

    def select_child_files(self):
        paths = filedialog.askopenfilenames(filetypes=[("Text files", "*.txt")])
        if paths:
            for p in paths:
                if p not in self.child_files:
                    self.child_files.append(p)
                    self.child_listbox.insert(tk.END, os.path.basename(p))

    def clear_children(self):
        self.child_files = []
        self.child_listbox.delete(0, tk.END)

    def run_process(self):
        try:
            if not self.parent_file.get():
                raise Exception("Выберите файл с кодами наборов.")
            if not self.child_files:
                raise Exception("Выберите хотя бы один файл с вложениями.")

            count = self.count_per_parent.get()
            if count <= 0:
                raise Exception("Количество вложений должно быть больше 0.")

            def ask_confirm(msg):
                return messagebox.askyesno("Подтверждение", msg)

            result_folder = perform_aggregation(
                self.parent_file.get(),
                self.child_files,
                count,
                output_callback=ask_confirm
            )

            if result_folder:
                messagebox.showinfo("Готово", f"Агрегация завершена!\nРезультаты в папке: {result_folder}")

        except Exception as e:
            error_msg = traceback.format_exc()
            messagebox.showerror("Ошибка", f"Произошла ошибка:\n{str(e)}\n\nПодробности:\n{error_msg}")

if __name__ == "__main__":
    root = tk.Tk()
    # Глобальный обработчик ошибок
    def show_error(*args):
        err = traceback.format_exc()
        messagebox.showerror("Критическая ошибка", err)

    root.report_callback_exception = show_error

    app = AggregationApp(root)
    root.mainloop()
