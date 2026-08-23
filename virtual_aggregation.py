"""
Скрипт для виртуальной агрегации кодов маркировки.

Инструкция по сборке в исполняемый файл (EXE):
1. Установите PyInstaller (если не установлен):
   pip install pyinstaller
2. Запустите сборку из командной строки:
   pyinstaller --noconsole --onefile virtual_aggregation.py
3. Готовый исполняемый файл появится в папке `dist/virtual_aggregation.exe`.
"""

import os
import re
import sys
import traceback
from datetime import datetime

# Ленивый / защищенный импорт tkinter для сохранения возможности запуска чистой логики без GUI
try:
    import tkinter as tk
    from tkinter import filedialog, messagebox
    HAS_TK = True
except ImportError:
    HAS_TK = False


def sanitize_filename(filename: str) -> str:
    """
    Заменяет недопустимые в именах файлов Windows символы на подчеркивание.
    """
    return re.sub(r'[\\/*?:"<>|]', '_', filename).strip()


def read_codes(file_path: str) -> list[str]:
    """
    Считывает маркировочные коды из TXT файла, поддерживая разные кодировки.
    Возвращает список непустых очищенных строк.
    """
    encodings = ['utf-8-sig', 'utf-16', 'utf-8', 'cp1251']
    for enc in encodings:
        try:
            with open(file_path, 'r', encoding=enc) as f:
                lines = [line.strip() for line in f if line.strip()]
            return lines
        except (UnicodeError, LookupError):
            continue
    # Если ни одна кодировка не подошла, пробуем с 'utf-8' и заменой ошибок
    with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
        return [line.strip() for line in f if line.strip()]


def perform_aggregation(parent_codes: list[str], child_codes: list[str], count_per_parent: int, confirm_callback=None) -> tuple[int, str]:
    """
    Выполняет виртуальную агрегацию кодов.

    :param parent_codes: Список родительских кодов (наборы)
    :param child_codes: Список дочерних кодов (вложения)
    :param count_per_parent: Количество вложений на один набор
    :param confirm_callback: Функция обратного вызова (bool) для запроса подтверждения при нехватке кодов
    :return: Кортеж (количество_созданных_файлов, путь_к_папке)
    """
    if not parent_codes:
        raise ValueError("Список родительских кодов пуст.")
    if not child_codes:
        raise ValueError("Список дочерних кодов пуст.")
    if count_per_parent <= 0:
        raise ValueError("Количество вложений должно быть больше 0.")

    total_required_children = len(parent_codes) * count_per_parent
    actual_children = len(child_codes)

    if actual_children < total_required_children:
        actual_sets = actual_children // count_per_parent
        msg = (
            f"Внимание: Недостаточно дочерних кодов для полной агрегации!\n\n"
            f"Родительских кодов: {len(parent_codes)}\n"
            f"Дочерних кодов: {actual_children}\n"
            f"Требуется на набор: {count_per_parent}\n"
            f"Всего требуется дочерних кодов: {total_required_children}\n\n"
            f"Сформировано будет наборов: {actual_sets} из {len(parent_codes)}.\n"
            f"Продолжить с частичной агрегацией?"
        )
        if confirm_callback:
            if not confirm_callback(msg):
                return 0, ""
        parent_codes = parent_codes[:actual_sets]

    if not parent_codes:
        raise ValueError("Недостаточно дочерних кодов даже для формирования одного полного набора.")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    folder_name = f"aggregation_results_{timestamp}"
    os.makedirs(folder_name, exist_ok=True)

    used_filenames = set()
    created_count = 0

    for i, parent_code in enumerate(parent_codes):
        start_idx = i * count_per_parent
        end_idx = start_idx + count_per_parent
        current_children = child_codes[start_idx:end_idx]

        base_filename = sanitize_filename(parent_code)
        if not base_filename:
            base_filename = f"set_{i + 1}"

        filename = base_filename
        suffix = 1
        while filename in used_filenames:
            filename = f"{base_filename}_{suffix}"
            suffix += 1
        used_filenames.add(filename)

        file_path = os.path.join(folder_name, f"{filename}.txt")
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(parent_code + '\n')
            for child in current_children:
                f.write(child + '\n')

        created_count += 1

    return created_count, folder_name


class AggregationGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Виртуальная агрегация наборов")
        self.root.geometry("580x480")
        self.root.resizable(False, False)

        self.parent_file_path = ""
        self.child_file_paths = []

        self.create_widgets()

    def create_widgets(self):
        # Перехват глобальных исключений
        self.root.report_callback_exception = self.show_error_traceback

        # Выбор файла родительских кодов
        frame_parent = tk.LabelFrame(self.root, text="1. Файл кодов маркировки наборов (родительские)", padx=10, pady=10)
        frame_parent.pack(fill="x", padx=15, pady=10)

        self.btn_parent = tk.Button(frame_parent, text="Выбрать файл наборов", command=self.select_parent_file)
        self.btn_parent.pack(side="left", padx=5)

        self.lbl_parent = tk.Label(frame_parent, text="Файл не выбран", anchor="w", fg="gray")
        self.lbl_parent.pack(side="left", fill="x", expand=True, padx=5)

        # Выбор файлов дочерних кодов
        frame_child = tk.LabelFrame(self.root, text="2. Файлы кодов маркировки содержимого (вложения)", padx=10, pady=10)
        frame_child.pack(fill="x", padx=15, pady=10)

        self.btn_child = tk.Button(frame_child, text="Выбрать файлы вложений", command=self.select_child_files)
        self.btn_child.pack(side="left", padx=5)

        self.lbl_child = tk.Label(frame_child, text="Файлы не выбраны", anchor="w", fg="gray")
        self.lbl_child.pack(side="left", fill="x", expand=True, padx=5)

        # Количество вложений
        frame_count = tk.LabelFrame(self.root, text="3. Параметры агрегации", padx=10, pady=10)
        frame_count.pack(fill="x", padx=15, pady=10)

        tk.Label(frame_count, text="Количество вложений в 1 набор:").pack(side="left", padx=5)
        self.entry_count = tk.Entry(frame_count, width=10)
        self.entry_count.pack(side="left", padx=5)
        self.entry_count.insert(0, "4")

        # Кнопка запуска
        self.btn_start = tk.Button(
            self.root,
            text="Запустить агрегацию",
            font=("Arial", 12, "bold"),
            bg="#4CAF50",
            fg="white",
            height=2,
            command=self.start_aggregation
        )
        self.btn_start.pack(fill="x", padx=15, pady=20)

    def show_error_traceback(self, exc_type, exc_value, exc_traceback):
        err_msg = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        messagebox.showerror("Ошибка", f"Произошла непредвиденная ошибка:\n\n{err_msg}")

    def select_parent_file(self):
        file_path = filedialog.askopenfilename(
            title="Выберите TXT файл с кодами наборов",
            filetypes=[("Текстовые файлы", "*.txt"), ("Все файлы", "*.*")]
        )
        if file_path:
            self.parent_file_path = file_path
            self.lbl_parent.config(text=os.path.basename(file_path), fg="black")

    def select_child_files(self):
        file_paths = filedialog.askopenfilenames(
            title="Выберите TXT файлы с кодами вложений",
            filetypes=[("Текстовые файлы", "*.txt"), ("Все файлы", "*.*")]
        )
        if file_paths:
            self.child_file_paths = list(file_paths)
            count = len(self.child_file_paths)
            self.lbl_child.config(text=f"Выбрано файлов: {count}", fg="black")

    def start_aggregation(self):
        if not self.parent_file_path:
            messagebox.showwarning("Ошибка", "Пожалуйста, выберите файл кодов наборов.")
            return

        if not self.child_file_paths:
            messagebox.showwarning("Ошибка", "Пожалуйста, выберите хотя бы один файл кодов вложений.")
            return

        try:
            count_per_parent = int(self.entry_count.get().strip())
            if count_per_parent <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Ошибка", "Количество вложений должно быть целым положительным числом.")
            return

        try:
            parent_codes = read_codes(self.parent_file_path)
            child_codes = []
            for cp in self.child_file_paths:
                child_codes.extend(read_codes(cp))

            def confirm_cb(msg):
                return messagebox.askyesno("Подтверждение", msg)

            created_count, folder_name = perform_aggregation(
                parent_codes, child_codes, count_per_parent, confirm_callback=confirm_cb
            )

            if created_count > 0:
                messagebox.showinfo(
                    "Успех",
                    f"Агрегация завершена успешно!\n\n"
                    f"Создано файлов наборов: {created_count}\n"
                    f"Папка с результатами:\n{os.path.abspath(folder_name)}"
                )

        except Exception as e:
            messagebox.showerror("Ошибка", str(e))


def main():
    if not HAS_TK:
        print("Ошибка: Tkinter недоступен в данной среде.")
        sys.exit(1)
    root = tk.Tk()
    app = AggregationGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
