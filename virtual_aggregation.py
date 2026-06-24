"""
Инструкция по сборке в EXE:
1. Установите PyInstaller: pip install pyinstaller
2. Соберите проект: pyinstaller --noconsole --onefile virtual_aggregation.py
"""

import tkinter as tk
from tkinter import filedialog, messagebox
import os
import re
from datetime import datetime

def read_codes(filepath):
    """Читает коды из файла, пробуя разные кодировки."""
    encodings = ['utf-8-sig', 'utf-16', 'utf-8', 'cp1251']
    for enc in encodings:
        try:
            with open(filepath, 'r', encoding=enc) as f:
                return [line.strip() for line in f if line.strip()]
        except (UnicodeDecodeError, LookupError):
            continue
    return []

def sanitize_filename(filename):
    """Удаляет недопустимые символы для имен файлов Windows."""
    return re.sub(r'[\\/*?:"<>|]', "_", filename)

def perform_aggregation(parent_file, child_files, count_per_set, progress_callback=None, confirm_callback=None):
    """
    Основная логика агрегации.
    progress_callback: функция для отображения статуса.
    confirm_callback: функция для подтверждения при нехватке кодов (принимает сообщение, возвращает bool).
    """
    parent_codes = read_codes(parent_file)
    if not parent_codes:
        return False, "Файл с кодами наборов пуст или не читается"

    all_child_codes = []
    for cf in child_files:
        all_child_codes.extend(read_codes(cf))

    if not all_child_codes:
        return False, "Файлы с кодами содержимого пусты или не читаются"

    needed_children = len(parent_codes) * count_per_set
    if len(all_child_codes) < needed_children:
        actual_sets = len(all_child_codes) // count_per_set
        if actual_sets == 0:
            return False, f"Дочерних кодов ({len(all_child_codes)}) недостаточно даже для одного набора (нужно {count_per_set})"

        msg = f"Дочерних кодов ({len(all_child_codes)}) недостаточно для всех наборов ({len(parent_codes)}).\nБудет создано только {actual_sets} наборов. Продолжить?"
        if confirm_callback and not confirm_callback(msg):
            return False, "Агрегация отменена пользователем"

        parent_codes = parent_codes[:actual_sets]

    # Создание папки для результатов
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = f"aggregation_results_{timestamp}"
    os.makedirs(output_dir, exist_ok=True)

    for i, p_code in enumerate(parent_codes):
        start_idx = i * count_per_set
        end_idx = start_idx + count_per_set
        current_children = all_child_codes[start_idx:end_idx]

        safe_p_code = sanitize_filename(p_code)
        filename = os.path.join(output_dir, f"{safe_p_code}.txt")

        with open(filename, 'w', encoding='utf-8') as f:
            f.write(p_code + "\n")
            for c_code in current_children:
                f.write(c_code + "\n")

        if progress_callback:
            progress_callback(f"Обработано наборов: {i+1} из {len(parent_codes)}")

    return True, output_dir

class VirtualAggregationApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Виртуальная агрегация")
        self.root.geometry("550x450")

        self.parent_file = ""
        self.child_files = []

        # UI элементы
        tk.Label(root, text="Виртуальная агрегация", font=("Arial", 16, "bold")).pack(pady=15)

        frame = tk.Frame(root)
        frame.pack(pady=5, padx=20, fill="x")

        # Выбор родительского файла
        self.btn_parent = tk.Button(frame, text="1. Выбрать файл кодов НАБОРОВ (родители)", command=self.select_parent_file)
        self.btn_parent.pack(pady=5, fill="x")
        self.lbl_parent = tk.Label(frame, text="Файл не выбран", fg="gray", wraplength=450)
        self.lbl_parent.pack()

        # Количество вложений
        tk.Label(frame, text="2. Количество вложений в один набор:", font=("Arial", 10, "bold")).pack(pady=(15, 0))
        self.entry_count = tk.Entry(frame, justify="center", font=("Arial", 12))
        self.entry_count.insert(0, "1")
        self.entry_count.pack(pady=5)

        # Выбор дочерних файлов
        self.btn_children = tk.Button(frame, text="3. Выбрать файлы кодов СОДЕРЖИМОГО (дети)", command=self.select_child_files)
        self.btn_children.pack(pady=5, fill="x")
        self.lbl_children = tk.Label(frame, text="Файлы не выбраны", fg="gray", wraplength=450)
        self.lbl_children.pack()

        # Кнопка старта
        self.btn_start = tk.Button(root, text="ЗАПУСТИТЬ АГРЕГАЦИЮ", command=self.start_aggregation,
                                   bg="#4CAF50", fg="white", font=("Arial", 12, "bold"), height=2)
        self.btn_start.pack(pady=25, padx=50, fill="x")

        # Статус бар
        self.status_label = tk.Label(root, text="", fg="blue")
        self.status_label.pack(side="bottom", pady=5)

    def select_parent_file(self):
        file = filedialog.askopenfilename(title="Выберите файл с родительскими кодами", filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if file:
            self.parent_file = file
            self.lbl_parent.config(text=os.path.basename(file), fg="black")

    def select_child_files(self):
        files = filedialog.askopenfilenames(title="Выберите файлы с дочерними кодами", filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if files:
            self.child_files = list(files)
            self.lbl_children.config(text=f"Выбрано файлов: {len(files)}", fg="black")

    def update_progress(self, msg):
        self.status_label.config(text=msg)
        self.root.update_idletasks()

    def confirm_dialog(self, msg):
        return messagebox.askyesno("Предупреждение", msg)

    def start_aggregation(self):
        if not self.parent_file:
            messagebox.showerror("Ошибка", "Сначала выберите файл с кодами наборов!")
            return
        if not self.child_files:
            messagebox.showerror("Ошибка", "Сначала выберите файлы с кодами содержимого!")
            return

        try:
            count_per_set = int(self.entry_count.get())
            if count_per_set <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Ошибка", "Введите целое положительное число вложений!")
            return

        self.btn_start.config(state="disabled")
        self.status_label.config(text="Обработка...")

        try:
            success, result = perform_aggregation(
                self.parent_file,
                self.child_files,
                count_per_set,
                progress_callback=self.update_progress,
                confirm_callback=self.confirm_dialog
            )

            if success:
                messagebox.showinfo("Успех", f"Агрегация завершена успешно!\n\nРезультаты сохранены в папку:\n{result}")
                self.status_label.config(text=f"Готово. Папка: {result}", fg="green")
            else:
                messagebox.showwarning("Внимание", result)
                self.status_label.config(text="Операция прервана", fg="red")
        except Exception as e:
            messagebox.showerror("Критическая ошибка", f"Произошла непредвиденная ошибка:\n{str(e)}")
            self.status_label.config(text="Ошибка", fg="red")
        finally:
            self.btn_start.config(state="normal")

if __name__ == "__main__":
    root = tk.Tk()
    try:
        app = VirtualAggregationApp(root)
        root.mainloop()
    except Exception as e:
        # Для отладки в EXE полезно поймать ошибки запуска
        messagebox.showerror("Ошибка запуска", str(e))
