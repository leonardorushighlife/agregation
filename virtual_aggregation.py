"""
Скрипт виртуальной агрегации кодов маркировки.

Инструкция по сборке в EXE с помощью PyInstaller:
1. Установите PyInstaller (если не установлен):
   pip install pyinstaller
2. Выполните команду для сборки одного EXE файла без консольного окна:
   pyinstaller --noconsole --onefile virtual_aggregation.py
3. Исполняемый файл появится в папке 'dist/virtual_aggregation.exe'.
"""

import os
import re
import sys
from datetime import datetime

# Импортируем tkinter с обработкой на случай работы без GUI (в тестах)
try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
    TK_AVAILABLE = True
except ImportError:
    TK_AVAILABLE = False


def read_codes_from_file(filepath):
    """
    Читает коды маркировки из текстового файла.
    Пробует различные кодировки: utf-8-sig, utf-16, utf-8, cp1251.
    Возвращает список непустых очищенных строк.
    """
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
        raise ValueError(f"Не удалось прочитать файл в известной кодировке: {filepath}")

    # Разбиваем на строки и убираем пробельные символы
    raw_lines = content.splitlines()
    codes = [line.strip() for line in raw_lines if line.strip()]
    return codes


def sanitize_filename(code, max_len=100):
    """
    Очищает код от символов, недопустимых в именах файлов Windows/Linux/macOS.
    """
    # Заменяем запрещенные символы \ / : * ? " < > | на подчеркивание
    clean_name = re.sub(r'[\\/*?:"<>|\r\n\t]', '_', code).strip()
    # Если имя получилось пустым
    if not clean_name:
        clean_name = "set"
    # Ограничиваем длину имени файла
    if len(clean_name) > max_len:
        clean_name = clean_name[:max_len]
    return clean_name


def perform_aggregation(parent_file, child_files, count_per_parent, output_dir=None, confirm_callback=None):
    """
    Основная логика виртуальной агрегации.

    :param parent_file: путь к файлу с родительскими кодами (наборы)
    :param child_files: список путей к файлам с дочерними кодами (вложения)
    :param count_per_parent: количество вложений на 1 набор (int)
    :param output_dir: директория для сохранения результатов (если None, создается новая)
    :param confirm_callback: опциональная функция для подтверждения (например, если вложений не хватает)
    :return: dict со статистикой агрегации {'output_dir': str, 'sets_created': int, 'child_used': int}
    """
    if count_per_parent <= 0:
        raise ValueError("Количество вложений должно быть положительным числом.")

    parent_codes = read_codes_from_file(parent_file)
    if not parent_codes:
        raise ValueError(f"Файл родительских кодов пуст: {parent_file}")

    child_codes = []
    for c_file in child_files:
        child_codes.extend(read_codes_from_file(c_file))

    if not child_codes:
        raise ValueError("Файлы вложений не содержат кодов маркировки.")

    total_required_children = len(parent_codes) * count_per_parent
    actual_sets = min(len(parent_codes), len(child_codes) // count_per_parent)

    if actual_sets == 0:
        raise ValueError(
            f"Недостаточно кодов вложений для формирования хотя бы одного набора.\n"
            f"Имеющихся кодов вложений: {len(child_codes)}, требуется минимум: {count_per_parent} на 1 набор."
        )

    if len(child_codes) < total_required_children:
        warning_msg = (
            f"Вниманию пользователя: Кодов вложений ({len(child_codes)}) недостаточно "
            f"для всех наборов ({len(parent_codes)} * {count_per_parent} = {total_required_children}).\n"
            f"Будет сформировано наборов: {actual_sets} из {len(parent_codes)}."
        )
        if confirm_callback:
            if not confirm_callback(warning_msg):
                return None

    if not output_dir:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = os.path.join(os.getcwd(), f"aggregation_results_{timestamp}")

    os.makedirs(output_dir, exist_ok=True)

    used_filenames = set()
    sets_created = 0
    child_index = 0

    for i in range(actual_sets):
        parent = parent_codes[i]
        items = child_codes[child_index : child_index + count_per_parent]
        child_index += count_per_parent

        base_filename = sanitize_filename(parent)
        filename = f"{base_filename}.txt"
        filepath = os.path.join(output_dir, filename)

        # Решение коллизий одинаковых имен файлов
        counter = 1
        while filename in used_filenames or os.path.exists(filepath):
            filename = f"{base_filename}_{counter}.txt"
            filepath = os.path.join(output_dir, filename)
            counter += 1

        used_filenames.add(filename)

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(parent + '\n')
            for item in items:
                f.write(item + '\n')

        sets_created += 1

    return {
        'output_dir': output_dir,
        'sets_created': sets_created,
        'child_used': sets_created * count_per_parent,
        'total_parents': len(parent_codes),
        'total_children': len(child_codes)
    }


class VirtualAggregationApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Виртуальная агрегация кодов маркировки")
        self.root.geometry("680x520")
        self.root.resizable(True, True)

        self.parent_file = ""
        self.child_files = []

        self._build_ui()

    def _build_ui(self):
        main_frame = ttk.Frame(self.root, padding="15")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Заголовок
        title_label = ttk.Label(
            main_frame,
            text="Модуль виртуальной агрегации кодов маркировки",
            font=("Arial", 14, "bold")
        )
        title_label.pack(pady=(0, 15))

        # Шаг 1: Выбор файла наборов (родительских кодов)
        step1_frame = ttk.LabelFrame(main_frame, text=" 1. Выберите файл кодов маркировки НАБОРОВ ", padding="10")
        step1_frame.pack(fill=tk.X, pady=5)

        btn_parent = ttk.Button(step1_frame, text="Обзор...", command=self.select_parent_file)
        btn_parent.pack(side=tk.LEFT, padx=(0, 10))

        self.lbl_parent = ttk.Label(step1_frame, text="Файл не выбран", foreground="gray")
        self.lbl_parent.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Шаг 2: Ввод количества вложений
        step2_frame = ttk.LabelFrame(main_frame, text=" 2. Укажите количество вложений в один набор ", padding="10")
        step2_frame.pack(fill=tk.X, pady=5)

        ttk.Label(step2_frame, text="Количество вложений на набор:").pack(side=tk.LEFT, padx=(0, 10))
        self.entry_count = ttk.Entry(step2_frame, width=10)
        self.entry_count.insert(0, "4")
        self.entry_count.pack(side=tk.LEFT)

        # Шаг 3: Выбор файлов содержимого (дочерних кодов)
        step3_frame = ttk.LabelFrame(main_frame, text=" 3. Выберите файлы кодов маркировки СОДЕРЖИМОГО ", padding="10")
        step3_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        btn_child = ttk.Button(step3_frame, text="Выбрать файлы TXT...", command=self.select_child_files)
        btn_child.pack(anchor=tk.W, pady=(0, 5))

        self.lbl_child_summary = ttk.Label(step3_frame, text="Файлы не выбраны", foreground="gray")
        self.lbl_child_summary.pack(anchor=tk.W, pady=(0, 5))

        # Список выбранных файлов
        list_frame = ttk.Frame(step3_frame)
        list_frame.pack(fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.child_listbox = tk.Listbox(list_frame, yscrollcommand=scrollbar.set, height=5)
        self.child_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.child_listbox.yview)

        # Кнопка запуска агрегации
        self.btn_run = ttk.Button(
            main_frame,
            text="Сформировать файлы агрегации",
            command=self.run_aggregation
        )
        self.btn_run.pack(pady=15, fill=tk.X, ipady=5)

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
            self.child_files = list(filenames)
            self.child_listbox.delete(0, tk.END)
            for f in self.child_files:
                self.child_listbox.insert(tk.END, os.path.basename(f))
            self.lbl_child_summary.config(
                text=f"Выбрано файлов: {len(self.child_files)}",
                foreground="black"
            )

    def run_aggregation(self):
        if not self.parent_file:
            messagebox.showerror("Ошибка", "Пожалуйста, выберите файл кодов маркировки наборов.")
            return

        if not self.child_files:
            messagebox.showerror("Ошибка", "Пожалуйста, выберите файлы кодов маркировки содержимого.")
            return

        try:
            count_per_parent = int(self.entry_count.get().strip())
            if count_per_parent <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Ошибка", "Укажите корректное положительное число для количества вложений.")
            return

        def confirm_cb(msg):
            return messagebox.askyesno("Предупреждение", msg + "\n\nПродолжить?")

        try:
            res = perform_aggregation(
                parent_file=self.parent_file,
                child_files=self.child_files,
                count_per_parent=count_per_parent,
                confirm_callback=confirm_cb
            )
            if res is None:
                return

            info = (
                f"Успешно завершено!\n\n"
                f"Создано файлов наборов: {res['sets_created']}\n"
                f"Использовано кодов вложений: {res['child_used']}\n"
                f"Результаты сохранены в папку:\n{res['output_dir']}"
            )
            messagebox.showinfo("Успех", info)

        except Exception as e:
            messagebox.showerror("Ошибка агрегации", str(e))


def main():
    if not TK_AVAILABLE:
        print("Ошибка: Модуль tkinter недоступен.")
        sys.exit(1)

    root = tk.Tk()
    app = VirtualAggregationApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
