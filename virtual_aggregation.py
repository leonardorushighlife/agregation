"""
Скрипт виртуальной агрегации кодов маркировки.

Инструкция по сборке в Исполняемый файл (.exe) с помощью PyInstaller:
1. Установите PyInstaller:
   pip install pyinstaller
2. Выполните команду сборки в консоли/терминале:
   pyinstaller --noconsole --onefile virtual_aggregation.py
3. Готовый исполняемый файл `virtual_aggregation.exe` будет находиться в папке `dist`.
"""

import sys
import os
import re
import traceback
from datetime import datetime

# Guarded import of tkinter for GUI execution vs test/headless execution
try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
    TK_AVAILABLE = True
except ImportError:
    TK_AVAILABLE = False


def sanitize_filename(filename: str) -> str:
    """
    Очищает строку от символов, не допустимых в именах файлов ОС Windows/Linux.
    """
    cleaned = re.sub(r'[\\/*?:"<>|\r\n\t]', '_', filename).strip()
    return cleaned if cleaned else "set_code"


def read_codes_from_file(filepath: str) -> list[str]:
    """
    Считывает строки с кодами из файла TXT, пробуя различные кодировки.
    Возвращает список непустых очищенных строк кодов.
    """
    encodings = ['utf-8-sig', 'utf-16', 'utf-8', 'cp1251']
    for enc in encodings:
        try:
            with open(filepath, 'r', encoding=enc) as f:
                lines = [line.strip() for line in f if line.strip()]
                return lines
        except (UnicodeError, LookupError):
            continue
    # Если ни одна кодировка не подошла, пробуем utf-8 с игнорированием ошибок
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        return [line.strip() for line in f if line.strip()]


def perform_aggregation(
    parent_file: str,
    child_files: list[str],
    count_per_set: int,
    output_dir: str = None,
    confirm_partial_cb=None
) -> dict:
    """
    Основная логика виртуальной агрегации.

    :param parent_file: Путь к TXT-файлу с родительскими кодами (коды наборов).
    :param child_files: Список путей к TXT-файлам с дочерними кодами (вложения).
    :param count_per_set: Количество вложений в один набор.
    :param output_dir: Целевая директория для результатов. Если None, создается автоматически.
    :param confirm_partial_cb: Функция обратного вызова для подтверждения частичной агрегации,
                               если дочерних кодов не хватает. Возвращает bool.
    :return: Словарь со статистикой работы.
    """
    if not parent_file or not os.path.isfile(parent_file):
        raise ValueError("Файл с кодами наборов не выбран или не существует.")

    if not child_files:
        raise ValueError("Файлы с кодами вложений не выбраны.")

    if count_per_set <= 0:
        raise ValueError("Количество вложений должно быть больше 0.")

    parent_codes = read_codes_from_file(parent_file)
    if not parent_codes:
        raise ValueError(f"Файл родительских кодов '{parent_file}' пуст.")

    child_codes = []
    for cfile in child_files:
        if os.path.isfile(cfile):
            child_codes.extend(read_codes_from_file(cfile))

    if not child_codes:
        raise ValueError("Ни один из выбранных файлов вложений не содержит кодов.")

    total_parents = len(parent_codes)
    total_children = len(child_codes)
    needed_children = total_parents * count_per_set

    actual_sets = total_parents
    if total_children < needed_children:
        possible_sets = total_children // count_per_set
        if possible_sets == 0:
            raise ValueError(
                f"Недостаточно кодов вложений ({total_children}) "
                f"даже для одного набора (требуется {count_per_set})."
            )

        if confirm_partial_cb:
            msg = (
                f"Кодов вложений ({total_children}) недостаточно для полного формирования "
                f"{total_parents} наборов (требуется {needed_children}).\n\n"
                f"Будет сформировано только {possible_sets} наборов.\n"
                f"Продолжить?"
            )
            if not confirm_partial_cb(msg):
                return {"status": "cancelled"}

        actual_sets = possible_sets

    if not output_dir:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = f"aggregation_results_{timestamp}"

    os.makedirs(output_dir, exist_ok=True)

    used_filenames = {}
    created_files_count = 0

    for i in range(actual_sets):
        parent = parent_codes[i]
        start_idx = i * count_per_set
        end_idx = start_idx + count_per_set
        current_children = child_codes[start_idx:end_idx]

        base_filename = sanitize_filename(parent)
        filename = f"{base_filename}.txt"

        if filename in used_filenames:
            used_filenames[filename] += 1
            filename = f"{base_filename}_{used_filenames[filename]}.txt"
        else:
            used_filenames[filename] = 0

        out_path = os.path.join(output_dir, filename)

        with open(out_path, 'w', encoding='utf-8', newline='\n') as f:
            f.write(parent + '\n')
            for child in current_children:
                f.write(child + '\n')

        created_files_count += 1

    return {
        "status": "success",
        "output_dir": output_dir,
        "sets_created": created_files_count,
        "children_used": created_files_count * count_per_set,
        "total_parents": total_parents,
        "total_children": total_children
    }


class VirtualAggregationApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Виртуальная агрегация кодов маркировки")
        self.root.geometry("620x480")
        self.root.resizable(False, False)

        self.parent_file_path = ""
        self.child_file_paths = []

        self._build_ui()

    def _build_ui(self):
        main_frame = ttk.Frame(self.root, padding=15)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 1. Выбор файла наборов (родительские коды)
        ttk.Label(main_frame, text="1. Файл кодов НАБОРОВ (родительские коды):", font=("Arial", 10, "bold")).pack(anchor=tk.W, pady=(0, 5))

        parent_frame = ttk.Frame(main_frame)
        parent_frame.pack(fill=tk.X, pady=(0, 15))

        self.parent_label = ttk.Entry(parent_frame, state="readonly")
        self.parent_label.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))

        btn_parent = ttk.Button(parent_frame, text="Обзор...", command=self.select_parent_file)
        btn_parent.pack(side=tk.RIGHT)

        # 2. Выбор файлов вложений (дочерние коды)
        ttk.Label(main_frame, text="2. Файлы кодов ВЛОЖЕНИЙ (дочерние коды):", font=("Arial", 10, "bold")).pack(anchor=tk.W, pady=(0, 5))

        child_frame = ttk.Frame(main_frame)
        child_frame.pack(fill=tk.X, pady=(0, 15))

        self.child_listbox = tk.Listbox(child_frame, height=4)
        self.child_listbox.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))

        child_btn_frame = ttk.Frame(child_frame)
        child_btn_frame.pack(side=tk.RIGHT, fill=tk.Y)

        btn_child = ttk.Button(child_btn_frame, text="Добавить...", command=self.select_child_files)
        btn_child.pack(fill=tk.X, pady=(0, 5))

        btn_clear_child = ttk.Button(child_btn_frame, text="Очистить", command=self.clear_child_files)
        btn_clear_child.pack(fill=tk.X)

        # 3. Выбор количества вложений в набор
        ttk.Label(main_frame, text="3. Количество вложений в 1 набор:", font=("Arial", 10, "bold")).pack(anchor=tk.W, pady=(0, 5))

        count_frame = ttk.Frame(main_frame)
        count_frame.pack(fill=tk.X, pady=(0, 20))

        self.count_spinbox = ttk.Spinbox(count_frame, from_=1, to=1000, width=10)
        self.count_spinbox.set(4)
        self.count_spinbox.pack(side=tk.LEFT)

        # Кнопка Запуск
        self.btn_run = tk.Button(
            main_frame,
            text="Сформировать агрегированные файлы",
            font=("Arial", 12, "bold"),
            bg="#2196F3",
            fg="white",
            activebackground="#0b7dda",
            activeforeground="white",
            command=self.run_aggregation,
            height=2
        )
        self.btn_run.pack(fill=tk.X, pady=(10, 0))

    def select_parent_file(self):
        file_path = filedialog.askopenfilename(
            title="Выберите файл кодов наборов",
            filetypes=[("Текстовые файлы", "*.txt"), ("Все файлы", "*.*")]
        )
        if file_path:
            self.parent_file_path = file_path
            self.parent_label.config(state="normal")
            self.parent_label.delete(0, tk.END)
            self.parent_label.insert(0, file_path)
            self.parent_label.config(state="readonly")

    def select_child_files(self):
        files = filedialog.askopenfilenames(
            title="Выберите файлы кодов вложений",
            filetypes=[("Текстовые файлы", "*.txt"), ("Все файлы", "*.*")]
        )
        if files:
            for f in files:
                if f not in self.child_file_paths:
                    self.child_file_paths.append(f)
                    self.child_listbox.insert(tk.END, os.path.basename(f))

    def clear_child_files(self):
        self.child_file_paths.clear()
        self.child_listbox.delete(0, tk.END)

    def confirm_partial(self, msg: str) -> bool:
        return messagebox.askyesno("Подтверждение частичной агрегации", msg)

    def run_aggregation(self):
        try:
            try:
                count_per_set = int(self.count_spinbox.get())
            except ValueError:
                messagebox.showerror("Ошибка", "Количество вложений должно быть целым числом.")
                return

            res = perform_aggregation(
                parent_file=self.parent_file_path,
                child_files=self.child_file_paths,
                count_per_set=count_per_set,
                confirm_partial_cb=self.confirm_partial
            )

            if res.get("status") == "cancelled":
                messagebox.showinfo("Отмена", "Операция отменена пользователем.")
                return

            msg = (
                f"Успешно создано наборов: {res['sets_created']}\n"
                f"Использовано вложений: {res['children_used']}\n"
                f"Результаты сохранены в папку:\n{os.path.abspath(res['output_dir'])}"
            )
            messagebox.showinfo("Успешно", msg)

        except Exception as e:
            err_msg = f"Произошла ошибка при выполнении агрегации:\n{e}"
            messagebox.showerror("Ошибка", err_msg)


def main():
    if not TK_AVAILABLE:
        print("Ошибка: Tkinter недоступен в данной системе.")
        sys.exit(1)

    root = tk.Tk()

    def global_exception_handler(exc_type, exc_value, exc_traceback):
        err_msg = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        messagebox.showerror("Критическая ошибка", f"Произошла непредвиденная ошибка:\n{err_msg}")

    root.report_callback_exception = global_exception_handler
    app = VirtualAggregationApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
