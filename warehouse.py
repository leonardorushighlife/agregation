import sqlite3
import os
import json
import xml.etree.ElementTree as ET
from datetime import datetime

class WarehouseManager:
    def __init__(self, db_path="data/warehouse.db"):
        self.db_path = db_path
        db_dir = os.path.dirname(self.db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path, timeout=10) as conn:
            cursor = conn.cursor()
            # Таблица юнитов
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS wh_units (
                    cis TEXT PRIMARY KEY,
                    box_sscc TEXT,
                    receive_time DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            # Таблица коробов
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS wh_boxes (
                    sscc TEXT PRIMARY KEY,
                    pallet_sscc TEXT,
                    status TEXT DEFAULT 'in_stock',
                    receive_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                    ship_time DATETIME
                )
            """)
            # Таблица палет
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS wh_pallets (
                    sscc TEXT PRIMARY KEY,
                    status TEXT DEFAULT 'in_stock',
                    receive_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                    ship_time DATETIME
                )
            """)
            # Таблица заказов
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS wh_orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_num TEXT UNIQUE,
                    product_name TEXT,
                    total_units INTEGER,
                    destination_rc TEXT,
                    status TEXT DEFAULT 'pending',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            # Таблица истории перемещений (для учета)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS wh_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    item_code TEXT,
                    item_type TEXT, -- 'unit', 'box', 'pallet'
                    action TEXT,    -- 'received', 'shipped'
                    order_id INTEGER,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

    def import_aggregation(self, file_path):
        """Импорт файла агрегации первого или второго уровня"""
        if not os.path.exists(file_path):
            return False, "File not found"

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Попытка парсинга как XML
            if "<?xml" in content or "<unit_pack>" in content:
                return self._import_xml(content)
            else:
                # Возможно, это какой-то другой текстовый формат,
                # но по ТЗ агрегация - это XML в TXT.
                return False, "Unknown format"
        except Exception as e:
            return False, str(e)

    def _import_xml(self, xml_content):
        try:
            root = ET.fromstring(xml_content)
            count_boxes = 0
            count_units = 0

            with sqlite3.connect(self.db_path, timeout=10) as conn:
                cursor = conn.cursor()
                for pack in root.findall(".//pack_content"):
                    box_sscc = pack.find("pack_code").text
                    # Если это палета, в ней лежат SSCC коробов, но структура та же
                    # Нам нужно понять, что мы импортируем.
                    # По ТЗ "подгружаются файлы агрегации первого уровня (юниты в короба)".

                    cursor.execute("INSERT OR IGNORE INTO wh_boxes (sscc) VALUES (?)", (box_sscc,))
                    count_boxes += 1

                    for cis in pack.findall("cis"):
                        unit_cis = cis.text
                        cursor.execute("INSERT OR REPLACE INTO wh_units (cis, box_sscc) VALUES (?, ?)",
                                       (unit_cis, box_sscc))
                        count_units += 1
                conn.commit()
            return True, f"Imported {count_boxes} boxes and {count_units} units"
        except Exception as e:
            return False, f"XML Error: {e}"

    def register_pallet(self, pallet_sscc, box_ssccs):
        """Регистрация палеты и привязка к ней коробов"""
        with sqlite3.connect(self.db_path, timeout=10) as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT OR REPLACE INTO wh_pallets (sscc) VALUES (?)", (pallet_sscc,))
            for box_sscc in box_ssccs:
                cursor.execute("UPDATE wh_boxes SET pallet_sscc = ? WHERE sscc = ?", (pallet_sscc, box_sscc))
                # Если короба еще не было в базе (не импортировали), создаем
                cursor.execute("INSERT OR IGNORE INTO wh_boxes (sscc, pallet_sscc) VALUES (?, ?)",
                               (box_sscc, pallet_sscc))
            conn.commit()

    def shipment(self, sscc):
        """Отгрузка палеты или короба"""
        with sqlite3.connect(self.db_path, timeout=10) as conn:
            cursor = conn.cursor()
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # Проверяем, палета ли это
            cursor.execute("SELECT sscc FROM wh_pallets WHERE sscc = ?", (sscc,))
            if cursor.fetchone():
                # Отгружаем палету и все короба в ней
                cursor.execute("UPDATE wh_pallets SET status = 'shipped', ship_time = ? WHERE sscc = ?", (now, sscc))
                cursor.execute("UPDATE wh_boxes SET status = 'shipped', ship_time = ? WHERE pallet_sscc = ?", (now, sscc))
                return True, "pallet"

            # Иначе проверяем, короб ли это
            cursor.execute("SELECT sscc FROM wh_boxes WHERE sscc = ?", (sscc,))
            if cursor.fetchone():
                cursor.execute("UPDATE wh_boxes SET status = 'shipped', ship_time = ? WHERE sscc = ?", (now, sscc))
                return True, "box"

            # Если в базе нет, но пришел код отгрузки - считаем как новый короб
            cursor.execute("INSERT INTO wh_boxes (sscc, status, ship_time) VALUES (?, 'shipped', ?)", (sscc, now))
            return True, "box_new"

    def return_item(self, sscc):
        """Возврат палеты или короба"""
        with sqlite3.connect(self.db_path, timeout=10) as conn:
            cursor = conn.cursor()

            # Проверяем, палета ли это
            cursor.execute("SELECT sscc FROM wh_pallets WHERE sscc = ?", (sscc,))
            if cursor.fetchone():
                cursor.execute("UPDATE wh_pallets SET status = 'in_stock', ship_time = NULL WHERE sscc = ?", (sscc,))
                cursor.execute("UPDATE wh_boxes SET status = 'in_stock', ship_time = NULL WHERE pallet_sscc = ?", (sscc,))
                return True, "pallet"

            # Иначе проверяем, короб ли это
            cursor.execute("SELECT sscc FROM wh_boxes WHERE sscc = ?", (sscc,))
            if cursor.fetchone():
                cursor.execute("UPDATE wh_boxes SET status = 'in_stock', ship_time = NULL WHERE sscc = ?", (sscc,))
                return True, "box"

            return False, "not_found"

    def get_stock_report(self):
        """Статистика остатков"""
        with sqlite3.connect(self.db_path, timeout=10) as conn:
            cursor = conn.cursor()

            cursor.execute("SELECT COUNT(*) FROM wh_units")
            total_units = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM wh_boxes WHERE status = 'in_stock'")
            boxes_in_stock = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM wh_boxes WHERE status = 'shipped'")
            boxes_shipped = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM wh_pallets WHERE status = 'in_stock'")
            pallets_in_stock = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM wh_pallets WHERE status = 'shipped'")
            pallets_shipped = cursor.fetchone()[0]

            return {
                "total_units": total_units,
                "boxes_stock": boxes_in_stock,
                "boxes_shipped": boxes_shipped,
                "pallets_stock": pallets_in_stock,
                "pallets_shipped": pallets_shipped
            }

    def add_order(self, order_num, product_name="", total_units=0, destination_rc=""):
        with sqlite3.connect(self.db_path, timeout=10) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO wh_orders (order_num, product_name, total_units, destination_rc, status)
                VALUES (?, ?, ?, ?, 'pending')
            """, (order_num, product_name, total_units, destination_rc))
            conn.commit()

    def get_pending_orders(self):
        with sqlite3.connect(self.db_path, timeout=10) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT order_num, product_name, total_units, destination_rc FROM wh_orders WHERE status = 'pending'")
            return [dict(zip(["num", "product", "units", "rc"], row)) for row in cursor.fetchall()]

    def get_shipped_orders(self):
        with sqlite3.connect(self.db_path, timeout=10) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT order_num, product_name, total_units, destination_rc FROM wh_orders WHERE status = 'completed'")
            return [dict(zip(["num", "product", "units", "rc"], row)) for row in cursor.fetchall()]

    def get_order_shipped_count(self, order_num):
        with sqlite3.connect(self.db_path, timeout=10) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(u.cis) FROM wh_units u
                JOIN wh_boxes b ON u.box_sscc = b.sscc
                JOIN wh_history h ON b.sscc = h.item_code OR b.pallet_sscc = h.item_code
                JOIN wh_orders o ON h.order_id = o.id
                WHERE o.order_num = ? AND h.action = 'shipped'
            """, (order_num,))
            # Это упрощенная логика, может считать дубли если история сложная.
            # Но для начала сойдет.
            row = cursor.fetchone()
            return row[0] if row else 0

    def complete_order(self, order_num):
        with sqlite3.connect(self.db_path, timeout=10) as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE wh_orders SET status = 'completed' WHERE order_num = ?", (order_num,))
            conn.commit()

    def delete_order(self, order_num):
        with sqlite3.connect(self.db_path, timeout=10) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM wh_orders WHERE order_num = ?", (order_num,))
            conn.commit()

    def update_order_status(self, order_num, status):
        with sqlite3.connect(self.db_path, timeout=10) as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE wh_orders SET status = ? WHERE order_num = ?", (status, order_num))
            conn.commit()

    def get_sscc_content(self, sscc):
        with sqlite3.connect(self.db_path, timeout=10) as conn:
            cursor = conn.cursor()
            # Проверяем, палета ли это
            cursor.execute("SELECT sscc FROM wh_boxes WHERE pallet_sscc = ?", (sscc,))
            boxes = cursor.fetchall()
            if boxes:
                # Возвращаем все юниты во всех коробках этой палеты
                cursor.execute("""
                    SELECT u.cis FROM wh_units u
                    JOIN wh_boxes b ON u.box_sscc = b.sscc
                    WHERE b.pallet_sscc = ?
                """, (sscc,))
                return [row[0] for row in cursor.fetchall()]

            # Иначе это коробка
            cursor.execute("SELECT cis FROM wh_units WHERE box_sscc = ?", (sscc,))
            units = cursor.fetchall()
            return [row[0] for row in units]

    def record_history(self, code, item_type, action, order_num=None):
        with sqlite3.connect(self.db_path, timeout=10) as conn:
            cursor = conn.cursor()
            order_id = None
            if order_num:
                cursor.execute("SELECT id FROM wh_orders WHERE order_num = ?", (order_num,))
                row = cursor.fetchone()
                if row: order_id = row[0]

            cursor.execute("INSERT INTO wh_history (item_code, item_type, action, order_id) VALUES (?, ?, ?, ?)",
                           (code, item_type, action, order_id))
            conn.commit()

    def get_history_report(self, start_date=None):
        """Отчет о движении товара"""
        with sqlite3.connect(self.db_path, timeout=10) as conn:
            cursor = conn.cursor()
            query = "SELECT action, item_type, COUNT(*) FROM wh_history"
            if start_date:
                query += f" WHERE timestamp >= '{start_date}'"
            query += " GROUP BY action, item_type"
            cursor.execute(query)
            return cursor.fetchall()

    def export_orders_json(self, path):
        orders = self.get_pending_orders()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(orders, f, ensure_ascii=False, indent=2)

    def import_orders_json(self, path):
        with open(path, "r", encoding="utf-8") as f:
            orders = json.load(f)
            for o in orders:
                self.add_order(o['num'], o['product'], int(o['units']), o['rc'])

    def sync_orders(self, server_orders):
        """server_orders: list of dicts with num, product, units, rc, status"""
        with sqlite3.connect(self.db_path, timeout=10) as conn:
            cursor = conn.cursor()

            # 1. Получаем все локальные номера заказов
            cursor.execute("SELECT order_num FROM wh_orders")
            local_nums = {row[0] for row in cursor.fetchall()}

            server_nums = {o['num'] for o in server_orders}

            # 2. Обновляем/Добавляем из сервера
            for o in server_orders:
                cursor.execute("""
                    INSERT INTO wh_orders (order_num, product_name, total_units, destination_rc, status)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(order_num) DO UPDATE SET
                        product_name=excluded.product_name,
                        total_units=excluded.total_units,
                        destination_rc=excluded.destination_rc,
                        status=excluded.status
                """, (o['num'], o['product'], o['units'], o['rc'], o['status']))

            # 3. Если заказ пропал с сервера и он был pending - удаляем?
            # Или лучше оставить для истории?
            # Пользователь сказал: "Только через программу администратора можно редактировать список, изменять статусы заказа, и так же удалять их"
            # Значит если удалили в админке - удаляем и тут.
            for num in local_nums:
                if num not in server_nums:
                    cursor.execute("DELETE FROM wh_orders WHERE order_num = ? AND status = 'pending'", (num,))

            conn.commit()
