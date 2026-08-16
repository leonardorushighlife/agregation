"""
Модуль виртуальной агрегации кодов маркировки.

Инструкция по сборке в EXE с помощью PyInstaller:
1. Установите PyInstaller:
   pip install pyinstaller
2. Выполните команду сборки в консоли:
   pyinstaller --noconsole --onefile virtual_aggregation.py
3. Готовый исполняемый файл будет находится в папке dist/virtual_aggregation.exe
"""

import os
import re
import sys
import traceback
from datetime import datetime

# Guarded import of tkinter for headless testing compatibility
try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
    HAS_TKINTER = True
except ImportError:
    HAS_TKINTER = False


def sanitize_filename(name: str) -> str:
    """
    Очищает строку от символов, недопустимых в именах файлов Windows/Linux.
    Заменяет символы \\ / : * ? " < > | на символ подчеркивания.
    """
    cleaned = re.sub(r'[\\/:*?"<>|]', '_', name.strip())
    # Удаляем управляющие символы
    cleaned = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', cleaned)
    return cleaned if cleaned else "unnamed"


def read_codes(file_path: str) -> list:
    """
    Считывает строки из текстового файла с каскадным перебором кодировок:
    UTF-8-SIG, UTF-16, UTF-8, CP1251.
    Возвращает список непустых очищенных строк (кодов).
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


def perform_aggregation(parent_file: str, child_files: list, count_per_parent: int,
                        output_dir: str = None, confirm_callback=None) -> dict:
    """
    Выполняет виртуальную агрегацию кодов.

    :param parent_file: Путь к TXT файлу с кодами наборов (родительские коды)
    :param child_files: Список путей к TXT файлам с кодами вложений (дочерние коды)
    :param count_per_parent: Количество вложений на один набор
    :param output_dir: Целевая директория для результатов. Если None, создается новая папка
    :param confirm_callback: Функция обратного вызова для подтверждения при нехватке кодов вложений.
                             Принимает (available_children, required_children, possible_sets).
                             Должна возвращать True для продолжения или False для отмены.
    :return: Словарь с результатами выполнения (status, created_files, output_dir, stats)
    """
    if count_per_parent <= 0:
        raise ValueError("Количество вложений должно быть больше 0.")

    parent_codes = read_codes(parent_file)
    if not parent_codes:
        raise ValueError("Файл с кодами наборов свободен от кодов или пуст.")

    all_child_codes = []
    for c_file in child_files:
        all_child_codes.extend(read_codes(c_file))

    if not all_child_codes:
        raise ValueError("Файлы с кодами вложений не содержат данных.")

    total_parents = len(parent_codes)
    total_children = len(all_child_codes)
    required_children = total_parents * count_per_parent

    if total_children < required_children:
        possible_sets = total_children // count_per_parent
        if confirm_callback is not None:
            approved = confirm_callback(total_children, required_children, possible_sets)
            if not approved:
                return {"status": "cancelled", "created_files": [], "output_dir": None}
        actual_sets = possible_sets
    else:
        actual_sets = total_parents

    if actual_sets == 0:
        raise ValueError(f"Недостаточно кодов вложений ({total_children}) даже для создания 1 полного набора (требуется {count_per_parent}).")

    if output_dir is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = os.path.abspath(f"aggregation_results_{timestamp}")

    os.makedirs(output_dir, exist_ok=True)

    created_files = []
    used_filenames = set()

    for i in range(actual_sets):
        p_code = parent_codes[i]
        start_idx = i * count_per_parent
        c_codes = all_child_codes[start_idx : start_idx + count_per_parent]

        base_name = sanitize_filename(p_code)
        filename = f"{base_name}.txt"
        filepath = os.path.join(output_dir, filename)

        # Обработка коллизий имен файлов
        suffix_counter = 1
        while filepath.lower() in used_filenames or os.path.exists(filepath):
            filename = f"{base_name}_{suffix_counter}.txt"
            filepath = os.path.join(output_dir, filename)
            suffix_counter += 1

        used_filenames.add(filepath.lower())

        # Запись в UTF-8 без BOM
        with open(filepath, 'w', encoding='utf-8', newline='\n') as out_f:
            out_f.write(p_code + '\n')
            for child in c_codes:
                out_f.write(child + '\n')

        created_files.append(filepath)

    return {
        "status": "success",
        "created_files": created_files,
        "output_dir": output_dir,
        "stats": {
            "parents_processed": actual_sets,
            "children_used": actual_sets * count_per_parent,
            "total_parents_available": total_parents,
            "total_children_available": total_children
        }
    }


class VirtualAggregationApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Виртуальная Агрегация Кодов Маркировки")
        self.root.geometry("650x550")
        self.root.minsize(600, 500)

        self.parent_file_path = tk.StringVar()
        self.child_file_paths = [tk.StringVar(), tk.StringVar(), tk.StringVar()]
        self.items_per_set = tk.StringVar(value="10")

        self._build_ui()

    def _build_ui(self):
        main_frame = ttk.Frame(self.root, padding=15)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Инструкция / Заголовок
        header_label = ttk.Label(
            main_frame,
            text="Виртуальная Агрегация Наборов",
            font=("Arial", 14, "bold")
        )
        header_label.pack(anchor=tk.W, pady=(0, 10))

        # Выбор файла наборов (родитель)
        parent_group = ttk.LabelFrame(main_frame, text=" 1. Файл кодов маркировки НАБОРА (1 файл) ", padding=10)
        parent_group.pack(fill=tk.X, pady=(0, 10))

        p_entry = ttk.Entry(parent_group, textvariable=self.parent_file_path)
        p_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        p_btn = ttk.Button(parent_group, text="Обзор...", command=self._select_parent_file)
        p_btn.pack(side=tk.RIGHT)

        # Выбор количества вложений
        count_group = ttk.LabelFrame(main_frame, text=" 2. Параметры агрегации ", padding=10)
        count_group.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(count_group, text="Количество вложений в один набор:").pack(side=tk.LEFT, padx=(0, 10))
        count_entry = ttk.Spinbox(count_group, from_=1, to=1000, textvariable=self.items_per_set, width=10)
        count_entry.pack(side=tk.LEFT)

        # Выбор файлов вложений (3 файла)
        child_group = ttk.LabelFrame(main_frame, text=" 3. Файлы кодов маркировки ВЛОЖЕНИЙ (3 файла) ", padding=10)
        child_group.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        for i in range(3):
            sub_frame = ttk.Frame(child_group)
            sub_frame.pack(fill=tk.X, pady=3)

            ttk.Label(sub_frame, text=f"Файл вложений #{i+1}:", width=18).pack(side=tk.LEFT)
            c_entry = ttk.Entry(sub_frame, textvariable=self.child_file_paths[i])
            c_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
            c_btn = ttk.Button(sub_frame, text="Обзор...", command=lambda idx=i: self._select_child_file(idx))
            c_btn.pack(side=tk.RIGHT)

        # Кнопка быстрой загрузки 3 файлов вложений сразу
        multi_btn = ttk.Button(child_group, text="Выбрать сразу 3 файла вложений...", command=self._select_multiple_child_files)
        multi_btn.pack(anchor=tk.E, pady=(5, 0))

        # Панель управления (Запуск)
        bottom_frame = ttk.Frame(main_frame)
        bottom_frame.pack(fill=tk.X, pady=(10, 0))

        self.run_btn = ttk.Button(bottom_frame, text="Выполнить виртуальную агрегацию", command=self._start_aggregation)
        self.run_btn.pack(fill=tk.X, ipady=8)

    def _select_parent_file(self):
        file_path = filedialog.askopenfilename(
            title="Выберите файл кодов маркировки НАБОРА",
            filetypes=[("Текстовые файлы", "*.txt"), ("Все файлы", "*.*")]
        )
        if file_path:
            self.parent_file_path.set(file_path)

    def _select_child_file(self, index: int):
        file_path = filedialog.askopenfilename(
            title=f"Выберите файл кодов вложений #{index+1}",
            filetypes=[("Текстовые файлы", "*.txt"), ("Все файлы", "*.*")]
        )
        if file_path:
            self.child_file_paths[index].set(file_path)

    def _select_multiple_child_files(self):
        files = filedialog.askopenfilenames(
            title="Выберите 3 файла кодов маркировки вложений",
            filetypes=[("Текстовые файлы", "*.txt"), ("Все файлы", "*.*")]
        )
        if files:
            for i in range(min(len(files), 3)):
                self.child_file_paths[i].set(files[i])

    def _confirm_partial(self, available, required, possible_sets):
        msg = (
            f"Недостаточно кодов вложений для агрегации всех наборов!\n\n"
            f"• Доступно вложений: {available}\n"
            f"• Требуется для всех наборов: {required}\n\n"
            f"Будет создано {possible_sets} полных наборов.\n"
            f"Продолжить?"
        )
        return messagebox.askyesno("Подтверждение частичной агрегации", msg, parent=self.root)

    def _start_aggregation(self):
        parent_file = self.parent_file_path.get().strip()
        if not parent_file or not os.path.exists(parent_file):
            messagebox.showerror("Ошибка", "Укажите существующий файл кодов набора!", parent=self.root)
            return

        child_files = [path.get().strip() for path in self.child_file_paths if path.get().strip()]
        if not child_files:
            messagebox.showerror("Ошибка", "Укажите хотя бы один файл кодов вложений!", parent=self.root)
            return

        for c_file in child_files:
            if not os.path.exists(c_file):
                messagebox.showerror("Ошибка", f"Файл вложений не найден:\n{c_file}", parent=self.root)
                return

        try:
            count = int(self.items_per_set.get().strip())
            if count <= 0:
                raise ValueError()
        except ValueError:
            messagebox.showerror("Ошибка", "Количество вложений должно быть целым положительным числом!", parent=self.root)
            return

        try:
            res = perform_aggregation(
                parent_file=parent_file,
                child_files=child_files,
                count_per_parent=count,
                confirm_callback=self._confirm_partial
            )

            if res["status"] == "cancelled":
                messagebox.showinfo("Отмена", "Операция отменена пользователем.", parent=self.root)
                return

            stats = res["stats"]
            success_msg = (
                f"Виртуальная агрегация успешно завершена!\n\n"
                f"• Обработано наборов: {stats['parents_processed']}\n"
                f"• Использовано вложений: {stats['children_used']}\n"
                f"• Папка с результатами:\n{res['output_dir']}"
            )
            messagebox.showinfo("Успех", success_msg, parent=self.root)

        except Exception as e:
            err_details = traceback.format_exc()
            messagebox.showerror("Ошибка агрегации", f"Произошла ошибка при выполнении агрегации:\n\n{e}\n\nДетали:\n{err_details}", parent=self.root)


def main():
    if not HAS_TKINTER:
        print("Ошибка: Графический интерфейс Tkinter недоступен в данной среде.")
        sys.exit(1)

    root = tk.Tk()
    app = VirtualAggregationApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
