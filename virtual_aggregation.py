"""
Скрипт для виртуальной агрегации кодов маркировки.

Инструкция по сборке в EXE файл через PyInstaller:
1. Установите PyInstaller, если он еще не установлен:
   pip install pyinstaller
2. Выполните команду сборки в консоли/терминале из директории со скриптом:
   pyinstaller --noconsole --onefile virtual_aggregation.py
3. Готовый исполняемый файл `.exe` появится в папке `dist/`.
"""

import os
import re
import sys
import datetime

# Ленивый или безопасный импорт tkinter для поддержки безголового запуска (headless unit testing)
try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
    TK_AVAILABLE = True
except ImportError:
    TK_AVAILABLE = False


def read_codes(file_path):
    """
    Считывает строки кодов из файла, пытаясь определить кодировку.
    Поддерживаемые кодировки: UTF-8-SIG, UTF-16, UTF-8, CP1251.
    Возвращает список непустых очищенных строк.
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


def sanitize_filename(filename, existing_names=None):
    """
    Очищает имя файла от недопустимых символов и предотвращает коллизии имен.
    """
    if existing_names is None:
        existing_names = set()

    # Замена недопустимых символов для имен файлов в Windows/Linux/macOS
    sanitized = re.sub(r'[\\/:*?"<>|]', '_', filename)
    sanitized = sanitized.strip('. ')
    if not sanitized:
        sanitized = "set_code"

    base_name = sanitized
    candidate = f"{base_name}.txt"
    counter = 1

    while candidate in existing_names:
        candidate = f"{base_name}_{counter}.txt"
        counter += 1

    existing_names.add(candidate)
    return candidate


def perform_aggregation(parent_file, child_files, count_per_set, output_dir=None, confirm_partial_callback=None):
    """
    Выполняет виртуальную агрегацию кодов.
    :param parent_file: Путь к файлу с кодами набора (родительские)
    :param child_files: Список путей к файлам с кодами вложений (дочерние)
    :param count_per_set: Количество вложений в 1 набор (int)
    :param output_dir: Целевая папка (если None, создается новая с временной меткой)
    :param confirm_partial_callback: Callback-функция, возвращающая True/False, если не хватает кодов
    :return: Словарь с результатами (папка, количество созданных файлов, всего прикреплено кодов)
    """
    if count_per_set <= 0:
        raise ValueError("Количество вложений должно быть больше 0.")

    parent_codes = read_codes(parent_file)
    if not parent_codes:
        raise ValueError("Файл кодов наборов пуст.")

    child_codes = []
    for c_file in child_files:
        child_codes.extend(read_codes(c_file))

    if not child_codes:
        raise ValueError("Файлы кодов вложений не содержат кодов.")

    total_needed = len(parent_codes) * count_per_set
    if len(child_codes) < total_needed:
        actual_sets = len(child_codes) // count_per_set
        if actual_sets == 0:
            raise ValueError(f"Недостаточно кодов вложений ({len(child_codes)}) даже для одного набора по {count_per_set} шт.")

        if confirm_partial_callback:
            msg = (f"Кодов вложений ({len(child_codes)}) недостаточно для полного формирования {len(parent_codes)} наборов.\n"
                   f"Будет сформировано только {actual_sets} наборов.\n"
                   f"Продолжить?")
            if not confirm_partial_callback(msg):
                return None

        parent_codes = parent_codes[:actual_sets]

    if output_dir is None:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = f"aggregation_results_{timestamp}"

    os.makedirs(output_dir, exist_ok=True)

    existing_filenames = set()
    created_count = 0
    child_idx = 0

    for p_code in parent_codes:
        filename = sanitize_filename(p_code, existing_filenames)
        filepath = os.path.join(output_dir, filename)

        items_for_this_set = child_codes[child_idx : child_idx + count_per_set]
        child_idx += count_per_set

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(p_code + '\n')
            for c_code in items_for_this_set:
                f.write(c_code + '\n')

        created_count += 1

    return {
        "output_dir": output_dir,
        "sets_created": created_count,
        "total_children_used": child_idx
    }


if TK_AVAILABLE:
    class VirtualAggregationApp:
        def __init__(self, root):
            self.root = root
            self.root.title("Виртуальная Агрегация Кодов Маркировки")
            self.root.geometry("600x480")
            self.root.resizable(False, False)

            self.parent_file = ""
            self.child_files = []

            self._create_widgets()

        def _create_widgets(self):
            pad = {'padx': 10, 'pady': 5}

            # Родительский файл (Набор)
            frame_parent = ttk.LabelFrame(self.root, text=" 1. Файл кодов маркировки на НАБОР ")
            frame_parent.pack(fill="x", **pad)

            self.lbl_parent = ttk.Label(frame_parent, text="Файл не выбран", wraplength=450)
            self.lbl_parent.pack(side="left", padx=10, pady=10, fill="x", expand=True)

            btn_parent = ttk.Button(frame_parent, text="Обзор...", command=self.select_parent_file)
            btn_parent.pack(side="right", padx=10, pady=10)

            # Дочерние файлы (Вложения)
            frame_child = ttk.LabelFrame(self.root, text=" 2. Файлы кодов маркировки ВЛОЖЕНИЙ (TXT) ")
            frame_child.pack(fill="both", expand=True, **pad)

            self.list_children = tk.Listbox(frame_child, selectmode=tk.EXTENDED, height=5)
            self.list_children.pack(side="left", fill="both", expand=True, padx=(10, 0), pady=10)

            scrollbar = ttk.Scrollbar(frame_child, orient="vertical", command=self.list_children.yview)
            scrollbar.pack(side="left", fill="y", pady=10)
            self.list_children.config(yscrollcommand=scrollbar.set)

            frame_child_btns = ttk.Frame(frame_child)
            frame_child_btns.pack(side="right", fill="y", padx=10, pady=10)

            btn_add_children = ttk.Button(frame_child_btns, text="Добавить...", command=self.add_child_files)
            btn_add_children.pack(fill="x", pady=2)

            btn_clear_children = ttk.Button(frame_child_btns, text="Очистить", command=self.clear_child_files)
            btn_clear_children.pack(fill="x", pady=2)

            # Настройки агрегации
            frame_settings = ttk.LabelFrame(self.root, text=" 3. Параметры ")
            frame_settings.pack(fill="x", **pad)

            ttk.Label(frame_settings, text="Количество вложений в 1 набор:").pack(side="left", padx=10, pady=10)
            self.ent_count = ttk.Entry(frame_settings, width=10)
            self.ent_count.insert(0, "10")
            self.ent_count.pack(side="left", padx=5, pady=10)

            # Кнопка запуска
            btn_run = ttk.Button(self.root, text="Сформировать агрегацию", command=self.run_aggregation)
            btn_run.pack(fill="x", padx=10, pady=15)

            # Строка состояния
            self.lbl_status = ttk.Label(self.root, text="Готов к работе", relief=tk.SUNKEN, anchor="w")
            self.lbl_status.pack(side="bottom", fill="x")

        def select_parent_file(self):
            filename = filedialog.askopenfilename(
                title="Выберите файл кодов наборов",
                filetypes=[("Текстовые файлы (*.txt)", "*.txt"), ("Все файлы", "*.*")]
            )
            if filename:
                self.parent_file = filename
                self.lbl_parent.config(text=filename)

        def add_child_files(self):
            filenames = filedialog.askopenfilenames(
                title="Выберите файлы кодов вложений",
                filetypes=[("Текстовые файлы (*.txt)", "*.txt"), ("Все файлы", "*.*")]
            )
            if filenames:
                for fn in filenames:
                    if fn not in self.child_files:
                        self.child_files.append(fn)
                        self.list_children.insert(tk.END, fn)

        def clear_child_files(self):
            self.child_files.clear()
            self.list_children.delete(0, tk.END)

        def run_aggregation(self):
            if not self.parent_file:
                messagebox.showerror("Ошибка", "Пожалуйста, выберите файл кодов наборов.")
                return

            if not self.child_files:
                messagebox.showerror("Ошибка", "Пожалуйста, выберите хотя бы один файл вложений.")
                return

            try:
                count_per_set = int(self.ent_count.get().strip())
                if count_per_set <= 0:
                    raise ValueError
            except ValueError:
                messagebox.showerror("Ошибка", "Укажите корректное положительное число вложений в набор.")
                return

            def confirm_partial(msg):
                return messagebox.askyesno("Недостаточно кодов вложений", msg)

            try:
                res = perform_aggregation(
                    parent_file=self.parent_file,
                    child_files=self.child_files,
                    count_per_set=count_per_set,
                    confirm_partial_callback=confirm_partial
                )

                if res:
                    out_dir = os.path.abspath(res['output_dir'])
                    msg = (f"Агрегация успешно завершена!\n\n"
                           f"Создано наборов (файлов): {res['sets_created']}\n"
                           f"Использовано вложений: {res['total_children_used']}\n"
                           f"Папка с результатами:\n{out_dir}")
                    messagebox.showinfo("Успех", msg)
                    self.lbl_status.config(text=f"Готово. Результаты в: {out_dir}")

            except Exception as e:
                messagebox.showerror("Ошибка агрегации", f"Произошла ошибка при выполнении операции:\n{str(e)}")


def global_exception_handler(exctype, value, tb):
    import traceback
    err_msg = "".join(traceback.format_exception(exctype, value, tb))
    print(err_msg, file=sys.stderr)
    if TK_AVAILABLE:
        try:
            messagebox.showerror("Критическая ошибка", f"Произошла непредвиденная ошибка:\n{value}\n\n{err_msg}")
        except Exception:
            pass


def main():
    if not TK_AVAILABLE:
        print("Ошибка: Графическое окружение Tkinter недоступно.")
        sys.exit(1)

    sys.excepthook = global_exception_handler
    root = tk.Tk()
    app = VirtualAggregationApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
