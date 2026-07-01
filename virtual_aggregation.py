"""
Скрипт для виртуальной агрегации кодов маркировки.
Позволяет сгруппировать коды вложений под родительскими кодами наборов.

Инструкция по сборке в EXE:
1. Установите PyInstaller: pip install pyinstaller
2. Выполните команду: pyinstaller --noconsole --onefile virtual_aggregation.py
"""

import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
import os
import datetime
import re

class VirtualAggregationApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Виртуальная агрегация")
        self.root.geometry("600x500")

        self.parent_file = ""
        self.child_files = []

        # UI Layout
        tk.Label(root, text="1. Выберите файл с кодами наборов (родители):").pack(pady=(10, 0))
        self.btn_parent = tk.Button(root, text="Выбрать родительский файл", command=self.select_parent_file)
        self.btn_parent.pack(pady=5)
        self.lbl_parent = tk.Label(root, text="Файл не выбран", fg="gray")
        self.lbl_parent.pack()

        tk.Label(root, text="2. Выберите файлы с кодами вложений (дети):").pack(pady=(10, 0))
        self.btn_children = tk.Button(root, text="Выбрать файлы вложений", command=self.select_child_files)
        self.btn_children.pack(pady=5)
        self.lbl_children = tk.Label(root, text="Файлы не выбраны", fg="gray")
        self.lbl_children.pack()

        tk.Label(root, text="3. Количество вложений в один набор:").pack(pady=(10, 0))
        self.entry_count = tk.Entry(root)
        self.entry_count.insert(0, "1")
        self.entry_count.pack(pady=5)

        self.btn_start = tk.Button(root, text="ЗАПУСТИТЬ АГРЕГАЦИЮ", command=self.start_aggregation, bg="green", fg="white", font=("Arial", 10, "bold"))
        self.btn_start.pack(pady=20)

        self.log_area = scrolledtext.ScrolledText(root, height=10)
        self.log_area.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

    def log(self, message):
        self.log_area.insert(tk.END, f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {message}\n")
        self.log_area.see(tk.END)

    def read_codes(self, file_path):
        encodings = ['utf-8-sig', 'utf-16', 'utf-8', 'cp1251']
        for enc in encodings:
            try:
                with open(file_path, 'r', encoding=enc) as f:
                    content = f.read()
                    # Если utf-16 прочитал абракадабру (например 1 байт на символ), контент может быть очень странным
                    # Но обычно он просто падает.
                    lines = [line.strip() for line in content.splitlines() if line.strip()]
                    return lines
            except (UnicodeDecodeError, UnicodeError):
                continue
        return []

    def select_parent_file(self):
        file = filedialog.askopenfilename(filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if file:
            self.parent_file = file
            self.lbl_parent.config(text=os.path.basename(file), fg="black")
            self.log(f"Выбран родительский файл: {file}")

    def select_child_files(self):
        files = filedialog.askopenfilenames(filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if files:
            self.child_files = list(files)
            self.lbl_children.config(text=f"Выбрано файлов: {len(files)}", fg="black")
            self.log(f"Выбрано файлов вложений: {len(files)}")

    def start_aggregation(self):
        if not self.parent_file:
            messagebox.showerror("Ошибка", "Выберите родительский файл!")
            return
        if not self.child_files:
            messagebox.showerror("Ошибка", "Выберите файлы вложений!")
            return

        try:
            count_per_parent = int(self.entry_count.get())
            if count_per_parent <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Ошибка", "Количество вложений должно быть положительным числом!")
            return

        parents = self.read_codes(self.parent_file)
        if not parents:
            messagebox.showerror("Ошибка", "Родительский файл пуст!")
            return

        all_children = []
        for cf in self.child_files:
            all_children.extend(self.read_codes(cf))

        if not all_children:
            messagebox.showerror("Ошибка", "Файлы вложений пусты!")
            return

        total_required = len(parents) * count_per_parent
        if len(all_children) < total_required:
            if not messagebox.askyesno("Предупреждение", f"Вложений ({len(all_children)}) меньше, чем требуется ({total_required}). Продолжить с частичным результатом?"):
                return

        def confirm_callback(msg):
            return messagebox.askyesno("Подтверждение", msg)

        def log_callback(msg):
            self.log(msg)

        success_count, output_dir = perform_aggregation(
            parents, all_children, count_per_parent, log_callback, confirm_callback
        )

        if success_count > 0:
            messagebox.showinfo("Готово", f"Агрегация завершена!\nСоздано файлов: {success_count}\nПапка: {output_dir}")

def sanitize_filename(filename):
    return re.sub(r'[\\/*?:"<>|]', "_", filename)

def perform_aggregation(parents, all_children, count_per_parent, log_fn=None, confirm_fn=None):
    total_required = len(parents) * count_per_parent
    if len(all_children) < total_required:
        if confirm_fn and not confirm_fn(f"Вложений ({len(all_children)}) меньше, чем требуется ({total_required}). Продолжить?"):
            return 0, None

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = f"aggregation_results_{timestamp}"
    os.makedirs(output_dir, exist_ok=True)

    if log_fn:
        log_fn(f"Начало агрегации. Папка: {output_dir}")

    success_count = 0
    child_idx = 0

    for p_code in parents:
        if child_idx + count_per_parent > len(all_children):
            if log_fn:
                log_fn(f"Недостаточно вложений для набора: {p_code}")
            break

        subset = all_children[child_idx : child_idx + count_per_parent]
        child_idx += count_per_parent

        safe_name = sanitize_filename(p_code)
        file_path = os.path.join(output_dir, f"{safe_name}.txt")

        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(p_code + "\n")
                for c_code in subset:
                    f.write(c_code + "\n")
            success_count += 1
        except Exception as e:
            if log_fn:
                log_fn(f"Ошибка при записи файла {safe_name}: {e}")

    if log_fn:
        log_fn(f"Агрегация завершена. Создано файлов: {success_count}")

    return success_count, output_dir

if __name__ == "__main__":
    root = tk.Tk()
    app = VirtualAggregationApp(root)
    root.mainloop()
