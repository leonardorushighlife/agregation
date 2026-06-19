import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import os
from datetime import datetime
import traceback

def sanitize_filename(filename):
    """Очистка имени файла от недопустимых символов."""
    for char in ['<', '>', ':', '"', '/', '\\', '|', '?', '*']:
        filename = filename.replace(char, '_')
    return filename

def read_codes(filepath):
    """Чтение кодов из файла с поддержкой различных кодировок."""
    encodings = ['utf-8-sig', 'utf-8', 'cp1251', 'utf-16']
    for enc in encodings:
        try:
            with open(filepath, 'r', encoding=enc) as f:
                return [line.strip() for line in f if line.strip()]
        except (UnicodeDecodeError, LookupError):
            continue
    raise Exception(f"Не удалось прочитать файл {filepath}. Проверьте кодировку.")

def perform_aggregation(parent_file, child_files, count_per_set):
    if not parent_file:
        raise Exception("Не выбран файл с кодами наборов (родители).")
    if not child_files:
        raise Exception("Не выбраны файлы с кодами вложений (дети).")
    if not count_per_set or int(count_per_set) <= 0:
        raise Exception("Укажите корректное количество вложений.")

    count_per_set = int(count_per_set)

    # Загрузка кодов
    parents = read_codes(parent_file)
    children = []
    for cf in child_files:
        children.extend(read_codes(cf))

    if not parents:
        raise Exception("Файл родителей пуст.")
    if not children:
        raise Exception("Файлы вложений пусты.")

    needed_children = len(parents) * count_per_set
    if len(children) < needed_children:
        if not messagebox.askyesno("Предупреждение",
                                   f"Кодов вложений ({len(children)}) меньше, чем требуется для всех наборов ({needed_children}).\n"
                                   f"Продолжить и собрать сколько получится?"):
            return

    # Создание папки
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = f"aggregation_results_{timestamp}"
    os.makedirs(output_dir, exist_ok=True)

    actual_sets = min(len(parents), len(children) // count_per_set)

    for i in range(actual_sets):
        p_code = parents[i]
        c_codes = children[i * count_per_set : (i + 1) * count_per_set]

        safe_name = sanitize_filename(p_code)
        output_file = os.path.join(output_dir, f"{safe_name}.txt")

        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(p_code + "\n")
            for c in c_codes:
                f.write(c + "\n")

    messagebox.showinfo("Готово", f"Агрегация завершена.\nОбработано наборов: {actual_sets}\nРезультаты в папке: {output_dir}")

class AggregatorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Виртуальная агрегация")
        self.root.geometry("600x450")

        self.parent_file = ""
        self.child_files = []

        style = ttk.Style()
        style.configure("TButton", padding=6, font=('Arial', 10))

        main_frame = ttk.Frame(root, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Родительский файл
        ttk.Label(main_frame, text="Файл с кодами наборов (родители):", font=('Arial', 10, 'bold')).pack(anchor=tk.W)
        self.parent_label = ttk.Label(main_frame, text="Файл не выбран", foreground="gray")
        self.parent_label.pack(anchor=tk.W, pady=(0, 10))
        ttk.Button(main_frame, text="Выбрать файл родителей", command=self.select_parent).pack(anchor=tk.W, pady=(0, 20))

        # Дочерние файлы
        ttk.Label(main_frame, text="Файлы с кодами вложений (дети):", font=('Arial', 10, 'bold')).pack(anchor=tk.W)
        self.child_label = ttk.Label(main_frame, text="Файлы не выбраны (0)", foreground="gray")
        self.child_label.pack(anchor=tk.W, pady=(0, 10))
        ttk.Button(main_frame, text="Выбрать файлы вложений", command=self.select_children).pack(anchor=tk.W, pady=(0, 20))

        # Количество вложений
        ttk.Label(main_frame, text="Количество вложений в один набор:", font=('Arial', 10, 'bold')).pack(anchor=tk.W)
        self.count_entry = ttk.Entry(main_frame, width=10)
        self.count_entry.insert(0, "1")
        self.count_entry.pack(anchor=tk.W, pady=(0, 30))

        # Кнопка запуска
        self.start_btn = ttk.Button(main_frame, text="НАЧАТЬ АГРЕГАЦИЮ", command=self.run_aggregation)
        self.start_btn.pack(fill=tk.X, ipady=10)

    def select_parent(self):
        file = filedialog.askopenfilename(title="Выберите файл родителей", filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if file:
            self.parent_file = file
            self.parent_label.config(text=os.path.basename(file), foreground="black")

    def select_children(self):
        files = filedialog.askopenfilenames(title="Выберите файлы вложений", filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if files:
            self.child_files = list(files)
            self.child_label.config(text=f"Выбрано файлов: {len(files)}", foreground="black")

    def run_aggregation(self):
        try:
            perform_aggregation(self.parent_file, self.child_files, self.count_entry.get())
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Ошибка", str(e))

if __name__ == "__main__":
    root = tk.Tk()
    app = AggregatorApp(root)
    root.mainloop()
