# -*- coding: utf-8 -*-
"""
Инструкция по сборке автономного исполняемого файла (EXE) с помощью PyInstaller:

1. Установите PyInstaller (если еще не установлен):
   pip install pyinstaller

2. Выполните команду сборки в терминале из корневой папки проекта:
   pyinstaller --noconsole --onefile virtual_aggregation.py

3. После завершения сборки исполняемый файл будет находиться в папке 'dist/virtual_aggregation.exe'.
   Вы можете скопировать его в любое удобное место и использовать независимо.
"""

import os
import sys
import re
import datetime

def read_codes(filepath):
    """
    Поддерживает чтение файлов кодов в разных кодировках по приоритету:
    UTF-8-SIG, UTF-16, UTF-8, CP1251.
    """
    encodings = ['utf-8-sig', 'utf-16', 'utf-8', 'cp1251']
    for enc in encodings:
        try:
            with open(filepath, 'r', encoding=enc) as f:
                content = f.read()
                # Разделение на строки и очистка от пробельных символов
                lines = [line.strip() for line in content.splitlines() if line.strip()]
                return lines
        except (UnicodeError, LookupError):
            continue
    raise ValueError(f"Не удалось прочитать файл {filepath} с использованием поддерживаемых кодировок.")

def sanitize_filename(name):
    """
    Санирует имя файла, заменяя недопустимые в Windows символы на нижнее подчеркивание.
    """
    sanitized = re.sub(r'[\\/:*?"<>|]', '_', name)
    if not sanitized.strip():
        sanitized = "unnamed_parent"
    return sanitized

def get_unique_filepath(directory, sanitized_name):
    """
    Возвращает уникальный путь к файлу в директории, предотвращая коллизии имен.
    """
    base_path = os.path.join(directory, f"{sanitized_name}.txt")
    if not os.path.exists(base_path):
        return base_path

    counter = 1
    while True:
        candidate = os.path.join(directory, f"{sanitized_name}_{counter}.txt")
        if not os.path.exists(candidate):
            return candidate
        counter += 1

def perform_aggregation(parent_file, child_files, count_per_parent, output_dir_base=".", confirm_callback=None):
    """
    Основная логика виртуальной агрегации.
    """
    if not parent_file:
        raise ValueError("Не выбран файл с родительскими кодами (кодами наборов).")
    if not child_files:
        raise ValueError("Не выбраны файлы с дочерними кодами (кодами содержимого).")
    try:
        count_per_parent = int(count_per_parent)
    except ValueError:
        raise ValueError("Количество вложений должно быть целым числом.")

    if count_per_parent <= 0:
        raise ValueError("Количество вложений должно быть больше 0.")

    parent_codes = read_codes(parent_file)
    child_codes = []
    for f in child_files:
        child_codes.extend(read_codes(f))

    total_parents = len(parent_codes)
    total_children = len(child_codes)
    required_children = total_parents * count_per_parent

    actual_sets = total_parents
    if total_children < required_children:
        actual_sets = min(total_parents, total_children // count_per_parent)
        message = (
            f"Доступных дочерних кодов ({total_children}) меньше, "
            f"чем требуется ({required_children}) для всех родительских кодов ({total_parents}).\n"
            f"Будет создано {actual_sets} полных наборов.\n"
            f"Продолжить с частичным результатом?"
        )
        if confirm_callback:
            if not confirm_callback(message):
                return None, "Агрегация отменена пользователем."
        else:
            # Если коллбэк отсутствует, по умолчанию продолжаем
            pass

    if actual_sets == 0:
        raise ValueError("Недостаточно дочерних кодов для формирования хотя бы одного полного набора.")

    # Создание папки результатов
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    folder_name = f"aggregation_results_{timestamp}"
    output_dir = os.path.join(output_dir_base, folder_name)
    os.makedirs(output_dir, exist_ok=True)

    created_files = []
    for i in range(actual_sets):
        parent = parent_codes[i]
        start_idx = i * count_per_parent
        end_idx = start_idx + count_per_parent
        current_children = child_codes[start_idx:end_idx]

        sanitized = sanitize_filename(parent)
        filepath = get_unique_filepath(output_dir, sanitized)

        with open(filepath, 'w', encoding='utf-8', newline='') as out_f:
            out_f.write(parent + "\n")
            for child in current_children:
                out_f.write(child + "\n")

        created_files.append(filepath)

    return output_dir, created_files

def run_gui():
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
    import traceback

    def global_exception_handler(exc_type, exc_value, exc_traceback):
        # Отображение полного трейсбэка при возникновении ошибки для удаленной отладки
        tb_lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
        tb_text = "".join(tb_lines)
        messagebox.showerror(
            "Критическая ошибка",
            f"Произошло непредвиденное исключение:\n\n{tb_text}"
        )

    sys.excepthook = global_exception_handler

    root = tk.Tk()
    root.title("Виртуальная Агрегация")
    root.geometry("650x550")
    root.minsize(550, 450)

    # Переменные интерфейса
    parent_file_path = tk.StringVar()
    child_file_paths = []
    count_var = tk.StringVar(value="24")

    # Стили
    style = ttk.Style()
    style.configure("TLabel", font=("Arial", 10))
    style.configure("TButton", font=("Arial", 10))
    style.configure("Header.TLabel", font=("Arial", 12, "bold"))

    # Фрейм основного содержимого
    main_frame = ttk.Frame(root, padding="15")
    main_frame.pack(fill=tk.BOTH, expand=True)

    # Заголовок
    header = ttk.Label(main_frame, text="Утилита виртуальной агрегации", style="Header.TLabel")
    header.pack(pady=(0, 15))

    # 1. Родительский файл
    parent_lf = ttk.LabelFrame(main_frame, text=" 1. Родительские коды (Коды наборов) ", padding="10")
    parent_lf.pack(fill=tk.X, pady=5)

    parent_entry = ttk.Entry(parent_lf, textvariable=parent_file_path, width=50)
    parent_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))

    def choose_parent_file():
        path = filedialog.askopenfilename(
            title="Выберите файл родительских кодов",
            filetypes=[("Текстовые файлы (*.txt)", "*.txt"), ("Все файлы (*.*)", "*.*")]
        )
        if path:
            parent_file_path.set(path)

    parent_btn = ttk.Button(parent_lf, text="Обзор...", command=choose_parent_file)
    parent_btn.pack(side=tk.RIGHT)

    # 2. Дочерние файлы
    child_lf = ttk.LabelFrame(main_frame, text=" 2. Дочерние коды (Коды содержимого) ", padding="10")
    child_lf.pack(fill=tk.BOTH, expand=True, pady=5)

    child_listbox = tk.Listbox(child_lf, height=5, font=("Arial", 9))
    child_listbox.pack(fill=tk.BOTH, expand=True, side=tk.LEFT, padx=(0, 10))

    scrollbar = ttk.Scrollbar(child_lf, orient="vertical", command=child_listbox.yview)
    scrollbar.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
    child_listbox.configure(yscrollcommand=scrollbar.set)

    def choose_child_files():
        paths = filedialog.askopenfilenames(
            title="Выберите файлы дочерних кодов",
            filetypes=[("Текстовые файлы (*.txt)", "*.txt"), ("Все файлы (*.*)", "*.*")]
        )
        if paths:
            child_file_paths.clear()
            child_listbox.delete(0, tk.END)
            for p in paths:
                child_file_paths.append(p)
                child_listbox.insert(tk.END, os.path.basename(p))

    child_btn_frame = ttk.Frame(child_lf)
    child_btn_frame.pack(side=tk.RIGHT, fill=tk.Y)

    child_btn = ttk.Button(child_btn_frame, text="Выбрать файлы", command=choose_child_files)
    child_btn.pack(fill=tk.X, pady=(0, 5))

    def clear_child_files():
        child_file_paths.clear()
        child_listbox.delete(0, tk.END)

    clear_btn = ttk.Button(child_btn_frame, text="Очистить", command=clear_child_files)
    clear_btn.pack(fill=tk.X)

    # 3. Параметры
    param_lf = ttk.Frame(main_frame, padding="5")
    param_lf.pack(fill=tk.X, pady=5)

    count_lbl = ttk.Label(param_lf, text="Количество вложений на один набор:")
    count_lbl.pack(side=tk.LEFT, padx=(0, 10))

    count_entry = ttk.Entry(param_lf, textvariable=count_var, width=10)
    count_entry.pack(side=tk.LEFT)

    # 4. Выполнение
    def run_aggregation():
        try:
            p_file = parent_file_path.get().strip()
            c_files = child_file_paths
            count_val = count_var.get().strip()

            def confirm_dialog(msg):
                return messagebox.askyesno("Подтверждение", msg)

            res = perform_aggregation(p_file, c_files, count_val, confirm_callback=confirm_dialog)
            if res is None:
                # Отменено пользователем
                return

            output_dir, created = res
            messagebox.showinfo(
                "Успех",
                f"Виртуальная агрегация успешно завершена!\n\n"
                f"Создано наборов: {len(created)}\n"
                f"Результаты сохранены в папку:\n{output_dir}"
            )
            # Пытаемся открыть папку результатов в проводнике
            try:
                if sys.platform == 'win32':
                    os.startfile(output_dir)
                elif sys.platform == 'darwin':
                    import subprocess
                    subprocess.Popen(['open', output_dir])
                else:
                    import subprocess
                    subprocess.Popen(['xdg-open', output_dir])
            except Exception:
                pass # Игнорируем ошибки открытия проводника

        except Exception as e:
            messagebox.showerror("Ошибка", str(e))

    exec_btn = ttk.Button(main_frame, text="Начать агрегацию", command=run_aggregation, style="TButton")
    exec_btn.pack(fill=tk.X, pady=15)

    root.mainloop()

if __name__ == "__main__":
    run_gui()
