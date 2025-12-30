from __future__ import annotations

import hashlib
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Dict, List
from uuid import uuid4

from core.audit import AuditTrailWriter
from core.llm import get_default_llm
from core.models import ArtifactRecord, InputFileRecord, StepRecord
from core import storage


@dataclass
class RunResult:
    run_id: str
    summary: str
    artifacts: List[ArtifactRecord]


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _build_input_records(inputs: Dict[str, Path]) -> List[InputFileRecord]:
    records: List[InputFileRecord] = []
    for name, path in inputs.items():
        path = Path(path)
        records.append(
            InputFileRecord(name=name, path=str(path), hash=_hash_file(path))
        )
    return records


class Engine:
    def __init__(self, registry: Dict[str, object] | None = None) -> None:
        from plugins.ticket_triage.plugin import TicketTriagePlugin
        from plugins.edocument_audit.plugin import EDocumentAuditPlugin

        self.registry = registry or {
            "ticket": TicketTriagePlugin(),
            "edoc": EDocumentAuditPlugin(),
        }
        self.audit_writer = AuditTrailWriter()
        self.llm = get_default_llm()

    def run(
        self,
        demo_type: str,
        inputs: Dict[str, Path],
        run_id: str | None = None,
    ) -> RunResult:
        if demo_type not in self.registry:
            raise ValueError(f"Unknown demo_type: {demo_type}")

        run_id = run_id or str(uuid4())
        input_records = _build_input_records(inputs)
        self.audit_writer.create_run(run_id, demo_type, input_records)

        plugin = self.registry[demo_type]
        try:
            result = plugin.analyze(inputs=inputs, llm=self.llm, run_id=run_id)
            if result.recommendations is not None:
                rec_path = storage.ensure_run_dir(run_id) / "recommendations.json"
                with rec_path.open("w", encoding="utf-8") as handle:
                    json.dump(result.recommendations, handle, indent=2, ensure_ascii=True)
            for step in result.steps:
                self.audit_writer.append_step(run_id, step)
            self.audit_writer.finalize_run(
                run_id, result.final_summary, result.artifacts
            )
            return RunResult(run_id=run_id, summary=result.final_summary, artifacts=result.artifacts)
        except Exception as exc:  # pragma: no cover - defensive path
            failed_step = StepRecord(
                title="Çalıştırma başarısız",
                action="RUN_FAILED",
                severity="high",
                evidence=[str(exc)],
                decision="Hata nedeniyle çalışma durduruldu",
                requires_approval=False,
                status="failed",
                duration_ms=0,
            )
            self.audit_writer.append_step(run_id, failed_step)
            self.audit_writer.finalize_run(run_id, f"Run failed: {exc}", [])
            raise
