"""Run the agent from the terminal and print the full trace."""
import sys
from app.agent import run_agent

def main():
    question = " ".join(sys.argv[1:]) or "Which product categories drove the most revenue? Show the top 3."
    print(f"\nQUESTION: {question}\n" + "=" * 60)
    result = run_agent(question)

    for s in result.steps:
        if s.type == "thought":
            print(f"\n[THOUGHT] {s.content}")
        elif s.type == "tool_call":
            print(f"\n[TOOL CALL] {s.tool}")
            if s.content:
                print(f"  -> {s.content}")
        elif s.type == "observation":
            preview = s.content if len(s.content) < 500 else s.content[:500] + " ..."
            print(f"[OBSERVATION]\n{preview}")
        elif s.type == "final":
            print(f"\n[FINAL ANSWER]\n{s.content}")

    print("\n" + "=" * 60)
    if result.error:
        print(f"ERROR: {result.error}")
    print(f"iterations={result.iterations}  tool_calls={result.tool_calls}  "
          f"sql_attempts={result.sql_attempts}  self_corrections={result.sql_errors}  "
          f"cost=${result.cost_usd}")

if __name__ == "__main__":
    main()
