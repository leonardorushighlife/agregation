"""
Скрипт виртуальной агрегации кодов маркировки.

Инструкция по сборке в исполняемый файл (.exe):
1. Установите PyInstaller:
   pip install pyinstaller
2. Выполните команду сборки:
   pyinstaller --noconsole --onefile virtual_aggregation.py
3. Готовый exe-файл появится в папке 'dist'.
"""

import os
import re
import sys
import datetime
import traceback

def read_codes(file_path):
    """
    Считывает строки из файла, пробуя последовательно различные кодировки.
    Удаляет пустые строки и пробельные символы по краям.
    """
    encodings = ['utf-8-sig', 'utf-16', 'utf-8', 'cp1251']
    for enc in encodings:
        try:
            with open(file_path, 'r', encoding=enc) as f:
                lines = [line.strip() for line in f if line.strip()]
            return lines
        except (UnicodeError, LookupError):
            continue
    raise ValueError(f"Не удалось прочитать файл {file_path}. Проверьте кодировку.")


def sanitize_filename(code):
    """
    Заменяет недопустимые символы в имени файла на символ подчеркивания.
    """
    return re.sub(r'[\x00-\x1f\\/:*?"<>|]', '_', code)


def perform_aggregation(parent_file, child_files, count_per_parent, confirm_callback=None):
    """
    Основная логика виртуальной агрегации.

    :param parent_file: путь к файлу с кодами наборов (родительские коды)
    :param child_files: список путей к файлам с кодами вложений (дочерние коды)
    :param count_per_parent: количество вложений в один набор
    :param confirm_callback: функция обратного вызова для подтверждения при нехватке кодов
    :return: кортеж (output_dir, created_count, total_children_used)
    """
    if count_per_parent <= 0:
        raise ValueError("Количество вложений должно быть больше 0.")

    parent_codes = read_codes(parent_file)
    if not parent_codes:
        raise ValueError("Файл с родительскими кодами пуст.")

    all_child_codes = []
    for cf in child_files:
        all_child_codes.extend(read_codes(cf))

    if not all_child_codes:
        raise ValueError("Файлы с кодами вложений пусты.")

    total_parents = len(parent_codes)
    total_children = len(all_child_codes)
    required_children = total_parents * count_per_parent

    possible_sets_by_children = total_children // count_per_parent
    actual_sets_count = min(total_parents, possible_sets_by_children)

    if required_children > total_children:
        msg = (
            f"Недостаточно кодов вложений!\n"
            f"Требуется: {required_children} кодов (на {total_parents} наборов по {count_per_parent} шт.).\n"
            f"Доступно: {total_children} кодов.\n"
            f"Будет сформировано полных наборов: {actual_sets_count}.\n"
            f"Продолжить?"
        )
        if confirm_callback and not confirm_callback(msg):
            return None, 0, 0

    if actual_sets_count == 0:
        raise ValueError(
            f"Недостаточно кодов вложений для создания хотя бы одного полного набора по {count_per_parent} шт."
        )

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = f"aggregation_results_{timestamp}"
    os.makedirs(output_dir, exist_ok=True)

    created_files = 0
    used_children = 0
    used_filenames = {}

    for i in range(actual_sets_count):
        parent_code = parent_codes[i]
        start_idx = i * count_per_parent
        end_idx = start_idx + count_per_parent
        children_subset = all_child_codes[start_idx:end_idx]

        base_filename = sanitize_filename(parent_code)
        if not base_filename:
            base_filename = f"set_{i+1}"

        filename = base_filename
        if filename.lower() in used_filenames:
            used_filenames[filename.lower()] += 1
            filename = f"{base_filename}_{used_filenames[filename.lower()]}"
        else:
            used_filenames[filename.lower()] = 0

        file_path = os.path.join(output_dir, f"{filename}.txt")
        with open(file_path, 'w', encoding='utf-8', newline='\n') as f:
            f.write(parent_code + '\n')
            for child in children_subset:
                f.write(child + '\n')

        created_files += 1
        used_children += len(children_subset)

    return output_dir, created_files, used_children


def launch_gui():
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk

    class AggregationApp:
        def __init__(self, root):
            self.root = root
            self.root.title("Виртуальная Агрегация Кодов Маркировки")
            self.root.geometry("600x480")
            self.root.minsize(550, 420)

            self.parent_file = ""
            self.child_files = []

            self._build_ui()

        def _build_ui(self):
            padding = {'padx': 10, 'pady': 5}

            # Родительский файл
            frame_parent = ttk.LabelFrame(self.root, text=" 1. Файл кодов маркировки наборов (Родительские) ")
            frame_parent.pack(fill="x", **padding)

            self.lbl_parent = ttk.Label(frame_parent, text="Файл не выбран", font=("Arial", 9, "italic"))
            self.lbl_parent.pack(side="left", padx=10, pady=8, expand=True, fill="x")

            btn_parent = ttk.Button(frame_parent, text="Обзор...", command=self.select_parent_file)
            btn_parent.pack(side="right", padx=10, pady=8)

            # Файлы вложений
            frame_child = ttk.LabelFrame(self.root, text=" 2. Файлы кодов маркировки вложений (Дочерние) ")
            frame_child.pack(fill="both", expand=True, **padding)

            btn_child = ttk.Button(frame_child, text="Добавить файлы...", command=self.select_child_files)
            btn_child.pack(anchor="ne", padx=10, pady=5)

            self.list_child = tk.Listbox(frame_child, selectmode=tk.EXTENDED, height=5)
            self.list_child.pack(fill="both", expand=True, padx=10, pady=5)

            btn_clear_child = ttk.Button(frame_child, text="Очистить список", command=self.clear_child_files)
            btn_clear_child.pack(anchor="se", padx=10, pady=5)

            # Количество вложений
            frame_count = ttk.LabelFrame(self.root, text=" 3. Параметры агрегации ")
            frame_count.pack(fill="x", **padding)

            ttk.Label(frame_count, text="Количество вложений в 1 набор:").pack(side="left", padx=10, pady=8)
            self.spin_count = ttk.Spinbox(frame_count, from_=1, to=10000, width=10)
            self.spin_count.set(1)
            self.spin_count.pack(side="left", padx=5, pady=8)

            # Кнопка Запуска
            btn_run = ttk.Button(self.root, text="Запустить агрегацию", command=self.run_aggregation)
            btn_run.pack(pady=15)

        def select_parent_file(self):
            path = filedialog.askopenfilename(
                title="Выберите файл с кодами наборов",
                filetypes=[("Текстовые файлы", "*.txt"), ("Все файлы", "*.*")]
            )
            if path:
                self.parent_file = path
                self.lbl_parent.config(text=os.path.basename(path), font=("Arial", 9, "normal"))

        def select_child_files(self):
            paths = filedialog.askopenfilenames(
                title="Выберите файлы с кодами вложений",
                filetypes=[("Текстовые файлы", "*.txt"), ("Все файлы", "*.*")]
            )
            if paths:
                for p in paths:
                    if p not in self.child_files:
                        self.child_files.append(p)
                        self.list_child.insert(tk.END, os.path.basename(p))

        def clear_child_files(self):
            self.child_files.clear()
            self.list_child.delete(0, tk.END)

        def run_aggregation(self):
            if not self.parent_file:
                messagebox.showerror("Ошибка", "Выберите файл с родительскими кодами наборов.")
                return

            if not self.child_files:
                messagebox.showerror("Ошибка", "Выберите хотя бы один файл с кодами вложений.")
                return

            try:
                count = int(self.spin_count.get())
                if count <= 0:
                    raise ValueError()
            except ValueError:
                messagebox.showerror("Ошибка", "Количество вложений должно быть положительным целым числом.")
                return

            try:
                out_dir, created, total_children = perform_aggregation(
                    parent_file=self.parent_file,
                    child_files=self.child_files,
                    count_per_parent=count,
                    confirm_callback=messagebox.askyesno
                )

                if out_dir:
                    messagebox.showinfo(
                        "Успех",
                        f"Виртуальная агрегация завершена!\n\n"
                        f"Создано наборов (файлов): {created}\n"
                        f"Использовано вложений: {total_children}\n"
                        f"Результаты сохранены в папке:\n{os.path.abspath(out_dir)}"
                    )
            except Exception as e:
                err_msg = traceback.format_exc()
                messagebox.showerror("Ошибка агрегации", f"{str(e)}\n\nДетали:\n{err_msg}")

    root = tk.Tk()

    # Глобальный обработчик исключений
    def report_callback_exception(exc_type, exc_value, exc_traceback):
        err_text = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        messagebox.showerror("Критическая ошибка", f"Произошла непредвиденная ошибка:\n\n{err_text}")

    root.report_callback_exception = report_callback_exception
    app = AggregationApp(root)
    root.mainloop()


if __name__ == "__main__":
    launch_gui()
