"""
Скрипт для виртуальной агрегации кодов маркировки.

Инструкция по сборке в исполняемый файл (.exe):
1. Установите PyInstaller, если он еще не установлен:
   pip install pyinstaller
2. Выполните команду для сборки файла .exe:
   pyinstaller --noconsole --onefile virtual_aggregation.py
3. Готовый исполняемый файл будет находиться в папке 'dist'.
"""

import datetime
import os
import re
import sys
import traceback

# Ленивый импорт tkinter для возможности тестирования без GUI
try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
    HAS_TKINTER = True
except ImportError:
    HAS_TKINTER = False


def sanitize_filename(code: str) -> str:
    """Очищает код от символов, недопустимых в именах файлов Windows/Linux."""
    sanitized = re.sub(r'[\x00-\x1f\\/:*?"<>|]', '_', code.strip())
    # Если имя файла оказалось пустым после очистки
    if not sanitized:
        sanitized = "set_code"
    # Ограничение длины имени файла для Windows (макс. 200 символов)
    return sanitized[:200]


def read_codes(filepath: str) -> list[str]:
    """
    Считывает коды маркировки из файла с поддержкой различных кодировок.
    Возвращает список непустых строк без внешних пробельных символов.
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

    # Разбиение по строкам и фильтрация пустых строк
    lines = [line.strip() for line in content.splitlines() if line.strip()]
    return lines


def perform_aggregation(
    parent_file: str,
    child_files: list[str],
    count_per_parent: int,
    output_dir: str,
    confirm_callback=None
) -> tuple[int, int]:
    """
    Выполняет виртуальную агрегацию:
    - Считывает коды наборов из parent_file.
    - Считывает коды вложений из всех файлов child_files.
    - Для каждого набора берет count_per_parent кодов вложений.
    - Сохраняет результат в отдельный TXT файл в папку output_dir.

    Returns:
        tuple[int, int]: (количество сформированных наборов, общее количество агрегированных вложений)
    """
    if count_per_parent <= 0:
        raise ValueError("Количество вложений на один набор должно быть больше 0.")

    parent_codes = read_codes(parent_file)
    if not parent_codes:
        raise ValueError("Файл наборов не содержит кодов маркировки.")

    all_child_codes = []
    for cf in child_files:
        all_child_codes.extend(read_codes(cf))

    if not all_child_codes:
        raise ValueError("Файлы вложений не содержат кодов маркировки.")

    total_parents = len(parent_codes)
    needed_children = total_parents * count_per_parent
    actual_children = len(all_child_codes)

    # Проверка на достаточность кодов вложений
    if actual_children < needed_children:
        msg = (
            f"Внимание: Недостаточно кодов вложений.\n"
            f"Требуется: {needed_children} (для {total_parents} наборов по {count_per_parent} шт.)\n"
            f"Доступно: {actual_children}\n\n"
            f"Продолжить с имеющимся количеством?"
        )
        if confirm_callback is not None:
            if not confirm_callback(msg):
                return 0, 0
        else:
            # По умолчанию в безынтерфейсном режиме продолжаем с максимальным числом полных наборов
            pass

    os.makedirs(output_dir, exist_ok=True)

    actual_sets = min(total_parents, actual_children // count_per_parent)
    used_filenames = {}
    created_count = 0
    total_children_aggregated = 0

    for i in range(actual_sets):
        p_code = parent_codes[i]
        start_idx = i * count_per_parent
        end_idx = start_idx + count_per_parent
        c_codes = all_child_codes[start_idx:end_idx]

        base_name = sanitize_filename(p_code)

        # Обработка возможных дубликатов имен файлов
        if base_name in used_filenames:
            used_filenames[base_name] += 1
            filename = f"{base_name}_{used_filenames[base_name]}.txt"
        else:
            used_filenames[base_name] = 0
            filename = f"{base_name}.txt"

        file_path = os.path.join(output_dir, filename)

        with open(file_path, 'w', encoding='utf-8') as out_f:
            out_f.write(p_code + '\n')
            for c_code in c_codes:
                out_f.write(c_code + '\n')

        created_count += 1
        total_children_aggregated += len(c_codes)

    return created_count, total_children_aggregated


class VirtualAggregationApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Виртуальная Агрегация Кодов Маркировки")
        self.root.geometry("680x520")
        self.root.minsize(600, 480)

        self.parent_file_path = tk.StringVar()
        self.child_files_paths = []
        self.count_per_parent = tk.IntVar(value=4)

        self._build_ui()

    def _build_ui(self):
        main_frame = ttk.Frame(self.root, padding="15")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 1. Файл наборов (Parent)
        parent_group = ttk.LabelFrame(main_frame, text=" 1. Файл кодов маркировки наборов ", padding="10")
        parent_group.pack(fill=tk.X, pady=(0, 10))

        ttk.Entry(parent_group, textvariable=self.parent_file_path, state="readonly").pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        ttk.Button(parent_group, text="Обзор...", command=self._select_parent_file).pack(side=tk.RIGHT)

        # 2. Количество вложений
        count_group = ttk.LabelFrame(main_frame, text=" 2. Количество вложений на один набор ", padding="10")
        count_group.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(count_group, text="Вложений в наборе:").pack(side=tk.LEFT, padx=(0, 10))
        spin = ttk.Spinbox(count_group, from_=1, to=10000, textvariable=self.count_per_parent, width=10)
        spin.pack(side=tk.LEFT)

        # 3. Файлы вложений (Children)
        child_group = ttk.LabelFrame(main_frame, text=" 3. Файлы кодов маркировки вложений ", padding="10")
        child_group.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        btn_frame = ttk.Frame(child_group)
        btn_frame.pack(fill=tk.X, pady=(0, 5))
        ttk.Button(btn_frame, text="Добавить файлы...", command=self._select_child_files).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(btn_frame, text="Очистить список", command=self._clear_child_files).pack(side=tk.LEFT)

        self.child_listbox = tk.Listbox(child_group, selectmode=tk.EXTENDED)
        self.child_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(child_group, orient=tk.VERTICAL, command=self.child_listbox.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.child_listbox.config(yscrollcommand=scrollbar.set)

        # 4. Кнопка выполнения
        action_frame = ttk.Frame(main_frame)
        action_frame.pack(fill=tk.X, pady=(5, 0))

        self.run_btn = ttk.Button(action_frame, text="Сформировать файлы агрегации", command=self._run_aggregation)
        self.run_btn.pack(fill=tk.X, ipady=5)

    def _select_parent_file(self):
        filepath = filedialog.askopenfilename(
            title="Выберите файл с кодами наборов",
            filetypes=[("Текстовые файлы", "*.txt"), ("Все файлы", "*.*")]
        )
        if filepath:
            self.parent_file_path.set(filepath)

    def _select_child_files(self):
        filepaths = filedialog.askopenfilenames(
            title="Выберите файлы с кодами вложений",
            filetypes=[("Текстовые файлы", "*.txt"), ("Все файлы", "*.*")]
        )
        if filepaths:
            for fp in filepaths:
                if fp not in self.child_files_paths:
                    self.child_files_paths.append(fp)
                    self.child_listbox.insert(tk.END, fp)

    def _clear_child_files(self):
        self.child_files_paths.clear()
        self.child_listbox.delete(0, tk.END)

    def _run_aggregation(self):
        parent_file = self.parent_file_path.get().strip()
        if not parent_file:
            messagebox.showwarning("Предупреждение", "Пожалуйста, выберите файл с кодами маркировки наборов.")
            return

        if not self.child_files_paths:
            messagebox.showwarning("Предупреждение", "Пожалуйста, выберите хотя бы один файл с кодами вложений.")
            return

        try:
            count = self.count_per_parent.get()
            if count <= 0:
                raise ValueError
        except Exception:
            messagebox.showerror("Ошибка", "Количество вложений должно быть целым положительным числом.")
            return

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = os.path.join(os.getcwd(), f"aggregation_results_{timestamp}")

        def confirm_dialog(msg: str) -> bool:
            return messagebox.askyesno("Подтверждение", msg)

        try:
            sets_created, children_used = perform_aggregation(
                parent_file=parent_file,
                child_files=self.child_files_paths,
                count_per_parent=count,
                output_dir=output_dir,
                confirm_callback=confirm_dialog
            )

            if sets_created > 0:
                messagebox.showinfo(
                    "Успех",
                    f"Виртуальная агрегация завершена успешно!\n\n"
                    f"Создано файлов наборов: {sets_created}\n"
                    f"Агрегировано вложений: {children_used}\n"
                    f"Папка с результатами:\n{output_dir}"
                )
            else:
                messagebox.showwarning("Информация", "Агрегация была отменена или не было создано ни одного файла.")

        except Exception as e:
            err_msg = f"Произошла ошибка при выполнении агрегации:\n{str(e)}"
            messagebox.showerror("Ошибка", err_msg)


def global_exception_handler(exctype, value, tb):
    """Глобальный обработчик ошибок для отладки в графическом режиме."""
    err_text = "".join(traceback.format_exception(exctype, value, tb))
    if HAS_TKINTER:
        messagebox.showerror("Критическая ошибка", f"Произошла непредвиденная ошибка:\n\n{err_text}")
    else:
        print(f"Критическая ошибка:\n{err_text}", file=sys.stderr)


def main():
    if not HAS_TKINTER:
        print("Ошибка: Графическая библиотека Tkinter не доступна.", file=sys.stderr)
        sys.exit(1)

    sys.excepthook = global_exception_handler
    root = tk.Tk()
    app = VirtualAggregationApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
