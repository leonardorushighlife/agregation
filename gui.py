import tkinter as tk
from tkinter import messagebox
import json
import os
from datetime import datetime
import requests
import openpyxl

from i18n import TEXT
from state import State
from gs1 import parse_gs1
from duplicate import DuplicateChecker
from errors import ErrorLog


APP_NAME = "aggregation_LEONID"
CONFIG_FILE = "config_local.json"
ADMIN_PASSWORD = "28091987"

# Карта для перевода русской раскладки в английскую
LAYOUT_MAP = {
    'й': 'q', 'ц': 'w', 'у': 'e', 'к': 'r', 'е': 't', 'н': 'y', 'г': 'u', 'ш': 'i', 'щ': 'o', 'з': 'p', 'х': '[', 'ъ': ']',
    'ф': 'a', 'ы': 's', 'в': 'd', 'а': 'f', 'п': 'g', 'р': 'h', 'о': 'j', 'л': 'k', 'д': 'l', 'ж': ';', 'э': "'",
    'я': 'z', 'ч': 'x', 'с': 'c', 'м': 'v', 'и': 'b', 'т': 'n', 'ь': 'm', 'б': ',', 'ю': '.',
    'Й': 'Q', 'Ц': 'W', 'У': 'E', 'К': 'R', 'Е': 'T', 'Н': 'Y', 'Г': 'U', 'Ш': 'I', 'Щ': 'O', 'З': 'P', 'Х': '{', 'Ъ': '}',
    'Ф': 'A', 'Ы': 'S', 'В': 'D', 'А': 'F', 'П': 'G', 'Р': 'H', 'О': 'J', 'Л': 'K', 'Д': 'L', 'Ж': ':', 'Э': '"',
    'Я': 'Z', 'Ч': 'X', 'С': 'C', 'М': 'V', 'И': 'B', 'Т': 'N', 'Ь': 'M', 'Б': '<', 'Ю': '>'
}

# -------------------------------------------------
# CONFIG
# -------------------------------------------------

def load_config():
    defaults = {
        "first_run": datetime.now().strftime("%Y-%m-%d"),
        "limit_enabled": True,
        "box_size": 24,
        "lp_tin": "7777777777",
        "gtin": "",
        "gtin_enabled": False,
        "product_name": "",
        "product_enabled": False,
        "tnved": "",
        "tnved_enabled": False,
        "ds_number": "",
        "ds_enabled": False,
        "tg_token": "",
        "tg_chat_id": "",
        "db_path": "data/duplicates.db"
    }

    if not os.path.exists(CONFIG_FILE):
        save_config(defaults)
        return defaults

    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            cfg = json.load(f)
            # Добавляем недостающие поля
            for k, v in defaults.items():
                if k not in cfg:
                    cfg[k] = v
            return cfg
    except:
        return defaults


def save_config(cfg):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)


def days_passed(date_str):
    try:
        start = datetime.strptime(date_str, "%Y-%m-%d")
        return (datetime.now() - start).days
    except:
        return 0


# -------------------------------------------------
# MAIN APP
# -------------------------------------------------

class App:
    def __init__(self):
        self.config = load_config()

        if self.config["limit_enabled"]:
            if days_passed(self.config["first_run"]) >= 180:
                self.config["box_size"] = 5
                save_config(self.config)

        self.lang = None
        self.state = State(self.config["box_size"])
        self.paused = False

        self.duplicates = DuplicateChecker(self.config["db_path"])
        self.errors = ErrorLog()

        self.root = tk.Tk()
        self.root.title(APP_NAME)
        self.root.geometry("720x560")
        self.root.resizable(False, False)

        self.show_language_screen()

    # -------------------------------------------------
    def clear(self):
        for w in self.root.winfo_children():
            w.destroy()

    def translate_layout(self, text):
        return "".join([LAYOUT_MAP.get(c, c) for c in text])

    # -------------------------------------------------
    # LANGUAGE + ADMIN
    # -------------------------------------------------

    def show_language_screen(self):
        self.clear()

        frame = tk.Frame(self.root)
        frame.pack(expand=True)

        tk.Button(
            self.root,
            text="⚙",
            command=self.admin_login
        ).place(x=680, y=10, width=30, height=30)

        tk.Label(frame, text="Select language", font=("Arial", 18)).pack(pady=30)

        for key in TEXT:
            tk.Button(
                frame,
                text=TEXT[key]["lang_name"],
                font=("Arial", 14),
                width=28,
                height=2,
                command=lambda l=key: self.set_language(l)
            ).pack(pady=10)

    def set_language(self, lang):
        self.lang = lang
        self.show_shift_form()

    # -------------------------------------------------
    # ADMIN
    # -------------------------------------------------

    def admin_login(self):
        win = tk.Toplevel(self.root)
        win.title("Admin")
        win.geometry("320x180")
        win.resizable(False, False)

        tk.Label(win, text="Password").pack(pady=15)
        entry = tk.Entry(win, show="*")
        entry.pack()

        def check():
            if entry.get() == ADMIN_PASSWORD:
                win.destroy()
                self.admin_panel()
            else:
                messagebox.showerror("Error", "Wrong password")

        tk.Button(win, text="OK", command=check).pack(pady=20)

    def admin_panel(self):
        win = tk.Toplevel(self.root)
        win.title("Admin panel")
        win.geometry("600x680")
        win.resizable(False, False)

        def block(title, value, enabled, row):
            tk.Label(win, text=title, anchor="w").grid(row=row, column=0, sticky="w", padx=10, pady=5)
            e = tk.Entry(win, width=30)
            e.insert(0, str(value))
            e.grid(row=row, column=1, padx=5)
            if enabled is not None:
                v = tk.BooleanVar(value=enabled)
                tk.Checkbutton(win, variable=v).grid(row=row, column=2)
                return e, v
            return e

        row = 0
        tk.Label(win, text="Settings").grid(row=row, column=0, padx=10, pady=5, sticky="w")
        row += 1

        box_entry = tk.Entry(win, width=10)
        box_entry.insert(0, str(self.config["box_size"]))
        box_entry.grid(row=row, column=1, sticky="w")
        tk.Label(win, text="Box size (5–200)").grid(row=row, column=0, padx=10, pady=5, sticky="w")
        limit_var = tk.BooleanVar(value=self.config["limit_enabled"])
        tk.Checkbutton(win, text="Limit", variable=limit_var).grid(row=row, column=2)

        row += 1
        tin_e = block("LP TIN", self.config["lp_tin"], None, row)
        row += 1
        db_e = block("DB Path", self.config["db_path"], None, row)
        row += 1
        gtin_e, gtin_v = block("GTIN", self.config["gtin"], self.config["gtin_enabled"], row)
        row += 1
        prod_e, prod_v = block("Product name", self.config["product_name"], self.config["product_enabled"], row)
        row += 1
        tnved_e, tnved_v = block("TN VED", self.config["tnved"], self.config["tnved_enabled"], row)
        row += 1
        ds_e, ds_v = block("DS number", self.config["ds_number"], self.config["ds_enabled"], row)
        row += 1

        tk.Label(win, text="Telegram").grid(row=row, column=0, padx=10, pady=10, sticky="w")
        row += 1
        tg_token_e = block("Bot Token", self.config["tg_token"], None, row)
        row += 1
        tg_chat_e = block("Chat ID", self.config["tg_chat_id"], None, row)

        def save():
            try:
                val = int(box_entry.get())
                if not 5 <= val <= 200:
                    raise ValueError
            except:
                messagebox.showerror("Error", "Invalid box size")
                return

            self.config.update({
                "box_size": val,
                "limit_enabled": limit_var.get(),
                "lp_tin": tin_e.get().strip(),
                "db_path": db_e.get().strip(),
                "gtin": gtin_e.get().strip(),
                "gtin_enabled": gtin_v.get(),
                "product_name": prod_e.get().strip(),
                "product_enabled": prod_v.get(),
                "tnved": tnved_e.get().strip(),
                "tnved_enabled": tnved_v.get(),
                "ds_number": ds_e.get().strip(),
                "ds_enabled": ds_v.get(),
                "tg_token": tg_token_e.get().strip(),
                "tg_chat_id": tg_chat_e.get().strip()
            })

            save_config(self.config)
            self.state.reset(val)
            self.duplicates = DuplicateChecker(self.config["db_path"]) # Re-init DB
            messagebox.showinfo("OK", "Saved")
            win.destroy()

        row += 1
        tk.Button(win, text="Save", command=save, width=20, height=2).grid(row=row, column=1, pady=20)

    # -------------------------------------------------
    # SHIFT FORM
    # -------------------------------------------------

    def show_shift_form(self):
        self.clear()
        t = TEXT[self.lang]

        frame = tk.Frame(self.root)
        frame.pack(expand=True)

        tk.Label(frame, text=t["precheck"], wraplength=640,
                 font=("Arial", 14), justify="center").pack(pady=20)

        self.entry_date = tk.Entry(frame, width=30, font=("Arial", 14), justify="center")
        self.entry_date.insert(0, datetime.now().strftime("%Y-%m-%d"))
        self.entry_date.pack(pady=5)
        tk.Label(frame, text=t["date"]).pack(pady=5)

        self.entry_wp = tk.Entry(frame, width=30, font=("Arial", 14), justify="center")
        self.entry_wp.pack(pady=5)
        tk.Label(frame, text=t["workplace"]).pack(pady=5)

        self.entry_name = tk.Entry(frame, width=30, font=("Arial", 14), justify="center")
        self.entry_name.pack(pady=5)
        tk.Label(frame, text=t["name"]).pack(pady=5)

        tk.Button(frame, text=t["start"], font=("Arial", 16),
                  width=26, height=2, command=self.start_shift).pack(pady=30)

    def start_shift(self):
        t = TEXT[self.lang]
        if not self.entry_date.get() or not self.entry_wp.get() or not self.entry_name.get():
            messagebox.showerror(t["error"], t["error_fill"])
            return

        self.shift_info = {
            "date": self.entry_date.get(),
            "workplace": self.entry_wp.get(),
            "name": self.entry_name.get()
        }
        self.state.reset(self.config["box_size"])
        self.show_scan_screen()

    # -------------------------------------------------
    # SCAN SCREEN
    # -------------------------------------------------

    def show_scan_screen(self):
        self.clear()
        t = TEXT[self.lang]

        self.info = tk.Label(self.root, font=("Arial", 16), justify="center")
        self.info.pack(pady=25)

        self.last = tk.Entry(
            self.root,
            state="readonly",
            width=60,
            font=("Arial", 14),
            justify="center"
        )
        self.last.pack(pady=15)

        # 🔑 hidden input for scanner
        self.scan_entry = tk.Entry(self.root)
        self.scan_entry.place(x=-100, y=-100)
        self.scan_entry.focus_set()
        self.scan_entry.bind("<Return>", self.on_scan)
        # Prevent losing focus
        self.root.bind("<Button-1>", lambda e: self.scan_entry.focus_set())

        btn = tk.Frame(self.root)
        btn.pack(side="bottom", pady=20)

        tk.Button(btn, text=t["pause"], width=16, command=self.pause).grid(row=0, column=0, padx=10)
        tk.Button(btn, text=t["save"], width=16, command=self.save_now).grid(row=0, column=1, padx=10)
        tk.Button(btn, text=t["end_shift"], width=18, command=self.end_shift).grid(row=0, column=2, padx=10)

        self.update_info()

    # -------------------------------------------------
    # BUTTON ACTIONS
    # -------------------------------------------------

    def pause(self):
        t = TEXT[self.lang]
        self.paused = True
        if messagebox.askokcancel(t["pause"], t["resume"]):
            self.paused = False
            self.scan_entry.focus_set()

    def save_now(self):
        t = TEXT[self.lang]
        files = self.perform_save()
        if files:
            messagebox.showinfo("", t["saved"])

    def end_shift(self):
        t = TEXT[self.lang]
        if self.state.in_box != 0:
            messagebox.showwarning(t["error"], t["need_close_box"])
            return
        if messagebox.askokcancel("", t["confirm_end"]):
            files = self.perform_save()
            self.send_to_telegram(files)
            messagebox.showinfo("", t["sent"])
            self.show_language_screen()

    # -------------------------------------------------
    # SCAN HANDLER
    # -------------------------------------------------

    def on_scan(self, event):
        if self.paused:
            self.scan_entry.delete(0, tk.END)
            return

        t = TEXT[self.lang]
        raw = self.scan_entry.get().strip()
        self.scan_entry.delete(0, tk.END)

        if not raw:
            return

        # Перевод раскладки
        raw = self.translate_layout(raw)

        if self.state.wait_sscc:
            # Валидация SSCC: должен начинаться с 00 и иметь 20 цифр
            if not raw.startswith("00") or not raw.isdigit() or len(raw) < 18:
                err = "Неверный формат SSCC (должен начинаться с 00 и содержать 18-20 цифр)"
                self.errors.add(raw, err)
                messagebox.showerror(t["error"], err)
                return

            self.state.scan_sscc(raw)
            self.show_last(f"SSCC: {raw}")
            self.update_info(box_closed=True)
            return

        try:
            parsed = parse_gs1(raw)

            if self.config["gtin_enabled"]:
                if parsed["gtin"] != self.config["gtin"]:
                    raise Exception(f"GTIN {parsed['gtin']} не совпадает с настройками ({self.config['gtin']})")

            self.duplicates.check(parsed["clean"])

        except Exception as e:
            self.errors.add(raw, str(e))
            messagebox.showerror(t["error"], str(e))
            return

        self.state.scan_unit(parsed)
        self.show_last(parsed["raw"])
        self.update_info()

    # -------------------------------------------------
    # SAVE LOGIC
    # -------------------------------------------------

    def perform_save(self):
        summary = self.state.get_shift_summary()
        if not summary["data"]:
            return []

        timestamp = summary["start_time"].strftime("%Y%m%d_%H%M%S")
        base_name = f"shift_{self.shift_info['workplace']}_{timestamp}"

        os.makedirs("output", exist_ok=True)
        generated_paths = []

        # Сохранение TXT (XML)
        generated_paths.extend(self.save_files_split(summary, base_name, "txt"))

        # Сохранение Excel (XLSX)
        generated_paths.extend(self.save_files_split(summary, base_name, "xlsx"))

        return generated_paths

    def save_files_split(self, summary, base_name, extension):
        codes_per_file = 30000
        file_idx = 1
        current_codes_count = 0
        current_boxes = []
        paths = []

        def write_part(boxes, idx):
            filename = f"output/{base_name}_{idx}.{extension}"
            if extension == "txt":
                content = self.generate_xml_content(boxes)
                with open(filename, "w", encoding="utf-8") as f:
                    f.write(content)
            elif extension == "xlsx":
                self.generate_excel_file(boxes, filename)
            return filename

        for sscc, units in summary["data"]:
            if current_codes_count + len(units) > codes_per_file:
                paths.append(write_part(current_boxes, file_idx))
                file_idx += 1
                current_boxes = []
                current_codes_count = 0

            current_boxes.append((sscc, units))
            current_codes_count += len(units)

        if current_boxes:
            paths.append(write_part(current_boxes, file_idx))

        return paths

    def generate_xml_content(self, boxes):
        xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
        xml += '<unit_pack>\n'
        xml += '    <Document>\n'
        xml += '        <organisation>\n'
        xml += '            <id_info>\n'
        xml += f'                <LP_info LP_TIN="{self.config["lp_tin"]}" />\n'
        xml += '            </id_info>\n'
        xml += '        </organisation>\n\n'

        for sscc, units in boxes:
            xml += '        <pack_content>\n'
            xml += f'            <pack_code>{sscc}</pack_code>\n'
            for u in units:
                xml += f'            <cis>{u["clean"]}</cis>\n'
            xml += '        </pack_content>\n\n'

        xml += '    </Document>\n'
        xml += '</unit_pack>'
        return xml

    def generate_excel_file(self, boxes, filename):
        wb = openpyxl.Workbook()
        ws = wb.active
        # Только коды маркировки, один в строке, без криптохвоста
        for sscc, units in boxes:
            for u in units:
                ws.append([u['clean']])
        wb.save(filename)

    # -------------------------------------------------
    # TELEGRAM
    # -------------------------------------------------

    def send_to_telegram(self, files):
        token = self.config.get("tg_token")
        chat_id = self.config.get("tg_chat_id")
        if not token or not chat_id or not files:
            return

        summary = self.state.get_shift_summary()
        msg = (f"Смена завершена\n"
               f"Оператор: {self.shift_info['name']}\n"
               f"Рабочее место: {self.shift_info['workplace']}\n"
               f"Коробов: {summary['total_boxes']}\n"
               f"Кодов: {summary['total_codes']}")

        try:
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            requests.post(url, data={"chat_id": chat_id, "text": msg}, timeout=10)

            url_doc = f"https://api.telegram.org/bot{token}/sendDocument"
            for path in files:
                if os.path.exists(path):
                    with open(path, "rb") as f:
                        # Фильтруем только нужные расширения
                        if path.endswith((".txt", ".xlsx")):
                            requests.post(url_doc, data={"chat_id": chat_id}, files={"document": f}, timeout=10)
        except Exception as e:
            print(f"Telegram error: {e}")

    # -------------------------------------------------
    # UI HELPERS
    # -------------------------------------------------

    def show_last(self, text):
        self.last.config(state="normal")
        self.last.delete(0, tk.END)
        self.last.insert(0, text)
        self.last.config(state="readonly")

    def update_info(self, box_closed=False):
        t = TEXT[self.lang]

        if box_closed:
            txt = t["box_closed"]
        elif self.state.wait_sscc:
            txt = t["scan_sscc"]
        else:
            txt = f"{t['box']}: {self.state.box}\n{t['count']}: {self.state.in_box} / {self.state.box_size}"

        self.info.config(text=txt)


def run():
    App().root.mainloop()
