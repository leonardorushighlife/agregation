"""
Скрипт для виртуальной агрегации кодов маркировки.
Позволяет распределить дочерние коды по родительским и сохранить каждый набор в отдельный файл.

Инструкция по сборке в EXE:
1. Установите pyinstaller: pip install pyinstaller
2. Соберите проект: pyinstaller --noconsole --onefile virtual_aggregation.py
"""

import tkinter as tk
from tkinter import filedialog, messagebox
import os
import datetime
import re
import traceback

def sanitize_filename(filename):
    # Удаление недопустимых символов для имени файла в Windows
    return re.sub(r'[\\/*?:"<>|]', "_", filename)

def read_codes_from_file(filepath):
    """Читает коды из файла, пробуя разные кодировки."""
    encodings = ['utf-8', 'utf-8-sig', 'cp1251', 'utf-16']
    for enc in encodings:
        try:
            with open(filepath, 'r', encoding=enc) as f:
                return [line.strip() for line in f if line.strip()]
        except (UnicodeDecodeError, UnicodeError):
            continue
    # Если ничего не помогло, попробуем с игнорированием ошибок
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        return [line.strip() for line in f if line.strip()]

class VirtualAggregationApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Виртуальная агрегация (наборы)")
        self.root.geometry("600x450")

        self.parent_file = ""
        self.child_files = []

        # UI элементы
        tk.Label(root, text="Виртуальная агрегация кодов", font=("Arial", 16, "bold")).pack(pady=20)

        # Выбор родительского файла
        frame_p = tk.LabelFrame(root, text="1. Коды наборов (Родители)", padx=10, pady=10)
        frame_p.pack(fill="x", padx=20, pady=5)

        self.btn_parent = tk.Button(frame_p, text="Выбрать файл", command=self.select_parent_file)
        self.btn_parent.pack(side="left")

        self.lbl_parent = tk.Label(frame_p, text="Файл не выбран", fg="red", wraplength=400)
        self.lbl_parent.pack(side="left", padx=10)

        # Количество вложений
        frame_c_count = tk.Frame(root, padx=10, pady=10)
        frame_c_count.pack(fill="x", padx=20)

        tk.Label(frame_c_count, text="Количество вложений в один набор:").pack(side="left")
        self.entry_count = tk.Entry(frame_c_count, width=10, justify="center")
        self.entry_count.insert(0, "1")
        self.entry_count.pack(side="left", padx=10)

        # Выбор дочерних файлов
        frame_c = tk.LabelFrame(root, text="2. Коды вложений (Дети)", padx=10, pady=10)
        frame_c.pack(fill="x", padx=20, pady=5)

        self.btn_children = tk.Button(frame_c, text="Выбрать файлы", command=self.select_child_files)
        self.btn_children.pack(side="left")

        self.lbl_children = tk.Label(frame_c, text="Файлы не выбраны", fg="red", wraplength=400)
        self.lbl_children.pack(side="left", padx=10)

        # Кнопка запуска
        self.btn_run = tk.Button(root, text="ЗАПУСТИТЬ АГРЕГАЦИЮ", font=("Arial", 12, "bold"),
                                 bg="#4CAF50", fg="white", height=2, command=self.run_aggregation)
        self.btn_run.pack(pady=30, fill="x", padx=50)

    def select_parent_file(self):
        file = filedialog.askopenfilename(title="Выберите файл с кодами наборов",
                                          filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if file:
            self.parent_file = file
            self.lbl_parent.config(text=os.path.basename(file), fg="black")

    def select_child_files(self):
        files = filedialog.askopenfilenames(title="Выберите файлы с кодами вложений",
                                            filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if files:
            self.child_files = list(files)
            self.lbl_children.config(text=f"Выбрано файлов: {len(files)}", fg="black")

    def run_aggregation(self):
        if not self.parent_file:
            messagebox.showerror("Ошибка", "Выберите файл с кодами наборов!")
            return
        if not self.child_files:
            messagebox.showerror("Ошибка", "Выберите файлы с кодами вложений!")
            return

        try:
            count_per_set = int(self.entry_count.get())
            if count_per_set <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Ошибка", "Введите корректное положительное число вложений!")
            return

        try:
            processed_count, output_dir = perform_aggregation(
                self.parent_file,
                self.child_files,
                count_per_set,
                confirm_callback=lambda msg: messagebox.askyesno("Предупреждение", msg)
            )

            if processed_count > 0:
                messagebox.showinfo("Готово",
                                    f"Агрегация завершена!\n\n"
                                    f"Обработано наборов: {processed_count}\n"
                                    f"Всего вложений: {processed_count * count_per_set}\n"
                                    f"Результаты сохранены в папку:\n{os.path.abspath(output_dir)}")

                # Открыть папку в проводнике (для Windows)
                try:
                    os.startfile(output_dir)
                except:
                    pass

        except Exception as e:
            error_msg = traceback.format_exc()
            messagebox.showerror("Критическая ошибка", f"Произошла ошибка при выполнении:\n{str(e)}\n\n{error_msg}")

def perform_aggregation(parent_file, child_files, count_per_set, confirm_callback=None):
    # Чтение кодов
    parents = read_codes_from_file(parent_file)
    children = []
    for cf in child_files:
        children.extend(read_codes_from_file(cf))

    if not parents:
        raise Exception("Файл с родительскими кодами пуст!")
    if not children:
        raise Exception("Файлы с дочерними кодами пусты!")

    total_needed = len(parents) * count_per_set
    if len(children) < total_needed:
        msg = f"Дочерних кодов ({len(children)}) меньше, чем требуется для всех наборов ({total_needed}).\n"
        msg += f"Будет создано только {len(children) // count_per_set} полных наборов. Продолжить?"
        if confirm_callback and not confirm_callback(msg):
            return 0, ""

    # Создание папки
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = f"aggregation_results_{timestamp}"
    os.makedirs(output_dir, exist_ok=True)

    processed_count = 0
    child_idx = 0

    for parent in parents:
        if child_idx + count_per_set > len(children):
            break

        set_children = children[child_idx : child_idx + count_per_set]
        child_idx += count_per_set

        # Сохранение в файл
        safe_parent = sanitize_filename(parent)
        filename = safe_parent + ".txt"
        filepath = os.path.join(output_dir, filename)

        # Если файл уже существует, добавляем индекс
        if os.path.exists(filepath):
            idx = 1
            while os.path.exists(os.path.join(output_dir, f"{safe_parent}_{idx}.txt")):
                idx += 1
            filepath = os.path.join(output_dir, f"{safe_parent}_{idx}.txt")

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(parent + "\n")
            for c in set_children:
                f.write(c + "\n")

        processed_count += 1

    return processed_count, output_dir

if __name__ == "__main__":
    root = tk.Tk()
    app = VirtualAggregationApp(root)
    root.mainloop()
