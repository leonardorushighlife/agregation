"""
Скрипт для виртуальной агрегации кодов маркировки.

Инструкция по сборке в исполняемый файл (.exe):
1. Установите PyInstaller (если еще не установлен):
   pip install pyinstaller
2. Выполните команду сборки в консоли:
   pyinstaller --noconsole --onefile virtual_aggregation.py
3. Готовый исполняемый файл будет находиться в папке 'dist/virtual_aggregation.exe'.
"""

import sys
import os
import re
import datetime
import traceback

# Ленивый импорт tkinter для поддержки headless-режима при тестировании
try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
    TK_AVAILABLE = True
except ImportError:
    TK_AVAILABLE = False


def sanitize_filename(filename: str) -> str:
    """
    Очищает строку от недопустимых символов для использования в качестве имени файла в ОС Windows/Linux.
    """
    if not filename:
        return "unnamed"
    # Заменяем недопустимые символы на символ подчеркивания
    sanitized = re.sub(r'[\\/:*?"<>|]', '_', filename.strip())
    # Удаляем управляющие символы и пробелы по краям
    sanitized = re.sub(r'[\s]+', ' ', sanitized).strip()
    return sanitized if sanitized else "unnamed"


def read_codes(file_path: str) -> list:
    """
    Считывает маркировочные коды из текстового файла, перебирая популярные кодировки.
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
        except Exception as e:
            raise e
    raise ValueError(f"Не удалось прочитать файл {file_path} ни в одной из поддерживаемых кодировок.")


def perform_aggregation(parent_file: str, child_files: list, count_per_set: int, confirm_callback=None, output_parent_dir: str = ".") -> dict:
    """
    Выполняет виртуальную агрегацию родительских кодов и кодов вложений.

    :param parent_file: Путь к TXT файлу с родительскими кодами (наборы).
    :param child_files: Список путей к TXT файлам с кодами вложений.
    :param count_per_set: Количество кодов вложений на один набор.
    :param confirm_callback: Функция обратного вызова для подтверждения продолжения при нехватке кодов вложений.
                             Принимает (missing_count, available_sets). Возвращает bool.
    :param output_parent_dir: Базовая директория для создания целевой папки с результатами.
    :return: Словарь с результатами выполнения.
    """
    if count_per_set <= 0:
        raise ValueError("Количество вложений на набор должно быть больше 0.")

    parent_codes = read_codes(parent_file)
    if not parent_codes:
        raise ValueError("Файл родительских кодов пуст.")

    all_child_codes = []
    for cf in child_files:
        codes = read_codes(cf)
        all_child_codes.extend(codes)

    if not all_child_codes:
        raise ValueError("Файлы вложений не содержат кодов.")

    total_parents = len(parent_codes)
    total_required_children = total_parents * count_per_set
    total_available_children = len(all_child_codes)

    if total_available_children < total_required_children:
        missing_children = total_required_children - total_available_children
        available_sets = total_available_children // count_per_set
        if confirm_callback:
            user_confirmed = confirm_callback(missing_children, available_sets)
            if not user_confirmed:
                return {"status": "cancelled", "reason": "Отменено пользователем из-за недостаточного количества кодов."}

        # Ограничиваем число наборов дольно доступным кодам
        actual_sets = available_sets
    else:
        actual_sets = total_parents

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    folder_name = f"aggregation_results_{timestamp}"
    output_dir = os.path.join(output_parent_dir, folder_name)
    os.makedirs(output_dir, exist_ok=True)

    created_files_count = 0
    used_filenames = set()

    for i in range(actual_sets):
        parent_code = parent_codes[i]
        start_idx = i * count_per_set
        end_idx = start_idx + count_per_set
        set_children = all_child_codes[start_idx:end_idx]

        base_name = sanitize_filename(parent_code)
        filename = f"{base_name}.txt"

        # Разрешение коллизий имен файлов
        suffix_counter = 1
        while filename in used_filenames or os.path.exists(os.path.join(output_dir, filename)):
            filename = f"{base_name}_{suffix_counter}.txt"
            suffix_counter += 1

        used_filenames.add(filename)
        file_path = os.path.join(output_dir, filename)

        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(parent_code + '\n')
            for child_code in set_children:
                f.write(child_code + '\n')

        created_files_count += 1

    return {
        "status": "success",
        "output_dir": output_dir,
        "created_files": created_files_count,
        "total_children_used": created_files_count * count_per_set
    }


class VirtualAggregationApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Виртуальная агрегация кодов маркировки")
        self.root.geometry("650x520")
        self.root.minsize(600, 480)

        self.parent_file = ""
        self.child_files = []

        self._build_ui()

    def _build_ui(self):
        main_frame = ttk.Frame(self.root, padding="15")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Секция родительского файла
        parent_frame = ttk.LabelFrame(main_frame, text="1. Файл кодов маркировки наборов (родительские коды)", padding="10")
        parent_frame.pack(fill=tk.X, pady=5)

        self.btn_select_parent = ttk.Button(parent_frame, text="Выбрать файл (TXT)", command=self._select_parent_file)
        self.btn_select_parent.pack(side=tk.LEFT, padx=(0, 10))

        self.lbl_parent_file = ttk.Label(parent_frame, text="Файл не выбран", foreground="gray")
        self.lbl_parent_file.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Секция количества вложений
        count_frame = ttk.LabelFrame(main_frame, text="2. Настройки агрегации", padding="10")
        count_frame.pack(fill=tk.X, pady=5)

        ttk.Label(count_frame, text="Количество вложений на 1 набор:").pack(side=tk.LEFT, padx=(0, 10))
        self.entry_count = ttk.Entry(count_frame, width=10)
        self.entry_count.insert(0, "4")
        self.entry_count.pack(side=tk.LEFT)

        # Секция файлов вложений
        child_frame = ttk.LabelFrame(main_frame, text="3. Файлы кодов маркировки вложений (содержимое)", padding="10")
        child_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        child_btn_frame = ttk.Frame(child_frame)
        child_btn_frame.pack(fill=tk.X, pady=(0, 5))

        self.btn_select_children = ttk.Button(child_btn_frame, text="Добавить файлы (TXT)", command=self._select_child_files)
        self.btn_select_children.pack(side=tk.LEFT, padx=(0, 10))

        self.btn_clear_children = ttk.Button(child_btn_frame, text="Очистить список", command=self._clear_child_files)
        self.btn_clear_children.pack(side=tk.LEFT)

        self.listbox_children = tk.Listbox(child_frame, height=6)
        self.listbox_children.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(child_frame, orient=tk.VERTICAL, command=self.listbox_children.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.listbox_children.config(yscrollcommand=scrollbar.set)

        # Секция запуска
        action_frame = ttk.Frame(main_frame, padding="5")
        action_frame.pack(fill=tk.X, pady=10)

        self.btn_start = ttk.Button(action_frame, text="Запустить виртуальную агрегацию", command=self._start_aggregation)
        self.btn_start.pack(fill=tk.X, ipady=5)

    def _select_parent_file(self):
        file_path = filedialog.askopenfilename(
            title="Выберите файл кодов набора",
            filetypes=[("Текстовые файлы", "*.txt"), ("Все файлы", "*.*")]
        )
        if file_path:
            self.parent_file = file_path
            self.lbl_parent_file.config(text=os.path.basename(file_path), foreground="black")

    def _select_child_files(self):
        files = filedialog.askopenfilenames(
            title="Выберите файлы кодов вложений",
            filetypes=[("Текстовые файлы", "*.txt"), ("Все файлы", "*.*")]
        )
        if files:
            for f in files:
                if f not in self.child_files:
                    self.child_files.append(f)
                    self.listbox_children.insert(tk.END, os.path.basename(f))

    def _clear_child_files(self):
        self.child_files.clear()
        self.listbox_children.delete(0, tk.END)

    def _confirm_missing(self, missing_count: int, available_sets: int) -> bool:
        return messagebox.askyesno(
            "Недостаточно кодов вложений",
            f"Внимание!\nНе хватает {missing_count} кодов вложений для агрегации всех наборов.\n"
            f"С имеющимися кодами можно сформировать наборов: {available_sets}.\n\n"
            "Продолжить агрегацию только для доступного количества наборов?"
        )

    def _start_aggregation(self):
        if not self.parent_file:
            messagebox.showwarning("Ошибка", "Пожалуйста, выберите файл с кодами наборов.")
            return

        if not self.child_files:
            messagebox.showwarning("Ошибка", "Пожалуйста, выберите хотя бы один файл с кодами вложений.")
            return

        try:
            count_per_set = int(self.entry_count.get().strip())
        except ValueError:
            messagebox.showwarning("Ошибка", "Введите корректное число для количества вложений.")
            return

        try:
            res = perform_aggregation(
                parent_file=self.parent_file,
                child_files=self.child_files,
                count_per_set=count_per_set,
                confirm_callback=self._confirm_missing
            )

            if res.get("status") == "success":
                messagebox.showinfo(
                    "Успех",
                    f"Виртуальная агрегация успешно завершена!\n\n"
                    f"Создано файлов (наборов): {res['created_files']}\n"
                    f"Использовано вложений: {res['total_children_used']}\n"
                    f"Результаты сохранены в папку:\n{res['output_dir']}"
                )
            elif res.get("status") == "cancelled":
                messagebox.showinfo("Отмена", "Операция отменена пользователем.")
        except Exception as e:
            err_msg = traceback.format_exc()
            messagebox.showerror("Ошибка агрегации", f"Произошла ошибка:\n{e}\n\nПодробности:\n{err_msg}")


def main():
    if not TK_AVAILABLE:
        print("Ошибка: Tkinter недоступен в данной системе.")
        sys.exit(1)

    def handle_exception(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        err_msg = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        messagebox.showerror("Критическая ошибка", f"Произошла непредвиденная ошибка:\n\n{err_msg}")

    sys.excepthook = handle_exception

    root = tk.Tk()
    app = VirtualAggregationApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
