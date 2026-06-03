import tkinter as tk
from tkinter import filedialog, messagebox
import os
from datetime import datetime

def perform_aggregation(set_file, attachment_files, count_per_set):
    try:
        # Чтение кодов наборов
        with open(set_file, 'r', encoding='utf-8') as f:
            set_codes = [line.strip() for line in f if line.strip()]

        # Чтение кодов вложений
        attachment_codes = []
        for file in attachment_files:
            with open(file, 'r', encoding='utf-8') as f:
                attachment_codes.extend([line.strip() for line in f if line.strip()])

        if not set_codes:
            raise Exception("Файл с кодами наборов пуст.")
        if not attachment_codes:
            raise Exception("Файлы с кодами вложений пусты.")

        needed_attachments = len(set_codes) * count_per_set
        if len(attachment_codes) < needed_attachments:
             actual_sets = len(attachment_codes) // count_per_set
             if actual_sets == 0:
                 raise Exception(f"Недостаточно кодов вложений даже для одного набора (нужно {count_per_set}, есть {len(attachment_codes)})")

             set_codes = set_codes[:actual_sets]
             # Будет выведено предупреждение в GUI, если это не вызвано как библиотека

        # Создание выходной папки
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = f"aggregation_{timestamp}"
        os.makedirs(output_dir, exist_ok=True)

        for i, set_code in enumerate(set_codes):
            start_idx = i * count_per_set
            end_idx = start_idx + count_per_set
            current_attachments = attachment_codes[start_idx:end_idx]

            # Имя файла на основе индекса для избежания проблем с символами в кодах
            file_name = f"set_{i+1}.txt"
            file_path = os.path.join(output_dir, file_name)

            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(set_code + "\n")
                for att in current_attachments:
                    f.write(att + "\n")

        return output_dir, len(set_codes)
    except Exception as e:
        raise e

class AggregationApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Виртуальная агрегация")
        self.root.geometry("500x450")

        self.set_file = ""
        self.attachment_files = []

        frame = tk.Frame(root, padx=20, pady=20)
        frame.pack(expand=True, fill="both")

        tk.Label(frame, text="1. Выберите файл с кодами НАБОРОВ:", font=("Arial", 10, "bold")).pack(anchor="w")
        tk.Button(frame, text="Выбрать файл", command=self.select_set_file).pack(pady=5, fill="x")
        self.lbl_set_file = tk.Label(frame, text="Файл не выбран", fg="grey", wraplength=450)
        self.lbl_set_file.pack(anchor="w", pady=(0, 10))

        tk.Label(frame, text="2. Укажите количество вложений в один набор:", font=("Arial", 10, "bold")).pack(anchor="w")
        self.ent_count = tk.Entry(frame, justify="center", font=("Arial", 12))
        self.ent_count.insert(0, "10")
        self.ent_count.pack(pady=5)

        tk.Label(frame, text="3. Выберите файлы с кодами ВЛОЖЕНИЙ:", font=("Arial", 10, "bold")).pack(anchor="w", pady=(10, 0))
        tk.Button(frame, text="Выбрать файлы", command=self.select_attachment_files).pack(pady=5, fill="x")
        self.lbl_att_files = tk.Label(frame, text="Файлы не выбраны", fg="grey", wraplength=450)
        self.lbl_att_files.pack(anchor="w", pady=(0, 10))

        self.btn_run = tk.Button(frame, text="ЗАПУСТИТЬ АГРЕГАЦИЮ", command=self.run,
                                 bg="#4CAF50", fg="white", font=("Arial", 12, "bold"), height=2)
        self.btn_run.pack(pady=20, fill="x")

    def select_set_file(self):
        self.set_file = filedialog.askopenfilename(title="Выберите файл кодов наборов",
                                                   filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if self.set_file:
            self.lbl_set_file.config(text=os.path.basename(self.set_file), fg="black")

    def select_attachment_files(self):
        self.attachment_files = filedialog.askopenfilenames(title="Выберите файлы кодов вложений",
                                                            filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if self.attachment_files:
            names = [os.path.basename(f) for f in self.attachment_files]
            display_text = ", ".join(names)
            if len(display_text) > 100:
                display_text = f"Выбрано файлов: {len(self.attachment_files)}"
            self.lbl_att_files.config(text=display_text, fg="black")

    def run(self):
        if not self.set_file:
            messagebox.showerror("Ошибка", "Выберите файл кодов наборов")
            return
        if not self.attachment_files:
            messagebox.showerror("Ошибка", "Выберите файлы кодов вложений")
            return

        try:
            count = int(self.ent_count.get())
            if count <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Ошибка", "Введите корректное число вложений")
            return

        try:
            # Предварительная проверка количества
            with open(self.set_file, 'r', encoding='utf-8') as f:
                set_count = len([line for line in f if line.strip()])

            att_count = 0
            for file in self.attachment_files:
                with open(file, 'r', encoding='utf-8') as f:
                    att_count += len([line for line in f if line.strip()])

            needed = set_count * count
            if att_count < needed:
                if not messagebox.askyesno("Предупреждение",
                    f"Кодов вложений ({att_count}) меньше, чем требуется для всех наборов ({needed}).\n"
                    f"Будет обработано только {att_count // count} наборов.\nПродолжить?"):
                    return

            out_dir, total = perform_aggregation(self.set_file, self.attachment_files, count)
            messagebox.showinfo("Готово", f"Успешно обработано {total} наборов.\nРезультаты в папке: {out_dir}")
        except Exception as e:
            messagebox.showerror("Ошибка", str(e))

if __name__ == "__main__":
    root = tk.Tk()
    app = AggregationApp(root)
    root.mainloop()

# Build command:
# pyinstaller --noconsole --onefile virtual_aggregation.py
