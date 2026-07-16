"""
Скрипт для виртуальной агрегации кодов маркировки.

Инструкция по сборке в исполняемый файл (EXE):
1. Установите необходимые зависимости:
   pip install pyinstaller
2. Выполните команду сборки в терминале:
   pyinstaller --noconsole --onefile virtual_aggregation.py
3. Готовый файл virtual_aggregation.exe будет находиться в папке 'dist'.
"""

import os
import sys
import datetime
import traceback
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

# ---------------------------------------------------------------------------
# GLOBAL EXCEPTION HANDLER
# ---------------------------------------------------------------------------

def global_excepthook(exctype, value, tb):
    tb_text = "".join(traceback.format_exception(exctype, value, tb))
    messagebox.showerror("Критическая ошибка", f"Произошла непредвиденная ошибка:\n\n{tb_text}")
    sys.__excepthook__(exctype, value, tb)

sys.excepthook = global_excepthook

# ---------------------------------------------------------------------------
# CORE LOGIC (Headless Compatible)
# ---------------------------------------------------------------------------

def read_codes(filepath):
    """
    Читает коды маркировки из файла, пробуя различные кодировки.
    Удаляет пустые строки и лишние пробелы.
    """
    encodings = ['utf-8-sig', 'utf-16', 'utf-8', 'cp1251']
    for enc in encodings:
        try:
            with open(filepath, 'r', encoding=enc) as f:
                content = f.read()
            lines = [line.strip() for line in content.splitlines() if line.strip()]
            return lines
        except UnicodeDecodeError:
            continue
        except Exception:
            continue
    raise ValueError(f"Не удалось прочитать файл {filepath} с использованием поддерживаемых кодировок.")


def sanitize_filename(parent_code):
    """
    Заменяет недопустимые для имен файлов в Windows символы на нижнее подчеркивание.
    """
    invalid_chars = r'\/:*?"<>|'
    sanitized = parent_code
    for char in invalid_chars:
        sanitized = sanitized.replace(char, '_')
    return sanitized


def get_unique_filepath(output_dir, sanitized_base, extension=".txt"):
    """
    Возвращает уникальный путь к файлу в папке, добавляя суффикс при коллизии имен.
    """
    base_path = os.path.join(output_dir, sanitized_base + extension)
    if not os.path.exists(base_path):
        return base_path

    counter = 1
    while True:
        new_path = os.path.join(output_dir, f"{sanitized_base}_{counter}{extension}")
        if not os.path.exists(new_path):
            return new_path
        counter += 1


def perform_aggregation(parent_file, child_files, count_per_parent, output_dir_base=".", confirm_callback=None):
    """
    Выполняет виртуальную агрегацию кодов.
    """
    if not parent_file:
        raise ValueError("Не выбран файл с родительскими кодами наборов.")
    if not child_files:
        raise ValueError("Не выбраны файлы с дочерними кодами вложений.")
    if count_per_parent <= 0:
        raise ValueError("Количество вложений должно быть больше нуля.")

    parents = read_codes(parent_file)
    children = []
    for cf in child_files:
        children.extend(read_codes(cf))

    P = len(parents)
    C = len(children)
    n = count_per_parent

    if P == 0:
        raise ValueError("Файл с кодами наборов пуст.")
    if C == 0:
        raise ValueError("Выбранные файлы вложений пусты.")

    required_children = P * n

    if C < required_children:
        actual_sets = C // n
        if actual_sets == 0:
            raise ValueError(
                f"Недостаточно кодов вложений ({C}) для создания хотя бы одного набора с количеством вложений {n}."
            )

        actual_sets = min(P, actual_sets)

        if confirm_callback:
            msg = (
                f"Доступных кодов вложений ({C}) меньше, чем требуется для полной агрегации ({required_children}).\n"
                f"Выполнить частичную агрегацию ({actual_sets} наборов)?"
            )
            if not confirm_callback(msg):
                return None, None
    else:
        actual_sets = P

    # Создаем новую папку с временной меткой
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = os.path.join(output_dir_base, f"aggregation_results_{timestamp}")
    os.makedirs(output_dir, exist_ok=True)

    created_files = []
    for i in range(actual_sets):
        parent_code = parents[i]
        start_idx = i * n
        end_idx = start_idx + n
        current_children = children[start_idx:end_idx]

        sanitized = sanitize_filename(parent_code)
        if not sanitized:
            sanitized = "empty_parent_code"

        filepath = get_unique_filepath(output_dir, sanitized)

        with open(filepath, 'w', encoding='utf-8', newline='\n') as f:
            f.write(parent_code + '\n')
            for child in current_children:
                f.write(child + '\n')

        created_files.append(filepath)

    return output_dir, created_files


# ---------------------------------------------------------------------------
# TKINTER GUI
# ---------------------------------------------------------------------------

class VirtualAggregationApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Виртуальная агрегация кодов маркировки")
        self.root.geometry("680x520")
        self.root.minsize(600, 450)

        self.parent_filepath = ""
        self.child_filepaths = []

        self.create_widgets()

    def create_widgets(self):
        # Главный фрейм с отступами
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 1. Секция выбора родительского файла (набора)
        parent_frame = ttk.LabelFrame(main_frame, text=" 1. Выберите файл с кодами наборов (родительские коды) ", padding="10")
        parent_frame.pack(fill=tk.X, pady=(0, 10))

        self.parent_entry = ttk.Entry(parent_frame, state="readonly")
        self.parent_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))

        parent_btn = ttk.Button(parent_frame, text="Обзор...", command=self.select_parent_file)
        parent_btn.pack(side=tk.RIGHT)

        # 2. Секция выбора файлов вложений (дочерние коды)
        child_frame = ttk.LabelFrame(main_frame, text=" 2. Выберите файлы с кодами вложений (дочерние коды) ", padding="10")
        child_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        # Фрейм со списком и скроллбаром
        list_container = ttk.Frame(child_frame)
        list_container.pack(fill=tk.BOTH, expand=True, side=tk.LEFT, padx=(0, 5))

        self.scrollbar = ttk.Scrollbar(list_container, orient=tk.VERTICAL)
        self.child_listbox = tk.Listbox(list_container, yscrollcommand=self.scrollbar.set, selectmode=tk.EXTENDED)
        self.scrollbar.config(command=self.child_listbox.yview)

        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.child_listbox.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)

        # Кнопки управления списком дочерних файлов
        child_btn_frame = ttk.Frame(child_frame)
        child_btn_frame.pack(side=tk.RIGHT, fill=tk.Y)

        add_btn = ttk.Button(child_btn_frame, text="Добавить...", command=self.add_child_files)
        add_btn.pack(fill=tk.X, pady=(0, 5))

        clear_btn = ttk.Button(child_btn_frame, text="Очистить", command=self.clear_child_files)
        clear_btn.pack(fill=tk.X)

        # 3. Секция настроек (количество вложений)
        settings_frame = ttk.Frame(main_frame)
        settings_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(settings_frame, text="Количество вложений в один набор:").pack(side=tk.LEFT, padx=(0, 5))

        self.count_var = tk.StringVar(value="10")
        self.count_spinbox = ttk.Spinbox(
            settings_frame,
            from_=1,
            to=10000,
            textvariable=self.count_var,
            width=10
        )
        self.count_spinbox.pack(side=tk.LEFT)

        # 4. Кнопка выполнения агрегации
        self.aggregate_btn = ttk.Button(
            main_frame,
            text="Выполнить агрегацию",
            command=self.start_aggregation
        )
        self.aggregate_btn.pack(fill=tk.X, ipady=5, pady=(0, 10))

        # 5. Область логов / результатов
        log_frame = ttk.LabelFrame(main_frame, text=" Лог выполнения ", padding="5")
        log_frame.pack(fill=tk.X, side=tk.BOTTOM)

        self.log_text = tk.Text(log_frame, height=5, state="disabled", wrap=tk.WORD)
        self.log_text.pack(fill=tk.BOTH, expand=True)

    def log(self, message):
        self.log_text.config(state="normal")
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.log_text.config(state="disabled")

    def select_parent_file(self):
        filepath = filedialog.askopenfilename(
            title="Выберите файл с кодами наборов",
            filetypes=[("Текстовые файлы", "*.txt"), ("Все файлы", "*.*")]
        )
        if filepath:
            self.parent_filepath = filepath
            self.parent_entry.config(state="normal")
            self.parent_entry.delete(0, tk.END)
            self.parent_entry.insert(0, filepath)
            self.parent_entry.config(state="readonly")
            self.log(f"Выбран файл наборов: {os.path.basename(filepath)}")

    def add_child_files(self):
        filepaths = filedialog.askopenfilenames(
            title="Выберите файлы с кодами вложений",
            filetypes=[("Текстовые файлы", "*.txt"), ("Все файлы", "*.*")]
        )
        if filepaths:
            for fp in filepaths:
                if fp not in self.child_filepaths:
                    self.child_filepaths.append(fp)
                    self.child_listbox.insert(tk.END, os.path.basename(fp))
                    self.log(f"Добавлен файл вложений: {os.path.basename(fp)}")

    def clear_child_files(self):
        self.child_filepaths.clear()
        self.child_listbox.delete(0, tk.END)
        self.log("Список файлов вложений очищен.")

    def start_aggregation(self):
        try:
            # Валидация количества вложений
            try:
                count_val = int(self.count_var.get())
                if count_val <= 0:
                    raise ValueError
            except ValueError:
                messagebox.showerror("Ошибка", "Количество вложений должно быть целым положительным числом.")
                return

            def confirm_dialog(msg):
                return messagebox.askyesno("Подтверждение", msg)

            # Вызываем основную логику
            result = perform_aggregation(
                parent_file=self.parent_filepath,
                child_files=self.child_filepaths,
                count_per_parent=count_val,
                output_dir_base=".",
                confirm_callback=confirm_dialog
            )

            if result is None or result[0] is None:
                self.log("Агрегация была отменена.")
                return

            output_dir, created_files = result

            self.log(f"Успешно завершено! Создана папка: {os.path.abspath(output_dir)}")
            self.log(f"Создано наборов: {len(created_files)}")

            messagebox.showinfo(
                "Успех",
                f"Агрегация успешно выполнена!\n\n"
                f"Создано наборов: {len(created_files)}\n"
                f"Результаты сохранены в папку:\n{os.path.abspath(output_dir)}"
            )

        except Exception as e:
            messagebox.showerror("Ошибка агрегации", str(e))
            self.log(f"Ошибка: {str(e)}")

def main():
    root = tk.Tk()
    app = VirtualAggregationApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
