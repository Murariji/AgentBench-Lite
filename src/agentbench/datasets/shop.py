"""The sample shop database for the Data Analyst benchmark.

Generated from a FIXED SEED, so every build is identical on every computer and the
benchmark's expected answers never change. Only this generator is committed to git;
the .db file is built on demand (and git-ignored).

Tables
    customers   (id, name, city, joined_on)
    products    (id, name, category, price)
    orders      (id, customer_id, order_date)
    order_items (order_id, product_id, quantity)

Edge cases built in ON PURPOSE (they are traps for agents):
    * customers from 7 cities, products in 4 categories
    * orders spread over 6 months (Jan-Jun 2026)
    * orders with several different products
    * 3 customers with NO orders        (INNER vs LEFT JOIN changes answers)
    * 2 products that were NEVER ordered
"""

import os
import random
import sqlite3
import tempfile
from datetime import date, timedelta
from pathlib import Path

SEED = 2026
DEFAULT_DB_PATH = Path("data") / "shop.db"  # fixed location, relative to the project folder

CITIES = ["Delhi", "Mumbai", "Bengaluru", "Chennai", "Kolkata", "Pune", "Jaipur"]

CUSTOMER_NAMES = [
    "Aarav Sharma", "Diya Patel", "Vihaan Gupta", "Ananya Iyer", "Arjun Reddy",
    "Ishita Das", "Kabir Singh", "Meera Nair", "Rohan Mehta", "Saanvi Joshi",
    "Aditya Rao", "Kavya Menon", "Dev Malhotra", "Riya Kapoor", "Yash Verma",
    "Tara Bose", "Nikhil Jain", "Pooja Kulkarni", "Siddharth Roy", "Neha Agarwal",
    "Karan Chopra", "Aditi Mishra", "Rahul Pillai", "Sneha Ghosh", "Varun Bhatt",
    "Ira Saxena", "Manav Sethi", "Lakshmi Krishnan", "Omkar Patil", "Zoya Khan",
]

# (name, category, price in rupees). The LAST TWO are never ordered.
PRODUCTS = [
    ("Wireless Mouse", "Electronics", 799),
    ("USB-C Charger", "Electronics", 1499),
    ("Bluetooth Speaker", "Electronics", 2999),
    ("Noise-Cancelling Headphones", "Electronics", 8999),
    ("Cotton T-Shirt", "Clothing", 499),
    ("Denim Jeans", "Clothing", 1799),
    ("Running Shoes", "Clothing", 3499),
    ("Basmati Rice 5kg", "Grocery", 649),
    ("Green Tea 100 bags", "Grocery", 399),
    ("Almonds 500g", "Grocery", 549),
    ("Python Crash Course", "Books", 1299),
    ("Atomic Habits", "Books", 499),
    ("Clean Code", "Books", 2199),
    ("Smart Watch", "Electronics", 12999),   # never ordered
    ("Silk Saree", "Clothing", 6499),        # never ordered
]

NUM_ORDERS = 150
CUSTOMERS_WITHOUT_ORDERS = 3   # the last 3 customers never order
PRODUCTS_NEVER_ORDERED = 2     # the last 2 products are never ordered


def _fill(conn: sqlite3.Connection) -> None:
    rng = random.Random(SEED)  # our own generator: same seed -> same numbers, every time
    conn.executescript("""
        CREATE TABLE customers (
            id INTEGER PRIMARY KEY, name TEXT NOT NULL, city TEXT NOT NULL, joined_on TEXT NOT NULL);
        CREATE TABLE products (
            id INTEGER PRIMARY KEY, name TEXT NOT NULL, category TEXT NOT NULL, price INTEGER NOT NULL);
        CREATE TABLE orders (
            id INTEGER PRIMARY KEY, customer_id INTEGER NOT NULL REFERENCES customers(id),
            order_date TEXT NOT NULL);
        CREATE TABLE order_items (
            order_id INTEGER NOT NULL REFERENCES orders(id),
            product_id INTEGER NOT NULL REFERENCES products(id),
            quantity INTEGER NOT NULL CHECK (quantity > 0),
            PRIMARY KEY (order_id, product_id));
    """)

    customers = []
    for i, name in enumerate(CUSTOMER_NAMES, start=1):
        city = CITIES[i - 1] if i <= len(CITIES) else rng.choice(CITIES)  # every city appears
        joined = date(2025, 1, 1) + timedelta(days=rng.randrange(365))
        customers.append((i, name, city, joined.isoformat()))
    conn.executemany("INSERT INTO customers VALUES (?, ?, ?, ?)", customers)

    conn.executemany(
        "INSERT INTO products VALUES (?, ?, ?, ?)",
        [(i, n, c, p) for i, (n, c, p) in enumerate(PRODUCTS, start=1)],
    )

    ordering_customers = list(range(1, len(CUSTOMER_NAMES) - CUSTOMERS_WITHOUT_ORDERS + 1))
    orderable_products = list(range(1, len(PRODUCTS) - PRODUCTS_NEVER_ORDERED + 1))
    start, days = date(2026, 1, 1), (date(2026, 6, 30) - date(2026, 1, 1)).days + 1
    for order_id in range(1, NUM_ORDERS + 1):
        order_date = start + timedelta(days=rng.randrange(days))
        conn.execute("INSERT INTO orders VALUES (?, ?, ?)",
                     (order_id, rng.choice(ordering_customers), order_date.isoformat()))
        for product_id in rng.sample(orderable_products, k=rng.randint(1, 4)):  # distinct products
            conn.execute("INSERT INTO order_items VALUES (?, ?, ?)",
                         (order_id, product_id, rng.randint(1, 5)))


def build_shop_db(path: str | Path = DEFAULT_DB_PATH, *, overwrite: bool = False) -> Path:
    """Build the shop database at ``path``. Never overwrites by accident.

    Safe replacement: the data is written to a temporary file in the same folder first,
    and only moved into place (``os.replace``, atomic) once it is complete. A crash
    half-way can never leave a broken shop.db behind.
    """
    path = Path(path)
    if path.exists() and not overwrite:
        raise FileExistsError(f"{path} already exists; pass overwrite=True (or --rebuild) to replace it")
    path.parent.mkdir(parents=True, exist_ok=True)

    # suffix ".db" so even a leftover temp file is covered by .gitignore's "*.db"
    fd, tmp_name = tempfile.mkstemp(prefix=".shop-", suffix=".tmp.db", dir=path.parent)
    os.close(fd)
    try:
        conn = sqlite3.connect(tmp_name)
        try:
            with conn:  # one transaction: all or nothing
                _fill(conn)
        finally:
            conn.close()
        os.replace(tmp_name, path)
    except BaseException:
        Path(tmp_name).unlink(missing_ok=True)
        raise
    return path
