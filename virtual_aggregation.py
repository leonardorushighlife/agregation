"""
Скрипт для виртуальной агрегации кодов маркировки.

Инструкция по сборке в исполняемый файл (EXE):
1. Установите PyInstaller: pip install pyinstaller
2. Выполните команду сборки:
   pyinstaller --noconsole --onefile virtual_aggregation.py
3. Готовый исполняемый файл будет находиться в папке dist/

Скрипт совместим с ОС Windows 8, 10 и 11.
"""

import os
import sys
import datetime
import traceback

# Глобальный обработчик исключений для вывода traceback в messagebox
def show_error_and_exit(exc_type, exc_value, exc_traceback):
    tb_lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
    tb_text = "".join(tb_lines)
    print(tb_text, file=sys.stderr)
    try:
        from tkinter import messagebox
        messagebox.showerror(
            "Критическая ошибка / Critical Error",
            f"Произошла непредвиденная ошибка:\n\n{tb_text}"
        )
    except Exception:
        pass
    sys.exit(1)

sys.excepthook = show_error_and_exit


def read_codes(filepath):
    """
    Считывает коды маркировки из файла с поддержкой различных кодировок:
    UTF-8-SIG, UTF-16, UTF-8, CP1251.
    Возвращает список непустых очищенных строк.
    """
    encodings = ['utf-8-sig', 'utf-16', 'utf-8', 'windows-1251']
    for enc in encodings:
        try:
            with open(filepath, mode='r', encoding=enc) as f:
                content = f.read()
            # Проверяем, не пустой ли файл и корректно ли прочитался.
            # Очищаем строки
            raw_lines = content.splitlines()
            codes = []
            for line in raw_lines:
                stripped = line.strip()
                if stripped:
                    codes.append(stripped)
            return codes
        except (UnicodeError, LookupError):
            continue
    # Если ни одна кодировка не подошла, выбрасываем исключение
    raise ValueError(f"Не удалось определить кодировку или прочитать файл: {filepath}")


def sanitize_filename(filename):
    r"""
    Заменяет недопустимые символы в именах файлов на подчеркивания.
    Недопустимые символы: \ / : * ? " < > |
    """
    invalid_chars = ['\\', '/', ':', '*', '?', '"', '<', '>', '|']
    sanitized = filename
    for char in invalid_chars:
        sanitized = sanitized.replace(char, '_')
    return sanitized


def perform_aggregation(parent_file, child_files, count_per_parent, output_dir=None, confirm_callback=None):
    """
    Основная логика агрегации кодов.
    Считывает родительские коды из parent_file.
    Считывает дочерние коды из списка файлов child_files и объединяет их в пул.
    count_per_parent - количество вложений на один родительский код.
    output_dir - путь к директории для сохранения результатов (по умолчанию создается новая).
    confirm_callback - функция для подтверждения частичной агрегации, если кодов не хватает.
                       Должна принимать (available_children, required_children, actual_sets)
                       и возвращать True/False.
    """
    parent_codes = read_codes(parent_file)
    if not parent_codes:
        raise ValueError("Файл кодов наборов пуст.")

    child_codes_pool = []
    for cf in child_files:
        child_codes_pool.extend(read_codes(cf))

    if not child_codes_pool:
        raise ValueError("Выбранные файлы вложений пусты или не содержат кодов.")

    required_children = len(parent_codes) * count_per_parent
    actual_sets = len(parent_codes)

    if len(child_codes_pool) < required_children:
        # Недостаточно дочерних кодов для полной агрегации
        possible_sets = len(child_codes_pool) // count_per_parent
        actual_sets = min(len(parent_codes), possible_sets)

        if actual_sets == 0:
            raise ValueError(
                f"Недостаточно кодов вложений. Доступно: {len(child_codes_pool)}, "
                f"требуется минимум {count_per_parent} для одного набора."
            )

        if confirm_callback:
            proceed = confirm_callback(len(child_codes_pool), required_children, actual_sets)
            if not proceed:
                return None, None
        else:
            # Если коллбека нет, по умолчанию продолжаем с частичными результатами
            pass

    if output_dir is None:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = f"aggregation_results_{timestamp}"

    os.makedirs(output_dir, exist_ok=True)

    used_filepaths = set()
    created_files_count = 0

    for i in range(actual_sets):
        p_code = parent_codes[i]
        c_codes = child_codes_pool[i * count_per_parent : (i + 1) * count_per_parent]

        base_name = sanitize_filename(p_code)
        filename = f"{base_name}.txt"
        filepath = os.path.join(output_dir, filename)

        counter = 1
        while filepath in used_filepaths or os.path.exists(filepath):
            filename = f"{base_name}_{counter}.txt"
            filepath = os.path.join(output_dir, filename)
            counter += 1

        used_filepaths.add(filepath)

        # Запись в кодировке UTF-8 без BOM
        with open(filepath, mode='w', encoding='utf-8', newline='') as out_f:
            out_f.write(p_code + '\n')
            for c_code in c_codes:
                out_f.write(c_code + '\n')

        created_files_count += 1

    return created_files_count, output_dir


class AggregationGUI:
    """
    Класс для отрисовки графического интерфейса Tkinter на русском языке.
    """
    def __init__(self, root):
        self.root = root
        self.root.title("Виртуальная Агрегация в Наборы")
        self.root.geometry("650x500")
        self.root.minsize(550, 400)

        # Переменные интерфейса
        self.parent_filepath = ""
        self.child_filepaths = []

        self.create_widgets()

    def create_widgets(self):
        from tkinter import ttk, StringVar

        style = ttk.Style()
        style.theme_use('clam')

        # Основной контейнер
        main_frame = ttk.Frame(self.root, padding="15")
        main_frame.pack(fill="both", expand=True)

        # Секция 1: Родительский файл (Наборы)
        parent_lf = ttk.LabelFrame(main_frame, text=" 1. Выберите файл с кодами НАБОРОВ (Родительские коды) ", padding="10")
        parent_lf.pack(fill="x", pady=5)

        self.parent_label_var = StringVar(value="Файл не выбран")
        parent_lbl = ttk.Label(parent_lf, textvariable=self.parent_label_var, wraplength=500, foreground="blue")
        parent_lbl.pack(side="left", fill="x", expand=True)

        parent_btn = ttk.Button(parent_lf, text="Обзор...", command=self.select_parent_file)
        parent_btn.pack(side="right")

        # Секция 2: Количество вложений
        count_lf = ttk.LabelFrame(main_frame, text=" 2. Количество вложений в один набор ", padding="10")
        count_lf.pack(fill="x", pady=5)

        ttk.Label(count_lf, text="Введите количество штук содержимого на 1 набор:").pack(side="left", padx=5)
        self.count_var = StringVar(value="4")
        count_entry = ttk.Entry(count_lf, textvariable=self.count_var, width=10)
        count_entry.pack(side="left", padx=5)

        # Секция 3: Дочерние файлы (Вложения)
        child_lf = ttk.LabelFrame(main_frame, text=" 3. Выберите файлы с кодами маркировки СОДЕРЖИМОГО (Вложения) ", padding="10")
        child_lf.pack(fill="both", expand=True, pady=5)

        self.child_listbox_frame = ttk.Frame(child_lf)
        self.child_listbox_frame.pack(fill="both", expand=True)

        from tkinter import Listbox
        self.child_listbox = Listbox(self.child_listbox_frame, selectmode="extended", height=6)
        self.child_listbox.pack(side="left", fill="both", expand=True)

        scrollbar = ttk.Scrollbar(self.child_listbox_frame, orient="vertical", command=self.child_listbox.yview)
        scrollbar.pack(side="right", fill="y")
        self.child_listbox.config(yscrollcommand=scrollbar.set)

        child_btn_frame = ttk.Frame(child_lf)
        child_btn_frame.pack(fill="x", pady=5)

        child_add_btn = ttk.Button(child_btn_frame, text="Добавить файлы...", command=self.add_child_files)
        child_add_btn.pack(side="left", padx=5)

        child_clear_btn = ttk.Button(child_btn_frame, text="Очистить список", command=self.clear_child_files)
        child_clear_btn.pack(side="left", padx=5)

        # Секция 4: Кнопка запуска агрегации
        action_frame = ttk.Frame(main_frame, padding="5")
        action_frame.pack(fill="x", pady=10)

        start_btn = ttk.Button(action_frame, text="НАЧАТЬ АГРЕГАЦИЮ", command=self.run_aggregation)
        start_btn.pack(fill="x", ipady=10)

    def select_parent_file(self):
        from tkinter import filedialog
        file_path = filedialog.askopenfilename(
            title="Выберите файл с кодами маркировки наборов",
            filetypes=[("Текстовые файлы", "*.txt"), ("Все файлы", "*.*")]
        )
        if file_path:
            self.parent_filepath = file_path
            self.parent_label_var.set(os.path.basename(file_path))

    def add_child_files(self):
        from tkinter import filedialog
        file_paths = filedialog.askopenfilenames(
            title="Выберите файлы с кодами вложений",
            filetypes=[("Текстовые файлы", "*.txt"), ("Все файлы", "*.*")]
        )
        if file_paths:
            for path in file_paths:
                if path not in self.child_filepaths:
                    self.child_filepaths.append(path)
                    self.child_listbox.insert("end", os.path.basename(path))

    def clear_child_files(self):
        self.child_filepaths = []
        self.child_listbox.delete(0, "end")

    def run_aggregation(self):
        from tkinter import messagebox
        if not self.parent_filepath:
            messagebox.showwarning("Предупреждение", "Пожалуйста, выберите файл с кодами наборов.")
            return

        if not self.child_filepaths:
            messagebox.showwarning("Предупреждение", "Пожалуйста, выберите хотя бы один файл с кодами вложений.")
            return

        try:
            count_val = int(self.count_var.get().strip())
            if count_val <= 0:
                raise ValueError()
        except ValueError:
            messagebox.showerror("Ошибка", "Количество вложений должно быть положительным целым числом.")
            return

        def gui_confirm_callback(available_children, required_children, actual_sets):
            return messagebox.askyesno(
                "Подтверждение",
                f"Внимание!\n\nДоступно кодов вложений: {available_children}\n"
                f"Требуется для полной агрегации: {required_children}\n\n"
                f"Будет создано только {actual_sets} полных наборов.\n"
                "Желаете продолжить с частичным результатом?"
            )

        try:
            count, out_dir = perform_aggregation(
                parent_file=self.parent_filepath,
                child_files=self.child_filepaths,
                count_per_parent=count_val,
                confirm_callback=gui_confirm_callback
            )
            if count is not None:
                abs_out_dir = os.path.abspath(out_dir)
                messagebox.showinfo(
                    "Успех",
                    f"Агрегация успешно завершена!\n\n"
                    f"Создано наборов (файлов): {count}\n"
                    f"Результаты сохранены в папку:\n{abs_out_dir}"
                )
        except Exception as e:
            messagebox.showerror("Ошибка агрегации", f"Произошла ошибка во время агрегации:\n\n{str(e)}")


if __name__ == "__main__":
    # Если запуск не в безголовом (headless) режиме (например, для тестов)
    import tkinter as tk
    root = tk.Tk()
    app = AggregationGUI(root)
    root.mainloop()
