from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


Severity = Literal["info", "low", "medium", "high"]
StepStatus = Literal["done", "needs_approval", "applied", "skipped", "failed"]


class InputFileRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    path: str
    hash: str


class ArtifactRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str
    path: str


class StepRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    step_id: str = Field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    title: str
    action: str
    severity: Severity
    evidence: List[str] = Field(default_factory=list)
    decision: str
    requires_approval: bool
    status: StepStatus
    duration_ms: int = 0


class RunAudit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    started_at: datetime
    finished_at: Optional[datetime] = None
    demo_type: str
    input_files: List[InputFileRecord]
    steps: List[StepRecord] = Field(default_factory=list)
    final_summary: Optional[str] = None
    artifacts: List[ArtifactRecord] = Field(default_factory=list)
