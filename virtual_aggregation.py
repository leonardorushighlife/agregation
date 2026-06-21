import tkinter as tk
from tkinter import filedialog, messagebox, ttk
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

        self.create_widgets()

    def create_widgets(self):
        # Parent file selection
        self.parent_btn = tk.Button(self.root, text="Выбрать файл с кодами наборов (Родители)", command=self.select_parent_file)
        self.parent_btn.pack(pady=10, fill=tk.X, padx=20)

        self.parent_label = tk.Label(self.root, text="Файл не выбран", fg="gray")
        self.parent_label.pack()

        # Child files selection
        self.child_btn = tk.Button(self.root, text="Выбрать файлы с кодами вложений (Дети)", command=self.select_child_files)
        self.child_btn.pack(pady=10, fill=tk.X, padx=20)

        self.child_label = tk.Label(self.root, text="Файлы не выбраны", fg="gray")
        self.child_label.pack()

        # Count per parent
        count_frame = tk.Frame(self.root)
        count_frame.pack(pady=10)
        tk.Label(count_frame, text="Количество вложений в один набор:").pack(side=tk.LEFT)
        self.count_entry = tk.Entry(count_frame, width=10)
        self.count_entry.insert(0, "1")
        self.count_entry.pack(side=tk.LEFT, padx=5)

        # Action button
        self.process_btn = tk.Button(self.root, text="Начать агрегацию", bg="green", fg="white", font=("Arial", 12, "bold"), command=self.process)
        self.process_btn.pack(pady=20, fill=tk.X, padx=20)

        # Log area
        self.log_text = tk.Text(self.root, height=10, state=tk.DISABLED)
        self.log_text.pack(pady=10, fill=tk.BOTH, expand=True, padx=20)

    def log(self, message):
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {message}\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)

    def select_parent_file(self):
        file = filedialog.askopenfilename(filetypes=[("Text files", "*.txt")])
        if file:
            self.parent_file = file
            self.parent_label.config(text=os.path.basename(file), fg="black")
            self.log(f"Выбран родительский файл: {os.path.basename(file)}")

    def select_child_files(self):
        files = filedialog.askopenfilenames(filetypes=[("Text files", "*.txt")])
        if files:
            self.child_files = list(files)
            self.child_label.config(text=f"Выбрано файлов: {len(files)}", fg="black")
            self.log(f"Выбрано дочерних файлов: {len(files)}")

    def process(self):
        if not self.parent_file:
            messagebox.showerror("Ошибка", "Выберите родительский файл!")
            return
        if not self.child_files:
            messagebox.showerror("Ошибка", "Выберите файлы вложений!")
            return

        try:
            count = int(self.count_entry.get())
            if count <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Ошибка", "Введите корректное количество вложений (целое число > 0)")
            return

        try:
            self.log("Загрузка кодов...")
            parents = read_codes(self.parent_file)
            children = read_codes(self.child_files)

            self.log(f"Загружено: {len(parents)} родителей, {len(children)} вложений.")

            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            output_dir = f"aggregation_results_{timestamp}"

            self.log(f"Начало агрегации в папку: {output_dir}")

            processed = perform_aggregation(parents, children, count, output_dir, self.log)

            self.log(f"Успешно завершено! Обработано наборов: {processed}")
            messagebox.showinfo("Готово", f"Агрегация завершена!\nОбработано наборов: {processed}\nРезультаты в папке: {output_dir}")

        except Exception as e:
            self.log(f"ОШИБКА: {str(e)}")
            messagebox.showerror("Ошибка", str(e))

def read_codes(filepaths):
    """Читает коды из одного или нескольких файлов с поддержкой разных кодировок."""
    if isinstance(filepaths, str):
        filepaths = [filepaths]

    codes = []
    encodings = ['utf-8', 'utf-8-sig', 'utf-16', 'cp1251']

    for path in filepaths:
        success = False
        for enc in encodings:
            try:
                with open(path, 'r', encoding=enc) as f:
                    content = f.read()
                    # Разделяем по строкам, удаляем пустые и пробелы
                    file_codes = [line.strip() for line in content.splitlines() if line.strip()]
                    codes.extend(file_codes)
                    success = True
                    break
            except (UnicodeDecodeError, Exception):
                continue
        if not success:
            raise Exception(f"Не удалось прочитать файл {path}. Проверьте кодировку.")
    return codes

def sanitize_filename(filename):
    """Удаляет недопустимые символы из имени файла."""
    return re.sub(r'[\\/*?:"<>|]', "_", filename)

def perform_aggregation(parent_codes, child_codes, count_per_parent, output_dir, log_callback=None):
    """Выполняет логику агрегации."""
    if not parent_codes:
        raise Exception("Список родительских кодов пуст.")
    if not child_codes:
        raise Exception("Список кодов вложений пуст.")

    total_needed = len(parent_codes) * count_per_parent
    if len(child_codes) < total_needed:
        actual_sets = len(child_codes) // count_per_parent
        if log_callback:
            log_callback(f"ПРЕДУПРЕЖДЕНИЕ: Недостаточно вложений. Будет обработано только {actual_sets} наборов.")
        parent_codes = parent_codes[:actual_sets]

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    for i, parent_code in enumerate(parent_codes):
        start_idx = i * count_per_parent
        end_idx = start_idx + count_per_parent
        current_children = child_codes[start_idx:end_idx]

        # Санитарная очистка имени файла (используем часть кода или весь код)
        safe_name = sanitize_filename(parent_code[:50]) # Ограничим длину
        filename = f"{safe_name}.txt"
        filepath = os.path.join(output_dir, filename)

        # Если файл уже существует, добавим индекс
        counter = 1
        while os.path.exists(filepath):
            filename = f"{safe_name}_{counter}.txt"
            filepath = os.path.join(output_dir, filename)
            counter += 1

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(parent_code + '\n')
            for child in current_children:
                f.write(child + '\n')

    return len(parent_codes)


if __name__ == "__main__":
    root = tk.Tk()
    app = VirtualAggregationApp(root)
    root.mainloop()
