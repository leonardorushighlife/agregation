import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
import os
import re
from datetime import datetime

# Команда для сборки в EXE:
# pyinstaller --noconsole --onefile virtual_aggregation.py

class VirtualAggregationApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Виртуальная агрегация наборов")
        self.root.geometry("600x600")

        self.parent_file = ""
        self.child_files = []

        self.create_widgets()

    def create_widgets(self):
        # Фрейм для выбора файлов
        file_frame = tk.LabelFrame(self.root, text="Выбор файлов", padx=10, pady=10)
        file_frame.pack(fill="x", padx=10, pady=5)

        tk.Button(file_frame, text="Выбрать файл с кодами НАБОРОВ (родители)", command=self.select_parent_file).pack(fill="x", pady=2)
        self.lbl_parent = tk.Label(file_frame, text="Файл не выбран", fg="red")
        self.lbl_parent.pack()

        tk.Button(file_frame, text="Выбрать файлы с кодами ВЛОЖЕНИЙ (дети)", command=self.select_child_files).pack(fill="x", pady=2)
        self.lbl_children = tk.Label(file_frame, text="Файлы не выбраны", fg="red")
        self.lbl_children.pack()

        # Параметры
        param_frame = tk.Frame(self.root, padx=10, pady=10)
        param_frame.pack(fill="x")

        tk.Label(param_frame, text="Количество вложений в один набор:").grid(row=0, column=0, sticky="w")
        self.ent_count = tk.Entry(param_frame, width=10)
        self.ent_count.insert(0, "4")
        self.ent_count.grid(row=0, column=1, padx=5)

        # Кнопка запуска
        tk.Button(self.root, text="ЗАПУСТИТЬ АГРЕГАЦИЮ", bg="green", fg="white", font=("Arial", 12, "bold"),
                  command=self.run_aggregation).pack(fill="x", padx=10, pady=10)

        # Лог
        self.log_area = scrolledtext.ScrolledText(self.root, height=15)
        self.log_area.pack(fill="both", expand=True, padx=10, pady=5)

    def log(self, message):
        self.log_area.insert(tk.END, f"[{datetime.now().strftime('%H:%M:%S')}] {message}\n")
        self.log_area.see(tk.END)
        self.root.update_idletasks()

    def select_parent_file(self):
        file = filedialog.askopenfilename(filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if file:
            self.parent_file = file
            self.lbl_parent.config(text=os.path.basename(file), fg="black")
            self.log(f"Выбран файл наборов: {file}")

    def select_child_files(self):
        files = filedialog.askopenfilenames(filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if files:
            self.child_files = list(files)
            self.lbl_children.config(text=f"Выбрано файлов: {len(files)}", fg="black")
            self.log(f"Выбрано файлов вложений: {len(files)}")

    def sanitize_filename(self, filename):
        # Удаляем недопустимые символы для имени файла
        return re.sub(r'[\\/*?:"<>|]', "_", filename)[:100]

    def read_codes(self, filepath):
        codes = []
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                for line in f:
                    code = line.strip()
                    if code:
                        codes.append(code)
        except Exception as e:
            self.log(f"Ошибка при чтении {filepath}: {e}")
        return codes

    def run_aggregation(self):
        if not self.parent_file:
            messagebox.showerror("Ошибка", "Выберите файл с кодами наборов!")
            return
        if not self.child_files:
            messagebox.showerror("Ошибка", "Выберите хотя бы один файл с кодами вложений!")
            return

        try:
            items_per_set = int(self.ent_count.get())
            if items_per_set <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Ошибка", "Введите корректное число вложений (целое число > 0)")
            return

        self.log("Начало процесса агрегации...")

        # 1. Читаем коды
        parent_codes = self.read_codes(self.parent_file)
        self.log(f"Загружено кодов наборов: {len(parent_codes)}")

        child_codes = []
        for cf in self.child_files:
            codes = self.read_codes(cf)
            child_codes.extend(codes)
            self.log(f"Из файла {os.path.basename(cf)} загружено кодов: {len(codes)}")

        self.log(f"Всего кодов вложений: {len(child_codes)}")

        if not parent_codes:
            messagebox.showwarning("Предупреждение", "Коды наборов не найдены.")
            return

        if len(child_codes) < items_per_set:
            messagebox.showwarning("Предупреждение", "Недостаточно вложений для хотя бы одного набора.")
            return

        # 2. Создаем папку
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = f"aggregation_results_{timestamp}"
        try:
            os.makedirs(output_dir, exist_ok=True)
            self.log(f"Создана папка: {output_dir}")
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось создать папку: {e}")
            return

        # 3. Агрегация
        sets_created = 0
        child_idx = 0

        for parent in parent_codes:
            if child_idx + items_per_set > len(child_codes):
                self.log("Вложения закончились. Агрегация завершена досрочно.")
                break

            # Берем группу детей
            current_children = child_codes[child_idx : child_idx + items_per_set]
            child_idx += items_per_set

            # Формируем имя файла
            safe_parent = self.sanitize_filename(parent)
            filename = os.path.join(output_dir, f"{safe_parent}.txt")

            try:
                with open(filename, "w", encoding="utf-8") as f:
                    f.write(parent + "\n")
                    for child in current_children:
                        f.write(child + "\n")
                sets_created += 1
            except Exception as e:
                self.log(f"Ошибка при записи файла {filename}: {e}")

        self.log(f"Успешно создано наборов: {sets_created}")
        self.log(f"Результаты сохранены в папке: {os.path.abspath(output_dir)}")
        messagebox.showinfo("Готово", f"Агрегация завершена!\nСоздано наборов: {sets_created}\nПапка: {output_dir}")

if __name__ == "__main__":
    root = tk.Tk()
    app = VirtualAggregationApp(root)
    root.mainloop()
