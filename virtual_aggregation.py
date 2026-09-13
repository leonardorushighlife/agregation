"""
Скрипт для виртуальной агрегации кодов маркировки.

Инструкция по сборке в EXE (PyInstaller):
1. Установите PyInstaller (если еще не установлен):
   pip install pyinstaller
2. Выполните команду для сборки исполняемого файла:
   pyinstaller --noconsole --onefile virtual_aggregation.py
3. Готовый файл `virtual_aggregation.exe` будет находится в папке `dist/`.
"""

import os
import re
import sys
import traceback
from datetime import datetime

# Lazy/guarded imports for GUI to allow headless testing of logic
try:
    import tkinter as tk
    from tkinter import filedialog, messagebox
except ImportError:
    tk = None


def read_codes_from_file(filepath):
    """
    Считывает коды из текстового файла, пробуя разные кодировки.
    Возвращает список непустых строк без символов перевода строки.
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
        raise ValueError(f"Не удалось прочитать файл {filepath}. Проверьте кодировку файла.")

    lines = [line.strip() for line in content.splitlines() if line.strip()]
    return lines


def read_all_codes(filepaths):
    """
    Считывает и объединяет коды из списка файлов.
    """
    all_codes = []
    for fp in filepaths:
        codes = read_codes_from_file(fp)
        all_codes.extend(codes)
    return all_codes


def sanitize_filename(code):
    """
    Удаляет или заменяет недопустимые символы в имени файла для ОС Windows/Linux.
    """
    # Заменяем запрещенные символы на подчеркивание
    sanitized = re.sub(r'[\\/*?:"<>|]', '_', code)
    # Ограничиваем длину имени файла при необходимости (макс 150 символов)
    if len(sanitized) > 150:
        sanitized = sanitized[:150]
    return sanitized.strip()


def perform_aggregation(parent_file, child_files, items_per_parent, confirm_callback=None):
    """
    Выполняет виртуальную агрегацию.

    :param parent_file: путь к файлу с родительскими кодами (коды наборов)
    :param child_files: список путей к файлам с дочерними кодами (вложения)
    :param items_per_parent: количество вложений на один набор
    :param confirm_callback: функция обратного вызова для подтверждения при нехватке кодов
    :return: dict со статистикой или информацией об успехе
    """
    if items_per_parent <= 0:
        raise ValueError("Количество вложений должно быть больше 0.")

    if not parent_file or not os.path.isfile(parent_file):
        raise ValueError("Не выбран или не существует файл кодов наборов (родительский файл).")

    if not child_files:
        raise ValueError("Не выбраны файлы с кодами вложений (дочерние файлы).")

    parent_codes = read_codes_from_file(parent_file)
    if not parent_codes:
        raise ValueError("Файл кодов наборов пуст.")

    child_codes = read_all_codes(child_files)
    if not child_codes:
        raise ValueError("Файлы вложений не содержат кодов.")

    total_parents = len(parent_codes)
    total_children = len(child_codes)
    required_children = total_parents * items_per_parent

    if total_children < required_children:
        max_possible_sets = total_children // items_per_parent
        warning_msg = (
            f"Внимание: Недостаточно кодов вложений!\n"
            f"Требуется: {required_children} кодов ({total_parents} наб. x {items_per_parent} вл.).\n"
            f"Доступно вложений: {total_children}.\n"
            f"Будет сформировано наборов: {max_possible_sets}.\n\n"
            f"Продолжить?"
        )
        if confirm_callback:
            if not confirm_callback(warning_msg):
                return {"status": "cancelled", "message": "Операция отменена пользователем."}
        total_parents = max_possible_sets

    if total_parents == 0:
        raise ValueError("Недостаточно кодов вложений даже для одного полного набора.")

    # Создаем новую папку с меткой времени
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    folder_name = f"aggregation_results_{timestamp}"
    os.makedirs(folder_name, exist_ok=True)

    used_filenames = {}
    created_count = 0
    child_index = 0

    for p_idx in range(total_parents):
        parent_code = parent_codes[p_idx]
        current_children = child_codes[child_index : child_index + items_per_parent]
        child_index += items_per_parent

        base_filename = sanitize_filename(parent_code)
        if not base_filename:
            base_filename = f"set_{p_idx + 1}"

        # Обработка дубликатов имен файлов
        if base_filename in used_filenames:
            used_filenames[base_filename] += 1
            filename = f"{base_filename}_{used_filenames[base_filename]}.txt"
        else:
            used_filenames[base_filename] = 0
            filename = f"{base_filename}.txt"

        filepath = os.path.join(folder_name, filename)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(parent_code + "\n")
            for c_code in current_children:
                f.write(c_code + "\n")

        created_count += 1

    return {
        "status": "success",
        "folder": os.path.abspath(folder_name),
        "created_sets": created_count,
        "used_children": child_index,
        "remaining_children": total_children - child_index,
        "remaining_parents": len(parent_codes) - total_parents
    }


class VirtualAggregationApp:
    """
    Графический интерфейс для виртуальной агрегации.
    """
    def __init__(self, root):
        self.root = root
        self.root.title("Виртуальная Агрегация Кодов Маркировки")
        self.root.geometry("650x520")
        self.root.resizable(False, False)

        self.parent_file = ""
        self.child_files = []

        self._build_ui()

    def _build_ui(self):
        # Frame для родительского файла
        frame_parent = tk.LabelFrame(self.root, text=" 1. Коды наборов (Родительский файл) ", font=("Arial", 10, "bold"), padx=10, pady=10)
        frame_parent.pack(fill="x", padx=15, pady=8)

        self.lbl_parent = tk.Label(frame_parent, text="Файл не выбран", fg="gray", anchor="w", width=55)
        self.lbl_parent.pack(side="left", fill="x", expand=True)

        btn_parent = tk.Button(frame_parent, text="Обзор...", width=12, command=self.select_parent_file)
        btn_parent.pack(side="right")

        # Frame для кол-ва вложений
        frame_count = tk.LabelFrame(self.root, text=" 2. Количество вложений в каждый набор ", font=("Arial", 10, "bold"), padx=10, pady=10)
        frame_count.pack(fill="x", padx=15, pady=8)

        tk.Label(frame_count, text="Вложений на 1 набор:").pack(side="left", padx=(0, 10))
        self.spin_count = tk.Spinbox(frame_count, from_=1, to=10000, width=10, font=("Arial", 11))
        self.spin_count.delete(0, "end")
        self.spin_count.insert(0, "10")
        self.spin_count.pack(side="left")

        # Frame для дочерних файлов
        frame_child = tk.LabelFrame(self.root, text=" 3. Коды вложений (Файлы содержимого) ", font=("Arial", 10, "bold"), padx=10, pady=10)
        frame_child.pack(fill="both", expand=True, padx=15, pady=8)

        btn_child = tk.Button(frame_child, text="Добавить TXT файлы...", command=self.select_child_files)
        btn_child.pack(anchor="w", pady=(0, 5))

        self.listbox_children = tk.Listbox(frame_child, height=6, selectmode=tk.EXTENDED)
        self.listbox_children.pack(side="left", fill="both", expand=True)

        scrollbar = tk.Scrollbar(frame_child, orient="vertical", command=self.listbox_children.yview)
        scrollbar.pack(side="right", fill="y")
        self.listbox_children.config(yscrollcommand=scrollbar.set)

        # Frame действий
        frame_action = tk.Frame(self.root, pady=10)
        frame_action.pack(fill="x", padx=15)

        btn_clear = tk.Button(frame_action, text="Очистить всё", width=15, command=self.clear_all)
        btn_clear.pack(side="left")

        btn_start = tk.Button(frame_action, text="Сформировать наборы", bg="#28a745", fg="white", font=("Arial", 11, "bold"), width=25, height=2, command=self.start_aggregation)
        btn_start.pack(side="right")

    def select_parent_file(self):
        fp = filedialog.askopenfilename(
            title="Выберите TXT файл с кодами наборов",
            filetypes=[("Текстовые файлы", "*.txt"), ("Все файлы", "*.*")]
        )
        if fp:
            self.parent_file = fp
            self.lbl_parent.config(text=os.path.basename(fp), fg="black")

    def select_child_files(self):
        fps = filedialog.askopenfilenames(
            title="Выберите TXT файлы с кодами вложений",
            filetypes=[("Текстовые файлы", "*.txt"), ("Все файлы", "*.*")]
        )
        if fps:
            for fp in fps:
                if fp not in self.child_files:
                    self.child_files.append(fp)
                    self.listbox_children.insert(tk.END, os.path.basename(fp))

    def clear_all(self):
        self.parent_file = ""
        self.child_files = []
        self.lbl_parent.config(text="Файл не выбран", fg="gray")
        self.listbox_children.delete(0, tk.END)

    def start_aggregation(self):
        try:
            items_per_parent = int(self.spin_count.get())
        except ValueError:
            messagebox.showerror("Ошибка", "Введите корректное число вложений.")
            return

        def confirm_cb(msg):
            return messagebox.askyesno("Подтверждение", msg)

        try:
            res = perform_aggregation(
                parent_file=self.parent_file,
                child_files=self.child_files,
                items_per_parent=items_per_parent,
                confirm_callback=confirm_cb
            )

            if res.get("status") == "success":
                msg = (
                    f"Агрегация успешно завершена!\n\n"
                    f"Создано файлов наборов: {res['created_sets']}\n"
                    f"Использовано вложений: {res['used_children']}\n"
                    f"Папка с результатом:\n{res['folder']}"
                )
                messagebox.showinfo("Успешно", msg)
            elif res.get("status") == "cancelled":
                messagebox.showinfo("Отмена", res.get("message", "Операция отменена."))

        except Exception as e:
            err_details = traceback.format_exc()
            messagebox.showerror("Ошибка агрегации", f"{str(e)}\n\nПодробности:\n{err_details}")


def main():
    if tk is None:
        print("Ошибка: Tkinter недоступен.")
        sys.exit(1)

    root = tk.Tk()
    app = VirtualAggregationApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
