import tkinter as tk
from tkinter import filedialog, messagebox
import os
from datetime import datetime

"""
Скрипт для виртуальной агрегации кодов маркировки.
Позволяет объединить коды наборов (родительские) с кодами вложений (дочерними)
в отдельные файлы согласно заданному количеству вложений.

Сборка в EXE:
pyinstaller --noconsole --onefile virtual_aggregation.py
"""

def perform_aggregation(parent_file, child_files, items_per_parent):
    try:
        items_per_parent = int(items_per_parent)
        if items_per_parent <= 0:
            raise ValueError
    except ValueError:
        messagebox.showerror("Ошибка", "Введите корректное число вложений (целое положительное число)")
        return

    if not parent_file:
        messagebox.showerror("Ошибка", "Не выбран файл с кодами наборов")
        return

    if not child_files:
        messagebox.showerror("Ошибка", "Не выбраны файлы с кодами вложений")
        return

    try:
        # Чтение кодов наборов
        with open(parent_file, 'r', encoding='utf-8') as f:
            parents = [line.strip() for line in f if line.strip()]

        # Чтение кодов вложений из всех выбранных файлов
        children = []
        for cf in child_files:
            with open(cf, 'r', encoding='utf-8') as f:
                children.extend([line.strip() for line in f if line.strip()])

        if not parents:
            messagebox.showerror("Ошибка", "Файл с кодами наборов пуст")
            return

        if not children:
            messagebox.showerror("Ошибка", "Файлы с кодами вложений пусты")
            return

        # Создание папки для результата
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        folder_name = f"Результат_Агрегации_{timestamp}"
        os.makedirs(folder_name, exist_ok=True)

        count = 0
        for i, p_code in enumerate(parents):
            start_idx = i * items_per_parent
            end_idx = start_idx + items_per_parent

            # Если вложения закончились, прекращаем процесс
            if start_idx >= len(children):
                break

            current_children = children[start_idx:end_idx]

            # Очистка кода для использования в имени файла (удаляем спецсимволы)
            safe_code = "".join(c for c in p_code if c.isalnum())[:15]
            filename = f"Набор_{i+1}_{safe_code}.txt"
            filepath = os.path.join(folder_name, filename)

            with open(filepath, 'w', encoding='utf-8') as out_f:
                # Сначала код набора
                out_f.write(p_code + "\n")
                # Затем коды вложений
                for c_code in current_children:
                    out_f.write(c_code + "\n")

            count += 1

        messagebox.showinfo("Успех", f"Агрегация завершена.\nСоздано файлов: {count}\nПапка: {folder_name}")

    except Exception as e:
        messagebox.showerror("Ошибка", f"Произошла ошибка при обработке: {e}")

class AggregatorGUI:
    def __init__(self, master):
        self.master = master
        master.title("Виртуальная Агрегация")
        master.geometry("600x450")
        master.resizable(False, False)

        self.parent_path = ""
        self.children_paths = []

        # Заголовок
        tk.Label(master, text="Инструмент виртуальной агрегации", font=("Arial", 14, "bold")).pack(pady=20)

        # Выбор файла наборов
        self.btn_parent = tk.Button(master, text="1. Выбрать файл с кодами НАБОРОВ", command=self.load_parent, width=45)
        self.btn_parent.pack(pady=5)
        self.lbl_parent = tk.Label(master, text="Файл не выбран", fg="gray")
        self.lbl_parent.pack()

        # Выбор файлов вложений
        self.btn_children = tk.Button(master, text="2. Выбрать файлы с кодами ВЛОЖЕНИЙ", command=self.load_children, width=45)
        self.btn_children.pack(pady=5)
        self.lbl_children = tk.Label(master, text="Файлы не выбраны", fg="gray")
        self.lbl_children.pack()

        # Количество вложений
        tk.Label(master, text="Количество вложений в каждый набор:").pack(pady=(20, 0))
        self.entry_count = tk.Entry(master, width=10, justify='center', font=("Arial", 12))
        self.entry_count.insert(0, "10")
        self.entry_count.pack(pady=5)

        # Кнопка запуска
        self.btn_start = tk.Button(master, text="НАЧАТЬ АГРЕГАЦИЮ", command=self.start,
                                   bg="#4CAF50", fg="white", font=("Arial", 12, "bold"), height=2, width=25)
        self.btn_start.pack(pady=30)

    def load_parent(self):
        path = filedialog.askopenfilename(title="Выберите файл с кодами наборов", filetypes=[("TXT files", "*.txt"), ("All files", "*.*")])
        if path:
            self.parent_path = path
            self.lbl_parent.config(text=os.path.basename(path), fg="green")

    def load_children(self):
        paths = filedialog.askopenfilenames(title="Выберите файлы с кодами вложений", filetypes=[("TXT files", "*.txt"), ("All files", "*.*")])
        if paths:
            self.children_paths = list(paths)
            self.lbl_children.config(text=f"Выбрано файлов: {len(paths)}", fg="green")

    def start(self):
        perform_aggregation(self.parent_path, self.children_paths, self.entry_count.get())

if __name__ == "__main__":
    root = tk.Tk()
    gui = AggregatorGUI(root)
    root.mainloop()
