import os
import tkinter as tk
from tkinter import filedialog, messagebox
from datetime import datetime
import re

class VirtualAggregationApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Виртуальная агрегация (TXT)")
        self.root.geometry("500x550")
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

        tk.Label(frame, text="2. Количество вложений из КАЖДОГО файла:", font=("Arial", 10, "bold")).pack(anchor="w")
        tk.Label(frame, text="(сколько кодов брать из каждого TXT файла для одного набора)", font=("Arial", 8), fg="gray").pack(anchor="w")
        self.ent_count = tk.Entry(frame)
        self.ent_count.insert(0, "1")
        self.ent_count.pack(fill="x", pady=(5, 15))

        tk.Label(frame, text="3. Выберите файлы с кодами вложений (дети):", font=("Arial", 10, "bold")).pack(anchor="w")
        self.btn_children = tk.Button(frame, text="Выбрать файлы", command=self.select_children)
        self.btn_children.pack(fill="x", pady=(5, 5))
        self.lbl_children = tk.Label(frame, text="Файлы не выбраны", fg="gray", wraplength=450)
        self.lbl_children.pack(anchor="w", pady=(0, 20))

        self.btn_process = tk.Button(
            frame,
            text="Выполнить агрегацию",
            bg="#2196F3",
            fg="white",
            font=("Arial", 12, "bold"),
            command=self.process
        )
        self.btn_process.pack(fill="x", pady=(10, 0), ipady=10)

        tk.Label(frame, text="Результат: новая папка с отдельными TXT файлами", font=("Arial", 8), fg="blue").pack(pady=(10, 0))

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
        # Пробуем разные кодировки
        for encoding in ['utf-8-sig', 'utf-8', 'cp1251']:
            try:
                with open(filepath, 'r', encoding=encoding) as f:
                    for line in f:
                        code = line.strip()
                        if code:
                            codes.append(code)
                return codes # Если прочитали, возвращаем
            except (UnicodeDecodeError, Exception):
                continue

        messagebox.showerror("Ошибка чтения", f"Не удалось прочитать файл {filepath}. Проверьте кодировку.")
        return []

    def sanitize_filename(self, filename):
        return re.sub(r'[\\/*?:"<>|]', "", filename)

    def process(self):
        if not self.parent_file:
            messagebox.showerror("Ошибка", "Выберите файл с кодами наборов")
            return

        try:
            count_per_file = int(self.ent_count.get())
            if count_per_file <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Ошибка", "Введите корректное число вложений (больше 0)")
            return

        if not self.child_files:
            messagebox.showerror("Ошибка", "Выберите файлы с кодами вложений")
            return

        # Загружаем коды родителей
        parent_codes = self.read_codes(self.parent_file)
        if not parent_codes:
            return

        # Загружаем коды детей из каждого файла отдельно
        child_files_data = []
        for cf in self.child_files:
            codes = self.read_codes(cf)
            if not codes:
                continue
            child_files_data.append(codes)

        if not child_files_data:
            messagebox.showerror("Ошибка", "Нет данных в файлах вложений")
            return

        # Считаем, сколько полных наборов мы можем собрать
        # Для каждого набора нужно 'count_per_file' кодов из КАЖДОГО файла детей
        possible_from_children = min(len(codes) // count_per_file for codes in child_files_data)
        actual_sets = min(len(parent_codes), possible_from_children)

        if actual_sets == 0:
            messagebox.showerror("Ошибка", "Недостаточно данных для создания наборов.\nПроверьте количество кодов и параметр вложений.")
            return

        # Создаем папку
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        folder_name = f"агрегация_{timestamp}"

        try:
            os.makedirs(folder_name, exist_ok=True)

            for i in range(actual_sets):
                p_code = parent_codes[i]

                # Имя файла на основе кода родителя
                safe_code = self.sanitize_filename(p_code)[:50]
                filename = f"Набор_{i+1}_{safe_code}.txt"
                filepath = os.path.join(folder_name, filename)

                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(p_code + "\n") # Родитель на первой строке

                    # Берем вложения из каждого файла
                    for codes_list in child_files_data:
                        start_idx = i * count_per_file
                        for k in range(count_per_file):
                            c_code = codes_list[start_idx + k]
                            f.write(c_code + "\n")

            messagebox.showinfo("Готово",
                f"Агрегация завершена!\n\n"
                f"Создано файлов: {actual_sets}\n"
                f"Папка: {folder_name}"
            )
        except Exception as e:
            messagebox.showerror("Ошибка", f"Произошла ошибка при записи:\n{e}")

if __name__ == "__main__":
    root = tk.Tk()
    app = VirtualAggregationApp(root)
    root.mainloop()
