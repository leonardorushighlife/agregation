import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import os
import sys
import traceback
from datetime import datetime
import re

def sanitize_filename(name):
    """Очищает строку от символов, недопустимых в именах файлов Windows."""
    return re.sub(r'[\\/*?:"<>|]', '_', name)

def read_codes(filepath):
    encodings = ['utf-8-sig', 'utf-8', 'cp1251', 'utf-16']
    for enc in encodings:
        try:
            with open(filepath, 'r', encoding=enc) as f:
                codes = [line.strip() for line in f if line.strip()]
                return codes
        except (UnicodeDecodeError, Exception):
            continue
    return []

def perform_aggregation(parent_file, child_files, count_per_set):
    parents = read_codes(parent_file)
    if not parents:
        raise ValueError("Файл с родительскими кодами пуст или не может быть прочитан.")

    all_children = []
    for f in child_files:
        all_children.extend(read_codes(f))

    if not all_children:
        raise ValueError("Список дочерних кодов пуст.")

    if len(all_children) < len(parents) * count_per_set:
        actual_sets = len(all_children) // count_per_set
        try:
            messagebox.showwarning("Внимание",
                f"Дочерних кодов хватит только на {actual_sets} полных наборов из {len(parents)}.")
        except:
            pass # No display environment
        parents = parents[:actual_sets]

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = f"aggregation_results_{timestamp}"
    os.makedirs(output_dir, exist_ok=True)

    count = 0
    for i, parent_code in enumerate(parents):
        start_idx = i * count_per_set
        end_idx = start_idx + count_per_set
        current_children = all_children[start_idx:end_idx]

        safe_name = sanitize_filename(parent_code[:50]) # Limit length for safety
        filename = os.path.join(output_dir, f"{safe_name}.txt")

        with open(filename, 'w', encoding='utf-8') as f:
            f.write(parent_code + '\n')
            for child in current_children:
                f.write(child + '\n')
        count += 1

    return output_dir, count

class VirtualAggregationApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Виртуальная агрегация")
        self.root.geometry("600x450")

        self.parent_file = ""
        self.child_files = []

        # UI Elements
        frame = tk.Frame(root, padx=20, pady=20)
        frame.pack(fill=tk.BOTH, expand=True)

        # Parent file selection
        tk.Label(frame, text="Файл с кодами наборов (родительские):").pack(anchor="w")
        self.parent_label = tk.Label(frame, text="Файл не выбран", fg="grey", wraplength=500, justify="left")
        self.parent_label.pack(anchor="w", pady=(0, 10))
        tk.Button(frame, text="Выбрать файл", command=self.select_parent_file).pack(anchor="w")

        tk.Separator(frame, orient="horizontal").pack(fill="x", pady=15)

        # Child files selection
        tk.Label(frame, text="Файлы с кодами вложений (дочерние):").pack(anchor="w")
        self.child_listbox = tk.Listbox(frame, height=5, width=70)
        self.child_listbox.pack(anchor="w", pady=(0, 5))

        btn_frame = tk.Frame(frame)
        btn_frame.pack(anchor="w", pady=(0, 10))
        tk.Button(btn_frame, text="Добавить файлы", command=self.add_child_files).pack(side=tk.LEFT, padx=(0, 10))
        tk.Button(btn_frame, text="Очистить список", command=self.clear_child_files).pack(side=tk.LEFT, padx=10)

        tk.Separator(frame, orient="horizontal").pack(fill="x", pady=15)

        # Count per set
        count_frame = tk.Frame(frame)
        count_frame.pack(anchor="w", pady=(0, 20))
        tk.Label(count_frame, text="Количество вложений в один набор:").pack(side=tk.LEFT)
        self.count_entry = tk.Entry(count_frame, width=10)
        self.count_entry.insert(0, "1")
        self.count_entry.pack(side=tk.LEFT, padx=10)

        # Start button
        self.start_btn = tk.Button(frame, text="Начать агрегацию", command=self.start_aggregation,
                                   bg="#4CAF50", fg="white", font=("Arial", 12, "bold"), height=2, width=20)
        self.start_btn.pack(pady=10)

    def select_parent_file(self):
        file = filedialog.askopenfilename(filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if file:
            self.parent_file = file
            self.parent_label.config(text=os.path.basename(file), fg="black")

    def add_child_files(self):
        files = filedialog.askopenfilenames(filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if files:
            for f in files:
                if f not in self.child_files:
                    self.child_files.append(f)
                    self.child_listbox.insert(tk.END, os.path.basename(f))

    def clear_child_files(self):
        self.child_files = []
        self.child_listbox.delete(0, tk.END)

    def start_aggregation(self):
        if not self.parent_file:
            messagebox.showerror("Ошибка", "Выберите файл с кодами наборов.")
            return
        if not self.child_files:
            messagebox.showerror("Ошибка", "Добавьте хотя бы один файл с кодами вложений.")
            return

        try:
            count_val = int(self.count_entry.get())
            if count_val <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Ошибка", "Введите корректное число вложений (больше 0).")
            return

        try:
            out_dir, total = perform_aggregation(self.parent_file, self.child_files, count_val)
            messagebox.showinfo("Готово", f"Агрегация завершена!\n\nОбработано наборов: {total}\nРезультаты в папке:\n{os.path.abspath(out_dir)}")
            # Open folder
            if sys.platform == 'win32':
                os.startfile(out_dir)
        except Exception as e:
            messagebox.showerror("Ошибка", f"Произошла ошибка при выполнении:\n{str(e)}\n\n{traceback.format_exc()}")

def main():
    try:
        root = tk.Tk()
        app = VirtualAggregationApp(root)
        root.mainloop()
    except Exception:
        messagebox.showerror("Ошибка", traceback.format_exc())

if __name__ == "__main__":
    main()
