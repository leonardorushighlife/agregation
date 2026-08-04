"""
Инструкция по сборке в исполняемый файл EXE:
1. Установите PyInstaller: pip install pyinstaller
2. Выполните команду для сборки:
   pyinstaller --noconsole --onefile virtual_aggregation.py
3. Готовый файл virtual_aggregation.exe появится в папке dist.

Этот скрипт поддерживает работу на операционных системах Windows 8, 10, 11.
"""

import os
import sys
import datetime
import traceback

# Ленивый / условный импорт tkinter для headless выполнения unit-тестов
try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
except ImportError:
    tk = None

def read_codes(filepath):
    """
    Читает коды маркировки из файла, пробуя несколько кодировок:
    UTF-8-SIG, UTF-16, UTF-8, CP1251.
    Обрабатывает UnicodeError и LookupError.
    """
    encodings = ["utf-8-sig", "utf-16", "utf-8", "cp1251"]
    for enc in encodings:
        try:
            with open(filepath, "r", encoding=enc) as f:
                content = f.read()
            # Разделяем на строки, очищаем и убираем пустые
            codes = [line.strip() for line in content.splitlines() if line.strip()]
            return codes
        except (UnicodeError, LookupError):
            continue
    raise ValueError(f"Не удалось прочитать файл {filepath} с использованием поддерживаемых кодировок.")

def sanitize_filename(filename):
    """
    Очищает имя файла от недопустимых символов Windows.
    """
    for char in ['\\', '/', ':', '*', '?', '"', '<', '>', '|']:
        filename = filename.replace(char, '_')
    return filename

def perform_aggregation(parent_file, child_files, count_per_parent, confirm_callback=None, output_dir=None):
    """
    Выполняет виртуальную агрегацию кодов маркировки.

    parent_file: путь к файлу с кодами наборов (родительскими).
    child_files: список путей к файлам с кодами содержимого (дочерними).
    count_per_parent: количество вложений в один набор.
    confirm_callback: callback(available, required) для подтверждения частичной агрегации.
                      Должен возвращать True для продолжения, False для отмены.
    output_dir: опциональная директория, в которой будет создана папка результатов.
    """
    if count_per_parent <= 0:
        raise ValueError("Количество вложений должно быть больше нуля.")

    parent_codes = read_codes(parent_file)
    child_codes = []
    for cf in child_files:
        child_codes.extend(read_codes(cf))

    total_parents = len(parent_codes)
    total_children = len(child_codes)
    required_children = total_parents * count_per_parent

    if total_children < required_children:
        if confirm_callback:
            if not confirm_callback(total_children, required_children):
                return None
        else:
            # Если коллбек не задан, по умолчанию продолжаем
            pass

    # Расчет actual_sets на основе минимально доступных кодов, чтобы избежать IndexError
    actual_sets = min(total_parents, total_children // count_per_parent)

    if actual_sets == 0:
        raise ValueError("Недостаточно кодов содержимого для создания хотя бы одного набора.")

    # Создание новой папки с временной меткой
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    folder_name = f"aggregation_results_{timestamp}"
    if output_dir:
        target_dir = os.path.join(output_dir, folder_name)
    else:
        target_dir = folder_name

    os.makedirs(target_dir, exist_ok=True)

    created_files = []
    used_filenames = set()

    for i in range(actual_sets):
        parent_code = parent_codes[i]
        sanitized = sanitize_filename(parent_code)

        base_name = sanitized
        suffix_counter = 1
        candidate_name = f"{base_name}.txt"

        while candidate_name.lower() in used_filenames:
            candidate_name = f"{base_name}_{suffix_counter}.txt"
            suffix_counter += 1

        used_filenames.add(candidate_name.lower())
        file_path = os.path.join(target_dir, candidate_name)

        start_idx = i * count_per_parent
        end_idx = start_idx + count_per_parent
        batch_children = child_codes[start_idx:end_idx]

        # Запись в кодировке UTF-8 без BOM
        with open(file_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(parent_code + "\n")
            for cc in batch_children:
                f.write(cc + "\n")

        created_files.append(file_path)

    return target_dir, created_files


# --- КЛАСС ГРАФИЧЕСКОГО ИНТЕРФЕЙСА (GUI) ---

class VirtualAggregationApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Виртуальная Агрегация")
        self.root.geometry("680x520")
        self.root.resizable(True, True)

        self.parent_file_path = ""
        self.child_file_paths = []

        self.create_widgets()

    def create_widgets(self):
        # Главный фрейм с отступами
        main_frame = ttk.Frame(self.root, padding="15 15 15 15")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 1. Секция выбора файлов родительских кодов
        parent_lf = ttk.LabelFrame(main_frame, text=" 1. Коды маркировки набора (Родительский файл) ", padding="10")
        parent_lf.pack(fill=tk.X, pady=5)

        self.parent_btn = ttk.Button(parent_lf, text="Выбрать файл...", command=self.select_parent_file)
        self.parent_btn.pack(side=tk.LEFT, padx=5)

        self.parent_label = ttk.Label(parent_lf, text="Файл не выбран", foreground="gray")
        self.parent_label.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

        # 2. Секция выбора количества вложений
        count_lf = ttk.LabelFrame(main_frame, text=" 2. Параметры набора ", padding="10")
        count_lf.pack(fill=tk.X, pady=5)

        ttk.Label(count_lf, text="Количество вложений в один набор:").pack(side=tk.LEFT, padx=5)
        self.count_var = tk.StringVar(value="4")
        self.count_spin = ttk.Spinbox(count_lf, from_=1, to=1000, textvariable=self.count_var, width=10)
        self.count_spin.pack(side=tk.LEFT, padx=5)

        # 3. Секция выбора файлов дочерних кодов
        child_lf = ttk.LabelFrame(main_frame, text=" 3. Коды маркировки содержимого (Дочерние файлы) ", padding="10")
        child_lf.pack(fill=tk.BOTH, expand=True, pady=5)

        btn_bar = ttk.Frame(child_lf)
        btn_bar.pack(fill=tk.X, pady=5)

        self.child_btn = ttk.Button(btn_bar, text="Добавить файлы...", command=self.add_child_files)
        self.child_btn.pack(side=tk.LEFT, padx=5)

        self.clear_child_btn = ttk.Button(btn_bar, text="Очистить список", command=self.clear_child_files)
        self.clear_child_btn.pack(side=tk.LEFT, padx=5)

        # Список выбранных дочерних файлов
        self.child_listbox = tk.Listbox(child_lf, selectmode=tk.MULTIPLE, height=6)
        self.child_listbox.pack(fill=tk.BOTH, expand=True, side=tk.LEFT, padx=5)

        scrollbar = ttk.Scrollbar(child_lf, orient=tk.VERTICAL, command=self.child_listbox.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.child_listbox.config(yscrollcommand=scrollbar.set)

        # 4. Кнопка запуска процесса
        self.action_btn = ttk.Button(main_frame, text="Выполнить агрегацию", style="Accent.TButton", command=self.run_aggregation)
        self.action_btn.pack(pady=15, fill=tk.X, side=tk.BOTTOM)

    def select_parent_file(self):
        file_path = filedialog.askopenfilename(
            title="Выберите файл с кодами маркировки наборов",
            filetypes=[("Текстовые файлы (*.txt)", "*.txt"), ("Все файлы (*.*)", "*.*")]
        )
        if file_path:
            self.parent_file_path = file_path
            self.parent_label.config(text=os.path.basename(file_path), foreground="black")

    def add_child_files(self):
        file_paths = filedialog.askopenfilenames(
            title="Выберите файлы с кодами вложений",
            filetypes=[("Текстовые файлы (*.txt)", "*.txt"), ("Все файлы (*.*)", "*.*")]
        )
        if file_paths:
            for fp in file_paths:
                if fp not in self.child_file_paths:
                    self.child_file_paths.append(fp)
                    self.child_listbox.insert(tk.END, os.path.basename(fp))

    def clear_child_files(self):
        self.child_file_paths.clear()
        self.child_listbox.delete(0, tk.END)

    def confirm_partial_callback(self, available, required):
        return messagebox.askyesno(
            "Подтверждение",
            f"Внимание: Доступно кодов содержимого: {available}, а требуется для полной агрегации: {required}.\n\n"
            f"Будет выполнена частичная агрегация для полностью заполненных наборов.\n"
            f"Продолжить?"
        )

    def run_aggregation(self):
        if not self.parent_file_path:
            messagebox.showerror("Ошибка", "Пожалуйста, выберите файл с кодами наборов (родительскими).")
            return

        if not self.child_file_paths:
            messagebox.showerror("Ошибка", "Пожалуйста, добавьте хотя бы один файл с кодами содержимого (дочерними).")
            return

        try:
            count_per_parent = int(self.count_var.get())
            if count_per_parent <= 0:
                raise ValueError()
        except ValueError:
            messagebox.showerror("Ошибка", "Количество вложений должно быть целым положительным числом.")
            return

        def global_exception_handler(ex_type, ex_value, ex_traceback):
            """
            Обработчик исключений, выводящий полный стек ошибки в messagebox.
            """
            tb_lines = traceback.format_exception(ex_type, ex_value, ex_traceback)
            tb_text = "".join(tb_lines)
            messagebox.showerror(
                "Критическая ошибка",
                f"Произошла непредвиденная ошибка:\n\n{tb_text}"
            )

        # Установка глобального обработчика исключений для GUI сессии
        sys.excepthook = global_exception_handler

        try:
            result = perform_aggregation(
                parent_file=self.parent_file_path,
                child_files=self.child_file_paths,
                count_per_parent=count_per_parent,
                confirm_callback=self.confirm_partial_callback
            )

            if result is None:
                messagebox.showinfo("Информация", "Агрегация отменена пользователем.")
                return

            target_dir, created_files = result
            messagebox.showinfo(
                "Успех",
                f"Агрегация завершена успешно!\n\n"
                f"Создано файлов: {len(created_files)}\n"
                f"Папка с результатами:\n{os.path.abspath(target_dir)}"
            )

        except Exception as e:
            tb_text = traceback.format_exc()
            messagebox.showerror(
                "Ошибка выполнения",
                f"Не удалось выполнить агрегацию:\n\n{str(e)}\n\nДетали:\n{tb_text}"
            )


def main():
    if tk is None:
        print("Ошибка: Tkinter не поддерживается или не установлен.")
        sys.exit(1)

    root = tk.Tk()

    # Стилизация ttk элементов
    style = ttk.Style()
    style.theme_use("clam")

    app = VirtualAggregationApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
