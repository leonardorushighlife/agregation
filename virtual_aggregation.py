import tkinter as tk
from tkinter import filedialog, messagebox
import os
from datetime import datetime

"""
Команда для сборки в EXE:
pyinstaller --onefile --noconsole virtual_aggregation.py
"""

class VirtualAggregationApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Виртуальная агрегация")
        self.root.geometry("500x400")

        self.parent_file = ""
        self.child_files = []

        # UI Elements
        tk.Label(root, text="Виртуальная агрегация", font=("Arial", 16, "bold")).pack(pady=10)

        # Parent Selection
        self.btn_parent = tk.Button(root, text="Выбрать файл кодов набора (родитель)", command=self.select_parent)
        self.btn_parent.pack(pady=5, fill=tk.X, padx=20)
        self.lbl_parent = tk.Label(root, text="Файл не выбран", fg="gray")
        self.lbl_parent.pack()

        # Child Selection
        self.btn_children = tk.Button(root, text="Выбрать файлы кодов вложений (дети)", command=self.select_children)
        self.btn_children.pack(pady=5, fill=tk.X, padx=20)
        self.lbl_children = tk.Label(root, text="Файлы не выбраны", fg="gray")
        self.lbl_children.pack()

        # Count per set
        tk.Label(root, text="Количество вложений в один набор:").pack(pady=(10, 0))
        self.entry_count = tk.Entry(root, justify="center")
        self.entry_count.insert(0, "4")
        self.entry_count.pack(pady=5)

        # Start Button
        self.btn_run = tk.Button(root, text="ЗАПУСТИТЬ АГРЕГАЦИЮ", bg="green", fg="white", font=("Arial", 12, "bold"), command=self.run_aggregation)
        self.btn_run.pack(pady=20, fill=tk.X, padx=50)

    def select_parent(self):
        file = filedialog.askopenfilename(filetypes=[("Text files", "*.txt")])
        if file:
            self.parent_file = file
            self.lbl_parent.config(text=os.path.basename(file), fg="black")

    def select_children(self):
        files = filedialog.askopenfilenames(filetypes=[("Text files", "*.txt")])
        if files:
            self.child_files = list(files)
            self.lbl_children.config(text=f"Выбрано файлов: {len(files)}", fg="black")

    def read_codes(self, filepath):
        encodings = ['utf-8', 'utf-8-sig', 'cp1251']
        for enc in encodings:
            try:
                with open(filepath, 'r', encoding=enc) as f:
                    return [line.strip() for line in f if line.strip()]
            except UnicodeDecodeError:
                continue
        raise Exception(f"Не удалось прочитать файл {filepath}. Проверьте кодировку.")

    def run_aggregation(self):
        if not self.parent_file:
            messagebox.showerror("Ошибка", "Выберите файл с кодами наборов!")
            return
        if not self.child_files:
            messagebox.showerror("Ошибка", "Выберите файлы с кодами вложений!")
            return

        try:
            items_per_set = int(self.entry_count.get())
            if items_per_set <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Ошибка", "Введите корректное число вложений!")
            return

        try:
            # Load parents
            parents = self.read_codes(self.parent_file)

            # Load children
            all_children = []
            for f in self.child_files:
                all_children.extend(self.read_codes(f))

            if len(all_children) < len(parents) * items_per_set:
                confirm = messagebox.askyesno("Предупреждение",
                    f"Кодов вложений ({len(all_children)}) меньше, чем требуется для всех наборов ({len(parents) * items_per_set}).\n"
                    f"Будет обработано только {len(all_children) // items_per_set} наборов. Продолжить?")
                if not confirm:
                    return

            # Create output directory
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_dir = f"aggregation_results_{timestamp}"
            os.makedirs(output_dir, exist_ok=True)

            count_done = 0
            for i, p_code in enumerate(parents):
                start_idx = i * items_per_set
                end_idx = start_idx + items_per_set

                if end_idx > len(all_children):
                    break

                set_children = all_children[start_idx:end_idx]

                # Sanitize filename (remove potentially invalid chars)
                safe_name = "".join([c for c in p_code if c.isalnum() or c in (' ', '-', '_')]).rstrip()
                if not safe_name:
                    safe_name = f"set_{i+1}"

                filename = os.path.join(output_dir, f"{safe_name}.txt")
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(p_code + "\n")
                    for c_code in set_children:
                        f.write(c_code + "\n")

                count_done += 1

            messagebox.showinfo("Успех", f"Агрегация завершена!\nСоздано файлов: {count_done}\nПапка: {output_dir}")

        except Exception as e:
            messagebox.showerror("Ошибка", f"Произошла ошибка: {str(e)}")

if __name__ == "__main__":
    root = tk.Tk()
    app = VirtualAggregationApp(root)
    root.mainloop()
