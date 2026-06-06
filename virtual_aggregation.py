import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from datetime import datetime

class VirtualAggregationApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Виртуальная агрегация")
        self.root.geometry("600x450")

        self.parent_file = ""
        self.child_files = []

        self.create_widgets()

    def create_widgets(self):
        frame = ttk.Frame(self.root, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)

        # Parent File Selection
        ttk.Label(frame, text="Файл с родительскими кодами (наборы):").pack(anchor=tk.W, pady=(0, 5))
        self.parent_label = ttk.Label(frame, text="Файл не выбран", foreground="gray")
        self.parent_label.pack(anchor=tk.W, pady=(0, 10))
        ttk.Button(frame, text="Выбрать файл", command=self.select_parent_file).pack(anchor=tk.W, pady=(0, 20))

        # Attachments Count
        ttk.Label(frame, text="Количество вложений в каждый набор:").pack(anchor=tk.W, pady=(0, 5))
        self.count_var = tk.StringVar(value="1")
        ttk.Entry(frame, textvariable=self.count_var, width=10).pack(anchor=tk.W, pady=(0, 20))

        # Child Files Selection
        ttk.Label(frame, text="Файлы с кодами вложений:").pack(anchor=tk.W, pady=(0, 5))
        self.child_label = ttk.Label(frame, text="Файлы не выбраны", foreground="gray")
        self.child_label.pack(anchor=tk.W, pady=(0, 10))
        ttk.Button(frame, text="Выбрать файлы", command=self.select_child_files).pack(anchor=tk.W, pady=(0, 20))

        # Progress Bar
        self.progress = ttk.Progressbar(frame, orient=tk.HORIZONTAL, length=400, mode='determinate')
        self.progress.pack(pady=20)

        # Run Button
        self.run_button = ttk.Button(frame, text="Запустить агрегацию", command=self.run_aggregation)
        self.run_button.pack(pady=10)

    def select_parent_file(self):
        file = filedialog.askopenfilename(filetypes=[("Text files", "*.txt")])
        if file:
            self.parent_file = file
            self.parent_label.config(text=os.path.basename(file), foreground="black")

    def select_child_files(self):
        files = filedialog.askopenfilenames(filetypes=[("Text files", "*.txt")])
        if files:
            self.child_files = list(files)
            self.child_label.config(text=f"Выбрано файлов: {len(files)}", foreground="black")

    def run_aggregation(self):
        if not self.parent_file:
            messagebox.showerror("Ошибка", "Выберите файл с родительскими кодами")
            return
        if not self.child_files:
            messagebox.showerror("Ошибка", "Выберите файлы с кодами вложений")
            return

        try:
            items_per_parent = int(self.count_var.get())
            if items_per_parent <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Ошибка", "Введите корректное число вложений (целое число > 0)")
            return

        try:
            # Read parent codes
            with open(self.parent_file, 'r', encoding='utf-8') as f:
                parents = [line.strip() for line in f if line.strip()]

            # Read child codes
            children = []
            for child_file in self.child_files:
                with open(child_file, 'r', encoding='utf-8') as f:
                    children.extend([line.strip() for line in f if line.strip()])

            if len(children) < len(parents) * items_per_parent:
                if not messagebox.askyesno("Предупреждение", f"Кодов вложений ({len(children)}) меньше, чем необходимо для всех наборов ({len(parents) * items_per_parent}). Продолжить?"):
                    return

            # Create output directory
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_dir = f"aggregation_{timestamp}"
            os.makedirs(output_dir, exist_ok=True)

            self.progress['maximum'] = len(parents)
            processed = 0

            for i, parent in enumerate(parents):
                start_idx = i * items_per_parent
                end_idx = start_idx + items_per_parent

                current_children = children[start_idx:end_idx]
                if not current_children:
                    break

                # Create individual file for each parent
                safe_parent_name = "".join(x for x in parent if x.isalnum() or x in "._- ")[:50]
                output_file = os.path.join(output_dir, f"{safe_parent_name}.txt")

                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(f"{parent}\n")
                    for child in current_children:
                        f.write(f"{child}\n")

                processed += 1
                self.progress['value'] = processed
                self.root.update_idletasks()

            messagebox.showinfo("Успех", f"Агрегация завершена.\nОбработано наборов: {processed}\nРезультаты в папке: {output_dir}")

        except Exception as e:
            messagebox.showerror("Ошибка", f"Произошла ошибка при выполнении: {str(e)}")
        finally:
            self.progress['value'] = 0

if __name__ == "__main__":
    root = tk.Tk()
    app = VirtualAggregationApp(root)
    root.mainloop()
