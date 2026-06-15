# Agentic SQL Analyst

A natural-language data analyst agent. Ask a question in plain English; the agent inspects the database schema, writes SQL, executes it, **self-corrects when a query errors**, and explains the answer in plain language — returning a full step-by-step trace of its reasoning.

**Live demo:** [Streamlit dashboard](https://agentic-sql-agent-9wteiy2gx7mfvix5zgxjbc.streamlit.app/) · **API:** [https://agentic-sql-agent.onrender.com/docs](https://agentic-sql-agent.onrender.com/docs)

---

## The problem

Non-technical stakeholders constantly need answers from a database but can't write SQL, and analysts get buried under ad-hoc "can you just pull…" requests. A single LLM call writing SQL blind frequently produces queries that reference nonexistent columns, miss a join, or simply don't run — and it has no way to know it failed.

## The solution

An agent that closes that gap with a **plan → act → observe → correct** loop. It always inspects the real schema before writing SQL, runs the query against the database, *reads the actual error or result*, and revises until it has a correct answer. The run-observe-fix loop is what separates this from a one-shot prompt.

This is Project 3 in a portfolio arc. Where the prior project (a multi-model LLM router) made a single routing decision, this project demonstrates **multi-step planning, tool use, and self-correction**.

---

## How it works

```
User question
     │
     ▼
┌─────────────────────────────────────────────┐
│  ReAct loop  (Groq llama-3.3-70b, temp 0)    │
│                                               │
│   1. inspect_schema   → learn real columns    │
│   2. run_sql          → execute SELECT         │
│   3. observe result / error                    │
│   4. if error: read it, fix query, retry       │
│   5. repeat until answered (max 6 iterations)  │
└─────────────────────────────────────────────┘
     │
     ▼
Final synthesis  (OpenAI gpt-4o-mini)  → plain-language answer
     │
     ▼
{ answer, full step trace, metrics, cost }
```

**Tools the agent can call**

| Tool | Purpose |
|------|---------|
| `inspect_schema` | Lists tables, columns, types, and sample rows. Always called first. |
| `run_sql` | Executes a single **read-only** `SELECT`. Returns rows or an error string the agent learns from. |
| `python_exec` | Sandboxed Python for arithmetic/formatting SQL can't easily do. |

**Model split (cost strategy).** A fast, cheap Groq model drives the tool-calling loop; OpenAI handles the final user-facing synthesis. This keeps cost per query in the fraction-of-a-cent range while preserving answer quality.

**Safety.** The agent is strictly read-only — `run_sql` rejects anything that isn't a single `SELECT`/`WITH…SELECT`, blocks `INSERT`/`UPDATE`/`DELETE`/DDL and multi-statement queries, and caps result size.

---

## Self-correction in action

The agent's defining behavior is recovering from its own mistakes. A real trace from the eval suite:

```
Q: What's the sales total for completed purchases made in the past 30 days?

[run_sql]  SELECT ... WHERE o.order_status = 'completed' AND ...
[observe]  ERROR: no such column: o.order_status      ← agent guessed wrong
[run_sql]  SELECT ... WHERE o.status = 'completed' AND ...
[observe]  RESULT: 59898.65                            ← read error, fixed, succeeded
```

The agent saw the error, identified the wrong column name, and corrected it without intervention.

---

## Evaluation

Following the LLM-as-judge / ground-truth methodology from the prior project, each eval question has a checker that validates the agent's answer against ground truth computed directly from the database — so success is objective, not subjective.

| Metric | Result |
|--------|--------|
| Task success rate | **6 / 6 (100%)** |
| Avg SQL attempts per query | 1.0–1.2 |
| Self-correction demonstrated | Yes (live, on date/column-ambiguity questions) |
| Avg cost per query | **~$0.0015** |

The suite includes deliberately ambiguous questions ("top buyers", "sales total") that force the agent to map fuzzy business language onto the real schema — which is where self-correction tends to fire.

**Data-quality gotchas surfaced and handled during development**

- **Non-unique customer names.** Aggregating spend by `name` merged distinct customers; the agent now groups by `customer_id` and shows the name only for display.
- **Ambiguous date boundaries.** "Past 30 days" is inclusive-or-exclusive ambiguous; the eval accepts either defensible interpretation.

```bash
python -m eval.run
```

---

## Tech stack

- **Agent:** ReAct loop over OpenAI function-calling; Groq (`llama-3.3-70b-versatile`) for the loop, OpenAI (`gpt-4o-mini`) for synthesis
- **Backend:** FastAPI on Render
- **Frontend:** Streamlit on Streamlit Cloud
- **Database:** SQLite (e-commerce schema: customers, products, orders, order_items), seeded on each deploy

---

## Run locally

```bash
# clone and enter
git clone https://github.com/mani271deep/agentic-sql-agent.git
cd agentic-sql-agent

# environment
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# keys
cp .env.example .env          # then add your OPENAI_API_KEY and GROQ_API_KEY

# build the sample database
python data/seed.py

# run the agent from the CLI
python -m app.run_cli "Which product categories drove the most revenue? Show the top 3."

# run the eval suite
python -m eval.run

# serve the API
python -m uvicorn app.main:app --reload --port 8000

# run the dashboard (in a second terminal, with the API running)
python -m streamlit run dashboard/app.py
```

> **Note:** the live backend runs on Render's free tier, which sleeps after ~15 min of inactivity. The first request after idle may take 30–50 seconds to wake the service.

---

## Project structure

```
agentic-sql-agent/
├── app/
│   ├── agent.py        # ReAct loop + model split + cost tracking
│   ├── tools.py        # inspect_schema, run_sql (read-only guard), python_exec
│   ├── schemas.py      # pydantic models for agent I/O
│   ├── main.py         # FastAPI: /run, /health
│   └── run_cli.py      # terminal runner with full trace printout
├── dashboard/
│   └── app.py          # Streamlit: trace view + metrics
├── data/
│   └── seed.py         # builds the sample e-commerce SQLite DB
├── eval/
│   ├── dataset.py      # questions + ground-truth checkers
│   └── run.py          # eval runner + results summary
├── tests/
│   └── test_tools.py   # tool smoke tests
├── render.yaml         # Render deploy config
├── runtime.txt         # pinned Python version
└── requirements.txt
```

---

## API

`POST /run`

```json
{ "question": "Who are our top 5 customers by total amount spent?" }
```

Returns the final answer plus the complete step trace, iteration/attempt counts, self-correction count, and cost in USD.
