"""
Скрипт виртуальной агрегации кодов маркировки.

Инструкция по сборке в исполняемый файл (.exe):
1. Установите PyInstaller (если не установлен):
   pip install pyinstaller
2. Выполните команду сборки в терминале:
   pyinstaller --noconsole --onefile virtual_aggregation.py
3. Готовый exe-файл будет находиться в папке dist/virtual_aggregation.exe.
"""

import os
import re
import sys
from datetime import datetime

# Lazy/guarded import of tkinter for GUI execution vs headless test execution
try:
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox
except ImportError:
    tk = None


def read_codes(filepath):
    """
    Считывает коды маркировки из текстового файла.
    Пробует различные кодировки (utf-8-sig, utf-16, utf-8, cp1251).
    Возвращает список непустых очищенных строк.
    """
    encodings = ['utf-8-sig', 'utf-16', 'utf-8', 'cp1251']
    content = None
    for enc in encodings:
        try:
            with open(filepath, 'r', encoding=enc) as f:
                content = f.read()
            break
        except (UnicodeError, LookupError):
            continue

    if content is None:
        raise ValueError(f"Не удалось прочитать файл {filepath} ни в одной из поддерживаемых кодировок.")

    lines = [line.strip() for line in content.splitlines() if line.strip()]
    return lines


def sanitize_filename(filename):
    """
    Заменяет недопустимые символы в имени файла на подчеркивание.
    """
    return re.sub(r'[\\/*?:"<>|]', '_', filename)


def perform_aggregation(parent_file, child_files, count_per_parent, output_dir=None, confirm_callback=None):
    """
    Выполняет виртуальную агрегацию:
    - parent_file: путь к файлу с кодами наборов
    - child_files: список путей к файлам с кодами вложений
    - count_per_parent: количество вложений на 1 набор (int)
    - output_dir: папка для сохранения результата (если None, создается автоматически с меткой времени)
    - confirm_callback: функция для запроса подтверждения у пользователя (при нехватке кодов), должна возвращать bool

    Возвращает словарь с результатами:
    {
        'output_dir': путь_к_папке,
        'created_files_count': количество_созданных_файлов,
        'total_parents': общее_число_родителей,
        'used_children': общее_число_использованных_вложений
    }
    """
    if count_per_parent <= 0:
        raise ValueError("Количество вложений на набор должно быть больше 0.")

    parent_codes = read_codes(parent_file)
    if not parent_codes:
        raise ValueError("Файл с кодами наборов пуст.")

    all_child_codes = []
    for cf in child_files:
        all_child_codes.extend(read_codes(cf))

    if not all_child_codes:
        raise ValueError("Выбранные файлы вложений не содержат кодов.")

    total_parents = len(parent_codes)
    required_children = total_parents * count_per_parent
    actual_children = len(all_child_codes)

    if actual_children < required_children:
        msg = (f"Внимание: Для {total_parents} наборов требуется {required_children} вложений,\n"
               f"но найдено только {actual_children} вложений.\n"
               f"Будет обработано столько полных наборов, насколько хватит кодов.\n"
               f"Продолжить?")
        if confirm_callback and not confirm_callback(msg):
            return None

    actual_sets = min(total_parents, actual_children // count_per_parent)
    if actual_sets == 0:
        raise ValueError(f"Недостаточно кодов вложений ({actual_children}) даже для одного набора по {count_per_parent} шт.")

    if output_dir is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = os.path.abspath(f"aggregation_results_{timestamp}")

    os.makedirs(output_dir, exist_ok=True)

    created_count = 0
    used_child_index = 0
    created_filenames = set()

    for i in range(actual_sets):
        p_code = parent_codes[i]
        c_codes = all_child_codes[used_child_index : used_child_index + count_per_parent]
        used_child_index += count_per_parent

        base_filename = sanitize_filename(p_code)
        filename = f"{base_filename}.txt"
        filepath = os.path.join(output_dir, filename)

        # Handle filename collisions if any
        suffix = 1
        while filepath in created_filenames or os.path.exists(filepath):
            filename = f"{base_filename}_{suffix}.txt"
            filepath = os.path.join(output_dir, filename)
            suffix += 1

        created_filenames.add(filepath)

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(p_code + '\n')
            for cc in c_codes:
                f.write(cc + '\n')

        created_count += 1

    return {
        'output_dir': output_dir,
        'created_files_count': created_count,
        'total_parents': total_parents,
        'used_children': used_child_index
    }


class VirtualAggregationApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Виртуальная агрегация кодов маркировки")
        self.root.geometry("650x520")
        self.root.minsize(550, 450)

        self.parent_file = ""
        self.child_files = []

        self._build_ui()

    def _build_ui(self):
        main_frame = ttk.Frame(self.root, padding="15")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 1. Выбор файла наборов (родители)
        parent_group = ttk.LabelFrame(main_frame, text=" 1. Коды маркировки наборов ", padding="10")
        parent_group.pack(fill=tk.X, pady=5)

        btn_parent = ttk.Button(parent_group, text="Выбрать файл наборов (.txt)", command=self._select_parent_file)
        btn_parent.pack(side=tk.LEFT, padx=5)

        self.lbl_parent_path = ttk.Label(parent_group, text="Файл не выбран", foreground="gray")
        self.lbl_parent_path.pack(side=tk.LEFT, padx=10, fill=tk.X, expand=True)

        # 2. Настройка количества вложений
        count_group = ttk.LabelFrame(main_frame, text=" 2. Количество вложений ", padding="10")
        count_group.pack(fill=tk.X, pady=5)

        ttk.Label(count_group, text="Количество вложений в 1 набор:").pack(side=tk.LEFT, padx=5)
        self.spin_count = ttk.Spinbox(count_group, from_=1, to=10000, width=10)
        self.spin_count.insert(0, "10")
        self.spin_count.pack(side=tk.LEFT, padx=5)

        # 3. Выбор файлов вложений (дочерние)
        child_group = ttk.LabelFrame(main_frame, text=" 3. Коды маркировки вложений ", padding="10")
        child_group.pack(fill=tk.BOTH, expand=True, pady=5)

        btn_child = ttk.Button(child_group, text="Выбрать файлы вложений (.txt)", command=self._select_child_files)
        btn_child.pack(anchor=tk.W, padx=5, pady=2)

        self.lbl_child_summary = ttk.Label(child_group, text="Файлы не выбраны", foreground="gray")
        self.lbl_child_summary.pack(anchor=tk.W, padx=5, pady=2)

        # Listbox for displaying selected child files
        list_frame = ttk.Frame(child_group)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.lst_child_files = tk.Listbox(list_frame, height=5)
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.lst_child_files.yview)
        self.lst_child_files.config(yscrollcommand=scrollbar.set)

        self.lst_child_files.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 4. Кнопка выполнения
        action_frame = ttk.Frame(main_frame, padding="10")
        action_frame.pack(fill=tk.X, pady=10)

        btn_start = ttk.Button(action_frame, text="Выполнить агрегацию", command=self._run_aggregation)
        btn_start.pack(fill=tk.X, ipady=5)

    def _select_parent_file(self):
        filepath = filedialog.askopenfilename(
            title="Выберите файл с кодами маркировки наборов",
            filetypes=[("Текстовые файлы", "*.txt"), ("Все файлы", "*.*")]
        )
        if filepath:
            self.parent_file = filepath
            self.lbl_parent_path.config(text=os.path.basename(filepath), foreground="black")

    def _select_child_files(self):
        filepaths = filedialog.askopenfilenames(
            title="Выберите файлы с кодами маркировки вложений",
            filetypes=[("Текстовые файлы", "*.txt"), ("Все файлы", "*.*")]
        )
        if filepaths:
            self.child_files = list(filepaths)
            self.lbl_child_summary.config(
                text=f"Выбрано файлов: {len(self.child_files)}",
                foreground="black"
            )
            self.lst_child_files.delete(0, tk.END)
            for f in self.child_files:
                self.lst_child_files.insert(tk.END, os.path.basename(f))

    def _run_aggregation(self):
        if not self.parent_file:
            messagebox.showwarning("Предупреждение", "Пожалуйста, выберите файл с кодами наборов.")
            return

        if not self.child_files:
            messagebox.showwarning("Предупреждение", "Пожалуйста, выберите хотя бы один файл с кодами вложений.")
            return

        try:
            count_per_parent = int(self.spin_count.get())
        except ValueError:
            messagebox.showerror("Ошибка", "Введите корректное числовое значение для количества вложений.")
            return

        def confirm_cb(msg):
            return messagebox.askyesno("Подтверждение", msg)

        try:
            res = perform_aggregation(
                parent_file=self.parent_file,
                child_files=self.child_files,
                count_per_parent=count_per_parent,
                confirm_callback=confirm_cb
            )

            if res is not None:
                messagebox.showinfo(
                    "Успех",
                    f"Виртуальная агрегация успешно завершена!\n\n"
                    f"Создано файлов (наборов): {res['created_files_count']}\n"
                    f"Использовано вложений: {res['used_children']}\n"
                    f"Результаты сохранены в папку:\n{res['output_dir']}"
                )
        except Exception as e:
            messagebox.showerror("Ошибка", f"Произошла ошибка при выполнении агрегации:\n{str(e)}")


def main():
    if tk is None:
        print("Ошибка: Tkinter не доступен в текущем окружении Python.")
        sys.exit(1)
    root = tk.Tk()
    app = VirtualAggregationApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
