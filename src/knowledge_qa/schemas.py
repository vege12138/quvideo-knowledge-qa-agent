from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

Status = Literal["answered", "clarification_required", "insufficient_evidence", "tool_error", "incomplete"]


class Citation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    doc_id: str
    chunk_id: str
    quote: str = Field(min_length=1)


class Answer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    answer: str = Field(min_length=1)
    status: Status
    clarification_reason: Literal["conflict", "missing_context"] | None = None
    citations: list[Citation] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)


class HistoryMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=12000)


class TraceEvent(BaseModel):
    step: int
    event: str
    data: dict = Field(default_factory=dict)


class QAResult(Answer):
    run_id: str
    mode: Literal["real", "mock"]
    reason_code: str = ""
    trace: list[TraceEvent] = Field(default_factory=list)
    metrics: dict = Field(default_factory=dict)

