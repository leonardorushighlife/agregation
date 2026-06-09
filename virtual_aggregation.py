import os
import tkinter as tk
from tkinter import filedialog, messagebox
from datetime import datetime
import openpyxl

class VirtualAggregationApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Виртуальная агрегация (Excel)")
        self.root.geometry("500x400")
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
        tk.Label(frame, text="(из каждого файла будет взято по 1 коду для каждого набора)", font=("Arial", 8), fg="blue").pack(anchor="w")
        self.btn_children = tk.Button(frame, text="Выбрать файлы", command=self.select_children)
        self.btn_children.pack(fill="x", pady=(5, 5))
        self.lbl_children = tk.Label(frame, text="Файлы не выбраны", fg="gray", wraplength=450)
        self.lbl_children.pack(anchor="w", pady=(0, 20))

        self.btn_process = tk.Button(
            frame,
            text="Создать Excel файл",
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

        # Load parent codes
        parent_codes = self.read_codes(self.parent_file)
        if not parent_codes:
            messagebox.showerror("Ошибка", "Файл наборов пуст")
            return

        # Load child codes from each file
        child_files_data = []
        for cf in self.child_files:
            codes = self.read_codes(cf)
            if not codes:
                messagebox.showwarning("Внимание", f"Файл {os.path.basename(cf)} пуст и будет проигнорирован")
                continue
            child_files_data.append(codes)

        if not child_files_data:
            messagebox.showerror("Ошибка", "Нет данных в файлах вложений")
            return

        # Calculate how many sets we can form
        min_children = min([len(codes) for codes in child_files_data])
        actual_sets = min(len(parent_codes), min_children)

        if actual_sets == 0:
            messagebox.showerror("Ошибка", "Недостаточно данных для создания хотя бы одного набора")
            return

        # Create folder
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        folder_name = f"агрегация_{timestamp}"
        output_filename = f"агрегация_{timestamp}.xlsx"
        output_path = os.path.join(folder_name, output_filename)

        try:
            os.makedirs(folder_name, exist_ok=True)
            wb = openpyxl.Workbook()
            ws = wb.active
            # Headers as per screenshot
            headers = ["Название набора", "Код идентификации набора", "Наименование товара", "Код маркировки"]
            ws.append(headers)

            processed_count = 0
            for i in range(actual_sets):
                p_code = parent_codes[i]
                for codes_list in child_files_data:
                    c_code = codes_list[i]
                    # Columns: 1-Empty, 2-Parent, 3-Empty, 4-Child
                    ws.append(["", p_code, "", c_code])
                processed_count += 1

            wb.save(output_path)

            messagebox.showinfo("Готово",
                f"Агрегация завершена!\n\n"
                f"Обработано наборов: {processed_count}\n"
                f"Создан файл: {output_path}"
            )
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось создать Excel файл:\n{e}")

if __name__ == "__main__":
    root = tk.Tk()
    app = VirtualAggregationApp(root)
    root.mainloop()
