"""FastAPI backend exposing the SQL agent."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.agent import run_agent
from app.schemas import AgentResult

app = FastAPI(title="Agentic SQL Analyst", version="1.0.0")

# Allow the Streamlit dashboard (any origin for the demo) to call this.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class RunRequest(BaseModel):
    question: str

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/run", response_model=AgentResult)
def run(req: RunRequest):
    return run_agent(req.question)
