"""
Инструкция по сборке в исполняемый файл (EXE) для Windows 8, 10, 11:
1. Установите необходимые библиотеки (если они еще не установлены):
   pip install pyinstaller
2. Запустите следующую команду в терминале в папке со скриптом:
   pyinstaller --noconsole --onefile virtual_aggregation.py
3. После завершения сборки готовый файл virtual_aggregation.exe будет находиться в папке 'dist'.
"""

import os
import re
import sys
import traceback
from datetime import datetime

# Guarded/lazy imports of tkinter for headless testing support
try:
    import tkinter as tk
    from tkinter import filedialog, messagebox
except ImportError:
    tk = None
    filedialog = None
    messagebox = None


def read_codes_from_file(filepath):
    """
    Читает коды из файла, пробуя различные кодировки по очереди:
    UTF-8-SIG, UTF-16, UTF-8, CP1251.
    Возвращает список непустых строк.
    """
    encodings = ['utf-8-sig', 'utf-16', 'utf-8', 'cp1251']
    for enc in encodings:
        try:
            with open(filepath, 'r', encoding=enc) as f:
                content = f.read()
            # Успешно прочитали, разобьем на строки и очистим от пробелов
            lines = [line.strip() for line in content.splitlines() if line.strip()]
            return lines
        except (UnicodeDecodeError, LookupError):
            continue
    raise ValueError(f"Не удалось прочитать файл {filepath} с использованием поддерживаемых кодировок (UTF-8, UTF-16, CP1251).")


def sanitize_filename(name):
    r"""
    Очищает код набора для использования в качестве имени файла на Windows.
    Заменяет символы \ / : * ? " < > | на символ подчеркивания.
    """
    sanitized = re.sub(r'[\/\\\:\*\?\"<>\|]', '_', name)
    sanitized = sanitized.strip()
    if not sanitized:
        sanitized = "empty_code"
    return sanitized


def perform_aggregation(set_file, attachment_files, count_per_set, confirm_callback=None):
    """
    Выполняет виртуальную агрегацию кодов маркировки.

    :param set_file: путь к файлу с кодами наборов (родительские коды)
    :param attachment_files: список путей к файлам с кодами вложений (дочерние коды)
    :param count_per_set: количество вложений в один набор
    :param confirm_callback: функция обратного вызова для подтверждения продолжения при нехватке вложений.
                             Должна принимать (actual_attachments, needed_attachments) и возвращать bool.
    :return: (путь к созданной папке, количество успешно созданных наборов)
    """
    parent_codes = read_codes_from_file(set_file)

    attachment_codes = []
    for filepath in attachment_files:
        attachment_codes.extend(read_codes_from_file(filepath))

    if not parent_codes:
        raise ValueError("Файл с кодами наборов пуст.")
    if not attachment_codes:
        raise ValueError("Файлы с кодами вложений пусты.")

    needed_attachments = len(parent_codes) * count_per_set

    # Если кодов вложений меньше, чем требуется для всех наборов
    if len(attachment_codes) < needed_attachments:
        actual_sets = len(attachment_codes) // count_per_set
        if actual_sets == 0:
            raise ValueError(f"Недостаточно кодов вложений даже для одного набора (требуется {count_per_set}, найдено {len(attachment_codes)}).")

        if confirm_callback:
            proceed = confirm_callback(len(attachment_codes), needed_attachments)
            if not proceed:
                raise ValueError("Операция отменена пользователем из-за недостаточного количества кодов вложений.")

        # Ограничиваем количество обрабатываемых наборов
        parent_codes = parent_codes[:actual_sets]

    # Создание выходной папки с временным штампом
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = f"aggregation_results_{timestamp}"
    os.makedirs(output_dir, exist_ok=True)

    used_filenames = set()
    total_written = 0

    for i, parent_code in enumerate(parent_codes):
        start_idx = i * count_per_set
        end_idx = start_idx + count_per_set
        current_attachments = attachment_codes[start_idx:end_idx]

        # Очистка имени файла
        base_name = sanitize_filename(parent_code)
        # Ограничение длины имени файла во избежание проблем на Windows
        if len(base_name) > 120:
            base_name = base_name[:120]

        filename = f"{base_name}.txt"

        # Обработка коллизий имен файлов
        if filename.lower() in used_filenames:
            suffix = 1
            while f"{base_name}_{suffix}.txt".lower() in used_filenames:
                suffix += 1
            filename = f"{base_name}_{suffix}.txt"

        used_filenames.add(filename.lower())

        file_path = os.path.join(output_dir, filename)

        # Запись в UTF-8 без BOM
        with open(file_path, 'w', encoding='utf-8', newline='\n') as f:
            f.write(parent_code + "\n")
            for att in current_attachments:
                f.write(att + "\n")

        total_written += 1

    return output_dir, total_written


class AggregationApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Виртуальная агрегация")
        self.root.geometry("600x480")
        self.root.minsize(500, 400)

        self.set_file = ""
        self.attachment_files = []

        # Настройка глобального перехватчика исключений
        self.root.report_callback_exception = self.show_traceback_error

        self.setup_ui()

    def setup_ui(self):
        # Главный контейнер с отступами
        main_frame = tk.Frame(self.root, padx=20, pady=15)
        main_frame.pack(fill="both", expand=True)

        # Заголовок
        lbl_title = tk.Label(main_frame, text="Утилита виртуальной агрегации", font=("Arial", 14, "bold"), fg="#1e3d59")
        lbl_title.pack(pady=(0, 15))

        # 1. Выбор файла кодов маркировки набора
        lbl_set = tk.Label(main_frame, text="1. Выберите файл с кодами маркировки НАБОРА:", font=("Arial", 10, "bold"))
        lbl_set.pack(anchor="w", pady=(5, 2))

        btn_set = tk.Button(main_frame, text="Выбрать файл набора", command=self.select_set_file, bg="#ffc107", fg="black", font=("Arial", 9, "bold"))
        btn_set.pack(fill="x", pady=2)

        self.lbl_set_status = tk.Label(main_frame, text="Файл не выбран", fg="grey", font=("Arial", 9, "italic"), wraplength=550, justify="left")
        self.lbl_set_status.pack(anchor="w", pady=(0, 10))

        # 2. Выбор количества вложений
        lbl_count = tk.Label(main_frame, text="2. Выберите количество вложений в один набор:", font=("Arial", 10, "bold"))
        lbl_count.pack(anchor="w", pady=(5, 2))

        # Рамка для ввода количества
        count_frame = tk.Frame(main_frame)
        count_frame.pack(anchor="w", pady=2)

        self.ent_count = tk.Entry(count_frame, width=10, font=("Arial", 11), justify="center")
        self.ent_count.insert(0, "4")  # По умолчанию 4 или другое
        self.ent_count.pack(side="left", padx=(0, 10))

        # 3. Выбор файлов кодов вложений
        lbl_attachments = tk.Label(main_frame, text="3. Выберите файлы с кодами маркировки ВЛОЖЕНИЙ:", font=("Arial", 10, "bold"))
        lbl_attachments.pack(anchor="w", pady=(10, 2))

        btn_attachments = tk.Button(main_frame, text="Выбрать файлы вложений", command=self.select_attachment_files, bg="#17a2b8", fg="white", font=("Arial", 9, "bold"))
        btn_attachments.pack(fill="x", pady=2)

        self.lbl_att_status = tk.Label(main_frame, text="Файлы не выбраны (выберите до 3-х или более файлов)", fg="grey", font=("Arial", 9, "italic"), wraplength=550, justify="left")
        self.lbl_att_status.pack(anchor="w", pady=(0, 15))

        # Кнопка Запуска
        self.btn_run = tk.Button(main_frame, text="ЗАПУСТИТЬ АГРЕГАЦИЮ", command=self.run_aggregation, bg="#28a745", fg="white", font=("Arial", 12, "bold"), height=2)
        self.btn_run.pack(fill="x", side="bottom", pady=10)

    def select_set_file(self):
        file_path = filedialog.askopenfilename(
            title="Выберите файл с кодами маркировки набора",
            filetypes=[("Текстовые файлы", "*.txt"), ("Все файлы", "*.*")]
        )
        if file_path:
            self.set_file = file_path
            self.lbl_set_status.config(text=f"Выбран: {os.path.basename(file_path)} ({file_path})", fg="green", font=("Arial", 9, "normal"))

    def select_attachment_files(self):
        file_paths = filedialog.askopenfilenames(
            title="Выберите файлы с кодами маркировки вложений",
            filetypes=[("Текстовые файлы", "*.txt"), ("Все файлы", "*.*")]
        )
        if file_paths:
            self.attachment_files = list(file_paths)
            files_basenames = [os.path.basename(f) for f in file_paths]
            display_text = f"Выбрано файлов: {len(file_paths)} ({', '.join(files_basenames)})"
            if len(display_text) > 120:
                display_text = f"Выбрано файлов: {len(file_paths)} ({', '.join(files_basenames[:3])} ...)"
            self.lbl_att_status.config(text=display_text, fg="green", font=("Arial", 9, "normal"))

    def run_aggregation(self):
        if not self.set_file:
            messagebox.showerror("Ошибка", "Пожалуйста, выберите файл с кодами маркировки набора (Шаг 1).")
            return

        if not self.attachment_files:
            messagebox.showerror("Ошибка", "Пожалуйста, выберите хотя бы один файл с кодами маркировки вложений (Шаг 3).")
            return

        # Валидация количества вложений
        try:
            count_val = self.ent_count.get().strip()
            if not count_val:
                raise ValueError("Поле количества вложений не должно быть пустым.")
            count_per_set = int(count_val)
            if count_per_set <= 0:
                raise ValueError("Количество вложений должно быть больше нуля.")
        except ValueError as e:
            messagebox.showerror("Ошибка", f"Некорректное значение количества вложений: {e}\nПожалуйста, введите целое положительное число.")
            return

        def gui_confirm_callback(actual_attachments, needed_attachments):
            msg = (
                f"Внимание!\n\n"
                f"Доступного количества кодов вложений ({actual_attachments}) "
                f"недостаточно для полной агрегации всех наборов (требуется {needed_attachments}).\n\n"
                f"Будет создано только {actual_attachments // count_per_set} полных наборов.\n"
                f"Продолжить операцию с частичными результатами?"
            )
            return messagebox.askyesno("Подтверждение частичной агрегации", msg)

        try:
            output_dir, total_written = perform_aggregation(
                self.set_file,
                self.attachment_files,
                count_per_set,
                confirm_callback=gui_confirm_callback
            )

            messagebox.showinfo(
                "Успех",
                f"Виртуальная агрегация успешно завершена!\n\n"
                f"Обработано наборов: {total_written}\n"
                f"Результаты сохранены в папку:\n{os.path.abspath(output_dir)}"
            )
        except Exception as e:
            messagebox.showerror("Ошибка агрегации", str(e))

    def show_traceback_error(self, exc, val, tb):
        """
        Глобальный обработчик исключений, показывающий messagebox с трассировкой.
        """
        err_msg = "".join(traceback.format_exception(exc, val, tb))
        dialog = tk.Toplevel(self.root)
        dialog.title("Критическая ошибка")
        dialog.geometry("600x450")
        dialog.focus_set()

        lbl_msg = tk.Label(dialog, text="Произошла критическая ошибка при выполнении приложения:", font=("Arial", 10, "bold"), fg="red")
        lbl_msg.pack(anchor="w", padx=10, pady=10)

        text_area = tk.Text(dialog, wrap="none", font=("Courier", 9))
        text_area.insert("1.0", err_msg)
        text_area.config(state="disabled")

        scroll_y = tk.Scrollbar(dialog, orient="vertical", command=text_area.yview)
        scroll_x = tk.Scrollbar(dialog, orient="horizontal", command=text_area.xview)
        text_area.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)

        scroll_y.pack(side="right", fill="y")
        scroll_x.pack(side="bottom", fill="x")
        text_area.pack(fill="both", expand=True, padx=10, pady=5)

        btn_ok = tk.Button(dialog, text="OK", command=dialog.destroy, width=10, font=("Arial", 10, "bold"))
        btn_ok.pack(pady=10)
        btn_ok.focus_set()


if __name__ == "__main__":
    if tk is None:
        print("Ошибка: Tkinter не установлен или недоступен в данной среде.")
        sys.exit(1)
    root = tk.Tk()
    app = AggregationApp(root)
    root.mainloop()
