from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from typing import List

from core.models import ArtifactRecord, InputFileRecord, RunAudit, StepRecord
from core import storage


_AUDIT_LOCK = threading.Lock()


def _write_audit(run_id: str, audit: RunAudit) -> None:
    audit_path = storage.get_audit_path(run_id)
    with audit_path.open("w", encoding="utf-8") as handle:
        json.dump(audit.model_dump(mode="json"), handle, indent=2, ensure_ascii=True)


def _read_audit(run_id: str) -> RunAudit:
    audit_path = storage.get_audit_path(run_id)
    with audit_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return RunAudit.model_validate(payload)


class AuditTrailWriter:
    def create_run(
        self,
        run_id: str,
        demo_type: str,
        input_files: List[InputFileRecord],
    ) -> RunAudit:
        started_at = datetime.now(timezone.utc)
        audit = RunAudit(
            run_id=run_id,
            started_at=started_at,
            demo_type=demo_type,
            input_files=input_files,
            steps=[],
            final_summary=None,
            artifacts=[],
        )
        storage.ensure_run_dir(run_id)
        _write_audit(run_id, audit)
        storage.upsert_index_entry(run_id, demo_type, started_at, None)
        return audit

    def append_step(self, run_id: str, step: StepRecord) -> RunAudit:
        with _AUDIT_LOCK:
            audit = _read_audit(run_id)
            audit.steps.append(step)
            _write_audit(run_id, audit)
        return audit

    def finalize_run(
        self, run_id: str, final_summary: str, artifacts: List[ArtifactRecord]
    ) -> RunAudit:
        with _AUDIT_LOCK:
            audit = _read_audit(run_id)
            audit.finished_at = datetime.now(timezone.utc)
            audit.final_summary = final_summary
            audit.artifacts = artifacts
            _write_audit(run_id, audit)
            storage.upsert_index_entry(
                run_id,
                audit.demo_type,
                audit.started_at,
                audit.finished_at,
            )
        return audit

    def mark_applied(self, run_id: str, step_id: str | None = None) -> RunAudit:
        with _AUDIT_LOCK:
            audit = _read_audit(run_id)
            for step in audit.steps:
                if step_id is None and step.requires_approval:
                    step.status = "applied"
                elif step_id is not None and step.step_id == step_id:
                    step.status = "applied"
            _write_audit(run_id, audit)
        return audit


class AuditTrailReader:
    def load_run(self, run_id: str) -> RunAudit:
        return _read_audit(run_id)
