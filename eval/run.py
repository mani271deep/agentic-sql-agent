"""Run the agent over the eval suite, check answers against ground truth, print a results table."""
import time
from eval.dataset import QUESTIONS
from app.agent import run_agent

def main():
    results = []
    print(f"\nRunning {len(QUESTIONS)} eval questions...\n")
    for item in QUESTIONS:
        t0 = time.time()
        r = run_agent(item["q"])
        elapsed = time.time() - t0
        try:
            passed = bool(item["check"](r.answer)) and not r.error
        except Exception as e:
            passed = False
            r.answer += f"  [checker error: {e}]"
        results.append({
            "id": item["id"], "passed": passed,
            "attempts": r.sql_attempts, "corrections": r.sql_errors,
            "cost": r.cost_usd, "secs": round(elapsed, 1),
        })
        print(f"  {'PASS' if passed else 'FAIL'}  {item['id']:24} "
              f"attempts={r.sql_attempts} corrections={r.sql_errors} "
              f"${r.cost_usd:.4f}  {elapsed:.1f}s")

    n = len(results)
    passed = sum(r["passed"] for r in results)
    total_cost = sum(r["cost"] for r in results)
    total_corr = sum(r["corrections"] for r in results)
    avg_attempts = sum(r["attempts"] for r in results) / n

    print("\n" + "=" * 60)
    print(f"Success rate:        {passed}/{n}  ({100*passed/n:.0f}%)")
    print(f"Avg SQL attempts:    {avg_attempts:.2f}")
    print(f"Total self-corrections observed: {total_corr}")
    print(f"Avg cost per query:  ${total_cost/n:.4f}")
    print(f"Total eval cost:     ${total_cost:.4f}")
    print("=" * 60)

if __name__ == "__main__":
    main()
