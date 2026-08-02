"""
Виртуальная агрегация кодов маркировки.
Скрипт группирует коды маркировки содержимого (вложений) по кодам маркировки наборов (родительских).

Инструкция по сборке в исполняемый файл (EXE):
1. Установите PyInstaller, если он еще не установлен:
   pip install pyinstaller
2. Выполните команду для сборки скрипта:
   pyinstaller --noconsole --onefile virtual_aggregation.py
3. Исполняемый файл появится в папке 'dist'.
"""

import os
import sys
import re
import time
import traceback

# Ленивый / защищенный импорт tkinter для тестирования в headless среде
try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
except (ImportError, ModuleNotFoundError):
    tk = None
    filedialog = None
    messagebox = None
    ttk = None

def sanitize_filename(name: str) -> str:
    """
    Очищает имя файла от символов, недопустимых в Windows, заменяя их на символ подчеркивания.
    Недопустимые символы: \\ / : * ? " < > |
    """
    invalid_chars = r'[\\/:*?"<>|]'
    return re.sub(invalid_chars, "_", name)

def read_codes(filepath: str) -> list[str]:
    """
    Читает коды из файла, последовательно пробуя кодировки UTF-8-SIG, UTF-16, UTF-8, CP1251.
    Перехватывает UnicodeError и LookupError. Возвращает список непустых очищенных строк.
    """
    encodings = ["utf-8-sig", "utf-16", "utf-8", "cp1251"]
    codes = []
    success = False

    for enc in encodings:
        try:
            with open(filepath, "r", encoding=enc) as f:
                content = f.read()
                # Разделяем на строки и очищаем от пробельных символов
                lines = [line.strip() for line in content.splitlines() if line.strip()]
                codes = lines
                success = True
                break
        except (UnicodeError, LookupError):
            continue

    if not success:
        raise ValueError(f"Не удалось прочитать файл {filepath} в поддерживаемых кодировках (UTF-8, UTF-16, CP1251).")
    return codes

def perform_aggregation(parent_codes: list[str], child_codes: list[str], count_per_parent: int, output_dir: str, confirm_callback=None) -> tuple[int, list[str]]:
    """
    Выполняет виртуальную агрегацию кодов.
    Берет по count_per_parent дочерних кодов для каждого родительского.
    Если кодов вложений меньше необходимого, запрашивает подтверждение через confirm_callback.
    Возвращает кортеж (количество успешно созданных наборов, список созданных файлов).
    """
    if count_per_parent <= 0:
        raise ValueError("Количество вложений должно быть больше нуля.")

    required_children = len(parent_codes) * count_per_parent
    actual_children = len(child_codes)

    if actual_children < required_children:
        if confirm_callback:
            if not confirm_callback(actual_children, required_children):
                return 0, []
        else:
            raise ValueError("Недостаточно кодов вложений для агрегации.")

    # Вычисляем количество наборов на основе деления минимального кол-ва кодов на количество вложений
    actual_sets = min(len(parent_codes), len(child_codes) // count_per_parent)

    if actual_sets == 0:
        return 0, []

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    created_files = []
    used_filenames = set()

    for i in range(actual_sets):
        parent_code = parent_codes[i]
        sanitized_parent = sanitize_filename(parent_code)

        filename = f"{sanitized_parent}.txt"
        filepath = os.path.join(output_dir, filename)

        # Обработка коллизий имен файлов путем добавления числового суффикса
        suffix = 1
        while filepath.lower() in used_filenames or os.path.exists(filepath):
            filename = f"{sanitized_parent}_{suffix}.txt"
            filepath = os.path.join(output_dir, filename)
            suffix += 1

        used_filenames.add(filepath.lower())

        # Получаем срез дочерних кодов
        start_idx = i * count_per_parent
        end_idx = start_idx + count_per_parent
        set_children = child_codes[start_idx:end_idx]

        # Запись набора в формате UTF-8 без BOM с символом перевода строки \n
        with open(filepath, "w", encoding="utf-8", newline="\n") as f:
            f.write(parent_code + "\n")
            for child in set_children:
                f.write(child + "\n")

        created_files.append(filepath)

    return actual_sets, created_files

class VirtualAggregationApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Виртуальная Агрегация Кодов Маркировки")
        self.root.geometry("700x550")
        self.root.minsize(600, 450)

        self.parent_filepath = ""
        self.parent_codes = []
        self.child_filepaths = []
        self.child_codes = []

        self.create_widgets()

    def create_widgets(self):
        # Главный контейнер с отступами
        main_frame = ttk.Frame(self.root, padding="15")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 1. Секция выбора файла наборов (родительских кодов)
        parent_group = ttk.LabelFrame(main_frame, text=" 1. Выбор кодов набора (родительские коды) ", padding="10")
        parent_group.pack(fill=tk.X, pady=(0, 10))

        self.btn_select_parent = ttk.Button(parent_group, text="Выбрать файл наборов...", command=self.select_parent_file)
        self.btn_select_parent.pack(side=tk.LEFT, padx=(0, 10))

        self.lbl_parent_info = ttk.Label(parent_group, text="Файл не выбран", wraplength=450)
        self.lbl_parent_info.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # 2. Секция выбора количества вложений
        count_group = ttk.LabelFrame(main_frame, text=" 2. Количество вложений на один набор ", padding="10")
        count_group.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(count_group, text="Вложений в наборе (штук):").pack(side=tk.LEFT, padx=(0, 10))

        self.var_count = tk.IntVar(value=10)
        self.spin_count = ttk.Spinbox(count_group, from_=1, to=100000, textvariable=self.var_count, width=10)
        self.spin_count.pack(side=tk.LEFT)

        # 3. Секция выбора файлов содержимого (дочерних кодов)
        child_group = ttk.LabelFrame(main_frame, text=" 3. Выбор файлов содержимого (коды вложений) ", padding="10")
        child_group.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        btn_frame = ttk.Frame(child_group)
        btn_frame.pack(fill=tk.X, pady=(0, 5))

        self.btn_select_children = ttk.Button(btn_frame, text="Выбрать файлы вложений...", command=self.select_child_files)
        self.btn_select_children.pack(side=tk.LEFT, padx=(0, 10))

        self.btn_clear_children = ttk.Button(btn_frame, text="Очистить список", command=self.clear_child_files)
        self.btn_clear_children.pack(side=tk.LEFT)

        # Список выбранных файлов
        list_frame = ttk.Frame(child_group)
        list_frame.pack(fill=tk.BOTH, expand=True)

        self.lst_children = tk.Listbox(list_frame, height=5)
        self.lst_children.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.lst_children.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.lst_children.config(yscrollcommand=scrollbar.set)

        self.lbl_child_info = ttk.Label(child_group, text="Всего выбрано файлов: 0 | Общее кол-во кодов вложений: 0")
        self.lbl_child_info.pack(anchor=tk.W, pady=(5, 0))

        # 4. Кнопка запуска и статус
        actions_frame = ttk.Frame(main_frame)
        actions_frame.pack(fill=tk.X, pady=(5, 0))

        self.btn_run = ttk.Button(actions_frame, text="Выполнить Агрегацию", command=self.run_aggregation, style="Accent.TButton")
        self.btn_run.pack(fill=tk.X, ipady=5)

        # Настройка стиля для яркой кнопки
        style = ttk.Style()
        style.configure("Accent.TButton", font=("Helvetica", 10, "bold"))

    def select_parent_file(self):
        filepath = filedialog.askopenfilename(
            title="Выбрать файл кодов маркировки наборов",
            filetypes=[("Текстовые файлы", "*.txt"), ("Все файлы", "*.*")]
        )
        if filepath:
            try:
                codes = read_codes(filepath)
                self.parent_filepath = filepath
                self.parent_codes = codes
                self.lbl_parent_info.config(
                    text=f"Выбран: {os.path.basename(filepath)} ({len(codes)} шт.)"
                )
            except Exception as e:
                messagebox.showerror("Ошибка при чтении файла", str(e))

    def select_child_files(self):
        filepaths = filedialog.askopenfilenames(
            title="Выбрать файлы кодов маркировки содержимого",
            filetypes=[("Текстовые файлы", "*.txt"), ("Все файлы", "*.*")]
        )
        if filepaths:
            errors = []
            for fp in filepaths:
                if fp not in self.child_filepaths:
                    try:
                        codes = read_codes(fp)
                        self.child_filepaths.append(fp)
                        self.child_codes.extend(codes)
                        self.lst_children.insert(tk.END, f"{os.path.basename(fp)} ({len(codes)} шт.)")
                    except Exception as e:
                        errors.append(f"{os.path.basename(fp)}: {e}")

            self.lbl_child_info.config(
                text=f"Всего выбрано файлов: {len(self.child_filepaths)} | Общее кол-во кодов вложений: {len(self.child_codes)}"
            )
            if errors:
                messagebox.showwarning("Ошибки при чтении файлов", "\n".join(errors))

    def clear_child_files(self):
        self.child_filepaths = []
        self.child_codes = []
        self.lst_children.delete(0, tk.END)
        self.lbl_child_info.config(text="Всего выбрано файлов: 0 | Общее кол-во кодов вложений: 0")

    def confirm_partial(self, actual, required):
        return messagebox.askyesno(
            "Недостаточно кодов",
            f"Количество доступных кодов вложений ({actual} шт.) меньше, "
            f"чем необходимо для полного заполнения всех наборов ({required} шт.).\n\n"
            f"Продолжить агрегацию частичных результатов?",
            icon="warning"
        )

    def run_aggregation(self):
        if not self.parent_filepath or not self.parent_codes:
            messagebox.showerror("Ошибка", "Пожалуйста, выберите файл с кодами наборов (родительскими).")
            return

        if not self.child_filepaths or not self.child_codes:
            messagebox.showerror("Ошибка", "Пожалуйста, выберите хотя бы один файл с кодами вложений.")
            return

        try:
            count = self.var_count.get()
        except tk.TclError:
            messagebox.showerror("Ошибка", "Количество вложений должно быть целым положительным числом.")
            return

        if count <= 0:
            messagebox.showerror("Ошибка", "Количество вложений должно быть больше нуля.")
            return

        # Генерация новой папки с таймстампом в текущей директории
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        output_dir = os.path.join(os.getcwd(), f"aggregation_results_{timestamp}")

        try:
            actual_sets, created_files = perform_aggregation(
                parent_codes=self.parent_codes,
                child_codes=self.child_codes,
                count_per_parent=count,
                output_dir=output_dir,
                confirm_callback=self.confirm_partial
            )

            if actual_sets > 0:
                messagebox.showinfo(
                    "Успех",
                    f"Агрегация успешно завершена!\n\n"
                    f"Создано наборов: {actual_sets}\n"
                    f"Всего файлов сохранено: {len(created_files)}\n"
                    f"Папка с результатами:\n{output_dir}"
                )
            else:
                messagebox.showinfo("Информация", "Агрегация была отменена или не создано ни одного набора.")

        except Exception as e:
            messagebox.showerror("Критическая ошибка при агрегации", str(e))

def show_exception_and_exit(exc_type, exc_value, exc_traceback):
    err_msg = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    if tk and tk._default_root:
        messagebox.showerror("Критическая ошибка", f"Произошла непредвиденная ошибка:\n\n{err_msg}")
    else:
        print(f"Критическая ошибка:\n{err_msg}", file=sys.stderr)
    sys.exit(1)

def main():
    if tk is None:
        print("Ошибка: Модуль tkinter недоступен. Запуск GUI невозможен.", file=sys.stderr)
        sys.exit(1)

    sys.excepthook = show_exception_and_exit

    root = tk.Tk()
    app = VirtualAggregationApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
