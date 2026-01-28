from flask import Flask, request, jsonify
import sqlite3
import datetime
import os

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
    print("Database initialized.")

@app.route('/check', methods=['POST'])
def check():
    data = request.json
    hwid = data.get('hwid')
    ip = data.get('ip')
    hostname = data.get('hostname')

    if not hwid:
        return jsonify({"status": "error", "message": "Missing HWID"}), 400

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT status FROM clients WHERE hwid = ?", (hwid,))
        row = cursor.fetchone()

        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if row:
            status = row[0]
            cursor.execute("UPDATE clients SET ip = ?, hostname = ?, last_seen = ? WHERE hwid = ?",
                           (ip, hostname, now, hwid))
            print(f"Update: {hostname} ({ip}) - {now}")
        else:
            status = 'allowed' # По умолчанию разрешаем новый запуск
            cursor.execute("INSERT INTO clients (hwid, ip, hostname, last_seen, status) VALUES (?, ?, ?, ?, ?)",
                           (hwid, ip, hostname, now, status))
            print(f"New client: {hostname} ({ip}) - {now}")
        conn.commit()

    return jsonify({
        "status": status,
        "message": "Доступ разрешен" if status == 'allowed' else "Программа заблокирована. Свяжитесь с разработчиком."
    })

@app.route('/list', methods=['GET'])
def list_clients():
    """Для дешборда админа"""
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
    """Для дешборда админа: блокировка/разблокировка"""
    data = request.json
    hwid = data.get('hwid')
    new_status = data.get('status') # 'allowed' или 'blocked'

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE clients SET status = ? WHERE hwid = ?", (new_status, hwid))
        conn.commit()
    return jsonify({"status": "ok"})

if __name__ == '__main__':
    init_db()
    # Запуск сервера на порту 8080. В продакшене нужен внешний IP.
    app.run(host='0.0.0.0', port=8080)
