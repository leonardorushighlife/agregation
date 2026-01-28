import tkinter as tk
from tkinter import messagebox, ttk
import requests
import threading
import time
import sqlite3
import datetime
import os
import sys
from flask import Flask, request, jsonify

# Добавляем корневую директорию в путь для импорта i18n
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    from i18n import TEXT
except ImportError:
    TEXT = {"ru": {"lang_name": "Error"}}

# --- СЕРВЕРНАЯ ЧАСТЬ (бывший server.py) ---
app = Flask(__name__)
DB_PATH = os.path.join(os.path.dirname(__file__), "clients.db")

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS clients (
                hwid TEXT PRIMARY KEY,
                ip TEXT,
                hostname TEXT,
                last_seen DATETIME,
                status TEXT DEFAULT 'allowed'
            )
        """)

@app.route('/check', methods=['POST'])
def check():
    data = request.json
    hwid = data.get('hwid')
    ip = data.get('ip')
    hostname = data.get('hostname')
    if not hwid: return jsonify({"status": "error", "message": "Missing HWID"}), 400
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT status FROM clients WHERE hwid = ?", (hwid,))
        row = cursor.fetchone()
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if row:
            status = row[0]
            cursor.execute("UPDATE clients SET ip = ?, hostname = ?, last_seen = ? WHERE hwid = ?", (ip, hostname, now, hwid))
        else:
            status = 'allowed'
            cursor.execute("INSERT INTO clients (hwid, ip, hostname, last_seen, status) VALUES (?, ?, ?, ?, ?)", (hwid, ip, hostname, now, status))
        conn.commit()
    return jsonify({"status": status, "message": "OK" if status == 'allowed' else "Blocked"})

@app.route('/list', methods=['GET'])
def list_clients():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT hwid, ip, hostname, last_seen, status FROM clients")
        rows = cursor.fetchall()
        clients = []
        for r in rows:
            clients.append({"hwid": r[0], "ip": r[1], "hostname": r[2], "last_seen": r[3], "status": r[4]})
        return jsonify(clients)

@app.route('/update_status', methods=['POST'])
def update_status():
    data = request.json
    hwid = data.get('hwid')
    new_status = data.get('status')
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE clients SET status = ? WHERE hwid = ?", (new_status, hwid))
        conn.commit()
    return jsonify({"status": "ok"})

def run_server():
    init_db()
    app.run(host='0.0.0.0', port=8080, debug=False, use_reloader=False)

# --- ИНТЕРФЕЙСНАЯ ЧАСТЬ (бывший dashboard.py) ---
DEFAULT_SERVER_URL = "http://127.0.0.1:8080"

class AdminDashboard:
    def __init__(self, root):
        self.root = root
        self.lang = "ru" # По умолчанию
        self.server_url = DEFAULT_SERVER_URL
        self.all_data = []
        self.url_var = tk.StringVar(value=self.server_url)
        self.search_var = tk.StringVar()
        self.search_var.trace("w", lambda *args: self.filter_data())

        self.setup_ui()
        self.load_data()

    def setup_ui(self):
        t = TEXT[self.lang]
        self.root.title(t.get("dash_title", "Admin Panel"))
        self.root.geometry("1000x700")
        self.root.configure(bg="#f5f5f5")

        for w in self.root.winfo_children(): w.destroy()

        # Стили
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview", rowheight=30, font=("Arial", 10))
        style.configure("Treeview.Heading", font=("Arial", 11, "bold"))

        # Верхняя панель
        top_frame = tk.Frame(self.root, bg="#2c3e50", height=80)
        top_frame.pack(side="top", fill="x")

        tk.Label(top_frame, text=t.get("dash_lic_mgmt", "LICENSES"), font=("Arial", 18, "bold"),
                 fg="white", bg="#2c3e50").pack(side="left", padx=20, pady=20)

        # Переключатель языка в админке
        lang_frame = tk.Frame(top_frame, bg="#2c3e50")
        lang_frame.pack(side="right", padx=10)
        for l_code in TEXT:
            tk.Button(lang_frame, text=l_code.upper(), width=3,
                      command=lambda c=l_code: self.change_lang(c)).pack(side="left", padx=2)

        search_frame = tk.Frame(top_frame, bg="#2c3e50")
        search_frame.pack(side="right", padx=20)

        tk.Label(search_frame, text=t.get("dash_server", "Server:"), fg="white", bg="#2c3e50").pack(side="left", padx=5)
        tk.Entry(search_frame, textvariable=self.url_var, width=20).pack(side="left", padx=5)

        tk.Label(search_frame, text=t.get("dash_search", "Search:"), fg="white", bg="#2c3e50").pack(side="left", padx=5)
        tk.Entry(search_frame, textvariable=self.search_var, width=15, font=("Arial", 11)).pack(side="left", padx=5)

        # Информационная панель
        self.status_bar = tk.Frame(self.root, bg="#ecf0f1", height=30)
        self.status_bar.pack(side="top", fill="x")
        self.lbl_stats = tk.Label(self.status_bar, text="", font=("Arial", 10), bg="#ecf0f1")
        self.lbl_stats.pack(side="left", padx=20)

        # Таблица
        table_frame = tk.Frame(self.root)
        table_frame.pack(expand=True, fill="both", padx=20, pady=10)

        cols = ("HWID", "IP", "HOST", "LAST", "STATUS")
        col_names = [
            t.get("dash_col_hwid", "HWID"),
            t.get("dash_col_ip", "IP"),
            t.get("dash_col_host", "Host"),
            t.get("dash_col_last", "Last"),
            t.get("dash_col_status", "Status")
        ]

        self.tree = ttk.Treeview(table_frame, columns=cols, show="headings")
        for i, col in enumerate(cols):
            self.tree.heading(col, text=col_names[i])
            self.tree.column(col, anchor="center")

        vsb = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self.tree.pack(expand=True, fill="both")

        self.tree.tag_configure('blocked', background='#ff9999')
        self.tree.tag_configure('allowed', background='#ccffcc')

        # Кнопки
        btn_frame = tk.Frame(self.root, bg="#f5f5f5")
        btn_frame.pack(side="bottom", fill="x", pady=20)

        tk.Button(btn_frame, text=t.get("dash_btn_refresh", "Refresh"), command=self.load_data,
                  bg="#3498db", fg="white", font=("Arial", 10, "bold"), width=20, height=2).pack(side="left", padx=20)

        tk.Button(btn_frame, text=t.get("dash_btn_block", "BLOCK"), command=lambda: self.set_status('blocked'),
                  bg="#e74c3c", fg="white", font=("Arial", 10, "bold"), width=20, height=2).pack(side="right", padx=10)

        tk.Button(btn_frame, text=t.get("dash_btn_allow", "ALLOW"), command=lambda: self.set_status('allowed'),
                  bg="#2ecc71", fg="white", font=("Arial", 10, "bold"), width=20, height=2).pack(side="right", padx=10)

    def change_lang(self, lang):
        self.lang = lang
        self.setup_ui()
        self.filter_data()

    def load_data(self):
        self.server_url = self.url_var.get().strip()
        def _fetch():
            try:
                resp = requests.get(f"{self.server_url}/list", timeout=5)
                if resp.status_code == 200:
                    self.all_data = resp.json()
                    self.root.after(0, self.filter_data)
            except: pass
        threading.Thread(target=_fetch, daemon=True).start()

    def filter_data(self):
        t = TEXT[self.lang]
        for item in self.tree.get_children(): self.tree.delete(item)
        query = self.search_var.get().lower()
        count_allowed = 0
        for c in self.all_data:
            if query in c['hwid'].lower() or query in c['ip'].lower() or query in c['hostname'].lower():
                tag = c['status']
                if tag == 'allowed': count_allowed += 1
                st_text = t.get("dash_status_ok", "OK") if tag == 'allowed' else t.get("dash_status_blocked", "BLOCKED")
                self.tree.insert("", "end", values=(c['hwid'], c['ip'], c['hostname'], c['last_seen'], st_text), tags=(tag,))

        self.lbl_stats.config(text=t.get("dash_stats", "{} devices").format(len(self.all_data), count_allowed, len(self.all_data)-count_allowed))

    def set_status(self, status):
        t = TEXT[self.lang]
        sel = self.tree.selection()
        if not sel: return
        hwid = self.tree.item(sel[0])['values'][0]
        try:
            requests.post(f"{self.url_var.get().strip()}/update_status", json={"hwid": hwid, "status": status}, timeout=5)
            self.load_data()
        except Exception as e:
            messagebox.showerror(t.get("error", "Error"), str(e))

if __name__ == "__main__":
    # Запуск сервера в отдельном потоке
    threading.Thread(target=run_server, daemon=True).start()

    root = tk.Tk()
    AdminDashboard(root)
    root.mainloop()
