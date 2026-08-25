"""
Инструкция по сборке исполняемого файла (EXE):
1. Установите PyInstaller, если он еще не установлен:
   pip install pyinstaller
2. Выполните команду сборки в консоли:
   pyinstaller --noconsole --onefile virtual_aggregation.py
3. Исполняемый файл `virtual_aggregation.exe` будет создан в папке `dist`.
"""

import sys
import os
import re
from datetime import datetime

# Guarded Tkinter import for headless testing compatibility
try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
    HAS_TKINTER = True
except ImportError:
    HAS_TKINTER = False


def read_codes(file_path):
    """
    Считывает маркировочные коды из файла TXT, перебирая распространенные кодировки.
    Возвращает список очищенных строк.
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
        raise ValueError(f"Не удалось прочитать файл {file_path}. Неподдерживаемая кодировка.")

    lines = [line.strip() for line in content.splitlines() if line.strip()]
    return lines


def sanitize_filename(name):
    """
    Заменяет недопустимые символы в имени файла на символ подчеркивания.
    """
    return re.sub(r'[\\/:*?"<>|]', '_', name)


def perform_aggregation(parent_file, child_files, count_per_parent, output_dir_base=None, confirm_callback=None):
    """
    Выполняет виртуальную агрегацию кодов маркировки.

    :param parent_file: Путь к TXT файлу с кодами набора (родительские)
    :param child_files: Список путей к TXT файлам с кодами вложений (дочерние)
    :param count_per_parent: Количество вложений в один набор
    :param output_dir_base: Базовый каталог для вывода (по умолчанию текущая директория)
    :param confirm_callback: Функция обратного вызова для подтверждения частичной агрегации
    :return: (output_folder, created_files_count)
    """
    if count_per_parent <= 0:
        raise ValueError("Количество вложений должно быть больше 0.")

    parent_codes = read_codes(parent_file)
    if not parent_codes:
        raise ValueError("Родительский файл не содержит кодов маркировки.")

    all_child_codes = []
    for c_file in child_files:
        all_child_codes.extend(read_codes(c_file))

    if not all_child_codes:
        raise ValueError("Файлы вложений не содержат кодов маркировки.")

    total_parents = len(parent_codes)
    needed_children = total_parents * count_per_parent
    actual_children = len(all_child_codes)

    actual_sets = total_parents
    if actual_children < needed_children:
        max_possible_sets = actual_children // count_per_parent
        actual_sets = min(total_parents, max_possible_sets)

        message = (
            f"Внимание: недопустимо мало кодов вложений!\n"
            f"Требуется кодов: {needed_children} (для {total_parents} наборов по {count_per_parent} шт.).\n"
            f"Доступно кодов: {actual_children}.\n"
            f"Будет сформировано наборов: {actual_sets}.\n"
            f"Продолжить частичную агрегацию?"
        )
        if confirm_callback:
            if not confirm_callback(message):
                raise Exception("Операция отменена пользователем.")
        else:
            raise Exception(f"Недостаточно кодов вложений ({actual_children} из {needed_children}).")

    if actual_sets == 0:
        raise ValueError("Недостаточно кодов вложений даже для одного полного набора.")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    folder_name = f"aggregation_results_{timestamp}"
    if output_dir_base:
        output_folder = os.path.join(output_dir_base, folder_name)
    else:
        output_folder = os.path.abspath(folder_name)

    os.makedirs(output_folder, exist_ok=True)

    created_count = 0
    for i in range(actual_sets):
        p_code = parent_codes[i]
        start_idx = i * count_per_parent
        end_idx = start_idx + count_per_parent
        c_codes = all_child_codes[start_idx:end_idx]

        base_filename = sanitize_filename(p_code)
        target_path = os.path.join(output_folder, f"{base_filename}.txt")

        # Обработка коллизий имен файлов
        suffix_idx = 1
        while os.path.exists(target_path):
            target_path = os.path.join(output_folder, f"{base_filename}_{suffix_idx}.txt")
            suffix_idx += 1

        with open(target_path, 'w', encoding='utf-8') as f:
            f.write(p_code + '\n')
            for child_code in c_codes:
                f.write(child_code + '\n')

        created_count += 1

    return output_folder, created_count


class VirtualAggregationApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Виртуальная агрегация кодов маркировки")
        self.root.geometry("650x520")
        self.root.resizable(False, False)

        self.parent_file = ""
        self.child_files = []

        self.setup_ui()

    def setup_ui(self):
        # Global exception handling for Tkinter
        self.root.report_callback_exception = self.handle_exception

        main_frame = ttk.Frame(self.root, padding=15)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 1. Родительский файл
        lbl_parent = ttk.Label(main_frame, text="1. Файл кодов маркировки на набор (родительский):", font=("Arial", 10, "bold"))
        lbl_parent.pack(anchor=tk.W, pady=(0, 5))

        f_parent = ttk.Frame(main_frame)
        f_parent.pack(fill=tk.X, pady=(0, 15))

        self.ent_parent = ttk.Entry(f_parent, width=60)
        self.ent_parent.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        btn_parent = ttk.Button(f_parent, text="Обзор...", command=self.select_parent_file)
        btn_parent.pack(side=tk.RIGHT)

        # 2. Количество вложений
        lbl_count = ttk.Label(main_frame, text="2. Количество вложений в один набор:", font=("Arial", 10, "bold"))
        lbl_count.pack(anchor=tk.W, pady=(0, 5))

        f_count = ttk.Frame(main_frame)
        f_count.pack(fill=tk.X, pady=(0, 15))

        self.spn_count = ttk.Spinbox(f_count, from_=1, to=1000, width=10)
        self.spn_count.set(4)
        self.spn_count.pack(side=tk.LEFT)

        # 3. Дочерние файлы
        lbl_child = ttk.Label(main_frame, text="3. Файлы кодов маркировки вложений (дочерние TXT):", font=("Arial", 10, "bold"))
        lbl_child.pack(anchor=tk.W, pady=(0, 5))

        f_child = ttk.Frame(main_frame)
        f_child.pack(fill=tk.BOTH, expand=True, pady=(0, 15))

        self.lst_child = tk.Listbox(f_child, height=8)
        self.lst_child.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))

        scrollbar = ttk.Scrollbar(f_child, orient=tk.VERTICAL, command=self.lst_child.yview)
        scrollbar.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 5))
        self.lst_child.config(yscrollcommand=scrollbar.set)

        f_child_btns = ttk.Frame(f_child)
        f_child_btns.pack(side=tk.RIGHT, fill=tk.Y)

        btn_add_child = ttk.Button(f_child_btns, text="Добавить...", command=self.select_child_files)
        btn_add_child.pack(fill=tk.X, pady=(0, 5))

        btn_clear_child = ttk.Button(f_child_btns, text="Очистить", command=self.clear_child_files)
        btn_clear_child.pack(fill=tk.X)

        # Button Perform
        btn_run = ttk.Button(main_frame, text="Сформировать файлы агрегации", command=self.run_aggregation)
        btn_run.pack(fill=tk.X, ipady=8, pady=(10, 0))

    def select_parent_file(self):
        filename = filedialog.askopenfilename(
            title="Выберите родительский файл кодов набора",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        if filename:
            self.parent_file = filename
            self.ent_parent.delete(0, tk.END)
            self.ent_parent.insert(0, filename)

    def select_child_files(self):
        filenames = filedialog.askopenfilenames(
            title="Выберите файлы кодов вложений",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        if filenames:
            for fn in filenames:
                if fn not in self.child_files:
                    self.child_files.append(fn)
                    self.lst_child.insert(tk.END, fn)

    def clear_child_files(self):
        self.child_files.clear()
        self.lst_child.delete(0, tk.END)

    def run_aggregation(self):
        parent = self.ent_parent.get().strip()
        if not parent or not os.path.exists(parent):
            messagebox.showerror("Ошибка", "Пожалуйста, укажите существующий родительский файл.")
            return

        if not self.child_files:
            messagebox.showerror("Ошибка", "Пожалуйста, выберите хотя бы один файл кодов вложений.")
            return

        try:
            count_per_parent = int(self.spn_count.get())
        except ValueError:
            messagebox.showerror("Ошибка", "Количество вложений должно быть целым числом.")
            return

        def confirm_cb(msg):
            return messagebox.askyesno("Подтверждение", msg)

        try:
            folder, count = perform_aggregation(parent, self.child_files, count_per_parent, confirm_callback=confirm_cb)
            messagebox.showinfo(
                "Успех",
                f"Виртуальная агрегация успешно завершена!\n\n"
                f"Создано файлов: {count}\n"
                f"Папка с результатами:\n{folder}"
            )
        except Exception as e:
            messagebox.showerror("Ошибка", str(e))

    def handle_exception(self, exc_type, exc_value, exc_traceback):
        import traceback
        err_msg = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        messagebox.showerror("Критическая ошибка", f"Произошла непредвиденная ошибка:\n\n{err_msg}")


def main():
    if not HAS_TKINTER:
        print("Ошибка: Tkinter не установлен в текущем окружении.")
        sys.exit(1)

    root = tk.Tk()
    app = VirtualAggregationApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
