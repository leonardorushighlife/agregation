"""
Утилита для виртуальной агрегации кодов маркировки.
Позволяет объединять родительские коды наборов и дочерние коды вложений в отдельные файлы.

Инструкция по сборке в исполняемый файл (EXE) с помощью PyInstaller:
1. Установите необходимые зависимости:
   pip install pyinstaller
2. Выполните команду для сборки:
   pyinstaller --noconsole --onefile virtual_aggregation.py
3. Исполняемый файл появится в папке dist/virtual_aggregation.exe
"""

import os
import sys
from datetime import datetime

# Функция для безопасного чтения кодов с автоопределением кодировки
def read_codes(filepath):
    encodings = ["utf-8-sig", "utf-16", "utf-8", "cp1251"]
    for enc in encodings:
        try:
            with open(filepath, "r", encoding=enc) as f:
                content = f.read()
                # Разделяем на строки, очищаем от пробельных символов и пропускаем пустые
                lines = content.splitlines()
                codes = [line.strip() for line in lines if line.strip()]
                return codes
        except (UnicodeError, LookupError):
            continue
    raise ValueError(f"Не удалось прочитать файл {filepath} с использованием поддерживаемых кодировок.")

# Функция санитарной очистки имени файла для Windows
def sanitize_filename(name):
    # Символы, недопустимые в именах файлов Windows: \ / : * ? " < > |
    for c in r'\/:*?"<>|':
        name = name.replace(c, "_")
    return name

# Основная функция агрегации
def perform_aggregation(parent_file, child_files, count_per_parent, output_dir_base=None, confirm_callback=None):
    if count_per_parent <= 0:
        raise ValueError("Количество вложений должно быть больше 0.")

    parent_codes = read_codes(parent_file)
    if not parent_codes:
        raise ValueError("Файл кодов наборов пуст.")

    all_child_codes = []
    for cf in child_files:
        all_child_codes.extend(read_codes(cf))

    if not all_child_codes:
        raise ValueError("Файлы кодов вложений пусты.")

    total_parents = len(parent_codes)
    total_required_children = total_parents * count_per_parent
    actual_children_available = len(all_child_codes)

    if actual_children_available < total_required_children:
        if confirm_callback:
            proceed = confirm_callback(actual_children_available, total_required_children)
            if not proceed:
                return None
        actual_sets = actual_children_available // count_per_parent
    else:
        actual_sets = total_parents

    if actual_sets == 0:
        raise ValueError("Недостаточно кодов вложений для сборки хотя бы одного полного набора.")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    folder_name = f"aggregation_results_{timestamp}"
    if output_dir_base:
        out_dir = os.path.join(output_dir_base, folder_name)
    else:
        out_dir = os.path.abspath(folder_name)

    os.makedirs(out_dir, exist_ok=True)

    created_files = []
    used_filenames = set()

    for i in range(actual_sets):
        parent_code = parent_codes[i]
        start_idx = i * count_per_parent
        end_idx = start_idx + count_per_parent
        attachments = all_child_codes[start_idx:end_idx]

        sanitized = sanitize_filename(parent_code)
        filename = f"{sanitized}.txt"
        filepath = os.path.join(out_dir, filename)
        suffix = 1
        while filepath.lower() in used_filenames:
            filename = f"{sanitized}_{suffix}.txt"
            filepath = os.path.join(out_dir, filename)
            suffix += 1

        used_filenames.add(filepath.lower())

        # Сохранение в кодировке UTF-8 без BOM с переводами строк \n
        with open(filepath, "w", encoding="utf-8", newline="\n") as f:
            f.write(parent_code + "\n")
            for att in attachments:
                f.write(att + "\n")

        created_files.append(filepath)

    return out_dir, len(created_files)

# GUI-класс с ленивым импортом tkinter
class VirtualAggregationApp:
    def __init__(self):
        import tkinter as tk
        from tkinter import ttk, filedialog, messagebox
        self.tk = tk
        self.ttk = ttk
        self.filedialog = filedialog
        self.messagebox = messagebox

        self.root = tk.Tk()
        self.root.title("Виртуальная Агрегация")
        self.root.geometry("640x480")
        self.root.resizable(False, False)

        self.parent_file = ""
        self.child_files = []

        self.create_widgets()

    def create_widgets(self):
        # Frame для выбора родительского файла
        parent_frame = self.ttk.LabelFrame(self.root, text=" 1. Выберите файл кодов маркировки набора (Родительские коды) ", padding=10)
        parent_frame.pack(fill="x", padx=15, pady=10)

        self.parent_btn = self.ttk.Button(parent_frame, text="Выбрать файл...", command=self.select_parent_file)
        self.parent_btn.pack(side="left", padx=5)

        self.parent_lbl = self.ttk.Label(parent_frame, text="Файл не выбран", foreground="gray", wraplength=450)
        self.parent_lbl.pack(side="left", padx=5, fill="x", expand=True)

        # Frame для выбора количества вложений
        count_frame = self.ttk.LabelFrame(self.root, text=" 2. Укажите количество вложений в один набор ", padding=10)
        count_frame.pack(fill="x", padx=15, pady=10)

        self.ttk.Label(count_frame, text="Количество вложений:").pack(side="left", padx=5)
        self.count_var = self.tk.StringVar(value="4")
        self.count_entry = self.ttk.Entry(count_frame, textvariable=self.count_var, width=10)
        self.count_entry.pack(side="left", padx=5)

        # Frame для выбора файлов вложений
        child_frame = self.ttk.LabelFrame(self.root, text=" 3. Выберите файлы кодов маркировки содержимого (Вложения) ", padding=10)
        child_frame.pack(fill="x", padx=15, pady=10)

        self.child_btn = self.ttk.Button(child_frame, text="Выбрать файлы...", command=self.select_child_files)
        self.child_btn.pack(side="left", padx=5)

        self.child_lbl = self.ttk.Label(child_frame, text="Файлы не выбраны", foreground="gray", wraplength=450)
        self.child_lbl.pack(side="left", padx=5, fill="x", expand=True)

        # Кнопка Запуска
        self.run_btn = self.ttk.Button(self.root, text="Выполнить агрегацию", style="Accent.TButton", command=self.run_aggregation)
        self.run_btn.pack(pady=25)

        # Стилизация кнопки агрегации
        style = self.ttk.Style()
        style.configure("Accent.TButton", font=("Arial", 12, "bold"))

    def select_parent_file(self):
        file = self.filedialog.askopenfilename(
            title="Выберите файл кодов набора",
            filetypes=[("Текстовые файлы", "*.txt"), ("Все файлы", "*.*")]
        )
        if file:
            self.parent_file = file
            self.parent_lbl.config(text=os.path.basename(file), foreground="black")

    def select_child_files(self):
        files = self.filedialog.askopenfilenames(
            title="Выберите файлы кодов содержимого",
            filetypes=[("Текстовые файлы", "*.txt"), ("Все файлы", "*.*")]
        )
        if files:
            self.child_files = list(files)
            if len(files) == 1:
                text = os.path.basename(files[0])
            else:
                text = f"Выбрано файлов: {len(files)}"
            self.child_lbl.config(text=text, foreground="black")

    def confirm_callback(self, available, required):
        return self.messagebox.askyesno(
            "Предупреждение",
            f"Доступно кодов вложений ({available}) меньше, чем требуется ({required}) для всех наборов.\n"
            f"Выполнить частичную агрегацию?"
        )

    def run_aggregation(self):
        if not self.parent_file:
            self.messagebox.showerror("Ошибка", "Пожалуйста, выберите файл с кодами наборов.")
            return

        if not self.child_files:
            self.messagebox.showerror("Ошибка", "Пожалуйста, выберите файлы с кодами вложений.")
            return

        try:
            count = int(self.count_var.get())
            if count <= 0:
                raise ValueError
        except ValueError:
            self.messagebox.showerror("Ошибка", "Введите корректное положительное число вложений.")
            return

        try:
            res = perform_aggregation(
                self.parent_file,
                self.child_files,
                count,
                confirm_callback=self.confirm_callback
            )
            if res is None:
                self.messagebox.showinfo("Отмена", "Операция отменена пользователем.")
                return

            out_dir, total_files = res
            self.messagebox.showinfo(
                "Успех",
                f"Агрегация успешно завершена!\n"
                f"Создано файлов: {total_files}\n"
                f"Результаты сохранены в папку:\n{out_dir}"
            )
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            self.messagebox.showerror("Ошибка агрегации", f"Произошла ошибка:\n{str(e)}\n\nЛог ошибки:\n{tb}")

    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    # Если запуск не как модуль (например, при сборке в exe или тестировании)
    app = VirtualAggregationApp()
    app.run()
