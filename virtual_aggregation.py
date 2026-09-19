"""
Скрипт для виртуальной агрегации кодов маркировки.

Инструкция по сборке в exe:
1. Установите PyInstaller (если еще не установлен):
   pip install pyinstaller
2. Выполните команду для сборки standalone-файла:
   pyinstaller --noconsole --onefile virtual_aggregation.py
3. Готовый exe-файл появится в папке dist/
"""

import os
import sys
import re
from datetime import datetime

# Определение базовых функций без жесткой привязки к Tkinter на этапе импорта
# для поддержки headless-тестирования.


def read_codes(file_path):
    """
    Считывает строки кодов из текстового файла.
    Пробует распространенные кодировки (utf-8-sig, utf-16, utf-8, cp1251).
    Возвращает список непустых очищенных от внешних пробелов строк.
    """
    encodings = ['utf-8-sig', 'utf-16', 'utf-8', 'cp1251']
    content = None
    for enc in encodings:
        try:
            with open(file_path, 'r', encoding=enc) as f:
                content = f.read()
            break
        except (UnicodeError, LookupError):
            continue

    if content is None:
        raise ValueError(f"Не удалось прочитать файл {file_path}. Проверьте кодировку файла.")

    lines = [line.strip() for line in content.splitlines() if line.strip()]
    return lines


def sanitize_filename(name):
    """
    Очищает строку для использования в качестве имени файла.
    Заменяет недопустимые для имен файлов символы на знак подчеркивания.
    """
    # Запрещенные символы в файловых системах Windows/Linux: \ / : * ? " < > |
    cleaned = re.sub(r'[\\/:*?"<>|]', '_', name)
    # Удаляем лишние пробелы и точки в конце
    cleaned = cleaned.strip('. ')
    if not cleaned:
        cleaned = "set_code"
    return cleaned


def perform_aggregation(parent_file, child_files, items_per_parent, output_dir=None, confirm_callback=None):
    """
    Выполняет виртуальную агрегацию:
    - parent_file: путь к файлу с кодами наборов (родители)
    - child_files: список путей к файлам с кодами вложений (дети)
    - items_per_parent: количество вложений в один набор (int > 0)
    - output_dir: кастомный путь для сохранения результатов (если None, создается timestamp-папка)
    - confirm_callback: функция обратного вызова при нехватке кодов вложений. Принимает (actual_sets, required_sets).
                        Возвращает True для продолжения или False для отмены.

    Возвращает словарь с результатами операции.
    """
    if items_per_parent <= 0:
        raise ValueError("Количество вложений должно быть больше 0.")

    if not parent_file or not os.path.exists(parent_file):
        raise ValueError("Файл кодов наборов не выбран или не существует.")

    if not child_files:
        raise ValueError("Не выбраны файлы кодов вложений.")

    parent_codes = read_codes(parent_file)
    if not parent_codes:
        raise ValueError("Файл кодов наборов пуст.")

    child_codes = []
    for c_file in child_files:
        if os.path.exists(c_file):
            child_codes.extend(read_codes(c_file))

    if not child_codes:
        raise ValueError("Файлы кодов вложений не содержат кодов.")

    total_parents = len(parent_codes)
    total_children = len(child_codes)
    max_possible_sets = total_children // items_per_parent

    if max_possible_sets < total_parents:
        if confirm_callback is not None:
            approved = confirm_callback(max_possible_sets, total_parents)
            if not approved:
                return {"status": "cancelled", "message": "Операция отменена пользователем."}

    actual_sets = min(total_parents, max_possible_sets)
    if actual_sets == 0:
        raise ValueError(
            f"Недостаточно кодов вложений ({total_children}) для формирования хотя бы одного набора "
            f"по {items_per_parent} шт."
        )

    if output_dir is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = f"aggregation_results_{timestamp}"

    os.makedirs(output_dir, exist_ok=True)

    used_filenames = {}
    created_files = []

    child_idx = 0
    for i in range(actual_sets):
        parent_code = parent_codes[i]
        set_children = child_codes[child_idx: child_idx + items_per_parent]
        child_idx += items_per_parent

        base_filename = sanitize_filename(parent_code)
        # Обработка возможного дублирования имен файлов
        if base_filename in used_filenames:
            used_filenames[base_filename] += 1
            filename = f"{base_filename}_{used_filenames[base_filename]}.txt"
        else:
            used_filenames[base_filename] = 0
            filename = f"{base_filename}.txt"

        file_path = os.path.join(output_dir, filename)

        # Формирование содержимого: первая строка - код набора, далее - коды вложений
        lines = [parent_code] + set_children
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines) + '\n')

        created_files.append(file_path)

    return {
        "status": "success",
        "output_dir": os.path.abspath(output_dir),
        "created_sets": actual_sets,
        "used_children": actual_sets * items_per_parent,
        "total_parents": total_parents,
        "total_children": total_children,
        "created_files": created_files
    }


def launch_gui():
    """
    Запускает графический интерфейс Tkinter.
    """
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk

    class VirtualAggregationGUI:
        def __init__(self, root):
            self.root = root
            self.root.title("Виртуальная агрегация наборов")
            self.root.geometry("640x520")
            self.root.resizable(True, True)

            self.parent_file = ""
            self.child_files = []

            self._build_ui()

        def _build_ui(self):
            padding = {'padx': 10, 'pady': 5}

            # 1. Выбор файла наборов (родительский файл)
            frame_parent = ttk.LabelFrame(self.root, text="1. Коды наборов (Родительский файл)")
            frame_parent.pack(fill="x", **padding)

            self.lbl_parent = ttk.Label(frame_parent, text="Файл не выбран", wraplength=450)
            self.lbl_parent.pack(side="left", fill="x", expand=True, padx=5, pady=5)

            btn_parent = ttk.Button(frame_parent, text="Обзор...", command=self.select_parent_file)
            btn_parent.pack(side="right", padx=5, pady=5)

            # 2. Выбор количества вложений в набор
            frame_count = ttk.LabelFrame(self.root, text="2. Количество вложений на 1 набор")
            frame_count.pack(fill="x", **padding)

            ttk.Label(frame_count, text="Вложений в наборе (шт.):").pack(side="left", padx=5, pady=5)
            self.spin_count = ttk.Spinbox(frame_count, from_=1, to=1000, width=10)
            self.spin_count.set(10)
            self.spin_count.pack(side="left", padx=5, pady=5)

            # 3. Выбор файлов вложений (дочерние файлы)
            frame_children = ttk.LabelFrame(self.root, text="3. Коды вложений (Файлы содержимого)")
            frame_children.pack(fill="both", expand=True, **padding)

            btn_frame_child = ttk.Frame(frame_children)
            btn_frame_child.pack(fill="x", padx=5, pady=2)

            btn_child = ttk.Button(btn_frame_child, text="Добавить файлы...", command=self.select_child_files)
            btn_child.pack(side="left", padx=2)

            btn_clear_child = ttk.Button(btn_frame_child, text="Очистить список", command=self.clear_child_files)
            btn_clear_child.pack(side="left", padx=2)

            self.lst_children = tk.Listbox(frame_children, height=6)
            self.lst_children.pack(fill="both", expand=True, padx=5, pady=5)

            # Статус информации о количестве кодов
            self.lbl_info = ttk.Label(self.root, text="Готово к работе", font=("Arial", 9, "italic"))
            self.lbl_info.pack(fill="x", padx=10, pady=2)

            # 4. Кнопка запуска агрегации
            btn_run = ttk.Button(self.root, text="Запустить агрегацию", command=self.run_aggregation)
            btn_run.pack(pady=10)

        def select_parent_file(self):
            path = filedialog.askopenfilename(
                title="Выберите файл с кодами наборов",
                filetypes=[("Текстовые файлы (*.txt)", "*.txt"), ("Все файлы (*.*)", "*.*")]
            )
            if path:
                self.parent_file = path
                self.lbl_parent.config(text=os.path.basename(path))
                self.update_info()

        def select_child_files(self):
            paths = filedialog.askopenfilenames(
                title="Выберите файлы с кодами вложений",
                filetypes=[("Текстовые файлы (*.txt)", "*.txt"), ("Все файлы (*.*)", "*.*")]
            )
            if paths:
                for p in paths:
                    if p not in self.child_files:
                        self.child_files.append(p)
                        self.lst_children.insert(tk.END, os.path.basename(p))
                self.update_info()

        def clear_child_files(self):
            self.child_files.clear()
            self.lst_children.delete(0, tk.END)
            self.update_info()

        def update_info(self):
            parents_cnt = 0
            children_cnt = 0

            if self.parent_file and os.path.exists(self.parent_file):
                try:
                    parents_cnt = len(read_codes(self.parent_file))
                except Exception:
                    parents_cnt = 0

            for cf in self.child_files:
                if os.path.exists(cf):
                    try:
                        children_cnt += len(read_codes(cf))
                    except Exception:
                        pass

            try:
                items_per = int(self.spin_count.get())
            except ValueError:
                items_per = 0

            possible_sets = (children_cnt // items_per) if items_per > 0 else 0
            self.lbl_info.config(
                text=f"Кодов наборов: {parents_cnt} | Кодов вложений: {children_cnt} | "
                     f"Возможно сформировать наборов: {possible_sets}"
            )

        def run_aggregation(self):
            try:
                items_per_parent = int(self.spin_count.get())
            except ValueError:
                messagebox.showerror("Ошибка", "Введите корректное число вложений на набор.")
                return

            def on_confirm(actual, required):
                msg = (f"Вложений недостаточно для всех {required} наборов.\n"
                       f"Будет создано {actual} наборов.\n\nПродолжить?")
                return messagebox.askyesno("Подтверждение", msg)

            try:
                res = perform_aggregation(
                    parent_file=self.parent_file,
                    child_files=self.child_files,
                    items_per_parent=items_per_parent,
                    confirm_callback=on_confirm
                )

                if res.get("status") == "cancelled":
                    messagebox.showinfo("Отмена", "Операция отменена пользователем.")
                    return

                msg = (f"Успешно создано наборов: {res['created_sets']}\n"
                       f"Использовано вложений: {res['used_children']}\n"
                       f"Результаты сохранены в папку:\n{res['output_dir']}")
                messagebox.showinfo("Успех", msg)

            except Exception as e:
                messagebox.showerror("Ошибка", str(e))

    root = tk.Tk()
    app = VirtualAggregationGUI(root)
    root.mainloop()


if __name__ == "__main__":
    try:
        launch_gui()
    except Exception as e:
        import traceback
        error_msg = f"Произошла фатальная ошибка:\n{e}\n\n{traceback.format_exc()}"
        print(error_msg, file=sys.stderr)
        try:
            import tkinter as tk
            from tkinter import messagebox
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror("Фатальная ошибка", error_msg)
        except Exception:
            pass
