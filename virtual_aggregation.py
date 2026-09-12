"""
Утилита для виртуальной агрегации кодов маркировки.

Инструкция по сборке в исполняемый файл (.exe) с помощью PyInstaller:
1. Установите PyInstaller (если еще не установлен):
   pip install pyinstaller
2. Выполните команду для сборки одного автономного exe-файла без консольного окна:
   pyinstaller --noconsole --onefile virtual_aggregation.py
3. Готовый exe-файл появится в папке dist/
"""

import os
import re
import sys
import traceback
from datetime import datetime

# Ленивый или условный импорт tkinter для поддержки headless-тестирования
try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
    HAS_TK = True
except ImportError:
    HAS_TK = False


def read_codes(filepath):
    """
    Считывает коды маркировки из текстового файла, проверяя популярные кодировки.
    Возвращает список непустых строк.
    """
    encodings = ["utf-8-sig", "utf-16", "utf-8", "cp1251"]
    lines = None

    for enc in encodings:
        try:
            with open(filepath, "r", encoding=enc) as f:
                lines = [line.strip() for line in f if line.strip()]
            break
        except (UnicodeError, LookupError):
            continue

    if lines is None:
        raise ValueError(f"Не удалось прочитать файл {filepath}. Проверьте кодировку файла.")

    return lines


def sanitize_filename(name):
    """
    Заменяет недопустимые символы для имени файла в Windows/Linux на нижнее подчеркивание.
    """
    return re.sub(r'[\\/:*?"<>|]', '_', name)


def perform_aggregation(parent_file, child_files, count_per_parent, output_dir=None, confirm_callback=None):
    """
    Основная логика виртуальной агрегации.

    :param parent_file: Путь к файлу с родительскими кодами (наборы)
    :param child_files: Список путей к файлам с дочерними кодами (вложения)
    :param count_per_parent: Количество вложений на один набор
    :param output_dir: Целевой каталог для результатов (если None, создается с меткой времени)
    :param confirm_callback: Функция обратного вызова при нехватке кодов вложений (возвращает bool)
    :return: Путь к директории с результатами и количество сформированных наборов
    """
    if not parent_file or not os.path.exists(parent_file):
        raise ValueError("Указанный файл родительских кодов не существует.")

    if not child_files:
        raise ValueError("Не выбpaн ни один файл с кодами вложений.")

    if count_per_parent <= 0:
        raise ValueError("Количество вложений должно быть больше 0.")

    parent_codes = read_codes(parent_file)
    if not parent_codes:
        raise ValueError("Файл родительских кодов пуст.")

    child_codes = []
    for cf in child_files:
        if os.path.exists(cf):
            child_codes.extend(read_codes(cf))

    if not child_codes:
        raise ValueError("Файлы вложений не содержат кодов.")

    total_parents = len(parent_codes)
    needed_children = total_parents * count_per_parent
    actual_children = len(child_codes)

    actual_sets = min(total_parents, actual_children // count_per_parent)

    if actual_sets < total_parents:
        msg = (
            f"Внимание: Недостаточно кодов вложений для всех наборов.\n"
            f"Требуется вложений: {needed_children} (для {total_parents} наборов по {count_per_parent} шт.).\n"
            f"Доступно вложений: {actual_children}.\n"
            f"Будет сформировано наборов: {actual_sets}.\n\n"
            f"Продолжить?"
        )
        if confirm_callback:
            if not confirm_callback(msg):
                return None, 0
        else:
            # Если нет callback, то продолжаем с имеющимися
            pass

    if actual_sets == 0:
        raise ValueError("Недостаточно кодов вложений даже для одного полного набора.")

    if output_dir is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = os.path.join(os.path.dirname(os.path.abspath(parent_file)), f"aggregation_results_{timestamp}")

    os.makedirs(output_dir, exist_ok=True)

    used_filenames = {}

    for i in range(actual_sets):
        p_code = parent_codes[i]
        c_codes = child_codes[i * count_per_parent : (i + 1) * count_per_parent]

        base_name = sanitize_filename(p_code)
        if not base_name:
            base_name = f"set_{i+1}"

        if base_name in used_filenames:
            used_filenames[base_name] += 1
            filename = f"{base_name}_{used_filenames[base_name]}.txt"
        else:
            used_filenames[base_name] = 0
            filename = f"{base_name}.txt"

        file_path = os.path.join(output_dir, filename)

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(p_code + "\n")
            for c_code in c_codes:
                f.write(c_code + "\n")

    return output_dir, actual_sets


class AggregationApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Виртуальная агрегация кодов маркировки")
        self.root.geometry("620x420")
        self.root.resizable(False, False)

        self.parent_file_path = ""
        self.child_file_paths = []

        self.create_widgets()

    def create_widgets(self):
        # Файл наборов (родительский)
        frame_parent = ttk.LabelFrame(self.root, text=" 1. Файл кодов маркировки наборов (родительский) ", padding=10)
        frame_parent.pack(fill="x", padx=15, pady=10)

        self.lbl_parent = ttk.Label(frame_parent, text="Файл не выбран", font=("Arial", 9, "italic"))
        self.lbl_parent.pack(side="left", fill="x", expand=True)

        btn_parent = ttk.Button(frame_parent, text="Выбрать файл", command=self.select_parent_file)
        btn_parent.pack(side="right")

        # Количество вложений
        frame_count = ttk.LabelFrame(self.root, text=" 2. Количество вложений в один набор ", padding=10)
        frame_count.pack(fill="x", padx=15, pady=5)

        ttk.Label(frame_count, text="Число вложений на один набор:").pack(side="left", padx=5)
        self.spin_count = ttk.Spinbox(frame_count, from_=1, to=1000, width=10)
        self.spin_count.set(1)
        self.spin_count.pack(side="left", padx=5)

        # Файлы вложений (дочерние)
        frame_child = ttk.LabelFrame(self.root, text=" 3. Файлы кодов маркировки вложений (дочерние) ", padding=10)
        frame_child.pack(fill="both", expand=True, padx=15, pady=10)

        self.lbl_child_info = ttk.Label(frame_child, text="Выбрано файлов: 0", font=("Arial", 9))
        self.lbl_child_info.pack(anchor="w")

        btn_child = ttk.Button(frame_child, text="Выбрать файлы TXT", command=self.select_child_files)
        btn_child.pack(anchor="e", pady=5)

        # Кнопка старта
        btn_start = ttk.Button(self.root, text="Запустить агрегацию", command=self.run_aggregation)
        btn_start.pack(pady=15, ipadx=20, ipady=5)

    def select_parent_file(self):
        filepath = filedialog.askopenfilename(
            title="Выберите файл с кодами наборов",
            filetypes=[("Текстовые файлы (*.txt)", "*.txt"), ("Все файлы (*.*)", "*.*")]
        )
        if filepath:
            self.parent_file_path = filepath
            self.lbl_parent.config(text=os.path.basename(filepath), font=("Arial", 9, "normal"))

    def select_child_files(self):
        filepaths = filedialog.askopenfilenames(
            title="Выберите файлы с кодами вложений",
            filetypes=[("Текстовые файлы (*.txt)", "*.txt"), ("Все файлы (*.*)", "*.*")]
        )
        if filepaths:
            self.child_file_paths = list(filepaths)
            self.lbl_child_info.config(text=f"Выбрано файлов: {len(self.child_file_paths)}")

    def run_aggregation(self):
        try:
            count = int(self.spin_count.get())
        except ValueError:
            messagebox.showerror("Ошибка", "Введите корректное число вложений.")
            return

        def confirm_cb(msg):
            return messagebox.askyesno("Подтверждение", msg)

        try:
            out_dir, created_sets = perform_aggregation(
                parent_file=self.parent_file_path,
                child_files=self.child_file_paths,
                count_per_parent=count,
                confirm_callback=confirm_cb
            )

            if out_dir and created_sets > 0:
                messagebox.showinfo(
                    "Успех",
                    f"Виртуальная агрегация успешно завершена!\n\n"
                    f"Сформировано наборов: {created_sets}\n"
                    f"Результаты сохранены в:\n{out_dir}"
                )
        except Exception as e:
            tb = traceback.format_exc()
            messagebox.showerror("Ошибка агрегации", f"{str(e)}\n\nПодробности:\n{tb}")


def global_exception_handler(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    tb_msg = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    if HAS_TK:
        messagebox.showerror("Критическая ошибка", f"Произошла непредвиденная ошибка:\n{exc_value}\n\n{tb_msg}")
    else:
        print(f"Критическая ошибка: {exc_value}\n{tb_msg}", file=sys.stderr)


if __name__ == "__main__":
    if HAS_TK:
        sys.excepthook = global_exception_handler
        root = tk.Tk()
        app = AggregationApp(root)
        root.mainloop()
    else:
        print("Ошибка: Tkinter не установлен или недоступен.")
