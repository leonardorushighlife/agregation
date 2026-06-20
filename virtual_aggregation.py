import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
import os
import sys
from datetime import datetime
import re

class VirtualAggregationApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Виртуальная агрегация")
        self.root.geometry("600x500")

        self.parent_file = ""
        self.child_files = []

        self.setup_ui()

    def setup_ui(self):
        # Заголовок
        tk.Label(self.root, text="Виртуальная агрегация наборов", font=("Arial", 16, "bold")).pack(pady=10)

        # Выбор файла родительских кодов
        frame_parent = tk.Frame(self.root)
        frame_parent.pack(fill="x", padx=20, pady=5)
        tk.Label(frame_parent, text="Коды наборов (1 файл):").pack(side="left")
        self.btn_parent = tk.Button(frame_parent, text="Выбрать файл", command=self.select_parent_file)
        self.btn_parent.pack(side="right")
        self.lbl_parent_path = tk.Label(self.root, text="Файл не выбран", fg="gray", font=("Arial", 8))
        self.lbl_parent_path.pack(fill="x", padx=20)

        # Выбор файлов дочерних кодов
        frame_child = tk.Frame(self.root)
        frame_child.pack(fill="x", padx=20, pady=5)
        tk.Label(frame_child, text="Коды вложений (TXT файлы):").pack(side="left")
        self.btn_child = tk.Button(frame_child, text="Выбрать файлы", command=self.select_child_files)
        self.btn_child.pack(side="right")
        self.lbl_child_count = tk.Label(self.root, text="Файлы не выбраны", fg="gray", font=("Arial", 8))
        self.lbl_child_count.pack(fill="x", padx=20)

        # Количество вложений
        frame_count = tk.Frame(self.root)
        frame_count.pack(fill="x", padx=20, pady=10)
        tk.Label(frame_count, text="Количество вложений в 1 набор:").pack(side="left")
        self.entry_count = tk.Entry(frame_count, width=10)
        self.entry_count.insert(0, "1")
        self.entry_count.pack(side="left", padx=10)

        # Кнопка запуска
        self.btn_run = tk.Button(self.root, text="НАЧАТЬ АГРЕГАЦИЮ", font=("Arial", 12, "bold"),
                                 bg="green", fg="white", height=2, command=self.run_aggregation)
        self.btn_run.pack(fill="x", padx=20, pady=20)

        # Лог событий
        tk.Label(self.root, text="Лог выполнения:").pack(anchor="w", padx=20)
        self.log_area = scrolledtext.ScrolledText(self.root, height=10, font=("Consolas", 9))
        self.log_area.pack(fill="both", padx=20, pady=5, expand=True)

    def log(self, message):
        self.log_area.insert(tk.END, f"[{datetime.now().strftime('%H:%M:%S')}] {message}\n")
        self.log_area.see(tk.END)

    def select_parent_file(self):
        filename = filedialog.askopenfilename(
            title="Выберите файл с кодами наборов",
            filetypes=(("Text files", "*.txt"), ("All files", "*.*"))
        )
        if filename:
            self.parent_file = filename
            self.lbl_parent_path.config(text=os.path.basename(filename), fg="black")
            self.log(f"Выбран родительский файл: {os.path.basename(filename)}")

    def select_child_files(self):
        filenames = filedialog.askopenfilenames(
            title="Выберите файлы с кодами вложений",
            filetypes=(("Text files", "*.txt"), ("All files", "*.*"))
        )
        if filenames:
            self.child_files = list(filenames)
            self.lbl_child_count.config(text=f"Выбрано файлов: {len(filenames)}", fg="black")
            self.log(f"Выбрано дочерних файлов: {len(filenames)}")

    def read_codes(self, filepath):
        """Читает коды из файла, пробуя разные кодировки."""
        encodings = ['utf-8-sig', 'utf-16', 'utf-8', 'cp1251']
        for enc in encodings:
            try:
                with open(filepath, 'r', encoding=enc) as f:
                    content = f.read()
                    # Разбиваем по строкам, убираем лишние пробелы и пустые строки
                    codes = [line.strip() for line in content.splitlines() if line.strip()]
                    return codes
            except (UnicodeDecodeError, Exception):
                continue
        return []

    def sanitize_filename(self, filename):
        """Удаляет недопустимые символы из имени файла."""
        return re.sub(r'[\\/*?:"<>|]', "_", filename)

    def run_aggregation(self):
        # Валидация ввода
        if not self.parent_file:
            messagebox.showerror("Ошибка", "Выберите файл с кодами наборов!")
            return
        if not self.child_files:
            messagebox.showerror("Ошибка", "Выберите файлы с кодами вложений!")
            return

        try:
            count_per_file = int(self.entry_count.get())
            if count_per_file < 1:
                raise ValueError
        except ValueError:
            messagebox.showerror("Ошибка", "Количество вложений должно быть целым числом больше 0!")
            return

        self.log("Начало процесса агрегации...")

        # Чтение кодов
        parent_codes = self.read_codes(self.parent_file)
        if not parent_codes:
            messagebox.showerror("Ошибка", "Файл наборов пуст или не удалось прочитать!")
            return

        all_child_codes = []
        for cf in self.child_files:
            codes = self.read_codes(cf)
            all_child_codes.extend(codes)
            self.log(f"Загружено {len(codes)} кодов из {os.path.basename(cf)}")

        if not all_child_codes:
            messagebox.showerror("Ошибка", "Файлы вложений пусты!")
            return

        # Расчет
        total_parents = len(parent_codes)
        total_children = len(all_child_codes)
        max_possible_sets = total_children // count_per_file

        actual_sets = min(total_parents, max_possible_sets)

        if actual_sets == 0:
            messagebox.showerror("Ошибка", f"Недостаточно вложений для создания хотя бы одного набора (нужно {count_per_file})")
            return

        self.log(f"Всего родительских кодов: {total_parents}")
        self.log(f"Всего дочерних кодов: {total_children}")
        self.log(f"Будет создано наборов: {actual_sets}")

        # Создание папки
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = f"aggregation_results_{timestamp}"
        try:
            os.makedirs(output_dir, exist_ok=True)
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось создать папку: {e}")
            return

        # Процесс агрегации
        success_count = 0
        child_idx = 0

        for i in range(actual_sets):
            p_code = parent_codes[i]
            # Берем N дочерних кодов
            current_children = all_child_codes[child_idx : child_idx + count_per_file]
            child_idx += count_per_file

            # Имя файла на основе родительского кода
            safe_name = self.sanitize_filename(p_code)
            if len(safe_name) > 150: # Ограничение длины для Windows
                safe_name = safe_name[:150]

            file_path = os.path.join(output_dir, f"{safe_name}.txt")

            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(p_code + "\n")
                    for c_code in current_children:
                        f.write(c_code + "\n")
                success_count += 1
            except Exception as e:
                self.log(f"Ошибка при записи файла {safe_name}: {e}")

        self.log(f"Агрегация завершена! Создано файлов: {success_count}")
        self.log(f"Результаты в папке: {os.path.abspath(output_dir)}")

        messagebox.showinfo("Готово", f"Успешно создано наборов: {success_count}\nПапка: {output_dir}")

if __name__ == "__main__":
    root = tk.Tk()
    app = VirtualAggregationApp(root)
    root.mainloop()
