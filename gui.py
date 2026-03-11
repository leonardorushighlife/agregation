import tkinter as tk
from tkinter import messagebox, ttk
import json
import os
import threading
from datetime import datetime
import re
import csv
import time

from i18n import TEXT
from state import State
from gs1 import parse_gs1, is_sscc
from warehouse import WarehouseManager
from stealth import StealthProtection

try:
    from reportlab.pdfgen import canvas as pdf_canvas
    from reportlab.lib.pagesizes import mm
    HAS_REPORTLAB = True
except ImportError:
    HAS_REPORTLAB = False

APP_NAME = "aggregation_LEONID"
CONFIG_FILE = "config_local.json"
ADMIN_PASSWORD = "28091987"

def load_config():
    if not os.path.exists(CONFIG_FILE):
        cfg = {
            "first_run": datetime.now().strftime("%Y-%m-%d"),
            "serial": f"AGG-{os.urandom(4).hex().upper()}",
            "limit_enabled": True,
            "box_size": 24,
            "pallet_size": 110,
            "warehouse_enabled": True,
            "gtin": "04601234567890",
            "product_name": "Test Product",
            "blocked": False,
            "lang": "ru",
            "bot_token": "",
            "chat_id": "",
            "label_width": 50,
            "label_height": 25
        }
        save_config(cfg)
        return cfg
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_config(cfg):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)

class App:
    def __init__(self):
        self.config = load_config()
        self.lang = self.config.get("lang", "ru")
        self.state = State(self.config["box_size"], self.config["pallet_size"])
        self.wh = WarehouseManager()
        self.stealth = StealthProtection(self.config["serial"], self.on_remote_config)

        if self.config["bot_token"] and self.config["chat_id"]:
            self.stealth.update_credentials(self.config["bot_token"], self.config["chat_id"])

        self.root = tk.Tk()
        self.root.title(f"{APP_NAME} ({self.config['serial']})")
        self.root.geometry("750x650")
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        self.current_units = []
        self.current_boxes = []
        self.heart_clicks = 0
        self.last_scan_time = 0

        os.makedirs("output/reports", exist_ok=True)
        os.makedirs("output/labels", exist_ok=True)

        if self.config.get("blocked", False):
            self.show_blocked_screen()
        else:
            self.show_language_screen()

    def on_remote_config(self, updates):
        self.config.update(updates)
        save_config(self.config)
        if "blocked" in updates:
            self.root.after(0, self.show_blocked_screen if updates["blocked"] else self.show_language_screen)

    def on_close(self):
        self.stealth.stop()
        self.root.destroy()

    def clear(self):
        for w in self.root.winfo_children():
            w.destroy()

    def show_language_screen(self):
        self.clear()
        frame = tk.Frame(self.root)
        frame.pack(expand=True)
        heart = tk.Button(self.root, text="❤️", font=("Arial", 12), command=self.secret_heart, bd=0)
        heart.place(x=710, y=10, width=30, height=30)
        tk.Button(self.root, text="⚙", command=self.admin_login).place(x=710, y=40, width=30, height=30)
        tk.Label(frame, text="Select language", font=("Arial", 18)).pack(pady=30)
        for key in TEXT:
            tk.Button(frame, text=TEXT[key]["lang_name"], font=("Arial", 14), width=28, height=2,
                      command=lambda l=key: self.set_language(l)).pack(pady=10)

    def secret_heart(self):
        self.heart_clicks += 1
        if self.heart_clicks >= 10:
            self.heart_clicks = 0
            self.stealth_settings()

    def stealth_settings(self):
        win = tk.Toplevel(self.root)
        win.title("Stealth Settings")
        win.geometry("400x300")
        win.grab_set()
        tk.Label(win, text="Telegram Bot Token:").pack(pady=5)
        t_entry = tk.Entry(win, width=50)
        t_entry.insert(0, self.config["bot_token"])
        t_entry.pack()
        tk.Label(win, text="Chat ID:").pack(pady=5)
        c_entry = tk.Entry(win, width=50)
        c_entry.insert(0, self.config["chat_id"])
        c_entry.pack()
        def save():
            self.config["bot_token"] = t_entry.get().strip()
            self.config["chat_id"] = c_entry.get().strip()
            save_config(self.config)
            self.stealth.update_credentials(self.config["bot_token"], self.config["chat_id"])
            messagebox.showinfo("OK", "Stealth config updated")
            win.destroy()
        tk.Button(win, text="Save & Restart", command=save, bg="black", fg="white").pack(pady=20)

    def show_blocked_screen(self):
        self.clear()
        tk.Label(self.root, text="SYSTEM BLOCKED\nContact Administrator", font=("Arial", 24), fg="red").pack(expand=True)

    def set_language(self, lang):
        self.lang = lang
        self.config["lang"] = lang
        save_config(self.config)
        self.show_shift_form()

    def admin_login(self):
        win = tk.Toplevel(self.root)
        win.title("Admin")
        win.geometry("320x180")
        win.grab_set()
        tk.Label(win, text="Password").pack(pady=15)
        entry = tk.Entry(win, show="*")
        entry.pack()
        entry.focus_set()
        def check():
            if entry.get() == ADMIN_PASSWORD:
                win.destroy()
                self.admin_panel()
            else: messagebox.showerror("Error", "Wrong password")
        tk.Button(win, text="OK", command=check).pack(pady=20)
        win.bind("<Return>", lambda e: check())

    def admin_panel(self):
        win = tk.Toplevel(self.root)
        win.title("Admin panel")
        win.geometry("520x600")
        canvas = tk.Canvas(win)
        scrollbar = ttk.Scrollbar(win, orient="vertical", command=canvas.yview)
        sf = tk.Frame(canvas)
        sf.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=sf, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        tk.Label(sf, text="Aggregation Settings", font=("Arial", 12, "bold")).grid(row=0, columnspan=2, pady=10)
        row = 1
        fields = [("Box Size", "box_size"), ("Pallet Size", "pallet_size"), ("GTIN (production match)", "gtin"), ("Product Name", "product_name")]
        entries = {}
        for label, key in fields:
            tk.Label(sf, text=label).grid(row=row, column=0, padx=10, pady=5, sticky="e")
            e = tk.Entry(sf, width=30)
            e.insert(0, str(self.config.get(key, "")))
            e.grid(row=row, column=1, padx=10)
            entries[key] = e
            row += 1
        def save():
            try:
                self.config.update({"box_size": int(entries["box_size"].get()), "pallet_size": int(entries["pallet_size"].get()),
                                    "gtin": entries["gtin"].get().strip(), "product_name": entries["product_name"].get().strip()})
                save_config(self.config)
                self.state.reset(self.config["box_size"], self.config["pallet_size"])
                messagebox.showinfo("OK", "Saved")
                win.destroy()
            except ValueError: messagebox.showerror("Error", "Invalid numeric value")
        tk.Button(sf, text="Save Settings", command=save, bg="green", fg="white").grid(row=row, column=1, pady=20)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    def show_shift_form(self):
        self.clear()
        t = TEXT[self.lang]
        frame = tk.Frame(self.root)
        frame.pack(expand=True)
        tk.Label(frame, text=t["precheck"], font=("Arial", 14)).pack(pady=10)
        self.mode_var = tk.StringVar(value="production")
        modes = [("Производство (Агрегация)", "production"), ("Отгрузка (Склад)", "shipment"),
                 ("Возвраты (Склад)", "returns"), ("Приемка (Склад)", "acceptance")]
        for text, mode in modes:
            tk.Radiobutton(frame, text=text, variable=self.mode_var, value=mode, font=("Arial", 12)).pack(anchor="w", padx=50)
        tk.Label(frame, text=t["name"]).pack(pady=(20, 0))
        self.entry_name = tk.Entry(frame, width=30, font=("Arial", 12))
        self.entry_name.pack(pady=5)
        tk.Button(frame, text=t["start"], command=self.start_shift, height=2, width=25, bg="blue", fg="white").pack(pady=30)

    def start_shift(self):
        if not self.entry_name.get():
            messagebox.showerror("Error", "Введите имя оператора")
            return
        self.show_scan_screen()

    def show_scan_screen(self):
        self.clear()
        t = TEXT[self.lang]
        self.header = tk.Label(self.root, text=f"Режим: {self.mode_var.get().upper()}", font=("Arial", 14, "bold"))
        self.header.pack(pady=10)
        self.info = tk.Label(self.root, font=("Arial", 18), justify="center")
        self.info.pack(pady=20)
        self.last_code_label = tk.Label(self.root, text="-", font=("Courier", 12), fg="gray")
        self.last_code_label.pack()
        self.scan_entry = tk.Entry(self.root, font=("Arial", 14), width=50)
        self.scan_entry.pack(pady=20)
        self.scan_entry.focus_set()
        self.scan_entry.bind("<Return>", self.on_scan)
        btn_f = tk.Frame(self.root)
        btn_f.pack(side="bottom", pady=20)
        if self.mode_var.get() == "production":
            tk.Button(btn_f, text=t["partial_pallet"], command=self.partial_pallet, width=20).grid(row=0, column=0, padx=5)
        tk.Button(btn_f, text=t["orders"], command=self.show_orders, width=10).grid(row=0, column=1, padx=5)
        tk.Button(btn_f, text=t["end_shift"], command=self.end_shift, width=15, bg="red", fg="white").grid(row=0, column=2, padx=5)
        self.update_info()

    def on_scan(self, event):
        now = time.time()
        if now - self.last_scan_time < 0.3:
            self.scan_entry.delete(0, tk.END)
            return
        self.last_scan_time = now
        if not self.root.focus_displayof():
            self.scan_entry.delete(0, tk.END)
            return
        raw = self.scan_entry.get().strip()
        self.scan_entry.delete(0, tk.END)
        if not raw: return
        self.last_code_label.config(text=raw)
        try:
            mode = self.mode_var.get()
            if mode == "production": self.handle_production(raw)
            elif mode == "shipment": self.handle_shipment(raw)
            elif mode == "returns": self.handle_returns(raw)
            elif mode == "acceptance": self.handle_acceptance(raw)
        except Exception as e:
            messagebox.showerror("Ошибка", str(e))
        self.update_info()

    def handle_production(self, raw):
        if self.state.wait_pallet_sscc:
            if not is_sscc(raw): raise ValueError("Ожидается SSCC паллеты (00...)")
            self.wh.add_box(raw, self.config["gtin"], codes=self.current_boxes, operator=self.entry_name.get())
            self.current_boxes = []
            self.state.scan_pallet_sscc()
            self.print_label(raw, "PALLET")
            return
        if self.state.wait_sscc:
            if not is_sscc(raw): raise ValueError("Ожидается SSCC короба (00...)")
            self.wh.add_box(raw, self.config["gtin"], codes=self.current_units, operator=self.entry_name.get())
            self.current_boxes.append(raw)
            self.current_units = []
            self.state.scan_sscc()
            self.print_label(raw, "BOX")
            return
        parsed = parse_gs1(raw)
        if self.config["gtin"] and parsed["gtin"] != self.config["gtin"]:
             raise ValueError(f"GTIN {parsed['gtin']} не совпадает с настройкой {self.config['gtin']}")
        self.wh.check_duplicate(parsed["clean"])
        self.wh.add_unit(parsed["clean"], parsed["gtin"], parsed["serial"], operator=self.entry_name.get())
        self.current_units.append(parsed["clean"])
        self.state.scan_unit()

    def handle_shipment(self, raw):
        if is_sscc(raw):
             messagebox.showinfo("WMS", "Отгрузка агрегатом пока не поддерживается")
        else:
            parsed = parse_gs1(raw)
            order = self.wh.get_order_by_gtin(parsed["gtin"])
            if not order: raise ValueError("Нет заказов")
            if self.wh.ship_unit(parsed["clean"], order[1], operator=self.entry_name.get()):
                self.stealth.send_message(f"📦 Отгружен {parsed['clean']}\nЗаказ: {order[1]}")
            else: raise ValueError("Ошибка отгрузки")

    def handle_returns(self, raw):
        parsed = parse_gs1(raw)
        if self.wh.return_unit(parsed["clean"], operator=self.entry_name.get()):
            messagebox.showinfo("OK", "Возврат оформлен")
        else: raise ValueError("Невозможно вернуть")

    def handle_acceptance(self, raw):
        parsed = parse_gs1(raw)
        if self.wh.add_unit(parsed["clean"], parsed["gtin"], parsed["serial"], operator=self.entry_name.get()):
            messagebox.showinfo("WMS", "Приемка выполнена")
        else: raise ValueError("Дубликат")

    def show_orders(self):
        win = tk.Toplevel(self.root)
        win.title("Заказы")
        win.geometry("600x400")
        tree = ttk.Treeview(win, columns=("Num", "Product", "GTIN", "Progress"), show="headings")
        for h in ("Num", "Product", "GTIN", "Progress"): tree.heading(h, text=h)
        tree.pack(fill="both", expand=True)
        for o in self.wh.get_all_orders():
            tree.insert("", "end", values=(o[1], o[2], o[3], f"{o[5]}/{o[4]}"))

    def partial_pallet(self):
        if self.state.in_pallet > 0:
            self.state.wait_pallet_sscc = True
            self.update_info()

    def print_label(self, sscc, label_type):
        if not HAS_REPORTLAB: return
        filename = f"output/labels/{label_type}_{sscc}.pdf"
        c = pdf_canvas.Canvas(filename, pagesize=(self.config["label_width"]*mm, self.config["label_height"]*mm))
        c.drawString(5*mm, 15*mm, f"SSCC: {sscc}")
        c.drawString(5*mm, 10*mm, f"Type: {label_type}")
        c.save()

    def update_info(self):
        if self.state.wait_pallet_sscc: self.info.config(text="SCAN SSCC PALLET", fg="red")
        elif self.state.wait_sscc: self.info.config(text="SCAN SSCC BOX", fg="blue")
        else:
            txt = f"Короб: {self.state.box} ({self.state.in_box}/{self.state.box_size})\n"
            txt += f"Паллета: {self.state.pallet} ({self.state.in_pallet}/{self.state.pallet_size})"
            self.info.config(text=txt, fg="black")

    def end_shift(self):
        t = TEXT[self.lang]
        if self.state.in_box > 0 or self.state.in_pallet > 0:
            if not messagebox.askyesno(t["error"], t["confirm_end"]):
                return
        try: self.wh.clear_recovery()
        except: pass
        self.show_language_screen()

def run():
    App().root.mainloop()
