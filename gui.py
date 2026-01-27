import tkinter as tk
from tkinter import messagebox
import json
import os
import shutil
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
        "limit_enabled": True, "box_size": 24, "lp_tin": "7777777777",
        "gtin": "", "gtin_enabled": False,
        "product_name": "", "product_enabled": False,
        "tnved": "", "tnved_enabled": False,
        "ds_number": "", "ds_enabled": False,
        "tg_token": "", "tg_chat_id": "", "db_path": "data/duplicates.db",
        "is_server": False
    }
    if not os.path.exists(CONFIG_FILE): save_config(defaults); return defaults
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            cfg = json.load(f);
            for k, v in defaults.items():
                if k not in cfg: cfg[k] = v
            return cfg
    except: return defaults

def save_config(cfg):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f: json.dump(cfg, f, indent=2, ensure_ascii=False)

def days_passed(date_str):
    try: return (datetime.now() - datetime.strptime(date_str, "%Y-%m-%d")).days
    except: return 0

class App:
    def __init__(self):
        self.config = load_config()
        # Лимит безопасности
        if self.config.get("limit_enabled") and days_passed(self.config["first_run"]) >= 180:
            self.config["box_size"] = 1

        self.duplicates = DuplicateChecker(self.config["db_path"], is_server=self.config.get("is_server", False))
        self.state = State(self.config["box_size"])
        self.paused = False
        self.root = tk.Tk()
        self.root.title(APP_NAME); self.root.geometry("720x560"); self.root.resizable(False, False)

        self.show_language_screen()
        self.check_recovery()

    def check_recovery(self):
        data = self.duplicates.get_recovery_data()
        if data:
            if messagebox.askyesno("Восстановление", "Найдена незавершенная смена. Продолжить?"):
                recovered_boxes = []
                last_info = None
                for sscc, units_json, info_json in data:
                    recovered_boxes.append((sscc, json.loads(units_json)))
                    last_info = json.loads(info_json)
                self.shift_info = last_info; self.state.load_recovery(recovered_boxes); self.show_scan_screen()
            else: self.duplicates.clear_recovery()

    def clear(self):
        for w in self.root.winfo_children(): w.destroy()

    def translate_layout(self, text): return "".join([LAYOUT_MAP.get(c, c) for c in text])
    def sanitize_input(self, text): return "".join([c for c in text if ord(c) < 128])

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
        tk.Label(win, text="Пароль").pack(pady=15); entry = tk.Entry(win, show="*"); entry.pack()
        def check():
            if entry.get() == ADMIN_PASSWORD: win.destroy(); self.admin_panel()
            else: messagebox.showerror("Ошибка", "Неверно")
        tk.Button(win, text="Войти", command=check).pack(pady=20)

    def admin_panel(self):
        win = tk.Toplevel(self.root); win.title("Админ-панель"); win.geometry("600x720")
        def block(title, val, enabled, row):
            tk.Label(win, text=title).grid(row=row, column=0, sticky="w", padx=10, pady=5)
            e = tk.Entry(win, width=30); e.insert(0, str(val)); e.grid(row=row, column=1)
            if enabled is not None:
                v = tk.BooleanVar(value=enabled); tk.Checkbutton(win, variable=v).grid(row=row, column=2)
                return e, v
            return e
        row = 0; tk.Label(win, text="Основные настройки", font=("Arial", 12, "bold")).grid(row=row, column=0, pady=10)
        row += 1; box_e = block("Размер короба", self.config["box_size"], None, row); row += 1
        tin_e = block("ИНН (LP TIN)", self.config["lp_tin"], None, row); row += 1
        gtin_e, gtin_v = block("GTIN товара", self.config["gtin"], self.config["gtin_enabled"], row); row += 1
        prod_e, prod_v = block("Название продукта", self.config["product_name"], self.config["product_enabled"], row); row += 1
        tnved_e, tnved_v = block("ТН ВЭД", self.config["tnved"], self.config["tnved_enabled"], row); row += 1
        ds_e, ds_v = block("Номер ДС", self.config["ds_number"], self.config["ds_enabled"], row); row += 1

        tk.Label(win, text="Сеть и Telegram", font=("Arial", 12, "bold")).grid(row=row, column=0, pady=10)
        row += 1; srv_v = tk.BooleanVar(value=self.config.get("is_server", False))
        tk.Checkbutton(win, text="Использовать как сервер дубликатов", variable=srv_v).grid(row=row, column=1, sticky="w"); row += 1
        tg_t = block("TG Bot Token", self.config["tg_token"], None, row); row += 1
        tg_c = block("TG Chat ID", self.config["tg_chat_id"], None, row); row += 1

        def save():
            self.config.update({
                "box_size": int(box_e.get()), "lp_tin": tin_e.get(), "gtin": gtin_e.get(), "gtin_enabled": gtin_v.get(),
                "product_name": prod_e.get(), "product_enabled": prod_v.get(), "tnved": tnved_e.get(), "tnved_enabled": tnved_v.get(),
                "ds_number": ds_e.get(), "ds_enabled": ds_v.get(), "tg_token": tg_t.get(), "tg_chat_id": tg_c.get(),
                "is_server": srv_v.get()
            })
            save_config(self.config); messagebox.showinfo("Успех", "Настройки сохранены. Перезапустите программу."); win.destroy()
        tk.Button(win, text="Сохранить", command=save, bg="#4CAF50", fg="white", width=20, height=2).grid(row=row, column=1, pady=20)

    def show_shift_form(self):
        self.clear(); t = TEXT[self.lang]; frame = tk.Frame(self.root); frame.pack(expand=True)
        self.entry_date = tk.Entry(frame, width=30, font=("Arial", 14), justify="center"); self.entry_date.insert(0, datetime.now().strftime("%d.%m.%Y")); self.entry_date.pack(pady=5)

        vcmd = (self.root.register(lambda P: P == "" or P.isdigit()), '%P')
        self.entry_wp = tk.Entry(frame, width=30, font=("Arial", 14), justify="center", validate="key", validatecommand=vcmd); self.entry_wp.pack(pady=5)
        tk.Label(frame, text=t["workplace"]).pack()

        self.entry_name = tk.Entry(frame, width=30, font=("Arial", 14), justify="center"); self.entry_name.pack(pady=5)
        tk.Label(frame, text=t["name"]).pack()
        tk.Button(frame, text=t["start"], font=("Arial", 16), width=26, height=2, command=self.start_shift).pack(pady=30)

    def start_shift(self):
        if not self.entry_date.get() or not self.entry_wp.get() or not self.entry_name.get():
            messagebox.showerror("Ошибка", "Заполните все поля"); return
        self.shift_info = {"date": self.entry_date.get(), "workplace": self.entry_wp.get(), "name": self.entry_name.get()}
        self.state.reset(self.config["box_size"]); self.show_scan_screen()

    def show_scan_screen(self):
        self.clear(); t = TEXT[self.lang]
        self.info = tk.Label(self.root, font=("Arial", 16), justify="center"); self.info.pack(pady=25)
        self.last = tk.Entry(self.root, state="readonly", width=60, font=("Arial", 14), justify="center"); self.last.pack(pady=15)
        self.scan_entry = tk.Entry(self.root); self.scan_entry.place(x=-100, y=-100); self.scan_entry.focus_set(); self.scan_entry.bind("<Return>", self.on_scan)
        self.root.bind("<Button-1>", lambda e: self.scan_entry.focus_set())

        btn = tk.Frame(self.root); btn.pack(side="bottom", pady=20)
        tk.Button(btn, text="Пауза", width=14, command=self.pause).grid(row=0, column=0, padx=10)
        tk.Button(btn, text="Отправить", width=14, command=self.save_now).grid(row=0, column=1, padx=10)
        tk.Button(btn, text="Завершить смену", width=16, command=self.end_shift).grid(row=0, column=2, padx=10)
        self.update_info()

    def pause(self): self.paused = True; messagebox.askokcancel("Пауза", "Продолжить?"); self.paused = False; self.scan_entry.focus_set()
    def save_now(self): self.perform_save(); messagebox.showinfo("Успех", "Сохранено")
    def end_shift(self):
        if self.state.in_box != 0: messagebox.showwarning("Ошибка", "Коробка не закрыта"); return
        if messagebox.askokcancel("Смена", "Завершить?"):
            files = self.perform_save(); self.send_to_telegram(files)
            self.duplicates.clear_recovery(); self.show_language_screen()

    def on_scan(self, event):
        raw = self.sanitize_input(self.translate_layout(self.scan_entry.get().strip())); self.scan_entry.delete(0, tk.END)
        if not raw: return
        if self.state.wait_sscc:
            try:
                self.duplicates.check_sscc(raw); units = self.state.scan_sscc(raw)
                self.duplicates.save_box_to_recovery(raw, units, self.shift_info)
                self.show_last(f"Коробка закрыта: {raw}"); self.update_info()
            except Exception as e: messagebox.showerror("Ошибка", str(e))
        else:
            try:
                parsed = parse_gs1(raw)
                if self.config["gtin_enabled"] and parsed["gtin"] != self.config["gtin"]: raise Exception("Неверный GTIN")
                self.duplicates.check(parsed["clean"]); self.state.scan_unit(parsed)
                self.show_last(parsed["raw"]); self.update_info()
            except Exception as e: messagebox.showerror("Ошибка GS1", str(e))
        self.scan_entry.focus_set()

    def perform_save(self):
        summary = self.state.get_shift_summary()
        if not summary["data"]: return []
        ts = datetime.now().strftime("%H%M%S"); dt = self.shift_info['date'].replace('.', '_'); op = self.shift_info['name'].replace(' ', '_')
        os.makedirs("output", exist_ok=True); base = f"output/смена_{dt}_{op}_{ts}"
        txt = f"{base}.txt"; xls_a = f"{base}_агрегация.xlsx"; xls_n = f"{base}_нанесение.xlsx"
        with open(txt, "w", encoding="utf-8") as f: f.write(self.generate_xml(summary["data"]))
        self.gen_xls_agg(summary["data"], xls_a); self.gen_xls_prod(summary["data"], xls_n)
        return [txt, xls_a, xls_n]

    def generate_xml(self, boxes):
        xml = '<?xml version="1.0" encoding="UTF-8"?>\n<unit_pack>\n'
        for s, u in boxes:
            xml += f'<pack_content><pack_code>{s}</pack_code>\n'
            for x in u: xml += f'<cis>{x["clean"]}</cis>\n'
            xml += '</pack_content>\n'
        return xml + '</unit_pack>'

    def gen_xls_agg(self, boxes, fn):
        wb = openpyxl.Workbook(); ws = wb.active; ws.append(["AGGREGATE", "ITEM"])
        for s, u in boxes:
            for x in u: ws.append([s, x['clean']])
        wb.save(fn)

    def gen_xls_prod(self, boxes, fn):
        wb = openpyxl.Workbook(); ws = wb.active
        ws.append(["Название продукта", "Код маркировки", "GTIN", "ТН ВЭД", "Декларация", "Номер ДС", "Дата"])
        for s, u in boxes:
            for x in u:
                ws.append([self.config["product_name"] if self.config["product_enabled"] else "", x["clean"], x["gtin"], self.config["tnved"] if self.config["tnved_enabled"] else "", "Декларация", self.config["ds_number"] if self.config["ds_enabled"] else "", self.shift_info["date"]])
        wb.save(fn)

    def send_to_telegram(self, files):
        t, c = self.config.get("tg_token"), self.config.get("tg_chat_id")
        if not t or not c: return
        try:
            sum_data = self.state.get_shift_summary()
            msg = f"👤 Оператор: {self.shift_info['name']}\n📦 Коробки: {sum_data['total_boxes']}\n🔢 Коды: {sum_data['total_codes']}"
            requests.post(f"https://api.telegram.org/bot{t}/sendMessage", data={"chat_id": c, "text": msg})
            for p in files:
                with open(p, "rb") as f: requests.post(f"https://api.telegram.org/bot{t}/sendDocument", data={"chat_id": c}, files={"document": f})
        except: pass

    def show_last(self, text):
        self.last.config(state="normal"); self.last.delete(0, tk.END); self.last.insert(0, text); self.last.config(state="readonly")

    def update_info(self):
        if self.state.wait_sscc: txt = "⚠️ ОЖИДАНИЕ SSCC КОДА"
        else: txt = f"Коробка: {self.state.box}\nСобрано: {self.state.in_box} / {self.state.box_size}"
        self.info.config(text=txt)

def run(): App().root.mainloop()
if __name__ == "__main__": run()
