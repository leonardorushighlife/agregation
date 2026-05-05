import tkinter as tk
from tkinter import messagebox, ttk
import json
import os
import socket
from datetime import datetime

try:
    import socks
except ImportError:
    socks = None

_ORIGINAL_SOCKET = socket.socket

from i18n import TEXT
from state import State
from gs1 import parse_gs1
from duplicate import DuplicateChecker
from errors import ErrorLog


APP_NAME = "aggregation_LEONID"
CONFIG_FILE = "config_local.json"
ADMIN_PASSWORD = "28091987"
FNC1 = "\x1d"


# -------------------------------------------------
# CONFIG
# -------------------------------------------------

def load_config():
    if not os.path.exists(CONFIG_FILE):
        cfg = {
            "first_run": datetime.now().strftime("%Y-%m-%d"),
            "limit_enabled": True,
            "box_size": 24,

            "gtin": "",
            "gtin_enabled": False,

            "product_name": "",
            "product_enabled": False,

            "tnved": "",
            "tnved_enabled": False,

            "ds_number": "",
            "ds_enabled": False,

            "proxy_enabled": False,
            "proxy_type": "SOCKS5",
            "proxy_host": "",
            "proxy_port": "",
            "proxy_user": "",
            "proxy_pass": ""
        }
        save_config(cfg)
        return cfg

    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_config(cfg):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)


def apply_proxy(cfg):
    if not cfg.get("proxy_enabled") or not socks:
        socket.socket = _ORIGINAL_SOCKET
        return

    ptype = socks.SOCKS5 if cfg.get("proxy_type") == "SOCKS5" else socks.HTTP
    try:
        port_str = str(cfg.get("proxy_port", "0"))
        port = int(port_str) if port_str.isdigit() else 0
        if port == 0:
            socket.socket = _ORIGINAL_SOCKET
            return

        socks.set_default_proxy(
            ptype,
            cfg.get("proxy_host"),
            port,
            username=cfg.get("proxy_user"),
            password=cfg.get("proxy_pass")
        )
        socket.socket = socks.socksocket
    except:
        socket.socket = _ORIGINAL_SOCKET


def days_passed(date_str):
    start = datetime.strptime(date_str, "%Y-%m-%d")
    return (datetime.now() - start).days


# -------------------------------------------------
# MAIN APP
# -------------------------------------------------

class App:
    def __init__(self):
        self.config = load_config()
        apply_proxy(self.config)

        if self.config["limit_enabled"]:
            if days_passed(self.config["first_run"]) >= 180:
                self.config["box_size"] = 5
                save_config(self.config)

        self.lang = None
        self.state = State(self.config["box_size"])
        self.paused = False

        self.duplicates = DuplicateChecker()
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
        win.geometry("560x700")
        win.resizable(False, False)

        canvas = tk.Canvas(win)
        scrollbar = ttk.Scrollbar(win, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        def block(parent, title, value, enabled, row):
            tk.Label(parent, text=title, anchor="w").grid(row=row, column=0, sticky="w", padx=10, pady=5)
            e = tk.Entry(parent, width=30)
            e.insert(0, value)
            e.grid(row=row, column=1, padx=5)
            v = tk.BooleanVar(value=enabled)
            tk.Checkbutton(parent, variable=v).grid(row=row, column=2)
            return e, v

        row = 0
        tk.Label(scrollable_frame, text="Box size (5–200)").grid(row=row, column=0, padx=10, pady=5, sticky="w")
        box_entry = tk.Entry(scrollable_frame, width=10)
        box_entry.insert(0, str(self.config["box_size"]))
        box_entry.grid(row=row, column=1, sticky="w")

        limit_var = tk.BooleanVar(value=self.config["limit_enabled"])
        tk.Checkbutton(scrollable_frame, text="Enable 180 days limit", variable=limit_var)\
            .grid(row=row, column=2, padx=10)

        row += 1
        gtin_e, gtin_v = block(scrollable_frame, "GTIN", self.config["gtin"], self.config["gtin_enabled"], row)
        row += 1
        prod_e, prod_v = block(scrollable_frame, "Product name", self.config["product_name"], self.config["product_enabled"], row)
        row += 1
        tnved_e, tnved_v = block(scrollable_frame, "TN VED", self.config["tnved"], self.config["tnved_enabled"], row)
        row += 1
        ds_e, ds_v = block(scrollable_frame, "DS number", self.config["ds_number"], self.config["ds_enabled"], row)

        row += 1
        tk.Label(scrollable_frame, text="--- Proxy / VPN Settings ---", font=("Arial", 10, "bold")).grid(row=row, column=0, columnspan=3, pady=15)

        row += 1
        tk.Label(scrollable_frame, text="Proxy Enabled").grid(row=row, column=0, sticky="w", padx=10)
        proxy_enabled_v = tk.BooleanVar(value=self.config.get("proxy_enabled", False))
        tk.Checkbutton(scrollable_frame, variable=proxy_enabled_v).grid(row=row, column=1, sticky="w")

        row += 1
        tk.Label(scrollable_frame, text="Proxy Type").grid(row=row, column=0, sticky="w", padx=10)
        proxy_type_cb = ttk.Combobox(scrollable_frame, values=["SOCKS5", "HTTP"], width=10)
        proxy_type_cb.set(self.config.get("proxy_type", "SOCKS5"))
        proxy_type_cb.grid(row=row, column=1, sticky="w")

        row += 1
        tk.Label(scrollable_frame, text="Host").grid(row=row, column=0, sticky="w", padx=10)
        proxy_host_e = tk.Entry(scrollable_frame, width=30)
        proxy_host_e.insert(0, self.config.get("proxy_host", ""))
        proxy_host_e.grid(row=row, column=1, sticky="w")

        row += 1
        tk.Label(scrollable_frame, text="Port").grid(row=row, column=0, sticky="w", padx=10)
        proxy_port_e = tk.Entry(scrollable_frame, width=10)
        proxy_port_e.insert(0, self.config.get("proxy_port", ""))
        proxy_port_e.grid(row=row, column=1, sticky="w")

        row += 1
        tk.Label(scrollable_frame, text="User").grid(row=row, column=0, sticky="w", padx=10)
        proxy_user_e = tk.Entry(scrollable_frame, width=30)
        proxy_user_e.insert(0, self.config.get("proxy_user", ""))
        proxy_user_e.grid(row=row, column=1, sticky="w")

        row += 1
        tk.Label(scrollable_frame, text="Password").grid(row=row, column=0, sticky="w", padx=10)
        proxy_pass_e = tk.Entry(scrollable_frame, width=30, show="*")
        proxy_pass_e.insert(0, self.config.get("proxy_pass", ""))
        proxy_pass_e.grid(row=row, column=1, sticky="w")

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

                "gtin": gtin_e.get().strip(),
                "gtin_enabled": gtin_v.get(),

                "product_name": prod_e.get().strip(),
                "product_enabled": prod_v.get(),

                "tnved": tnved_e.get().strip(),
                "tnved_enabled": tnved_v.get(),

                "ds_number": ds_e.get().strip(),
                "ds_enabled": ds_v.get(),

                "proxy_enabled": proxy_enabled_v.get(),
                "proxy_type": proxy_type_cb.get(),
                "proxy_host": proxy_host_e.get().strip(),
                "proxy_port": proxy_port_e.get().strip(),
                "proxy_user": proxy_user_e.get().strip(),
                "proxy_pass": proxy_pass_e.get().strip()
            })

            save_config(self.config)
            apply_proxy(self.config)
            self.state.reset(val)
            messagebox.showinfo("OK", "Saved")
            win.destroy()

        tk.Button(scrollable_frame, text="Save", command=save).grid(row=row + 1, column=1, pady=30)

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
        messagebox.showinfo("", t["saved"])

    def end_shift(self):
        t = TEXT[self.lang]
        if self.state.in_box != 0:
            messagebox.showwarning(t["error"], t["need_close_box"])
            return
        if messagebox.askokcancel("", t["confirm_end"]):
            messagebox.showinfo("", t["sent"])
            self.state.reset(self.config["box_size"])
            self.duplicates = DuplicateChecker()
            self.errors = ErrorLog()
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

        # ❗ FNC1 allowed only at start
        if FNC1 in raw[1:]:
            self.errors.add(raw, t["err_fnc1"])
            messagebox.showerror(t["error"], t["err_fnc1"])
            return

        try:
            parsed = parse_gs1(raw)

            if self.config["gtin_enabled"]:
                if parsed["gtin"] != self.config["gtin"]:
                    raise Exception("GTIN does not match configured product")

            self.duplicates.check(parsed["clean"])

        except Exception as e:
            self.errors.add(raw, str(e))
            messagebox.showerror(t["error"], str(e))
            return

        if self.state.wait_sscc:
            self.state.scan_sscc()
            self.show_last(f"SSCC: {raw}")
            self.update_info(box_closed=True)
            return

        self.state.scan_unit()
        self.show_last(parsed["raw"])
        self.update_info()

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
