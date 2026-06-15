"""Smoke-test each tool in isolation."""
from app.tools import inspect_schema, run_sql, python_exec, _is_safe_select

def main():
    print("=== inspect_schema ===")
    print(inspect_schema()[:400], "...\n")

    print("=== run_sql (valid) ===")
    print(run_sql("SELECT category, COUNT(*) FROM products GROUP BY category"), "\n")

    print("=== run_sql (bad column -> error the agent can learn from) ===")
    print(run_sql("SELECT nonexistent_col FROM products"), "\n")

    print("=== run_sql (blocked write) ===")
    print(run_sql("DELETE FROM products WHERE product_id = 1"), "\n")

    print("=== run_sql (blocked multi-statement) ===")
    print(run_sql("SELECT 1; SELECT 2"), "\n")

    print("=== python_exec ===")
    print(python_exec("print(round(1234.5678, 2))"), "\n")

    print("=== guard unit checks ===")
    for q in ["SELECT 1", "WITH x AS (SELECT 1) SELECT * FROM x",
              "DROP TABLE products", "update products set unit_price=0"]:
        ok, reason = _is_safe_select(q)
        print(f"  {ok!s:5} | {q[:40]} | {reason}")

if __name__ == "__main__":
    main()
