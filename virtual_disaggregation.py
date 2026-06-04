import tkinter as tk
from tkinter import filedialog, messagebox
import os
from datetime import datetime

def perform_disaggregation(input_files):
    try:
        all_sets = []
        all_attachments = []

        for file_path in input_files:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = [line.strip() for line in f if line.strip()]
                if not lines:
                    continue

                # Первая строка - код набора
                all_sets.append(lines[0])
                # Остальные строки - вложения
                if len(lines) > 1:
                    all_attachments.extend(lines[1:])

        if not all_sets and not all_attachments:
            raise Exception("Не удалось извлечь данные из выбранных файлов.")

        # Создание выходной папки
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = f"disaggregation_{timestamp}"
        os.makedirs(output_dir, exist_ok=True)

        sets_path = os.path.join(output_dir, "all_sets.txt")
        atts_path = os.path.join(output_dir, "all_attachments.txt")

        with open(sets_path, 'w', encoding='utf-8') as f:
            for s in all_sets:
                f.write(s + "\n")

        with open(atts_path, 'w', encoding='utf-8') as f:
            for a in all_attachments:
                f.write(a + "\n")

        return output_dir, len(all_sets), len(all_attachments)
    except Exception as e:
        raise e

class DisaggregationApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Виртуальная разагрегация")
        self.root.geometry("500x400")

        self.input_files = []

        frame = tk.Frame(root, padx=20, pady=20)
        frame.pack(expand=True, fill="both")

        tk.Label(frame, text="1. Выберите файлы для РАЗАГРЕГАЦИИ:", font=("Arial", 10, "bold")).pack(anchor="w")
        tk.Button(frame, text="Выбрать файлы", command=self.select_files).pack(pady=10, fill="x")

        self.lbl_files = tk.Label(frame, text="Файлы не выбраны", fg="grey", wraplength=450)
        self.lbl_files.pack(anchor="w", pady=(0, 20))

        self.btn_run = tk.Button(frame, text="ЗАПУСТИТЬ РАЗАГРЕГАЦИЮ", command=self.run,
                                 bg="#f44336", fg="white", font=("Arial", 12, "bold"), height=2)
        self.btn_run.pack(pady=20, fill="x")

    def select_files(self):
        self.input_files = filedialog.askopenfilenames(title="Выберите файлы наборов",
                                                       filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if self.input_files:
            display_text = f"Выбрано файлов: {len(self.input_files)}"
            self.lbl_files.config(text=display_text, fg="black")

    def run(self):
        if not self.input_files:
            messagebox.showerror("Ошибка", "Выберите файлы для обработки")
            return

        try:
            out_dir, sets_count, atts_count = perform_disaggregation(self.input_files)
            messagebox.showinfo("Готово",
                f"Обработка завершена.\nНаборов: {sets_count}\nВложений: {atts_count}\nРезультаты в папке: {out_dir}")
        except Exception as e:
            messagebox.showerror("Ошибка", str(e))

if __name__ == "__main__":
    root = tk.Tk()
    app = DisaggregationApp(root)
    root.mainloop()

# Build command for Windows 8/10/11:
# pyinstaller --noconsole --onefile virtual_disaggregation.py
