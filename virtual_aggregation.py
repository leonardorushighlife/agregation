import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import os
import re
from datetime import datetime
import traceback

"""
Скрипт для виртуальной агрегации кодов маркировки.
Команда для сборки в EXE:
pyinstaller --noconsole --onefile virtual_aggregation.py
"""

class VirtualAggregationApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Виртуальная агрегация")
        self.root.geometry("600x500")

        self.parent_file = ""
        self.child_files = []

        self.setup_ui()

    def setup_ui(self):
        padding = {'padx': 10, 'pady': 5}

        # Родительские коды
        frame_parent = ttk.LabelFrame(self.root, text="Родительские коды (наборы)")
        frame_parent.pack(fill="x", **padding)

        self.btn_parent = tk.Button(frame_parent, text="Выбрать файл с кодами наборов", command=self.select_parent_file)
        self.btn_parent.pack(side="left", **padding)

        self.lbl_parent = tk.Label(frame_parent, text="Файл не выбран", fg="red")
        self.lbl_parent.pack(side="left", **padding)

        # Вложения
        frame_child = ttk.LabelFrame(self.root, text="Коды вложений (единицы)")
        frame_child.pack(fill="x", **padding)

        self.btn_child = tk.Button(frame_child, text="Выбрать файлы с кодами вложений", command=self.select_child_files)
        self.btn_child.pack(side="left", **padding)

        self.lbl_child = tk.Label(frame_child, text="Файлы не выбраны", fg="red")
        self.lbl_child.pack(side="left", **padding)

        # Настройки
        frame_settings = tk.Frame(self.root)
        frame_settings.pack(fill="x", **padding)

        tk.Label(frame_settings, text="Количество вложений в каждый набор:").pack(side="left", **padding)
        self.ent_count = tk.Entry(frame_settings, width=10)
        self.ent_count.insert(0, "1")
        self.ent_count.pack(side="left", **padding)

        # Действие
        self.btn_run = tk.Button(self.root, text="Начать агрегацию", command=self.run_aggregation, bg="green", fg="white", font=("Arial", 12, "bold"))
        self.btn_run.pack(pady=20)

        # Лог
        self.txt_log = tk.Text(self.root, height=10, state="disabled")
        self.txt_log.pack(fill="both", expand=True, **padding)

    def log(self, message):
        self.txt_log.config(state="normal")
        self.txt_log.insert(tk.END, f"[{datetime.now().strftime('%H:%M:%S')}] {message}\n")
        self.txt_log.see(tk.END)
        self.txt_log.config(state="disabled")
        self.root.update_idletasks()

    def select_parent_file(self):
        filename = filedialog.askopenfilename(title="Выберите файл с родительскими кодами", filetypes=[("Text files", "*.txt")])
        if filename:
            self.parent_file = filename
            self.lbl_parent.config(text=os.path.basename(filename), fg="black")
            self.log(f"Выбран родительский файл: {filename}")

    def select_child_files(self):
        filenames = filedialog.askopenfilenames(title="Выберите файлы с кодами вложений", filetypes=[("Text files", "*.txt")])
        if filenames:
            self.child_files = list(filenames)
            self.lbl_child.config(text=f"Выбрано файлов: {len(filenames)}", fg="black")
            self.log(f"Выбрано файлов вложений: {len(filenames)}")

    def read_codes(self, filepath):
        encodings = ['utf-8-sig', 'utf-16', 'utf-8', 'cp1251']
        for enc in encodings:
            try:
                with open(filepath, 'r', encoding=enc) as f:
                    content = f.read()
                codes = [line.strip() for line in content.splitlines() if line.strip()]
                return codes
            except (UnicodeDecodeError, UnicodeError):
                continue
        raise Exception(f"Не удалось определить кодировку файла {filepath}")

    def sanitize_filename(self, filename):
        return re.sub(r'[\\/*?:"<>|]', "_", filename)

    def run_aggregation(self):
        try:
            if not self.parent_file:
                messagebox.showwarning("Внимание", "Выберите файл с родительскими кодами!")
                return
            if not self.child_files:
                messagebox.showwarning("Внимание", "Выберите файлы с кодами вложений!")
                return

            try:
                count_per_parent = int(self.ent_count.get())
                if count_per_parent <= 0:
                    raise ValueError
            except ValueError:
                messagebox.showwarning("Внимание", "Введите корректное количество вложений (целое число больше 0)!")
                return

            self.log("Начало процесса агрегации...")

            # 1. Чтение родительских кодов
            parent_codes = self.read_codes(self.parent_file)
            self.log(f"Загружено родительских кодов: {len(parent_codes)}")

            # 2. Чтение всех дочерних кодов
            all_child_codes = []
            for f in self.child_files:
                codes = self.read_codes(f)
                all_child_codes.extend(codes)
            self.log(f"Всего загружено кодов вложений: {len(all_child_codes)}")

            # 3. Проверка количества
            total_required = len(parent_codes) * count_per_parent
            if len(all_child_codes) < total_required:
                actual_sets = len(all_child_codes) // count_per_parent
                if not messagebox.askyesno("Недостаточно кодов",
                    f"Доступно вложений: {len(all_child_codes)}\n"
                    f"Требуется для всех наборов: {total_required}\n"
                    f"Будет собрано наборов: {actual_sets}\n\n"
                    f"Продолжить с частичной агрегацией?"):
                    self.log("Агрегация отменена пользователем.")
                    return
                parent_codes = parent_codes[:actual_sets]

            # 4. Создание папки
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_dir = f"aggregation_results_{timestamp}"
            os.makedirs(output_dir, exist_ok=True)
            self.log(f"Создана папка: {output_dir}")

            self.perform_pairing_and_writing(parent_codes, all_child_codes, count_per_parent, output_dir)

        except Exception as e:
            self.log(f"ОШИБКА: {str(e)}")
            messagebox.showerror("Ошибка", f"Произошла ошибка во время агрегации:\n{traceback.format_exc()}")

    def perform_pairing_and_writing(self, parent_codes, all_child_codes, count_per_parent, output_dir):
        used_filenames = set()

        for i, parent_code in enumerate(parent_codes):
            # Извлекаем вложения для текущего родителя
            start_idx = i * count_per_parent
            end_idx = start_idx + count_per_parent
            current_children = all_child_codes[start_idx:end_idx]

            # Формируем имя файла
            base_name = self.sanitize_filename(parent_code)
            filename = f"{base_name}.txt"

            # Обработка коллизий имен
            counter = 1
            while filename.lower() in used_filenames:
                filename = f"{base_name}_{counter}.txt"
                counter += 1

            used_filenames.add(filename.lower())
            filepath = os.path.join(output_dir, filename)

            # Запись в файл
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(parent_code + "\n")
                for child in current_children:
                    f.write(child + "\n")

            if (i + 1) % 10 == 0 or (i + 1) == len(parent_codes):
                self.log(f"Обработано наборов: {i + 1} из {len(parent_codes)}")

        self.log("Агрегация успешно завершена!")
        messagebox.showinfo("Готово", f"Агрегация завершена!\nРезультаты в папке: {output_dir}")

if __name__ == "__main__":
    try:
        root = tk.Tk()
        app = VirtualAggregationApp(root)
        root.mainloop()
    except Exception as e:
        with open("error_log.txt", "w") as f:
            traceback.print_exc(file=f)
        messagebox.showerror("Критическая ошибка", traceback.format_exc())
