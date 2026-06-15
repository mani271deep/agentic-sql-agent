"""Pydantic models for agent I/O."""
from pydantic import BaseModel
from typing import Any, Optional

class Step(BaseModel):
    type: str                      # "thought" | "tool_call" | "observation" | "final"
    tool: Optional[str] = None
    args: Optional[dict[str, Any]] = None
    content: str = ""

class AgentResult(BaseModel):
    question: str
    answer: str
    steps: list[Step]
    iterations: int
    tool_calls: int
    sql_attempts: int
    sql_errors: int           # self-corrections triggered by SQL errors
    cost_usd: float
    model_loop: str
    model_final: str
    error: Optional[str] = None
