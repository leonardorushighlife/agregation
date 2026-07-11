# Инструкция по сборке в EXE:
# pip install pyinstaller
# pyinstaller --noconsole --onefile virtual_aggregation.py

import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from datetime import datetime
import re

def read_codes(filepaths):
    """Считывает коды из списка файлов, поддерживая разные кодировки."""
    if isinstance(filepaths, str):
        filepaths = [filepaths]

    codes = []
    encodings = ['utf-8-sig', 'utf-16', 'utf-8', 'cp1251']

    for path in filepaths:
        success = False
        for enc in encodings:
            try:
                with open(path, 'r', encoding=enc) as f:
                    content = f.read()
                    # Разделяем по строкам, убираем пробелы и пустые строки
                    file_codes = [line.strip() for line in content.splitlines() if line.strip()]
                    codes.extend(file_codes)
                success = True
                break
            except (UnicodeDecodeError, UnicodeError):
                continue
        if not success:
            raise Exception(f"Не удалось прочитать файл {path}. Неподдерживаемая кодировка.")
    return codes

def sanitize_filename(name):
    """Удаляет недопустимые символы для имен файлов Windows."""
    return re.sub(r'[\\/*?:"<>|]', '_', name)

def perform_aggregation(parent_codes, child_codes, count_per_parent, callback_info=None):
    """
    Основная логика сопоставления кодов.
    Возвращает список кортежей (parent, [children])
    """
    total_required = len(parent_codes) * count_per_parent
    if len(child_codes) < total_required:
        actual_sets = len(child_codes) // count_per_parent
        if callback_info:
            if not callback_info(len(parent_codes), len(child_codes), actual_sets, count_per_parent):
                return None
        parent_codes = parent_codes[:actual_sets]

    results = []
    for i, p_code in enumerate(parent_codes):
        start_idx = i * count_per_parent
        end_idx = start_idx + count_per_parent
        results.append((p_code, child_codes[start_idx:end_idx]))

    return results

class VirtualAggregationApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Виртуальная агрегация")
        self.root.geometry("600x450")
        self.root.resizable(False, False)

        self.parent_file = ""
        self.child_files = []

        # UI Elements
        tk.Label(root, text="Виртуальная агрегация", font=("Arial", 18, "bold")).pack(pady=20)

        frame = tk.Frame(root)
        frame.pack(pady=10, padx=20, fill="x")

        # Parent file selection
        self.btn_parent = tk.Button(frame, text="Выбрать файл кодов НАБОРОВ (1 файл)", command=self.select_parent, width=40)
        self.btn_parent.pack(pady=5)
        self.lbl_parent = tk.Label(frame, text="Файл не выбран", fg="red", wraplength=500)
        self.lbl_parent.pack()

        # Child files selection
        self.btn_children = tk.Button(frame, text="Выбрать файлы кодов ВЛОЖЕНИЙ (например, 3 файла)", command=self.select_children, width=40)
        self.btn_children.pack(pady=(15, 5))
        self.lbl_children = tk.Label(frame, text="Файлы не выбраны", fg="red", wraplength=500)
        self.lbl_children.pack()

        # Attachments count
        tk.Label(frame, text="Количество вложений в каждом наборе:", font=("Arial", 10)).pack(pady=(20, 0))
        self.ent_count = tk.Entry(frame, justify='center', font=("Arial", 12), width=10)
        self.ent_count.insert(0, "1")
        self.ent_count.pack(pady=5)

        # Start button
        self.btn_start = tk.Button(root, text="НАЧАТЬ АГРЕГАЦИЮ", command=self.start_aggregation,
                                   bg="#4CAF50", fg="white", font=("Arial", 14, "bold"), height=2, width=25)
        self.btn_start.pack(pady=30)

    def select_parent(self):
        file = filedialog.askopenfilename(title="Выберите файл с кодами наборов", filetypes=[("Text files", "*.txt")])
        if file:
            self.parent_file = file
            self.lbl_parent.config(text=os.path.basename(file), fg="green")

    def select_children(self):
        files = filedialog.askopenfilenames(title="Выберите файлы с кодами вложений", filetypes=[("Text files", "*.txt")])
        if files:
            self.child_files = list(files)
            self.lbl_children.config(text=f"Выбрано файлов: {len(self.child_files)}", fg="green")

    def start_aggregation(self):
        if not self.parent_file:
            messagebox.showerror("Ошибка", "Выберите файл с кодами наборов!")
            return
        if not self.child_files:
            messagebox.showerror("Ошибка", "Выберите файлы с кодами вложений!")
            return

        try:
            count_per_parent = int(self.ent_count.get())
            if count_per_parent <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Ошибка", "Введите корректное количество вложений (целое число больше 0)!")
            return

        try:
            parent_codes = read_codes(self.parent_file)
            child_codes = read_codes(self.child_files)
        except Exception as e:
            messagebox.showerror("Ошибка при чтении файлов", str(e))
            return

        if not parent_codes:
            messagebox.showerror("Ошибка", "Файл кодов наборов пуст!")
            return
        if not child_codes:
            messagebox.showerror("Ошибка", "Файлы вложений пусты!")
            return

        def confirm_partial(p_len, c_len, actual, per_p):
            return messagebox.askokcancel("Предупреждение",
                f"Недостаточно вложений для всех наборов.\n\n"
                f"Кодов наборов: {p_len}\n"
                f"Кодов вложений: {c_len}\n"
                f"Требуется на набор: {per_p}\n\n"
                f"Будет собрано наборов: {actual}\n"
                f"Продолжить?")

        aggregated_data = perform_aggregation(parent_codes, child_codes, count_per_parent, confirm_partial)

        if not aggregated_data:
            return

        # Создание папки для результатов
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = f"aggregation_results_{timestamp}"
        os.makedirs(output_dir, exist_ok=True)

        count_created = 0
        used_filenames = set()

        for p_code, children in aggregated_data:
            base_name = sanitize_filename(p_code)
            filename = f"{base_name}.txt"

            # Обработка коллизий имен файлов
            counter = 1
            while filename in used_filenames:
                filename = f"{base_name}_{counter}.txt"
                counter += 1

            used_filenames.add(filename)

            file_path = os.path.join(output_dir, filename)
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(p_code + "\n")
                for c_code in children:
                    f.write(c_code + "\n")
            count_created += 1

        messagebox.showinfo("Успех", f"Агрегация завершена!\nСоздано файлов: {count_created}\nПапка: {output_dir}")

if __name__ == "__main__":
    root = tk.Tk()
    app = VirtualAggregationApp(root)
    root.mainloop()
