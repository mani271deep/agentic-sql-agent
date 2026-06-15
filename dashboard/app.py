"""Streamlit dashboard for the Agentic SQL Analyst."""
import os
import requests
import streamlit as st

# Point at local FastAPI by default; override via env var for deployment.
API_URL = os.environ.get("AGENT_API_URL", "http://127.0.0.1:8000")

st.set_page_config(page_title="Agentic SQL Analyst", page_icon="🧮", layout="wide")

st.title("🧮 Agentic SQL Analyst")
st.caption("Ask a question in plain English. The agent inspects the schema, "
           "writes SQL, runs it, self-corrects on errors, and explains the answer.")

EXAMPLES = [
    "Which product categories drove the most revenue? Show the top 3.",
    "Who are our top 5 customers by total amount spent, and which country is each from?",
    "What was our total completed-order revenue in the last 30 days?",
    "How many orders were cancelled, by country?",
]

with st.sidebar:
    st.header("Try an example")
    for ex in EXAMPLES:
        if st.button(ex, use_container_width=True):
            st.session_state["question"] = ex
    st.divider()
    st.caption(f"API: {API_URL}")

question = st.text_input(
    "Your question",
    value=st.session_state.get("question", EXAMPLES[0]),
)

run = st.button("Run agent", type="primary")

def render_step(i, step):
    t = step["type"]
    if t == "tool_call":
        with st.expander(f"🔧 Step {i}: call `{step['tool']}`", expanded=True):
            if step.get("content"):
                st.code(step["content"], language="sql"
                        if step["tool"] == "run_sql" else "python")
            else:
                st.write("_(no arguments)_")
    elif t == "observation":
        is_error = step["content"].startswith("ERROR")
        with st.expander(
            f"{'❌' if is_error else '👁️'} Step {i}: observation from `{step['tool']}`"
            f"{'  — self-correcting' if is_error else ''}",
            expanded=is_error,
        ):
            st.code(step["content"], language="text")
    elif t == "thought":
        with st.expander(f"💭 Step {i}: reasoning", expanded=False):
            st.write(step["content"])
    elif t == "final":
        st.success("Final answer")
        st.markdown(step["content"])

if run and question.strip():
    with st.spinner("Agent working..."):
        try:
            resp = requests.post(f"{API_URL}/run",
                                 json={"question": question}, timeout=120)
            resp.raise_for_status()
            result = resp.json()
        except Exception as e:
            st.error(f"Request failed: {e}")
            st.stop()

    if result.get("error"):
        st.error(f"Agent error: {result['error']}")

    # Metrics row
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Iterations", result["iterations"])
    c2.metric("SQL attempts", result["sql_attempts"])
    c3.metric("Self-corrections", result["sql_errors"])
    c4.metric("Cost (USD)", f"${result['cost_usd']:.4f}")

    st.subheader("Agent trace")
    for i, step in enumerate(result["steps"], 1):
        render_step(i, step)

    st.divider()
    st.caption(f"Loop model: {result['model_loop']}  •  "
               f"Final model: {result['model_final']}")
