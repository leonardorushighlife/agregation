import tkinter as tk
from tkinter import filedialog, messagebox
import os
from datetime import datetime
import re
import traceback

# Инструкция для сборки в EXE:
# pyinstaller --noconsole --onefile virtual_aggregation.py

def sanitize_filename(filename):
    return re.sub(r'[\\/*?:"<>|]', "_", filename)

def read_codes(filepaths):
    if isinstance(filepaths, str):
        filepaths = [filepaths]

    codes = []
    # UTF-8-SIG (with BOM) -> UTF-16 -> UTF-8 -> CP1251
    encodings = ['utf-8-sig', 'utf-16', 'utf-8', 'windows-1251']

    for path in filepaths:
        success = False
        for enc in encodings:
            try:
                with open(path, 'r', encoding=enc) as f:
                    content = f.read()
                    # Если считалось что-то совсем странное (много нулевых байтов в utf-8), пробуем другую кодировку
                    if enc == 'utf-8' and '\x00' in content:
                        continue

                    lines = content.splitlines()
                    for line in lines:
                        c = line.strip()
                        if c:
                            codes.append(c)
                    success = True
                    break
            except (UnicodeDecodeError, UnicodeError):
                continue

        if not success:
            raise Exception(f"Не удалось определить кодировку файла: {path}")

    return codes

def perform_aggregation(parent_file, child_files, count_per_parent, progress_callback=None):
    parents = read_codes(parent_file)
    children = read_codes(child_files)

    if not parents:
        raise Exception("Файл наборов пуст!")
    if not children:
        raise Exception("Файлы вложений пусты!")

    total_required = len(parents) * count_per_parent
    if len(children) < total_required:
        actual_sets = len(children) // count_per_parent
        if actual_sets == 0:
            raise Exception(f"Недостаточно вложений даже для одного набора! Всего вложений: {len(children)}, требуется на один: {count_per_parent}")

        # Можно было бы спросить пользователя, но для ядра просто ограничим
        parents = parents[:actual_sets]

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = f"aggregation_results_{timestamp}"
    os.makedirs(output_dir, exist_ok=True)

    for i, p_code in enumerate(parents):
        start_idx = i * count_per_parent
        end_idx = start_idx + count_per_parent
        batch = children[start_idx:end_idx]

        filename = sanitize_filename(p_code) + ".txt"
        file_path = os.path.join(output_dir, filename)

        # Если вдруг дубликат кода набора, добавим индекс
        if os.path.exists(file_path):
            filename = f"{sanitize_filename(p_code)}_{i}.txt"
            file_path = os.path.join(output_dir, filename)

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(p_code + "\n")
            for c_code in batch:
                f.write(c_code + "\n")

        if progress_callback:
            progress_callback(i + 1, len(parents))

    return output_dir, len(parents)

class VirtualAggregationApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Виртуальная агрегация")
        self.root.geometry("500x450")

        self.parent_file = ""
        self.child_files = []

        # UI elements
        tk.Label(root, text="Виртуальная агрегация", font=("Arial", 16, "bold")).pack(pady=10)

        # Parent file
        self.btn_parent = tk.Button(root, text="Выбрать файл с кодами НАБОРА", command=self.select_parent_file)
        self.btn_parent.pack(pady=5)
        self.lbl_parent = tk.Label(root, text="Файл не выбран", fg="red")
        self.lbl_parent.pack()

        # Attachment count
        tk.Label(root, text="Количество вложений в один набор:").pack(pady=(10, 0))
        self.ent_count = tk.Entry(root, justify="center")
        self.ent_count.insert(0, "1")
        self.ent_count.pack()

        # Child files
        self.btn_children = tk.Button(root, text="Выбрать файлы с кодами ВЛОЖЕНИЙ", command=self.select_child_files)
        self.btn_children.pack(pady=5)
        self.lbl_children = tk.Label(root, text="Файлы не выбраны", fg="red")
        self.lbl_children.pack()

        # Process button
        self.btn_process = tk.Button(root, text="НАЧАТЬ АГРЕГАЦИЮ", command=self.process,
                                     bg="green", fg="white", font=("Arial", 12, "bold"),
                                     height=2, width=20)
        self.btn_process.pack(pady=30)

    def select_parent_file(self):
        file = filedialog.askopenfilename(filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if file:
            self.parent_file = file
            self.lbl_parent.config(text=os.path.basename(file), fg="black")

    def select_child_files(self):
        files = filedialog.askopenfilenames(filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if files:
            self.child_files = list(files)
            self.lbl_children.config(text=f"Выбрано файлов: {len(files)}", fg="black")

    def process(self):
        if not self.parent_file:
            messagebox.showerror("Ошибка", "Выберите файл с кодами наборов!")
            return
        if not self.child_files:
            messagebox.showerror("Ошибка", "Выберите файлы с кодами вложений!")
            return

        try:
            count = int(self.ent_count.get())
            if count <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Ошибка", "Введите корректное количество вложений (целое число больше 0)!")
            return

        try:
            parents = read_codes(self.parent_file)
            children = read_codes(self.child_files)

            total_req = len(parents) * count
            if len(children) < total_req:
                actual = len(children) // count
                if actual == 0:
                    messagebox.showwarning("Предупреждение", f"Недостаточно вложений даже для одного набора!\nВсего вложений: {len(children)}, требуется: {count}")
                    return

                if not messagebox.askyesno("Внимаение", f"Вложений ({len(children)}) не хватит на все наборы ({len(parents)}).\nБудет собрано только {actual} наборов. Продолжить?"):
                    return

            out_dir, total = perform_aggregation(self.parent_file, self.child_files, count)

            messagebox.showinfo("Успех", f"Агрегация завершена!\nСоздано наборов: {total}\nПапка: {out_dir}")
            os.startfile(out_dir) if hasattr(os, 'startfile') else None

        except Exception as e:
            messagebox.showerror("Ошибка", f"Произошла ошибка при выполнении:\n{str(e)}")

if __name__ == "__main__":
    try:
        root = tk.Tk()
        app = VirtualAggregationApp(root)
        root.mainloop()
    except Exception:
        messagebox.showerror("Критическая ошибка", traceback.format_exc())
