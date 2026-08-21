"""
Скрипт виртуальной агрегации кодов маркировки.

Инструкция по сборке в EXE с помощью PyInstaller:
1. Установите PyInstaller:
   pip install pyinstaller
2. Выполните команду сборки:
   pyinstaller --noconsole --onefile virtual_aggregation.py
3. Исполняемый файл появится в папке dist/virtual_aggregation.exe
"""

import os
import re
import sys
from datetime import datetime


def read_codes(filepath):
    """
    Считывает строки из текстового файла с последовательной проверкой кодировок:
    UTF-8-SIG, UTF-16, UTF-8, CP1251.
    """
    encodings = ["utf-8-sig", "utf-16", "utf-8", "cp1251"]
    lines = []

    for enc in encodings:
        try:
            with open(filepath, "r", encoding=enc) as f:
                content = f.read()
                lines = [line.strip() for line in content.splitlines() if line.strip()]
                return lines
        except (UnicodeError, LookupError):
            continue

    # Если ни одна кодировка не подошла через splitlines, пробуем читать посимвольно/построчно с игнорированием
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        lines = [line.strip() for line in f if line.strip()]
    return lines


def sanitize_filename(code):
    """
    Заменяет символы, недопустимые в именах файлов Windows/Unix, на подчёркивание.
    """
    # Недопустимые символы: \ / : * ? " < > |
    cleaned = re.sub(r'[\\/:*?"<>|]', '_', code)
    # Удаляем управляющие символы
    cleaned = re.sub(r'[\r\n\t\x00-\x1f]', '_', cleaned).strip('. ')
    if not cleaned:
        cleaned = "set"
    return cleaned


def perform_aggregation(parent_file, child_files, count_per_parent, output_dir=None, confirm_callback=None):
    """
    Выполняет логику виртуальной агрегации:
    1. Читает родительские коды из parent_file.
    2. Читает дочерние коды из списка child_files.
    3. При необходимости запрашивает подтверждение через confirm_callback.
    4. Создаёт отдельную папку и записывает файлы наборов.

    Возвращает словарь со статистикой: {"created_files": int, "output_dir": str}.
    """
    if count_per_parent <= 0:
        raise ValueError("Количество вложений должно быть больше 0.")

    parent_codes = read_codes(parent_file)
    if not parent_codes:
        raise ValueError("Файл кодов маркировки наборов пуст или не содержит корректных кодов.")

    child_codes = []
    for cf in child_files:
        if cf and os.path.exists(cf):
            child_codes.extend(read_codes(cf))

    if not child_codes:
        raise ValueError("Файлы кодов вложений пусты или не содержат корректных кодов.")

    total_parents = len(parent_codes)
    total_needed = total_parents * count_per_parent
    total_available = len(child_codes)

    if total_available < total_needed:
        possible_sets = total_available // count_per_parent
        if possible_sets == 0:
            raise ValueError(
                f"Недостаточно кодов вложений ({total_available}) даже для одного набора. "
                f"Требуется минимум {count_per_parent} кодов."
            )
        if confirm_callback:
            proceed = confirm_callback(total_needed, total_available, possible_sets)
            if not proceed:
                return {"created_files": 0, "output_dir": None, "cancelled": True}
        total_parents = possible_sets
        parent_codes = parent_codes[:total_parents]

    if not output_dir:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = os.path.abspath(f"aggregation_results_{timestamp}")

    os.makedirs(output_dir, exist_ok=True)

    created_files_count = 0
    used_filenames = set()

    for i in range(total_parents):
        parent_code = parent_codes[i]
        start_idx = i * count_per_parent
        end_idx = start_idx + count_per_parent
        current_children = child_codes[start_idx:end_idx]

        base_name = sanitize_filename(parent_code)
        filename = f"{base_name}.txt"
        counter = 1
        while filename.lower() in used_filenames or os.path.exists(os.path.join(output_dir, filename)):
            filename = f"{base_name}_{counter}.txt"
            counter += 1

        used_filenames.add(filename.lower())
        file_path = os.path.join(output_dir, filename)

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(parent_code + "\n")
            for c_code in current_children:
                f.write(c_code + "\n")

        created_files_count += 1

    return {"created_files": created_files_count, "output_dir": output_dir, "cancelled": False}


class VirtualAggregationApp:
    def __init__(self, root):
        import tkinter as tk
        from tkinter import ttk, filedialog, messagebox

        self.tk = tk
        self.filedialog = filedialog
        self.messagebox = messagebox

        self.root = root
        self.root.title("Виртуальная агрегация кодов маркировки")
        self.root.geometry("680x480")
        self.root.resizable(False, False)

        self.parent_file_var = tk.StringVar()
        self.child_file1_var = tk.StringVar()
        self.child_file2_var = tk.StringVar()
        self.child_file3_var = tk.StringVar()
        self.count_per_parent_var = tk.IntVar(value=10)

        self.create_widgets()

    def create_widgets(self):
        tk = self.tk

        main_frame = tk.Frame(self.root, padx=15, pady=15)
        main_frame.pack(fill="both", expand=True)

        title_lbl = tk.Label(
            main_frame,
            text="Виртуальная агрегация кодов маркировки",
            font=("Arial", 14, "bold")
        )
        title_lbl.pack(pady=(0, 15))

        # Секция 1: Родительский файл
        parent_group = tk.LabelFrame(main_frame, text="1. Файл кодов маркировки наборов (1 файл)", padx=10, pady=10)
        parent_group.pack(fill="x", pady=5)

        p_entry = tk.Entry(parent_group, textvariable=self.parent_file_var, width=62)
        p_entry.pack(side="left", padx=(0, 5))
        p_btn = tk.Button(parent_group, text="Обзор...", command=self.select_parent_file)
        p_btn.pack(side="right")

        # Секция 2: Количество вложений
        count_group = tk.LabelFrame(main_frame, text="2. Количество вложений в один набор", padx=10, pady=10)
        count_group.pack(fill="x", pady=5)

        tk.Label(count_group, text="Количество штук:").pack(side="left", padx=(0, 10))
        count_spin = tk.Spinbox(count_group, from_=1, to=1000, textvariable=self.count_per_parent_var, width=10)
        count_spin.pack(side="left")

        # Секция 3: Файлы вложений (3 файла)
        child_group = tk.LabelFrame(main_frame, text="3. Файлы кодов маркировки содержимого (3 файла TXT)", padx=10, pady=10)
        child_group.pack(fill="x", pady=5)

        for i, var in enumerate([self.child_file1_var, self.child_file2_var, self.child_file3_var], start=1):
            row_frame = tk.Frame(child_group)
            row_frame.pack(fill="x", pady=2)
            tk.Label(row_frame, text=f"Файл {i}:", width=8, anchor="w").pack(side="left")
            entry = tk.Entry(row_frame, textvariable=var, width=52)
            entry.pack(side="left", padx=(0, 5))
            btn = tk.Button(row_frame, text="Обзор...", command=lambda v=var: self.select_child_file(v))
            btn.pack(side="right")

        # Кнопка запуска
        run_btn = tk.Button(
            main_frame,
            text="Сформировать файлы агрегации",
            font=("Arial", 12, "bold"),
            bg="#4CAF50",
            fg="white",
            pady=8,
            command=self.run_aggregation
        )
        run_btn.pack(fill="x", pady=(15, 0))

    def select_parent_file(self):
        filename = self.filedialog.askopenfilename(
            title="Выберите файл кодов наборов",
            filetypes=[("Текстовые файлы", "*.txt"), ("Все файлы", "*.*")]
        )
        if filename:
            self.parent_file_var.set(filename)

    def select_child_file(self, target_var):
        filename = self.filedialog.askopenfilename(
            title="Выберите файл кодов вложений",
            filetypes=[("Текстовые файлы", "*.txt"), ("Все файлы", "*.*")]
        )
        if filename:
            target_var.set(filename)

    def run_aggregation(self):
        parent_file = self.parent_file_var.get().strip()
        child_files = [
            self.child_file1_var.get().strip(),
            self.child_file2_var.get().strip(),
            self.child_file3_var.get().strip()
        ]
        child_files = [f for f in child_files if f]

        if not parent_file or not os.path.exists(parent_file):
            self.messagebox.showerror("Ошибка", "Пожалуйста, выберите существующий файл кодов наборов.")
            return

        if not child_files:
            self.messagebox.showerror("Ошибка", "Пожалуйста, выберите хотя бы один файл кодов вложений.")
            return

        for cf in child_files:
            if not os.path.exists(cf):
                self.messagebox.showerror("Ошибка", f"Файл не найден: {cf}")
                return

        try:
            count = self.count_per_parent_var.get()
            if count <= 0:
                raise ValueError
        except Exception:
            self.messagebox.showerror("Ошибка", "Введите корректное число вложений (больше 0).")
            return

        def confirm_cb(needed, available, possible):
            msg = (
                f"Внимание!\n\n"
                f"Для агрегации всех наборов требуется кодов вложений: {needed}.\n"
                f"Доступно кодов вложения: {available}.\n\n"
                f"Будет сформировано только {possible} полных наборов.\n"
                f"Продолжить?"
            )
            return self.messagebox.askyesno("Недостаточно кодов вложений", msg)

        try:
            result = perform_aggregation(
                parent_file=parent_file,
                child_files=child_files,
                count_per_parent=count,
                confirm_callback=confirm_cb
            )

            if result.get("cancelled"):
                self.messagebox.showinfo("Отмена", "Операция отменена пользователем.")
                return

            self.messagebox.showinfo(
                "Успех",
                f"Виртуальная агрегация завершена!\n\n"
                f"Создано файлов наборов: {result['created_files']}\n"
                f"Папка с результатами:\n{result['output_dir']}"
            )
        except Exception as e:
            self.messagebox.showerror("Ошибка агрегации", str(e))


def main():
    import tkinter as tk
    root = tk.Tk()
    app = VirtualAggregationApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
