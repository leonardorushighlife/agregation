import os
import tkinter as tk
from tkinter import filedialog, messagebox
from datetime import datetime
import re
import traceback

def sanitize_filename(filename):
    # Удаляем или заменяем символы, недопустимые в именах файлов Windows
    return re.sub(r'[\\/*?:"<>|]', "_", filename)

def read_codes(file_path):
    encodings = ['utf-8-sig', 'utf-8', 'cp1251', 'utf-16']
    for enc in encodings:
        try:
            with open(file_path, 'r', encoding=enc) as f:
                return [line.strip() for line in f if line.strip()]
        except (UnicodeDecodeError, PermissionError):
            continue
    raise Exception(f"Не удалось прочитать файл {file_path}. Проверьте кодировку.")

class VirtualAggregationApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Виртуальная Агрегация")
        self.root.geometry("550x450")

        self.parent_file = ""
        self.child_files = []

        # Стили
        style = {'padx': 10, 'pady': 5}

        # UI Элементы
        tk.Label(root, text="1. Выберите файл с кодами маркировки НАБОРА (родители):", font=("Arial", 10, "bold")).pack(**style)
        self.btn_parent = tk.Button(root, text="Выбрать родительский файл", command=self.select_parent_file, width=30)
        self.btn_parent.pack(**style)
        self.lbl_parent = tk.Label(root, text="Файл не выбран", fg="red")
        self.lbl_parent.pack(**style)

        tk.Label(root, text="2. Введите количество вложений в один набор:", font=("Arial", 10, "bold")).pack(**style)
        self.entry_count = tk.Entry(root, justify='center', font=("Arial", 12))
        self.entry_count.insert(0, "1")
        self.entry_count.pack(**style)

        tk.Label(root, text="3. Выберите файлы с кодами маркировки СОДЕРЖИМОГО (дети):", font=("Arial", 10, "bold")).pack(**style)
        self.btn_children = tk.Button(root, text="Выбрать дочерние файлы", command=self.select_child_files, width=30)
        self.btn_children.pack(**style)
        self.lbl_children = tk.Label(root, text="Файлы не выбраны", fg="red")
        self.lbl_children.pack(**style)

        self.btn_start = tk.Button(root, text="ЗАПУСТИТЬ АГРЕГАЦИЮ", command=self.start_aggregation,
                                   bg="#4CAF50", fg="white", font=("Arial", 12, "bold"), height=2, width=30)
        self.btn_start.pack(pady=30)

    def select_parent_file(self):
        filename = filedialog.askopenfilename(title="Выберите файл с кодами наборов",
                                            filetypes=[("Текстовые файлы", "*.txt"), ("Все файлы", "*.*")])
        if filename:
            self.parent_file = filename
            self.lbl_parent.config(text=os.path.basename(filename), fg="green")

    def select_child_files(self):
        filenames = filedialog.askopenfilenames(title="Выберите файлы с кодами содержимого",
                                              filetypes=[("Текстовые файлы", "*.txt"), ("Все файлы", "*.*")])
        if filenames:
            self.child_files = list(filenames)
            self.lbl_children.config(text=f"Выбрано файлов: {len(filenames)}", fg="green")

    def start_aggregation(self):
        if not self.parent_file:
            messagebox.showerror("Ошибка", "Выберите файл с кодами наборов!")
            return
        if not self.child_files:
            messagebox.showerror("Ошибка", "Выберите файлы с кодами содержимого!")
            return

        try:
            count_per_file = int(self.entry_count.get())
            if count_per_file <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Ошибка", "Введите корректное целое число вложений!")
            return

        try:
            # Читаем родительские коды
            parents = read_codes(self.parent_file)

            # Читаем дочерние коды
            children = []
            for cf in self.child_files:
                children.extend(read_codes(cf))

            if not parents:
                messagebox.showerror("Ошибка", "В родительском файле нет кодов!")
                return
            if not children:
                messagebox.showerror("Ошибка", "В дочерних файлах нет кодов!")
                return

            needed_total = len(parents) * count_per_file
            if len(children) < needed_total:
                msg = f"Дочерних кодов ({len(children)}) меньше, чем требуется для всех наборов ({needed_total}).\n\nБудет создано только {len(children) // count_per_file} полных наборов. Продолжить?"
                if not messagebox.askyesno("Предупреждение", msg):
                    return

            # Создаем папку для результатов
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            output_folder = f"aggregation_results_{timestamp}"
            os.makedirs(output_folder, exist_ok=True)

            actual_sets = min(len(parents), len(children) // count_per_file)

            for i in range(actual_sets):
                p_code = parents[i]
                c_codes = children[i * count_per_file : (i + 1) * count_per_file]

                # Очищаем код для использования в имени файла
                clean_p_code = sanitize_filename(p_code)
                # Если код слишком длинный, обрезаем для имени файла
                if len(clean_p_code) > 100:
                    clean_p_code = clean_p_code[:100]

                file_name = f"{clean_p_code}.txt"
                file_path = os.path.join(output_folder, file_name)

                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(p_code + "\n")
                    for cc in c_codes:
                        f.write(cc + "\n")

            messagebox.showinfo("Успех", f"Агрегация завершена успешно!\n\nСоздано наборов: {actual_sets}\nПапка с результатом: {output_folder}")

            # Открываем папку в проводнике (только для Windows)
            if os.name == 'nt':
                os.startfile(output_folder)

        except Exception as e:
            error_msg = traceback.format_exc()
            messagebox.showerror("Критическая ошибка", f"Произошла ошибка:\n{error_msg}")

if __name__ == "__main__":
    root = tk.Tk()
    app = VirtualAggregationApp(root)
    root.mainloop()
