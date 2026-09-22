"""
Скрипт для виртуальной агрегации кодов маркировки.

Инструкция по сборке в исполняемый файл (.exe):
1. Установите PyInstaller, если он еще не установлен:
   pip install pyinstaller
2. Выполните команду для сборки единого файлового приложения без консольного окна:
   pyinstaller --noconsole --onefile virtual_aggregation.py
3. Исполняемый файл появится в папке 'dist/virtual_aggregation.exe'.
"""

import os
import sys
import re
from datetime import datetime

# Вспомогательная функция очистки имени файла от невалидных символов Windows
def sanitize_filename(filename: str) -> str:
    """
    Заменяет символы, не допустимые в именах файлов Windows, на символ подчёркивания.
    """
    if not filename:
        return "set_code"
    # Символы \ / : * ? " < > |
    sanitized = re.sub(r'[\\/*?:"<>|]', '_', filename.strip())
    # Удаляем управляющие символы
    sanitized = re.sub(r'[\x00-\x1f\x7f]', '', sanitized)
    return sanitized if sanitized else "set_code"

# Чтение кодов из файла с подбором кодировок
def read_codes(filepath: str) -> list:
    """
    Считывает строки из текстового файла, проверяя популярные кодировки.
    Возвращает список непустых очищенных строк (кодов).
    """
    encodings = ['utf-8-sig', 'utf-16', 'utf-8', 'cp1251']
    last_error = None

    for enc in encodings:
        try:
            with open(filepath, 'r', encoding=enc) as f:
                lines = f.readlines()
            # Успешно прочитали, очищаем от пробелов и переводов строк
            codes = [line.strip() for line in lines if line.strip()]
            return codes
        except (UnicodeError, LookupError) as e:
            last_error = e
            continue

    if last_error:
        raise last_error
    return []

# Ядро логики агрегации
def perform_aggregation(parent_file: str, child_files: list, count_per_parent: int, output_dir: str = None, confirm_callback=None) -> dict:
    """
    Выполняет виртуальную агрегацию:
    - parent_file: путь к TXT файлу с кодами набора (родительские)
    - child_files: список путей к TXT файлам с кодами вложений (дочерние)
    - count_per_parent: количество вложений в один набор
    - output_dir: кастомный каталог для сохранения (если None, создаётся новый с отметкой времени)
    - confirm_callback: функция обратного вызова (возвращает bool) при нехватке дочерних кодов
    """
    if not parent_file or not os.path.isfile(parent_file):
        raise ValueError("Указанный файл с кодами наборов не существует.")

    if not child_files:
        raise ValueError("Не выбраны файлы с кодами вложений.")

    if count_per_parent <= 0:
        raise ValueError("Количество вложений на набор должно быть больше 0.")

    parent_codes = read_codes(parent_file)
    if not parent_codes:
        raise ValueError("Файл с кодами наборов пуст или содержит недопустимые данные.")

    child_codes = []
    for c_file in child_files:
        if os.path.isfile(c_file):
            child_codes.extend(read_codes(c_file))

    if not child_codes:
        raise ValueError("Файлы с кодами вложений не содержат корректных кодов.")

    total_parents = len(parent_codes)
    needed_children = total_parents * count_per_parent
    actual_children = len(child_codes)

    # Проверка на достаточность дочерних кодов
    if actual_children < needed_children:
        msg = f"Для {total_parents} наборов требуется {needed_children} вложений, но найдено только {actual_children}.\nПродолжить с имеющимся количеством?"
        if confirm_callback:
            if not confirm_callback(msg):
                raise OperationCanceled("Операция отменена пользователем.")

    # Вычисляем сколько полноценных/частичных наборов получится
    actual_sets = min(total_parents, actual_children // count_per_parent)
    if actual_children % count_per_parent != 0 and actual_sets < total_parents and actual_children > actual_sets * count_per_parent:
        actual_sets += 1

    actual_sets = min(total_parents, actual_sets)

    if actual_sets == 0:
        raise ValueError("Недостаточно кодов вложений даже для одного набора.")

    # Создание директории для результатов
    if not output_dir:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = f"aggregation_results_{timestamp}"

    os.makedirs(output_dir, exist_ok=True)

    used_filenames = set()
    created_files_count = 0
    used_child_index = 0

    for i in range(actual_sets):
        p_code = parent_codes[i]
        base_name = sanitize_filename(p_code)

        filename = f"{base_name}.txt"
        counter = 1
        while filename.lower() in used_filenames:
            filename = f"{base_name}_{counter}.txt"
            counter += 1

        used_filenames.add(filename.lower())
        file_path = os.path.join(output_dir, filename)

        # Выбираем порцию дочерних кодов
        current_children = child_codes[used_child_index:used_child_index + count_per_parent]
        used_child_index += len(current_children)

        # Запись в файл UTF-8 без BOM
        with open(file_path, 'w', encoding='utf-8', newline='\n') as out_f:
            out_f.write(p_code + '\n')
            for c_code in current_children:
                out_f.write(c_code + '\n')

        created_files_count += 1

    return {
        'output_dir': output_dir,
        'created_files': created_files_count,
        'total_parents': total_parents,
        'used_children': used_child_index
    }


class OperationCanceled(Exception):
    """Исключение при отмене операции пользователем."""
    pass


# Графический интерфейс Tkinter (ленивая загрузка для возможности запуска тестов без GUI)
def run_gui():
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
    import traceback

    class AggregationGUI:
        def __init__(self, root):
            self.root = root
            self.root.title("Виртуальная агрегация кодов маркировки")
            self.root.geometry("620x520")
            self.root.resizable(False, False)

            self.parent_file = ""
            self.child_files = []

            self.setup_ui()

        def setup_ui(self):
            padding = {'padx': 10, 'pady': 5}

            # Группа 1: Файл кодов набора
            frame_parent = ttk.LabelFrame(self.root, text=" 1. Коды маркировки наборов (родительские) ")
            frame_parent.pack(fill="x", **padding)

            btn_parent = ttk.Button(frame_parent, text="Выбрать файл наборов (1 файл)", command=self.select_parent_file)
            btn_parent.pack(side="left", **padding)

            self.lbl_parent = ttk.Label(frame_parent, text="Файл не выбран", wraplength=400)
            self.lbl_parent.pack(side="left", fill="x", expand=True, **padding)

            # Группа 2: Количество вложений
            frame_count = ttk.LabelFrame(self.root, text=" 2. Количество вложений ")
            frame_count.pack(fill="x", **padding)

            lbl_count = ttk.Label(frame_count, text="Количество вложений на 1 набор:")
            lbl_count.pack(side="left", **padding)

            self.spin_count = ttk.Spinbox(frame_count, from_=1, to=10000, width=10)
            self.spin_count.set(1)
            self.spin_count.pack(side="left", **padding)

            # Группа 3: Файлы кодов вложений
            frame_child = ttk.LabelFrame(self.root, text=" 3. Коды маркировки вложений (дочерние) ")
            frame_child.pack(fill="both", expand=True, **padding)

            btn_child = ttk.Button(frame_child, text="Выбрать файлы вложений (TXT)", command=self.select_child_files)
            btn_child.pack(anchor="w", **padding)

            self.lbl_child_summary = ttk.Label(frame_child, text="Выбрано файлов: 0")
            self.lbl_child_summary.pack(anchor="w", **padding)

            self.listbox_children = tk.Listbox(frame_child, height=6)
            self.listbox_children.pack(fill="both", expand=True, **padding)

            # Кнопка запуска
            self.btn_run = ttk.Button(self.root, text=" Выполнить агрегацию ", command=self.start_aggregation)
            self.btn_run.pack(pady=10)

        def select_parent_file(self):
            path = filedialog.askopenfilename(
                title="Выберите файл с кодами маркировки набора",
                filetypes=[("Текстовые файлы", "*.txt"), ("Все файлы", "*.*")]
            )
            if path:
                self.parent_file = path
                self.lbl_parent.config(text=os.path.basename(path))

        def select_child_files(self):
            paths = filedialog.askopenfilenames(
                title="Выберите файлы с кодами маркировки вложений",
                filetypes=[("Текстовые файлы", "*.txt"), ("Все файлы", "*.*")]
            )
            if paths:
                self.child_files = list(paths)
                self.lbl_child_summary.config(text=f"Выбрано файлов: {len(self.child_files)}")
                self.listbox_children.delete(0, tk.END)
                for p in self.child_files:
                    self.listbox_children.insert(tk.END, os.path.basename(p))

        def confirm_dialog(self, message: str) -> bool:
            return messagebox.askyesno("Внимание", message)

        def start_aggregation(self):
            try:
                count_str = self.spin_count.get()
                if not count_str.isdigit():
                    messagebox.showerror("Ошибка", "Количество вложений должно быть целым положительным числом.")
                    return

                count_val = int(count_str)

                result = perform_aggregation(
                    parent_file=self.parent_file,
                    child_files=self.child_files,
                    count_per_parent=count_val,
                    confirm_callback=self.confirm_dialog
                )

                msg = (
                    f"Виртуальная агрегация успешно завершена!\n\n"
                    f"Результаты сохранены в папку:\n{os.path.abspath(result['output_dir'])}\n\n"
                    f"Создано файлов: {result['created_files']}\n"
                    f"Использовано вложений: {result['used_children']}"
                )
                messagebox.showinfo("Успех", msg)

            except OperationCanceled:
                messagebox.showinfo("Информация", "Операция отменена.")
            except Exception as e:
                err_msg = f"Произошла ошибка при выполнении агрегации:\n{str(e)}\n\nДетали:\n{traceback.format_exc()}"
                messagebox.showerror("Ошибка", err_msg)

    root = tk.Tk()
    app = AggregationGUI(root)
    root.mainloop()


if __name__ == "__main__":
    run_gui()
