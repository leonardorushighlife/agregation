"""
Скрипт для виртуальной агрегации кодов маркировки.

Инструкция по сборке в исполняемый файл (.exe) с помощью PyInstaller:
1. Установите PyInstaller (если еще не установлен):
   pip install pyinstaller
2. Выполните команду для сборки единого .exe файла без консольного окна:
   pyinstaller --noconsole --onefile virtual_aggregation.py
3. Готовый файл virtual_aggregation.exe будет находиться в папке dist/.
"""

import os
import re
import sys
import traceback
from datetime import datetime

# Lazy / guarded import of tkinter for headless execution and unit tests
try:
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox
    HAS_TKINTER = True
except ImportError:
    HAS_TKINTER = False


def read_codes(file_path):
    """
    Читает коды из текстового файла, последовательно пробуя различные кодировки.
    Возвращает список непустых строк без концевых пробелов.
    """
    encodings = ['utf-8-sig', 'utf-16', 'utf-8', 'cp1251']
    content = None

    for enc in encodings:
        try:
            with open(file_path, 'r', encoding=enc) as f:
                content = f.read()
            break
        except (UnicodeError, LookupError):
            continue

    if content is None:
        raise ValueError(f"Не удалось прочитать файл {file_path}. Поддерживаемые кодировки: UTF-8, UTF-16, CP1251.")

    lines = [line.strip() for line in content.splitlines() if line.strip()]
    return lines


def clean_filename(code):
    """
    Очищает код от символов, не допустимых в именах файлов Windows/Linux.
    """
    cleaned = re.sub(r'[\\/*?:"<>|]', '_', code)
    cleaned = cleaned.strip('. ')
    return cleaned if cleaned else "set_code"


def perform_aggregation(parent_file, child_files, items_per_parent, output_dir=None, confirm_partial_callback=None):
    """
    Выполняет логику виртуальной агрегации.

    :param parent_file: Путь к TXT файлу с кодами наборов (родительские)
    :param child_files: Список путей к TXT файлам с кодами вложений (дочерние)
    :param items_per_parent: Количество вложений на один набор (int)
    :param output_dir: Директория для результатов. Если None, создается новая папке с меткой времени.
    :param confirm_partial_callback: Функция обратного вызова (msg: str) -> bool для подтверждения неполной агрегации.
    :return: (output_dir, created_files_count, total_children_used)
    """
    if items_per_parent <= 0:
        raise ValueError("Количество вложений должно быть больше 0.")

    if not parent_file or not os.path.exists(parent_file):
        raise ValueError("Файл кодов набора не выбран или не существует.")

    if not child_files:
        raise ValueError("Не выбраны файлы кодов вложений.")

    parent_codes = read_codes(parent_file)
    if not parent_codes:
        raise ValueError("Файл с кодами наборов не содержит кодов.")

    all_child_codes = []
    for cf in child_files:
        if os.path.exists(cf):
            all_child_codes.extend(read_codes(cf))

    if not all_child_codes:
        raise ValueError("Файлы кодов вложений не содержат данных.")

    required_children = len(parent_codes) * items_per_parent
    actual_available = len(all_child_codes)

    if actual_available < required_children:
        actual_sets = actual_available // items_per_parent
        msg = (f"Внимание: Недостаточно кодов вложений!\n\n"
               f"Требуется кодов вложений: {required_children} (для {len(parent_codes)} наборов по {items_per_parent} шт.)\n"
               f"Доступно кодов вложений: {actual_available}\n"
               f"Будет сформировано только {actual_sets} полных наборов.\n\n"
               f"Продолжить агрегацию?")
        if confirm_partial_callback is not None:
            if not confirm_partial_callback(msg):
                return None, 0, 0
        parent_codes = parent_codes[:actual_sets]

    if not parent_codes:
        raise ValueError("Недостаточно кодов вложений даже для одного полного набора.")

    if output_dir is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = os.path.join(os.getcwd(), f"aggregation_results_{timestamp}")

    os.makedirs(output_dir, exist_ok=True)

    created_files_count = 0
    used_filenames = set()
    child_index = 0

    for parent in parent_codes:
        base_name = clean_filename(parent)
        filename = f"{base_name}.txt"
        filepath = os.path.join(output_dir, filename)

        counter = 1
        while filename.lower() in used_filenames or os.path.exists(filepath):
            filename = f"{base_name}_{counter}.txt"
            filepath = os.path.join(output_dir, filename)
            counter += 1

        used_filenames.add(filename.lower())

        attachments = all_child_codes[child_index : child_index + items_per_parent]
        child_index += items_per_parent

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(parent + '\n')
            for att in attachments:
                f.write(att + '\n')

        created_files_count += 1

    return output_dir, created_files_count, child_index


if HAS_TKINTER:
    class AggregationApp:
        def __init__(self, root):
            self.root = root
            self.root.title("Виртуальная агрегация кодов маркировки")
            self.root.geometry("650x550")
            self.root.minsize(550, 480)

            self.parent_file = ""
            self.child_files = []

            self._create_widgets()

        def _create_widgets(self):
            padding = {'padx': 10, 'pady': 5}

            # Frame 1: Parent file selection
            frame_parent = ttk.LabelFrame(self.root, text=" 1. Файл кодов наборов (родительские) ")
            frame_parent.pack(fill="x", **padding)

            self.lbl_parent = ttk.Label(frame_parent, text="Файл не выбран", wraplength=480)
            self.lbl_parent.pack(side="left", fill="x", expand=True, padx=5, pady=5)

            btn_parent = ttk.Button(frame_parent, text="Обзор...", command=self.select_parent_file)
            btn_parent.pack(side="right", padx=5, pady=5)

            # Frame 2: Items count per parent
            frame_count = ttk.LabelFrame(self.root, text=" 2. Количество вложений в один набор ")
            frame_count.pack(fill="x", **padding)

            lbl_count = ttk.Label(frame_count, text="Число вложений на 1 набор:")
            lbl_count.pack(side="left", padx=5, pady=5)

            self.spin_count = ttk.Spinbox(frame_count, from_=1, to=10000, width=10)
            self.spin_count.set(10)
            self.spin_count.pack(side="left", padx=5, pady=5)

            # Frame 3: Child files selection
            frame_child = ttk.LabelFrame(self.root, text=" 3. Файлы кодов вложений (дочерние) ")
            frame_child.pack(fill="x", **padding)

            self.lbl_child = ttk.Label(frame_child, text="Файлы не выбраны", wraplength=480)
            self.lbl_child.pack(side="left", fill="x", expand=True, padx=5, pady=5)

            btn_child = ttk.Button(frame_child, text="Обзор...", command=self.select_child_files)
            btn_child.pack(side="right", padx=5, pady=5)

            # Frame 4: Run process
            frame_action = ttk.Frame(self.root)
            frame_action.pack(fill="x", **padding)

            btn_run = ttk.Button(frame_action, text="Запустить агрегацию", command=self.run_aggregation)
            btn_run.pack(fill="x", ipady=5)

            # Frame 5: Status / Log
            frame_log = ttk.LabelFrame(self.root, text=" Лог работы ")
            frame_log.pack(fill="both", expand=True, **padding)

            self.txt_log = tk.Text(frame_log, wrap="word", height=10)
            self.txt_log.pack(side="left", fill="both", expand=True, padx=5, pady=5)

            scrollbar = ttk.Scrollbar(frame_log, orient="vertical", command=self.txt_log.yview)
            scrollbar.pack(side="right", fill="y")
            self.txt_log.config(yscrollcommand=scrollbar.set)

        def log(self, message):
            self.txt_log.insert(tk.END, message + "\n")
            self.txt_log.see(tk.END)

        def select_parent_file(self):
            path = filedialog.askopenfilename(
                title="Выберите TXT файл с кодами наборов",
                filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
            )
            if path:
                self.parent_file = path
                self.lbl_parent.config(text=os.path.basename(path))
                self.log(f"Выбран файл кодов наборов: {path}")

        def select_child_files(self):
            paths = filedialog.askopenfilenames(
                title="Выберите TXT файлы с кодами вложений",
                filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
            )
            if paths:
                self.child_files = list(paths)
                self.lbl_child.config(text=f"Выбрано файлов: {len(paths)}")
                self.log(f"Выбрано файлов кодов вложений ({len(paths)}):")
                for p in paths:
                    self.log(f" - {p}")

        def run_aggregation(self):
            try:
                if not self.parent_file:
                    messagebox.showwarning("Предупреждение", "Пожалуйста, выберите файл с кодами наборов!")
                    return

                if not self.child_files:
                    messagebox.showwarning("Предупреждение", "Пожалуйста, выберите хотя бы один файл с кодами вложений!")
                    return

                try:
                    items_per_parent = int(self.spin_count.get())
                except ValueError:
                    messagebox.showerror("Ошибка", "Введите корректное число для количества вложений!")
                    return

                def confirm_cb(msg):
                    return messagebox.askyesno("Подтверждение", msg)

                self.log("Начало процесса агрегации...")
                out_dir, count, total_used = perform_aggregation(
                    parent_file=self.parent_file,
                    child_files=self.child_files,
                    items_per_parent=items_per_parent,
                    confirm_partial_callback=confirm_cb
                )

                if out_dir is None:
                    self.log("Процесс отменен пользователем.")
                    return

                self.log("--- Агрегация успешно завершена! ---")
                self.log(f"Создано файлов наборов: {count}")
                self.log(f"Всего использовано кодов вложений: {total_used}")
                self.log(f"Результаты сохранены в папку: {out_dir}")

                messagebox.showinfo("Успех", f"Агрегация завершена!\n\nСоздано наборов: {count}\nПапка: {out_dir}")

            except Exception as e:
                err_msg = f"Произошла ошибка при выполнении агрегации:\n{str(e)}"
                tb = traceback.format_exc()
                self.log(f"ОШИБКА: {e}")
                self.log(tb)
                messagebox.showerror("Ошибка", f"{err_msg}\n\nДетали:\n{tb}")


def main():
    if not HAS_TKINTER:
        print("Ошибка: Графический интерфейс Tkinter недоступен.")
        sys.exit(1)

    root = tk.Tk()
    app = AggregationApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
