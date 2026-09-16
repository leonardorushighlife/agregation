"""
Модуль виртуальной агрегации кодов маркировки.

Позволяет объединить код набора (родительский код) и коды содержимого (дочерние коды)
из текстовых файлов (TXT) в индивидуальные текстовые файлы для каждого набора.

Инструкция по сборке в исполняемый файл (EXE):
    pyinstaller --noconsole --onefile virtual_aggregation.py
"""

import os
import re
import sys
import traceback
from datetime import datetime


def read_codes(filepath):
    """
    Считывает коды маркировки из текстового файла.

    Пробует различные кодировки (utf-8-sig, utf-16, utf-8, cp1251).
    Возвращает список непустых строк с удаленными крайними пробельными символами.
    """
    encodings = ["utf-8-sig", "utf-16", "utf-8", "cp1251"]
    content = None

    for enc in encodings:
        try:
            with open(filepath, "r", encoding=enc) as f:
                content = f.read()
            break
        except (UnicodeError, LookupError):
            continue

    if content is None:
        raise ValueError(f"Не удалось прочитать файл {filepath} с использованием поддерживаемых кодировок.")

    codes = [line.strip() for line in content.splitlines() if line.strip()]
    return codes


def sanitize_filename(filename):
    """
    Очищает строку от недопустимых символов для использования в имени файла Windows/Linux.
    Заменяет \\ / : * ? " < > | на подчеркивание '_'.
    """
    return re.sub(r'[\\/:*?"<>|]', '_', filename)


def perform_aggregation(parent_file, child_files, items_per_parent, output_dir=None, confirm_callback=None):
    """
    Выполняет виртуальную агрегацию кодов маркировки.

    :param parent_file: Путь к TXT файлу с кодами наборов (родительские коды)
    :param child_files: Список путей к TXT файлам с кодами вложений (дочерние коды)
    :param items_per_parent: Количество вложений на 1 набор
    :param output_dir: Целевая папка для сохранения результатов (по умолчанию создается с меткой времени)
    :param confirm_callback: Функция обратного вызова (принимает message) -> bool для подтверждения при нехватке кодов
    :return: Кортеж (путь_к_папке_результатов, количество_созданных_файлов)
    """
    if items_per_parent <= 0:
        raise ValueError("Количество вложений на 1 набор должно быть больше 0.")

    parent_codes = read_codes(parent_file)
    if not parent_codes:
        raise ValueError(f"Файл родительских кодов {parent_file} не содержит кодов.")

    child_codes = []
    for c_file in child_files:
        child_codes.extend(read_codes(c_file))

    if not child_codes:
        raise ValueError("Выбранные файлы вложений не содержат кодов.")

    total_parents = len(parent_codes)
    required_children = total_parents * items_per_parent
    actual_children = len(child_codes)

    if actual_children < required_children:
        msg = (f"Внимание: Недостаточно кодов вложений!\n"
               f"Требуется: {required_children} (для {total_parents} наборов по {items_per_parent} вложений).\n"
               f"Доступно: {actual_children}.\n"
               f"Будет сформировано только полное число наборов: {actual_children // items_per_parent}.\n"
               f"Продолжить?")
        if confirm_callback is not None:
            if not confirm_callback(msg):
                return None, 0

    actual_sets = min(total_parents, actual_children // items_per_parent)
    if actual_sets == 0:
        raise ValueError("Недостаточно кодов вложений даже для одного полного набора.")

    if output_dir is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = os.path.join(os.getcwd(), f"aggregation_results_{timestamp}")

    os.makedirs(output_dir, exist_ok=True)

    used_filenames = {}
    created_files_count = 0

    for i in range(actual_sets):
        p_code = parent_codes[i]
        c_codes_subset = child_codes[i * items_per_parent : (i + 1) * items_per_parent]

        base_name = sanitize_filename(p_code)
        if not base_name:
            base_name = f"set_{i+1}"

        filename = f"{base_name}.txt"
        if filename in used_filenames:
            used_filenames[filename] += 1
            filename = f"{base_name}_{used_filenames[filename]}.txt"
        else:
            used_filenames[filename] = 0

        file_path = os.path.join(output_dir, filename)

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(p_code + "\n")
            for c_code in c_codes_subset:
                f.write(c_code + "\n")

        created_files_count += 1

    return output_dir, created_files_count


class VirtualAggregationApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Виртуальная агрегация наборов")
        self.root.geometry("650x550")
        self.root.resizable(True, True)

        self.parent_file = ""
        self.child_files = []

        self._create_widgets()

    def _create_widgets(self):
        import tkinter as tk
        from tkinter import ttk, filedialog, messagebox

        padding = {'padx': 10, 'pady': 5}

        # Выбор файла родительских кодов
        frame_parent = ttk.LabelFrame(self.root, text="1. Файл кодов маркировки наборов (родительский)")
        frame_parent.pack(fill="x", **padding)

        self.btn_select_parent = ttk.Button(frame_parent, text="Выбрать файл наборов...", command=self._select_parent_file)
        self.btn_select_parent.pack(side="left", **padding)

        self.lbl_parent = ttk.Label(frame_parent, text="Файл не выбран", wraplength=450)
        self.lbl_parent.pack(side="left", fill="x", expand=True, **padding)

        # Выбор файлов дочерних кодов
        frame_child = ttk.LabelFrame(self.root, text="2. Файлы кодов маркировки вложений (содержимого)")
        frame_child.pack(fill="both", expand=True, **padding)

        btn_frame = ttk.Frame(frame_child)
        btn_frame.pack(fill="x", **padding)

        self.btn_select_child = ttk.Button(btn_frame, text="Добавить файлы вложений...", command=self._select_child_files)
        self.btn_select_child.pack(side="left", **padding)

        self.btn_clear_child = ttk.Button(btn_frame, text="Очистить список", command=self._clear_child_files)
        self.btn_clear_child.pack(side="left", **padding)

        self.lst_child = tk.Listbox(frame_child, selectmode=tk.EXTENDED)
        self.lst_child.pack(fill="both", expand=True, **padding)

        # Параметр количества вложений
        frame_count = ttk.LabelFrame(self.root, text="3. Количество вложений в 1 набор")
        frame_count.pack(fill="x", **padding)

        ttk.Label(frame_count, text="Количество кодов содержимого на 1 набор:").pack(side="left", **padding)
        self.spin_count = ttk.Spinbox(frame_count, from_=1, to=10000, width=10)
        self.spin_count.set(10)
        self.spin_count.pack(side="left", **padding)

        # Кнопка запуска агрегации
        frame_action = ttk.Frame(self.root)
        frame_action.pack(fill="x", **padding)

        self.btn_run = ttk.Button(frame_action, text="Сформировать агрегированные файлы", command=self._run_aggregation)
        self.btn_run.pack(fill="x", ipady=5, **padding)

    def _select_parent_file(self):
        from tkinter import filedialog
        path = filedialog.askopenfilename(
            title="Выберите TXT файл с кодами наборов",
            filetypes=[("Текстовые файлы", "*.txt"), ("Все файлы", "*.*")]
        )
        if path:
            self.parent_file = path
            self.lbl_parent.config(text=path)

    def _select_child_files(self):
        from tkinter import filedialog
        paths = filedialog.askopenfilenames(
            title="Выберите TXT файлы с кодами вложений",
            filetypes=[("Текстовые файлы", "*.txt"), ("Все файлы", "*.*")]
        )
        if paths:
            for p in paths:
                if p not in self.child_files:
                    self.child_files.append(p)
                    self.lst_child.insert("end", p)

    def _clear_child_files(self):
        self.child_files.clear()
        self.lst_child.delete(0, "end")

    def _run_aggregation(self):
        from tkinter import messagebox

        if not self.parent_file:
            messagebox.showwarning("Предупреждение", "Пожалуйста, выберите файл с кодами наборов.")
            return

        if not self.child_files:
            messagebox.showwarning("Предупреждение", "Пожалуйста, выберите хотя бы один файл с кодами вложений.")
            return

        try:
            count = int(self.spin_count.get())
            if count <= 0:
                raise ValueError()
        except ValueError:
            messagebox.showerror("Ошибка", "Количество вложений должно быть целым положительным числом.")
            return

        def confirm_cb(msg):
            return messagebox.askyesno("Подтверждение", msg)

        try:
            out_dir, num_created = perform_aggregation(
                parent_file=self.parent_file,
                child_files=self.child_files,
                items_per_parent=count,
                confirm_callback=confirm_cb
            )

            if out_dir and num_created > 0:
                messagebox.showinfo(
                    "Успех",
                    f"Агрегация успешно завершена!\n\n"
                    f"Создано файлов: {num_created}\n"
                    f"Папка с результатами:\n{out_dir}"
                )
        except Exception as e:
            messagebox.showerror("Ошибка агрегации", f"Произошла ошибка при выполнении агрегации:\n{str(e)}")


def main():
    try:
        import tkinter as tk
        from tkinter import messagebox

        root = tk.Tk()

        def custom_excepthook(exc_type, exc_value, exc_traceback):
            err_msg = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
            try:
                messagebox.showerror("Критическая ошибка", f"Произошла непредвиденная ошибка:\n\n{err_msg}")
            except Exception:
                pass
            sys.__excepthook__(exc_type, exc_value, exc_traceback)

        sys.excepthook = custom_excepthook

        app = VirtualAggregationApp(root)
        root.mainloop()
    except Exception as e:
        print(f"Ошибка запуска GUI: {e}")


if __name__ == "__main__":
    main()
