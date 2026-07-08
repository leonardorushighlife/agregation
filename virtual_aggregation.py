"""
Скрипт для виртуальной агрегации кодов маркировки.
Позволяет объединить коды агрегатов (наборов) с кодами вложений из нескольких файлов.

Инструкция для сборки в EXE:
1. Установите PyInstaller: pip install pyinstaller
2. Соберите проект: pyinstaller --noconsole --onefile virtual_aggregation.py

Автор: Jules
Дата: 2024
"""

import os
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from datetime import datetime
import traceback
import re

def read_codes(filepath):
    """Считывает коды из файла, пробуя различные кодировки."""
    encodings = ['utf-8-sig', 'utf-16', 'utf-8', 'cp1251']
    for enc in encodings:
        try:
            with open(filepath, 'r', encoding=enc) as f:
                return [line.strip() for line in f if line.strip()]
        except (UnicodeDecodeError, UnicodeError):
            continue
    raise Exception(f"Не удалось определить кодировку файла: {filepath}")

def sanitize_filename(filename):
    """Очищает строку для использования в качестве имени файла."""
    # Заменяем недопустимые символы на подчеркивание
    return re.sub(r'[\\/*?:"<>|]', '_', filename)

def perform_aggregation(parent_file, child_files, count_per_parent, status_callback=None, confirm_callback=None):
    """
    Основная логика агрегации.
    status_callback: функция для обновления статуса в UI.
    confirm_callback: функция для подтверждения продолжения при нехватке кодов.
    """
    if status_callback: status_callback("Чтение файлов...")

    parents = read_codes(parent_file)
    all_children = []
    for cf in child_files:
        all_children.extend(read_codes(cf))

    total_required = len(parents) * count_per_parent
    actual_sets = len(parents)

    if len(all_children) < total_required:
        msg = f"Внимание! Недостаточно кодов вложений.\nДоступно: {len(all_children)}\nТребуется: {total_required}\n\nПродолжить и собрать только возможные полные наборы?"
        if confirm_callback:
            if not confirm_callback(msg):
                return None
            actual_sets = len(all_children) // count_per_parent
        else:
            actual_sets = len(all_children) // count_per_parent

    if actual_sets == 0:
        raise Exception("Недостаточно кодов даже для одного набора.")

    # Создание папки для результатов
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = f"aggregation_results_{timestamp}"
    os.makedirs(output_dir, exist_ok=True)

    child_idx = 0
    created_count = 0

    for i in range(actual_sets):
        parent_code = parents[i]
        sanitized_parent = sanitize_filename(parent_code)

        # Обработка возможных дубликатов имен файлов (если коды после очистки совпали)
        filename = f"{sanitized_parent}.txt"
        filepath = os.path.join(output_dir, filename)
        counter = 1
        while os.path.exists(filepath):
            filename = f"{sanitized_parent}_{counter}.txt"
            filepath = os.path.join(output_dir, filename)
            counter += 1

        current_children = all_children[child_idx : child_idx + count_per_parent]
        child_idx += count_per_parent

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(parent_code + '\n')
            for c in current_children:
                f.write(c + '\n')

        created_count += 1
        if status_callback:
            status_callback(f"Создано файлов: {created_count} из {actual_sets}")

    return output_dir, created_count

class AggregatorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Виртуальная Агрегация")
        self.root.geometry("600x450")

        self.parent_file = ""
        self.child_files = []

        self.setup_ui()

    def setup_ui(self):
        style = ttk.Style()
        style.configure("TButton", padding=6, font=('Arial', 10))
        style.configure("TLabel", font=('Arial', 10))

        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Секция родительского файла
        ttk.Label(main_frame, text="Файл с кодами наборов (родители):").pack(anchor=tk.W)
        parent_btn_frame = ttk.Frame(main_frame)
        parent_btn_frame.pack(fill=tk.X, pady=(5, 15))

        self.parent_label = ttk.Label(parent_btn_frame, text="Файл не выбран", foreground="gray")
        self.parent_label.pack(side=tk.LEFT, fill=tk.X, expand=True)

        ttk.Button(parent_btn_frame, text="Выбрать", command=self.select_parent_file).pack(side=tk.RIGHT)

        # Секция количества вложений
        ttk.Label(main_frame, text="Количество вложений в каждый набор:").pack(anchor=tk.W)
        self.count_entry = ttk.Entry(main_frame, width=10)
        self.count_entry.insert(0, "1")
        self.count_entry.pack(anchor=tk.W, pady=(5, 15))

        # Секция файлов вложений
        ttk.Label(main_frame, text="Файлы с кодами вложений (дети):").pack(anchor=tk.W)
        child_btn_frame = ttk.Frame(main_frame)
        child_btn_frame.pack(fill=tk.X, pady=(5, 10))

        self.child_listbox = tk.Listbox(main_frame, height=5)
        self.child_listbox.pack(fill=tk.BOTH, expand=True, pady=5)

        ttk.Button(child_btn_frame, text="Добавить файлы", command=self.select_child_files).pack(side=tk.LEFT)
        ttk.Button(child_btn_frame, text="Очистить список", command=self.clear_child_files).pack(side=tk.RIGHT)

        # Кнопка запуска
        self.start_btn = ttk.Button(main_frame, text="НАЧАТЬ АГРЕГАЦИЮ", command=self.start_process)
        self.start_btn.pack(fill=tk.X, pady=20)

        # Статус
        self.status_var = tk.StringVar(value="Готов к работе")
        self.status_label = ttk.Label(main_frame, textvariable=self.status_var, font=('Arial', 9, 'italic'))
        self.status_label.pack(anchor=tk.W)

    def select_parent_file(self):
        file = filedialog.askopenfilename(title="Выберите файл с кодами наборов", filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if file:
            self.parent_file = file
            self.parent_label.config(text=os.path.basename(file), foreground="black")

    def select_child_files(self):
        files = filedialog.askopenfilenames(title="Выберите файлы с кодами вложений", filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if files:
            for f in files:
                if f not in self.child_files:
                    self.child_files.append(f)
                    self.child_listbox.insert(tk.END, os.path.basename(f))

    def clear_child_files(self):
        self.child_files = []
        self.child_listbox.delete(0, tk.END)

    def start_process(self):
        if not self.parent_file:
            messagebox.showerror("Ошибка", "Не выбран файл с кодами наборов!")
            return
        if not self.child_files:
            messagebox.showerror("Ошибка", "Не выбраны файлы с кодами вложений!")
            return

        try:
            count = int(self.count_entry.get())
            if count <= 0: raise ValueError
        except ValueError:
            messagebox.showerror("Ошибка", "Введите корректное число вложений (больше 0)!")
            return

        self.start_btn.config(state=tk.DISABLED)

        try:
            result = perform_aggregation(
                self.parent_file,
                self.child_files,
                count,
                status_callback=self.update_status,
                confirm_callback=lambda m: messagebox.askyesno("Подтверждение", m)
            )

            if result:
                output_dir, total = result
                messagebox.showinfo("Успех", f"Агрегация завершена!\nСоздано наборов: {total}\nРезультаты в папке: {output_dir}")
                self.update_status("Завершено успешно")
            else:
                self.update_status("Отменено пользователем")

        except Exception as e:
            error_msg = f"Произошла ошибка:\n{str(e)}\n\n{traceback.format_exc()}"
            print(error_msg)
            messagebox.showerror("Ошибка", f"Произошла ошибка: {str(e)}")
            self.update_status("Ошибка в процессе")
        finally:
            self.start_btn.config(state=tk.NORMAL)

    def update_status(self, text):
        self.status_var.set(text)
        self.root.update_idletasks()

def main():
    try:
        root = tk.Tk()
        app = AggregatorApp(root)
        root.mainloop()
    except Exception as e:
        # Критическая ошибка при запуске
        error_log = traceback.format_exc()
        try:
            import tkinter.messagebox as mb
            mb.showerror("Критическая ошибка", f"Приложение не смогло запуститься:\n{e}\n\n{error_log}")
        except:
            print(error_log)

if __name__ == "__main__":
    main()
