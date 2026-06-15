"""Tools the SQL agent can call: schema inspection, guarded SQL execution, python eval."""
import sqlite3
import io
import contextlib
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "ecommerce.db"

# --- Guardrails -------------------------------------------------------------
# Read-only agent: only single SELECT statements are allowed.
FORBIDDEN = {
    "insert", "update", "delete", "drop", "alter", "create",
    "replace", "truncate", "attach", "detach", "pragma", "vacuum",
}

def _is_safe_select(sql: str) -> tuple[bool, str]:
    stripped = sql.strip().rstrip(";").strip()
    if not stripped:
        return False, "Empty query."
    lowered = stripped.lower()
    if not lowered.startswith("select") and not lowered.startswith("with"):
        return False, "Only SELECT (or WITH...SELECT) queries are allowed."
    # Block multiple statements
    if ";" in stripped:
        return False, "Multiple statements are not allowed; submit one SELECT."
    # Block forbidden keywords as whole words
    tokens = set(lowered.replace("(", " ").replace(")", " ").split())
    hit = tokens & FORBIDDEN
    if hit:
        return False, f"Forbidden keyword(s): {', '.join(sorted(hit))}. Read-only access."
    return True, ""

# --- Tool: inspect_schema ---------------------------------------------------
def inspect_schema() -> str:
    """Return all tables, their columns/types, and 2 sample rows each."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    tables = [r[0] for r in cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()]
    out = []
    for t in tables:
        cols = cur.execute(f"PRAGMA table_info({t})").fetchall()
        col_desc = ", ".join(f"{c[1]} {c[2]}" for c in cols)
        out.append(f"TABLE {t} ({col_desc})")
        sample = cur.execute(f"SELECT * FROM {t} LIMIT 2").fetchall()
        for row in sample:
            out.append(f"    sample: {row}")
    conn.close()
    return "\n".join(out)

# --- Tool: run_sql ----------------------------------------------------------
def run_sql(sql: str) -> str:
    """Execute a read-only SELECT and return rows, or an error string the agent can learn from."""
    ok, reason = _is_safe_select(sql)
    if not ok:
        return f"ERROR: {reason}"
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()
        cur.execute(sql)
        cols = [d[0] for d in cur.description] if cur.description else []
        rows = cur.fetchmany(100)  # cap result size
        if not rows:
            return "RESULT: (0 rows returned)"
        header = " | ".join(cols)
        body = "\n".join(" | ".join(str(v) for v in r) for r in rows)
        note = f"\n(showing first 100 rows)" if len(rows) == 100 else ""
        return f"RESULT:\n{header}\n{body}{note}"
    except sqlite3.Error as e:
        return f"ERROR: {type(e).__name__}: {e}"
    finally:
        conn.close()

# --- Tool: python_exec ------------------------------------------------------
def python_exec(code: str) -> str:
    """Run a small snippet of Python for post-query math/formatting. Captures stdout."""
    buf = io.StringIO()
    safe_globals = {"__builtins__": {
        "print": print, "len": len, "sum": sum, "min": min, "max": max,
        "round": round, "sorted": sorted, "range": range, "abs": abs,
        "float": float, "int": int, "str": str, "list": list, "dict": dict,
        "enumerate": enumerate, "zip": zip,
    }}
    try:
        with contextlib.redirect_stdout(buf):
            exec(code, safe_globals, {})
        output = buf.getvalue().strip()
        return f"OUTPUT:\n{output}" if output else "OUTPUT: (no stdout)"
    except Exception as e:
        return f"ERROR: {type(e).__name__}: {e}"

# --- Tool registry: OpenAI function-calling specs ---------------------------
TOOL_SPECS = [
    {
        "type": "function",
        "function": {
            "name": "inspect_schema",
            "description": "Inspect the database: lists all tables, their columns and types, and sample rows. Call this FIRST before writing any SQL.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_sql",
            "description": "Execute a single read-only SELECT query against the SQLite database. Returns result rows or an error message. If you get an error, read it and fix your query.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sql": {"type": "string", "description": "A single SELECT statement. No INSERT/UPDATE/DELETE/DDL."}
                },
                "required": ["sql"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "python_exec",
            "description": "Run a small Python snippet for arithmetic or formatting on query results. Use print() to produce output.",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "Python code; use print() for output."}
                },
                "required": ["code"],
            },
        },
    },
]

# Dispatch map: name -> callable
TOOL_FUNCTIONS = {
    "inspect_schema": inspect_schema,
    "run_sql": run_sql,
    "python_exec": python_exec,
}
