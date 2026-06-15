"""Eval questions. Each has a checker that validates the agent's answer against ground truth
computed directly from the DB, so success is objective, not vibes."""
import sqlite3
from pathlib import Path

DB = Path(__file__).parent.parent / "data" / "ecommerce.db"

def _scalar(sql):
    conn = sqlite3.connect(DB)
    try:
        return conn.execute(sql).fetchone()[0]
    finally:
        conn.close()

def _rows(sql):
    conn = sqlite3.connect(DB)
    try:
        return conn.execute(sql).fetchall()
    finally:
        conn.close()

def _has_number(answer: str, value: float, tol: float = 0.01) -> bool:
    """True if a number close to `value` appears in the answer (ignoring commas/$)."""
    import re
    nums = re.findall(r"[-+]?\d[\d,]*\.?\d*", answer.replace("$", ""))
    for n in nums:
        try:
            if abs(float(n.replace(",", "")) - value) <= max(tol, abs(value) * 0.01):
                return True
        except ValueError:
            continue
    return False

def _has_text(answer: str, needle: str) -> bool:
    return needle.lower() in answer.lower()

# Ground truth, computed live so it always matches the seeded DB.
TOP_CATEGORY = _rows("""
    SELECT p.category, SUM(oi.quantity*p.unit_price) rev
    FROM order_items oi JOIN products p ON oi.product_id=p.product_id
    GROUP BY p.category ORDER BY rev DESC LIMIT 1
""")[0]

TOP_CUSTOMER = _rows("""
    SELECT c.name, SUM(oi.quantity*p.unit_price) total
    FROM customers c JOIN orders o ON c.customer_id=o.customer_id
    JOIN order_items oi ON o.order_id=oi.order_id
    JOIN products p ON oi.product_id=p.product_id
    GROUP BY c.customer_id ORDER BY total DESC LIMIT 1
""")[0]

CANCELLED = _scalar("SELECT COUNT(*) FROM orders WHERE status='cancelled'")
NUM_CUSTOMERS = _scalar("SELECT COUNT(*) FROM customers")

QUESTIONS = [
    {
        "id": "top_category",
        "q": "Which product category generated the most revenue? Name it and the amount.",
        "check": lambda a: _has_text(a, TOP_CATEGORY[0]) and _has_number(a, TOP_CATEGORY[1]),
    },
    {
        "id": "top_customer",
        "q": "Who is the single highest-spending customer, and how much did they spend?",
        "check": lambda a: _has_text(a, TOP_CUSTOMER[0]) and _has_number(a, TOP_CUSTOMER[1]),
    },
    {
        "id": "cancelled_count",
        "q": "How many orders have a cancelled status?",
        "check": lambda a: _has_number(a, CANCELLED),
    },
    {
        "id": "customer_count",
        "q": "How many customers are in the database?",
        "check": lambda a: _has_number(a, NUM_CUSTOMERS),
    },
    # --- Deliberately tricky: ambiguous wording to exercise self-correction ---
    {
        "id": "tricky_buyers",
        "q": "List the top 3 buyers by how much money they have spent in total.",
        # 'buyers' isn't a table; agent must map to customers + the spend join.
        "check": lambda a: sum(_has_text(a, r[0]) for r in _rows("""
            SELECT c.name FROM customers c JOIN orders o ON c.customer_id=o.customer_id
            JOIN order_items oi ON o.order_id=oi.order_id
            JOIN products p ON oi.product_id=p.product_id
            GROUP BY c.customer_id ORDER BY SUM(oi.quantity*p.unit_price) DESC LIMIT 3
        """)) >= 2,
    },
    {
        "id": "tricky_revenue_month",
        "q": "What's the sales total for completed purchases made in the past 30 days?",
        # 'past 30 days' boundary is ambiguous (inclusive vs exclusive), so accept either.
        "check": lambda a: any(_has_number(a, _scalar(f"""
            SELECT SUM(oi.quantity*p.unit_price) FROM orders o
            JOIN order_items oi ON o.order_id=oi.order_id
            JOIN products p ON oi.product_id=p.product_id
            WHERE o.status='completed' AND o.order_date {op} DATE('now','-30 days')
        """)) for op in (">=", ">")),
    },
]
