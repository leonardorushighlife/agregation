"""
Инструкция по сборке в исполняемый файл (EXE):
1. Установите необходимые библиотеки (если они еще не установлены):
   pip install pyinstaller
2. Выполните команду сборки в терминале из корневой папки проекта:
   pyinstaller --noconsole --onefile virtual_aggregation.py
3. Исполняемый файл появится в папке 'dist/virtual_aggregation.exe'.
"""

import os
import re
import datetime
import traceback
import sys

# Ленивый/безопасный импорт tkinter для headless-тестов
try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
except ImportError:
    tk = None

def sanitize_filename(parent_code):
    """
    Очищает родительский код от символов, запрещенных в именах файлов Windows.
    Заменяет их на символ подчеркивания.
    """
    forbidden = r'[\\/:*?"<>|]'
    return re.sub(forbidden, '_', parent_code)

def read_codes(filepath):
    """
    Читает коды из текстового файла, поддерживая автоматический выбор кодировок:
    UTF-8-SIG, UTF-16, UTF-8, CP1251.
    """
    encodings = ['utf-8-sig', 'utf-16', 'utf-8', 'cp1251']
    for enc in encodings:
        try:
            with open(filepath, 'r', encoding=enc) as f:
                content = f.read()
                # Разделение по строкам, удаление пустых строк и лишних пробелов
                lines = [line.strip() for line in content.splitlines() if line.strip()]
                return lines
        except (UnicodeError, LookupError):
            continue
    raise ValueError(f"Не удалось прочитать файл {filepath} с использованием поддерживаемых кодировок.")

def perform_aggregation(parent_codes, child_codes, count_per_parent, output_dir, confirm_callback=None):
    """
    Выполняет виртуальную агрегацию кодов.
    Аргументы:
        parent_codes: список кодов наборов (родительских).
        child_codes: список кодов вложений.
        count_per_parent: количество вложений в один набор.
        output_dir: директория для сохранения результатов.
        confirm_callback: функция обратного вызова для подтверждения продолжения (при нехватке кодов).
    Возвращает:
        (success, result_message_or_list)
    """
    if not parent_codes:
        raise ValueError("Список кодов наборов пуст.")
    if not child_codes:
        raise ValueError("Список кодов вложений пуст.")
    if count_per_parent <= 0:
        raise ValueError("Количество вложений должно быть больше нуля.")

    total_required = len(parent_codes) * count_per_parent
    actual_sets = len(parent_codes)

    if len(child_codes) < total_required:
        if confirm_callback:
            msg = (f"Количество доступных кодов вложений ({len(child_codes)}) "
                   f"меньше необходимого ({total_required}).\n"
                   f"Будет создано только {len(child_codes) // count_per_parent} "
                   f"полных наборов.\nПродолжить?")
            if not confirm_callback(msg):
                return False, "Операция отменена пользователем."

        actual_sets = len(child_codes) // count_per_parent
        if actual_sets == 0:
            raise ValueError("Недостаточно кодов вложений для создания хотя бы одного полного набора.")

    os.makedirs(output_dir, exist_ok=True)

    used_filenames = {}
    created_files = []

    for i in range(actual_sets):
        parent = parent_codes[i]
        children = child_codes[i * count_per_parent : (i + 1) * count_per_parent]

        base_name = sanitize_filename(parent)

        # Разрешение коллизий имен файлов
        candidate_name = base_name
        suffix_counter = 1
        while candidate_name in used_filenames:
            candidate_name = f"{base_name}_{suffix_counter}"
            suffix_counter += 1

        used_filenames[candidate_name] = True

        filepath = os.path.join(output_dir, f"{candidate_name}.txt")

        # Запись в формате UTF-8 без BOM
        with open(filepath, 'w', encoding='utf-8', newline='') as f:
            f.write(parent + "\n")
            for child in children:
                f.write(child + "\n")

        created_files.append(filepath)

    return True, created_files

class VirtualAggregationApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Виртуальная Агрегация")
        self.root.geometry("620x480")
        self.root.minsize(550, 400)

        # Переменные для хранения путей к файлам
        self.parent_file = tk.StringVar()
        self.child_files = []
        self.count_per_parent = tk.IntVar(value=4)

        self._create_widgets()

    def _create_widgets(self):
        # Настройка сетки
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        main_frame = ttk.Frame(self.root, padding="15")
        main_frame.grid(row=0, column=0, sticky="nsew")
        main_frame.columnconfigure(1, weight=1)

        # Секция выбора файлов наборов (Родительских)
        ttk.Label(main_frame, text="Файл кодов маркировки набора (родительский):", font=("Arial", 10, "bold")).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 5))

        parent_entry = ttk.Entry(main_frame, textvariable=self.parent_file, font=("Arial", 9))
        parent_entry.grid(row=1, column=0, columnspan=2, sticky="ew", padx=(0, 5), pady=(0, 15))

        parent_btn = ttk.Button(main_frame, text="Выбрать файл", command=self._select_parent_file)
        parent_btn.grid(row=1, column=2, sticky="ew", pady=(0, 15))

        # Секция выбора файлов содержимого (Вложений)
        ttk.Label(main_frame, text="Файлы кодов маркировки вложений (содержимого):", font=("Arial", 10, "bold")).grid(row=2, column=0, columnspan=3, sticky="w", pady=(0, 5))

        self.children_text = tk.Text(main_frame, height=6, wrap="none", font=("Arial", 9))
        self.children_text.grid(row=3, column=0, columnspan=2, sticky="nsew", padx=(0, 5), pady=(0, 10))
        self.children_text.config(state="disabled")

        scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=self.children_text.yview)
        scrollbar.grid(row=3, column=2, sticky="ns", pady=(0, 10))
        self.children_text.config(yscrollcommand=scrollbar.set)

        child_btn_frame = ttk.Frame(main_frame)
        child_btn_frame.grid(row=4, column=0, columnspan=3, sticky="ew", pady=(0, 15))
        child_btn_frame.columnconfigure(0, weight=1)
        child_btn_frame.columnconfigure(1, weight=1)

        select_children_btn = ttk.Button(child_btn_frame, text="Добавить файлы вложений", command=self._select_children_files)
        select_children_btn.grid(row=0, column=0, sticky="ew", padx=(0, 5))

        clear_children_btn = ttk.Button(child_btn_frame, text="Очистить список", command=self._clear_children_files)
        clear_children_btn.grid(row=0, column=1, sticky="ew", padx=(5, 0))

        # Секция выбора количества вложений
        qty_frame = ttk.Frame(main_frame)
        qty_frame.grid(row=5, column=0, columnspan=3, sticky="w", pady=(0, 20))

        ttk.Label(qty_frame, text="Количество вложений в набор:", font=("Arial", 9, "bold")).pack(side="left", padx=(0, 10))
        qty_spinbox = ttk.Spinbox(qty_frame, from_=1, to=10000, textvariable=self.count_per_parent, width=10, font=("Arial", 9))
        qty_spinbox.pack(side="left")

        # Кнопка Запуска
        self.run_btn = ttk.Button(main_frame, text="Выполнить агрегацию", style="Accent.TButton", command=self._run_aggregation)
        self.run_btn.grid(row=6, column=0, columnspan=3, sticky="ew", ipady=10)

        # Настройка стилей
        style = ttk.Style()
        style.configure("Accent.TButton", font=("Arial", 11, "bold"))

    def _select_parent_file(self):
        filepath = filedialog.askopenfilename(
            title="Выбрать файл кодов маркировки наборов",
            filetypes=[("Текстовые файлы", "*.txt"), ("Все файлы", "*.*")]
        )
        if filepath:
            self.parent_file.set(filepath)

    def _select_children_files(self):
        filepaths = filedialog.askopenfilenames(
            title="Выбрать файлы кодов маркировки вложений",
            filetypes=[("Текстовые файлы", "*.txt"), ("Все файлы", "*.*")]
        )
        if filepaths:
            self.child_files.extend(filepaths)
            self.child_files = list(set(self.child_files))  # Удаление дубликатов файлов
            self._update_children_text()

    def _clear_children_files(self):
        self.child_files = []
        self._update_children_text()

    def _update_children_text(self):
        self.children_text.config(state="normal")
        self.children_text.delete("1.0", "end")
        for f in self.child_files:
            self.children_text.insert("end", f"{os.path.basename(f)} ({f})\n")
        self.children_text.config(state="disabled")

    def _run_aggregation(self):
        # Валидация полей
        if not self.parent_file.get():
            messagebox.showerror("Ошибка", "Пожалуйста, выберите файл с кодами маркировки наборов.")
            return

        if not self.child_files:
            messagebox.showerror("Ошибка", "Пожалуйста, выберите хотя бы один файл с кодами маркировки вложений.")
            return

        try:
            qty = self.count_per_parent.get()
            if qty <= 0:
                raise ValueError()
        except Exception:
            messagebox.showerror("Ошибка", "Количество вложений должно быть целым положительным числом.")
            return

        # Чтение кодов
        try:
            parent_codes = read_codes(self.parent_file.get())
        except Exception as e:
            messagebox.showerror("Ошибка чтения родительского файла", f"Произошла ошибка: {e}")
            return

        child_codes = []
        for filepath in self.child_files:
            try:
                child_codes.extend(read_codes(filepath))
            except Exception as e:
                messagebox.showerror("Ошибка чтения файла вложений", f"Не удалось прочитать файл {filepath}:\n{e}")
                return

        # Создание целевой папки
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = f"aggregation_results_{timestamp}"

        # Коллбэк подтверждения
        def confirm_callback(msg):
            return messagebox.askyesno("Внимание", msg)

        # Запуск агрегации
        try:
            success, result = perform_aggregation(
                parent_codes, child_codes, qty, output_dir, confirm_callback
            )
            if success:
                abs_path = os.path.abspath(output_dir)
                messagebox.showinfo(
                    "Успех",
                    f"Агрегация успешно завершена!\nСоздано файлов: {len(result)}\nПапка сохранения: {abs_path}"
                )
            else:
                messagebox.showwarning("Отмена", result)
        except Exception as e:
            messagebox.showerror("Ошибка агрегации", f"Произошла критическая ошибка: {e}")

def global_exception_handler(exctype, value, tb):
    """
    Глобальный обработчик ошибок для вывода подробного traceback.
    """
    err_msg = "".join(traceback.format_exception(exctype, value, tb))
    print(err_msg, file=sys.stderr)
    if tk:
        try:
            # Создаем временное скрытое окно, если основное не создано или упало
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror("Критическая ошибка", f"Произошло непредвиденное исключение:\n\n{err_msg}")
        except Exception:
            pass
    sys.exit(1)

if __name__ == "__main__":
    sys.excepthook = global_exception_handler
    if tk is None:
        print("Ошибка: Пакет tkinter не установлен. Запустите скрипт в среде с графическим интерфейсом.")
        sys.exit(1)

    root = tk.Tk()
    app = VirtualAggregationApp(root)
    root.mainloop()
