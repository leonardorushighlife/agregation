"""
Скрипт для виртуальной агрегации кодов маркировки.

Инструкция по сборке в EXE (PyInstaller):
----------------------------------------
1. Установите PyInstaller (если не установлен):
   pip install pyinstaller

2. Выполните команду в терминале:
   pyinstaller --noconsole --onefile virtual_aggregation.py

3. Исполняемый файл `virtual_aggregation.exe` будет создан в папке `dist/`.
"""

import os
import re
import sys
from datetime import datetime
import tkinter as tk
from tkinter import filedialog, messagebox, ttk


def sanitize_filename(name: str) -> str:
    """Очищает строку от символов, не допустимых в именах файлов."""
    name = name.strip()
    # Заменяем недопустимые символы ОС на подчёркивание
    clean_name = re.sub(r'[\\/*?:"<>|]', '_', name)
    # Ограничиваем длину имени файла
    return clean_name[:100] if clean_name else "set_output"


def read_codes(filepath: str) -> list[str]:
    """Считывает коды маркировки из текстового файла, удаляя пустые строки и пробелы."""
    encodings = ['utf-8', 'utf-8-sig', 'cp1251', 'utf-16']
    lines = []

    for enc in encodings:
        try:
            with open(filepath, 'r', encoding=enc) as f:
                lines = f.readlines()
            break
        except (UnicodeDecodeError, UnicodeError):
            continue

    codes = [line.strip() for line in lines if line.strip()]
    return codes


def perform_aggregation(parent_file: str, child_files: list[str], items_per_set: int, output_dir: str = None) -> tuple[str, int, int]:
    """
    Выполняет виртуальную агрегацию.

    :param parent_file: Путь к файлу с кодами маркировки наборов (родительские коды)
    :param child_files: Список путей к файлам с кодами маркировки вложений
    :param items_per_set: Количество вложений на один набор
    :param output_dir: Кастомный каталог для сохранения (если None, создается новая папка)
    :return: Кортеж (путь_к_папке, количество_созданных_наборов, использовано_кодов_вложений)
    """
    if not parent_file or not os.path.exists(parent_file):
        raise FileNotFoundError("Файл с кодами наборов не найден.")

    if not child_files:
        raise ValueError("Не выбраны файлы с кодами вложений.")

    if items_per_set <= 0:
        raise ValueError("Количество вложений должно быть больше 0.")

    parent_codes = read_codes(parent_file)
    if not parent_codes:
        raise ValueError("Файл с кодами наборов пуст.")

    child_codes = []
    for c_file in child_files:
        if os.path.exists(c_file):
            child_codes.extend(read_codes(c_file))

    if not child_codes:
        raise ValueError("Файлы вложений не содержат кодов.")

    if output_dir is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = f"aggregation_results_{timestamp}"

    os.makedirs(output_dir, exist_ok=True)

    created_count = 0
    used_child_count = 0

    for i, parent_code in enumerate(parent_codes):
        start_idx = i * items_per_set
        end_idx = start_idx + items_per_set

        # Проверяем, достаточно ли кодов вложений для очередного набора
        if start_idx >= len(child_codes):
            break

        set_child_codes = child_codes[start_idx:end_idx]
        if len(set_child_codes) < items_per_set:
            # Прерываем, если на полный набор кодов не хватает
            break

        filename = f"{sanitize_filename(parent_code)}.txt"
        filepath = os.path.join(output_dir, filename)

        # Если файл с таким именем уже существует, добавляем суффикс
        counter = 1
        while os.path.exists(filepath):
            filename = f"{sanitize_filename(parent_code)}_{counter}.txt"
            filepath = os.path.join(output_dir, filename)
            counter += 1

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(parent_code + '\n')
            for child_code in set_child_codes:
                f.write(child_code + '\n')

        created_count += 1
        used_child_count += len(set_child_codes)

    return output_dir, created_count, used_child_count


class VirtualAggregationApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Виртуальная Агрегация Кодов Маркировки")
        self.root.geometry("680x520")
        self.root.resizable(False, False)

        self.parent_file = ""
        self.child_files = []

        self.build_ui()

    def build_ui(self):
        # Frame для выбора файла наборов
        frame_parent = tk.LabelFrame(self.root, text="1. Файл кодов маркировки набора (родительский)", font=("Arial", 10, "bold"), padx=10, pady=10)
        frame_parent.pack(fill="x", padx=15, pady=5)

        self.lbl_parent = tk.Label(frame_parent, text="Файл не выбран", fg="gray", anchor="w")
        self.lbl_parent.pack(side="left", fill="x", expand=True)

        btn_parent = tk.Button(frame_parent, text="Выбрать файл", command=self.select_parent_file)
        btn_parent.pack(side="right")

        # Frame для выбора файлов вложений
        frame_child = tk.LabelFrame(self.root, text="2. Файлы кодов маркировки вложений (содержимое)", font=("Arial", 10, "bold"), padx=10, pady=10)
        frame_child.pack(fill="x", padx=15, pady=5)

        self.lbl_child = tk.Label(frame_child, text="Выбрано файлов: 0", fg="gray", anchor="w")
        self.lbl_child.pack(side="left", fill="x", expand=True)

        btn_child = tk.Button(frame_child, text="Выбрать файлы (TXT)", command=self.select_child_files)
        btn_child.pack(side="right")

        # Frame для настройки количества вложений
        frame_config = tk.LabelFrame(self.root, text="3. Настройка агрегации", font=("Arial", 10, "bold"), padx=10, pady=10)
        frame_config.pack(fill="x", padx=15, pady=5)

        tk.Label(frame_config, text="Количество вложений на 1 набор:").pack(side="left", padx=5)

        self.spin_count = tk.Spinbox(frame_config, from_=1, to=1000, width=10)
        self.spin_count.delete(0, "end")
        self.spin_count.insert(0, "3")
        self.spin_count.pack(side="left", padx=5)

        # Кнопка запуска
        btn_start = tk.Button(self.root, text="Запустить агрегацию", font=("Arial", 12, "bold"), bg="#4CAF50", fg="white", command=self.run_aggregation)
        btn_start.pack(pady=15)

        # Текстовое поле лога / статуса
        frame_log = tk.LabelFrame(self.root, text="Лог выполнения", font=("Arial", 9))
        frame_log.pack(fill="both", expand=True, padx=15, pady=5)

        self.txt_log = tk.Text(frame_log, state="disabled", height=8, font=("Consolas", 9))
        self.txt_log.pack(fill="both", expand=True, padx=5, pady=5)

    def log(self, message: str):
        self.txt_log.config(state="normal")
        self.txt_log.insert("end", message + "\n")
        self.txt_log.see("end")
        self.txt_log.config(state="disabled")

    def select_parent_file(self):
        file_path = filedialog.askopenfilename(
            title="Выберите файл кодов наборов",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        if file_path:
            self.parent_file = file_path
            self.lbl_parent.config(text=os.path.basename(file_path), fg="black")
            self.log(f"Выбран файл наборов: {file_path}")

    def select_child_files(self):
        files = filedialog.askopenfilenames(
            title="Выберите файлы кодов вложений",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        if files:
            self.child_files = list(files)
            self.lbl_child.config(text=f"Выбрано файлов: {len(self.child_files)}", fg="black")
            self.log(f"Выбрано файлов вложений: {len(self.child_files)}")
            for f in self.child_files:
                self.log(f"  - {os.path.basename(f)}")

    def run_aggregation(self):
        if not self.parent_file:
            messagebox.showerror("Ошибка", "Пожалуйста, выберите файл с кодами наборов.")
            return

        if not self.child_files:
            messagebox.showerror("Ошибка", "Пожалуйста, выберите файлы с кодами вложений.")
            return

        try:
            items_per_set = int(self.spin_count.get())
            if items_per_set <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Ошибка", "Введите корректное число вложений (целое положительное число).")
            return

        try:
            output_dir, created_count, used_child_count = perform_aggregation(
                parent_file=self.parent_file,
                child_files=self.child_files,
                items_per_set=items_per_set
            )

            self.log("----------------------------------------")
            self.log("Агрегация успешно завершена!")
            self.log(f"Результаты сохранены в папку: {os.path.abspath(output_dir)}")
            self.log(f"Создано файлов наборов: {created_count}")
            self.log(f"Использовано кодов вложений: {used_child_count}")
            self.log("----------------------------------------")

            messagebox.showinfo(
                "Успех",
                f"Агрегация завершена!\n\nСоздано наборов: {created_count}\nПапка: {output_dir}"
            )

        except Exception as e:
            self.log(f"Ошибка при выполнении: {str(e)}")
            messagebox.showerror("Ошибка агрегации", str(e))


def main():
    root = tk.Tk()
    app = VirtualAggregationApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
