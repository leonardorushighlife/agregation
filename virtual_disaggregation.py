"""
Виртуальная деагрегация кодов маркировки.
Этот скрипт извлекает родительский и дочерние коды из файлов наборов в выбранной папке
и объединяет их в два сводных текстовых файла.

Инструкция по сборке в exe:
1. Установите PyInstaller:
   pip install pyinstaller
2. Выполните команду сборки в консоли:
   pyinstaller --noconsole --onefile virtual_disaggregation.py
3. Скомпилированный файл будет находиться в папке dist/virtual_disaggregation.exe
"""

import os
import sys

# Ленивый импорт tkinter для headless-тестирования
def get_tkinter():
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
    return tk, filedialog, messagebox, ttk


def read_codes(filepath: str) -> list:
    """
    Читает коды из файла, пробуя разные кодировки по очереди:
    UTF-8-SIG, UTF-16, UTF-8, CP1251.
    """
    encodings = ['utf-8-sig', 'utf-16', 'utf-8', 'windows-1251']
    content = ""
    for encoding in encodings:
        try:
            with open(filepath, 'r', encoding=encoding) as f:
                content = f.read()
            break
        except Exception:
            continue
    else:
        raise ValueError(f"Не удалось прочитать файл {filepath} с использованием поддерживаемых кодировок.")

    # Разделяем на строки и очищаем
    lines = [line.strip() for line in content.splitlines() if line.strip()]
    return lines


def perform_disaggregation(input_dir: str) -> tuple:
    """
    Выполняет деагрегацию.
    Читает все txt-файлы в папке. Из каждого файла первая строка считается родителем (набором),
    все последующие — дочерними (вложениями).
    Возвращает (путь к parents_consolidated.txt, путь к children_consolidated.txt, кол-во обработанных файлов).
    """
    if not input_dir or not os.path.isdir(input_dir):
        raise ValueError("Выбранная директория не существует или не является папкой.")

    txt_files = [os.path.join(input_dir, f) for f in os.listdir(input_dir) if f.lower().endswith('.txt')]

    # Исключаем файлы результатов, если они уже были созданы в этой же папке
    parents_out_name = "parents_consolidated.txt"
    children_out_name = "children_consolidated.txt"

    txt_files = [f for f in txt_files if os.path.basename(f) not in (parents_out_name, children_out_name)]

    if not txt_files:
        raise ValueError("В выбранной папке не найдено текстовых файлов (.txt) для обработки.")

    all_parents = []
    all_children = []

    for filepath in txt_files:
        lines = read_codes(filepath)
        if not lines:
            continue

        # Первая строка — родительский код
        all_parents.append(lines[0])
        # Последующие строки — дочерние коды
        if len(lines) > 1:
            all_children.extend(lines[1:])

    # Запись результатов в ту же папку
    parents_file_path = os.path.join(input_dir, parents_out_name)
    children_file_path = os.path.join(input_dir, children_out_name)

    with open(parents_file_path, 'w', encoding='utf-8', newline='\n') as pf:
        for p in all_parents:
            pf.write(p + '\n')

    with open(children_file_path, 'w', encoding='utf-8', newline='\n') as cf:
        for c in all_children:
            cf.write(c + '\n')

    return parents_file_path, children_file_path, len(txt_files)


# -----------------------------------------------------------------------------
# ИНТЕРФЕЙС TKINTER
# -----------------------------------------------------------------------------

class VirtualDisaggregationApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Виртуальная деагрегационная утилита")
        self.root.geometry("600x350")
        self.root.resizable(True, True)

        self.input_dir = ""

        self.create_widgets()

    def create_widgets(self):
        tk, filedialog, messagebox, ttk = get_tkinter()

        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.pack(fill="both", expand=True)

        # Описание
        desc_label = ttk.Label(
            main_frame,
            text="Данная утилита позволяет объединить отдельные файлы наборов обратно в два файла:\n"
                 "- parents_consolidated.txt (все коды наборов)\n"
                 "- children_consolidated.txt (все коды вложений)\n\n"
                 "Выберите папку, содержащую файлы наборов (.txt).",
            justify="left",
            wraplength=550
        )
        desc_label.pack(fill="x", pady=10)

        # Выбор директории
        dir_lf = ttk.LabelFrame(main_frame, text=" Папка с файлами наборов ", padding="15")
        dir_lf.pack(fill="x", pady=10)

        self.dir_btn = ttk.Button(dir_lf, text="Выбрать папку...", command=self.select_directory)
        self.dir_btn.pack(side="left", padx=5)

        self.dir_label = ttk.Label(dir_lf, text="Папка не выбрана", wraplength=400, foreground="gray")
        self.dir_label.pack(side="left", padx=5, fill="x", expand=True)

        # Кнопка запуска
        self.run_btn = ttk.Button(
            main_frame,
            text="Запустить деагрегацию",
            command=self.run_disaggregation,
            style="Accent.TButton"
        )
        self.run_btn.pack(fill="x", pady=15)

        # Настройка стиля кнопки
        style = ttk.Style()
        style.configure("Accent.TButton", font=("Arial", 11, "bold"))

    def select_directory(self):
        tk, filedialog, messagebox, ttk = get_tkinter()
        dirpath = filedialog.askdirectory(title="Выберите папку с файлами наборов")
        if dirpath:
            self.input_dir = dirpath
            self.dir_label.config(text=dirpath, foreground="black")

    def run_disaggregation(self):
        tk, filedialog, messagebox, ttk = get_tkinter()
        try:
            parents_file, children_file, file_count = perform_disaggregation(self.input_dir)

            messagebox.showinfo(
                "Успех",
                f"Деагрегация успешно завершена!\n"
                f"Обработано файлов: {file_count}\n\n"
                f"Созданы файлы:\n"
                f"- {os.path.basename(parents_file)}\n"
                f"- {os.path.basename(children_file)}\n\n"
                f"В папке:\n{self.input_dir}"
            )
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            messagebox.showerror(
                "Ошибка при деагрегации",
                f"Произошла ошибка во время деагрегации:\n\n{str(e)}\n\nПодробности:\n{tb}"
            )


def main():
    try:
        tk, filedialog, messagebox, ttk = get_tkinter()
    except ImportError:
        # headless-режим
        print("Интерфейс Tkinter не поддерживается или отсутствует.")
        sys.exit(1)

    root = tk.Tk()
    app = VirtualDisaggregationApp(root)

    # Глобальный перехват исключений
    def show_error(self, *args):
        import traceback
        err = traceback.format_exception(*args)
        messagebox.showerror("Критическая ошибка", f"Произошло необработанное исключение:\n\n{''.join(err)}")

    tk.Tk.report_callback_exception = show_error

    root.mainloop()


if __name__ == "__main__":
    main()
