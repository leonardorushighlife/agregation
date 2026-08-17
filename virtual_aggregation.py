"""
Скрипт виртуальной агрегации кодов маркировки.

Позволяет объединить код маркировки набора (родительский код) и коды маркировки
вложений (дочерние коды) из выбранных TXT файлов в отдельные итоговые TXT файлы.

Для сборки в исполняемый файл (.exe) используйте PyInstaller:
    pip install pyinstaller
    pyinstaller --noconsole --onefile virtual_aggregation.py
"""

import os
import re
import sys
import datetime
import traceback

def sanitize_filename(filename: str) -> str:
    """
    Очищает строку от символов, не допустимых в именах файлов Windows/Linux.
    """
    if not filename:
        return "unnamed"
    # Заменяем недопустимые символы в файловой системе на подчеркивание
    cleaned = re.sub(r'[\\/*?:"<>|]', '_', filename.strip())
    # Удаляем управляющие символы и пробелы с концов
    cleaned = cleaned.strip()
    return cleaned if cleaned else "unnamed"


def read_codes(filepath: str) -> list[str]:
    """
    Считывает строки кодов из текстового файла, пробуя различные кодировки.
    Удаляет пустые строки и пробельные символы.
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
        raise ValueError(f"Не удалось прочитать файл {filepath}. Неподдерживаемая кодировка.")

    # Разбиваем по строкам, очищаем и фильтруем пустые
    lines = [line.strip() for line in content.splitlines()]
    return [line for line in lines if line]


def perform_aggregation(
    parent_file: str,
    child_files: list[str],
    items_per_set: int,
    output_dir: str = None,
    confirm_callback=None
) -> tuple[int, str]:
    """
    Выполняет виртуальную агрегацию.

    :param parent_file: Путь к TXT файлу с кодами наборов (родительские)
    :param child_files: Список путей к TXT файлам с кодами вложений (дочерние)
    :param items_per_set: Количество вложений в один набор
    :param output_dir: Целевая директория для результатов (если None, создается новая папка)
    :param confirm_callback: Функция обратного вызова (callable) для подтверждения при нехватке кодов
    :return: (количество_успешно_созданных_файлов, путь_к_папке_результатов)
    """
    if items_per_set <= 0:
        raise ValueError("Количество вложений должно быть больше 0.")

    parent_codes = read_codes(parent_file)
    if not parent_codes:
        raise ValueError("Файл кодов наборов пуст.")

    child_codes = []
    for cfile in child_files:
        child_codes.extend(read_codes(cfile))

    if not child_codes:
        raise ValueError("Выбранные файлы вложений не содержат кодов.")

    total_parents = len(parent_codes)
    required_children = total_parents * items_per_set

    # Проверка на достаточность кодов вложений
    if len(child_codes) < required_children:
        msg = (f"Внимание: Недостаточно кодов вложений!\n"
               f"Требуется: {required_children} ({total_parents} наборов * {items_per_set} вл.)\n"
               f"Доступно кодов вложений: {len(child_codes)}\n\n"
               f"Продолжить сборку только полных наборов?")
        if confirm_callback:
            if not confirm_callback(msg):
                raise InterruptedError("Операция отменена пользователем.")

    actual_sets = min(total_parents, len(child_codes) // items_per_set)
    if actual_sets == 0:
        raise ValueError("Недостаточно кодов вложений даже для одного полного набора.")

    if output_dir is None:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = os.path.join(os.getcwd(), f"aggregation_results_{timestamp}")

    os.makedirs(output_dir, exist_ok=True)

    created_files_count = 0
    used_filenames = {}

    for i in range(actual_sets):
        p_code = parent_codes[i]
        c_codes = child_codes[i * items_per_set : (i + 1) * items_per_set]

        base_name = sanitize_filename(p_code)

        # Обработка коллизий имен файлов
        if base_name in used_filenames:
            used_filenames[base_name] += 1
            filename = f"{base_name}_{used_filenames[base_name]}.txt"
        else:
            used_filenames[base_name] = 0
            filename = f"{base_name}.txt"

        file_path = os.path.join(output_dir, filename)

        # Запись в файл (родительский код в первой строке, затем дочерние)
        with open(file_path, 'w', encoding='utf-8') as out_f:
            out_f.write(p_code + '\n')
            for cc in c_codes:
                out_f.write(cc + '\n')

        created_files_count += 1

    return created_files_count, output_dir


def main_gui():
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox

    def global_exception_handler(exc_type, exc_value, exc_traceback):
        err_msg = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        messagebox.showerror("Критическая ошибка", f"Произошла непредвиденная ошибка:\n{err_msg}")

    sys.excepthook = global_exception_handler

    root = tk.Tk()
    root.title("Виртуальная агрегация наборов")
    root.geometry("600x480")
    root.resizable(False, False)

    # Переменные формы
    parent_file_var = tk.StringVar()
    child_files_var = tk.StringVar()
    items_count_var = tk.IntVar(value=4)
    child_files_list = []

    def select_parent_file():
        path = filedialog.askopenfilename(
            title="Выберите файл с кодами наборов (родительские)",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        if path:
            parent_file_var.set(path)

    def select_child_files():
        nonlocal child_files_list
        paths = filedialog.askopenfilenames(
            title="Выберите файлы с кодами вложений (дочерние)",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        if paths:
            child_files_list = list(paths)
            child_files_var.set(f"Выбрано файлов: {len(child_files_list)}")

    def run_aggregation():
        p_file = parent_file_var.get()
        if not p_file or not os.path.exists(p_file):
            messagebox.showwarning("Предупреждение", "Пожалуйста, выберите файл с кодами наборов.")
            return

        if not child_files_list:
            messagebox.showwarning("Предупреждение", "Пожалуйста, выберите хотя бы один файл с кодами вложений.")
            return

        try:
            items_per_set = items_count_var.get()
            if items_per_set <= 0:
                raise ValueError()
        except Exception:
            messagebox.showwarning("Предупреждение", "Укажите корректное положительное число вложений.")
            return

        def confirm_cb(msg):
            return messagebox.askyesno("Подтверждение", msg)

        try:
            count, out_path = perform_aggregation(
                parent_file=p_file,
                child_files=child_files_list,
                items_per_set=items_per_set,
                confirm_callback=confirm_cb
            )
            messagebox.showinfo(
                "Успех",
                f"Виртуальная агрегация успешно завершена!\n\n"
                f"Создано файлов: {count}\n"
                f"Папка с результатом:\n{out_path}"
            )
        except InterruptedError:
            pass
        except Exception as e:
            messagebox.showerror("Ошибка", str(e))

    # Стилизация
    style = ttk.Style()
    style.theme_use('clam')

    main_frame = ttk.Frame(root, padding=20)
    main_frame.pack(fill=tk.BOTH, expand=True)

    lbl_title = ttk.Label(main_frame, text="Виртуальная агрегация кодов маркировки", font=("Helvetica", 14, "bold"))
    lbl_title.pack(pady=(0, 20))

    # Section 1: Parent file
    frame_parent = ttk.LabelFrame(main_frame, text="1. Файл кодов маркировки набора (родительские)", padding=10)
    frame_parent.pack(fill=tk.X, pady=(0, 10))

    ent_parent = ttk.Entry(frame_parent, textvariable=parent_file_var, state="readonly", width=50)
    ent_parent.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))

    btn_parent = ttk.Button(frame_parent, text="Обзор...", command=select_parent_file)
    btn_parent.pack(side=tk.RIGHT)

    # Section 2: Items count
    frame_count = ttk.LabelFrame(main_frame, text="2. Количество вложений в один набор", padding=10)
    frame_count.pack(fill=tk.X, pady=(0, 10))

    spn_count = ttk.Spinbox(frame_count, from_=1, to=1000, textvariable=items_count_var, width=10)
    spn_count.pack(side=tk.LEFT)

    lbl_count_info = ttk.Label(frame_count, text=" штук на 1 родительский код", font=("Helvetica", 9, "italic"))
    lbl_count_info.pack(side=tk.LEFT, padx=10)

    # Section 3: Child files
    frame_child = ttk.LabelFrame(main_frame, text="3. Файлы кодов маркировки содержимого (вложения)", padding=10)
    frame_child.pack(fill=tk.X, pady=(0, 20))

    ent_child = ttk.Entry(frame_child, textvariable=child_files_var, state="readonly", width=50)
    ent_child.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))

    btn_child = ttk.Button(frame_child, text="Обзор...", command=select_child_files)
    btn_child.pack(side=tk.RIGHT)

    # Section 4: Process button
    btn_run = ttk.Button(main_frame, text="Запустить агрегацию", command=run_aggregation)
    btn_run.pack(ipady=8, fill=tk.X)

    root.mainloop()


if __name__ == "__main__":
    main_gui()
