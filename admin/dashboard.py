import tkinter as tk
from tkinter import messagebox, ttk
import requests

# Адрес сервера лицензий (в реальных условиях должен быть публичный IP или домен)
SERVER_URL = "http://127.0.0.1:8080"

class AdminDashboard:
    def __init__(self, root):
        self.root = root
        self.root.title("Aggregator - ГЛАВНЫЙ АДМИНИСТРАТОР")
        self.root.geometry("950x550")

        # Заголовок
        tk.Label(root, text="Мониторинг и управление лицензиями", font=("Arial", 16, "bold")).pack(pady=15)

        # Описание
        tk.Label(root, text=f"Сервер управления: {SERVER_URL}", font=("Arial", 9), fg="gray").pack()

        # Таблица
        cols = ("HWID", "IP-адрес", "Имя ПК", "Был в сети", "Статус")
        self.tree = ttk.Treeview(root, columns=cols, show="headings", height=15)

        # Настройка колонок
        self.tree.heading("HWID", text="ID оборудования")
        self.tree.heading("IP-адрес", text="IP-адрес")
        self.tree.heading("Имя ПК", text="Имя компьютера")
        self.tree.heading("Был в сети", text="Последний запуск")
        self.tree.heading("Статус", text="Статус доступа")

        self.tree.column("HWID", width=180, anchor="center")
        self.tree.column("IP-адрес", width=120, anchor="center")
        self.tree.column("Имя ПК", width=150, anchor="center")
        self.tree.column("Был в сети", width=180, anchor="center")
        self.tree.column("Статус", width=120, anchor="center")

        # Цветовая разметка для статусов
        self.tree.tag_configure('blocked', background='#FFCDD2')
        self.tree.tag_configure('allowed', background='#C8E6C9')

        self.tree.pack(expand=True, fill="both", padx=20, pady=10)

        # Панель кнопок
        btn_frame = tk.Frame(root)
        btn_frame.pack(pady=20)

        tk.Button(btn_frame, text="🔄 Обновить список", command=self.load_data,
                  font=("Arial", 10), bg="#2196F3", fg="white", width=18, height=2).grid(row=0, column=0, padx=10)

        tk.Button(btn_frame, text="🚫 БЛОКИРОВАТЬ", command=lambda: self.set_status('blocked'),
                  font=("Arial", 10, "bold"), bg="#f44336", fg="white", width=18, height=2).grid(row=0, column=1, padx=10)

        tk.Button(btn_frame, text="✅ РАЗБЛОКИРОВАТЬ", command=lambda: self.set_status('allowed'),
                  font=("Arial", 10, "bold"), bg="#4CAF50", fg="white", width=18, height=2).grid(row=0, column=2, padx=10)

        self.load_data()

    def load_data(self):
        try:
            # Очистка текущих данных
            for item in self.tree.get_children():
                self.tree.delete(item)

            resp = requests.get(f"{SERVER_URL}/list", timeout=5)
            if resp.status_code == 200:
                clients = resp.json()
                for c in clients:
                    tag = c['status']
                    self.tree.insert("", "end", values=(
                        c['hwid'], c['ip'], c['hostname'], c['last_seen'],
                        "ДОСТУПЕН" if c['status'] == 'allowed' else "ЗАБЛОКИРОВАН"
                    ), tags=(tag,))
            else:
                messagebox.showerror("Ошибка", f"Сервер вернул код {resp.status_code}")
        except Exception as e:
            messagebox.showerror("Ошибка связи", f"Не удалось получить данные с сервера:\n{e}")

    def set_status(self, status):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Внимание", "Пожалуйста, выберите устройство в таблице")
            return

        hwid = self.tree.item(selected[0])['values'][0]
        try:
            resp = requests.post(f"{SERVER_URL}/update_status", json={"hwid": hwid, "status": status}, timeout=5)
            if resp.status_code == 200:
                self.load_data()
                action = "заблокировано" if status == 'blocked' else "разблокировано"
                messagebox.showinfo("Успех", f"Устройство {hwid} успешно {action}")
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось обновить статус:\n{e}")

if __name__ == "__main__":
    root = tk.Tk()
    AdminDashboard(root)
    root.mainloop()
