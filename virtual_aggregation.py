"""
Утилита виртуальной агрегации кодов маркировки.

Инструкция по сборке в исполняемый файл (.exe):
1. Установите PyInstaller:
   pip install pyinstaller
2. Скомпилируйте скрипт в один файл без консольного окна:
   pyinstaller --noconsole --onefile virtual_aggregation.py
3. Готовый exe файл будет находиться в папке 'dist/'.
"""

import sys
import os
import re
import datetime
import traceback

# Ленивый импорт tkinter для корректной работы в headless тестах
try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
except ImportError:
    tk = None
    filedialog = None
    messagebox = None
    ttk = None


def sanitize_filename(filename):
    """
    Очищает строку от символов, недопустимых в именах файлов ОС Windows/Linux.
    """
    if not filename:
        return "unnamed"
    # Заменяем запрещенные символы на подчёркивания
    sanitized = re.sub(r'[\\/*?:"<>|]', '_', filename.strip())
    # Убираем управляющие символы
    sanitized = "".join(ch for ch in sanitized if ord(ch) >= 32)
    return sanitized if sanitized else "unnamed"


def read_codes(file_path):
    """
    Считывает коды маркировки из текстового файла.
    Пробует различные кодировки: UTF-8-SIG, UTF-16, UTF-8, CP1251.
    """
    encodings = ['utf-8-sig', 'utf-16', 'utf-8', 'cp1251']
    for enc in encodings:
        try:
            with open(file_path, 'r', encoding=enc) as f:
                lines = [line.strip() for line in f if line.strip()]
            return lines
        except (UnicodeError, LookupError):
            continue
        except Exception as e:
            raise e
    raise ValueError(f"Не удалось прочитать файл {file_path}. Поддерживаются кодировки UTF-8, UTF-16, CP1251.")


def perform_aggregation(parent_file, child_files, count_per_parent, confirm_callback=None):
    """
    Выполняет агрегацию кодов из родительского файла и файлов вложений.

    :param parent_file: путь к файлу с кодами наборов
    :param child_files: список путей к файлам с кодами вложений
    :param count_per_parent: количество вложений в один набор (int)
    :param confirm_callback: кастомная функция (или dialog) для подтверждения при нехватке кодов
    :return: (output_dir, created_count)
    """
    parent_codes = read_codes(parent_file)
    if not parent_codes:
        raise ValueError("Родительский файл не содержит кодов маркировки.")

    all_child_codes = []
    for c_file in child_files:
        all_child_codes.extend(read_codes(c_file))

    if not all_child_codes:
        raise ValueError("Файлы вложений не содержат кодов маркировки.")

    total_required = len(parent_codes) * count_per_parent
    actual_sets = min(len(parent_codes), len(all_child_codes) // count_per_parent)

    if actual_sets < len(parent_codes):
        msg = (f"Внимание: Недостаточно кодов вложений!\n"
               f"Требуется: {total_required} (наборов: {len(parent_codes)}, по {count_per_parent} шт.)\n"
               f"Доступно вложений: {len(all_child_codes)}\n"
               f"Будет сформировано наборов: {actual_sets}.\n"
               f"Продолжить?")
        if confirm_callback:
            if not confirm_callback(msg):
                return None, 0

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = f"aggregation_results_{timestamp}"
    os.makedirs(output_dir, exist_ok=True)

    created_count = 0
    used_filenames = {}

    for i in range(actual_sets):
        parent_code = parent_codes[i]
        start_idx = i * count_per_parent
        end_idx = start_idx + count_per_parent
        children = all_child_codes[start_idx:end_idx]

        base_filename = sanitize_filename(parent_code)
        filename = f"{base_filename}.txt"

        # Разрешение коллизий имён файлов
        if filename in used_filenames:
            used_filenames[filename] += 1
            filename = f"{base_filename}_{used_filenames[filename]}.txt"
        else:
            used_filenames[filename] = 0

        file_path = os.path.join(output_dir, filename)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(parent_code + '\n')
            for child in children:
                f.write(child + '\n')

        created_count += 1

    return output_dir, created_count


class VirtualAggregationApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Виртуальная агрегация наборов")
        self.root.geometry("650x450")
        self.root.resizable(True, True)

        self.parent_file = ""
        self.child_files = []

        self._build_ui()

    def _build_ui(self):
        main_frame = ttk.Frame(self.root, padding="15")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Выбор родительского файла
        lbl_parent = ttk.Label(main_frame, text="1. Файл кодов маркировки наборов (родительский TXT):", font=("Helvetica", 10, "bold"))
        lbl_parent.pack(anchor=tk.W, pady=(0, 5))

        f_parent = ttk.Frame(main_frame)
        f_parent.pack(fill=tk.X, pady=(0, 15))

        self.lbl_parent_path = ttk.Label(f_parent, text="Файл не выбран", relief=tk.SUNKEN, anchor=tk.W)
        self.lbl_parent_path.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        btn_parent = ttk.Button(f_parent, text="Обзор...", command=self.select_parent_file)
        btn_parent.pack(side=tk.RIGHT)

        # Количество вложений
        lbl_count = ttk.Label(main_frame, text="2. Количество вложений в каждый набор:", font=("Helvetica", 10, "bold"))
        lbl_count.pack(anchor=tk.W, pady=(0, 5))

        self.spin_count = ttk.Spinbox(main_frame, from_=1, to=1000, width=10)
        self.spin_count.set(10)
        self.spin_count.pack(anchor=tk.W, pady=(0, 15))

        # Выбор дочерних файлов
        lbl_children = ttk.Label(main_frame, text="3. Файлы кодов маркировки вложений (дочерние TXT):", font=("Helvetica", 10, "bold"))
        lbl_children.pack(anchor=tk.W, pady=(0, 5))

        f_children = ttk.Frame(main_frame)
        f_children.pack(fill=tk.BOTH, expand=True, pady=(0, 15))

        self.lst_children = tk.Listbox(f_children, selectmode=tk.EXTENDED, height=6)
        self.lst_children.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))

        scrollbar = ttk.Scrollbar(f_children, orient=tk.VERTICAL, command=self.lst_children.yview)
        scrollbar.pack(side=tk.LEFT, fill=tk.Y)
        self.lst_children.config(yscrollcommand=scrollbar.set)

        f_child_btns = ttk.Frame(f_children)
        f_child_btns.pack(side=tk.RIGHT, fill=tk.Y, padx=(5, 0))

        btn_add_child = ttk.Button(f_child_btns, text="Добавить...", command=self.select_child_files)
        btn_add_child.pack(fill=tk.X, pady=(0, 5))

        btn_clear_child = ttk.Button(f_child_btns, text="Очистить", command=self.clear_child_files)
        btn_clear_child.pack(fill=tk.X)

        # Кнопка запуска
        btn_start = ttk.Button(main_frame, text="Сформировать агрегированные файлы", command=self.run_aggregation)
        btn_start.pack(fill=tk.X, ipady=5)

    def select_parent_file(self):
        file_path = filedialog.askopenfilename(
            title="Выберите родительский TXT файл с кодами наборов",
            filetypes=[("Текстовые файлы", "*.txt"), ("Все файлы", "*.*")]
        )
        if file_path:
            self.parent_file = file_path
            self.lbl_parent_path.config(text=file_path)

    def select_child_files(self):
        files = filedialog.askopenfilenames(
            title="Выберите TXT файлы с кодами вложений",
            filetypes=[("Текстовые файлы", "*.txt"), ("Все файлы", "*.*")]
        )
        if files:
            for f in files:
                if f not in self.child_files:
                    self.child_files.append(f)
                    self.lst_children.insert(tk.END, f)

    def clear_child_files(self):
        self.child_files.clear()
        self.lst_children.delete(0, tk.END)

    def run_aggregation(self):
        if not self.parent_file:
            messagebox.showerror("Ошибка", "Не выбран родительский файл кодов наборов!")
            return

        if not self.child_files:
            messagebox.showerror("Ошибка", "Не выбраны файлы кодов вложений!")
            return

        try:
            count_per_parent = int(self.spin_count.get())
            if count_per_parent <= 0:
                raise ValueError()
        except ValueError:
            messagebox.showerror("Ошибка", "Количество вложений должно быть положительным целым числом!")
            return

        def confirm_cb(msg):
            return messagebox.askyesno("Подтверждение", msg)

        try:
            out_dir, created_count = perform_aggregation(
                self.parent_file,
                self.child_files,
                count_per_parent,
                confirm_callback=confirm_cb
            )

            if out_dir and created_count > 0:
                messagebox.showinfo(
                    "Успех",
                    f"Агрегация успешно завершена!\n\n"
                    f"Создано файлов: {created_count}\n"
                    f"Папка с результатом:\n{os.path.abspath(out_dir)}"
                )
            elif created_count == 0 and out_dir is not None:
                messagebox.showwarning("Предупреждение", "Не было создано ни одного файла.")

        except Exception as e:
            tb = traceback.format_exc()
            messagebox.showerror("Ошибка при выполнении агрегации", f"{str(e)}\n\n{tb}")


def main():
    if tk is None:
        print("Ошибка: Tkinter недоступен в данной среде.")
        sys.exit(1)

    root = tk.Tk()

    # Глобальный перехватчик ошибок в Tkinter
    def show_error(self, exc, val, tb):
        err_msg = "".join(traceback.format_exception(exc, val, tb))
        messagebox.showerror("Критическая ошибка", f"Произошла непредвиденная ошибка:\n{err_msg}")

    tk.Tk.report_callback_exception = show_error

    app = VirtualAggregationApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
