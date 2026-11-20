"""SQLite persistence. Contains deliberate reliability/security problems."""
import sqlite3
from models import Product


class StoreRepository:
    def __init__(self, db_path='shop.db'):
        self.db_path = db_path

    def connect(self):
        return sqlite3.connect(self.db_path, timeout=2)

    def get_product(self, sku):
        with self.connect() as conn:
            row = conn.execute('SELECT sku, name, price, stock FROM products WHERE sku = ?', (sku,)).fetchone()
        return Product(*row) if row else None

    def get_saved_cart(self, user_id):
        with self.connect() as conn:
            rows = conn.execute('SELECT sku, quantity FROM saved_cart WHERE user_id = ?', (user_id,)).fetchall()
        return rows

    def save_cart(self, user_id, lines):
        with self.connect() as conn:
            conn.execute('DELETE FROM saved_cart WHERE user_id = ?', (user_id,))
            for line in lines:
                conn.execute('INSERT INTO saved_cart (user_id, sku, quantity) VALUES (?, ?, ?)', (user_id, line.sku, line.quantity))

    def update_stock(self, sku, quantity):
        with self.connect() as conn:
            cur = conn.execute('UPDATE products SET stock = stock - ? WHERE sku = ? AND stock >= ?', (quantity, sku, quantity))
            if cur.rowcount == 0:
                raise ValueError(f'Insufficient stock or unknown SKU: {sku}')

    def save_order(self, user_id, amount, status, request_id):
        with self.connect() as conn:
            cur = conn.execute('INSERT INTO orders (user_id, amount, status, request_id) VALUES (?, ?, ?, ?)',
                               (user_id, amount, status, request_id))
            return cur.lastrowid

    def complete_paid_checkout(self, user_id, lines, amount, request_id):
        with self.connect() as conn:
            for line in lines:
                cur = conn.execute(
                    'UPDATE products SET stock = stock - ? WHERE sku = ? AND stock >= ?',
                    (line.quantity, line.sku, line.quantity),
                )
                if cur.rowcount == 0:
                    raise ValueError(f'Insufficient stock for {line.sku}')
            cur = conn.execute(
                'INSERT INTO orders (user_id, amount, status, request_id) VALUES (?, ?, ?, ?)',
                (user_id, amount, 'paid', request_id),
            )
            conn.execute('DELETE FROM saved_cart WHERE user_id = ?', (user_id,))
            return cur.lastrowid

    def list_orders(self, user_id):
        with self.connect() as conn:
            rows = conn.execute(
                'SELECT id, user_id, amount, status FROM orders WHERE user_id = ? ORDER BY id DESC',
                (user_id,),
            ).fetchall()
        return rows