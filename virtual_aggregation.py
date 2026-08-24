"""
Скрипт для виртуальной агрегации кодов маркировки.

Инструкции по сборке в исполняемый файл (.exe) с помощью PyInstaller:
1. Установите PyInstaller:
   pip install pyinstaller
2. Выполните команду для сборки standalone файла без консольного окна:
   pyinstaller --noconsole --onefile virtual_aggregation.py
3. Готовый файл virtual_aggregation.exe будет находиться в папке 'dist'.
"""

import os
import re
import sys
import datetime
import traceback

def read_codes(filepath):
    """
    Считывает маркировочные коды из файлa TXT.
    Пробует различные кодировки: UTF-8-SIG, UTF-16, UTF-8, CP1251.
    """
    encodings = ['utf-8-sig', 'utf-16', 'utf-8', 'cp1251']
    for enc in encodings:
        try:
            with open(filepath, 'r', encoding=enc) as f:
                lines = [line.strip() for line in f if line.strip()]
            return lines
        except (UnicodeError, LookupError):
            continue
    # Если ни одна кодировка не подошла через open(), прочитать в binary и декодировать c errors='replace'
    with open(filepath, 'rb') as f:
        content = f.read().decode('utf-8', errors='replace')
    return [line.strip() for line in content.splitlines() if line.strip()]


def sanitize_filename(name):
    """
    Очищает строку от недопустимых для имени файла символов.
    """
    sanitized = re.sub(r'[\/\\\:\*\?\"<>\|]', '_', name)
    sanitized = re.sub(r'[\x00-\x1f\x7f]', '_', sanitized)
    sanitized = sanitized.strip('. ')
    return sanitized if sanitized else "set_code"


def perform_aggregation(parent_file, child_files, count_per_parent, output_dir_base=None, confirm_partial_callback=None):
    """
    Выполняет виртуальную агрегацию.

    :param parent_file: Путь к TXT файлу с кодами родителя (набора).
    :param child_files: Список путей к TXT файлам с кодами вложений.
    :param count_per_parent: Количество вложений на 1 родительский код.
    :param output_dir_base: Базовая директория для создания выходной папки (по умолчанию текущая).
    :param confirm_partial_callback: Callback-функция (message -> bool) для подтверждения частичной агрегации.
    :return: dict с результатом (success, output_folder, sets_created, total_children_used, message).
    """
    if count_per_parent <= 0:
        return {'success': False, 'message': 'Количество вложений должно быть больше 0.'}

    parent_codes = read_codes(parent_file)
    if not parent_codes:
        return {'success': False, 'message': f'Файл родительских кодов пуст или не удалось прочитать: {parent_file}'}

    child_codes = []
    for cf in child_files:
        codes = read_codes(cf)
        child_codes.extend(codes)

    if not child_codes:
        return {'success': False, 'message': 'Файлы вложений не содержат кодов.'}

    total_parents = len(parent_codes)
    total_children = len(child_codes)
    required_children = total_parents * count_per_parent

    if total_children < required_children:
        msg = (f"Вниманию пользователю:\n"
               f"Всего кодов вложений ({total_children}) меньше, чем требуется для полного заполнения всех наборов "
               f"({required_children} для {total_parents} наборов по {count_per_parent} шт.).\n\n"
               f"Продолжить с имеющимся количеством вложений?")
        if confirm_partial_callback:
            if not confirm_partial_callback(msg):
                return {'success': False, 'message': 'Операция отменена пользователем.'}

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    folder_name = f"aggregation_results_{timestamp}"
    if output_dir_base:
        output_folder = os.path.join(output_dir_base, folder_name)
    else:
        output_folder = os.path.abspath(folder_name)

    os.makedirs(output_folder, exist_ok=True)

    child_idx = 0
    sets_created = 0
    used_filenames = set()

    for p_code in parent_codes:
        if child_idx >= total_children:
            break

        # Берём до count_per_parent кодов вложений
        items_for_this_set = child_codes[child_idx : child_idx + count_per_parent]
        child_idx += len(items_for_this_set)

        if not items_for_this_set:
            break

        base_fname = sanitize_filename(p_code)
        fname = f"{base_fname}.txt"
        counter = 1
        while fname in used_filenames or os.path.exists(os.path.join(output_folder, fname)):
            fname = f"{base_fname}_{counter}.txt"
            counter += 1

        used_filenames.add(fname)
        file_path = os.path.join(output_folder, fname)

        with open(file_path, 'w', encoding='utf-8', newline='\n') as f:
            f.write(p_code + '\n')
            for c_code in items_for_this_set:
                f.write(c_code + '\n')

        sets_created += 1

    return {
        'success': True,
        'output_folder': output_folder,
        'sets_created': sets_created,
        'total_children_used': child_idx,
        'message': f'Успешно создано наборов: {sets_created}.\nПапка с результатами:\n{output_folder}'
    }


def main_gui():
    try:
        import tkinter as tk
        from tkinter import ttk, filedialog, messagebox
    except ImportError:
        print("GUI библиотека tkinter не доступна.")
        sys.exit(1)

    class AggregationApp:
        def __init__(self, root):
            self.root = root
            self.root.title("Виртуальная агрегация кодов маркировки")
            self.root.geometry("620x450")
            self.root.resizable(True, True)

            self.parent_file = ""
            self.child_files = []

            self._create_widgets()

        def _create_widgets(self):
            padding = {'padx': 10, 'pady': 5}

            # Родительский файл
            frame_parent = ttk.LabelFrame(self.root, text="1. Выбор файла родительских кодов (наборов)")
            frame_parent.pack(fill="x", **padding)

            self.lbl_parent = ttk.Label(frame_parent, text="Файл не выбран", wraplength=580)
            self.lbl_parent.pack(anchor="w", padx=5, pady=2)

            btn_parent = ttk.Button(frame_parent, text="Обзор...", command=self._select_parent_file)
            btn_parent.pack(anchor="e", padx=5, pady=2)

            # Количество вложений
            frame_count = ttk.LabelFrame(self.root, text="2. Количество вложений на 1 набор")
            frame_count.pack(fill="x", **padding)

            ttk.Label(frame_count, text="Вложений в набор (шт.):").pack(side="left", padx=5, pady=5)
            self.spin_count = ttk.Spinbox(frame_count, from_=1, to=1000, width=10)
            self.spin_count.set(10)
            self.spin_count.pack(side="left", padx=5, pady=5)

            # Файлы вложений
            frame_child = ttk.LabelFrame(self.root, text="3. Выбор файлов кодов вложений (TXT)")
            frame_child.pack(fill="both", expand=True, **padding)

            btn_child = ttk.Button(frame_child, text="Добавить файлы...", command=self._select_child_files)
            btn_child.pack(anchor="e", padx=5, pady=2)

            btn_clear_child = ttk.Button(frame_child, text="Очистить список", command=self._clear_child_files)
            btn_clear_child.pack(anchor="e", padx=5, pady=2)

            self.list_child = tk.Listbox(frame_child, height=5)
            self.list_child.pack(fill="both", expand=True, padx=5, pady=5)

            # Кнопка запуска
            btn_run = ttk.Button(self.root, text="Запустить агрегацию", command=self._run_aggregation)
            btn_run.pack(pady=10)

        def _select_parent_file(self):
            path = filedialog.askopenfilename(
                title="Выберите TXT файл родительских кодов",
                filetypes=[("Текстовые файлы", "*.txt"), ("Все файлы", "*.*")]
            )
            if path:
                self.parent_file = path
                self.lbl_parent.config(text=path)

        def _select_child_files(self):
            paths = filedialog.askopenfilenames(
                title="Выберите TXT файлы кодов вложений",
                filetypes=[("Текстовые файлы", "*.txt"), ("Все файлы", "*.*")]
            )
            if paths:
                for p in paths:
                    if p not in self.child_files:
                        self.child_files.append(p)
                        self.list_child.insert(tk.END, p)

        def _clear_child_files(self):
            self.child_files = []
            self.list_child.delete(0, tk.END)

        def _confirm_callback(self, message_text):
            from tkinter import messagebox
            return messagebox.askyesno("Подтверждение", message_text)

        def _run_aggregation(self):
            from tkinter import messagebox
            if not self.parent_file:
                messagebox.showerror("Ошибка", "Не выбран файл родительских кодов!")
                return

            if not self.child_files:
                messagebox.showerror("Ошибка", "Не выбраны файлы кодов вложений!")
                return

            try:
                count = int(self.spin_count.get())
                if count <= 0:
                    raise ValueError()
            except ValueError:
                messagebox.showerror("Ошибка", "Количество вложений должно быть целым положительным числом!")
                return

            try:
                res = perform_aggregation(
                    parent_file=self.parent_file,
                    child_files=self.child_files,
                    count_per_parent=count,
                    confirm_partial_callback=self._confirm_callback
                )
                if res['success']:
                    messagebox.showinfo("Успех", res['message'])
                else:
                    messagebox.showwarning("Предупреждение", res['message'])
            except Exception as e:
                tb = traceback.format_exc()
                messagebox.showerror("Критическая ошибка", f"Произошла ошибка при выполнении:\n{e}\n\nTraceback:\n{tb}")

    root = tk.Tk()
    app = AggregationApp(root)
    root.mainloop()


if __name__ == "__main__":
    try:
        main_gui()
    except Exception as e:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("Необработанная ошибка", f"Ошибка: {e}\n\n{traceback.format_exc()}")
