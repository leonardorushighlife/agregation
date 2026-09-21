"""
Скрипт для виртуальной агрегации кодов маркировки.

Инструкция по сборке в исполняемый файл (.exe):
1. Установите PyInstaller (если еще не установлен):
   pip install pyinstaller
2. Выполните команду сборки в консоли:
   pyinstaller --noconsole --onefile virtual_aggregation.py
3. Готовый файл virtual_aggregation.exe будет находится в папке 'dist'.
"""

import os
import sys
import re
import datetime
import traceback

# Разрешаем запуск без GUI в тестовой среде
try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
    TK_AVAILABLE = True
except ImportError:
    TK_AVAILABLE = False


def sanitize_filename(name):
    """
    Очищает строку от недопустимых символов для имени файла на Windows/Linux.
    """
    if not name:
        return "unnamed"
    # Замена недопустимых символов \ / : * ? " < > | на подчеркивание
    sanitized = re.sub(r'[\\/:*?"<>|]', '_', name.strip())
    # Удаление концевых точек и пробелов
    sanitized = sanitized.strip('. ')
    return sanitized if sanitized else "unnamed"


def read_codes(filepath):
    """
    Считывает коды маркировки из файла, пробуя различные кодировки.
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
        raise ValueError(f"Не удалось прочитать файл {filepath}. Проверьте кодировку файла.")

    # Разбиваем по строкам, удаляем пустые строки и внешние пробелы
    lines = [line.strip() for line in content.splitlines() if line.strip()]
    return lines


def perform_aggregation(parent_file, child_files, items_per_parent, output_dir=None, confirm_callback=None):
    """
    Основная логика агрегации кодов маркировки.

    :param parent_file: Путь к файлу с кодами набора (родительские коды)
    :param child_files: Список путей к файлам с кодами вложений (дочерние коды)
    :param items_per_parent: Количество кодов вложений в один набор
    :param output_dir: Целевая папка для сохранения (если None, создается новая)
    :param confirm_callback: Callback-функция для подтверждения действий пользователем
    :return: Кортеж (число_созданных_файлов, путь_к_папке)
    """
    if not parent_file or not os.path.exists(parent_file):
        raise FileNotFoundError("Файл с кодами набора не выбран или не существует.")

    if not child_files:
        raise ValueError("Не выбраны файлы с кодами вложений.")

    if items_per_parent <= 0:
        raise ValueError("Количество вложений должно быть больше 0.")

    parent_codes = read_codes(parent_file)
    if not parent_codes:
        raise ValueError("Файл с кодами набора пуст.")

    all_child_codes = []
    for c_file in child_files:
        if os.path.exists(c_file):
            all_child_codes.extend(read_codes(c_file))

    if not all_child_codes:
        raise ValueError("Выбранные файлы вложений не содержат кодов маркировки.")

    total_required = len(parent_codes) * items_per_parent
    actual_available = len(all_child_codes)

    if actual_available < total_required:
        msg = f"Для {len(parent_codes)} наборов требуется {total_required} вложений, но доступно только {actual_available}.\nПродолжить частичную агрегацию?"
        if confirm_callback:
            if not confirm_callback(msg):
                return 0, None

    actual_sets = min(len(parent_codes), actual_available // items_per_parent)
    if actual_sets == 0:
        raise ValueError(f"Недостаточно кодов вложений для формирования хотя бы одного полного набора из {items_per_parent} шт.")

    if not output_dir:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = os.path.abspath(f"aggregation_results_{timestamp}")

    os.makedirs(output_dir, exist_ok=True)

    created_count = 0
    used_filenames = set()

    for i in range(actual_sets):
        p_code = parent_codes[i]
        c_codes = all_child_codes[i * items_per_parent : (i + 1) * items_per_parent]

        base_filename = sanitize_filename(p_code)
        filename = f"{base_filename}.txt"

        # Обработка коллизий имен файлов
        suffix = 1
        filepath = os.path.join(output_dir, filename)
        while filepath.lower() in used_filenames or os.path.exists(filepath):
            filename = f"{base_filename}_{suffix}.txt"
            filepath = os.path.join(output_dir, filename)
            suffix += 1

        used_filenames.add(filepath.lower())

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(p_code + '\n')
            for c_code in c_codes:
                f.write(c_code + '\n')

        created_count += 1

    return created_count, output_dir


class AggregationApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Виртуальная агрегация кодов маркировки")
        self.root.geometry("600x480")
        self.root.minsize(500, 400)

        self.parent_file = ""
        self.child_files = []

        self._create_widgets()

    def _create_widgets(self):
        main_frame = ttk.Frame(self.root, padding=15)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 1. Файл кодов набора
        group_parent = ttk.LabelFrame(main_frame, text=" 1. Файл кодов набора (Родительский) ", padding=10)
        group_parent.pack(fill=tk.X, pady=(0, 10))

        self.lbl_parent = ttk.Label(group_parent, text="Файл не выбран", wraplength=400)
        self.lbl_parent.pack(side=tk.LEFT, fill=tk.X, expand=True)

        btn_select_parent = ttk.Button(group_parent, text="Выбрать файл", command=self._select_parent_file)
        btn_select_parent.pack(side=tk.RIGHT, padx=(10, 0))

        # 2. Настройки вложений
        group_count = ttk.LabelFrame(main_frame, text=" 2. Параметры агрегации ", padding=10)
        group_count.pack(fill=tk.X, pady=(0, 10))

        lbl_count = ttk.Label(group_count, text="Количество вложений в 1 набор:")
        lbl_count.pack(side=tk.LEFT, padx=(0, 10))

        self.spin_count = ttk.Spinbox(group_count, from_=1, to=1000, width=10)
        self.spin_count.set(1)
        self.spin_count.pack(side=tk.LEFT)

        # 3. Файлы кодов вложений
        group_child = ttk.LabelFrame(main_frame, text=" 3. Файлы кодов вложений (Дочерние) ", padding=10)
        group_child.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        btn_select_child = ttk.Button(group_child, text="Добавить файлы TXT", command=self._select_child_files)
        btn_select_child.pack(anchor=tk.W, pady=(0, 5))

        self.listbox_child = tk.Listbox(group_child, selectmode=tk.EXTENDED)
        self.listbox_child.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(group_child, orient=tk.VERTICAL, command=self.listbox_child.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.listbox_child.config(yscrollcommand=scrollbar.set)

        # Кнопка очистки списка вложений
        btn_clear_child = ttk.Button(group_child, text="Очистить", command=self._clear_child_files)
        btn_clear_child.pack(anchor=tk.E, pady=(5, 0))

        # 4. Запуск
        btn_start = ttk.Button(main_frame, text="Сформировать файлы агрегации", command=self._start_aggregation)
        btn_start.pack(fill=tk.X, ipady=5)

    def _select_parent_file(self):
        filepath = filedialog.askopenfilename(
            title="Выберите файл с кодами набора",
            filetypes=[("Текстовые файлы", "*.txt"), ("Все файлы", "*.*")]
        )
        if filepath:
            self.parent_file = filepath
            self.lbl_parent.config(text=filepath)

    def _select_child_files(self):
        filepaths = filedialog.askopenfilenames(
            title="Выберите файлы с кодами вложений",
            filetypes=[("Текстовые файлы", "*.txt"), ("Все файлы", "*.*")]
        )
        if filepaths:
            for fp in filepaths:
                if fp not in self.child_files:
                    self.child_files.append(fp)
                    self.listbox_child.insert(tk.END, fp)

    def _clear_child_files(self):
        self.child_files.clear()
        self.listbox_child.delete(0, tk.END)

    def _confirm_dialog(self, message):
        return messagebox.askyesno("Подтверждение", message)

    def _start_aggregation(self):
        try:
            items_per_parent = int(self.spin_count.get())
        except ValueError:
            messagebox.showerror("Ошибка ввода", "Введите корректное число вложений.")
            return

        try:
            created_count, output_dir = perform_aggregation(
                parent_file=self.parent_file,
                child_files=self.child_files,
                items_per_parent=items_per_parent,
                confirm_callback=self._confirm_dialog
            )

            if created_count > 0:
                messagebox.showinfo(
                    "Успех",
                    f"Успешно создано файлов: {created_count}\nПапка с результатами:\n{output_dir}"
                )
        except Exception as e:
            messagebox.showerror("Ошибка агрегации", str(e))


def main():
    if not TK_AVAILABLE:
        print("Ошибка: Tkinter не доступен в текущей среде.")
        sys.exit(1)

    root = tk.Tk()

    def custom_excepthook(exc_type, exc_value, exc_traceback):
        err_msg = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        messagebox.showerror("Необработанная ошибка", f"Произошла ошибка:\n{err_msg}")

    sys.excepthook = custom_excepthook

    app = AggregationApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
