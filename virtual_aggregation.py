import tkinter as tk
from tkinter import filedialog, messagebox
import os
import datetime
import re
import traceback

def sanitize_filename(filename):
    """Удаляет недопустимые символы для имен файлов Windows."""
    return re.sub(r'[\\/*?:"<>|]', '_', filename)

def read_codes(filepath):
    """Читает коды из файла с поддержкой различных кодировок."""
    encodings = ['utf-8-sig', 'utf-8', 'cp1251', 'utf-16']
    for enc in encodings:
        try:
            with open(filepath, 'r', encoding=enc) as f:
                return [line.strip() for line in f if line.strip()]
        except (UnicodeDecodeError, LookupError):
            continue
    raise Exception(f"Не удалось прочитать файл {filepath} в поддерживаемых кодировках.")

class VirtualAggregationApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Виртуальная агрегация")
        self.root.geometry("500x400")

        self.parent_file = ""
        self.child_files = []

        # Интерфейс
        tk.Label(root, text="Виртуальная агрегация", font=("Arial", 16)).pack(pady=10)

        # Выбор родительского файла
        self.btn_parent = tk.Button(root, text="Выбрать файл с кодами наборов (1 файл)", command=self.select_parent)
        self.btn_parent.pack(pady=5)
        self.lbl_parent = tk.Label(root, text="Файл не выбран", fg="gray")
        self.lbl_parent.pack()

        # Выбор дочерних файлов
        self.btn_children = tk.Button(root, text="Выбрать файлы с кодами вложений (TXT)", command=self.select_children)
        self.btn_children.pack(pady=5)
        self.lbl_children = tk.Label(root, text="Файлы не выбраны", fg="gray")
        self.lbl_children.pack()

        # Количество вложений
        tk.Label(root, text="Количество вложений в один набор:").pack(pady=10)
        self.entry_count = tk.Entry(root)
        self.entry_count.insert(0, "4")  # Значение по умолчанию
        self.entry_count.pack()

        # Кнопка запуска
        self.btn_run = tk.Button(root, text="Начать агрегацию", command=self.run_aggregation, bg="green", fg="white", font=("Arial", 12, "bold"))
        self.btn_run.pack(pady=30)

    def select_parent(self):
        filename = filedialog.askopenfilename(title="Выберите файл с кодами наборов", filetypes=[("Text files", "*.txt")])
        if filename:
            self.parent_file = filename
            self.lbl_parent.config(text=os.path.basename(filename), fg="black")

    def select_children(self):
        filenames = filedialog.askopenfilenames(title="Выберите файлы с кодами вложений", filetypes=[("Text files", "*.txt")])
        if filenames:
            self.child_files = list(filenames)
            self.lbl_children.config(text=f"Выбрано файлов: {len(filenames)}", fg="black")

    def run_aggregation(self):
        try:
            # Валидация
            if not self.parent_file:
                messagebox.showwarning("Предупреждение", "Выберите файл с кодами наборов!")
                return
            if not self.child_files:
                messagebox.showwarning("Предупреждение", "Выберите файлы с кодами вложений!")
                return

            try:
                count_per_set = int(self.entry_count.get())
                if count_per_set <= 0:
                    raise ValueError
            except ValueError:
                messagebox.showwarning("Предупреждение", "Введите корректное число вложений!")
                return

            self.perform_aggregation(count_per_set)

        except Exception as e:
            error_msg = traceback.format_exc()
            messagebox.showerror("Ошибка", f"Произошла ошибка:\n{error_msg}")

    def perform_aggregation(self, count_per_set):
        # 1. Читаем родительские коды
        parents = read_codes(self.parent_file)

        # 2. Читаем дочерние коды и объединяем в общий пул
        all_children = []
        for f in self.child_files:
            all_children.extend(read_codes(f))

        if not parents:
            messagebox.showwarning("Предупреждение", "Файл с кодами наборов пуст!")
            return
        if not all_children:
            messagebox.showwarning("Предупреждение", "Файлы с кодами вложений пусты!")
            return

        # 3. Расчет количества возможных наборов
        max_sets_by_children = len(all_children) // count_per_set
        actual_sets = min(len(parents), max_sets_by_children)

        if actual_sets == 0:
            messagebox.showwarning("Предупреждение", f"Недостаточно вложений ({len(all_children)}) для создания хотя бы одного набора из {count_per_set} шт.")
            return

        # 4. Создаем папку для результатов
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = f"aggregation_results_{timestamp}"
        os.makedirs(output_dir, exist_ok=True)

        # 5. Процесс агрегации
        for i in range(actual_sets):
            parent_code = parents[i]
            child_subset = all_children[i * count_per_set : (i + 1) * count_per_set]

            # Санитизируем имя файла
            safe_name = sanitize_filename(parent_code)
            file_path = os.path.join(output_dir, f"{safe_name}.txt")

            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(parent_code + "\n")
                for child in child_subset:
                    f.write(child + "\n")

        messagebox.showinfo("Успех", f"Агрегация завершена!\nСоздано наборов: {actual_sets}\nРезультаты в папке: {output_dir}")

if __name__ == "__main__":
    root = tk.Tk()
    app = VirtualAggregationApp(root)
    root.mainloop()
