import tkinter as tk
from tkinter import filedialog, messagebox
import os
from datetime import datetime
import re

def sanitize_filename(filename):
    # Удаляем символы, запрещенные в именах файлов Windows
    return re.sub(r'[\\/*?:"<>|]', "_", filename)

def read_file_with_encodings(filepath):
    encodings = ['utf-8-sig', 'utf-8', 'cp1251', 'utf-16']
    for enc in encodings:
        try:
            with open(filepath, 'r', encoding=enc) as f:
                return [line.strip() for line in f if line.strip()]
        except (UnicodeDecodeError, LookupError):
            continue
    raise Exception(f"Не удалось прочитать файл {filepath}. Проверьте кодировку.")

class VirtualAggregationApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Виртуальная агрегация")
        self.root.geometry("500x450")

        self.parent_file = ""
        self.child_files = []

        # Элементы интерфейса
        tk.Label(root, text="Виртуальная агрегация", font=("Arial", 16)).pack(pady=10)

        tk.Button(root, text="Выбрать файл с кодами набора (родитель)", command=self.select_parent).pack(pady=5)
        self.lbl_parent = tk.Label(root, text="Файл не выбран", fg="grey", wraplength=450)
        self.lbl_parent.pack()

        tk.Button(root, text="Выбрать файлы с кодами вложений (дети)", command=self.select_children).pack(pady=5)
        self.lbl_children = tk.Label(root, text="Файлы не выбраны", fg="grey", wraplength=450)
        self.lbl_children.pack()

        tk.Label(root, text="Количество вложений в один набор:").pack(pady=(15, 0))
        self.entry_count = tk.Entry(root, justify="center")
        self.entry_count.insert(0, "1")
        self.entry_count.pack(pady=5)

        tk.Button(root, text="ЗАПУСТИТЬ АГРЕГАЦИЮ", font=("Arial", 12, "bold"), bg="green", fg="white",
                  command=self.run_aggregation).pack(pady=30)

    def select_parent(self):
        self.parent_file = filedialog.askopenfilename(title="Выберите файл с родительскими кодами",
                                                       filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if self.parent_file:
            self.lbl_parent.config(text=os.path.basename(self.parent_file), fg="black")

    def select_children(self):
        self.child_files = filedialog.askopenfilenames(title="Выберите файлы с кодами вложений",
                                                        filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if self.child_files:
            self.lbl_children.config(text=f"Выбрано файлов: {len(self.child_files)}", fg="black")

    def run_aggregation(self):
        if not self.parent_file:
            messagebox.showerror("Ошибка", "Выберите файл с кодами набора!")
            return
        if not self.child_files:
            messagebox.showerror("Ошибка", "Выберите файлы с кодами вложений!")
            return

        try:
            count_per_set = int(self.entry_count.get())
            if count_per_set <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Ошибка", "Введите корректное число вложений!")
            return

        try:
            parent_codes = read_file_with_encodings(self.parent_file)
            all_child_codes = []
            for f in self.child_files:
                all_child_codes.extend(read_file_with_encodings(f))

            if not parent_codes:
                messagebox.showerror("Ошибка", "Файл родителей пуст!")
                return
            if not all_child_codes:
                messagebox.showerror("Ошибка", "Файлы вложений пусты!")
                return

            num_parents = len(parent_codes)
            num_children = len(all_child_codes)

            # Рассчитываем сколько наборов мы можем собрать
            actual_sets = min(num_parents, num_children // count_per_set)

            if actual_sets == 0:
                messagebox.showerror("Ошибка", f"Недостаточно вложений для создания хотя бы одного набора.\nРодителей: {num_parents}, Вложений: {num_children}")
                return

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_dir = f"aggregation_results_{timestamp}"
            os.makedirs(output_dir, exist_ok=True)

            for i in range(actual_sets):
                parent = parent_codes[i]
                children = all_child_codes[i * count_per_set : (i + 1) * count_per_set]

                # Санитизация имени файла (используем родительский код)
                safe_name = sanitize_filename(parent)
                file_path = os.path.join(output_dir, f"{safe_name}.txt")

                with open(file_path, "w", encoding="utf-8") as out_f:
                    out_f.write(parent + "\n")
                    for child in children:
                        out_f.write(child + "\n")

            messagebox.showinfo("Готово", f"Агрегация завершена!\nСоздано наборов: {actual_sets}\nРезультаты в папке: {output_dir}")

        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            messagebox.showerror("Ошибка", f"Произошла ошибка:\n{e}\n\nПодробности:\n{error_details}")

if __name__ == "__main__":
    root = tk.Tk()
    app = VirtualAggregationApp(root)
    root.mainloop()
