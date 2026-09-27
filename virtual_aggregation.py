"""
Скрипт для виртуальной агрегации кодов маркировки.

Инструкция по сборке в отдельный исполняемый файл (EXE):
1. Установите PyInstaller, если он еще не установлен:
   pip install pyinstaller
2. Выполните команду сборки в консоли:
   pyinstaller --noconsole --onefile virtual_aggregation.py
3. Готовый файл virtual_aggregation.exe будет создан в папке dist/
"""

import os
import sys
import re
import traceback
from datetime import datetime

# Функция для чтения кодов маркировки из файла с поддержкой различных кодировок
def read_codes(filepath):
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

    lines = content.splitlines()
    codes = [line.strip() for line in lines if line.strip()]
    return codes


def sanitize_filename(name):
    # Замена недопустимых символов для имен файлов в ОС Windows
    return re.sub(r'[\\/:*?"<>|]', '_', name)


def perform_aggregation(parent_file, child_files, items_per_parent, confirm_partial_callback=None):
    if items_per_parent <= 0:
        raise ValueError("Количество вложений должно быть больше 0.")

    parent_codes = read_codes(parent_file)
    if not parent_codes:
        raise ValueError("Файл с кодами наборов пуст.")

    child_codes = []
    for c_file in child_files:
        child_codes.extend(read_codes(c_file))

    if not child_codes:
        raise ValueError("Файлы с кодами вложений пусты.")

    total_parents = len(parent_codes)
    total_children = len(child_codes)
    required_children = total_parents * items_per_parent

    actual_sets = total_parents
    if total_children < required_children:
        possible_sets = total_children // items_per_parent
        if possible_sets == 0:
            raise ValueError(
                f"Недостаточно кодов вложений ({total_children}) даже для одного набора (требуется {items_per_parent})."
            )

        msg = (
            f"Внимание: Недостаточно кодов вложений!\n"
            f"Кодов наборов: {total_parents}\n"
            f"Требуется кодов вложений: {required_children} ({items_per_parent} на набор)\n"
            f"Доступно кодов вложений: {total_children}\n\n"
            f"Будет сформировано только {possible_sets} полных наборов из {total_parents}.\n"
            f"Продолжить?"
        )

        if confirm_partial_callback is not None:
            if not confirm_partial_callback(msg):
                return None
        actual_sets = possible_sets

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = f"aggregation_results_{timestamp}"
    os.makedirs(output_dir, exist_ok=True)

    used_filenames = {}
    created_files = []

    for i in range(actual_sets):
        parent_code = parent_codes[i]
        start_idx = i * items_per_parent
        end_idx = start_idx + items_per_parent
        current_children = child_codes[start_idx:end_idx]

        base_filename = sanitize_filename(parent_code)
        if not base_filename:
            base_filename = f"set_{i+1}"

        if base_filename in used_filenames:
            used_filenames[base_filename] += 1
            filename = f"{base_filename}_{used_filenames[base_filename]}.txt"
        else:
            used_filenames[base_filename] = 0
            filename = f"{base_filename}.txt"

        file_path = os.path.join(output_dir, filename)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(parent_code + '\n')
            for child in current_children:
                f.write(child + '\n')

        created_files.append(file_path)

    return {
        "output_dir": output_dir,
        "sets_count": len(created_files),
        "created_files": created_files
    }


class VirtualAggregationApp:
    def __init__(self, root):
        import tkinter as tk
        from tkinter import ttk, filedialog, messagebox

        self.tk = tk
        self.filedialog = filedialog
        self.messagebox = messagebox

        self.root = root
        self.root.title("Виртуальная Агрегация Кодов Маркировки")
        self.root.geometry("620x450")
        self.root.resizable(False, False)

        self.parent_file = ""
        self.child_files = []

        self._create_widgets()

    def _create_widgets(self):
        tk = self.tk

        # Заголовок
        title_label = tk.Label(
            self.root,
            text="Виртуальная Агрегация Кодов Маркировки",
            font=("Arial", 14, "bold")
        )
        title_label.pack(pady=15)

        # Фрейм выбора файла набора
        f_parent = tk.LabelFrame(self.root, text=" 1. Файл с кодами наборов (родительские коды) ", font=("Arial", 10, "bold"), padx=10, pady=10)
        f_parent.pack(fill="x", padx=20, pady=5)

        self.btn_parent = tk.Button(f_parent, text="Выбрать файл...", command=self.select_parent_file, width=20)
        self.btn_parent.pack(side="left", padx=5)

        self.lbl_parent = tk.Label(f_parent, text="Файл не выбран", fg="gray", anchor="w")
        self.lbl_parent.pack(side="left", fill="x", expand=True, padx=5)

        # Фрейм количества вложений
        f_count = tk.LabelFrame(self.root, text=" 2. Количество вложений в один набор ", font=("Arial", 10, "bold"), padx=10, pady=10)
        f_count.pack(fill="x", padx=20, pady=5)

        tk.Label(f_count, text="Вложений на набор:").pack(side="left", padx=5)
        self.spin_count = tk.Spinbox(f_count, from_=1, to=1000, width=10, font=("Arial", 10))
        self.spin_count.delete(0, "end")
        self.spin_count.insert(0, "4")
        self.spin_count.pack(side="left", padx=5)

        # Фрейм выбора файлов вложений
        f_child = tk.LabelFrame(self.root, text=" 3. Файлы с кодами вложений (дочерние коды) ", font=("Arial", 10, "bold"), padx=10, pady=10)
        f_child.pack(fill="x", padx=20, pady=5)

        self.btn_child = tk.Button(f_child, text="Выбрать файлы...", command=self.select_child_files, width=20)
        self.btn_child.pack(side="left", padx=5)

        self.lbl_child = tk.Label(f_child, text="Файлы не выбраны", fg="gray", anchor="w")
        self.lbl_child.pack(side="left", fill="x", expand=True, padx=5)

        # Кнопка запуска
        self.btn_run = tk.Button(
            self.root,
            text="Сформировать наборы (Агрегацию)",
            font=("Arial", 12, "bold"),
            bg="#4CAF50",
            fg="white",
            command=self.run_aggregation,
            height=2
        )
        self.btn_run.pack(fill="x", padx=20, pady=20)

    def select_parent_file(self):
        filename = self.filedialog.askopenfilename(
            title="Выберите файл с кодами наборов",
            filetypes=[("Текстовые файлы", "*.txt"), ("Все файлы", "*.*")]
        )
        if filename:
            self.parent_file = filename
            self.lbl_parent.config(text=os.path.basename(filename), fg="black")

    def select_child_files(self):
        filenames = self.filedialog.askopenfilenames(
            title="Выберите файлы с кодами вложений",
            filetypes=[("Текстовые файлы", "*.txt"), ("Все файлы", "*.*")]
        )
        if filenames:
            self.child_files = list(filenames)
            count = len(self.child_files)
            if count == 1:
                text = os.path.basename(self.child_files[0])
            else:
                text = f"Выбрано файлов: {count}"
            self.lbl_child.config(text=text, fg="black")

    def run_aggregation(self):
        if not self.parent_file:
            self.messagebox.showerror("Ошибка", "Пожалуйста, выберите файл с кодами наборов.")
            return

        if not self.child_files:
            self.messagebox.showerror("Ошибка", "Пожалуйста, выберите хотя бы один файл с кодами вложений.")
            return

        try:
            items_per_parent = int(self.spin_count.get())
        except ValueError:
            self.messagebox.showerror("Ошибка", "Введите корректное число для количества вложений.")
            return

        def confirm_cb(msg):
            return self.messagebox.askyesno("Подтверждение", msg)

        try:
            result = perform_aggregation(
                self.parent_file,
                self.child_files,
                items_per_parent,
                confirm_partial_callback=confirm_cb
            )

            if result is None:
                self.messagebox.showinfo("Отмена", "Операция отменена пользователем.")
                return

            msg = (
                f"Виртуальная агрегация успешно завершена!\n\n"
                f"Создано наборов (файлов): {result['sets_count']}\n"
                f"Результаты сохранены в папке:\n{os.path.abspath(result['output_dir'])}"
            )
            self.messagebox.showinfo("Успех", msg)

        except Exception as e:
            tb = traceback.format_exc()
            self.messagebox.showerror("Ошибка при агрегации", f"{str(e)}\n\nПодробности:\n{tb}")


def main():
    import tkinter as tk

    def show_exception(exc_type, exc_value, exc_traceback):
        from tkinter import messagebox
        tb = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        messagebox.showerror("Критическая ошибка", f"Произошла непредвиденная ошибка:\n{exc_value}\n\n{tb}")

    root = tk.Tk()
    root.report_callback_exception = show_exception
    app = VirtualAggregationApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
