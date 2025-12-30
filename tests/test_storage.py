from __future__ import annotations

from pathlib import Path

from core import storage
from core.audit import AuditTrailWriter
from core.models import InputFileRecord


def _create_input(tmp_path: Path) -> Path:
    path = tmp_path / "input.csv"
    path.write_text("id,value\n1,10\n", encoding="utf-8")
    return path


def test_list_runs_returns_entries(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    writer = AuditTrailWriter()
    input_file = _create_input(tmp_path)
    writer.create_run(
        run_id="run-storage-1",
        demo_type="ticket",
        input_files=[InputFileRecord(name="tickets", path=str(input_file), hash="abc")],
    )
    runs = storage.list_runs()
    assert runs
    assert runs[0]["run_id"] == "run-storage-1"


def test_load_run_reads_audit(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    writer = AuditTrailWriter()
    input_file = _create_input(tmp_path)
    writer.create_run(
        run_id="run-storage-2",
        demo_type="ticket",
        input_files=[InputFileRecord(name="tickets", path=str(input_file), hash="abc")],
    )
    audit = storage.load_run("run-storage-2")
    assert audit.run_id == "run-storage-2"


def test_delete_run_removes_directory(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    writer = AuditTrailWriter()
    input_file = _create_input(tmp_path)
    run_id = "run-storage-3"
    writer.create_run(
        run_id=run_id,
        demo_type="ticket",
        input_files=[InputFileRecord(name="tickets", path=str(input_file), hash="abc")],
    )
    run_dir = storage.get_runs_dir() / run_id
    assert run_dir.exists()
    storage.delete_run(run_id)
    assert not run_dir.exists()
    assert storage.list_runs() == []


def test_clear_runs_removes_all(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    writer = AuditTrailWriter()
    input_file = _create_input(tmp_path)
    writer.create_run(
        run_id="run-storage-4",
        demo_type="ticket",
        input_files=[InputFileRecord(name="tickets", path=str(input_file), hash="abc")],
    )
    writer.create_run(
        run_id="run-storage-5",
        demo_type="ticket",
        input_files=[InputFileRecord(name="tickets", path=str(input_file), hash="abc")],
    )
    storage.clear_runs()
    assert storage.list_runs() == []
