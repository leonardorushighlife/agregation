import tkinter as tk
from tkinter import messagebox, ttk
import requests
import threading
import time

# Адрес сервера лицензий (в реальных условиях должен быть публичный IP или домен)
# Например: http://192.168.1.50:8080
SERVER_URL = "http://127.0.0.1:8080"

class AdminDashboard:
    def __init__(self, root):
        self.root = root
        self.root.title("Aggregator Enterprise - ПАНЕЛЬ УПРАВЛЕНИЯ")
        self.root.geometry("1000x650")
        self.root.configure(bg="#f5f5f5")

        self.all_data = []

        # Стили
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview", rowheight=30, font=("Arial", 10))
        style.configure("Treeview.Heading", font=("Arial", 11, "bold"))

        # Верхняя панель (Заголовок и Поиск)
        top_frame = tk.Frame(root, bg="#2c3e50", height=80)
        top_frame.pack(side="top", fill="x")

        tk.Label(top_frame, text="УПРАВЛЕНИЕ ЛИЦЕНЗИЯМИ", font=("Arial", 18, "bold"),
                 fg="white", bg="#2c3e50").pack(side="left", padx=20, pady=20)

        search_frame = tk.Frame(top_frame, bg="#2c3e50")
        search_frame.pack(side="right", padx=20)

        tk.Label(search_frame, text="Поиск:", fg="white", bg="#2c3e50").pack(side="left", padx=5)
        self.search_var = tk.StringVar()
        self.search_var.trace("w", lambda *args: self.filter_data())
        tk.Entry(search_frame, textvariable=self.search_var, width=25, font=("Arial", 11)).pack(side="left", padx=5)

        # Информационная панель
        self.status_bar = tk.Frame(root, bg="#ecf0f1", height=30)
        self.status_bar.pack(side="top", fill="x")
        self.lbl_stats = tk.Label(self.status_bar, text="Всего устройств: 0 | В сети: 0",
                                  font=("Arial", 10), bg="#ecf0f1")
        self.lbl_stats.pack(side="left", padx=20)

        # Таблица
        table_frame = tk.Frame(root)
        table_frame.pack(expand=True, fill="both", padx=20, pady=10)

        cols = ("HWID", "IP-адрес", "Имя ПК", "Последний запуск", "Статус")
        self.tree = ttk.Treeview(table_frame, columns=cols, show="headings")

        for col in cols:
            self.tree.heading(col, text=col)
            self.tree.column(col, anchor="center")

        self.tree.column("HWID", width=200)
        self.tree.column("IP-адрес", width=120)
        self.tree.column("Имя ПК", width=150)
        self.tree.column("Последний запуск", width=180)
        self.tree.column("Статус", width=130)

        # Скроллбар
        vsb = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self.tree.pack(expand=True, fill="both")

        # Теги для раскраски
        self.tree.tag_configure('blocked', background='#ff9999')
        self.tree.tag_configure('allowed', background='#ccffcc')

        # Панель кнопок
        btn_frame = tk.Frame(root, bg="#f5f5f5")
        btn_frame.pack(side="bottom", fill="x", pady=20)

        tk.Button(btn_frame, text="🔄 Обновить список", command=self.load_data,
                  bg="#3498db", fg="white", font=("Arial", 10, "bold"), width=20, height=2).pack(side="left", padx=20)

        self.btn_block = tk.Button(btn_frame, text="🚫 БЛОКИРОВАТЬ", command=lambda: self.set_status('blocked'),
                                   bg="#e74c3c", fg="white", font=("Arial", 10, "bold"), width=20, height=2)
        self.btn_block.pack(side="right", padx=10)

        self.btn_allow = tk.Button(btn_frame, text="✅ РАЗБЛОКИРОВАТЬ", command=lambda: self.set_status('allowed'),
                                   bg="#2ecc71", fg="white", font=("Arial", 10, "bold"), width=20, height=2)
        self.btn_allow.pack(side="right", padx=10)

        # Авто-обновление в фоне
        self.load_data()

    def load_data(self):
        def _fetch():
            try:
                resp = requests.get(f"{SERVER_URL}/list", timeout=5)
                if resp.status_code == 200:
                    self.all_data = resp.json()
                    self.root.after(0, self.filter_data)
            except Exception as e:
                print(f"Update error: {e}")

        threading.Thread(target=_fetch, daemon=True).start()

    def filter_data(self):
        # Очистка
        for item in self.tree.get_children():
            self.tree.delete(item)

        search_query = self.search_var.get().lower()
        count_allowed = 0

        for c in self.all_data:
            match = (search_query in c['hwid'].lower() or
                     search_query in c['ip'].lower() or
                     search_query in c['hostname'].lower())

            if match:
                tag = c['status']
                if tag == 'allowed': count_allowed += 1

                self.tree.insert("", "end", values=(
                    c['hwid'], c['ip'], c['hostname'], c['last_seen'],
                    "РАБОТАЕТ" if c['status'] == 'allowed' else "ЗАБЛОКИРОВАН"
                ), tags=(tag,))

        self.lbl_stats.config(text=f"Всего устройств: {len(self.all_data)} | Допущено: {count_allowed} | Заблокировано: {len(self.all_data) - count_allowed}")

    def set_status(self, status):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Внимание", "Выберите устройство из списка")
            return

        hwid = self.tree.item(selected[0])['values'][0]
        try:
            resp = requests.post(f"{SERVER_URL}/update_status", json={"hwid": hwid, "status": status}, timeout=5)
            if resp.status_code == 200:
                self.load_data()
                action = "заблокировано" if status == 'blocked' else "разблокировано"
                messagebox.showinfo("Успех", f"Устройство {hwid} {action}")
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось связаться с сервером: {e}")

if __name__ == "__main__":
    root = tk.Tk()
    AdminDashboard(root)
    root.mainloop()
