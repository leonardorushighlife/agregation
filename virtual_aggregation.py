import tkinter as tk
from tkinter import filedialog, messagebox
import os
from datetime import datetime

# Инструкция для сборки в EXE:
# pyinstaller --noconsole --onefile virtual_aggregation.py

class VirtualAggregationApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Виртуальная агрегация")
        self.root.geometry("600x400")

        self.parent_file = ""
        self.child_files = []

        # UI Elements
        tk.Label(root, text="Виртуальная агрегация наборов", font=("Arial", 16, "bold")).pack(pady=10)

        # Родительские коды
        self.btn_parent = tk.Button(root, text="Выбрать файл с кодами наборов (родители)", command=self.select_parent_file)
        self.btn_parent.pack(pady=5)
        self.lbl_parent = tk.Label(root, text="Файл не выбран", fg="gray")
        self.lbl_parent.pack()

        # Коды вложений
        self.btn_children = tk.Button(root, text="Выбрать файлы с кодами вложений (дети)", command=self.select_child_files)
        self.btn_children.pack(pady=5)
        self.lbl_children = tk.Label(root, text="Файлы не выбраны", fg="gray")
        self.lbl_children.pack()

        # Количество вложений
        tk.Label(root, text="Количество вложений в один набор:").pack(pady=10)
        self.entry_count = tk.Entry(root, justify="center")
        self.entry_count.insert(0, "1")
        self.entry_count.pack()

        # Кнопка СТАРТ
        self.btn_start = tk.Button(root, text="НАЧАТЬ АГРЕГАЦИЮ", font=("Arial", 12, "bold"),
                                   bg="green", fg="white", width=25, height=2, command=self.start_aggregation)
        self.btn_start.pack(pady=30)

    def select_parent_file(self):
        filename = filedialog.askopenfilename(title="Выберите файл с родительскими кодами",
                                             filetypes=[("Text files", "*.txt")])
        if filename:
            self.parent_file = filename
            self.lbl_parent.config(text=os.path.basename(filename), fg="black")

    def select_child_files(self):
        filenames = filedialog.askopenfilenames(title="Выберите файлы с кодами вложений",
                                               filetypes=[("Text files", "*.txt")])
        if filenames:
            self.child_files = list(filenames)
            self.lbl_children.config(text=f"Выбрано файлов: {len(filenames)}", fg="black")

    def read_codes(self, filepath):
        codes = []
        if not os.path.exists(filepath):
            return codes
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                code = line.strip()
                if code:
                    codes.append(code)
        return codes

    def start_aggregation(self):
        if not self.parent_file:
            messagebox.showerror("Ошибка", "Выберите файл с родительскими кодами")
            return
        if not self.child_files:
            messagebox.showerror("Ошибка", "Выберите файлы с кодами вложений")
            return

        try:
            items_per_set = int(self.entry_count.get())
            if items_per_set <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Ошибка", "Введите корректное число вложений")
            return

        # Загрузка кодов
        parents = self.read_codes(self.parent_file)
        children = []
        for f in self.child_files:
            children.extend(self.read_codes(f))

        if not parents:
            messagebox.showerror("Ошибка", "Файл родителей пуст")
            return
        if not children:
            messagebox.showerror("Ошибка", "Файлы вложений пусты")
            return

        needed_children = len(parents) * items_per_set
        if len(children) < needed_children:
            messagebox.showwarning("Предупреждение",
                                   f"Кодов вложений ({len(children)}) меньше чем требуется для всех наборов ({needed_children}).\n"
                                   f"Будет обработано только {len(children) // items_per_set} наборов.")

        # Создание папки
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = f"aggregation_results_{timestamp}"
        os.makedirs(output_dir, exist_ok=True)

        count_done = 0
        child_idx = 0

        for parent_code in parents:
            if child_idx + items_per_set > len(children):
                break

            # Берем дочерние коды
            current_children = children[child_idx : child_idx + items_per_set]
            child_idx += items_per_set

            # Генерируем имя файла (используем часть кода или индекс во избежание проблем с длиной имени)
            safe_name = "".join(x for x in parent_code if x.isalnum())[:20]
            filename = os.path.join(output_dir, f"set_{count_done+1}_{safe_name}.txt")

            with open(filename, "w", encoding="utf-8") as f:
                f.write(parent_code + "\n")
                for c in current_children:
                    f.write(c + "\n")

            count_done += 1

        messagebox.showinfo("Готово", f"Агрегация завершена!\nСоздано файлов: {count_done}\nПапка: {output_dir}")

if __name__ == "__main__":
    root = tk.Tk()
    app = VirtualAggregationApp(root)
    root.mainloop()
