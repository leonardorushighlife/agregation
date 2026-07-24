"""
Виртуальная агрегация кодов маркировки.
Этот скрипт группирует коды маркировки набора и коды вложений в отдельные файлы.

Инструкция по сборке в exe:
1. Установите PyInstaller:
   pip install pyinstaller
2. Выполните команду сборки в консоли:
   pyinstaller --noconsole --onefile virtual_aggregation.py
3. Скомпилированный файл будет находиться в папке dist/virtual_aggregation.exe
"""

import os
import sys
import re
from datetime import datetime

# Ленивый импорт tkinter для headless-тестирования
def get_tkinter():
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
    return tk, filedialog, messagebox, ttk


def sanitize_filename(name: str) -> str:
    """
    Заменяет недопустимые для имени файла символы на знак подчеркивания.
    """
    # Символы, недопустимые в Windows: \ / : * ? " < > |
    invalid_chars = r'[\\/:*?"<>|]'
    sanitized = re.sub(invalid_chars, '_', name)
    return sanitized.strip()


def read_codes(filepath: str) -> list:
    """
    Читает коды из файла, пробуя разные кодировки по очереди:
    UTF-8-SIG, UTF-16, UTF-8, CP1251.
    """
    encodings = ['utf-8-sig', 'utf-16', 'utf-8', 'windows-1251']
    content = ""
    for encoding in encodings:
        try:
            with open(filepath, 'r', encoding=encoding) as f:
                content = f.read()
            break
        except Exception:
            continue
    else:
        raise ValueError(f"Не удалось прочитать файл {filepath} с использованием поддерживаемых кодировок.")

    # Разделяем на строки и очищаем
    lines = [line.strip() for line in content.splitlines() if line.strip()]
    return lines


def perform_aggregation(parent_file: str, child_files: list, count_per_parent: int, confirm_callback=None) -> tuple:
    """
    Выполняет агрегацию кодов.
    Возвращает (путь к созданной папке, количество успешно собранных наборов).
    """
    if not parent_file:
        raise ValueError("Не выбран файл с кодами наборов.")
    if not child_files:
        raise ValueError("Не выбраны файлы с кодами вложений.")
    if count_per_parent <= 0:
        raise ValueError("Количество вложений должно быть больше нуля.")

    parent_codes = read_codes(parent_file)
    if not parent_codes:
        raise ValueError("Файл кодов наборов пуст.")

    child_codes = []
    for cf in child_files:
        child_codes.extend(read_codes(cf))

    if not child_codes:
        raise ValueError("Файлы кодов вложений пусты.")

    total_required = len(parent_codes) * count_per_parent
    actual_sets = len(parent_codes)

    if len(child_codes) < total_required:
        actual_sets = len(child_codes) // count_per_parent
        if actual_sets == 0:
            raise ValueError(
                f"Недостаточно кодов вложений даже для одного набора.\n"
                f"Требуется кодов на один набор: {count_per_parent}, "
                f"всего доступно вложений: {len(child_codes)}."
            )

        if confirm_callback:
            msg = (
                f"Доступных дочерних кодов ({len(child_codes)}) недостаточно для полного заполнения "
                f"всех родительских кодов ({len(parent_codes)}) по {count_per_parent} шт.\n"
                f"Будет собрано только {actual_sets} наборов.\n\n"
                f"Продолжить?"
            )
            if not confirm_callback(msg):
                raise ValueError("Операция отменена пользователем.")
        else:
            # Если callback отсутствует, продолжаем по умолчанию
            pass

    # Создание папки результатов
    parent_dir = os.path.dirname(os.path.abspath(parent_file))
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir_name = f"aggregation_results_{timestamp}"
    output_dir = os.path.join(parent_dir, output_dir_name)
    os.makedirs(output_dir, exist_ok=True)

    # Словарь для отслеживания уникальности имен файлов в рамках текущей папки
    used_filenames = set()

    for i in range(actual_sets):
        p_code = parent_codes[i]
        c_codes = child_codes[i * count_per_parent : (i + 1) * count_per_parent]

        base_filename = sanitize_filename(p_code)
        filename = f"{base_filename}.txt"
        file_path = os.path.join(output_dir, filename)

        # Обработка коллизий
        suffix = 1
        while filename.lower() in used_filenames or os.path.exists(file_path):
            filename = f"{base_filename}_{suffix}.txt"
            file_path = os.path.join(output_dir, filename)
            suffix += 1

        used_filenames.add(filename.lower())

        # Запись в кодировке UTF-8 без BOM
        with open(file_path, 'w', encoding='utf-8', newline='\n') as out_f:
            out_f.write(p_code + '\n')
            for c_code in c_codes:
                out_f.write(c_code + '\n')

    return output_dir, actual_sets


# -----------------------------------------------------------------------------
# ИНТЕРФЕЙС ТКINTER
# -----------------------------------------------------------------------------

class VirtualAggregationApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Виртуальная агрегация")
        self.root.geometry("650x550")
        self.root.resizable(True, True)

        self.parent_file = ""
        self.child_files = []

        self.create_widgets()

    def create_widgets(self):
        tk, filedialog, messagebox, ttk = get_tkinter()

        # Главный фрейм с отступами
        main_frame = ttk.Frame(self.root, padding="15")
        main_frame.pack(fill="both", expand=True)

        # Секция 1: Родительский файл
        parent_lf = ttk.LabelFrame(main_frame, text=" 1. Коды наборов (Родительские коды) ", padding="10")
        parent_lf.pack(fill="x", pady=5)

        self.parent_btn = ttk.Button(parent_lf, text="Выбрать файл...", command=self.select_parent_file)
        self.parent_btn.pack(side="left", padx=5)

        self.parent_label = ttk.Label(parent_lf, text="Файл не выбран", wraplength=450, foreground="gray")
        self.parent_label.pack(side="left", padx=5, fill="x", expand=True)

        # Секция 2: Количество вложений
        count_lf = ttk.LabelFrame(main_frame, text=" 2. Параметры ", padding="10")
        count_lf.pack(fill="x", pady=5)

        ttk.Label(count_lf, text="Количество вложений в один набор:").pack(side="left", padx=5)
        self.count_var = tk.StringVar(value="4")
        self.count_entry = ttk.Entry(count_lf, textvariable=self.count_var, width=10)
        self.count_entry.pack(side="left", padx=5)

        # Секция 3: Дочерние файлы
        child_lf = ttk.LabelFrame(main_frame, text=" 3. Коды содержимого (Вложения) ", padding="10")
        child_lf.pack(fill="both", expand=True, pady=5)

        child_btn_frame = ttk.Frame(child_lf)
        child_btn_frame.pack(fill="x")

        self.child_btn = ttk.Button(child_btn_frame, text="Выбрать файлы...", command=self.select_child_files)
        self.child_btn.pack(side="left", padx=5)

        self.clear_child_btn = ttk.Button(child_btn_frame, text="Очистить список", command=self.clear_child_files)
        self.clear_child_btn.pack(side="left", padx=5)

        # Список выбранных файлов
        self.child_listbox = tk.Listbox(child_lf, height=8)
        self.child_listbox.pack(fill="both", expand=True, pady=5, padx=5)

        # Скроллбар для списка
        scrollbar = ttk.Scrollbar(self.child_listbox, orient="vertical", command=self.child_listbox.yview)
        scrollbar.pack(side="right", fill="y")
        self.child_listbox.config(yscrollcommand=scrollbar.set)

        # Секция 4: Запуск
        self.run_btn = ttk.Button(main_frame, text="Запустить агрегацию", command=self.run_aggregation, style="Accent.TButton")
        self.run_btn.pack(pady=10, fill="x")

        # Настройка стиля кнопки
        style = ttk.Style()
        style.configure("Accent.TButton", font=("Arial", 11, "bold"))

    def select_parent_file(self):
        tk, filedialog, messagebox, ttk = get_tkinter()
        filepath = filedialog.askopenfilename(
            title="Выберите файл с кодами наборов",
            filetypes=[("Текстовые файлы", "*.txt"), ("Все файлы", "*.*")]
        )
        if filepath:
            self.parent_file = filepath
            self.parent_label.config(text=os.path.basename(filepath), foreground="black")

    def select_child_files(self):
        tk, filedialog, messagebox, ttk = get_tkinter()
        filepaths = filedialog.askopenfilenames(
            title="Выберите файлы с кодами вложений",
            filetypes=[("Текстовые файлы", "*.txt"), ("Все файлы", "*.*")]
        )
        if filepaths:
            for fp in filepaths:
                if fp not in self.child_files:
                    self.child_files.append(fp)
                    self.child_listbox.insert(tk.END, os.path.basename(fp))

    def clear_child_files(self):
        self.child_files = []
        self.child_listbox.delete(0, 'end')

    def run_aggregation(self):
        tk, filedialog, messagebox, ttk = get_tkinter()
        try:
            try:
                count = int(self.count_var.get())
                if count <= 0:
                    raise ValueError()
            except ValueError:
                messagebox.showerror("Ошибка", "Количество вложений должно быть целым положительным числом.")
                return

            def confirm_dialog(msg):
                return messagebox.askyesno("Внимание", msg)

            output_dir, actual_sets = perform_aggregation(
                parent_file=self.parent_file,
                child_files=self.child_files,
                count_per_parent=count,
                confirm_callback=confirm_dialog
            )

            messagebox.showinfo(
                "Успех",
                f"Агрегация успешно завершена!\n"
                f"Создано наборов: {actual_sets}\n"
                f"Результаты сохранены в папку:\n{output_dir}"
            )

        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            messagebox.showerror(
                "Ошибка при агрегации",
                f"Произошла ошибка во время выполнения агрегации:\n\n{str(e)}\n\nПодробности:\n{tb}"
            )


def main():
    try:
        tk, filedialog, messagebox, ttk = get_tkinter()
    except ImportError:
        # headless-режим или отсутствие tkinter (например, при тестировании)
        print("Интерфейс Tkinter не поддерживается или отсутствует.")
        sys.exit(1)

    root = tk.Tk()
    app = VirtualAggregationApp(root)

    # Глобальный перехват исключений для GUI
    def show_error(self, *args):
        import traceback
        err = traceback.format_exception(*args)
        messagebox.showerror("Критическая ошибка", f"Произошло необработанное исключение:\n\n{''.join(err)}")

    tk.Tk.report_callback_exception = show_error

    root.mainloop()


if __name__ == "__main__":
    main()
