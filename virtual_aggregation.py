import os
import tkinter as tk
from tkinter import filedialog, messagebox
from datetime import datetime
import re

def sanitize_filename(name):
    # Remove characters that are illegal in Windows filenames
    return re.sub(r'[\\/*?:"<>|]', "_", name)

def aggregate_codes(parent_codes, child_codes, count_per_set, folder_name):
    actual_sets = min(len(parent_codes), len(child_codes) // count_per_set)
    processed_count = 0

    for i in range(actual_sets):
        p_code = parent_codes[i]
        start_idx = i * count_per_set
        end_idx = start_idx + count_per_set

        current_children = child_codes[start_idx:end_idx]

        safe_p_code = sanitize_filename(p_code)
        filename = f"Набор_{i+1}_{safe_p_code[:30]}.txt"
        filepath = os.path.join(folder_name, filename)

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(p_code + "\n")
            for c_code in current_children:
                f.write(c_code + "\n")
        processed_count += 1
    return processed_count

class VirtualAggregationApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Виртуальная агрегация")
        self.root.geometry("500x450")
        self.root.resizable(False, False)

        self.parent_file = ""
        self.child_files = []

        # UI Elements
        frame = tk.Frame(root, padx=20, pady=20)
        frame.pack(expand=True, fill="both")

        tk.Label(frame, text="1. Выберите файл с кодами наборов (родители):", font=("Arial", 10, "bold")).pack(anchor="w")
        self.btn_parent = tk.Button(frame, text="Выбрать файл", command=self.select_parent)
        self.btn_parent.pack(fill="x", pady=(5, 5))
        self.lbl_parent = tk.Label(frame, text="Файл не выбран", fg="gray", wraplength=450)
        self.lbl_parent.pack(anchor="w", pady=(0, 15))

        tk.Label(frame, text="2. Выберите файлы с кодами вложений (дети):", font=("Arial", 10, "bold")).pack(anchor="w")
        self.btn_children = tk.Button(frame, text="Выбрать файлы", command=self.select_children)
        self.btn_children.pack(fill="x", pady=(5, 5))
        self.lbl_children = tk.Label(frame, text="Файлы не выбраны", fg="gray", wraplength=450)
        self.lbl_children.pack(anchor="w", pady=(0, 15))

        tk.Label(frame, text="3. Количество вложений в один набор:", font=("Arial", 10, "bold")).pack(anchor="w")
        self.ent_count = tk.Entry(frame, font=("Arial", 12))
        self.ent_count.insert(0, "1")
        self.ent_count.pack(fill="x", pady=(5, 15))

        self.btn_process = tk.Button(
            frame,
            text="Запустить агрегацию",
            bg="#4CAF50",
            fg="white",
            font=("Arial", 12, "bold"),
            command=self.process
        )
        self.btn_process.pack(fill="x", pady=(10, 0), ipady=10)

    def select_parent(self):
        file = filedialog.askopenfilename(
            title="Выберите файл с кодами наборов",
            filetypes=[("TXT files", "*.txt"), ("All files", "*.*")]
        )
        if file:
            self.parent_file = file
            self.lbl_parent.config(text=os.path.basename(file), fg="black")

    def select_children(self):
        files = filedialog.askopenfilenames(
            title="Выберите файлы с кодами вложений",
            filetypes=[("TXT files", "*.txt"), ("All files", "*.*")]
        )
        if files:
            self.child_files = list(files)
            self.lbl_children.config(text=f"Выбрано файлов: {len(files)}", fg="black")

    def read_codes(self, filepath):
        codes = []
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                for line in f:
                    code = line.strip()
                    if code:
                        codes.append(code)
        except Exception as e:
            messagebox.showerror("Ошибка чтения", f"Не удалось прочитать файл {filepath}:\n{e}")
        return codes

    def process(self):
        if not self.parent_file:
            messagebox.showerror("Ошибка", "Выберите файл с кодами наборов")
            return
        if not self.child_files:
            messagebox.showerror("Ошибка", "Выберите файлы с кодами вложений")
            return

        try:
            count_per_set = int(self.ent_count.get())
            if count_per_set <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Ошибка", "Введите корректное число вложений (целое число больше 0)")
            return

        # Load codes
        parent_codes = self.read_codes(self.parent_file)
        child_codes = []
        for cf in self.child_files:
            child_codes.extend(self.read_codes(cf))

        if not parent_codes:
            messagebox.showerror("Ошибка", "Файл наборов пуст или не содержит кодов")
            return
        if not child_codes:
            messagebox.showerror("Ошибка", "Файлы вложений пусты или не содержат кодов")
            return

        total_possible_sets = len(child_codes) // count_per_set
        actual_sets = min(len(parent_codes), total_possible_sets)

        if len(parent_codes) > total_possible_sets:
            msg = f"Кодов вложений ({len(child_codes)}) хватит только на {total_possible_sets} наборов.\n" \
                  f"У вас {len(parent_codes)} кодов наборов.\n\nПродолжить агрегацию для {total_possible_sets} наборов?"
            if not messagebox.askyesno("Внимание", msg):
                return

        # Create folder
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        folder_name = f"агрегация_{timestamp}"
        try:
            os.makedirs(folder_name, exist_ok=True)
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось создать папку:\n{e}")
            return

        # Distribute
        try:
            processed_count = aggregate_codes(parent_codes, child_codes, count_per_set, folder_name)
        except Exception as e:
            messagebox.showerror("Ошибка", f"Произошла ошибка при выполнении агрегации:\n{e}")
            return

        messagebox.showinfo("Готово",
            f"Агрегация завершена!\n\n"
            f"Создано наборов: {processed_count}\n"
            f"Использовано вложений: {processed_count * count_per_set}\n"
            f"Результаты в папке: {folder_name}"
        )

if __name__ == "__main__":
    root = tk.Tk()
    app = VirtualAggregationApp(root)
    root.mainloop()
