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
    defaults = {"first_run": datetime.now().strftime("%Y-%m-%d"), "limit_enabled": True, "box_size": 24, "lp_tin": "7777777777", "gtin": "", "gtin_enabled": False, "product_name": "", "product_enabled": False, "tnved": "", "tnved_enabled": False, "ds_number": "", "ds_enabled": False, "tg_token": "", "tg_chat_id": "", "db_path": "data/duplicates.db"}
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
        self.duplicates = DuplicateChecker(self.config["db_path"])
        self.state = State(self.config["box_size"])
        self.paused = False
        self.root = tk.Tk()
        self.root.title(APP_NAME); self.root.geometry("720x560"); self.root.resizable(False, False)

        # Лимит безопасности
        self.is_limited = False
        if self.config.get("limit_enabled") and days_passed(self.config["first_run"]) >= 180:
            self.is_limited = True
            messagebox.showwarning("Безопасность", "Срок действия лицензии истек. Работа ограничена.")
            self.config["box_size"] = 1 # Делаем работу невыносимой

        self.check_unsent_files()
        self.show_language_screen()
        self.check_recovery()

    def check_recovery(self):
        """Проверка на наличие данных после сбоя"""
        data = self.duplicates.get_recovery_data()
        if data:
            if messagebox.askyesno("Восстановление", "Обнаружена незавершенная смена. Продолжить?"):
                recovered_boxes = []
                last_shift_info = None
                for sscc, units_json, shift_info_json in data:
                    recovered_boxes.append((sscc, json.loads(units_json)))
                    last_shift_info = json.loads(shift_info_json)

                self.shift_info = last_shift_info
                self.state.load_recovery(recovered_boxes)
                self.show_scan_screen()
            else:
                self.duplicates.clear_recovery()

    def check_unsent_files(self):
        """Попытка отправить файлы, которые не ушли ранее"""
        unsent_dir = "output/unsent"
        if os.path.exists(unsent_dir):
            files = [os.path.join(unsent_dir, f) for f in os.listdir(unsent_dir)]
            if files: self.send_to_telegram(files, is_retry=True)

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
        win = tk.Toplevel(self.root); win.title("Админка"); win.geometry("600x720")
        def block(title, val, row):
            tk.Label(win, text=title).grid(row=row, column=0, sticky="w", padx=10, pady=5)
            e = tk.Entry(win, width=30); e.insert(0, str(val)); e.grid(row=row, column=1); return e
        row = 0; box_e = block("Размер короба", self.config["box_size"], row); row += 1
        tin_e = block("ИНН", self.config["lp_tin"], row); row += 1
        prod_e = block("Продукт", self.config["product_name"], row); row += 1
        tnved_e = block("ТН ВЭД", self.config["tnved"], row); row += 1
        tg_t = block("TG Token", self.config["tg_token"], row); row += 1
        tg_c = block("TG Chat ID", self.config["tg_chat_id"], row); row += 1
        def save():
            self.config.update({"box_size": int(box_e.get()), "lp_tin": tin_e.get(), "product_name": prod_e.get(), "tnved": tnved_e.get(), "tg_token": tg_t.get(), "tg_chat_id": tg_c.get()})
            save_config(self.config); win.destroy()
        tk.Button(win, text="Сохранить", command=save).grid(row=row, column=1, pady=20)

    def show_shift_form(self):
        self.clear(); t = TEXT[self.lang]; frame = tk.Frame(self.root); frame.pack(expand=True)
        self.entry_date = tk.Entry(frame, width=30, font=("Arial", 14), justify="center"); self.entry_date.insert(0, datetime.now().strftime("%d.%m.%Y")); self.entry_date.pack(pady=5)
        self.entry_wp = tk.Entry(frame, width=30, font=("Arial", 14), justify="center"); self.entry_wp.pack(pady=5)
        tk.Label(frame, text=t["workplace"]).pack()
        self.entry_name = tk.Entry(frame, width=30, font=("Arial", 14), justify="center"); self.entry_name.pack(pady=5)
        tk.Label(frame, text=t["name"]).pack()
        tk.Button(frame, text=t["start"], font=("Arial", 16), command=self.start_shift).pack(pady=30)

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
        tk.Button(btn, text=t["save"], command=self.save_now).grid(row=0, column=1, padx=10)
        tk.Button(btn, text=t["end_shift"], command=self.end_shift).grid(row=0, column=2, padx=10)
        self.update_info()

    def on_scan(self, event):
        raw = self.sanitize_input(self.translate_layout(self.scan_entry.get().strip()))
        self.scan_entry.delete(0, tk.END)
        if not raw: return
        if self.state.wait_sscc:
            try:
                self.duplicates.check_sscc(raw)
                units = self.state.scan_sscc(raw)
                # Страховка: пишем в БД сразу после закрытия короба
                self.duplicates.save_box_to_recovery(raw, units, self.shift_info)
                self.show_last(f"Коробка закрыта: {raw}"); self.update_info()
            except Exception as e: messagebox.showerror("Ошибка", str(e))
        else:
            try:
                parsed = parse_gs1(raw); self.duplicates.check(parsed["clean"])
                self.state.scan_unit(parsed); self.show_last(parsed["raw"]); self.update_info()
            except Exception as e: messagebox.showerror("Ошибка", str(e))
        self.scan_entry.focus_set()

    def save_now(self): self.perform_save(); messagebox.showinfo("Успех", "Сохранено")
    def end_shift(self):
        if self.state.in_box != 0: messagebox.showwarning("Ошибка", "Коробка не закрыта"); return
        files = self.perform_save()
        self.send_to_telegram(files)
        self.duplicates.clear_recovery()
        messagebox.showinfo("Готово", "Смена завершена")
        self.show_language_screen()

    def perform_save(self):
        summary = self.state.get_shift_summary()
        if not summary["data"]: return []
        ts = datetime.now().strftime("%H%M%S"); date_s = self.shift_info['date'].replace('.', '_'); op = self.shift_info['name'].replace(' ', '_')
        os.makedirs("output", exist_ok=True)
        base = f"output/смена_{date_s}_{op}_{ts}"

        # Генерация файлов
        txt = f"{base}.txt"; xls_a = f"{base}_агрегация.xlsx"; xls_n = f"{base}_нанесение.xlsx"
        with open(txt, "w", encoding="utf-8") as f: f.write(self.generate_xml(summary["data"]))
        self.gen_xls_agg(summary["data"], xls_a)
        self.gen_xls_prod(summary["data"], xls_n)
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
        wb = openpyxl.Workbook(); ws = wb.active; ws.append(["Продукт", "КМ", "GTIN", "ТН ВЭД", "Дата"])
        for s, u in boxes:
            for x in u: ws.append([self.config["product_name"], x["clean"], x["gtin"], self.config["tnved"], self.shift_info["date"]])
        wb.save(fn)

    def send_to_telegram(self, files, is_retry=False):
        t, c = self.config.get("tg_token"), self.config.get("tg_chat_id")
        if not t or not c: return
        try:
            if not is_retry:
                sum_data = self.state.get_shift_summary()
                msg = f"✅ Смена завершена\n👤 Оператор: {self.shift_info['name']}\n📦 Полных коробов: {sum_data['total_boxes']}\n🔢 Всего кодов: {sum_data['total_codes']}"
                requests.post(f"https://api.telegram.org/bot{t}/sendMessage", data={"chat_id": c, "text": msg}, timeout=10)

            for p in files:
                with open(p, "rb") as f:
                    res = requests.post(f"https://api.telegram.org/bot{t}/sendDocument", data={"chat_id": c}, files={"document": f}, timeout=20)
                if res.status_code == 200 and is_retry: os.remove(p)
        except:
            if not is_retry:
                # Если не ушло — в папку unsent
                unsent_dir = "output/unsent"; os.makedirs(unsent_dir, exist_ok=True)
                for p in files: shutil.copy(p, unsent_dir)

    def show_last(self, text):
        self.last.config(state="normal"); self.last.delete(0, tk.END); self.last.insert(0, text); self.last.config(state="readonly")

    def update_info(self):
        if self.state.wait_sscc: txt = "⚠️ ОЖИДАНИЕ SSCC КОДА"
        else: txt = f"Коробка: {self.state.box} | Собрано: {self.state.in_box}/{self.state.box_size}"
        self.info.config(text=txt)

def run(): App().root.mainloop()
if __name__ == "__main__": run()
