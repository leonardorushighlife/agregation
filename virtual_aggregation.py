"""
Скрипт для виртуальной агрегации кодов маркировки.

Инструкция по сборке в EXE файл через PyInstaller:
1. Установите PyInstaller, если он еще не установлен:
   pip install pyinstaller

2. Выполните команду для сборки однофайлового приложения без консольного окна:
   pyinstaller --noconsole --onefile virtual_aggregation.py

3. Готовый исполняемый файл `virtual_aggregation.exe` будет находиться в папке `dist/`.
"""

import os
import sys
import traceback
from datetime import datetime

# Функция очистки имени файла от недупустимых символов OS
def sanitize_filename(filename):
    invalid_chars = ['\\', '/', ':', '*', '?', '"', '<', '>', '|']
    for char in invalid_chars:
        filename = filename.replace(char, '_')
    return filename.strip()

# Чтение кодов из файла с поддержкой различных кодировок
def read_codes(file_path):
    encodings = ['utf-8-sig', 'utf-16', 'utf-8', 'cp1251']
    for enc in encodings:
        try:
            with open(file_path, 'r', encoding=enc) as f:
                lines = [line.strip() for line in f if line.strip()]
            return lines
        except (UnicodeError, LookupError):
            continue
    # Если ни одна кодировка не подошла
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        return [line.strip() for line in f if line.strip()]

# Основная логика виртуальной агрегации
def perform_aggregation(parent_file, child_files, count_per_parent, output_dir=None, confirm_callback=None):
    if not parent_file:
        raise ValueError("Не выбран файл с кодами наборов (родительские коды).")
    if not child_files:
        raise ValueError("Не выбраны файлы с кодами вложений (дочерние коды).")
    if count_per_parent <= 0:
        raise ValueError("Количество вложений должно быть больше 0.")

    parents = read_codes(parent_file)
    if not parents:
        raise ValueError("Файл с родительскими кодами пуст или не содержит корректных строк.")

    all_children = []
    for cf in child_files:
        all_children.extend(read_codes(cf))

    if not all_children:
        raise ValueError("Выбранные файлы вложений не содержат корректных кодов.")

    required_children = len(parents) * count_per_parent
    actual_sets = min(len(parents), len(all_children) // count_per_parent)

    if len(all_children) < required_children:
        msg = (
            f"Внимание! Недостаточно кодов вложений для всех наборов.\n\n"
            f"Родительских кодов: {len(parents)}\n"
            f"Требуется вложений: {required_children} ({len(parents)} x {count_per_parent})\n"
            f"Доступно вложений: {len(all_children)}\n"
            f"Будет создано полных наборов: {actual_sets}\n\n"
            f"Продолжить с частичным результатом?"
        )
        if confirm_callback:
            if not confirm_callback(msg):
                return None

    if actual_sets == 0:
        raise ValueError("Недостаточно кодов вложений даже для создания одного полного набора.")

    if not output_dir:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = os.path.join(os.getcwd(), f"aggregation_results_{timestamp}")

    os.makedirs(output_dir, exist_ok=True)

    created_files_count = 0
    children_used = 0

    for i in range(actual_sets):
        parent_code = parents[i]
        start_idx = i * count_per_parent
        end_idx = start_idx + count_per_parent
        current_children = all_children[start_idx:end_idx]

        base_name = sanitize_filename(parent_code)
        if not base_name:
            base_name = f"set_{i+1}"

        out_filepath = os.path.join(output_dir, f"{base_name}.txt")
        suffix = 1
        while os.path.exists(out_filepath):
            out_filepath = os.path.join(output_dir, f"{base_name}_{suffix}.txt")
            suffix += 1

        with open(out_filepath, 'w', encoding='utf-8') as out_file:
            out_file.write(parent_code + '\n')
            for child in current_children:
                out_file.write(child + '\n')

        created_files_count += 1
        children_used += len(current_children)

    return {
        "output_dir": output_dir,
        "sets_created": created_files_count,
        "total_parents": len(parents),
        "total_children_used": children_used,
        "total_children_available": len(all_children)
    }

class VirtualAggregationGUI:
    def __init__(self, root):
        import tkinter as tk
        from tkinter import ttk, filedialog, messagebox

        self.root = root
        self.root.title("Виртуальная Агрегация Наборов")
        self.root.geometry("650x450")
        self.root.minsize(600, 400)

        self.parent_file = ""
        self.child_files = []

        self.setup_ui(tk, ttk, filedialog, messagebox)

    def setup_ui(self, tk, ttk, filedialog, messagebox):
        self.tk = tk
        self.ttk = ttk
        self.filedialog = filedialog
        self.messagebox = messagebox

        padding = {'padx': 10, 'pady': 5}

        # Выбор родительского файла
        parent_frame = ttk.LabelFrame(self.root, text="1. Файл с кодами маркировки наборов (Родительские коды)")
        parent_frame.pack(fill="x", **padding)

        self.btn_select_parent = ttk.Button(parent_frame, text="Выбрать файл", command=self.select_parent_file)
        self.btn_select_parent.pack(side="left", **padding)

        self.lbl_parent_path = ttk.Label(parent_frame, text="Файл не выбран", wraplength=450)
        self.lbl_parent_path.pack(side="left", fill="x", expand=True, **padding)

        # Выбор количества вложений
        count_frame = ttk.LabelFrame(self.root, text="2. Параметры агрегации")
        count_frame.pack(fill="x", **padding)

        ttk.Label(count_frame, text="Количество вложений в один набор:").pack(side="left", **padding)

        self.spn_count = ttk.Spinbox(count_frame, from_=1, to=1000, width=10)
        self.spn_count.set(4)
        self.spn_count.pack(side="left", **padding)

        # Выбор дочерних файлов
        child_frame = ttk.LabelFrame(self.root, text="3. Файлы с кодами маркировки вложений (Дочерние коды)")
        child_frame.pack(fill="both", expand=True, **padding)

        btn_child_frame = ttk.Frame(child_frame)
        btn_child_frame.pack(fill="x", **padding)

        self.btn_select_children = ttk.Button(btn_child_frame, text="Добавить файлы", command=self.select_child_files)
        self.btn_select_children.pack(side="left", **padding)

        self.btn_clear_children = ttk.Button(btn_child_frame, text="Очистить список", command=self.clear_child_files)
        self.btn_clear_children.pack(side="left", **padding)

        self.lbl_child_summary = ttk.Label(btn_child_frame, text="Выбрано файлов: 0")
        self.lbl_child_summary.pack(side="right", **padding)

        # Список выбранных дочерних файлов
        list_frame = ttk.Frame(child_frame)
        list_frame.pack(fill="both", expand=True, **padding)

        self.lst_children = tk.Listbox(list_frame, selectmode=tk.EXTENDED)
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.lst_children.yview)
        self.lst_children.configure(yscrollcommand=scrollbar.set)

        self.lst_children.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Кнопка запуска
        action_frame = ttk.Frame(self.root)
        action_frame.pack(fill="x", **padding)

        self.btn_run = ttk.Button(action_frame, text="Выполнить агрегацию", command=self.run_aggregation)
        self.btn_run.pack(fill="x", ipady=5)

    def select_parent_file(self):
        filename = self.filedialog.askopenfilename(
            title="Выберите файл с кодами наборов",
            filetypes=[("Текстовые файлы", "*.txt"), ("Все файлы", "*.*")]
        )
        if filename:
            self.parent_file = filename
            self.lbl_parent_path.config(text=os.path.basename(filename))

    def select_child_files(self):
        filenames = self.filedialog.askopenfilenames(
            title="Выберите файлы с кодами вложений",
            filetypes=[("Текстовые файлы", "*.txt"), ("Все файлы", "*.*")]
        )
        if filenames:
            for fn in filenames:
                if fn not in self.child_files:
                    self.child_files.append(fn)
                    self.lst_children.insert(self.tk.END, os.path.basename(fn))
            self.lbl_child_summary.config(text=f"Выбрано файлов: {len(self.child_files)}")

    def clear_child_files(self):
        self.child_files.clear()
        self.lst_children.delete(0, self.tk.END)
        self.lbl_child_summary.config(text="Выбрано файлов: 0")

    def run_aggregation(self):
        try:
            count = int(self.spn_count.get())
        except ValueError:
            self.messagebox.showerror("Ошибка", "Количество вложений должно быть целым числом.")
            return

        def ask_confirm(msg):
            return self.messagebox.askyesno("Подтверждение", msg)

        try:
            res = perform_aggregation(
                parent_file=self.parent_file,
                child_files=self.child_files,
                count_per_parent=count,
                confirm_callback=ask_confirm
            )

            if res is None:
                self.messagebox.showinfo("Отмена", "Операция агрегации была отменена пользователем.")
                return

            msg = (
                f"Виртуальная агрегация успешно завершена!\n\n"
                f"Создано файлов наборов: {res['sets_created']}\n"
                f"Использовано вложений: {res['total_children_used']} из {res['total_children_available']}\n\n"
                f"Результаты сохранены в папке:\n{res['output_dir']}"
            )
            self.messagebox.showinfo("Успех", msg)

        except Exception as e:
            tb = traceback.format_exc()
            self.messagebox.showerror("Ошибка агрегации", f"{str(e)}\n\nПодробности:\n{tb}")

def global_excepthook(exctype, value, tb):
    tb_str = "".join(traceback.format_exception(exctype, value, tb))
    try:
        from tkinter import messagebox
        messagebox.showerror("Критическая ошибка", f"Произошла непредвиденная ошибка:\n{value}\n\n{tb_str}")
    except Exception:
        print(f"Критическая ошибка: {value}\n{tb_str}", file=sys.stderr)

def main():
    sys.excepthook = global_excepthook
    import tkinter as tk
    root = tk.Tk()
    app = VirtualAggregationGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()
