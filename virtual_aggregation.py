"""
Инструкция по сборке в EXE (PyInstaller):
1. Установите PyInstaller: pip install pyinstaller
2. Выполните команду для сборки:
   pyinstaller --noconsole --onefile virtual_aggregation.py
3. Готовый исполняемый файл будет находиться в папке 'dist'.
"""

import os
import sys
import re
import traceback
from datetime import datetime

# Lazy/Guarded Tkinter imports to support headless execution and unit testing
try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
    TK_AVAILABLE = True
except ImportError:
    TK_AVAILABLE = False


def sanitize_filename(filename):
    """
    Заменяет недопустимые для имен файлов символы на символ подчеркивания.
    """
    if not filename:
        return "set"
    return re.sub(r'[\\/*?:"<>|\r\n\t]', '_', filename).strip()


def read_codes(file_path):
    """
    Читает коды из текстового файла, пробуя разные кодировки (UTF-8-SIG, UTF-16, UTF-8, CP1251).
    Возвращает список непустых строк.
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
        raise ValueError(f"Не удалось прочитать файл {file_path}. Поддерживаемые кодировки: UTF-8, UTF-16, CP1251.")

    lines = [line.strip() for line in content.splitlines() if line.strip()]
    return lines


def perform_aggregation(parent_file, child_files, count_per_parent, output_base_dir=None, confirm_callback=None):
    """
    Выполняет виртуальную агрегацию кодов.

    :param parent_file: путь к файлу с кодами наборов (родительские коды)
    :param child_files: список путей к файлам с кодами вложений (дочерние коды)
    :param count_per_parent: количество вложений на 1 набор
    :param output_base_dir: директория для создания итоговой папки (если None, используется текущая папка)
    :param confirm_callback: функция обратного вызова для подтверждения продолжения при нехватке кодов
    :return: (output_folder, count_sets_created)
    """
    if not parent_file or not os.path.exists(parent_file):
        raise ValueError("Файл с кодами набора не выбран или не существует.")

    if not child_files:
        raise ValueError("Не выбраны файлы с кодами вложений.")

    if count_per_parent <= 0:
        raise ValueError("Количество вложений должно быть больше 0.")

    parent_codes = read_codes(parent_file)
    if not parent_codes:
        raise ValueError("Файл с кодами наборов пуст.")

    all_child_codes = []
    for c_file in child_files:
        if os.path.exists(c_file):
            all_child_codes.extend(read_codes(c_file))

    if not all_child_codes:
        raise ValueError("Выбранные файлы вложений не содержат кодов.")

    total_parents = len(parent_codes)
    total_children = len(all_child_codes)
    required_children = total_parents * count_per_parent

    max_possible_sets = total_children // count_per_parent

    if max_possible_sets < total_parents:
        msg = (
            f"Внимание: Недостаточно кодов вложений!\n\n"
            f"Кодов наборов: {total_parents}\n"
            f"Кодов вложений в наличии: {total_children}\n"
            f"Требуется кодов вложений ({count_per_parent} шт. на набор): {required_children}\n\n"
            f"Будет сформировано наборов: {max_possible_sets}.\n"
            f"Продолжить?"
        )
        if confirm_callback:
            if not confirm_callback(msg):
                return None, 0

    actual_sets = min(total_parents, max_possible_sets)
    if actual_sets == 0:
        raise ValueError("Недостаточно кодов вложений даже для одного набора.")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    folder_name = f"aggregation_results_{timestamp}"

    if output_base_dir:
        output_folder = os.path.join(output_base_dir, folder_name)
    else:
        output_folder = os.path.abspath(folder_name)

    os.makedirs(output_folder, exist_ok=True)

    child_idx = 0
    created_count = 0
    used_filenames = set()

    for i in range(actual_sets):
        p_code = parent_codes[i]
        c_codes = all_child_codes[child_idx: child_idx + count_per_parent]
        child_idx += count_per_parent

        sanitized_p = sanitize_filename(p_code)
        filename = f"{sanitized_p}.txt"
        file_path = os.path.join(output_folder, filename)

        # Обработка коллизий имен файлов
        suffix = 1
        while filename.lower() in used_filenames or os.path.exists(file_path):
            filename = f"{sanitized_p}_{suffix}.txt"
            file_path = os.path.join(output_folder, filename)
            suffix += 1

        used_filenames.add(filename.lower())

        # Запись файла набора в UTF-8 без BOM
        with open(file_path, 'w', encoding='utf-8', newline='\n') as f:
            f.write(p_code + '\n')
            for c_code in c_codes:
                f.write(c_code + '\n')

        created_count += 1

    return output_folder, created_count


class VirtualAggregationApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Виртуальная агрегация кодов маркировки")
        self.root.geometry("650x550")
        self.root.minsize(550, 450)

        self.parent_file = ""
        self.child_files = []

        self.create_widgets()

    def create_widgets(self):
        # Перехват глобальных исключений
        self.root.report_callback_exception = self.show_error

        main_frame = ttk.Frame(self.root, padding="15")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Шаг 1: Выбор файла кодов набора
        group_parent = ttk.LabelFrame(main_frame, text=" 1. Файл кодов маркировки НАБОРА (1 файл) ", padding="10")
        group_parent.pack(fill=tk.X, pady=(0, 10))

        self.lbl_parent = ttk.Label(group_parent, text="Файл не выбран", foreground="gray", wraplength=450)
        self.lbl_parent.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))

        btn_parent = ttk.Button(group_parent, text="Обзор...", command=self.select_parent_file)
        btn_parent.pack(side=tk.RIGHT)

        # Шаг 2: Выбор файлов кодов вложений
        group_child = ttk.LabelFrame(main_frame, text=" 2. Файлы кодов маркировки ВЛОЖЕНИЙ (1 и более файлов) ", padding="10")
        group_child.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        self.txt_child_files = tk.Text(group_child, height=6, state=tk.DISABLED, wrap=tk.WORD)
        self.txt_child_files.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))

        scrollbar = ttk.Scrollbar(group_child, command=self.txt_child_files.yview)
        scrollbar.pack(side=tk.LEFT, fill=tk.Y)
        self.txt_child_files.config(yscrollcommand=scrollbar.set)

        btn_child_frame = ttk.Frame(group_child)
        btn_child_frame.pack(side=tk.RIGHT, fill=tk.Y)

        btn_child = ttk.Button(btn_child_frame, text="Обзор...", command=self.select_child_files)
        btn_child.pack(fill=tk.X, pady=(0, 5))

        btn_clear_child = ttk.Button(btn_child_frame, text="Очистить", command=self.clear_child_files)
        btn_clear_child.pack(fill=tk.X)

        # Шаг 3: Настройки и запуск
        group_settings = ttk.LabelFrame(main_frame, text=" 3. Параметры агрегации ", padding="10")
        group_settings.pack(fill=tk.X, pady=(0, 10))

        lbl_count = ttk.Label(group_settings, text="Количество вложений на 1 набор:")
        lbl_count.pack(side=tk.LEFT, padx=(0, 10))

        self.spin_count = ttk.Spinbox(group_settings, from_=1, to=1000, width=8)
        self.spin_count.set(10)
        self.spin_count.pack(side=tk.LEFT)

        # Кнопка старта
        btn_start = ttk.Button(main_frame, text="Создать папки и сформировать наборы", command=self.run_aggregation)
        btn_start.pack(fill=tk.X, ipady=5, pady=(5, 0))

    def select_parent_file(self):
        filename = filedialog.askopenfilename(
            title="Выберите файл с кодами наборов",
            filetypes=[("Текстовые файлы", "*.txt"), ("Все файлы", "*.*")]
        )
        if filename:
            self.parent_file = filename
            self.lbl_parent.config(text=os.path.basename(filename), foreground="black")

    def select_child_files(self):
        filenames = filedialog.askopenfilenames(
            title="Выберите файлы с кодами вложений",
            filetypes=[("Текстовые файлы", "*.txt"), ("Все файлы", "*.*")]
        )
        if filenames:
            self.child_files.extend(filenames)
            # Удаляем дубликаты сохраняя порядок
            self.child_files = list(dict.fromkeys(self.child_files))
            self.update_child_files_display()

    def clear_child_files(self):
        self.child_files = []
        self.update_child_files_display()

    def update_child_files_display(self):
        self.txt_child_files.config(state=tk.NORMAL)
        self.txt_child_files.delete("1.0", tk.END)
        for f in self.child_files:
            self.txt_child_files.insert(tk.END, os.path.basename(f) + "\n")
        self.txt_child_files.config(state=tk.DISABLED)

    def confirm_dialog(self, message):
        return messagebox.askyesno("Подтверждение", message, parent=self.root)

    def run_aggregation(self):
        try:
            count = int(self.spin_count.get())
        except ValueError:
            messagebox.showerror("Ошибка", "Введите корректное число вложений.")
            return

        try:
            output_folder, created_count = perform_aggregation(
                parent_file=self.parent_file,
                child_files=self.child_files,
                count_per_parent=count,
                confirm_callback=self.confirm_dialog
            )

            if output_folder and created_count > 0:
                messagebox.showinfo(
                    "Успех",
                    f"Виртуальная агрегация завершена!\n\n"
                    f"Успешно создано наборов: {created_count}\n"
                    f"Результаты сохранены в папке:\n{output_folder}"
                )
        except Exception as e:
            messagebox.showerror("Ошибка", str(e))

    def show_error(self, exc_type, exc_value, exc_traceback):
        err_msg = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        messagebox.showerror("Непредвиденная ошибка", err_msg)


def main():
    if not TK_AVAILABLE:
        print("Ошибка: Графический интерфейс Tkinter недоступен.")
        sys.exit(1)

    root = tk.Tk()
    app = VirtualAggregationApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
