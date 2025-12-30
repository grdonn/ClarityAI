from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

from core.models import ArtifactRecord, StepRecord


@dataclass
class AnalysisResult:
    steps: List[StepRecord]
    final_summary: str
    artifacts: List[ArtifactRecord]
    recommendations: List[dict]


class BasePlugin(ABC):
    name: str
    description: str
    expected_inputs: List[str]

    @abstractmethod
    def analyze(self, inputs: Dict[str, Path], llm, run_id: str) -> AnalysisResult:
        raise NotImplementedError

    @abstractmethod
    def apply(self, inputs: Dict[str, Path], recommendations: List[dict], run_id: str) -> List[ArtifactRecord]:
        raise NotImplementedError
