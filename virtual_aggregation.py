# -*- coding: utf-8 -*-
"""
Утилита для виртуальной агрегации маркированных товаров в наборы.
Используется для группировки кодов содержимого (дочерних) под кодом набора (родительским).

Инструкция по сборке в исполняемый файл (EXE):
1. Установите PyInstaller:
   pip install pyinstaller
2. Выполните команду сборки:
   pyinstaller --noconsole --onefile virtual_aggregation.py
"""

import os
import re
import sys
import traceback
from datetime import datetime

# Ленивый импорт tkinter для безопасного тестирования в headless-режиме
try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
    TK_AVAILABLE = True
except ImportError:
    TK_AVAILABLE = False

def sanitize_filename(name):
    """
    Санитаризует имя файла, заменяя недопустимые в Windows символы на подчеркивания.
    """
    sanitized = re.sub(r'[\\/*?:"<>|]', '_', name)
    return sanitized

def read_codes(filepath):
    """
    Считывает коды маркировки из файла с поддержкой различных кодировок:
    UTF-8-SIG, UTF-16, UTF-8, CP1251.
    """
    encodings = ["utf-8-sig", "utf-16", "utf-8", "cp1251"]
    for enc in encodings:
        try:
            with open(filepath, "r", encoding=enc) as f:
                content = f.read()
            codes = [line.strip() for line in content.splitlines() if line.strip()]
            return codes
        except (UnicodeError, LookupError):
            continue
    raise ValueError(f"Не удалось прочитать файл {filepath} с использованием поддерживаемых кодировок.")

def perform_aggregation(parent_codes, child_codes, count_per_parent, output_dir, confirm_callback=None):
    """
    Выполняет виртуальную агрегацию кодов маркировки.
    Возвращает (success, created_count).
    """
    if not parent_codes:
        raise ValueError("Список кодов наборов (родительских) пуст.")
    if not child_codes:
        raise ValueError("Список вложенных кодов (дочерних) пуст.")
    if count_per_parent <= 0:
        raise ValueError("Количество вложений должно быть больше 0.")

    total_required_children = len(parent_codes) * count_per_parent
    actual_sets = len(parent_codes)

    if len(child_codes) < total_required_children:
        max_possible_sets = len(child_codes) // count_per_parent
        actual_sets = min(len(parent_codes), max_possible_sets)

        if actual_sets == 0:
            raise ValueError(
                f"Недостаточно кодов содержимого для создания хотя бы одного набора.\n"
                f"Доступно дочерних кодов: {len(child_codes)}, требуется на один набор: {count_per_parent}."
            )

        if confirm_callback:
            msg = (
                f"Доступных дочерних кодов ({len(child_codes)}) меньше, чем требуется для всех наборов "
                f"({total_required_children}). Будет создано только {actual_sets} наборов.\n"
                f"Продолжить?"
            )
            if not confirm_callback(msg):
                return False, 0

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    written_files = set()
    created_count = 0

    for i in range(actual_sets):
        parent = parent_codes[i]
        start_idx = i * count_per_parent
        end_idx = start_idx + count_per_parent
        children = child_codes[start_idx:end_idx]

        sanitized_parent = sanitize_filename(parent)
        base_filename = f"{sanitized_parent}.txt"
        file_path = os.path.join(output_dir, base_filename)

        suffix_idx = 1
        while file_path in written_files:
            base_filename = f"{sanitized_parent}_{suffix_idx}.txt"
            file_path = os.path.join(output_dir, base_filename)
            suffix_idx += 1

        written_files.add(file_path)

        # Запись набора в кодировке UTF-8 без BOM
        with open(file_path, "w", encoding="utf-8", newline="") as f:
            f.write(parent + "\n")
            for child in children:
                f.write(child + "\n")

        created_count += 1

    return True, created_count


class AggregationApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Виртуальная Агрегация")
        self.root.geometry("640x520")
        self.root.resizable(False, False)

        self.parent_file = ""
        self.child_files = []

        self.create_widgets()

    def create_widgets(self):
        # Фрейм для родительского файла
        parent_frame = ttk.LabelFrame(self.root, text=" 1. Выберите 1 файл с кодами наборов (родительские коды) ", padding=10)
        parent_frame.pack(fill="x", padx=15, pady=10)

        self.btn_select_parent = ttk.Button(parent_frame, text="Выбрать файл наборов", command=self.select_parent_file)
        self.btn_select_parent.pack(side="left", padx=5)

        self.lbl_parent_status = ttk.Label(parent_frame, text="Файл не выбран", foreground="red")
        self.lbl_parent_status.pack(side="left", padx=10)

        # Фрейм для количества вложений
        count_frame = ttk.LabelFrame(self.root, text=" 2. Укажите количество вложений в один набор ", padding=10)
        count_frame.pack(fill="x", padx=15, pady=10)

        ttk.Label(count_frame, text="Вложений в набор:").pack(side="left", padx=5)
        self.ent_count = ttk.Entry(count_frame, width=10)
        self.ent_count.insert(0, "4")
        self.ent_count.pack(side="left", padx=5)

        # Фрейм для дочерних файлов
        child_frame = ttk.LabelFrame(self.root, text=" 3. Выберите файлы содержимого (дочерние коды) ", padding=10)
        child_frame.pack(fill="both", expand=True, padx=15, pady=10)

        self.btn_select_children = ttk.Button(child_frame, text="Выбрать файлы содержимого", command=self.select_child_files)
        self.btn_select_children.pack(anchor="w", padx=5, pady=5)

        self.txt_children_list = tk.Text(child_frame, height=8, width=70, state="disabled", wrap="none")
        self.txt_children_list.pack(fill="both", expand=True, padx=5, pady=5)

        # Кнопка запуска агрегации
        self.btn_run = ttk.Button(self.root, text="Запустить агрегацию", command=self.run_aggregation)
        self.btn_run.pack(pady=15)

    def select_parent_file(self):
        file_path = filedialog.askopenfilename(
            title="Выберите 1 файл с кодами наборов",
            filetypes=[("Текстовые файлы", "*.txt"), ("Все файлы", "*.*")]
        )
        if file_path:
            self.parent_file = file_path
            filename = os.path.basename(file_path)
            self.lbl_parent_status.config(text=f"Выбран: {filename}", foreground="green")

    def select_child_files(self):
        file_paths = filedialog.askopenfilenames(
            title="Выберите файлы содержимого",
            filetypes=[("Текстовые файлы", "*.txt"), ("Все файлы", "*.*")]
        )
        if file_paths:
            self.child_files = list(file_paths)
            self.txt_children_list.config(state="normal")
            self.txt_children_list.delete("1.0", tk.END)
            for path in self.child_files:
                self.txt_children_list.insert(tk.END, f"{os.path.basename(path)}\n")
            self.txt_children_list.config(state="disabled")

    def run_aggregation(self):
        if not self.parent_file:
            messagebox.showerror("Ошибка", "Пожалуйста, выберите файл с кодами наборов (родительскими кодами).")
            return

        if not self.child_files:
            messagebox.showerror("Ошибка", "Пожалуйста, выберите хотя бы один файл содержимого (дочерними кодами).")
            return

        try:
            count_val = int(self.ent_count.get().strip())
            if count_val <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Ошибка", "Количество вложений должно быть целым числом больше нуля.")
            return

        try:
            parent_codes = read_codes(self.parent_file)
            child_codes = []
            for filepath in self.child_files:
                child_codes.extend(read_codes(filepath))

            # Создание новой папки с временной меткой
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_dir = f"aggregation_results_{timestamp}"

            def confirm_dialog(msg):
                # Настройка окна подтверждения во избежание скрытия кнопок при длинных сообщениях
                confirm_win = tk.Toplevel(self.root)
                confirm_win.title("Предупреждение")
                confirm_win.geometry("600x250")
                confirm_win.resizable(False, False)
                confirm_win.grab_set()

                lbl = ttk.Label(confirm_win, text=msg, wraplength=560, justify="left")
                lbl.pack(padx=20, pady=20, expand=True)

                result_holder = {"value": False}

                def on_yes():
                    result_holder["value"] = True
                    confirm_win.destroy()

                def on_no():
                    result_holder["value"] = False
                    confirm_win.destroy()

                btn_frame = ttk.Frame(confirm_win)
                btn_frame.pack(pady=15, side="bottom")

                btn_yes = ttk.Button(btn_frame, text="Да", command=on_yes)
                btn_yes.pack(side="left", padx=10)
                btn_yes.focus_set()

                btn_no = ttk.Button(btn_frame, text="Нет", command=on_no)
                btn_no.pack(side="left", padx=10)

                self.root.wait_window(confirm_win)
                return result_holder["value"]

            success, created_count = perform_aggregation(
                parent_codes=parent_codes,
                child_codes=child_codes,
                count_per_parent=count_val,
                output_dir=output_dir,
                confirm_callback=confirm_dialog
            )

            if success:
                messagebox.showinfo(
                    "Успех",
                    f"Виртуальная агрегация успешно завершена!\n\n"
                    f"Создано наборов: {created_count}\n"
                    f"Результаты сохранены в папку:\n{os.path.abspath(output_dir)}"
                )
        except Exception as e:
            # Отображение полного трейсбэка ошибки во избежание сложностей с отладкой
            tb = traceback.format_exc()
            error_win = tk.Toplevel(self.root)
            error_win.title("Критическая ошибка")
            error_win.geometry("600x450")
            error_win.resizable(False, False)
            error_win.grab_set()

            lbl = ttk.Label(error_win, text=f"Произошла ошибка при выполнении операции:\n{str(e)}", font=("Arial", 11, "bold"), foreground="red", wraplength=560)
            lbl.pack(padx=20, pady=10)

            txt = tk.Text(error_win, height=15, width=70)
            txt.insert("1.0", tb)
            txt.config(state="disabled")
            txt.pack(padx=20, pady=5, fill="both", expand=True)

            btn_ok = ttk.Button(error_win, text="OK", command=error_win.destroy)
            btn_ok.pack(pady=10, side="bottom")
            btn_ok.focus_set()


def global_exception_handler(exc_type, exc_value, exc_traceback):
    """
    Глобальный обработчик исключений для отображения полного трейсбэка.
    """
    tb = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    print(tb, file=sys.stderr)
    if TK_AVAILABLE:
        try:
            error_win = tk.Toplevel()
            error_win.title("Критическая ошибка")
            error_win.geometry("600x450")
            error_win.resizable(False, False)
            error_win.grab_set()

            lbl = ttk.Label(error_win, text=f"Произошла непредвиденная ошибка:\n{str(exc_value)}", font=("Arial", 11, "bold"), foreground="red", wraplength=560)
            lbl.pack(padx=20, pady=10)

            txt = tk.Text(error_win, height=15, width=70)
            txt.insert("1.0", tb)
            txt.config(state="disabled")
            txt.pack(padx=20, pady=5, fill="both", expand=True)

            btn_ok = ttk.Button(error_win, text="OK", command=error_win.destroy)
            btn_ok.pack(pady=10, side="bottom")
            btn_ok.focus_set()
            error_win.wait_window()
        except Exception:
            messagebox.showerror("Критическая ошибка", f"Произошла непредвиденная ошибка:\n{tb}")


def main():
    sys.excepthook = global_exception_handler
    if not TK_AVAILABLE:
        print("Ошибка: Модуль tkinter недоступен. Запуск в графическом режиме невозможен.", file=sys.stderr)
        sys.exit(1)
    root = tk.Tk()
    app = AggregationApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
