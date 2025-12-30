from __future__ import annotations

from pathlib import Path

from core.audit import AuditTrailReader, AuditTrailWriter
from core.models import ArtifactRecord, InputFileRecord, StepRecord


def _create_input_file(tmp_path: Path) -> Path:
    path = tmp_path / "input.csv"
    path.write_text("id,value\n1,10\n", encoding="utf-8")
    return path


def test_create_run_creates_audit_json(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    input_file = _create_input_file(tmp_path)
    writer = AuditTrailWriter()
    run_id = "run-1"
    writer.create_run(
        run_id=run_id,
        demo_type="ticket",
        input_files=[InputFileRecord(name="tickets", path=str(input_file), hash="abc")],
    )
    audit_path = tmp_path / "runs" / run_id / "audit.json"
    assert audit_path.exists()


def test_append_step_adds_step(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    input_file = _create_input_file(tmp_path)
    writer = AuditTrailWriter()
    run_id = "run-2"
    writer.create_run(
        run_id=run_id,
        demo_type="ticket",
        input_files=[InputFileRecord(name="tickets", path=str(input_file), hash="abc")],
    )
    step = StepRecord(
        title="Check",
        action="CHECK",
        severity="info",
        evidence=["ok"],
        decision="done",
        requires_approval=False,
        status="done",
        duration_ms=5,
    )
    writer.append_step(run_id, step)
    audit = AuditTrailReader().load_run(run_id)
    assert len(audit.steps) == 1


def test_finalize_updates_summary_and_artifacts(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    input_file = _create_input_file(tmp_path)
    writer = AuditTrailWriter()
    run_id = "run-3"
    writer.create_run(
        run_id=run_id,
        demo_type="ticket",
        input_files=[InputFileRecord(name="tickets", path=str(input_file), hash="abc")],
    )
    artifacts = [ArtifactRecord(type="pdf", path="report.pdf")]
    writer.finalize_run(run_id, "summary", artifacts)
    audit = AuditTrailReader().load_run(run_id)
    assert audit.final_summary == "summary"
    assert len(audit.artifacts) == 1


def test_mark_applied_updates_status(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    input_file = _create_input_file(tmp_path)
    writer = AuditTrailWriter()
    run_id = "run-4"
    writer.create_run(
        run_id=run_id,
        demo_type="ticket",
        input_files=[InputFileRecord(name="tickets", path=str(input_file), hash="abc")],
    )
    step = StepRecord(
        title="Needs approval",
        action="APPROVAL",
        severity="low",
        evidence=[],
        decision="pending",
        requires_approval=True,
        status="needs_approval",
        duration_ms=0,
    )
    writer.append_step(run_id, step)
    writer.mark_applied(run_id)
    audit = AuditTrailReader().load_run(run_id)
    assert audit.steps[0].status == "applied"
