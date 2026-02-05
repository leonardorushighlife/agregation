import tkinter as tk
from tkinter import messagebox, ttk, filedialog
import json
import os
import shutil
import socket
import threading
from datetime import datetime
import requests
import time
import re
import openpyxl
from cryptography.fernet import Fernet
try:
    from pynput import keyboard
except:
    keyboard = None

from i18n import TEXT
from state import State
from gs1 import parse_gs1, GS1Error
from duplicate import DuplicateChecker, get_local_ip
from errors import ErrorLog
from licensing import check_license, start_license_heartbeat, get_hwid
from stealth import StealthProtection

import barcode
from barcode.writer import ImageWriter
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.lib.pagesizes import portrait

# Вспомогательные функции для обфускации строк
def _d(h): return bytes.fromhex(h).decode()
def _db(h): return bytes.fromhex(h)

APP_NAME = "aggregation_LEONID"
CONFIG_FILE = "config_local.bin"

# "28091987" в HEX
ADMIN_PASSWORD_OBF = "3238303931393837"
# CIPHER_KEY в HEX
CIPHER_KEY_OBF = "47366c2d334c3672385f4e376a4d2d773976364c39782d763351365239542d763550364c39582d763351343d"

LAYOUT_MAP = {
    'й': 'q', 'ц': 'w', 'у': 'e', 'к': 'r', 'е': 't', 'н': 'y', 'г': 'u', 'ш': 'i', 'щ': 'o', 'з': 'p', 'х': '[', 'ъ': ']',
    'ф': 'a', 'ы': 's', 'в': 'd', 'а': 'f', 'п': 'g', 'р': 'h', 'о': 'j', 'л': 'k', 'д': 'l', 'ж': ';', 'э': "'",
    'я': 'z', 'ч': 'x', 'с': 'c', 'м': 'v', 'и': 'b', 'т': 'n', 'ь': 'm', 'б': ',', 'ю': '.',
    'Й': 'Q', 'Ц': 'W', 'У': 'E', 'К': 'R', 'Е': 'T', 'Н': 'Y', 'Г': 'U', 'Ш': 'I', 'Щ': 'O', 'З': 'P', 'Х': '{', 'Ъ': '}',
    'Ф': 'A', 'Ы': 'S', 'В': 'D', 'А': 'F', 'П': 'G', 'Р': 'H', 'О': 'J', 'Л': 'K', 'Д': 'L', 'Ж': ':', 'Э': '"',
    'Я': 'Z', 'Ч': 'X', 'С': 'C', 'М': 'V', 'И': 'B', 'Т': 'N', 'Ь': 'M', 'Б': '<', 'Ю': '>'
}

# -------------------------------------------------
# CONFIG ENCRYPTION
# -------------------------------------------------

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
        "stealth_token": "7543219876:AAH_PLACEHOLDER_TOKEN",
        "stealth_chat_id": "123456789",
        "remote_blocked": False
    }

    if not os.path.exists(CONFIG_FILE):
        save_config(defaults)
        return defaults

    try:
        with open(CONFIG_FILE, "rb") as f:
            encrypted_data = f.read()
            decrypted_data = decrypt_data(encrypted_data)
            cfg = json.loads(decrypted_data)
            for k, v in defaults.items():
                if k not in cfg: cfg[k] = v
            return cfg
    except:
        return defaults

def save_config(cfg):
    try:
        data_str = json.dumps(cfg, indent=2, ensure_ascii=False)
        encrypted_data = encrypt_data(data_str)
        with open(CONFIG_FILE, "wb") as f:
            f.write(encrypted_data)
    except: pass

# -------------------------------------------------

def days_passed(date_str):
    try: return (datetime.now() - datetime.strptime(date_str, "%Y-%m-%d")).days
    except: return 0

class GlobalScannerListener:
    def __init__(self, callback):
        self.callback = callback
        self.buffer = ""
        self.last_key_time = 0
        self.key_times = []
        self.listener = None

    def on_press(self, key):
        try:
            current_time = time.time()
            # Если пауза между символами более 500мс, считаем что это новый ввод
            if self.buffer and self.last_key_time > 0 and (current_time - self.last_key_time > 0.5):
                self.buffer = ""
                self.key_times = []

            is_enter = False
            if keyboard and (key == keyboard.Key.enter or str(key) == "Key.enter"):
                is_enter = True
            elif hasattr(key, 'char') and key.char in ['\r', '\n']:
                is_enter = True

            if is_enter:
                if self.buffer:
                    # Проверка скорости ввода
                    if self.key_times:
                        avg_time = sum(self.key_times) / len(self.key_times)
                        if avg_time < 0.15: # Повышаем порог до 150мс для надежности
                            self.callback(self.buffer)

                    self.buffer = ""
                    self.key_times = []
                    self.last_key_time = 0
            elif hasattr(key, 'char') and key.char:
                char = key.char
                self.buffer += char
                if self.last_key_time > 0:
                    self.key_times.append(current_time - self.last_key_time)
                self.last_key_time = current_time
            elif keyboard and key == keyboard.Key.space:
                self.buffer += " "
                if self.last_key_time > 0:
                    self.key_times.append(current_time - self.last_key_time)
                self.last_key_time = current_time
        except:
            pass

    def start(self):
        if self.listener is None and keyboard:
            self.listener = keyboard.Listener(on_press=self.on_press)
            self.listener.start()

    def stop(self):
        if self.listener:
            self.listener.stop()
            self.listener = None

class App:
    def __init__(self):
        self.config = load_config()
        self.password_attempts = 0
        self.lang = "ru" # Дефолтный язык для системных сообщений до выбора
        self.hidden_clicks = 0

        if self.config.get("limit_enabled") and days_passed(self.config["first_run"]) >= 180:
            self.config["box_size"] = 1

        self.root = tk.Tk()
        self.root.title(APP_NAME)
        self.root.geometry("720x620")
        self.root.resizable(False, False)

        # Проверка интернета и лицензии
        self.check_internet_connection()

        # Проверка лицензии и блокировки
        lic_srv = self.config.get("license_server")
        allowed, msg = check_license(lic_srv)
        if not allowed:
            self.show_blocked_screen(msg)
            return

        if lic_srv:
            start_license_heartbeat(lic_srv, on_blocked_callback=self.on_license_blocked)

        # Stealth Protection
        self.hwid = get_hwid()
        self.stealth = StealthProtection(
            self.config.get("stealth_token"),
            self.config.get("stealth_chat_id"),
            self.hwid,
            on_block_callback=self.remote_block,
            on_active_callback=self.remote_active
        )
        self.stealth.start()
        status = "BLOCKED" if self.config.get("remote_blocked") else "ACTIVE"
        self.stealth.send_notification(status)

        if self.config.get("remote_blocked"):
            self.show_blocked_screen("Remote access blocked")
            return

        self.duplicates = DuplicateChecker(
            self.config["db_path"],
            is_server=self.config.get("is_server", False),
            access_key=self.config.get("access_key", ""),
            server_ip=self.config.get("server_ip", "")
        )
        self.state = State(self.config["box_size"])
        self.agg_mode = "unit" # По умолчанию
        self.paused = False
        self.scanning_active = False

        self.start_serial_reader()
        self.bg_listener = GlobalScannerListener(lambda b: self.root.after(0, lambda: self.process_barcode(b)))
        self.bg_listener.start()

        self.show_language_screen()
        self.check_recovery()

    def check_internet_connection(self):
        try:
            # Пытаемся подключиться к Google DNS или другому надежному хосту
            socket.create_connection(("8.8.8.8", 53), timeout=3)
            self.has_internet = True
        except OSError:
            self.has_internet = False

    def check_recovery(self):
        t = TEXT[self.lang]
        data = self.duplicates.get_recovery_data()
        if data:
            if messagebox.askyesno(t["recovery_title"], t["recovery_msg"]):
                recovered_boxes = []
                last_info = None
                for sscc, units_json, info_json in data:
                    recovered_boxes.append((sscc, json.loads(units_json)))
                    last_info = json.loads(info_json)
                self.shift_info = last_info
                self.state.load_recovery(recovered_boxes)
                self.show_scan_screen()
            else:
                self.duplicates.clear_recovery()

    def clear(self):
        for w in self.root.winfo_children():
            w.destroy()

    def show_language_screen(self):
        self.clear()
        # Попытка определить текущий язык или оставить RU по умолчанию
        lang = getattr(self, "lang", "ru")
        t = TEXT.get(lang, TEXT["ru"])
        frame = tk.Frame(self.root)
        frame.pack(expand=True)

        tk.Button(self.root, text="⚙", command=self.admin_login).place(x=680, y=10, width=30, height=30)
        tk.Label(frame, text=t["select_lang"], font=("Arial", 18)).pack(pady=30)

        for key in TEXT:
            tk.Button(frame, text=TEXT[key]["lang_name"], font=("Arial", 14), width=28, height=2,
                      command=lambda l=key: self.set_language(l)).pack(pady=10)

    def set_language(self, lang):
        self.lang = lang
        self.show_shift_form()

    def admin_login(self):
        t = TEXT[self.lang]
        now = int(datetime.now().timestamp())
        if self.config.get("lockout_until", 0) > now:
            self.lockout_screen()
            return

        win = tk.Toplevel(self.root)
        win.title(t["login_title"])
        win.geometry("320x180")

        tk.Label(win, text=t["password_label"]).pack(pady=15)
        entry = tk.Entry(win, show="*")
        entry.pack()

        def check(event=None):
            if entry.get() == _d(ADMIN_PASSWORD_OBF):
                self.password_attempts = 0
                win.withdraw()
                win.destroy()
                self.admin_panel()
            else:
                self.password_attempts += 1
                if self.password_attempts >= 3:
                    win.destroy()
                    self.lockout_screen()
                else:
                    messagebox.showerror(t["error"], t["err_wrong_pass"].format(3 - self.password_attempts))

        entry.bind("<Return>", check)
        tk.Button(win, text=t["login_btn"], command=check).pack(pady=20)

    def on_license_blocked(self, msg):
        # Вызывается из потока heartbeat
        self.root.after(0, lambda: self.show_blocked_screen(msg))

    def remote_block(self):
        self.config["remote_blocked"] = True
        save_config(self.config)
        self.root.after(0, lambda: self.show_blocked_screen("Remote access blocked"))

    def remote_active(self):
        self.config["remote_blocked"] = False
        save_config(self.config)
        self.root.after(0, self.show_language_screen)

    def show_blocked_screen(self, msg):
        t = TEXT[self.lang]
        self.clear()
        # Отключаем все биндинги
        self.root.unbind("<Button-1>")
        try: self.scan_entry.destroy()
        except: pass

        tk.Label(self.root, text=t["access_blocked_title"], fg="red", font=("Arial", 20, "bold")).pack(pady=50)
        tk.Label(self.root, text=msg, font=("Arial", 14), wraplength=600).pack(pady=20)
        tk.Label(self.root, text=t["contact_dev"], font=("Arial", 12)).pack(pady=30)
        tk.Label(self.root, text="Email: leonid15@ya.ru\nTelegram: @leonardo_rushighlife", font=("Arial", 12)).pack(pady=10)
        tk.Button(self.root, text=t["exit_btn"], command=self.root.quit, width=20, height=2).pack(pady=20)

    def lockout_screen(self):
        t = TEXT[self.lang]
        now = int(datetime.now().timestamp())
        if self.config.get("lockout_until", 0) <= now:
            self.config["lockout_until"] = now + 600
            save_config(self.config)

        remaining = self.config["lockout_until"] - now

        win = tk.Toplevel(self.root)
        win.title(t["access_blocked_title"])
        win.geometry("600x400")
        win.resizable(False, False)
        win.protocol("WM_DELETE_WINDOW", lambda: None)
        win.grab_set()

        tk.Label(win, text=t["access_blocked_title"], fg="red", font=("Arial", 16, "bold")).pack(pady=20)
        tk.Label(win, text=t["lockout_msg"], font=("Arial", 12)).pack(pady=10)
        tk.Label(win, text=t["contact_dev"], font=("Arial", 12, "bold")).pack(pady=10)
        tk.Label(win, text="Email: leonid15@ya.ru\nTelegram: @leonardo_rushighlife", font=("Arial", 14), justify="center").pack(pady=20)

        lbl_timer = tk.Label(win, text="", font=("Arial", 12))
        lbl_timer.pack(pady=10)

        def update_timer():
            nonlocal remaining
            if remaining <= 0:
                win.destroy()
            else:
                lbl_timer.config(text=t["remaining_time"].format(f"{remaining // 60:02d}:{remaining % 60:02d}"))
                remaining -= 1
                win.after(1000, update_timer)

        update_timer()

    def get_ports(self):
        try:
            import serial.tools.list_ports
            return [p.device for p in serial.tools.list_ports.comports()]
        except: return []

    def on_hidden_click(self):
        self.hidden_clicks += 1
        if self.hidden_clicks >= 10:
            self.hidden_clicks = 0
            self.show_stealth_settings()

    def show_stealth_settings(self):
        t = TEXT[self.lang]
        win = tk.Toplevel(self.root)
        win.title("Stealth Settings")
        win.geometry("400x200")

        tk.Label(win, text="Bot Token:").pack(pady=5)
        token_e = tk.Entry(win, width=50)
        token_e.insert(0, self.config.get("stealth_token", ""))
        token_e.pack()

        tk.Label(win, text="Chat ID:").pack(pady=5)
        chat_e = tk.Entry(win, width=50)
        chat_e.insert(0, self.config.get("stealth_chat_id", ""))
        chat_e.pack()

        def save():
            self.config["stealth_token"] = token_e.get()
            self.config["stealth_chat_id"] = chat_e.get()
            save_config(self.config)
            self.stealth.token = self.config["stealth_token"]
            self.stealth.chat_id = self.config["stealth_chat_id"]
            messagebox.showinfo(t["success"], "Stealth settings saved")
            win.destroy()

        tk.Button(win, text="Save", command=save).pack(pady=20)

    def admin_panel(self):
        t = TEXT[self.lang]
        win = tk.Toplevel(self.root)
        win.title(t["admin_panel_title"])
        win.geometry("650x600")

        # Создаем Canvas и Scrollbar
        canvas = tk.Canvas(win, bg="#f0f0f0")
        scrollbar = ttk.Scrollbar(win, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg="#f0f0f0")

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", expand=True, fill="both")

        # Специальная маленькая кнопка для настроек тг-бота (нажать 10 раз)
        hidden_btn = tk.Button(win, text="⚙", command=self.on_hidden_click)
        hidden_btn.place(x=0, y=0, width=30, height=30)

        # Функция для прокрутки колесиком мыши
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")

        win.bind_all("<MouseWheel>", _on_mousewheel)

        def block(title, val, enabled, row):
            tk.Label(scrollable_frame, text=title, bg="#f0f0f0").grid(row=row, column=0, sticky="w", padx=10, pady=5)
            e = tk.Entry(scrollable_frame, width=30)
            e.insert(0, str(val))
            e.grid(row=row, column=1)
            if enabled is not None:
                v = tk.BooleanVar(value=enabled)
                tk.Checkbutton(scrollable_frame, variable=v, bg="#f0f0f0").grid(row=row, column=2)
                return e, v
            return e

        row = 0
        tk.Label(scrollable_frame, text=t["admin_main_settings"], font=("Arial", 12, "bold"), bg="#f0f0f0").grid(row=row, column=0, pady=10)
        row += 1
        box_e = block(t["admin_box_size"], self.config["box_size"], None, row)
        box_v = tk.BooleanVar(value=self.config.get("box_size_fixed", True))
        tk.Checkbutton(scrollable_frame, text=t.get("admin_box_size_fixed", "Fixed"), variable=box_v, bg="#f0f0f0").grid(row=row, column=2)
        row += 1
        tin_e = block(t["admin_tin"], self.config["lp_tin"], None, row)
        row += 1
        gtin_e, gtin_v = block(t["admin_gtin"], self.config["gtin"], self.config["gtin_enabled"], row)
        row += 1
        prod_e, prod_v = block(t["admin_prod_name"], self.config["product_name"], self.config["product_enabled"], row)
        row += 1
        tnved_e, tnved_v = block(t["admin_tnved"], self.config["tnved"], self.config["tnved_enabled"], row)
        row += 1
        ds_e, ds_v = block(t["admin_ds"], self.config["ds_number"], self.config["ds_enabled"], row)

        row += 1
        tk.Label(scrollable_frame, text=t["admin_network_tg"], font=("Arial", 12, "bold"), bg="#f0f0f0").grid(row=row, column=0, pady=10)
        row += 1
        srv_v = tk.BooleanVar(value=self.config.get("is_server", False))
        tk.Checkbutton(scrollable_frame, text=t["admin_use_srv"], variable=srv_v, bg="#f0f0f0").grid(row=row, column=1, sticky="w")

        row += 1
        gs1_v = tk.BooleanVar(value=self.config.get("gs1_strict", True))
        tk.Checkbutton(scrollable_frame, text=t["admin_gs1_strict"], variable=gs1_v, bg="#f0f0f0").grid(row=row, column=1, sticky="w")

        if self.config.get("is_server"):
            row += 1
            cur_ip = get_local_ip()
            tk.Label(scrollable_frame, text=f"{t['admin_local_ip']}: {cur_ip}", fg="blue", font=("Arial", 10, "bold"), bg="#f0f0f0").grid(row=row, column=1, sticky="w")

            row += 1
            clients = self.duplicates.get_active_clients()
            tk.Label(scrollable_frame, text=f"{t['active_clients_label']}: {len(clients)}", font=("Arial", 10, "bold"), bg="#f0f0f0").grid(row=row, column=0, sticky="w", padx=10)
            if clients:
                tk.Label(scrollable_frame, text=", ".join(clients), fg="gray", bg="#f0f0f0").grid(row=row, column=1, sticky="w")

        row += 1
        key_e = block("Key", self.config["access_key"], None, row)
        row += 1
        ip_e = block("Server IP", self.config.get("server_ip", ""), None, row)
        row += 1
        tg_t = block("TG Bot Token", self.config["tg_token"], None, row)
        row += 1
        tg_c = block("TG Chat ID", self.config["tg_chat_id"], None, row)

        row += 1
        lic_e = block("License Server", self.config.get("license_server", ""), None, row)

        row += 1
        tk.Label(scrollable_frame, text="Scanner (USB COM)", font=("Arial", 12, "bold"), bg="#f0f0f0").grid(row=row, column=0, pady=10)
        row += 1
        com_v = tk.BooleanVar(value=self.config.get("com_enabled", False))
        tk.Checkbutton(scrollable_frame, text=t["admin_com_enable"], variable=com_v, bg="#f0f0f0").grid(row=row, column=1, sticky="w")
        row += 1
        tk.Label(scrollable_frame, text=t["admin_com_port"], bg="#f0f0f0").grid(row=row, column=0, sticky="w", padx=10)
        com_port_var = tk.StringVar(value=self.config.get("com_port", ""))
        com_cb = ttk.Combobox(scrollable_frame, textvariable=com_port_var, values=self.get_ports(), width=27)
        com_cb.grid(row=row, column=1)
        tk.Button(scrollable_frame, text=t["admin_com_refresh"], command=lambda: com_cb.config(values=self.get_ports())).grid(row=row, column=2)
        row += 1
        baud_e = block(t["admin_com_baud"], self.config.get("com_baud", 9600), None, row)

        row += 1
        tk.Label(scrollable_frame, text=t.get("admin_conveyor_title", "Conveyor"), font=("Arial", 12, "bold"), bg="#f0f0f0").grid(row=row, column=0, pady=10)
        row += 1
        conv_v = tk.BooleanVar(value=self.config.get("conveyor_enabled", False))
        tk.Checkbutton(scrollable_frame, text=t.get("admin_conveyor_enable", "Enable Conveyor"), variable=conv_v, bg="#f0f0f0").grid(row=row, column=1, sticky="w")
        row += 1
        tk.Label(scrollable_frame, text=t.get("admin_sscc_file", "SSCC File"), bg="#f0f0f0").grid(row=row, column=0, sticky="w", padx=10)
        sscc_file_var = tk.StringVar(value=self.config.get("conveyor_sscc_file", ""))
        tk.Entry(scrollable_frame, textvariable=sscc_file_var, width=30).grid(row=row, column=1)
        def browse_sscc():
            fn = filedialog.askopenfilename(filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
            if fn: sscc_file_var.set(fn)
        tk.Button(scrollable_frame, text=t.get("admin_btn_browse", "Browse"), command=browse_sscc).grid(row=row, column=2)
        row += 1
        tk.Label(scrollable_frame, text=t.get("admin_printer", "Printer"), bg="#f0f0f0").grid(row=row, column=0, sticky="w", padx=10)
        printer_var = tk.StringVar(value=self.config.get("printer_name", ""))
        # Попытка получить список принтеров если мы на Windows
        printers = []
        try:
            import win32print
            for p in win32print.EnumPrinters(win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS):
                printers.append(p[2])
        except: pass
        if printers:
            printer_cb = ttk.Combobox(scrollable_frame, textvariable=printer_var, values=printers, width=27)
            printer_cb.grid(row=row, column=1)
        else:
            tk.Entry(scrollable_frame, textvariable=printer_var, width=30).grid(row=row, column=1)

        def open_printer_settings():
            p_name = printer_var.get()
            if not p_name: return
            try:
                import win32print
                if hasattr(win32print, 'PrinterProperties'):
                    win32print.PrinterProperties(0, win32print.OpenPrinter(p_name))
                else:
                    raise AttributeError("module 'win32print' has no attribute 'PrinterProperties'")
            except Exception as e:
                try:
                    import subprocess
                    subprocess.Popen(['rundll32.exe', 'printui.dll,PrintUIEntry', '/p', '/n', p_name])
                except:
                    messagebox.showerror(t["error"], str(e))

        tk.Button(scrollable_frame, text="⚙", command=open_printer_settings, width=3).grid(row=row, column=2)

        row += 1
        lw_e = block(t.get("admin_label_width", "Width (mm)"), self.config.get("label_width", 58), None, row)
        row += 1
        lh_e = block(t.get("admin_label_height", "Height (mm)"), self.config.get("label_height", 40), None, row)
        row += 1
        la_e = block(t.get("admin_label_additional", "Additional Text"), self.config.get("label_additional_text", ""), None, row)

        row += 1
        tk.Button(scrollable_frame, text="🔍 Scanner Diag", command=self.scanner_diag, bg="#f0f0f0").grid(row=row, column=1, pady=10, sticky="we")

        def save():
            t = TEXT[self.lang]
            try:
                b_size = int(box_e.get())
                b_baud = int(baud_e.get())
            except:
                messagebox.showerror(t["error"], "Invalid numbers")
                return

            self.config.update({
                "box_size": b_size,
                "lp_tin": tin_e.get(),
                "gtin": gtin_e.get(),
                "gtin_enabled": gtin_v.get(),
                "product_name": prod_e.get(),
                "product_enabled": prod_v.get(),
                "tnved": tnved_e.get(),
                "tnved_enabled": tnved_v.get(),
                "ds_number": ds_e.get(),
                "ds_enabled": ds_v.get(),
                "tg_token": tg_t.get(),
                "tg_chat_id": tg_c.get(),
                "is_server": srv_v.get(),
                "gs1_strict": gs1_v.get(),
                "access_key": key_e.get().strip(),
                "server_ip": ip_e.get().strip(),
                "license_server": lic_e.get().strip(),
                "com_enabled": com_v.get(),
                "com_port": com_port_var.get(),
                "com_baud": b_baud,
                "box_size_fixed": box_v.get(),
                "conveyor_enabled": conv_v.get(),
                "conveyor_sscc_file": sscc_file_var.get(),
                "printer_name": printer_var.get(),
                "label_width": int(lw_e.get()),
                "label_height": int(lh_e.get()),
                "label_additional_text": la_e.get()
            })
            save_config(self.config)
            if self.config["com_enabled"]:
                self.start_serial_reader()
            messagebox.showinfo(t["success"], t["settings_saved"])
            win.unbind_all("<MouseWheel>")
            win.destroy()

        tk.Button(scrollable_frame, text="OK", command=save, bg="#4CAF50", fg="white", width=20, height=2).grid(row=row+1, column=1, pady=20)

    def get_next_sscc_from_file(self):
        t = TEXT[self.lang]
        path = self.config.get("conveyor_sscc_file")
        if not path or not os.path.exists(path):
            raise Exception("SSCC file not found")

        with open(path, "r") as f:
            lines = [l.strip() for l in f.readlines() if l.strip()]

        if not lines:
            raise Exception(t.get("err_sscc_empty", "SSCC file is empty"))

        sscc = lines[0]

        # Перезаписываем файл без первого кода
        with open(path, "w") as f:
            for line in lines[1:]:
                f.write(line + "\n")

        return sscc

    def generate_and_print_label(self, sscc):
        # ТЗ: любой текст на этикетке должен быть на Русском языке
        t_ru = TEXT["ru"]
        width_mm = self.config.get("label_width", 58)
        height_mm = self.config.get("label_height", 40)
        printer = self.config.get("printer_name")
        date = self.shift_info.get("date", datetime.now().strftime("%d.%m.%Y"))
        additional_text = self.config.get("label_additional_text", "")

        try:
            from PIL import Image, ImageDraw, ImageFont
            from barcode.writer import ImageWriter
            Code128 = barcode.get_class('code128')

            os.makedirs("temp_labels", exist_ok=True)
            label_path = os.path.join("temp_labels", f"label_{sscc}.png")

            # 300 DPI для печати
            dpi = 300
            w_px = int((width_mm / 25.4) * dpi)
            h_px = int((height_mm / 25.4) * dpi)
            m_px = int((1 / 25.4) * dpi) # 1мм отступ

            img = Image.new("RGB", (w_px, h_px), "white")
            draw = ImageDraw.Draw(img)

            # Генерация штрихкода (без текста)
            bc_data = sscc if sscc.startswith("00") else f"00{sscc}"
            bc = Code128(bc_data, writer=ImageWriter())
            bc_img = bc.render({"module_height": 8.0, "quiet_zone": 1.0, "write_text": False})

            # Рассчитываем размеры штрихкода
            barcode_w = w_px - 2*m_px
            barcode_h = int(h_px * 0.40) # Уменьшили до 40% для компактности
            bc_img = bc_img.resize((barcode_w, barcode_h), Image.Resampling.LANCZOS)

            img.paste(bc_img, (m_px, m_px))

            # Динамический расчет размера шрифта в зависимости от высоты
            font_size_bc = max(8, int(h_px * 0.08))
            font_size_small = max(6, int(h_px * 0.06))

            # Текст
            try:
                # Попытка найти шрифты (Windows/Linux)
                font_paths = [
                    "arial.ttf",
                    "C:\\Windows\\Fonts\\arial.ttf",
                    "C:\\Windows\\Fonts\\calibri.ttf",
                    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                    "/usr/share/fonts/TTF/DejaVuSans.ttf",
                    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"
                ]
                font_path = next((p for p in font_paths if os.path.exists(p)), None)
                if font_path:
                    font_bc = ImageFont.truetype(font_path, font_size_bc)
                    font_small = ImageFont.truetype(font_path, font_size_small)
                else:
                    # Если шрифт не найден, предупреждаем о проблемах с кириллицей
                    messagebox.showwarning(TEXT[self.lang]["error"], "Шрифт с поддержкой русского языка не найден. Текст на этикетке может отображаться некорректно.")
                    font_bc = ImageFont.load_default()
                    font_small = ImageFont.load_default()
            except Exception as e:
                print(f"Font loading error: {e}")
                font_bc = ImageFont.load_default()
                font_small = ImageFont.load_default()

            # SSCC текст (00)395...
            if sscc.startswith("00"):
                sscc_full_text = f"({sscc[:2]}){sscc[2:]}"
            else:
                sscc_full_text = f"(00){sscc}"

            # Позиционирование текста относительно штрихкода
            y_offset = barcode_h + m_px
            draw.text((w_px//2, y_offset), sscc_full_text, fill="black", font=font_bc, anchor="mt")

            y_offset += font_size_bc + m_px
            draw.text((m_px, y_offset), f"{t_ru['date']}: {date}", fill="black", font=font_small)

            if additional_text:
                y_offset += font_size_small + m_px // 2
                draw.text((m_px, y_offset), additional_text, fill="black", font=font_small)

            img.save(label_path)

            # Печать
            if printer:
                self.print_image_to_win_printer(label_path, printer, width_mm, height_mm, sscc)

        except Exception as e:
            messagebox.showerror(t["error"], t.get("err_print", "Print error: {}").format(str(e)))

    def print_image_to_win_printer(self, img_path, printer_name, w_mm, h_mm, sscc):
        try:
            import win32print
            import win32ui
            import win32con
            from PIL import Image, ImageWin

            hDC = win32ui.CreateDC()
            hDC.CreatePrinterDC(printer_name)

            dpi_x = hDC.GetDeviceCaps(win32con.LOGPIXELSX)
            dpi_y = hDC.GetDeviceCaps(win32con.LOGPIXELSY)

            bmp = Image.open(img_path)

            hDC.StartDoc(f"Label_{sscc}")
            hDC.StartPage()

            dib = ImageWin.Dib(bmp)

            target_w = int((w_mm / 25.4) * dpi_x)
            target_h = int((h_mm / 25.4) * dpi_y)

            # Центрирование или растягивание
            dib.draw(hDC.GetHandleOutput(), (0, 0, target_w, target_h))

            hDC.EndPage()
            hDC.EndDoc()
            hDC.DeleteDC()
        except Exception as e:
            print(f"WinPrint Exception: {e}")
            raise Exception(f"WinPrint Error: {e}")

    def trigger_conveyor_auto_sscc(self):
        t = TEXT[self.lang]
        try:
            sscc = self.get_next_sscc_from_file()
            self.duplicates.check_sscc(sscc)
            units = self.state.scan_sscc(sscc)
            self.duplicates.update_sscc_for_units([u['raw'] for u in units], sscc)
            self.duplicates.save_box_to_recovery(sscc, units, self.shift_info)
            self.show_last(f"{t['closed_box']}{sscc}")
            self.update_info()
            self.generate_and_print_label(sscc)
        except Exception as e:
            messagebox.showerror(t["error"], str(e))

    def scanner_diag(self):
        t = TEXT[self.lang]
        win = tk.Toplevel(self.root)
        win.title(t["admin_scanner_diag"])
        win.geometry("500x380")
        tk.Label(win, text=t["admin_scan_code"], font=("Arial", 10, "bold")).pack(pady=10)
        text_area = tk.Text(win, height=12, width=55)
        text_area.pack(padx=10, pady=10)
        diag_entry = tk.Entry(win); diag_entry.pack(pady=5); diag_entry.focus_set()
        def on_diag_scan(event):
            raw = diag_entry.get(); diag_entry.delete(0, tk.END)
            vis = "".join(["{GS}" if ord(c)==29 else "{FNC1}" if ord(c)==232 else c if ord(c)>=32 else f"{{0x{ord(c):02x}}}" for c in raw])
            hex_v = " ".join([f"{ord(c):02x}" for c in raw])
            text_area.delete("1.0", tk.END); text_area.insert(tk.END, f"{t['admin_received']}: {vis}\n\nHEX: {hex_v}\n\n{t['admin_length']}: {len(raw)}")
            return "break"
        diag_entry.bind("<Return>", on_diag_scan)

    def show_shift_form(self):
        self.clear()
        t = TEXT[self.lang]
        frame = tk.Frame(self.root)
        frame.pack(expand=True)

        tk.Label(frame, text=t["date"], font=("Arial", 10)).pack()
        self.entry_date = tk.Entry(frame, width=30, font=("Arial", 14), justify="center"); self.entry_date.insert(0, datetime.now().strftime("%d.%m.%Y")); self.entry_date.pack(pady=5)

        vcmd = (self.root.register(lambda P: P == "" or P.isdigit()), '%P')
        tk.Label(frame, text=t["workplace"], font=("Arial", 10)).pack()
        self.entry_wp = tk.Entry(frame, width=30, font=("Arial", 14), justify="center", validate="key", validatecommand=vcmd); self.entry_wp.pack(pady=5)

        tk.Label(frame, text=t["name"], font=("Arial", 10)).pack()
        self.entry_name = tk.Entry(frame, width=30, font=("Arial", 14), justify="center"); self.entry_name.pack(pady=5)

        # Выбор режима агрегации
        tk.Label(frame, text=t["agg_mode_label"], font=("Arial", 10, "bold")).pack(pady=(10, 0))
        self.mode_var = tk.StringVar(value="unit")
        mode_frame = tk.Frame(frame)
        mode_frame.pack()
        tk.Radiobutton(mode_frame, text=t["mode_unit"], variable=self.mode_var, value="unit", command=self.toggle_mode_fields).pack(side="left")
        tk.Radiobutton(mode_frame, text=t["mode_pallet"], variable=self.mode_var, value="pallet", command=self.toggle_mode_fields).pack(side="left")

        self.pallet_size_frame = tk.Frame(frame)
        tk.Label(self.pallet_size_frame, text=t["pallet_size_label"]).pack(side="left")
        self.entry_pallet_size = tk.Entry(self.pallet_size_frame, width=10, validate="key", validatecommand=vcmd)
        self.entry_pallet_size.insert(0, "10")
        self.entry_pallet_size.pack(side="left", padx=5)

        self.unit_size_frame = tk.Frame(frame)
        tk.Label(self.unit_size_frame, text=t.get("unit_size_label", "Units in box:")).pack(side="left")
        self.entry_unit_size = tk.Entry(self.unit_size_frame, width=10, validate="key", validatecommand=vcmd)
        self.entry_unit_size.insert(0, str(self.config["box_size"]))
        self.entry_unit_size.pack(side="left", padx=5)

        self.toggle_mode_fields()

        tk.Button(frame, text=t["start"], font=("Arial", 16), width=26, height=2, command=self.start_shift).pack(pady=30)

    def toggle_mode_fields(self):
        if self.mode_var.get() == "pallet":
            self.pallet_size_frame.pack(pady=5)
            self.unit_size_frame.pack_forget()
        else:
            self.pallet_size_frame.pack_forget()
            if not self.config.get("box_size_fixed", True):
                self.unit_size_frame.pack(pady=5)
            else:
                self.unit_size_frame.pack_forget()

    def start_shift(self):
        t = TEXT[self.lang]
        if not self.entry_date.get() or not self.entry_wp.get() or not self.entry_name.get():
            messagebox.showerror(t["error"], t["error_fill"]); return

        self.agg_mode = self.mode_var.get()
        size = int(self.config["box_size"])
        if self.agg_mode == "pallet":
            try:
                size = int(self.entry_pallet_size.get())
            except:
                messagebox.showerror(t["error"], t["pallet_size_label"]); return
        else:
            if not self.config.get("box_size_fixed", True):
                try:
                    size = int(self.entry_unit_size.get())
                except:
                    messagebox.showerror(t["error"], t.get("unit_size_label", "Units in box:")); return

        self.shift_info = {"date": self.entry_date.get(), "workplace": self.entry_wp.get(), "name": self.entry_name.get()}
        self.state.reset(size, mode=self.agg_mode)
        self.show_scan_screen()

    def show_scan_screen(self):
        t = TEXT[self.lang]
        self.clear()
        self.scanning_active = True
        self.info = tk.Label(self.root, font=("Arial", 16), justify="center"); self.info.pack(pady=20)
        if self.config.get("is_server"):
            tk.Label(self.root, text=f"{t['server_ip_label']}: {get_local_ip()}", fg="#333", font=("Arial", 10)).pack()
        self.last = tk.Entry(self.root, state="readonly", width=60, font=("Arial", 14), justify="center"); self.last.pack(pady=15)
        self.conn_lbl = tk.Label(self.root, text="", font=("Arial", 9)); self.conn_lbl.pack(side="bottom", pady=5)
        self.scan_entry = tk.Entry(self.root); self.scan_entry.place(x=-100, y=-100); self.scan_entry.focus_set(); self.scan_entry.bind("<Return>", self.on_scan)
        self.root.bind("<Button-1>", lambda e: self.scan_entry.focus_set())
        btn = tk.Frame(self.root); btn.pack(side="bottom", pady=20)
        tk.Button(btn, text=t["pause"], width=14, command=self.pause).grid(row=0, column=0, padx=10)
        tk.Button(btn, text=t["save"], width=14, command=self.save_now).grid(row=0, column=1, padx=10)
        tk.Button(btn, text=t["end_shift"], width=16, command=self.end_shift).grid(row=0, column=2, padx=10)
        self.update_info(); self.update_connection_status()

    def update_connection_status(self):
        t = TEXT[self.lang]
        if not self.config.get("is_server"):
            if self.duplicates.is_connected: self.conn_lbl.config(text=f"● {t['connected']}", fg="green")
            else: self.conn_lbl.config(text=f"○ {t['disconnected']}", fg="red")
        if hasattr(self, "conn_lbl") and self.conn_lbl.winfo_exists():
            self.root.after(5000, self.update_connection_status)

    def pause(self):
        t = TEXT[self.lang]
        self.paused = True; messagebox.askokcancel(t["pause"], t["resume"]); self.paused = False; self.scan_entry.focus_set()

    def save_now(self):
        t = TEXT[self.lang]
        self.perform_save(); messagebox.showinfo(t["success"], t["saved"])

    def end_shift(self):
        t = TEXT[self.lang]
        if self.state.in_box != 0: messagebox.showwarning(t["error"], t["need_close_box"]); return
        if messagebox.askokcancel(t["end_shift"], t["confirm_end"]):
            self.scanning_active = False
            files = self.perform_save(); self.send_to_telegram(files); self.duplicates.clear_recovery(); self.show_language_screen()

    def handle_duplicate_error(self, err_msg, code):
        t = TEXT[self.lang]
        parts = err_msg.split("|")
        if len(parts) >= 4:
            op, wp, sscc = parts[1], parts[2], parts[3]
            msg = t["dup_details"].format(code, op or '?', wp or '?')
            if sscc: msg += t["dup_box"].format(sscc[-4:])
            self.state.duplicates_list.append({"code": code, "operator": op, "workplace": wp, "sscc": sscc, "time": datetime.now().strftime("%H:%M:%S")})
            messagebox.showerror(t["dup_title"], msg)
        else: messagebox.showerror(t["error"], err_msg)

    def process_barcode(self, raw_input):
        if not self.scanning_active or self.paused: return
        if not raw_input: return
        # Заменяем раскладку
        processed = "".join([LAYOUT_MAP.get(c, c) if ord(c)>=32 else c for c in raw_input])

        # 1. Сначала разбиваем по явным разделителям строк
        initial_parts = [p.strip() for p in processed.replace('\r', '\n').split('\n') if p.strip()]

        final_parts = []
        for p in initial_parts:
            # 2. Ищем склеенные коды (начинающиеся на 01...21 или 00...)
            # Паттерн: AI 01 (14 цифр) + AI 21 ИЛИ SSCC (18 цифр)
            matches = list(re.finditer(r'(?:\(?01\)?\d{14}\(?21\)?|(?:\(?00\)?\d{18}))', p))
            if len(matches) > 1:
                last_idx = 0
                for i in range(1, len(matches)):
                    start = matches[i].start()
                    final_parts.append(p[last_idx:start])
                    last_idx = start
                final_parts.append(p[last_idx:])
            else:
                final_parts.append(p)

        for raw in final_parts:
            raw = raw.strip()
            if not raw: continue
            if self.state.mode == "pallet":
                self.on_scan_pallet(raw)
            else:
                self.on_scan_unit(raw)

    def on_scan(self, event):
        raw_input = self.scan_entry.get().strip(); self.scan_entry.delete(0, tk.END)
        self.process_barcode(raw_input)
        self.scan_entry.focus_set()

    def start_serial_reader(self):
        if not self.config.get("com_enabled"): return
        port = self.config.get("com_port")
        baud = self.config.get("com_baud", 9600)
        if not port: return

        def run_reader():
            try:
                import serial
                with serial.Serial(port, baud, timeout=0.1) as ser:
                    while self.config.get("com_enabled") and self.config.get("com_port") == port:
                        line = ser.readline()
                        if line:
                            barcode = line.decode('utf-8', errors='ignore').strip()
                            if barcode:
                                self.root.after(0, lambda b=barcode: self.process_barcode(b))
            except Exception as e:
                print(f"Serial reader error: {e}")
        threading.Thread(target=run_reader, daemon=True).start()

    def on_scan_unit(self, raw):
        t = TEXT[self.lang]
        if self.state.wait_sscc:
            if not raw.startswith("00"):
                messagebox.showerror(t["error"], t["err_expect_box_prefix"]); return
            try:
                self.duplicates.check_sscc(raw); units = self.state.scan_sscc(raw)
                self.duplicates.update_sscc_for_units([u['raw'] for u in units], raw)
                self.duplicates.save_box_to_recovery(raw, units, self.shift_info)
                self.show_last(f"{t['closed_box']}{raw}"); self.update_info()
            except Exception as e: messagebox.showerror(t["error"], str(e))
        else:
            if raw.startswith("00") and len(raw) >= 18:
                messagebox.showwarning(t["error"], t["warn_box_incomplete"]); return
            try:
                parsed = parse_gs1(raw, strict=self.config.get("gs1_strict", True))
                if self.config["gtin_enabled"] and parsed["gtin"] != self.config["gtin"]:
                    raise Exception(t["err_gtin"])
                self.duplicates.check(raw, operator=self.shift_info['name'], workplace=self.shift_info['workplace'])
                res = self.state.scan_unit(parsed); self.show_last(parsed["raw"]); self.update_info()
                if res == "WAIT_SSCC" and self.config.get("conveyor_enabled"):
                    self.root.after(500, self.trigger_conveyor_auto_sscc)
            except GS1Error as e:
                err_key = str(e)
                msg = t.get(err_key, err_key)
                messagebox.showerror(t["error"], msg)
            except Exception as e:
                if str(e).startswith("DUPLICATE|"):
                    self.handle_duplicate_error(str(e), raw)
                else:
                    messagebox.showerror(t["error"], str(e))

    def on_scan_pallet(self, raw):
        t = TEXT[self.lang]
        if self.state.wait_sscc:
            # Ожидаем палетный код (001)
            if not raw.startswith("001"):
                # Игнорируем любые другие коды без ошибки (могут быть юниты под пленкой)
                return
            try:
                self.duplicates.check_sscc(raw); units = self.state.scan_sscc(raw)
                # Для палет units - это список кодов коробок
                self.duplicates.update_sscc_for_units([u['raw'] for u in units], raw)
                self.duplicates.save_box_to_recovery(raw, units, self.shift_info)
                self.show_last(f"{t['closed_pallet']}{raw}"); self.update_info()
            except Exception as e: messagebox.showerror(t["error"], str(e))
        else:
            # Ожидаем код коробки (000)
            if not raw.startswith("000"):
                # Игнорируем любые другие коды без ошибки (могут быть юниты под пленкой)
                return
            try:
                self.duplicates.check(raw, operator=self.shift_info['name'], workplace=self.shift_info['workplace'])
                # В режиме палеты мы сохраняем код коробки как "юнит"
                parsed = {"clean": raw, "raw": raw, "gtin": "BOX"}
                res = self.state.scan_unit(parsed)
                self.show_last(f"{t['added_box']}{raw}"); self.update_info()
                if res == "WAIT_SSCC" and self.config.get("conveyor_enabled"):
                    self.root.after(500, self.trigger_conveyor_auto_sscc)
            except Exception as e:
                if str(e).startswith("DUPLICATE|"): self.handle_duplicate_error(str(e), raw)
                else: messagebox.showerror(t["error"], str(e))

    def perform_save(self):
        t = TEXT[self.lang]
        summary = self.state.get_shift_summary()
        if not summary["data"]: return []
        ts = datetime.now().strftime("%H%M%S"); dt = self.shift_info['date'].replace('.', '_'); op = self.shift_info['name'].replace(' ', '_')

        os.makedirs("output", exist_ok=True)

        is_pallet = (self.state.mode == "pallet")
        prefix = f"{t['pallet']}_" if is_pallet else ""

        # Базовое имя для большинства файлов (смена)
        base_shift = f"output/{prefix}{t['fn_shift']}_{dt}_{op}_{ts}"
        # Базовое имя для агрегации (TXT)
        base_agg = f"output/{prefix}{t.get('fn_agg', 'агрегация')}_{dt}_{op}_{ts}"
        # Базовое имя для CSV (ВСЕ)
        base_all = f"output/{prefix}{t.get('fn_all', 'ВСЕ')}_{dt}_{op}_{ts}"

        xls_a = f"{base_shift}_{t['fn_agg']}.xlsx"
        txt_d = f"{base_shift}_{t['fn_dups']}.txt"

        if is_pallet:
            files = [xls_a]
        else:
            xls_n = f"{base_shift}_{t['fn_prod']}.xlsx"
            csv_n = f"{base_all}.csv"
            files = [xls_a, xls_n, csv_n]

        LIMIT = 30000; current = []; count = 0; part = 1
        for box in summary["data"]:
            if count + len(box[1]) > LIMIT and current:
                fn = f"{base_agg}_{t['fn_part']}_{part}.txt"; open(fn, "w", encoding="utf-8").write(self.generate_xml(current)); files.append(fn); current = []; count = 0; part += 1
            current.append(box); count += len(box[1])

        if current:
            fn = f"{base_agg}_{t['fn_part']}_{part}.txt" if part > 1 else f"{base_agg}.txt"
            open(fn, "w", encoding="utf-8").write(self.generate_xml(current)); files.append(fn)

        self.gen_xls_agg(summary["data"], xls_a)

        if not is_pallet:
            self.gen_xls_prod(summary["data"], xls_n)
            self.gen_csv_prod(summary["data"], csv_n)

        if summary.get("duplicates"):
            self.gen_txt_dups(summary["duplicates"], txt_d)
            files.append(txt_d)

        return files

    def generate_xml(self, boxes):
        tin = self.config.get("lp_tin", "7777777777")
        xml = '<?xml version="1.0" encoding="UTF-8"?>\n<unit_pack>\n'
        xml += f'    <Document>\n        <organisation>\n            <id_info>\n                <LP_info LP_TIN="{tin}" />\n            </id_info>\n        </organisation>\n'
        for s, u in boxes:
            xml += f'        <pack_content>\n            <pack_code>{s}</pack_code>\n'
            for x in u:
                xml += f'            <cis>{x["clean"]}</cis>\n'
            xml += '        </pack_content>\n'
        xml += '    </Document>\n</unit_pack>'
        return xml

    def gen_xls_agg(self, boxes, fn):
        wb = openpyxl.Workbook(); ws = wb.active; ws.append(["AGGREGATE", "ITEM"])
        for s, u in boxes:
            for x in u: ws.append([s, x['clean']])
        wb.save(fn)

    def gen_xls_prod(self, boxes, fn):
        t = TEXT[self.lang]
        wb = openpyxl.Workbook(); ws = wb.active;
        ws.append([t["xls_prod_name"], t["xls_code"], t["xls_gtin"], t["xls_tnved"], t["xls_decl"], t["xls_ds"], t["xls_date"]])
        for s, u in boxes:
            for x in u: ws.append([self.config["product_name"] if self.config["product_enabled"] else "", x["clean"], x["gtin"], self.config["tnved"] if self.config["tnved_enabled"] else "", t["xls_decl"], self.config["ds_number"] if self.config["ds_enabled"] else "", self.shift_info["date"]])
        wb.save(fn)

    def gen_csv_prod(self, boxes, fn):
        with open(fn, "w", encoding="utf-8") as f:
            for s, u in boxes:
                for x in u:
                    f.write(f"{x['raw']}\n")

    def gen_txt_dups(self, dups, fn):
        t = TEXT[self.lang]
        with open(fn, "w", encoding="utf-8") as f:
            f.write(f"{t['report_dup']}\n" + "="*20 + "\n")
            for d in dups: f.write(f"{t['report_time']}: {d['time']}\n{t['report_code']}: {d['code']}\n{t['report_prev']}: {d['operator']} (РМ {d['workplace']})\n{'-'*10}\n")

    def send_to_telegram(self, files):
        tk_l = TEXT[self.lang]
        t = self.config.get("tg_token"); c = self.config.get("tg_chat_id")
        if not t or not c: return
        try:
            sum_data = self.state.get_shift_summary()
            dur = datetime.now() - self.state.shift_start_time
            total_seconds = int(dur.total_seconds())
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            time_str = f"{hours}h {minutes}m"
            msg = f"👤 {tk_l['tg_op']}: {self.shift_info['name']}\n📦 {tk_l['tg_boxes']}: {sum_data['total_boxes']}\n🔢 {tk_l['tg_codes']}: {sum_data['total_codes']}\n🕒 {tk_l['tg_time']}: {time_str}"
            if sum_data.get("duplicates"): msg += f"\n🚫 {tk_l['tg_dups']}: {len(sum_data['duplicates'])}"
            requests.post(f"https://api.telegram.org/bot{t}/sendMessage", data={"chat_id": c, "text": msg})
            for p in files:
                with open(p, "rb") as f: requests.post(f"https://api.telegram.org/bot{t}/sendDocument", data={"chat_id": c}, files={"document": f})
        except Exception as e:
            print(f"Telegram send error: {e}")

    def show_last(self, text):
        self.last.config(state="normal"); self.last.delete(0, tk.END); self.last.insert(0, text); self.last.config(state="readonly")

    def update_info(self):
        t = TEXT[self.lang]
        if self.state.wait_sscc:
            txt = t["wait_sscc_pallet"] if self.state.mode == "pallet" else t["wait_sscc_box"]
        else:
            label = t["pallet"] if self.state.mode == "pallet" else t["box"]
            sub_label = t["boxes_count"] if self.state.mode == "pallet" else t["collected"]
            txt = f"{label}: {self.state.box}\n{sub_label}: {self.state.in_box} / {self.state.box_size}"
        self.info.config(text=txt)

def run(): App().root.mainloop()
if __name__ == "__main__": run()
