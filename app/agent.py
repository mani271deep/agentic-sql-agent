"""ReAct-style SQL agent: plan -> inspect -> write SQL -> run -> observe -> self-correct -> answer."""
import os
import json
from dotenv import load_dotenv
from groq import Groq
from openai import OpenAI

from app.tools import TOOL_SPECS, TOOL_FUNCTIONS
from app.schemas import Step, AgentResult

load_dotenv()

LOOP_MODEL = "llama-3.3-70b-versatile"   # Groq
FINAL_MODEL = "gpt-4o-mini"              # OpenAI
MAX_ITERATIONS = 6

PRICING = {
    "llama-3.3-70b-versatile": {"in": 0.59, "out": 0.79},
    "gpt-4o-mini":             {"in": 0.15, "out": 0.60},
}

SYSTEM_PROMPT = """You are a data analyst agent with read-only access to a SQLite e-commerce database.

Your job: answer the user's question by querying the database.

Rules:
1. ALWAYS call inspect_schema first to learn the exact tables and columns. Never guess column names.
2. Write a single SELECT query and run it with run_sql.
3. If run_sql returns an ERROR, read it carefully, fix your query, and try again.
4. Revenue = SUM(order_items.quantity * products.unit_price) via the appropriate joins.
5. Customer names are NOT unique; always GROUP BY customer_id (not name) when aggregating per customer, then show the name for display.
6. Use python_exec only for arithmetic/formatting that SQL can't easily do.
7. When you have the data needed to answer, STOP calling tools and write a short final answer.

Be efficient: don't call tools you don't need."""

def _price(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    p = PRICING.get(model, {"in": 0, "out": 0})
    return (prompt_tokens * p["in"] + completion_tokens * p["out"]) / 1_000_000

def run_agent(question: str) -> AgentResult:
    groq = Groq(api_key=os.environ["GROQ_API_KEY"])
    openai = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ]
    steps: list[Step] = []
    cost = 0.0
    tool_calls = 0
    sql_attempts = 0
    sql_errors = 0
    iterations = 0

    try:
        for _ in range(MAX_ITERATIONS):
            iterations += 1
            resp = groq.chat.completions.create(
                model=LOOP_MODEL,
                messages=messages,
                tools=TOOL_SPECS,
                tool_choice="auto",
                temperature=0,
            )
            if resp.usage:
                cost += _price(LOOP_MODEL, resp.usage.prompt_tokens,
                               resp.usage.completion_tokens)
            msg = resp.choices[0].message

            if not msg.tool_calls:
                if msg.content:
                    steps.append(Step(type="thought", content=msg.content))
                break

            messages.append({
                "role": "assistant",
                "content": msg.content or "",
                "tool_calls": [
                    {"id": tc.id, "type": "function",
                     "function": {"name": tc.function.name,
                                  "arguments": tc.function.arguments}}
                    for tc in msg.tool_calls
                ],
            })

            for tc in msg.tool_calls:
                name = tc.function.name
                raw_args = tc.function.arguments or "{}"
                try:
                    args = json.loads(raw_args)
                except (json.JSONDecodeError, TypeError):
                    args = {}
                if not isinstance(args, dict):
                    args = {}
                steps.append(Step(type="tool_call", tool=name, args=args,
                                  content=args.get("sql") or args.get("code") or ""))
                tool_calls += 1

                fn = TOOL_FUNCTIONS.get(name)
                observation = fn(**args) if fn else f"ERROR: unknown tool {name}"

                if name == "run_sql":
                    sql_attempts += 1
                    if observation.startswith("ERROR"):
                        sql_errors += 1

                steps.append(Step(type="observation", tool=name,
                                  content=observation))
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": observation,
                })

        final_resp = openai.chat.completions.create(
            model=FINAL_MODEL,
            messages=messages + [{
                "role": "user",
                "content": "Using the query results above, give a clear, concise final answer to my original question. Include the key numbers.",
            }],
            temperature=0,
        )
        if final_resp.usage:
            cost += _price(FINAL_MODEL, final_resp.usage.prompt_tokens,
                           final_resp.usage.completion_tokens)
        answer = final_resp.choices[0].message.content or "(no answer produced)"
        steps.append(Step(type="final", content=answer))

        return AgentResult(
            question=question, answer=answer, steps=steps,
            iterations=iterations, tool_calls=tool_calls,
            sql_attempts=sql_attempts, sql_errors=sql_errors,
            cost_usd=round(cost, 6),
            model_loop=LOOP_MODEL, model_final=FINAL_MODEL,
        )
    except Exception as e:
        return AgentResult(
            question=question, answer="", steps=steps,
            iterations=iterations, tool_calls=tool_calls,
            sql_attempts=sql_attempts, sql_errors=sql_errors,
            cost_usd=round(cost, 6),
            model_loop=LOOP_MODEL, model_final=FINAL_MODEL,
            error=f"{type(e).__name__}: {e}",
        )
