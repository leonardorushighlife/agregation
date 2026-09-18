"""
Скрипт для виртуальной агрегации кодов маркировки.
Позволяет группировать коды маркировки вложений под родительскими кодами наборов.

Инструкция по сборке в исполняемый файл (.exe) для Windows 8, 10, 11:
1. Установите PyInstaller:
   pip install pyinstaller
2. Выполните команду для сборки:
   pyinstaller --noconsole --onefile virtual_aggregation.py
3. Готовый файл virtual_aggregation.exe будет находиться в папке dist/
"""

import os
import re
import sys
import traceback
from datetime import datetime


def sanitize_filename(name: str) -> str:
    """
    Очищает строку от символов, недопустимых в именах файлов Windows/Linux.
    """
    if not name:
        return "unnamed"
    # Заменяем недопустимые символы \ / : * ? " < > | на подчеркивание
    sanitized = re.sub(r'[\\/:*?"<>|]', '_', name)
    # Удаляем управляющие символы
    sanitized = "".join(ch for ch in sanitized if ord(ch) >= 32)
    sanitized = sanitized.strip()
    return sanitized if sanitized else "unnamed"


def read_codes(file_path: str) -> list[str]:
    """
    Считывает строки из текстового файла с последовательным перебором кодировок:
    utf-8-sig, utf-16, utf-8, cp1251. Возвращает список очищенных непустых строк.
    """
    encodings = ["utf-8-sig", "utf-16", "utf-8", "cp1251"]
    lines = []

    for encoding in encodings:
        try:
            with open(file_path, "r", encoding=encoding) as f:
                content = f.read()
                lines = [line.strip() for line in content.splitlines() if line.strip()]
                return lines
        except (UnicodeError, LookupError):
            continue
        except Exception as e:
            raise e

    # Если ни одна кодировка не подошла, пробуем utf-8 с игнорированием ошибок
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()
        lines = [line.strip() for line in content.splitlines() if line.strip()]
    return lines


def perform_aggregation(
    parent_file: str,
    child_files: list[str],
    count_per_parent: int,
    output_dir: str = None,
    confirm_callback=None
) -> dict:
    """
    Выполняет виртуальную агрегацию:
    - Поочередно связывает родительский код с заданным количеством кодов вложений.
    - Создает папку результатов и сохраняет отдельный TXT для каждого набора.
    """
    if count_per_parent <= 0:
        raise ValueError("Количество вложений должно быть больше 0.")

    if not parent_file or not os.path.exists(parent_file):
        raise FileNotFoundError("Файл родительских кодов не найден.")

    if not child_files:
        raise ValueError("Не выбрано ни одного файла с кодами вложений.")

    for cf in child_files:
        if not os.path.exists(cf):
            raise FileNotFoundError(f"Файл кодов вложений не найден: {cf}")

    parent_codes = read_codes(parent_file)
    if not parent_codes:
        raise ValueError("Файл родительских кодов пуст.")

    child_codes = []
    for cf in child_files:
        child_codes.extend(read_codes(cf))

    if not child_codes:
        raise ValueError("Выбранные файлы кодов вложений не содержат данных.")

    total_required = len(parent_codes) * count_per_parent
    actual_sets = min(len(parent_codes), len(child_codes) // count_per_parent)

    if len(child_codes) < total_required:
        msg = (
            f"Внимание: Недостаточно кодов вложений!\n\n"
            f"Требуется: {total_required} (для {len(parent_codes)} наборов по {count_per_parent} шт.)\n"
            f"Имеется кодов вложений: {len(child_codes)}\n"
            f"Будет сформировано полных наборов: {actual_sets}\n\n"
            f"Продолжить?"
        )
        if confirm_callback:
            if not confirm_callback(msg):
                return {"status": "cancelled", "message": "Операция отменена пользователем."}

    if actual_sets == 0:
        raise ValueError(
            f"Недостаточно кодов вложений для формирования даже одного набора по {count_per_parent} шт."
        )

    if output_dir is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = f"aggregation_results_{timestamp}"

    os.makedirs(output_dir, exist_ok=True)

    used_filenames = {}
    created_files_count = 0

    child_idx = 0
    for p_idx in range(actual_sets):
        parent_code = parent_codes[p_idx]
        current_children = child_codes[child_idx : child_idx + count_per_parent]
        child_idx += count_per_parent

        base_name = sanitize_filename(parent_code)
        if base_name in used_filenames:
            used_filenames[base_name] += 1
            filename = f"{base_name}_{used_filenames[base_name]}.txt"
        else:
            used_filenames[base_name] = 0
            filename = f"{base_name}.txt"

        file_path = os.path.join(output_dir, filename)
        with open(file_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(parent_code + "\n")
            for c_code in current_children:
                f.write(c_code + "\n")

        created_files_count += 1

    return {
        "status": "success",
        "output_dir": output_dir,
        "parents_processed": actual_sets,
        "files_created": created_files_count,
        "total_children_used": created_files_count * count_per_parent,
    }


class VirtualAggregationApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Виртуальная агрегация кодов маркировки")
        self.root.geometry("650x520")
        self.root.minsize(550, 450)

        self.parent_file = ""
        self.child_files = []

        self._build_ui()

    def _build_ui(self):
        import tkinter as tk
        from tkinter import ttk

        style = ttk.Style(self.root)
        style.theme_use("clam")

        main_frame = ttk.Frame(self.root, padding=15)
        main_frame.pack(fill=tk.BOTH, expand=True)

        title_label = ttk.Label(
            main_frame,
            text="Виртуальная агрегация вложений в наборы",
            font=("Segoe UI", 14, "bold")
        )
        title_label.pack(anchor=tk.W, pady=(0, 15))

        # Секция 1: Родительский файл
        parent_frame = ttk.LabelFrame(main_frame, text=" 1. Файл кодов маркировки наборов (Родитель) ", padding=10)
        parent_frame.pack(fill=tk.X, pady=(0, 10))

        self.parent_path_var = tk.StringVar(value="Файл не выбран")
        parent_entry = ttk.Entry(parent_frame, textvariable=self.parent_path_var, state="readonly")
        parent_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))

        btn_select_parent = ttk.Button(parent_frame, text="Выбрать файл...", command=self.select_parent_file)
        btn_select_parent.pack(side=tk.RIGHT)

        # Секция 2: Количество вложений
        count_frame = ttk.LabelFrame(main_frame, text=" 2. Параметры агрегации ", padding=10)
        count_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(count_frame, text="Количество вложений на 1 набор:").pack(side=tk.LEFT, padx=(0, 10))
        self.count_var = tk.StringVar(value="1")
        count_spin = ttk.Spinbox(count_frame, from_=1, to=10000, textvariable=self.count_var, width=10)
        count_spin.pack(side=tk.LEFT)

        # Секция 3: Файлы вложений
        child_frame = ttk.LabelFrame(main_frame, text=" 3. Файлы кодов маркировки вложений (Дети) ", padding=10)
        child_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 15))

        btn_select_children = ttk.Button(child_frame, text="Выбрать файлы вложений...", command=self.select_child_files)
        btn_select_children.pack(anchor=tk.W, pady=(0, 5))

        list_container = ttk.Frame(child_frame)
        list_container.pack(fill=tk.BOTH, expand=True)

        self.child_listbox = tk.Listbox(list_container, selectmode=tk.EXTENDED)
        scrollbar = ttk.Scrollbar(list_container, orient=tk.VERTICAL, command=self.child_listbox.yview)
        self.child_listbox.config(yscrollcommand=scrollbar.set)

        self.child_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Секция 4: Запуск
        action_frame = ttk.Frame(main_frame)
        action_frame.pack(fill=tk.X)

        self.btn_run = ttk.Button(action_frame, text="Выполнить агрегацию", command=self.run_aggregation)
        self.btn_run.pack(fill=tk.X, ipady=5)

    def select_parent_file(self):
        from tkinter import filedialog
        file_path = filedialog.askopenfilename(
            title="Выберите TXT файл родительских кодов наборов",
            filetypes=[("Текстовые файлы (*.txt)", "*.txt"), ("Все файлы (*.*)", "*.*")]
        )
        if file_path:
            self.parent_file = file_path
            self.parent_path_var.set(file_path)

    def select_child_files(self):
        from tkinter import filedialog
        files = filedialog.askopenfilenames(
            title="Выберите TXT файлы кодов вложений",
            filetypes=[("Текстовые файлы (*.txt)", "*.txt"), ("Все файлы (*.*)", "*.*")]
        )
        if files:
            self.child_files = list(files)
            import tkinter as tk
            self.child_listbox.delete(0, tk.END)
            for f in self.child_files:
                self.child_listbox.insert(tk.END, os.path.basename(f))

    def confirm_callback(self, message: str) -> bool:
        from tkinter import messagebox
        return messagebox.askyesno("Подтверждение", message)

    def run_aggregation(self):
        from tkinter import messagebox

        if not self.parent_file:
            messagebox.showwarning("Предупреждение", "Пожалуйста, выберите файл родительских кодов.")
            return

        if not self.child_files:
            messagebox.showwarning("Предупреждение", "Пожалуйста, выберите файлы кодов вложений.")
            return

        try:
            count_per_parent = int(self.count_var.get().strip())
        except ValueError:
            messagebox.showerror("Ошибка", "Количество вложений должно быть целым числом.")
            return

        try:
            result = perform_aggregation(
                parent_file=self.parent_file,
                child_files=self.child_files,
                count_per_parent=count_per_parent,
                confirm_callback=self.confirm_callback
            )

            if result["status"] == "success":
                msg = (
                    f"Агрегация успешно завершена!\n\n"
                    f"Обработано наборов: {result['parents_processed']}\n"
                    f"Создано файлов: {result['files_created']}\n"
                    f"Использовано вложений: {result['total_children_used']}\n\n"
                    f"Папка с результатами:\n{os.path.abspath(result['output_dir'])}"
                )
                messagebox.showinfo("Успех", msg)
            elif result["status"] == "cancelled":
                messagebox.showinfo("Отмена", result.get("message", "Операция отменена."))
        except Exception as e:
            err_msg = f"Произошла ошибка при выполнении агрегации:\n\n{str(e)}"
            messagebox.showerror("Ошибка", err_msg)


def main():
    import tkinter as tk
    from tkinter import messagebox

    def handle_exception(exc_type, exc_value, exc_traceback):
        err = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        messagebox.showerror("Неперехваченное исключение", f"Произошла критическая ошибка:\n\n{err}")

    sys.excepthook = handle_exception

    root = tk.Tk()
    app = VirtualAggregationApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
