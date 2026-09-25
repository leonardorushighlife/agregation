"""
Виртуальная агрегация наборов кодов маркировки.

Инструкция по сборке в EXE:
1. Установите PyInstaller: pip install pyinstaller
2. Выполните команду сборки:
   pyinstaller --noconsole --onefile virtual_aggregation.py
3. Исполняемый файл virtual_aggregation.exe будет создан в папке dist/
"""

import os
import re
import sys
import traceback
from datetime import datetime

# Guarded imports for tkinter to allow headless testing of core logic
try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
    HAS_TK = True
except ImportError:
    HAS_TK = False


def read_codes(file_path):
    """
    Считывает строки из файла с последовательным опросом нескольких кодировок.
    Возвращает список непустых очищенных от внешних пробелов строк.
    """
    encodings = ["utf-8-sig", "utf-16", "utf-8", "cp1251"]
    for enc in encodings:
        try:
            with open(file_path, "r", encoding=enc) as f:
                lines = [line.strip() for line in f if line.strip()]
            return lines
        except (UnicodeError, LookupError):
            continue
    raise ValueError(f"Не удалось прочитать файл {file_path}. Поддерживаемые кодировки: UTF-8, UTF-16, CP1251.")


def sanitize_filename(name):
    """
    Заменяет недопустимые для имен файлов символы на подчёркивание.
    """
    sanitized = re.sub(r'[\\/:*?"<>|]', '_', name).strip()
    if not sanitized:
        sanitized = "set_code"
    return sanitized


def perform_aggregation(parent_file, child_files, count_per_parent, confirm_callback=None, output_base_dir=None):
    """
    Выполняет виртуальную агрегацию.

    :param parent_file: Путь к файлу с кодами наборов (родительские коды)
    :param child_files: Список путей к файлам с кодами вложений (дочерние коды)
    :param count_per_parent: Количество вложений в один набор
    :param confirm_callback: Функция обратного вызова для подтверждения продолжения при нехватке кодов
    :param output_base_dir: Базовая директория для создания итоговой папки (по умолчанию текущая директория)
    :return: Кортеж (успех: bool, сообщение: str, путь_к_папке: str)
    """
    if count_per_parent <= 0:
        return False, "Количество вложений должно быть больше 0.", None

    if not parent_file or not os.path.exists(parent_file):
        return False, "Родительский файл не выбран или не существует.", None

    if not child_files:
        return False, "Файлы вложений не выбраны.", None

    try:
        parent_codes = read_codes(parent_file)
    except Exception as e:
        return False, f"Ошибка при чтении родительского файла: {e}", None

    if not parent_codes:
        return False, "Родительский файл пуст.", None

    all_child_codes = []
    for cf in child_files:
        if not os.path.exists(cf):
            return False, f"Файл вложений не существует: {cf}", None
        try:
            codes = read_codes(cf)
            all_child_codes.extend(codes)
        except Exception as e:
            return False, f"Ошибка при чтении файла вложений {cf}: {e}", None

    if not all_child_codes:
        return False, "Файлы вложений не содержат кодов.", None

    total_parents = len(parent_codes)
    needed_children = total_parents * count_per_parent
    actual_children = len(all_child_codes)

    actual_sets = total_parents
    if actual_children < needed_children:
        max_possible_sets = actual_children // count_per_parent
        if max_possible_sets == 0:
            return False, f"Недостаточно кодов вложений ({actual_children}) даже для одного набора (требуется {count_per_parent}).", None

        if confirm_callback:
            prompt_msg = (
                f"Недостаточно кодов вложений!\n\n"
                f"Требуется вложений: {needed_children} (для {total_parents} наборов по {count_per_parent} шт.)\n"
                f"Имеется вложений: {actual_children}\n\n"
                f"Сформировать только {max_possible_sets} наборов?"
            )
            confirmed = confirm_callback(prompt_msg)
            if not confirmed:
                return False, "Операция отменена пользователем.", None

        actual_sets = max_possible_sets

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    folder_name = f"aggregation_results_{timestamp}"
    if output_base_dir:
        output_folder = os.path.join(output_base_dir, folder_name)
    else:
        output_folder = os.path.abspath(folder_name)

    os.makedirs(output_folder, exist_ok=True)

    used_filenames = set()

    for i in range(actual_sets):
        p_code = parent_codes[i]
        start_idx = i * count_per_parent
        c_codes = all_child_codes[start_idx : start_idx + count_per_parent]

        base_filename = sanitize_filename(p_code)
        filename = f"{base_filename}.txt"

        # Разрешение коллизий имен файлов
        counter = 1
        while filename in used_filenames or os.path.exists(os.path.join(output_folder, filename)):
            filename = f"{base_filename}_{counter}.txt"
            counter += 1

        used_filenames.add(filename)
        file_path = os.path.join(output_folder, filename)

        # Сохранение итогового файла без BOM в UTF-8
        with open(file_path, "w", encoding="utf-8") as out_f:
            out_f.write(p_code + "\n")
            for c_code in c_codes:
                out_f.write(c_code + "\n")

    msg = (
        f"Успешно создано наборов: {actual_sets}\n"
        f"Использовано вложений: {actual_sets * count_per_parent}\n"
        f"Папка с результатом:\n{output_folder}"
    )
    return True, msg, output_folder


class AggregationApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Виртуальная агрегация наборов")
        self.root.geometry("620x450")
        self.root.minsize(550, 400)

        self.parent_file = ""
        self.child_files = []

        self._build_ui()

    def _build_ui(self):
        main_frame = ttk.Frame(self.root, padding="15")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Раздел 1: Выбор файла наборов (родительский файл)
        parent_frame = ttk.LabelFrame(main_frame, text=" 1. Файл кодов маркировки наборов (родительские) ", padding="10")
        parent_frame.pack(fill=tk.X, pady=(0, 10))

        self.btn_select_parent = ttk.Button(parent_frame, text="Выбрать файл наборов (.txt)", command=self._select_parent_file)
        self.btn_select_parent.pack(side=tk.LEFT, padx=(0, 10))

        self.lbl_parent_path = ttk.Label(parent_frame, text="Файл не выбран", foreground="gray")
        self.lbl_parent_path.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Раздел 2: Количество вложений в набор
        count_frame = ttk.LabelFrame(main_frame, text=" 2. Количество вложений в один набор ", padding="10")
        count_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(count_frame, text="Вложений на набор:").pack(side=tk.LEFT, padx=(0, 10))
        self.spin_count = ttk.Spinbox(count_frame, from_=1, to=1000, width=10)
        self.spin_count.set(2)
        self.spin_count.pack(side=tk.LEFT)

        # Раздел 3: Выбор файлов вложений (дочерние файлы)
        child_frame = ttk.LabelFrame(main_frame, text=" 3. Файлы кодов маркировки вложений (содержимое) ", padding="10")
        child_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        child_btn_frame = ttk.Frame(child_frame)
        child_btn_frame.pack(fill=tk.X, pady=(0, 5))

        self.btn_select_children = ttk.Button(child_btn_frame, text="Добавить файлы вложений (.txt)", command=self._select_child_files)
        self.btn_select_children.pack(side=tk.LEFT, padx=(0, 10))

        self.btn_clear_children = ttk.Button(child_btn_frame, text="Очистить список", command=self._clear_child_files)
        self.btn_clear_children.pack(side=tk.LEFT)

        self.lst_child_files = tk.Listbox(child_frame, height=5)
        self.lst_child_files.pack(fill=tk.BOTH, expand=True)

        # Раздел 4: Кнопка старта
        self.btn_run = ttk.Button(main_frame, text="Сформировать файлы агрегации", command=self._run_aggregation)
        self.btn_run.pack(fill=tk.X, ipady=5)

    def _select_parent_file(self):
        file_path = filedialog.askopenfilename(
            title="Выберите файл с кодами маркировки наборов",
            filetypes=[("Текстовые файлы", "*.txt"), ("Все файлы", "*.*")]
        )
        if file_path:
            self.parent_file = file_path
            self.lbl_parent_path.config(text=os.path.basename(file_path), foreground="black")

    def _select_child_files(self):
        files = filedialog.askopenfilenames(
            title="Выберите файлы с кодами маркировки вложений",
            filetypes=[("Текстовые файлы", "*.txt"), ("Все файлы", "*.*")]
        )
        if files:
            for f in files:
                if f not in self.child_files:
                    self.child_files.append(f)
                    self.lst_child_files.insert(tk.END, os.path.basename(f))

    def _clear_child_files(self):
        self.child_files.clear()
        self.lst_child_files.delete(0, tk.END)

    def _confirm_callback(self, message):
        return messagebox.askyesno("Подтверждение", message)

    def _run_aggregation(self):
        if not self.parent_file:
            messagebox.showwarning("Предупреждение", "Пожалуйста, выберите родительский файл кодов наборов.")
            return

        if not self.child_files:
            messagebox.showwarning("Предупреждение", "Пожалуйста, выберите хотя бы один файл кодов вложений.")
            return

        try:
            count_per_parent = int(self.spin_count.get())
        except ValueError:
            messagebox.showerror("Ошибка", "Количество вложений должно быть целым числом.")
            return

        success, msg, folder = perform_aggregation(
            parent_file=self.parent_file,
            child_files=self.child_files,
            count_per_parent=count_per_parent,
            confirm_callback=self._confirm_callback
        )

        if success:
            messagebox.showinfo("Успех", msg)
        else:
            messagebox.showerror("Ошибка", msg)


def global_exception_handler(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    err_msg = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    if HAS_TK:
        try:
            messagebox.showerror("Критическая ошибка", f"Произошла непредвиденная ошибка:\n\n{err_msg}")
        except Exception:
            pass
    print("Uncaught exception:", err_msg, file=sys.stderr)


def main():
    if not HAS_TK:
        print("Ошибка: Графическое окружение Tkinter недоступно.")
        sys.exit(1)

    sys.excepthook = global_exception_handler

    root = tk.Tk()
    app = AggregationApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
