from __future__ import annotations

from pathlib import Path

import pytest

from core.engine import Engine
from core import storage

class FailingPlugin:
    name = "failing"
    description = "Fails on analyze"
    expected_inputs = ["tickets"]

    def analyze(self, inputs, llm, run_id):
        raise RuntimeError("boom")

    def apply(self, inputs, recommendations, run_id):
        return []


def _create_input_file(tmp_path: Path) -> Path:
    path = tmp_path / "tickets.csv"
    path.write_text("ticket_id,created_at,channel,customer_text\n1,2024-01-01,email,test\n", encoding="utf-8")
    return path


def test_engine_failure_records_failed_step(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    input_file = _create_input_file(tmp_path)
    engine = Engine(registry={"ticket": FailingPlugin()})
    with pytest.raises(RuntimeError):
        engine.run("ticket", {"tickets": input_file})
    runs = storage.list_runs()
    assert len(runs) == 1
    run_id = runs[0]["run_id"]
    audit = storage.load_run(run_id)
    assert any(step.status == "failed" for step in audit.steps)
