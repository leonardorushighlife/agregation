"""
Виртуальная агрегация кодов маркировки.

Инструкция по сборке в exe:
1. Установите PyInstaller (если не установлен):
   pip install pyinstaller
2. Выполните команду сборки:
   pyinstaller --noconsole --onefile virtual_aggregation.py
3. Исполняемый файл появится в папке dist/
"""

import os
import re
import sys
import datetime

# Поддерживаемые кодировки для чтения файлов
ENCODINGS = ['utf-8-sig', 'utf-16', 'utf-8', 'cp1251']


def read_codes(filepath):
    """
    Считывает коды маркировки из текстового файла, пробуя различные кодировки.
    Возвращает список непустых строк (кодов).
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Файл не найден: {filepath}")

    for enc in ENCODINGS:
        try:
            with open(filepath, 'r', encoding=enc) as f:
                lines = [line.strip() for line in f if line.strip()]
            return lines
        except (UnicodeError, LookupError):
            continue

    raise UnicodeError(f"Не удалось прочитать файл {filepath} в поддерживаемых кодировках.")


def sanitize_filename(filename):
    """
    Заменяет запрещенные символы в имени файла на символ подчеркивания.
    """
    return re.sub(r'[\\/*?:"<>|]', '_', filename)


def perform_aggregation(parent_file, child_files, count_per_set, output_dir=None, confirm_callback=None):
    """
    Основная логика виртуальной агрегации.

    :param parent_file: Путь к файлу с кодами маркировки наборов (родителей).
    :param child_files: Список путей к файлам с кодами маркировки вложений (детей).
    :param count_per_set: Количество вложений на один набор (целое число).
    :param output_dir: Папка для сохранения результатов. Если None, создаётся timestamp-папка.
    :param confirm_callback: Функция обратного вызова для подтверждения при нехватке кодов вложений.
                             Должна возвращать True/False.
    :return: Кортеж (путь_к_папке_результатов, количество_успешно_созданных_файлов).
    """
    if not parent_file:
        raise ValueError("Не выбран файл кодов наборов.")
    if not child_files:
        raise ValueError("Не выбраны файлы кодов вложений.")
    if count_per_set <= 0:
        raise ValueError("Количество вложений должно быть больше 0.")

    parents = read_codes(parent_file)
    if not parents:
        raise ValueError("Файл кодов наборов пуст.")

    children = []
    for cf in child_files:
        children.extend(read_codes(cf))

    if not children:
        raise ValueError("Выбранные файлы вложений не содержат кодов.")

    total_required_children = len(parents) * count_per_set
    if len(children) < total_required_children:
        actual_sets = len(children) // count_per_set
        msg = (f"Недостаточно кодов вложений!\n"
               f"Требуется: {total_required_children} ({len(parents)} наб. x {count_per_set} вл.), "
               f"в наличии: {len(children)}.\n"
               f"Будет сформировано только {actual_sets} наборов.\nПродолжить?")
        if confirm_callback is not None:
            if not confirm_callback(msg):
                return None, 0
        parents = parents[:actual_sets]

    if not output_dir:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = f"aggregation_results_{timestamp}"

    os.makedirs(output_dir, exist_ok=True)

    created_count = 0
    used_filenames = set()

    for i, parent_code in enumerate(parents):
        base_name = sanitize_filename(parent_code)
        filename = f"{base_name}.txt"

        # Предотвращение коллизий имён файлов
        suffix = 1
        while filename in used_filenames or os.path.exists(os.path.join(output_dir, filename)):
            filename = f"{base_name}_{suffix}.txt"
            suffix += 1

        used_filenames.add(filename)

        start_idx = i * count_per_set
        set_children = children[start_idx:start_idx + count_per_set]

        filepath = os.path.join(output_dir, filename)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(parent_code + '\n')
            for child_code in set_children:
                f.write(child_code + '\n')

        created_count += 1

    return output_dir, created_count


def run_gui():
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk

    class VirtualAggregationApp:
        def __init__(self, root):
            self.root = root
            self.root.title("Виртуальная агрегация кодов маркировки")
            self.root.geometry("600x420")
            self.root.resizable(False, False)

            self.parent_file = ""
            self.child_files = []

            self.create_widgets()

        def create_widgets(self):
            frame = ttk.Frame(self.root, padding=15)
            frame.pack(fill=tk.BOTH, expand=True)

            # 1. Выбор файла родительских кодов
            ttk.Label(frame, text="1. Файл кодов маркировки наборов (родительские):", font=("Helvetica", 10, "bold")).pack(anchor=tk.W, pady=(0, 5))
            parent_btn_frame = ttk.Frame(frame)
            parent_btn_frame.pack(fill=tk.X, pady=(0, 10))

            self.parent_lbl = ttk.Label(parent_btn_frame, text="Файл не выбран", relief=tk.SUNKEN, anchor=tk.W)
            self.parent_lbl.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))

            ttk.Button(parent_btn_frame, text="Обзор...", command=self.select_parent_file).pack(side=tk.RIGHT)

            # 2. Количество вложений на набор
            ttk.Label(frame, text="2. Количество вложений в один набор:", font=("Helvetica", 10, "bold")).pack(anchor=tk.W, pady=(0, 5))
            count_frame = ttk.Frame(frame)
            count_frame.pack(fill=tk.X, pady=(0, 10))

            self.count_var = tk.StringVar(value="10")
            count_entry = ttk.Entry(count_frame, textvariable=self.count_var, width=10)
            count_entry.pack(side=tk.LEFT)

            # 3. Выбор файлов вложений (дочерние)
            ttk.Label(frame, text="3. Файлы кодов маркировки вложений (дочерние):", font=("Helvetica", 10, "bold")).pack(anchor=tk.W, pady=(0, 5))
            child_btn_frame = ttk.Frame(frame)
            child_btn_frame.pack(fill=tk.X, pady=(0, 5))

            self.child_lbl = ttk.Label(child_btn_frame, text="Файлы не выбраны", relief=tk.SUNKEN, anchor=tk.W)
            self.child_lbl.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))

            ttk.Button(child_btn_frame, text="Обзор...", command=self.select_child_files).pack(side=tk.RIGHT)

            self.child_listbox = tk.Listbox(frame, height=5)
            self.child_listbox.pack(fill=tk.BOTH, expand=True, pady=(0, 15))

            # 4. Кнопка запуска
            start_btn = ttk.Button(frame, text="Выполнить виртуальную агрегацию", command=self.start_aggregation)
            start_btn.pack(fill=tk.X, ipady=5)

        def select_parent_file(self):
            filepath = filedialog.askopenfilename(
                title="Выберите файл кодов наборов",
                filetypes=[("Текстовые файлы", "*.txt"), ("Все файлы", "*.*")]
            )
            if filepath:
                self.parent_file = filepath
                self.parent_lbl.config(text=os.path.basename(filepath))

        def select_child_files(self):
            filepaths = filedialog.askopenfilenames(
                title="Выберите файлы кодов вложений",
                filetypes=[("Текстовые файлы", "*.txt"), ("Все файлы", "*.*")]
            )
            if filepaths:
                self.child_files = list(filepaths)
                self.child_lbl.config(text=f"Выбрано файлов: {len(self.child_files)}")
                self.child_listbox.delete(0, tk.END)
                for f in self.child_files:
                    self.child_listbox.insert(tk.END, os.path.basename(f))

        def confirm_dialog(self, msg):
            return messagebox.askyesno("Подтверждение", msg)

        def start_aggregation(self):
            try:
                try:
                    count_per_set = int(self.count_var.get().strip())
                except ValueError:
                    messagebox.showerror("Ошибка", "Введите корректное число вложений на набор.")
                    return

                out_dir, created = perform_aggregation(
                    parent_file=self.parent_file,
                    child_files=self.child_files,
                    count_per_set=count_per_set,
                    confirm_callback=self.confirm_dialog
                )

                if out_dir and created > 0:
                    messagebox.showinfo(
                        "Успех",
                        f"Виртуальная агрегация успешно завершена!\n\n"
                        f"Создано наборов/файлов: {created}\n"
                        f"Папка результатов:\n{os.path.abspath(out_dir)}"
                    )
            except Exception as e:
                messagebox.showerror("Ошибка", str(e))

    root = tk.Tk()

    def global_exception_handler(exc_type, exc_value, exc_traceback):
        import traceback
        err_msg = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        messagebox.showerror("Необработанная ошибка", f"Произошла ошибка в программе:\n\n{err_msg}")

    sys.excepthook = global_exception_handler

    app = VirtualAggregationApp(root)
    root.mainloop()


if __name__ == "__main__":
    run_gui()
