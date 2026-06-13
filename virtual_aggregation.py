import tkinter as tk
from tkinter import filedialog, messagebox
import os
import re
from datetime import datetime

def read_codes(filepath):
    codes = []
    encodings = ['utf-8', 'utf-8-sig', 'cp1251']
    for enc in encodings:
        try:
            with open(filepath, 'r', encoding=enc) as f:
                lines = f.readlines()
                codes = [line.strip() for line in lines if line.strip()]
            return codes
        except (UnicodeDecodeError, Exception):
            continue
    return []

def sanitize_filename(filename):
    return re.sub(r'[\\/*?:"<>|]', "_", filename)

def perform_aggregation(parent_file, child_files, count_per_file, progress_callback=None):
    parent_codes = read_codes(parent_file)
    if not parent_codes:
        return False, "Файл наборов пуст"

    all_child_codes = []
    for cf in child_files:
        all_child_codes.extend(read_codes(cf))

    if not all_child_codes:
        return False, "Файлы вложений пусты"

    # Create output directory
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = f"aggregation_results_{timestamp}"
    os.makedirs(output_dir, exist_ok=True)

    success_count = 0
    child_index = 0

    for i in range(len(parent_codes)):
        if child_index >= len(all_child_codes):
            break

        p_code = parent_codes[i]
        safe_name = sanitize_filename(p_code)
        if len(safe_name) > 150:
            safe_name = safe_name[:150]

        file_path = os.path.join(output_dir, f"{safe_name}.txt")
        if os.path.exists(file_path):
            file_path = os.path.join(output_dir, f"{safe_name}_{i}.txt")

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(p_code + "\n")
            for _ in range(count_per_file):
                if child_index < len(all_child_codes):
                    f.write(all_child_codes[child_index] + "\n")
                    child_index += 1

        success_count += 1
        if progress_callback:
            progress_callback(success_count)

    return True, (success_count, output_dir)

class VirtualAggregationApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Виртуальная агрегация")
        self.root.geometry("600x400")

        self.parent_file = ""
        self.child_files = []

        # UI Elements
        tk.Label(root, text="Виртуальная агрегация кодов маркировки", font=("Arial", 14, "bold")).pack(pady=10)

        # Parent file selection
        self.btn_parent = tk.Button(root, text="Выбрать файл с кодами наборов (Родитель)", command=self.select_parent_file)
        self.btn_parent.pack(pady=5, fill=tk.X, padx=20)
        self.lbl_parent = tk.Label(root, text="Файл не выбран", fg="red")
        self.lbl_parent.pack()

        # Child files selection
        self.btn_children = tk.Button(root, text="Выбрать файлы с кодами вложений (Дети)", command=self.select_child_files)
        self.btn_children.pack(pady=5, fill=tk.X, padx=20)
        self.lbl_children = tk.Label(root, text="Файлы не выбраны", fg="red")
        self.lbl_children.pack()

        # Count of attachments
        tk.Label(root, text="Количество вложений в каждый набор:").pack(pady=(10, 0))
        self.entry_count = tk.Entry(root, justify="center")
        self.entry_count.insert(0, "1")
        self.entry_count.pack(pady=5)

        # Start button
        self.btn_start = tk.Button(root, text="Начать агрегацию", command=self.start_aggregation, bg="green", fg="white", font=("Arial", 12, "bold"))
        self.btn_start.pack(pady=20, fill=tk.X, padx=50)

        self.status_label = tk.Label(root, text="", font=("Arial", 10))
        self.status_label.pack(side=tk.BOTTOM, pady=10)

    def select_parent_file(self):
        file = filedialog.askopenfilename(filetypes=[("Text files", "*.txt")])
        if file:
            self.parent_file = file
            self.lbl_parent.config(text=os.path.basename(file), fg="black")

    def select_child_files(self):
        files = filedialog.askopenfilenames(filetypes=[("Text files", "*.txt")])
        if files:
            self.child_files = list(files)
            self.lbl_children.config(text=f"Выбрано файлов: {len(files)}", fg="black")

    def start_aggregation(self):
        if not self.parent_file:
            messagebox.showerror("Ошибка", "Выберите файл с кодами наборов")
            return
        if not self.child_files:
            messagebox.showerror("Ошибка", "Выберите файлы с кодами вложений")
            return

        try:
            count_per_file = int(self.entry_count.get())
            if count_per_file <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Ошибка", "Количество вложений должно быть целым положительным числом")
            return

        # Check total codes before starting
        parent_codes = read_codes(self.parent_file)
        all_child_codes_len = sum(len(read_codes(cf)) for cf in self.child_files)

        needed_children = len(parent_codes) * count_per_file
        if all_child_codes_len < needed_children:
            if not messagebox.askyesno("Предупреждение", f"Кодов вложений ({all_child_codes_len}) меньше чем требуется ({needed_children}). Продолжить с частичной агрегацией?"):
                return

        success, result = perform_aggregation(self.parent_file, self.child_files, count_per_file)

        if success:
            count, out_dir = result
            messagebox.showinfo("Успех", f"Агрегация завершена!\nСоздано наборов: {count}\nПапка: {out_dir}")
            self.status_label.config(text=f"Готово: {count} наборов в {out_dir}")
        else:
            messagebox.showerror("Ошибка", result)

if __name__ == "__main__":
    root = tk.Tk()
    app = VirtualAggregationApp(root)
    root.mainloop()
