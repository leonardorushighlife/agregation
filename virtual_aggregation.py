"""
Инструкция по сборке исполняемого файла (.exe):
1. Установите PyInstaller (если не установлен):
   pip install pyinstaller

2. Выполните команду для сборки скрипта в один exe-файл без консольного окна:
   pyinstaller --noconsole --onefile virtual_aggregation.py

Исполняемый файл будет создан в папке dist/.
"""

import sys
import os
import re
from datetime import datetime

# Ленивый импорт Tkinter для работы в headless-режиме (например, при запуске модульных тестов)
try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
    HAS_TKINTER = True
except ImportError:
    HAS_TKINTER = False


def sanitize_filename(name: str) -> str:
    """
    Очищает строку от недопустимых символов для имени файла в Windows/Linux.
    """
    # Заменяем запрещенные символы \ / : * ? " < > | на подчеркивание
    sanitized = re.sub(r'[\\/*?:"<>|]', '_', name.strip())
    # Если строка пустая после очистки, берем дефолтное имя
    if not sanitized:
        sanitized = "unnamed_set"
    return sanitized


def read_codes(file_path: str) -> list:
    """
    Считывает коды маркировки из файла с поддержкой различных кодировок.
    Игнорирует пустые строки.
    """
    encodings = ['utf-8-sig', 'utf-16', 'utf-8', 'cp1251']
    content = None

    for enc in encodings:
        try:
            with open(file_path, 'r', encoding=enc) as f:
                content = f.read()
            break
        except (UnicodeError, LookupError):
            continue

    if content is None:
        raise ValueError(f"Не удалось прочитать файл {file_path} ни в одной из поддерживаемых кодировок.")

    # Разбиваем по строкам и очищаем
    lines = [line.strip() for line in content.splitlines() if line.strip()]
    return lines


def perform_aggregation(parent_file: str, child_files: list, count_per_parent: int, output_base_dir: str = None, confirm_callback=None) -> dict:
    """
    Выполняет виртуальную агрегацию.

    :param parent_file: Путь к TXT файлу с родительскими кодами (наборы).
    :param child_files: Список путей к TXT файлам с дочерними кодами (вложения).
    :param count_per_parent: Количество вложений в один набор.
    :param output_base_dir: Базовая директория для сохранения результатов (по умолчанию текущая директория).
    :param confirm_callback: Функция обратного вызова при нехватке дочерних кодов confirm_callback(available_sets, total_parents) -> bool.
    :return: Словарь с результатами агрегации.
    """
    if count_per_parent <= 0:
        raise ValueError("Количество вложений должно быть больше 0.")

    if not parent_file or not os.path.exists(parent_file):
        raise FileNotFoundError("Файл кодов наборов не найден.")

    if not child_files:
        raise ValueError("Не выбpaн ни один файл кодов вложений.")

    parent_codes = read_codes(parent_file)
    if not parent_codes:
        raise ValueError("Файл кодов наборов пуст.")

    child_codes = []
    for cf in child_files:
        if os.path.exists(cf):
            child_codes.extend(read_codes(cf))

    if not child_codes:
        raise ValueError("Файлы кодов вложений не содержат корректных кодов.")

    total_parents = len(parent_codes)
    needed_children = total_parents * count_per_parent
    actual_sets = total_parents

    if len(child_codes) < needed_children:
        max_possible_sets = len(child_codes) // count_per_parent
        if max_possible_sets == 0:
            raise ValueError(f"Недостаточно кодов вложений ({len(child_codes)}) даже для одного полного набора из {count_per_parent} шт.")

        if confirm_callback is not None:
            approved = confirm_callback(max_possible_sets, total_parents)
            if not approved:
                return {"status": "cancelled", "message": "Операция отменена пользователем."}

        actual_sets = max_possible_sets

    # Создание папки с временной меткой
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    folder_name = f"aggregation_results_{timestamp}"
    if output_base_dir:
        output_dir = os.path.join(output_base_dir, folder_name)
    else:
        output_dir = os.path.abspath(folder_name)

    os.makedirs(output_dir, exist_ok=True)

    created_files = 0
    used_child_codes_count = 0

    for i in range(actual_sets):
        p_code = parent_codes[i]
        start_idx = i * count_per_parent
        end_idx = start_idx + count_per_parent
        current_children = child_codes[start_idx:end_idx]

        base_filename = sanitize_filename(p_code)
        target_filename = f"{base_filename}.txt"
        target_path = os.path.join(output_dir, target_filename)

        # Обработка коллизий имен файлов
        suffix = 1
        while os.path.exists(target_path):
            target_filename = f"{base_filename}_{suffix}.txt"
            target_path = os.path.join(output_dir, target_filename)
            suffix += 1

        # Запись файла результата (UTF-8 без BOM)
        with open(target_path, 'w', encoding='utf-8', newline='\n') as f:
            f.write(p_code + '\n')
            for c_code in current_children:
                f.write(c_code + '\n')

        created_files += 1
        used_child_codes_count += len(current_children)

    return {
        "status": "success",
        "output_dir": output_dir,
        "created_files": created_files,
        "used_children": used_child_codes_count,
        "total_parents": total_parents
    }


class VirtualAggregationApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Виртуальная Агрегация Кодов Маркировки")
        self.root.geometry("650x550")
        self.root.minsize(600, 500)

        self.parent_file = ""
        self.child_files = []

        self._build_ui()

    def _build_ui(self):
        main_frame = ttk.Frame(self.root, padding=15)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 1. Выбор файла наборов (Родительские коды)
        parent_frame = ttk.LabelFrame(main_frame, text=" 1. Файл кодов НАБОРОВ (1 файл) ", padding=10)
        parent_frame.pack(fill=tk.X, pady=(0, 10))

        self.parent_label = ttk.Label(parent_frame, text="Файл не выбран", wraplength=450, foreground="gray")
        self.parent_label.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))

        btn_browse_parent = ttk.Button(parent_frame, text="Выбрать файл...", command=self.select_parent_file)
        btn_browse_parent.pack(side=tk.RIGHT)

        # 2. Выбор файлов вложений (Дочерние коды)
        child_frame = ttk.LabelFrame(main_frame, text=" 2. Файлы кодов ВЛОЖЕНИЙ (1 или несколько) ", padding=10)
        child_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        btn_browse_child = ttk.Button(child_frame, text="Добавить / Выбрать файлы...", command=self.select_child_files)
        btn_browse_child.pack(anchor=tk.W, pady=(0, 5))

        self.child_listbox = tk.Listbox(child_frame, height=6)
        self.child_listbox.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)

        scrollbar = ttk.Scrollbar(child_frame, orient=tk.VERTICAL, command=self.child_listbox.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.child_listbox.config(yscrollcommand=scrollbar.set)

        # 3. Параметры агрегации
        param_frame = ttk.LabelFrame(main_frame, text=" 3. Параметры ", padding=10)
        param_frame.pack(fill=tk.X, pady=(0, 15))

        ttk.Label(param_frame, text="Количество вложений в один набор:").pack(side=tk.LEFT, padx=(0, 10))
        self.count_spinbox = ttk.Spinbox(param_frame, from_=1, to=1000, width=10)
        self.count_spinbox.set(4)
        self.count_spinbox.pack(side=tk.LEFT)

        # 4. Кнопка запуска
        self.btn_run = ttk.Button(main_frame, text="Выполнить виртуальную агрегацию", command=self.run_aggregation)
        self.btn_run.pack(fill=tk.X, ipady=5)

    def select_parent_file(self):
        file_path = filedialog.askopenfilename(
            title="Выберите TXT файл кодов наборов",
            filetypes=[("Текстовые файлы", "*.txt"), ("Все файлы", "*.*")]
        )
        if file_path:
            self.parent_file = file_path
            self.parent_label.config(text=os.path.basename(file_path), foreground="black")

    def select_child_files(self):
        files = filedialog.askopenfilenames(
            title="Выберите TXT файлы кодов вложений",
            filetypes=[("Текстовые файлы", "*.txt"), ("Все файлы", "*.*")]
        )
        if files:
            self.child_files = list(files)
            self.child_listbox.delete(0, tk.END)
            for f in self.child_files:
                self.child_listbox.insert(tk.END, os.path.basename(f))

    def run_aggregation(self):
        if not self.parent_file:
            messagebox.showwarning("Предупреждение", "Пожалуйста, выберите файл кодов наборов.")
            return

        if not self.child_files:
            messagebox.showwarning("Предупреждение", "Пожалуйста, выберите хотя бы один файл кодов вложений.")
            return

        try:
            count_per_parent = int(self.count_spinbox.get())
        except ValueError:
            messagebox.showerror("Ошибка", "Количество вложений должно быть целым числом.")
            return

        def gui_confirm(available_sets, total_parents):
            msg = (f"Кодов вложений недостаточно для всех {total_parents} наборов.\n"
                   f"Доступно кодов только на {available_sets} полных наборов.\n\n"
                   f"Продолжить и создать {available_sets} файлов?")
            return messagebox.askyesno("Подтверждение", msg)

        try:
            res = perform_aggregation(
                parent_file=self.parent_file,
                child_files=self.child_files,
                count_per_parent=count_per_parent,
                confirm_callback=gui_confirm
            )

            if res.get("status") == "success":
                msg = (f"Успешно завершено!\n\n"
                       f"Создано файлов (наборов): {res['created_files']}\n"
                       f"Использовано вложений: {res['used_children']}\n"
                       f"Результаты сохранены в папку:\n{res['output_dir']}")
                messagebox.showinfo("Успех", msg)
            elif res.get("status") == "cancelled":
                messagebox.showinfo("Отмена", res.get("message", "Операция отменена."))

        except Exception as e:
            messagebox.showerror("Ошибка агрегации", str(e))


def global_exception_handler(exc_type, exc_value, exc_traceback):
    """
    Глобальный обработчик необработанных исключений для вывода стека вызовов в диалоговом окне.
    """
    import traceback
    err_msg = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    if HAS_TKINTER:
        messagebox.showerror("Критическая ошибка", f"Произошла непредвиденная ошибка:\n\n{err_msg}")
    else:
        print(f"Критическая ошибка:\n{err_msg}", file=sys.stderr)


def main():
    if not HAS_TKINTER:
        print("Ошибка: Tkinter не установлен или недоступен в данной системе.")
        sys.exit(1)

    sys.excepthook = global_exception_handler

    root = tk.Tk()
    app = VirtualAggregationApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
