"""
Скрипт виртуальной агрегации кодов маркировки.

Инструкция по сборке в исполняемый файл (.exe):
1. Установите PyInstaller:
   pip install pyinstaller
2. Выполните команду сборки:
   pyinstaller --noconsole --onefile virtual_aggregation.py
3. Готовый файл virtual_aggregation.exe будет находится в папке dist/
"""

import os
import re
import sys
import traceback
from datetime import datetime

# Guarded Tkinter import to allow headless unit testing
try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
    HAS_TK = True
except ImportError:
    HAS_TK = False


def sanitize_filename(name: str) -> str:
    """Очищает строку для использования в качестве имени файла."""
    clean_str = re.sub(r'[\\/*?:"<>|]', '_', name.strip())
    clean_str = re.sub(r'[\r\n\t]', '', clean_str)
    return clean_str or "unnamed"


def read_codes(file_path: str) -> list[str]:
    """
    Считывает коды из текстового файла, проверяя популярные кодировки.
    Возвращает список непустых строк без внешних пробельных символов.
    """
    encodings = ['utf-8-sig', 'utf-16', 'utf-8', 'cp1251']
    for enc in encodings:
        try:
            with open(file_path, 'r', encoding=enc) as f:
                lines = f.readlines()
                codes = [line.strip() for line in lines if line.strip()]
                return codes
        except (UnicodeError, LookupError):
            continue
    # Если ни одна кодировка не подошла (или файл не текстовый), пробуем еще раз стандартно с заменой ошибок
    with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
        return [line.strip() for line in f.readlines() if line.strip()]


def perform_aggregation(parent_file: str, child_files: list[str], count_per_parent: int,
                        confirm_callback=None) -> tuple[str, int, int]:
    """
    Основная логика виртуальной агрегации.

    :param parent_file: Путь к файлу с родительскими кодами (наборы)
    :param child_files: Список путей к файлам с дочерними кодами (вложения)
    :param count_per_parent: Количество вложений на один набор
    :param confirm_callback: Функция обратного вызова для подтверждения при нехватке кодов
    :return: Кортеж (путь к созданной папке, количество сформированных наборов, общее число использованных вложений)
    """
    if not parent_file or not os.path.exists(parent_file):
        raise ValueError("Файл с кодами наборов не выбран или не существует.")

    if not child_files:
        raise ValueError("Не выбpaно ни одного файла с кодами вложений.")

    if count_per_parent <= 0:
        raise ValueError("Количество вложений должно быть больше нуля.")

    parent_codes = read_codes(parent_file)
    if not parent_codes:
        raise ValueError("Файл кодов наборов пуст.")

    child_codes = []
    for cf in child_files:
        if os.path.exists(cf):
            child_codes.extend(read_codes(cf))

    if not child_codes:
        raise ValueError("Файлы вложений не содержат валидных кодов.")

    total_parents = len(parent_codes)
    total_required_children = total_parents * count_per_parent

    if len(child_codes) < total_required_children:
        actual_sets = len(child_codes) // count_per_parent
        if actual_sets == 0:
            raise ValueError(
                f"Недостаточно кодов вложений ({len(child_codes)}) "
                f"даже для одного набора (требуется {count_per_parent})."
            )
        if confirm_callback:
            msg = (
                f"Внимание: Кодов вложений ({len(child_codes)}) недостаточно "
                f"для заполнения всех {total_parents} наборов (требуется {total_required_children}).\n\n"
                f"Будет сформировано только {actual_sets} полных наборов.\nПродолжить?"
            )
            if not confirm_callback(msg):
                raise InterruptedError("Операция отменена пользователем.")
        parent_codes = parent_codes[:actual_sets]

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    parent_dir = os.path.dirname(parent_file) or "."
    output_dir = os.path.join(parent_dir, f"aggregation_results_{timestamp}")
    os.makedirs(output_dir, exist_ok=True)

    created_files_count = 0
    used_children_count = 0
    used_filenames = set()

    for i, p_code in enumerate(parent_codes):
        start_idx = i * count_per_parent
        end_idx = start_idx + count_per_parent
        current_children = child_codes[start_idx:end_idx]

        if len(current_children) < count_per_parent:
            break

        base_filename = sanitize_filename(p_code)
        filename = f"{base_filename}.txt"
        counter = 1
        while filename in used_filenames:
            filename = f"{base_filename}_{counter}.txt"
            counter += 1
        used_filenames.add(filename)

        file_path = os.path.join(output_dir, filename)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(p_code + "\n")
            for c_code in current_children:
                f.write(c_code + "\n")

        created_files_count += 1
        used_children_count += len(current_children)

    return output_dir, created_files_count, used_children_count


class AggregationApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Виртуальная Агрегация Кодов Маркировки")
        self.root.geometry("650x520")
        self.root.minsize(550, 450)

        self.parent_file_path = ""
        self.child_file_paths = []

        self._build_ui()

    def _build_ui(self):
        style = ttk.Style()
        style.theme_use('clam')

        main_frame = ttk.Frame(self.root, padding=15)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 1. Выбор файла наборов
        group_parent = ttk.LabelFrame(main_frame, text=" 1. Коды маркировки набора (Родитель) ", padding=10)
        group_parent.pack(fill=tk.X, pady=5)

        self.lbl_parent = ttk.Label(group_parent, text="Файл не выбран", foreground="gray")
        self.lbl_parent.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

        btn_parent = ttk.Button(group_parent, text="Выбрать файл...", command=self.select_parent_file)
        btn_parent.pack(side=tk.RIGHT)

        # 2. Количество вложений
        group_count = ttk.LabelFrame(main_frame, text=" 2. Параметры агрегации ", padding=10)
        group_count.pack(fill=tk.X, pady=5)

        ttk.Label(group_count, text="Количество вложений на 1 набор:").pack(side=tk.LEFT, padx=5)
        self.ent_count = ttk.Entry(group_count, width=10)
        self.ent_count.insert(0, "4")
        self.ent_count.pack(side=tk.LEFT, padx=5)

        # 3. Выбор файлов вложений
        group_children = ttk.LabelFrame(main_frame, text=" 3. Коды маркировки вложений (Дочерние) ", padding=10)
        group_children.pack(fill=tk.BOTH, expand=True, pady=5)

        btn_children = ttk.Button(group_children, text="Добавить TXT файлы вложений...", command=self.select_child_files)
        btn_children.pack(anchor=tk.NE, pady=(0, 5))

        self.lst_children = tk.Listbox(group_children, selectmode=tk.EXTENDED)
        self.lst_children.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)

        scrollbar = ttk.Scrollbar(group_children, orient=tk.VERTICAL, command=self.lst_children.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.lst_children.config(yscrollcommand=scrollbar.set)

        # Кнопка очистки списка дочерних файлов
        btn_clear = ttk.Button(group_children, text="Очистить список", command=self.clear_child_files)
        btn_clear.pack(anchor=tk.SE, pady=(5, 0))

        # 4. Выполнение
        btn_run = ttk.Button(main_frame, text="Выполнить виртуальную агрегацию", command=self.run_aggregation)
        btn_run.pack(fill=tk.X, pady=15, ipady=5)

    def select_parent_file(self):
        filename = filedialog.askopenfilename(
            title="Выберите файл с кодами наборов",
            filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")]
        )
        if filename:
            self.parent_file_path = filename
            self.lbl_parent.config(text=os.path.basename(filename), foreground="black")

    def select_child_files(self):
        filenames = filedialog.askopenfilenames(
            title="Выберите TXT файлы с кодами вложений",
            filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")]
        )
        if filenames:
            for fn in filenames:
                if fn not in self.child_file_paths:
                    self.child_file_paths.append(fn)
                    self.lst_children.insert(tk.END, os.path.basename(fn))

    def clear_child_files(self):
        self.child_file_paths.clear()
        self.lst_children.delete(0, tk.END)

    def run_aggregation(self):
        try:
            cnt_str = self.ent_count.get().strip()
            if not cnt_str.isdigit():
                messagebox.showerror("Ошибка", "Количество вложений должно быть целым положительным числом.")
                return
            count_per_parent = int(cnt_str)

            out_dir, num_sets, num_children = perform_aggregation(
                self.parent_file_path,
                self.child_file_paths,
                count_per_parent,
                confirm_callback=messagebox.askyesno
            )

            messagebox.showinfo(
                "Успех",
                f"Виртуальная агрегация успешно завершена!\n\n"
                f"Создано наборов (файлов): {num_sets}\n"
                f"Использовано вложений: {num_children}\n\n"
                f"Результаты сохранены в папке:\n{out_dir}"
            )

        except InterruptedError:
            pass
        except Exception as e:
            err_msg = traceback.format_exc()
            messagebox.showerror("Ошибка при агрегации", f"{str(e)}\n\nПодробности:\n{err_msg[:300]}")


def show_uncaught_exception(exctype, value, tb):
    err_text = "".join(traceback.format_exception(exctype, value, tb))
    if HAS_TK:
        try:
            messagebox.showerror("Критическая ошибка", f"Произошла непредвиденная ошибка:\n{err_text}")
        except Exception:
            pass
    print(err_text, file=sys.stderr)


sys.excepthook = show_uncaught_exception


def main():
    if not HAS_TK:
        print(" Ошибка: Графический интерфейс Tkinter недоступен.", file=sys.stderr)
        sys.exit(1)
    root = tk.Tk()
    app = AggregationApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
