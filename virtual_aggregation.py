"""
Инструкция по сборке утилиты в standalone exe файл на Windows 8, 10, 11:
1. Установите необходимые библиотеки (если они еще не установлены):
   pip install pyinstaller
2. Запустите следующую команду в терминале (командной строке) из папки проекта:
   pyinstaller --noconsole --onefile virtual_aggregation.py
3. Готовый исполняемый файл будет находиться в папке 'dist'.
"""

import os
import re
import sys
from datetime import datetime

# Ленивый импорт tkinter для headless тестирования
try:
    import tkinter as tk
    from tkinter import filedialog, messagebox
except ImportError:
    tk = None


def sanitize_filename(filename):
    r"""
    Очищает имя файла от символов, недопустимых в Windows: \ / : * ? " < > |
    Заменяет их на подчеркивание.
    """
    if not filename:
        return "empty_code"
    # Заменяем недопустимые символы на подчеркивание
    sanitized = re.sub(r'[\\/*?:"<>|]', '_', filename)
    # Ограничиваем длину имени файла для стабильности в ОС Windows
    return sanitized[:120].strip()


def read_codes(filepath):
    """
    Читает коды из файла, используя различные кодировки для максимальной совместимости.
    Поддерживаемые кодировки: UTF-8-SIG, UTF-16, UTF-8, CP1251.
    Возвращает список непустых строк без пробелов.
    """
    encodings = ["utf-8-sig", "utf-16", "utf-8", "cp1251"]
    content = None

    for enc in encodings:
        try:
            with open(filepath, "r", encoding=enc) as f:
                content = f.read()
            break
        except (UnicodeDecodeError, Exception):
            continue

    if content is None:
        raise ValueError(f"Не удалось прочитать файл {filepath}. Неизвестная кодировка.")

    codes = []
    for line in content.splitlines():
        line_clean = line.strip()
        if line_clean:
            codes.append(line_clean)

    return codes


def perform_aggregation(parent_file, child_files, count_per_parent, confirm_callback=None, info_callback=None, error_callback=None):
    """
    Выполняет виртуальную агрегацию кодов маркировки.

    :param parent_file: Путь к файлу с родительскими кодами (наборы)
    :param child_files: Список путей к файлам с дочерними кодами (вложения)
    :param count_per_parent: Количество вложений в один набор
    :param confirm_callback: Функция для запроса подтверждения пользователя (принимает сообщение, возвращает bool)
    :param info_callback: Функция для вывода информационных сообщений (принимает заголовок и сообщение)
    :param error_callback: Функция для вывода ошибок (принимает заголовок и сообщение)
    """
    if not parent_file:
        if error_callback:
            error_callback("Ошибка", "Не выбран файл с кодами наборов.")
        return False

    if not child_files:
        if error_callback:
            error_callback("Ошибка", "Не выбраны файлы с кодами вложений.")
        return False

    try:
        count_per_parent = int(count_per_parent)
        if count_per_parent <= 0:
            raise ValueError()
    except ValueError:
        if error_callback:
            error_callback("Ошибка", "Количество вложений должно быть положительным целым числом.")
        return False

    # Считываем родительские коды
    try:
        parent_codes = read_codes(parent_file)
    except Exception as e:
        if error_callback:
            error_callback("Ошибка чтения", f"Не удалось прочитать файл наборов:\n{e}")
        return False

    if not parent_codes:
        if error_callback:
            error_callback("Ошибка", "Файл наборов пуст.")
        return False

    # Считываем дочерние коды
    child_codes = []
    for cf in child_files:
        try:
            child_codes.extend(read_codes(cf))
        except Exception as e:
            if error_callback:
                error_callback("Ошибка чтения", f"Не удалось прочитать файл вложений '{cf}':\n{e}")
            return False

    if not child_codes:
        if error_callback:
            error_callback("Ошибка", "Выбранные файлы вложений не содержат кодов.")
        return False

    required_child_count = len(parent_codes) * count_per_parent
    actual_sets = len(parent_codes)

    # Обработка нехватки кодов вложений
    if len(child_codes) < required_child_count:
        max_possible_sets = len(child_codes) // count_per_parent
        actual_sets = min(len(parent_codes), max_possible_sets)

        msg = (
            f"Внимание! Недостаточно дочерних кодов для полной агрегации.\n\n"
            f"Всего кодов наборов: {len(parent_codes)}\n"
            f"Требуется вложений: {required_child_count} (по {count_per_parent} на набор)\n"
            f"Доступно вложений: {len(child_codes)}\n\n"
            f"Будет создано полных наборов: {actual_sets}.\n"
            f"Продолжить?"
        )
        if confirm_callback:
            if not confirm_callback(msg):
                return False
        else:
            # Если коллбека нет, по умолчанию останавливаем или продолжаем
            return False

    if actual_sets == 0:
        if error_callback:
            error_callback("Ошибка", "Недостаточно кодов вложений даже для одного набора.")
        return False

    # Создаем папку результатов
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir_name = f"aggregation_results_{timestamp}"

    # Создаем папку в той же директории, где находится родительский файл
    parent_dir = os.path.dirname(os.path.abspath(parent_file))
    output_dir = os.path.join(parent_dir, output_dir_name)

    try:
        os.makedirs(output_dir, exist_ok=True)
    except Exception as e:
        if error_callback:
            error_callback("Ошибка создания папки", f"Не удалось создать папку '{output_dir}':\n{e}")
        return False

    # Выполняем агрегацию
    success_count = 0
    used_filenames = set()

    for i in range(actual_sets):
        parent_code = parent_codes[i]
        children = child_codes[i * count_per_parent : (i + 1) * count_per_parent]

        # Санитаризуем имя файла
        base_name = sanitize_filename(parent_code)
        filename = f"{base_name}.txt"
        file_path = os.path.join(output_dir, filename)

        # Обработка коллизий имен файлов
        collision_counter = 1
        while file_path.lower() in used_filenames or os.path.exists(file_path):
            filename = f"{base_name}_{collision_counter}.txt"
            file_path = os.path.join(output_dir, filename)
            collision_counter += 1

        used_filenames.add(file_path.lower())

        try:
            # Запись в кодировке UTF-8 без BOM
            with open(file_path, "w", encoding="utf-8", newline="\n") as f:
                f.write(parent_code + "\n")
                for child in children:
                    f.write(child + "\n")
            success_count += 1
        except Exception as e:
            if error_callback:
                error_callback("Ошибка записи", f"Не удалось записать файл '{file_path}':\n{e}")
            return False

    if info_callback:
        info_callback(
            "Успешно",
            f"Агрегация завершена успешно!\n\n"
            f"Создано наборов: {success_count}\n"
            f"Папка с результатами:\n{output_dir}"
        )

    return True


class VirtualAggregationApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Виртуальная агрегация кодов")
        self.root.geometry("620x420")
        self.root.resizable(True, True)

        self.parent_file_path = ""
        self.child_file_paths = []

        self.create_widgets()

    def create_widgets(self):
        # Главный фрейм
        main_frame = tk.Frame(self.root, padx=15, pady=15)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Заголовок
        title_label = tk.Label(
            main_frame,
            text="Виртуальная агрегация кодов маркировки",
            font=("Arial", 14, "bold"),
            fg="#2c3e50"
        )
        title_label.pack(pady=(0, 15))

        # Раздел 1: Выбор родительского файла (наборы)
        parent_frame = tk.LabelFrame(main_frame, text=" 1. Коды маркировки наборов (родительские) ", padx=10, pady=10)
        parent_frame.pack(fill=tk.X, pady=(0, 10))

        self.btn_select_parent = tk.Button(
            parent_frame,
            text="Выбрать файл...",
            command=self.select_parent_file,
            width=15,
            bg="#3498db",
            fg="white",
            relief=tk.FLAT
        )
        self.btn_select_parent.pack(side=tk.LEFT, padx=(0, 10))

        self.lbl_parent_status = tk.Label(
            parent_frame,
            text="Файл не выбран",
            fg="red",
            anchor="w",
            wraplength=400
        )
        self.lbl_parent_status.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Раздел 2: Выбор количества вложений
        count_frame = tk.LabelFrame(main_frame, text=" 2. Параметры агрегации ", padx=10, pady=10)
        count_frame.pack(fill=tk.X, pady=(0, 10))

        tk.Label(count_frame, text="Количество вложений в один набор:").pack(side=tk.LEFT, padx=(0, 10))

        self.ent_count = tk.Entry(count_frame, width=8, font=("Arial", 10, "bold"), justify=tk.CENTER)
        self.ent_count.insert(0, "4")
        self.ent_count.pack(side=tk.LEFT)

        # Раздел 3: Выбор дочерних файлов (вложения)
        child_frame = tk.LabelFrame(main_frame, text=" 3. Коды маркировки вложений (содержимое) ", padx=10, pady=10)
        child_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 15))

        self.btn_select_children = tk.Button(
            child_frame,
            text="Выбрать файлы...",
            command=self.select_child_files,
            width=15,
            bg="#3498db",
            fg="white",
            relief=tk.FLAT
        )
        self.btn_select_children.pack(side=tk.LEFT, anchor="n", padx=(0, 10))

        # Список файлов вложений с прокруткой
        list_container = tk.Frame(child_frame)
        list_container.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.scrollbar = tk.Scrollbar(list_container)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.lst_children = tk.Listbox(
            list_container,
            yscrollcommand=self.scrollbar.set,
            height=4,
            font=("Arial", 9)
        )
        self.lst_children.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.scrollbar.config(command=self.lst_children.yview)

        # Кнопка Запуска
        self.btn_start = tk.Button(
            main_frame,
            text="ВЫПОЛНИТЬ АГРЕГАЦИЮ",
            command=self.start_aggregation,
            font=("Arial", 12, "bold"),
            bg="#2ecc71",
            fg="white",
            pady=8,
            relief=tk.FLAT
        )
        self.btn_start.pack(fill=tk.X)

    def select_parent_file(self):
        path = filedialog.askopenfilename(
            title="Выберите файл кодов наборов (родительских кодов)",
            filetypes=[("Текстовые файлы", "*.txt"), ("Все файлы", "*.*")]
        )
        if path:
            self.parent_file_path = path
            self.lbl_parent_status.config(
                text=os.path.basename(path),
                fg="green"
            )

    def select_child_files(self):
        paths = filedialog.askopenfilenames(
            title="Выберите файлы кодов вложений",
            filetypes=[("Текстовые файлы", "*.txt"), ("Все файлы", "*.*")]
        )
        if paths:
            self.child_file_paths = list(paths)
            self.lst_children.delete(0, tk.END)
            for p in self.child_file_paths:
                self.lst_children.insert(tk.END, os.path.basename(p))

    def start_aggregation(self):
        def gui_confirm(msg):
            return messagebox.askyesno("Подтверждение", msg)

        def gui_info(title, msg):
            messagebox.showinfo(title, msg)

        def gui_error(title, msg):
            messagebox.showerror(title, msg)

        perform_aggregation(
            parent_file=self.parent_file_path,
            child_files=self.child_file_paths,
            count_per_parent=self.ent_count.get().strip(),
            confirm_callback=gui_confirm,
            info_callback=gui_info,
            error_callback=gui_error
        )


def main():
    if tk is None:
        print("Ошибка: Tkinter не доступен в текущем окружении.")
        sys.exit(1)

    try:
        root = tk.Tk()
        app = VirtualAggregationApp(root)
        root.mainloop()
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        # Показываем MessageBox с трейсбэком ошибки
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "Критическая ошибка",
            f"Произошел сбой в работе приложения:\n\n{e}\n\nТрейсбэк:\n{tb}"
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
