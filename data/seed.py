"""Seed a realistic e-commerce SQLite database for the SQL agent."""
import sqlite3
import random
from datetime import date, timedelta
from pathlib import Path

DB_PATH = Path(__file__).parent / "ecommerce.db"

SCHEMA = """
DROP TABLE IF EXISTS order_items;
DROP TABLE IF EXISTS orders;
DROP TABLE IF EXISTS products;
DROP TABLE IF EXISTS customers;

CREATE TABLE customers (
    customer_id   INTEGER PRIMARY KEY,
    name          TEXT NOT NULL,
    email         TEXT NOT NULL,
    country       TEXT NOT NULL,
    signup_date   DATE NOT NULL
);

CREATE TABLE products (
    product_id    INTEGER PRIMARY KEY,
    name          TEXT NOT NULL,
    category      TEXT NOT NULL,
    unit_price    REAL NOT NULL
);

CREATE TABLE orders (
    order_id      INTEGER PRIMARY KEY,
    customer_id   INTEGER NOT NULL,
    order_date    DATE NOT NULL,
    status        TEXT NOT NULL,
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
);

CREATE TABLE order_items (
    order_item_id INTEGER PRIMARY KEY,
    order_id      INTEGER NOT NULL,
    product_id    INTEGER NOT NULL,
    quantity      INTEGER NOT NULL,
    FOREIGN KEY (order_id) REFERENCES orders(order_id),
    FOREIGN KEY (product_id) REFERENCES products(product_id)
);
"""

COUNTRIES = ["USA", "UK", "Germany", "India", "Canada", "Australia", "France"]
CATEGORIES = {
    "Electronics": [("Wireless Earbuds", 79.99), ("Laptop Stand", 34.99),
                    ("USB-C Hub", 49.99), ("Mechanical Keyboard", 119.99),
                    ("4K Monitor", 329.99)],
    "Home & Kitchen": [("Espresso Machine", 249.99), ("Air Fryer", 99.99),
                       ("Knife Set", 89.99), ("Blender", 59.99)],
    "Apparel": [("Running Shoes", 109.99), ("Rain Jacket", 79.99),
                ("Wool Socks 3-Pack", 24.99), ("Backpack", 64.99)],
    "Books": [("SQL in Practice", 39.99), ("System Design Primer", 44.99),
              ("Cooking Basics", 29.99)],
    "Sports": [("Yoga Mat", 29.99), ("Dumbbell Set", 149.99),
               ("Water Bottle", 19.99)],
}

def seed():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.executescript(SCHEMA)

    random.seed(42)
    today = date.today()

    # Customers (signed up over the last ~2 years)
    customers = []
    first_names = ["Alex", "Sam", "Jordan", "Maria", "Liam", "Noah", "Olivia",
                   "Emma", "Raj", "Priya", "Chen", "Sofia", "Lucas", "Mia", "Ben"]
    last_names = ["Smith", "Patel", "Garcia", "Kim", "Müller", "Brown", "Singh",
                  "Lopez", "Wang", "Dubois", "Rossi", "Khan", "Nguyen", "Clark"]
    for cid in range(1, 201):
        name = f"{random.choice(first_names)} {random.choice(last_names)}"
        email = f"user{cid}@example.com"
        country = random.choice(COUNTRIES)
        signup = today - timedelta(days=random.randint(0, 730))
        customers.append((cid, name, email, country, signup.isoformat()))
    cur.executemany("INSERT INTO customers VALUES (?,?,?,?,?)", customers)

    # Products
    products = []
    pid = 1
    for category, items in CATEGORIES.items():
        for pname, price in items:
            products.append((pid, pname, category, price))
            pid += 1
    cur.executemany("INSERT INTO products VALUES (?,?,?,?)", products)
    product_ids = [p[0] for p in products]

    # Orders + items over the last 180 days (so "last quarter" questions work)
    statuses = ["completed", "completed", "completed", "shipped", "cancelled"]
    orders = []
    items = []
    oid = 1
    item_id = 1
    for _ in range(1200):
        cid = random.randint(1, 200)
        odate = today - timedelta(days=random.randint(0, 180))
        status = random.choice(statuses)
        orders.append((oid, cid, odate.isoformat(), status))
        for _ in range(random.randint(1, 4)):
            items.append((item_id, oid, random.choice(product_ids),
                          random.randint(1, 3)))
            item_id += 1
        oid += 1
    cur.executemany("INSERT INTO orders VALUES (?,?,?,?)", orders)
    cur.executemany("INSERT INTO order_items VALUES (?,?,?,?)", items)

    conn.commit()

    # Quick sanity print
    for tbl in ["customers", "products", "orders", "order_items"]:
        n = cur.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
        print(f"  {tbl}: {n} rows")
    conn.close()
    print(f"Seeded {DB_PATH}")

if __name__ == "__main__":
    seed()
