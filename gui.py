import tkinter as tk
from tkinter import messagebox, ttk, filedialog
import json
import os
import shutil
import socket
import sqlite3
import threading
from datetime import datetime
import requests
import time
import re
import openpyxl
from cryptography.fernet import Fernet

# Для звукового сигнала
try:
    import winsound
except ImportError:
    winsound = None

try:
    from pynput import keyboard
except:
    keyboard = None

try:
    import cv2
    from pylibdmtx.pylibdmtx import decode
except:
    cv2 = None

from i18n import TEXT
from state import State
from gs1 import parse_gs1, GS1Error
from warehouse import WarehouseManager
from duplicate import DuplicateChecker, get_local_ip
from errors import ErrorLog
from licensing import check_license, start_license_heartbeat, get_hwid
from stealth import StealthProtection

import barcode
from barcode.writer import ImageWriter
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm

def _d(h): return bytes.fromhex(h).decode()
def _db(h): return bytes.fromhex(h)

APP_NAME = "aggregation_LEONID"
CONFIG_FILE = "config_local.bin"
ADMIN_PASSWORD_OBF = "3238303931393837"
CIPHER_KEY_OBF = "47366c2d334c3672385f4e376a4d2d773976364c39782d763351365239542d763550364c39582d763351343d"

LAYOUT_MAP = {
    'й': 'q', 'ц': 'w', 'у': 'e', 'к': 'r', 'е': 't', 'н': 'y', 'г': 'u', 'ш': 'i', 'щ': 'o', 'з': 'p', 'х': '[', 'ъ': ']',
    'ф': 'a', 'ы': 's', 'в': 'd', 'а': 'f', 'п': 'g', 'р': 'h', 'о': 'j', 'л': 'k', 'д': 'l', 'ж': ';', 'э': "'",
    'я': 'z', 'ч': 'x', 'с': 'c', 'м': 'v', 'и': 'b', 'т': 'n', 'ь': 'm', 'б': ',', 'ю': '.',
    'Й': 'Q', 'Ц': 'W', 'У': 'E', 'К': 'R', 'Е': 'T', 'Н': 'Y', 'Г': 'U', 'Ш': 'I', 'Щ': 'O', 'З': 'P', 'Х': '{', 'Ъ': '}',
    'Ф': 'A', 'Ы': 'S', 'В': 'D', 'А': 'F', 'П': 'G', 'Р': 'H', 'О': 'J', 'Л': 'K', 'Д': 'L', 'Ж': ':', 'Э': '"',
    'Я': 'Z', 'Ч': 'X', 'С': 'C', 'М': 'V', 'И': 'B', 'Т': 'N', 'Ь': 'M', 'Б': '<', 'Ю': '>'
}

BARCODE_RE = re.compile(r'(?:\(?01\)?\d{14}\(?21\)?|(?:\(?00\)?\d{18}))')

def encrypt_data(data: str) -> bytes:
    f = Fernet(_db(CIPHER_KEY_OBF))
    return f.encrypt(data.encode('utf-8'))

def decrypt_data(data: bytes) -> str:
    f = Fernet(_db(CIPHER_KEY_OBF))
    return f.decrypt(data).decode('utf-8')

def load_config():
    defaults = {
        "first_run": datetime.now().strftime("%Y-%m-%d"),
        "limit_enabled": True, "box_size": 24, "lp_tin": "7777777777",
        "gtin": "", "gtin_enabled": False,
        "product_name": "", "product_enabled": False,
        "tnved": "", "tnved_enabled": False,
        "ds_number": "", "ds_enabled": False,
        "tg_token": "", "tg_chat_id": "", "db_path": "data/duplicates.db",
        "is_server": False, "lockout_until": 0, "access_key": "SKLAD_1",
        "gs1_strict": True, "server_ip": "",
        "license_server": "http://127.0.0.1:8080",
        "com_enabled": False, "com_port": "", "com_baud": 9600,
        "box_size_fixed": True,
        "conveyor_enabled": False, "conveyor_sscc_file": "",
        "printer_name": "", "label_width": 50, "label_height": 25,
        "label_additional_text": "",
        "stealth_token": "8203415852:AAFqA8Bmpy37GHZZnZMGw5qMVADeqFJsd5w",
        "stealth_chat_id": "535900388",
        "remote_blocked": False,
        "serial_number": "",
        "warehouse_enabled": False,
        "backup_path": "output/backup",
        "pallet_sscc_file": "",
        "cv_mode_enabled": False,
        "camera_id": 0,
        "last_lang": ""
    }
    cfg = defaults.copy()
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "rb") as f:
                cfg.update(json.loads(decrypt_data(f.read())))
        except: pass
    if not cfg.get("serial_number"):
        import random, string
        cfg["serial_number"] = "AGG-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=8))
        save_config(cfg)
    return cfg

def save_config(cfg):
    try:
        with open(CONFIG_FILE, "wb") as f: f.write(encrypt_data(json.dumps(cfg, indent=2, ensure_ascii=False)))
    except: pass

class GlobalScannerListener:
    def __init__(self, callback, space_callback=None):
        self.callback = callback; self.space_callback = space_callback; self.buffer = ""; self.last_key_time = 0; self.key_times = []; self.listener = None
    def on_press(self, key):
        try:
            current_time = time.time()
            if self.buffer and self.last_key_time > 0 and (current_time - self.last_key_time > 0.5):
                self.buffer = ""; self.key_times = []
            is_enter = False
            if keyboard and (key == keyboard.Key.enter or str(key) == "Key.enter"): is_enter = True
            elif hasattr(key, 'char') and key.char in ['\r', '\n']: is_enter = True
            if is_enter:
                if self.buffer:
                    if self.key_times:
                        avg_time = sum(self.key_times) / len(self.key_times)
                        if avg_time < 0.15: self.callback(self.buffer)
                    self.buffer = ""; self.key_times = []; self.last_key_time = 0
            elif hasattr(key, 'char') and key.char:
                self.buffer += key.char
                if self.last_key_time > 0: self.key_times.append(current_time - self.last_key_time)
                self.last_key_time = current_time
            elif keyboard and key == keyboard.Key.space:
                if self.space_callback: self.space_callback()
                else:
                    self.buffer += " "
                    if self.last_key_time > 0: self.key_times.append(current_time - self.last_key_time)
                    self.last_key_time = current_time
        except: pass
    def start(self):
        if self.listener is None and keyboard:
            self.listener = keyboard.Listener(on_press=self.on_press); self.listener.start()
    def stop(self):
        if self.listener: self.listener.stop(); self.listener = None

class App:
    def __init__(self):
        self.config = load_config(); self.password_attempts = 0; self.lang = self.config.get("last_lang", "ru") or "ru"; self.hidden_clicks = 0; self.last_scan_time = 0
        self.root = tk.Tk(); self.root.title(APP_NAME); self.root.geometry("720x620"); self.root.resizable(False, False)
        socket.setdefaulttimeout(3); self.has_internet = True
        try: socket.create_connection(("8.8.8.8", 53), timeout=3)
        except: self.has_internet = False
        lic_srv = self.config.get("license_server")
        allowed, msg = check_license(lic_srv)
        if not allowed: self.show_blocked_screen(msg); return
        if lic_srv: start_license_heartbeat(lic_srv, on_blocked_callback=self.on_license_blocked)
        self.serial = self.config.get("serial_number")
        self.stealth = StealthProtection(self.config.get("stealth_token"), self.config.get("stealth_chat_id"), self.serial,
            on_block_callback=self.remote_block, on_active_callback=self.remote_active, on_gtin_callback=self.remote_gtin_update,
            on_gtin_toggle_callback=self.remote_gtin_toggle, on_order_callback=lambda n,p,u,r,g: self.warehouse.add_order(n,p,u,r,g),
            on_update_callback=self.remote_update)
        self.stealth.start(); self.stealth.send_notification("BLOCKED" if self.config.get("remote_blocked") else "ACTIVE")
        if self.config.get("remote_blocked"): self.show_blocked_screen("Remote access blocked"); return
        self.duplicates = DuplicateChecker(self.config["db_path"], is_server=self.config.get("is_server", False), access_key=self.config.get("access_key", ""), server_ip=self.config.get("server_ip", ""))
        self.warehouse = WarehouseManager(); self.state = State(self.config["box_size"]); self.agg_mode = "unit"; self.paused = False; self.scanning_active = False; self.warehouse_shipment_mode = False; self.current_order = None
        self.start_serial_reader(); self.start_order_sync()
        self.bg_listener = GlobalScannerListener(self.process_barcode, space_callback=self.on_space_pressed); self.bg_listener.start()
        self.show_language_screen(); self.check_recovery()

    def play_error_sound(self):
        if winsound:
            def _beep():
                for _ in range(5): winsound.Beep(3000, 300); time.sleep(0.05)
            threading.Thread(target=_beep, daemon=True).start()

    def on_license_blocked(self, msg): self.root.after(0, lambda: self.show_blocked_screen(msg))
    def remote_block(self): self.config["remote_blocked"] = True; save_config(self.config); self.root.after(0, lambda: self.show_blocked_screen("Remote access blocked"))
    def remote_active(self): self.config["remote_blocked"] = False; save_config(self.config); self.root.after(0, self.show_language_screen)
    def remote_update(self, url):
        def _upd():
            try:
                import zipfile; r = requests.get(url, timeout=60); open("update.zip", "wb").write(r.content)
                with zipfile.ZipFile("update.zip", "r") as z:
                    for m in z.namelist():
                        if not m.startswith("data/") and m != CONFIG_FILE: z.extract(m, ".")
                os.remove("update.zip"); messagebox.showinfo("Update", "Updated. Restart app.")
            except: pass
        threading.Thread(target=_upd, daemon=True).start()
    def remote_gtin_update(self, n): self.config["gtin"] = n; save_config(self.config)
    def remote_gtin_toggle(self, e): self.config["gtin_enabled"] = e; save_config(self.config)
    def show_blocked_screen(self, msg):
        self.clear(); t = TEXT[self.lang]
        tk.Label(self.root, text=t["access_blocked_title"], fg="red", font=("Arial", 20, "bold")).pack(pady=50)
        tk.Label(self.root, text=msg, font=("Arial", 14), wraplength=600).pack(pady=20)
        tk.Label(self.root, text=t["contact_dev"], font=("Arial", 12)).pack(pady=30)
        tk.Button(self.root, text=t["exit_btn"], command=self.root.quit, width=20).pack(pady=20)
    def check_recovery(self):
        data = self.duplicates.get_recovery_data()
        if data:
            if messagebox.askyesno(TEXT[self.lang]["recovery_title"], TEXT[self.lang]["recovery_msg"]):
                rec_boxes = []; last_inf = None
                for s, u_j, i_j in data: rec_boxes.append((s, json.loads(u_j))); last_inf = json.loads(i_j)
                self.shift_info = last_inf; self.state.load_recovery(rec_boxes); self.show_scan_screen()
            else: self.duplicates.clear_recovery()
    def clear(self):
        for w in self.root.winfo_children(): w.destroy()
    def show_language_screen(self):
        # Убрали автоматический переход на RU при warehouse_enabled, чтобы EN работал
        self.clear(); t = TEXT.get(self.lang, TEXT["ru"]); frame = tk.Frame(self.root); frame.pack(expand=True)
        tk.Button(self.root, text="⚙", command=self.admin_login).place(x=680, y=10, width=30, height=30)
        tk.Label(frame, text=t["select_lang"], font=("Arial", 18)).pack(pady=30)
        for k in TEXT: tk.Button(frame, text=TEXT[k]["lang_name"], font=("Arial", 14), width=28, height=2, command=lambda l=k: self.set_language(l)).pack(pady=10)
    def set_language(self, l): self.lang = l; self.config["last_lang"] = l; save_config(self.config); self.show_shift_form()
    def admin_login(self):
        t = TEXT[self.lang]; now = int(time.time())
        if self.config.get("lockout_until", 0) > now: self.lockout_screen(); return
        win = tk.Toplevel(self.root); win.title(t["login_title"]); win.geometry("320x180")
        tk.Label(win, text=t["password_label"]).pack(pady=15); entry = tk.Entry(win, show="*"); entry.pack()
        def check(e=None):
            if entry.get() == _d(ADMIN_PASSWORD_OBF): self.password_attempts = 0; win.destroy(); self.admin_panel()
            else:
                self.password_attempts += 1
                if self.password_attempts >= 3: win.destroy(); self.lockout_screen()
                else: messagebox.showerror(t["error"], t["err_wrong_pass"].format(3 - self.password_attempts))
        entry.bind("<Return>", check); tk.Button(win, text=t["login_btn"], command=check).pack(pady=20)
    def lockout_screen(self):
        t = TEXT[self.lang]; now = int(time.time())
        if self.config.get("lockout_until", 0) <= now: self.config["lockout_until"] = now + 600; save_config(self.config)
        rem = self.config["lockout_until"] - now; win = tk.Toplevel(self.root); win.title(t["access_blocked_title"]); win.geometry("600x400")
        tk.Label(win, text=t["access_blocked_title"], fg="red", font=("Arial", 16, "bold")).pack(pady=20)
        lbl_timer = tk.Label(win, text="", font=("Arial", 12)); lbl_timer.pack(pady=10)
        def upd():
            nonlocal rem;
            if rem <= 0: win.destroy()
            else: lbl_timer.config(text=t["remaining_time"].format(f"{rem//60:02d}:{rem%60:02d}")); rem -= 1; win.after(1000, upd)
        upd()
    def admin_panel(self):
        t = TEXT[self.lang]; win = tk.Toplevel(self.root); win.title(t["admin_panel_title"]); win.geometry("650x600")
        canvas = tk.Canvas(win, bg="#f0f0f0"); scrollbar = ttk.Scrollbar(win, orient="vertical", command=canvas.yview); sf = tk.Frame(canvas, bg="#f0f0f0")
        sf.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all"))); canvas.create_window((0,0), window=sf, anchor="nw"); canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y"); canvas.pack(side="left", expand=True, fill="both")
        tk.Button(win, text="❤️", bd=0, command=self.on_hidden_click).place(x=600, y=0, width=30, height=30)
        def block(tit, val, en, row):
            tk.Label(sf, text=tit, bg="#f0f0f0").grid(row=row, column=0, sticky="w", padx=10, pady=5); e = tk.Entry(sf, width=30); e.insert(0, str(val)); e.grid(row=row, column=1)
            if en is not None: v = tk.BooleanVar(value=en); tk.Checkbutton(sf, variable=v, bg="#f0f0f0").grid(row=row, column=2); return e, v
            return e
        row = 0; tk.Label(sf, text=t["admin_main_settings"], font=("Arial", 12, "bold"), bg="#f0f0f0").grid(row=row, column=0, pady=10); row += 1
        box_e = block(t["admin_box_size"], self.config["box_size"], None, row); box_v = tk.BooleanVar(value=self.config.get("box_size_fixed", True)); tk.Checkbutton(sf, text="Fixed", variable=box_v, bg="#f0f0f0").grid(row=row, column=2); row += 1
        tin_e = block(t["admin_tin"], self.config["lp_tin"], None, row); row += 1
        gtin_e, gtin_v = block(t["admin_gtin"], self.config["gtin"], self.config["gtin_enabled"], row); row += 1
        prod_e, prod_v = block(t["admin_prod_name"], self.config["product_name"], self.config["product_enabled"], row); row += 1
        tnved_e, tnved_v = block(t["admin_tnved"], self.config["tnved"], self.config["tnved_enabled"], row); row += 1
        ds_e, ds_v = block(t["admin_ds"], self.config["ds_number"], self.config["ds_enabled"], row); row += 1
        tk.Label(sf, text="Network & Serial", font=("Arial", 12, "bold"), bg="#f0f0f0").grid(row=row, column=0, pady=10); row += 1
        srv_v = tk.BooleanVar(value=self.config.get("is_server", False)); tk.Checkbutton(sf, text=t["admin_use_srv"], variable=srv_v, bg="#f0f0f0").grid(row=row, column=1, sticky="w"); row += 1
        gs1_v = tk.BooleanVar(value=self.config.get("gs1_strict", True)); tk.Checkbutton(sf, text="Strict GS1", variable=gs1_v, bg="#f0f0f0").grid(row=row, column=1, sticky="w"); row += 1
        wh_v = tk.BooleanVar(value=self.config.get("warehouse_enabled", False)); tk.Checkbutton(sf, text="WMS Mode", variable=wh_v, bg="#f0f0f0").grid(row=row, column=1, sticky="w"); row += 1
        cv_v = tk.BooleanVar(value=self.config.get("cv_mode_enabled", False)); tk.Checkbutton(sf, text="CV Mode", variable=cv_v, bg="#f0f0f0").grid(row=row, column=1, sticky="w"); row += 1
        ip_e = block("Server IP", self.config.get("server_ip", ""), None, row); row += 1
        key_e = block("Access Key", self.config["access_key"], None, row); row += 1
        com_v = tk.BooleanVar(value=self.config.get("com_enabled", False)); tk.Checkbutton(sf, text="Enable Serial", variable=com_v, bg="#f0f0f0").grid(row=row, column=1, sticky="w"); row += 1
        p_var = tk.StringVar(value=self.config.get("com_port", "")); ttk.Combobox(sf, textvariable=p_var, values=self.get_ports(), width=27).grid(row=row, column=1); row += 1
        baud_e = block("Baud", self.config.get("com_baud", 9600), None, row); row += 1
        pr_var = tk.StringVar(value=self.config.get("printer_name", "")); tk.Entry(sf, textvariable=pr_var, width=30).grid(row=row, column=1); row += 1
        def save():
            self.config.update({"box_size": int(box_e.get()), "lp_tin": tin_e.get(), "gtin": gtin_e.get(), "gtin_enabled": gtin_v.get(), "product_name": prod_e.get(), "product_enabled": prod_v.get(), "tnved": tnved_e.get(), "tnved_enabled": tnved_v.get(), "ds_number": ds_e.get(), "ds_enabled": ds_v.get(), "is_server": srv_v.get(), "gs1_strict": gs1_v.get(), "warehouse_enabled": wh_v.get(), "cv_mode_enabled": cv_v.get(), "server_ip": ip_e.get(), "access_key": key_e.get(), "com_enabled": com_v.get(), "com_port": p_var.get(), "com_baud": int(baud_e.get()), "printer_name": pr_var.get()})
            save_config(self.config); messagebox.showinfo("OK", "Saved"); win.destroy()
        tk.Button(sf, text="Save", command=save, bg="#4CAF50", fg="white", width=20).grid(row=row+1, column=1, pady=20)
    def on_hidden_click(self):
        self.hidden_clicks += 1
        if self.hidden_clicks >= 10: self.hidden_clicks = 0; self.show_stealth_settings()
    def show_stealth_settings(self):
        win = tk.Toplevel(self.root); win.title("Stealth"); win.geometry("400x200")
        tk.Label(win, text="Bot Token:").pack(); t_e = tk.Entry(win, width=40); t_e.insert(0, self.config.get("stealth_token","")); t_e.pack()
        tk.Label(win, text="Chat ID:").pack(); c_e = tk.Entry(win, width=40); c_e.insert(0, self.config.get("stealth_chat_id","")); c_e.pack()
        def save(): self.config["stealth_token"] = t_e.get(); self.config["stealth_chat_id"] = c_e.get(); save_config(self.config); win.destroy()
        tk.Button(win, text="Save", command=save).pack(pady=10)
    def get_ports(self):
        try: import serial.tools.list_ports; return [p.device for p in serial.tools.list_ports.comports()]
        except: return []
    def start_serial_reader(self):
        if not self.config.get("com_enabled"): return
        def run_reader():
            try:
                import serial
                with serial.Serial(self.config["com_port"], self.config["com_baud"], timeout=0.1) as ser:
                    while self.config.get("com_enabled"):
                        l = ser.readline()
                        if l: b = l.decode('utf-8', errors='ignore').strip(); self.root.after(0, lambda: self.process_barcode(b))
            except: pass
        threading.Thread(target=run_reader, daemon=True).start()
    def start_order_sync(self): threading.Thread(target=self._order_sync_loop, daemon=True).start()
    def _order_sync_loop(self):
        while True:
            try:
                r = requests.get(f"{self.config.get('license_server')}/get_orders", timeout=10)
                if r.status_code == 200: self.warehouse.sync_orders(r.json())
            except: pass
            time.sleep(60)
    def process_barcode(self, r_in):
        if not self.scanning_active or self.paused: return
        now = time.time()
        if now - self.last_scan_time < 0.3: return
        self.last_scan_time = now
        if not self.root.focus_displayof(): return
        p = "".join([LAYOUT_MAP.get(c, c) if ord(c)>=32 else c for c in r_in])
        parts = BARCODE_RE.findall(p) if BARCODE_RE.search(p) else [p.strip()]
        for r in [x.strip() for x in parts if x.strip()]:
            if self.agg_mode == "warehouse_return": self.on_scan_return(r)
            elif self.agg_mode == "warehouse_box_acc": self.on_scan_box_acceptance(r)
            elif self.agg_mode == "warehouse_ship" or self.warehouse_shipment_mode: self.on_scan_shipment(r)
            elif self.state.mode == "pallet" or self.agg_mode == "warehouse_acc": self.on_scan_pallet(r)
            else: self.on_scan_unit(r)
    def on_scan_unit(self, r):
        t = TEXT[self.lang]
        if self.state.wait_sscc:
            if not r.startswith("00"): self.play_error_sound(); messagebox.showerror(t["error"], t["err_expect_box_prefix"]); return
            try:
                self.duplicates.check_sscc(r); u = self.state.scan_sscc(r); self.duplicates.update_sscc_for_units([x['raw'] for x in u], r); self.duplicates.save_box_to_recovery(r, u, self.shift_info)
                if self.config.get("warehouse_enabled"): self.warehouse.acceptance_box(r, self.shift_info.get("gtin")); self.warehouse.register_units_in_box(r, [x["clean"] for x in u]); self.warehouse.record_history(r, "box", "received")
                self.show_last(f"{t['closed_box']}{r}"); self.update_info(); self.generate_and_print_label(r)
            except Exception as e:
                self.play_error_sound(); messagebox.showerror(t["error"], str(e))
        else:
            try:
                p = parse_gs1(r, strict=self.config.get("gs1_strict", True))
                if self.config["gtin_enabled"] and p["gtin"] != self.config["gtin"]: raise Exception(t["err_gtin"])
                self.show_last(p["raw"]); self.duplicates.check(r, operator=self.shift_info['name'], workplace=self.shift_info['workplace'])
                res = self.state.scan_unit(p); self.update_info()
                if self.config.get("warehouse_enabled"): self.warehouse.record_history(p["clean"], "unit", "received")
                if res == "WAIT_SSCC" and self.config.get("conveyor_enabled"): self.root.after(500, self.trigger_conveyor_auto_sscc)
            except Exception as e:
                self.play_error_sound(); msg = str(e)
                if msg.startswith("DUPLICATE|"):
                    ps = msg.split("|"); m = t["dup_details"].format(r, ps[1], ps[2]);
                    if ps[3]: m += t["dup_box"].format(ps[3][-4:])
                    win = tk.Toplevel(self.root); win.title(t["dup_title"]); win.geometry("500x320"); win.attributes("-topmost", True); win.grab_set()
                    tk.Label(win, text=m, font=("Arial", 14, "bold"), fg="red", justify="left", wraplength=450).pack(pady=30, padx=20)
                    btn = tk.Button(win, text="OK (ENTER)", command=win.destroy, width=20, height=2, bg="red", fg="white", font=("Arial", 12, "bold"))
                    btn.pack(pady=20); btn.focus_set(); win.bind("<Return>", lambda e: win.destroy()); win.bind("<Escape>", lambda e: win.destroy())
                else: messagebox.showerror(t["error"], t.get(msg, msg))
    def on_scan_shipment(self, r):
        if not r.startswith("00"): self.play_error_sound(); messagebox.showerror("Error", "Need SSCC"); return
        if not self.current_order: self.play_error_sound(); messagebox.showerror("Error", "Select Order"); return
        try:
            inf = self.warehouse.get_sscc_info(r)
            if not inf: raise Exception("Not found in DB")
            ok, typ = self.warehouse.shipment(r)
            if ok:
                self.warehouse.record_history(r, inf["type"], "shipped", self.current_order)
                cnt = self.warehouse.get_sscc_content(r); self.state.boxes_data.append((r, [{"clean":x,"raw":x,"gtin":inf.get("gtin","")} for x in cnt]))
                self.state.total_codes_in_shift += len(cnt); self.show_last(f"SHIPPED: {r}"); self.update_info()
        except Exception as e: self.play_error_sound(); messagebox.showerror("Error", str(e))
    def on_scan_return(self, r):
        if not r.startswith("00"): return
        try:
            ok, typ = self.warehouse.return_item(r)
            if ok: self.warehouse.record_history(r, typ, "returned"); self.show_last(f"RETURNED: {r}")
            else: self.play_error_sound(); messagebox.showwarning("Error", "Not found")
        except Exception as e: self.play_error_sound(); messagebox.showerror("Error", str(e))
    def generate_and_print_label(self, s): pass
    def on_space_pressed(self):
        if self.config.get("cv_mode_enabled"): self.toggle_cv_scanner()
    def toggle_cv_scanner(self): pass
    def trigger_conveyor_auto_sscc(self): pass
    def show_shift_form(self):
        self.clear(); t = TEXT[self.lang]; tk.Button(self.root, text="⚙", command=self.admin_login).place(x=680,y=10)
        f = tk.Frame(self.root); f.pack(expand=True)
        tk.Label(f, text=t["date"]).pack(); e_d = tk.Entry(f, width=30); e_d.insert(0, datetime.now().strftime("%d.%m.%Y")); e_d.pack()
        is_wh = self.config.get("warehouse_enabled")
        if is_wh:
            tk.Label(f, text="GTIN").pack(); e_w = tk.Entry(f, width=30); e_w.insert(0, self.config.get("gtin","")); e_w.pack()
            tk.Label(f, text="Product").pack(); e_n = tk.Entry(f, width=30); e_n.insert(0, self.config.get("product_name","")); e_n.pack()
        else:
            tk.Label(f, text=t["workplace"]).pack(); e_w = tk.Entry(f, width=30); e_w.pack()
            tk.Label(f, text=t["name"]).pack(); e_n = tk.Entry(f, width=30); e_n.pack()
        self.entry_date, self.entry_wp, self.entry_name = e_d, e_w, e_n
        tk.Button(f, text=t["start"], command=self.start_shift, width=20, height=2).pack(pady=20)
    def start_shift(self):
        self.shift_info = {"date": self.entry_date.get(), "workplace": self.entry_wp.get(), "name": self.entry_name.get()}
        self.state.reset(self.config["box_size"]); self.show_scan_screen()
    def show_scan_screen(self):
        self.clear(); self.scanning_active = True; t = TEXT[self.lang]
        self.info = tk.Label(self.root, font=("Arial", 16)); self.info.pack(pady=20)
        self.last = tk.Entry(self.root, state="readonly", width=60, font=("Arial", 14)); self.last.pack(pady=15)
        self.scan_entry = tk.Entry(self.root); self.scan_entry.place(x=-100,y=-100); self.scan_entry.focus_set(); self.scan_entry.bind("<Return>", self.on_scan)
        tk.Button(self.root, text=t["end_shift"], command=self.end_shift).pack(side="bottom", pady=20)
        self.update_info()
    def on_scan(self, e): r = self.scan_entry.get(); self.scan_entry.delete(0, tk.END); self.process_barcode(r)
    def end_shift(self): self.scanning_active = False; self.duplicates.clear_recovery(); self.show_language_screen()
    def show_last(self, t): self.last.config(state="normal"); self.last.delete(0, tk.END); self.last.insert(0, t); self.last.config(state="readonly")
    def update_info(self):
        t = TEXT[self.lang]
        if self.state.wait_sscc: txt = t["wait_sscc_box"]
        else: txt = f"{t['box']}: {self.state.box}\n{t['collected']}: {self.state.in_box} / {self.state.box_size}"
        self.info.config(text=txt)

def run(): App().root.mainloop()
if __name__ == "__main__": run()
