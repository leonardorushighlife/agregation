"""
Скрипт для виртуальной агрегации кодов маркировки.
Позволяет привязать выбранное количество вложений (кодов маркировки) к каждому набору (родительскому коду)
и сохранить каждый набор в отдельный TXT-файл в создаваемой папке.

Инструкция по сборке в исполняемый файл (exe):
1. Установите PyInstaller:
   pip install pyinstaller
2. Соберите исполняемый файл командой:
   pyinstaller --noconsole --onefile virtual_aggregation.py
3. Исполняемый файл появится в папке dist/virtual_aggregation.exe
"""

import os
import re
import datetime

ENCODINGS = ['utf-8-sig', 'utf-16', 'utf-8', 'cp1251']

def sanitize_filename(name):
    """
    Очищает строку от символов, недопустимых в именах файлов Windows.
    """
    clean = re.sub(r'[\\/*?:"<>|]', '_', name.strip())
    clean = clean.strip('. ')
    if not clean:
        clean = "set"
    return clean

def read_codes(filepaths):
    """
    Считывает коды маркировки из одного или нескольких файлов txt.
    Автоматически определяет кодировку из списка ENCODINGS.
    Возвращает список очищенных непустых строк.
    """
    if isinstance(filepaths, str):
        filepaths = [filepaths]

    codes = []
    for filepath in filepaths:
        if not os.path.isfile(filepath):
            continue

        file_codes = None
        for enc in ENCODINGS:
            try:
                with open(filepath, 'r', encoding=enc) as f:
                    file_codes = [line.strip() for line in f if line.strip()]
                break
            except (UnicodeError, LookupError):
                continue

        if file_codes is not None:
            codes.extend(file_codes)
        else:
            raise ValueError(f"Не удалось прочитать файл {filepath}. Неподдерживаемая кодировка.")

    return codes

def perform_aggregation(parent_file, child_files, count_per_parent, output_dir=None, confirm_callback=None):
    """
    Выполняет виртуальную агрегацию кодов маркировки.

    :param parent_file: Путь к txt файлу с кодами наборов (родительские)
    :param child_files: Список путей к txt файлам с кодами вложений (дочерние)
    :param count_per_parent: Количество вложений в каждый набор
    :param output_dir: Целевая директория (если None, создается новая)
    :param confirm_callback: Функция обратного вызова для подтверждения продолжения при нехватке кодов
    :return: (успех: bool, сообщение: str, количество_созданных_файлов: int)
    """
    parents = read_codes(parent_file)
    if not parents:
        return False, "Файл кодов наборов пуст или не содержит корректных строк.", 0

    children = read_codes(child_files)
    if not children:
        return False, "Файлы кодов вложений пусты или не содержат корректных строк.", 0

    needed_children = len(parents) * count_per_parent
    available_children = len(children)

    if available_children < needed_children:
        if confirm_callback is not None:
            approved = confirm_callback(available_children, needed_children)
            if not approved:
                return False, "Операция отменена пользователем.", 0

    if output_dir is None:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = f"aggregation_results_{timestamp}"

    os.makedirs(output_dir, exist_ok=True)

    child_index = 0
    created_files = []
    used_filepaths = set()

    for parent in parents:
        if child_index >= available_children:
            break

        set_children = children[child_index : child_index + count_per_parent]
        if len(set_children) < count_per_parent:
            break

        child_index += count_per_parent

        clean_name = sanitize_filename(parent)
        filename = f"{clean_name}.txt"
        filepath = os.path.join(output_dir, filename)

        suffix = 1
        while filepath in used_filepaths or os.path.exists(filepath):
            filename = f"{clean_name}_{suffix}.txt"
            filepath = os.path.join(output_dir, filename)
            suffix += 1

        used_filepaths.add(filepath)

        with open(filepath, 'w', encoding='utf-8', newline='\n') as f:
            f.write(parent + '\n')
            for child in set_children:
                f.write(child + '\n')

        created_files.append(filepath)

    msg = f"Успешно обработано наборов: {len(created_files)}. Результаты сохранены в папку: {os.path.abspath(output_dir)}"
    return True, msg, len(created_files)


def run_gui():
    """
    Запуск графического интерфейса Tkinter.
    """
    import sys
    import traceback
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk

    def custom_excepthook(exc_type, exc_value, exc_traceback):
        err_msg = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        messagebox.showerror("Критическая ошибка", f"Произошла непредвиденная ошибка:\n\n{err_msg}")

    sys.excepthook = custom_excepthook

    root = tk.Tk()
    root.title("Виртуальная агрегация кодов маркировки")
    root.geometry("680x520")
    root.resizable(True, True)

    parent_file_var = tk.StringVar()
    child_files_list = []
    count_var = tk.IntVar(value=1)

    # Frame parent file
    frame_parent = ttk.LabelFrame(root, text="1. Выберите файл с кодами наборов (родительские)", padding=10)
    frame_parent.pack(fill="x", padx=10, pady=5)

    entry_parent = ttk.Entry(frame_parent, textvariable=parent_file_var, width=60)
    entry_parent.pack(side="left", fill="x", expand=True, padx=(0, 5))

    def btn_select_parent():
        f = filedialog.askopenfilename(title="Выберите файл кодов наборов", filetypes=[("Текстовые файлы", "*.txt"), ("Все файлы", "*.*")])
        if f:
            parent_file_var.set(f)

    ttk.Button(frame_parent, text="Обзор...", command=btn_select_parent).pack(side="right")

    # Frame count
    frame_count = ttk.LabelFrame(root, text="2. Укажите количество вложений в один набор", padding=10)
    frame_count.pack(fill="x", padx=10, pady=5)

    ttk.Label(frame_count, text="Количество вложений:").pack(side="left", padx=(0, 5))
    spin_count = ttk.Spinbox(frame_count, from_=1, to=1000, textvariable=count_var, width=10)
    spin_count.pack(side="left")

    # Frame child files
    frame_child = ttk.LabelFrame(root, text="3. Выберите файлы с кодами содержимого (вложений)", padding=10)
    frame_child.pack(fill="both", expand=True, padx=10, pady=5)

    listbox_children = tk.Listbox(frame_child, height=6)
    listbox_children.pack(side="left", fill="both", expand=True, padx=(0, 5))

    scrollbar = ttk.Scrollbar(frame_child, orient="vertical", command=listbox_children.yview)
    scrollbar.pack(side="left", fill="y", padx=(0, 5))
    listbox_children.config(yscrollcommand=scrollbar.set)

    frame_child_btns = ttk.Frame(frame_child)
    frame_child_btns.pack(side="right", fill="y")

    def btn_add_children():
        files = filedialog.askopenfilenames(title="Выберите файлы кодов вложений", filetypes=[("Текстовые файлы", "*.txt"), ("Все файлы", "*.*")])
        if files:
            for f in files:
                if f not in child_files_list:
                    child_files_list.append(f)
                    listbox_children.insert(tk.END, f)

    def btn_clear_children():
        child_files_list.clear()
        listbox_children.delete(0, tk.END)

    ttk.Button(frame_child_btns, text="Добавить...", command=btn_add_children).pack(fill="x", pady=2)
    ttk.Button(frame_child_btns, text="Очистить", command=btn_clear_children).pack(fill="x", pady=2)

    # Frame action
    frame_action = ttk.Frame(root, padding=10)
    frame_action.pack(fill="x", padx=10, pady=5)

    def btn_start_aggregation():
        parent_file = parent_file_var.get().strip()
        if not parent_file:
            messagebox.showwarning("Предупреждение", "Пожалуйста, выберите файл с кодами наборов.")
            return

        if not child_files_list:
            messagebox.showwarning("Предупреждение", "Пожалуйста, выберите хотя бы один файл с кодами вложений.")
            return

        try:
            count = count_var.get()
            if count <= 0:
                raise ValueError()
        except Exception:
            messagebox.showwarning("Предупреждение", "Количество вложений должно быть положительным целым числом.")
            return

        def confirm_cb(available, needed):
            return messagebox.askyesno(
                "Нехватка кодов вложений",
                f"Доступно кодов вложений: {available}\nТребуется кодов вложений: {needed}\n\n"
                f"Продолжить агрегацию только для доступного количества наборов?"
            )

        try:
            success, msg, count_created = perform_aggregation(
                parent_file=parent_file,
                child_files=child_files_list,
                count_per_parent=count,
                confirm_callback=confirm_cb
            )
            if success:
                messagebox.showinfo("Успех", msg)
            else:
                messagebox.showerror("Ошибка", msg)
        except Exception as e:
            messagebox.showerror("Ошибка", f"Произошла ошибка при выполнении агрегации:\n{e}")

    btn_start = ttk.Button(frame_action, text="Выполнить агрегацию", command=btn_start_aggregation)
    btn_start.pack(fill="x", ipady=5)

    root.mainloop()


if __name__ == "__main__":
    run_gui()
