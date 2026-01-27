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
            for k, v in defaults.items():
                if k not in cfg:
                    cfg[k] = v
            return cfg
    except:
        return defaults

def save_config(cfg):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)

class App:
    def __init__(self):
        self.config = load_config()
        self.lang = None
        self.state = State(self.config["box_size"])
        self.paused = False
        self.boxes_since_save = 0
        self.duplicates = DuplicateChecker(self.config["db_path"])
        self.errors = ErrorLog()
        self.root = tk.Tk()
        self.root.title(APP_NAME)
        self.root.geometry("720x560")
        self.root.resizable(False, False)
        self.show_language_screen()

    def clear(self):
        for w in self.root.winfo_children(): w.destroy()

    def translate_layout(self, text):
        return "".join([LAYOUT_MAP.get(c, c) for c in text])

    def sanitize_input(self, text):
        return "".join([c for c in text if ord(c) < 128])

    def show_language_screen(self):
        self.clear(); frame = tk.Frame(self.root); frame.pack(expand=True)
        tk.Button(self.root, text="⚙", command=self.admin_login).place(x=680, y=10, width=30, height=30)
        tk.Label(frame, text="Выберите язык / Select language", font=("Arial", 18)).pack(pady=30)
        for key in TEXT:
            tk.Button(frame, text=TEXT[key]["lang_name"], font=("Arial", 14), width=28, height=2,
                      command=lambda l=key: self.set_language(l)).pack(pady=10)

    def set_language(self, lang): self.lang = lang; self.show_shift_form()

    def admin_login(self):
        win = tk.Toplevel(self.root); win.title("Вход"); win.geometry("320x180")
        tk.Label(win, text="Введите пароль").pack(pady=15)
        entry = tk.Entry(win, show="*"); entry.pack()
        def check():
            if entry.get() == ADMIN_PASSWORD: win.destroy(); self.admin_panel()
            else: messagebox.showerror("Ошибка", "Неверный пароль")
        tk.Button(win, text="Войти", command=check).pack(pady=20)

    def admin_panel(self):
        win = tk.Toplevel(self.root); win.title("Админка"); win.geometry("600x720")
        def block(title, value, enabled, row):
            tk.Label(win, text=title).grid(row=row, column=0, sticky="w", padx=10, pady=5)
            e = tk.Entry(win, width=30); e.insert(0, str(value)); e.grid(row=row, column=1)
            if enabled is not None:
                v = tk.BooleanVar(value=enabled); tk.Checkbutton(win, variable=v).grid(row=row, column=2)
                return e, v
            return e
        row = 0; tk.Label(win, text="Настройки системы", font=("Arial", 12, "bold")).grid(row=row, column=0, columnspan=3, pady=10)
        row += 1; box_entry = tk.Entry(win, width=10); box_entry.insert(0, str(self.config["box_size"])); box_entry.grid(row=row, column=1, sticky="w")
        tk.Label(win, text="Размер короба").grid(row=row, column=0, sticky="w", padx=10)
        row += 1; tin_e = block("ИНН", self.config["lp_tin"], None, row)
        row += 1; db_e = block("База данных", self.config["db_path"], None, row)
        row += 1; gtin_e, gtin_v = block("GTIN", self.config["gtin"], self.config["gtin_enabled"], row)
        row += 1; prod_e, prod_v = block("Название", self.config["product_name"], self.config["product_enabled"], row)
        row += 1; tnved_e, tnved_v = block("ТН ВЭД", self.config["tnved"], self.config["tnved_enabled"], row)
        row += 1; ds_e, ds_v = block("Номер ДС", self.config["ds_number"], self.config["ds_enabled"], row)
        row += 1; tk.Label(win, text="Telegram", font=("Arial", 12, "bold")).grid(row=row, column=0, columnspan=3, pady=10)
        row += 1; tg_token_e = block("Token", self.config["tg_token"], None, row)
        row += 1; tg_chat_e = block("Chat ID", self.config["tg_chat_id"], None, row)
        def save():
            self.config.update({"box_size": int(box_entry.get()), "lp_tin": tin_e.get().strip(), "db_path": db_e.get().strip(), "gtin": gtin_e.get().strip(), "gtin_enabled": gtin_v.get(), "product_name": prod_e.get().strip(), "product_enabled": prod_v.get(), "tnved": tnved_e.get().strip(), "tnved_enabled": tnved_v.get(), "ds_number": ds_e.get().strip(), "ds_enabled": ds_v.get(), "tg_token": tg_token_e.get().strip(), "tg_chat_id": tg_chat_e.get().strip()})
            save_config(self.config); self.state.reset(self.config["box_size"]); self.duplicates = DuplicateChecker(self.config["db_path"]); win.destroy()
        row += 1; tk.Button(win, text="Сохранить", command=save, bg="#4CAF50", fg="white").grid(row=row, column=1, pady=20)

    def show_shift_form(self):
        self.clear(); t = TEXT[self.lang]; frame = tk.Frame(self.root); frame.pack(expand=True)
        self.entry_date = tk.Entry(frame, width=30, font=("Arial", 14), justify="center"); self.entry_date.insert(0, datetime.now().strftime("%d.%m.%Y")); self.entry_date.pack(pady=5)
        tk.Label(frame, text=t["date"]).pack(); self.entry_wp = tk.Entry(frame, width=30, font=("Arial", 14)); self.entry_wp.pack(pady=5)
        tk.Label(frame, text=t["workplace"]).pack(); self.entry_name = tk.Entry(frame, width=30, font=("Arial", 14)); self.entry_name.pack(pady=5)
        tk.Label(frame, text=t["name"]).pack(); tk.Button(frame, text=t["start"], font=("Arial", 16), command=self.start_shift).pack(pady=30)

    def start_shift(self):
        self.shift_info = {"date": self.entry_date.get(), "workplace": self.entry_wp.get(), "name": self.entry_name.get()}
        self.state.reset(self.config["box_size"]); self.show_scan_screen()

    def show_scan_screen(self):
        self.clear(); t = TEXT[self.lang]
        self.info = tk.Label(self.root, font=("Arial", 16)); self.info.pack(pady=25)
        self.last = tk.Entry(self.root, state="readonly", width=60, font=("Arial", 14), justify="center"); self.last.pack(pady=15)
        self.scan_entry = tk.Entry(self.root); self.scan_entry.place(x=-100, y=-100); self.scan_entry.focus_set(); self.scan_entry.bind("<Return>", self.on_scan)
        self.root.bind("<Button-1>", lambda e: self.scan_entry.focus_set())
        btn = tk.Frame(self.root); btn.pack(side="bottom", pady=20)
        tk.Button(btn, text=t["pause"], command=self.pause).grid(row=0, column=0, padx=10)
        tk.Button(btn, text=t["save"], command=self.save_now).grid(row=0, column=1, padx=10)
        tk.Button(btn, text=t["end_shift"], command=self.end_shift).grid(row=0, column=2, padx=10)
        self.update_info()

    def pause(self): self.paused = True; messagebox.askokcancel("Пауза", "Продолжить?"); self.paused = False; self.scan_entry.focus_set()
    def save_now(self): self.perform_save(); messagebox.showinfo("Успех", "Сохранено")
    def end_shift(self):
        if self.state.in_box != 0: messagebox.showwarning("Ошибка", "Коробка не закрыта"); return
        self.send_to_telegram(self.perform_save()); self.show_language_screen()

    def on_scan(self, event):
        if self.paused: return
        raw = self.sanitize_input(self.translate_layout(self.scan_entry.get().strip()))
        self.scan_entry.delete(0, tk.END)
        if not raw: return
        if self.state.wait_sscc:
            if not raw.startswith("00") or not raw.isdigit(): messagebox.showerror("Ошибка", "Неверный SSCC"); return
            try:
                self.duplicates.check_sscc(raw); self.state.scan_sscc(raw)
                self.boxes_since_save += 1
                if self.boxes_since_save >= 30: self.perform_save(); self.boxes_since_save = 0
                self.show_last(f"Коробка №{self.state.box-1} ЗАКРЫТА. Ждем товары для №{self.state.box}"); self.update_info()
            except Exception as e: messagebox.showerror("Ошибка", str(e))
        else:
            try:
                parsed = parse_gs1(raw)
                if self.config["gtin_enabled"] and parsed["gtin"] != self.config["gtin"]: raise Exception("Неверный GTIN")
                self.duplicates.check(parsed["clean"]); self.state.scan_unit(parsed)
                self.show_last(parsed["raw"]); self.update_info()
            except Exception as e: messagebox.showerror("Ошибка", str(e))
        self.scan_entry.focus_set()

    def perform_save(self):
        summary = self.state.get_shift_summary()
        if not summary["data"]: return []
        ts = summary["start_time"].strftime("%Y%m%d_%H%M%S"); os.makedirs("output", exist_ok=True)
        base = f"output/смена_{self.shift_info['workplace']}_{ts}"
        with open(f"{base}.txt", "w", encoding="utf-8") as f: f.write(self.generate_xml_content(summary["data"]))
        self.generate_excel_production(summary["data"], f"{base}.xlsx"); return [f"{base}.txt", f"{base}.xlsx"]

    def generate_xml_content(self, boxes):
        xml = '<?xml version="1.0" encoding="UTF-8"?>\n<unit_pack>\n'
        for sscc, units in boxes:
            xml += f'<pack_content><pack_code>{sscc}</pack_code>\n'
            for u in units: xml += f'<cis>{u["clean"]}</cis>\n'
            xml += '</pack_content>\n'
        return xml + '</unit_pack>'

    def generate_excel_production(self, boxes, filename):
        wb = openpyxl.Workbook(); ws = wb.active
        ws.append(["Продукт", "КМ", "GTIN", "ТН ВЭД", "ДС", "Дата"])
        for sscc, units in boxes:
            for u in units:
                ws.append([self.config["product_name"] if self.config["product_enabled"] else "", u["clean"], u["gtin"], self.config["tnved"] if self.config["tnved_enabled"] else "", self.config["ds_number"], self.shift_info["date"]])
        wb.save(filename)

    def send_to_telegram(self, files):
        t, c = self.config.get("tg_token"), self.config.get("tg_chat_id")
        if t and c:
            try:
                for p in files:
                    with open(p, "rb") as f: requests.post(f"https://api.telegram.org/bot{t}/sendDocument", data={"chat_id": c}, files={"document": f})
            except: pass

    def show_last(self, text):
        self.last.config(state="normal"); self.last.delete(0, tk.END); self.last.insert(0, text); self.last.config(state="readonly")

    def update_info(self):
        if self.state.wait_sscc: txt = "Ожидание SSCC..."
        else: txt = f"Коробка: {self.state.box}\nОтсканировано: {self.state.in_box} / {self.state.box_size}"
        self.info.config(text=txt)

def run():
    App().root.mainloop()

if __name__ == "__main__":
    run()
