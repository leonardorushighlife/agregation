"""
Скрипт для виртуальной агрегации кодов маркировки.

Инструкция по сборке в исполняемый файл (.exe):
1. Установите PyInstaller:
   pip install pyinstaller
2. Выполните команду сборки:
   pyinstaller --noconsole --onefile virtual_aggregation.py
3. Исполняемый файл появится в папке dist/virtual_aggregation.exe
"""

import os
import re
import sys
import traceback
from datetime import datetime

# Guarded import of tkinter for headless testing support
try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
    HAS_TKINTER = True
except ImportError:
    HAS_TKINTER = False


def sanitize_filename(name):
    """
    Заменяет недопустимые символы в имени файла на символ подчеркивания.
    """
    cleaned = re.sub(r'[\\/*?:"<>|]', '_', name.strip())
    return cleaned or "set"


def read_codes(filepath):
    """
    Считывает строки из текстового файла с последовательной проверкой кодировок:
    utf-8-sig, utf-16, utf-8, cp1251.
    """
    encodings = ["utf-8-sig", "utf-16", "utf-8", "cp1251"]
    for enc in encodings:
        try:
            with open(filepath, "r", encoding=enc) as f:
                lines = [line.strip() for line in f if line.strip()]
            return lines
        except (UnicodeError, LookupError):
            continue
    raise ValueError(f"Не удалось прочитать файл {filepath} с использованием поддерживаемых кодировок.")


def perform_aggregation(parent_file, child_files, items_per_parent, confirm_callback=None):
    """
    Выполняет виртуальную агрегацию.

    :param parent_file: Путь к файлу с кодами наборов (родительские)
    :param child_files: Список путей к файлам с кодами вложений (дочерние)
    :param items_per_parent: Количество вложений на один набор (int)
    :param confirm_callback: Функция обратного вызова для подтверждения при нехватке кодов
    :return: Словарь с информацией о результатах (folder_path, total_created, actual_sets)
    """
    if items_per_parent <= 0:
        raise ValueError("Количество вложений должно быть больше нуля.")

    parent_codes = read_codes(parent_file)
    if not parent_codes:
        raise ValueError("Файл кодов наборов пуст.")

    child_codes = []
    for cf in child_files:
        child_codes.extend(read_codes(cf))

    if not child_codes:
        raise ValueError("Файлы кодов вложений пусты.")

    total_parents = len(parent_codes)
    needed_children = total_parents * items_per_parent

    actual_sets = total_parents
    if len(child_codes) < needed_children:
        available_sets = len(child_codes) // items_per_parent
        if available_sets == 0:
            raise ValueError(
                f"Недостаточно кодов вложений ({len(child_codes)}) "
                f"даже для одного набора по {items_per_parent} шт."
            )

        if confirm_callback:
            msg = (
                f"Недостаточно кодов вложений!\n\n"
                f"Требуется: {needed_children} (для {total_parents} наборов)\n"
                f"Имеется: {len(child_codes)}\n\n"
                f"Будет сформировано только {available_sets} наборов.\n"
                f"Продолжить?"
            )
            if not confirm_callback(msg):
                return None

        actual_sets = available_sets

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = f"aggregation_results_{timestamp}"
    os.makedirs(output_dir, exist_ok=True)

    created_files = []
    used_filenames = set()

    child_idx = 0
    for i in range(actual_sets):
        p_code = parent_codes[i]
        base_filename = sanitize_filename(p_code)

        filename = f"{base_filename}.txt"
        counter = 1
        while filename.lower() in used_filenames:
            filename = f"{base_filename}_{counter}.txt"
            counter += 1

        used_filenames.add(filename.lower())
        file_path = os.path.join(output_dir, filename)

        c_codes = child_codes[child_idx : child_idx + items_per_parent]
        child_idx += items_per_parent

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(p_code + "\n")
            for c in c_codes:
                f.write(c + "\n")

        created_files.append(file_path)

    return {
        "folder_path": os.path.abspath(output_dir),
        "total_created": len(created_files),
        "actual_sets": actual_sets
    }


if HAS_TKINTER:
    class AggregationApp:
        def __init__(self, root):
            self.root = root
            self.root.title("Виртуальная агрегация кодов маркировки")
            self.root.geometry("620x520")
            self.root.resizable(False, False)

            self.parent_file = ""
            self.child_files = []

            self.setup_ui()

        def setup_ui(self):
            # Header
            header_frame = tk.Frame(self.root, bg="#2c3e50", height=60)
            header_frame.pack(fill="x")
            header_label = tk.Label(
                header_frame,
                text="Модуль виртуальной агрегации",
                font=("Arial", 16, "bold"),
                fg="white",
                bg="#2c3e50"
            )
            header_label.pack(pady=15)

            main_frame = tk.Frame(self.root, padx=20, pady=15)
            main_frame.pack(fill="both", expand=True)

            # Step 1: Parent file
            lbl_parent = tk.Label(main_frame, text="1. Файл с кодами наборов (Родительские коды):", font=("Arial", 10, "bold"))
            lbl_parent.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 5))

            self.txt_parent = tk.Entry(main_frame, width=52, font=("Arial", 10))
            self.txt_parent.grid(row=1, column=0, padx=(0, 10), sticky="w")

            btn_browse_parent = tk.Button(main_frame, text="Обзор...", width=12, command=self.select_parent_file)
            btn_browse_parent.grid(row=1, column=1, sticky="w")

            # Step 2: Items per parent
            lbl_count = tk.Label(main_frame, text="2. Количество вложений в каждый набор:", font=("Arial", 10, "bold"))
            lbl_count.grid(row=2, column=0, columnspan=2, sticky="w", pady=(15, 5))

            self.spin_count = tk.Spinbox(main_frame, from_=1, to=1000, width=10, font=("Arial", 10))
            self.spin_count.delete(0, "end")
            self.spin_count.insert(0, "1")
            self.spin_count.grid(row=3, column=0, sticky="w")

            # Step 3: Child files
            lbl_child = tk.Label(main_frame, text="3. Файлы с кодами вложений (Содержимое):", font=("Arial", 10, "bold"))
            lbl_child.grid(row=4, column=0, columnspan=2, sticky="w", pady=(15, 5))

            self.lbl_child_summary = tk.Label(main_frame, text="Файлы не выбраны", fg="gray", font=("Arial", 9))
            self.lbl_child_summary.grid(row=5, column=0, sticky="w")

            btn_browse_child = tk.Button(main_frame, text="Выбрать файлы...", width=16, command=self.select_child_files)
            btn_browse_child.grid(row=5, column=1, sticky="w")

            # Listbox for child files
            self.lst_child = tk.Listbox(main_frame, width=68, height=6, font=("Arial", 9))
            self.lst_child.grid(row=6, column=0, columnspan=2, pady=(5, 15), sticky="w")

            # Execute button
            btn_run = tk.Button(
                main_frame,
                text="Сформировать агрегацию",
                font=("Arial", 11, "bold"),
                bg="#27ae60",
                fg="white",
                height=2,
                command=self.run_aggregation
            )
            btn_run.grid(row=7, column=0, columnspan=2, sticky="ew")

        def select_parent_file(self):
            filename = filedialog.askopenfilename(
                title="Выберите файл кодов наборов",
                filetypes=[("Текстовые файлы", "*.txt"), ("Все файлы", "*.*")]
            )
            if filename:
                self.parent_file = filename
                self.txt_parent.delete(0, tk.END)
                self.txt_parent.insert(0, filename)

        def select_child_files(self):
            filenames = filedialog.askopenfilenames(
                title="Выберите файлы кодов вложений",
                filetypes=[("Текстовые файлы", "*.txt"), ("Все файлы", "*.*")]
            )
            if filenames:
                self.child_files = list(filenames)
                self.lst_child.delete(0, tk.END)
                for f in self.child_files:
                    self.lst_child.insert(tk.END, os.path.basename(f))
                self.lbl_child_summary.config(
                    text=f"Выбрано файлов: {len(self.child_files)}",
                    fg="green"
                )

        def run_aggregation(self):
            try:
                parent_path = self.txt_parent.get().strip()
                if not parent_path:
                    messagebox.showerror("Ошибка", "Пожалуйста, выберите файл кодов наборов.")
                    return

                if not self.child_files:
                    messagebox.showerror("Ошибка", "Пожалуйста, выберите хотя бы один файл кодов вложений.")
                    return

                try:
                    items_per_parent = int(self.spin_count.get().strip())
                except ValueError:
                    messagebox.showerror("Ошибка", "Укажите корректное числовое значение для количества вложений.")
                    return

                def confirm(msg):
                    return messagebox.askyesno("Подтверждение", msg)

                result = perform_aggregation(
                    parent_file=parent_path,
                    child_files=self.child_files,
                    items_per_parent=items_per_parent,
                    confirm_callback=confirm
                )

                if result is not None:
                    messagebox.showinfo(
                        "Успех",
                        f"Виртуальная агрегация успешно завершена!\n\n"
                        f"Создано файлов: {result['total_created']}\n"
                        f"Папка с результатами:\n{result['folder_path']}"
                    )

            except Exception as e:
                err_msg = f"Произошла ошибка при выполнении агрегации:\n\n{str(e)}\n\nПодробности:\n{traceback.format_exc()}"
                messagebox.showerror("Ошибка выполнения", err_msg)


def main():
    if not HAS_TKINTER:
        print("Ошибка: Модуль tkinter недоступен в данной среде.")
        sys.exit(1)

    root = tk.Tk()
    app = AggregationApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
