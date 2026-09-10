"""
Скрипт виртуальной агрегации кодов маркировки.

Инструкция по сборке в исполняемый файл (.exe) для Windows:
1. Установите PyInstaller (если ещё не установлен):
   pip install pyinstaller
2. Выполните команду сборки в консоли:
   pyinstaller --noconsole --onefile virtual_aggregation.py
3. Исполняемый файл появится в папке 'dist/virtual_aggregation.exe'.
"""

import os
import re
import sys
import datetime
import traceback
from typing import List, Tuple, Optional, Callable


def sanitize_filename(filename: str) -> str:
    """
    Очищает строку от символов, недопустимых в именах файлов Windows/Linux.
    """
    sanitized = re.sub(r'[\\/*?:"<>|]', '_', filename.strip())
    sanitized = "".join(ch for ch in sanitized if ord(ch) >= 32)
    return sanitized if sanitized else "set"


def read_codes_from_file(filepath: str) -> List[str]:
    """
    Читает коды маркировки из файла с поддержкой различных кодировок.
    Возвращает список непустых очищенных строк.
    """
    encodings = ["utf-8-sig", "utf-16", "utf-8", "cp1251"]
    lines = None

    for enc in encodings:
        try:
            with open(filepath, "r", encoding=enc) as f:
                lines = f.readlines()
            break
        except (UnicodeError, LookupError):
            continue

    if lines is None:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()

    codes = [line.strip() for line in lines if line.strip()]
    return codes


def read_codes_from_files(filepaths: List[str]) -> List[str]:
    """
    Читает и объединяет коды маркировки из нескольких файлов.
    """
    all_codes = []
    for fp in filepaths:
        if os.path.isfile(fp):
            codes = read_codes_from_file(fp)
            all_codes.extend(codes)
    return all_codes


def perform_aggregation(
    parent_file: str,
    child_files: List[str],
    items_per_set: int,
    output_base_dir: Optional[str] = None,
    confirm_callback: Optional[Callable[[str], bool]] = None
) -> Tuple[int, str]:
    """
    Выполняет виртуальную агрегацию кодов маркировки.

    :param parent_file: Путь к файлу с кодами наборов (родительские коды)
    :param child_files: Список путей к файлам с кодами вложений (дочерние коды)
    :param items_per_set: Количество вложений в один набор
    :param output_base_dir: Базовая директория для сохранения результатов
    :param confirm_callback: Callback-функция для подтверждения действий пользователем (возвращает True/False)
    :return: Кортеж (количество сформированных наборов, путь к папке с результатами)
    """
    if items_per_set <= 0:
        raise ValueError("Количество вложений на набор должно быть больше 0.")

    if not os.path.isfile(parent_file):
        raise FileNotFoundError(f"Файл с кодами наборов не найден: {parent_file}")

    parent_codes = read_codes_from_file(parent_file)
    if not parent_codes:
        raise ValueError("Файл с кодами наборов пуст или не содержит корректных строк.")

    child_codes = read_codes_from_files(child_files)
    if not child_codes:
        raise ValueError("Файлы вложений пусты или не содержат корректных строк.")

    total_parents = len(parent_codes)
    needed_children = total_parents * items_per_set
    available_children = len(child_codes)

    if available_children < items_per_set:
        raise ValueError(
            f"Недостаточно кодов вложений ({available_children}) даже для одного набора.\n"
            f"Требуется минимум {items_per_set} кодов."
        )

    if available_children < needed_children:
        msg = (
            f"Внимание: Недостаточно кодов вложений для всех наборов.\n"
            f"Доступно вложений: {available_children}\n"
            f"Требуется для {total_parents} наборов: {needed_children}\n"
            f"Будет сформировано полных наборов: {available_children // items_per_set}.\n"
            f"Продолжить?"
        )
        if confirm_callback:
            if not confirm_callback(msg):
                raise InterruptedError("Операция отменена пользователем.")

    # Создаём папку для результатов
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    folder_name = f"aggregation_results_{timestamp}"

    if output_base_dir:
        target_dir = os.path.join(output_base_dir, folder_name)
    else:
        target_dir = os.path.abspath(folder_name)

    os.makedirs(target_dir, exist_ok=True)

    actual_sets = min(total_parents, available_children // items_per_set)
    used_filenames = set()

    for i in range(actual_sets):
        p_code = parent_codes[i]
        start_idx = i * items_per_set
        c_codes = child_codes[start_idx : start_idx + items_per_set]

        base_name = sanitize_filename(p_code)
        filename = f"{base_name}.txt"
        filepath = os.path.join(target_dir, filename)

        # Обработка возможной коллизии имен файлов
        suffix = 1
        while filepath.lower() in used_filenames or os.path.exists(filepath):
            filename = f"{base_name}_{suffix}.txt"
            filepath = os.path.join(target_dir, filename)
            suffix += 1

        used_filenames.add(filepath.lower())

        with open(filepath, "w", encoding="utf-8", newline="\n") as f:
            f.write(p_code + "\n")
            for c_code in c_codes:
                f.write(c_code + "\n")

    return actual_sets, target_dir


# Попытка импортировать Tkinter для GUI режима
try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
    HAS_TKINTER = True
except ImportError:
    HAS_TKINTER = False


class VirtualAggregationApp:
    def __init__(self, root: "tk.Tk"):
        self.root = root
        self.root.title("Виртуальная Агрегация Наборов")
        self.root.geometry("650x520")
        self.root.minsize(550, 450)

        self.parent_file_path = ""
        self.child_file_paths = []

        self.create_widgets()

    def create_widgets(self):
        main_frame = ttk.Frame(self.root, padding="15 15 15 15")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 1. Выбор файла с кодами наборов
        group_parent = ttk.LabelFrame(main_frame, text=" 1. Файл с кодами наборов (Родительский) ", padding="10 10 10 10")
        group_parent.pack(fill=tk.X, pady=(0, 10))

        btn_parent = ttk.Button(group_parent, text="Выбрать файл наборов (.txt)", command=self.select_parent_file)
        btn_parent.pack(side=tk.LEFT, padx=(0, 10))

        self.lbl_parent_path = ttk.Label(group_parent, text="Файл не выбран", foreground="gray")
        self.lbl_parent_path.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # 2. Количество вложений в набор
        group_count = ttk.LabelFrame(main_frame, text=" 2. Параметры агрегации ", padding="10 10 10 10")
        group_count.pack(fill=tk.X, pady=(0, 10))

        lbl_items = ttk.Label(group_count, text="Количество вложений в 1 набор:")
        lbl_items.pack(side=tk.LEFT, padx=(0, 10))

        self.spin_count = ttk.Spinbox(group_count, from_=1, to=1000, width=10)
        self.spin_count.set(4)
        self.spin_count.pack(side=tk.LEFT)

        # 3. Выбор файлов с кодами вложений
        group_children = ttk.LabelFrame(main_frame, text=" 3. Файлы с кодами вложений (Содержимое) ", padding="10 10 10 10")
        group_children.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        frame_child_btn = ttk.Frame(group_children)
        frame_child_btn.pack(fill=tk.X, pady=(0, 5))

        btn_children = ttk.Button(frame_child_btn, text="Выбрать файлы вложений (.txt)...", command=self.select_child_files)
        btn_children.pack(side=tk.LEFT, padx=(0, 10))

        btn_clear_children = ttk.Button(frame_child_btn, text="Очистить список", command=self.clear_child_files)
        btn_clear_children.pack(side=tk.LEFT)

        # Список выбранных файлов
        list_frame = ttk.Frame(group_children)
        list_frame.pack(fill=tk.BOTH, expand=True)

        self.lst_children = tk.Listbox(list_frame, height=6)
        self.lst_children.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.lst_children.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.lst_children.config(yscrollcommand=scrollbar.set)

        # 4. Кнопка выполнения агрегации
        self.btn_run = ttk.Button(main_frame, text="Запустить агрегацию", command=self.run_aggregation)
        self.btn_run.pack(fill=tk.X, ipady=8, pady=(5, 0))

        # Состояние / Статус бар
        self.lbl_status = ttk.Label(main_frame, text="Готово к работе", relief=tk.SUNKEN, anchor=tk.W)
        self.lbl_status.pack(fill=tk.X, pady=(10, 0))

    def select_parent_file(self):
        path = filedialog.askopenfilename(
            title="Выберите файл с кодами маркировки наборов",
            filetypes=[("Текстовые файлы (*.txt)", "*.txt"), ("Все файлы (*.*)", "*.*")]
        )
        if path:
            self.parent_file_path = path
            self.lbl_parent_path.config(text=os.path.basename(path), foreground="black")
            self.lbl_status.config(text=f"Выбран файл наборов: {os.path.basename(path)}")

    def select_child_files(self):
        paths = filedialog.askopenfilenames(
            title="Выберите файлы с кодами маркировки вложений (можно выбрать несколько, например 3 файла)",
            filetypes=[("Текстовые файлы (*.txt)", "*.txt"), ("Все файлы (*.*)", "*.*")]
        )
        if paths:
            for p in paths:
                if p not in self.child_file_paths:
                    self.child_file_paths.append(p)
                    self.lst_children.insert(tk.END, p)
            self.lbl_status.config(text=f"Всего выбрано файлов вложений: {len(self.child_file_paths)}")

    def clear_child_files(self):
        self.child_file_paths.clear()
        self.lst_children.delete(0, tk.END)
        self.lbl_status.config(text="Список файлов вложений очищен")

    def confirm_callback(self, message: str) -> bool:
        return messagebox.askyesno("Подтверждение", message)

    def run_aggregation(self):
        if not self.parent_file_path:
            messagebox.showwarning("Ошибка ввода", "Пожалуйста, выберите файл с кодами наборов.")
            return

        if not self.child_file_paths:
            messagebox.showwarning("Ошибка ввода", "Пожалуйста, выберите хотя бы один файл с кодами вложений.")
            return

        try:
            items_per_set = int(self.spin_count.get())
            if items_per_set <= 0:
                raise ValueError()
        except ValueError:
            messagebox.showwarning("Ошибка ввода", "Количество вложений должно быть целым положительным числом.")
            return

        try:
            self.lbl_status.config(text="Выполняется агрегация...")
            self.root.update()

            count, out_dir = perform_aggregation(
                parent_file=self.parent_file_path,
                child_files=self.child_file_paths,
                items_per_set=items_per_set,
                confirm_callback=self.confirm_callback
            )

            msg = f"Успешно сформировано наборов: {count}\nРезультаты сохранены в папку:\n{out_dir}"
            self.lbl_status.config(text=f"Завершено: {count} наборов создано")
            messagebox.showinfo("Успех", msg)

        except InterruptedError:
            self.lbl_status.config(text="Операция отменена")
        except Exception as e:
            self.lbl_status.config(text="Произошла ошибка")
            messagebox.showerror("Ошибка агрегации", str(e))


def main():
    if not HAS_TKINTER:
        print("Ошибка: Графический интерфейс Tkinter недоступен в данной системе.")
        sys.exit(1)

    root = tk.Tk()
    app = VirtualAggregationApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
